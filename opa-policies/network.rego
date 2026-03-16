package zta.network

import rego.v1

# Network VLAN management policy — enforces group-based authorization.
#
# Workshop Section 4 uses this policy:
#   A network engineer (not in network-admins) is denied.
#   A network admin (in network-admins) is allowed and updates CMDB.

default allow := false

allow if {
	condition_user_authorized
	condition_valid_vlan
	condition_action_permitted
}

# User must be in the network-admins group
condition_user_authorized if {
	some group in input.user_groups
	group == "network-admins"
}

# VLAN ID must be in the permitted range (100-999, excluding reserved)
condition_valid_vlan if {
	input.vlan_id >= 100
	input.vlan_id <= 999
}

# Only specific actions are allowed
permitted_actions := {"create_vlan", "modify_vlan", "delete_vlan", "assign_port"}

condition_action_permitted if {
	permitted_actions[input.action]
}

decision := {
	"allow": allow,
	"user": input.user,
	"action": input.action,
	"vlan_id": input.vlan_id,
	"conditions": {
		"user_authorized": condition_user_authorized,
		"valid_vlan": condition_valid_vlan,
		"action_permitted": condition_action_permitted,
	},
	"reason": reason,
}

default reason := "all conditions met"

reason := msg if {
	not condition_user_authorized
	msg := sprintf("DENIED: user '%s' is not a member of network-admins group", [input.user])
}

reason := msg if {
	condition_user_authorized
	not condition_valid_vlan
	msg := sprintf("DENIED: VLAN ID %d is outside the permitted range (100-999)", [input.vlan_id])
}

reason := msg if {
	condition_user_authorized
	condition_valid_vlan
	not condition_action_permitted
	msg := sprintf("DENIED: action '%s' is not permitted", [input.action])
}
