package aap.gateway

import rego.v1

# AAP Platform Policy — evaluated by the AAP Controller BEFORE a job launches.
#
# This is the OUTER defence ring:
#   "Is this user allowed to launch this job template at all?"
#
# The in-playbook OPA checks (zta.network, zta.patching, etc.) are the
# INNER ring, which validate runtime parameters like VLAN IDs and SPIFFE IDs.
#
# AAP sends a POST to OPA with:
#   input.user        — username, groups, is_superuser
#   input.action      — "launch", "update", "delete", etc.
#   input.resource    — job template name, type, inventory
#   input.extra_vars  — survey/extra variables passed to the job

default allow := false

# ── Superusers bypass all checks ────────────────────────────────────

allow if {
	input.user.is_superuser
}

# ── Network job templates ───────────────────────────────────────────
# Only network-admins may launch any template with "VLAN" or "Network"
# in the name.

allow if {
	input.action == "launch"
	is_network_template
	user_in_group("network-admins")
}

is_network_template if contains(lower(input.resource.name), "vlan")
is_network_template if contains(lower(input.resource.name), "network")

# ── Patching job templates ──────────────────────────────────────────
# Only patch-admins may launch patching templates.

allow if {
	input.action == "launch"
	is_patching_template
	user_in_group("patch-admins")
}

is_patching_template if contains(lower(input.resource.name), "patch")

# ── Database / application job templates ────────────────────────────
# Only app-deployers may launch DB credential or deploy templates.

allow if {
	input.action == "launch"
	is_app_template
	user_in_group("app-deployers")
}

is_app_template if contains(lower(input.resource.name), "database")
is_app_template if contains(lower(input.resource.name), "credential")
is_app_template if contains(lower(input.resource.name), "deploy")
is_app_template if contains(lower(input.resource.name), "application")

# ── Verification / read-only templates ──────────────────────────────
# Anyone authenticated can run verification and test templates.

allow if {
	input.action == "launch"
	is_readonly_template
	input.user.username != ""
}

is_readonly_template if contains(lower(input.resource.name), "verify")
is_readonly_template if contains(lower(input.resource.name), "test")
is_readonly_template if contains(lower(input.resource.name), "check")
is_readonly_template if contains(lower(input.resource.name), "list")

# ── Non-launch actions (view, cancel) ──────────────────────────────
# Authenticated users can view and cancel their own jobs.

allow if {
	input.action != "launch"
	input.user.username != ""
}

# ── Helper ──────────────────────────────────────────────────────────

user_in_group(group) if {
	some g in input.user.groups
	g == group
}

# ── Decision object ─────────────────────────────────────────────────

decision := {
	"allow": allow,
	"user": input.user.username,
	"action": input.action,
	"template": object.get(input.resource, "name", "unknown"),
	"reason": reason,
}

default reason := "all conditions met — job launch permitted"

reason := msg if {
	not allow
	input.action == "launch"
	is_network_template
	msg := sprintf("DENIED at platform level: user '%s' is not in network-admins — cannot launch network templates", [input.user.username])
}

reason := msg if {
	not allow
	input.action == "launch"
	is_patching_template
	msg := sprintf("DENIED at platform level: user '%s' is not in patch-admins — cannot launch patching templates", [input.user.username])
}

reason := msg if {
	not allow
	input.action == "launch"
	is_app_template
	msg := sprintf("DENIED at platform level: user '%s' is not in app-deployers — cannot launch application templates", [input.user.username])
}

reason := msg if {
	not allow
	input.action == "launch"
	not is_network_template
	not is_patching_template
	not is_app_template
	not is_readonly_template
	msg := sprintf("DENIED at platform level: no policy grants user '%s' access to template '%s'", [input.user.username, input.resource.name])
}
