# Section 4 — SPIFFE-Verified, RBAC-Controlled Network VLAN Management

## Objective

Demonstrate **defence in depth** for network automation: a VLAN change must be
authorised by **both** a verified workload identity (SPIFFE) and an authorised
user identity (IdM). Two OPA policy rings evaluate both layers before the
Arista switches are touched and the CMDB updated.

## Zero Trust Principles

| Principle | How This Section Demonstrates It |
|-----------|----------------------------------|
| **Defence in depth** | Two OPA policy rings — platform gate + runtime check |
| **Workload identity** | SPIFFE/SPIRE cryptographically proves the automation platform is legitimate |
| **User identity** | IdM group membership determines who can request network changes |
| **Deny by default** | No VLAN change without explicit allow from both rings |
| **Audit trail** | Netbox CMDB records both the user and the workload SPIFFE ID |
| **Micro-segmentation** | VLAN isolation enforced on Arista cEOS switch fabric |

## Zero Trust Layers

| Layer | Technology | What It Proves |
|-------|------------|----------------|
| **Platform gate** | AAP Policy as Code + OPA | The user is allowed to **launch** this job template at all (outer ring) |
| **Workload identity** | SPIFFE / SPIRE | The automation platform itself is cryptographically attested — not a rogue script |
| **User identity** | IdM (FreeIPA) | The human requesting the change is in the `network-admins` group |
| **Runtime policy** | OPA (in-playbook) | SPIFFE ID + user + VLAN + action are validated with runtime context (inner ring) |
| **Enforcement** | AAP + Arista | The job only proceeds if both rings return `allow: true` |
| **Audit trail** | Netbox CMDB | The VLAN record includes both the user and the workload SPIFFE ID |

## Defence in Depth — Two OPA Policy Rings

```
  User clicks "Launch" in AAP
       │
       ▼
  ┌─────────────────────────────────────────────────┐
  │  OUTER RING — AAP Policy as Code (aap.gateway)  │
  │                                                  │
  │  AAP Controller asks OPA:                        │
  │    "Can this user launch this template?"         │
  │                                                  │
  │  Checks: user groups vs template name            │
  │  neteng → Configure VLAN = DENIED (never runs)   │
  │  netadmin → Configure VLAN = ALLOWED             │
  └──────────────────────┬──────────────────────────┘
                         │ (only if outer ring allows)
                         ▼
  ┌─────────────────────────────────────────────────┐
  │  INNER RING — In-playbook policy (zta.network)   │
  │                                                  │
  │  Playbook asks OPA with runtime context:         │
  │    SPIFFE ID + user + VLAN ID + action           │
  │                                                  │
  │  Checks: workload identity, VLAN range,          │
  │          action allowlist, user group             │
  └──────────────────────┬──────────────────────────┘
                         │ (only if inner ring allows)
                         ▼
                  Arista + Netbox
```

The **outer ring** cannot be bypassed — AAP enforces it before the playbook
even starts. The **inner ring** validates parameters that only exist at
runtime (the specific VLAN ID, the SPIFFE workload identity).

## OPA Policies

### Outer Ring — `aap.gateway` (platform level)

Matches job template names to required IdM groups:

| Template pattern | Required group |
|-----------------|----------------|
| Contains "VLAN" or "Network" | `network-admins` |
| Contains "Patch" | `patch-admins` |
| Contains "Deploy", "Database", "Credential" | `app-deployers` |
| Contains "Verify", "Test", "Check" | Any authenticated user |

### Inner Ring — `zta.network` (runtime level)

The `zta.network` policy checks **four conditions** — all must pass:

| # | Condition | What It Checks |
|---|-----------|----------------|
| 1 | **Workload verified** | Caller's SPIFFE ID is in the trusted set (`spiffe://zta.lab/workload/network-automation`) |
| 2 | **User authorized** | User is in the `network-admins` group in IdM |
| 3 | **Valid VLAN** | VLAN ID is in the permitted range (100–999) |
| 4 | **Action permitted** | Action is one of: `create_vlan`, `modify_vlan`, `delete_vlan`, `assign_port` |

---

## Exercise 4.1 — Create the Job Template

| Template Name | Playbook | Inventory | Credentials |
|---------------|----------|-----------|-------------|
| Configure VLAN | `section4/playbooks/configure-vlan.yml` | ZTA Lab Inventory | ZTA Machine Credential, ZTA Arista Credential |

### Survey Variables

The template should prompt for:
- `new_vlan_id`: VLAN ID to create (e.g. `200`)
- `new_vlan_name`: VLAN name (e.g. `DMZ`)

---

## Exercise 4.2 — Denied (Network Engineer)

1. Log into AAP as `neteng` (not a member of any group)
2. Launch the **Configure VLAN** template
3. Fill in: `new_vlan_id: 200`, `new_vlan_name: DMZ`
4. Observe the output:

```
SPIFFE Workload Identity Verification

  SPIFFE ID: spiffe://zta.lab/workload/network-automation
  Host:      control
  Status:    VERIFIED ✓

OPA Network Policy Decision

  User:      neteng
  Action:    create_vlan
  VLAN ID:   200
  SPIFFE ID: spiffe://zta.lab/workload/network-automation
  Result:    DENIED

  Conditions:
    Workload verified:      PASS
    User in network-admins: FAIL
    Valid VLAN ID:          PASS
    Action permitted:       PASS

  DENIED: user 'neteng' is not a member of network-admins group
```

The SPIFFE check passes (the platform is legitimate) but the **user** is not
authorised. The Arista switches are never touched.

---

## Exercise 4.3 — Allowed (Network Admin)

1. Log into AAP as `netadmin` (member of `network-admins`)
2. Launch the same **Configure VLAN** template
3. Fill in: `new_vlan_id: 200`, `new_vlan_name: DMZ`
4. Observe the success:

```
SPIFFE Workload Identity Verification

  SPIFFE ID: spiffe://zta.lab/workload/network-automation
  Status:    VERIFIED ✓

OPA Network Policy Decision

  Result:    ALLOWED
  All conditions: PASS

VLAN 200 (DMZ) created on ceos1, ceos2, ceos3

VLAN Configuration Complete

  VLAN 200 (DMZ)
  Switches:   ceos1, ceos2, ceos3 (Arista cEOS fabric)
  Netbox:     Created
  User:       netadmin
  Workload:   spiffe://zta.lab/workload/network-automation
```

5. Verify on the Arista switches: `show vlan brief` — VLAN 200 should appear
6. Verify in Netbox: the VLAN record includes the SPIFFE workload ID in the description

---

## Exercise 4.4 — Test Additional Scenarios

### Scenario A — Invalid VLAN range

1. Log in as `netadmin`
2. Launch with `new_vlan_id: 5000` (outside 100–999 range)
3. Observe: OPA denies — "VLAN ID 5000 is outside the permitted range"

### Scenario B — Missing SPIFFE identity

1. Stop the SPIRE Agent on the `control` host:
   ```bash
   ssh rhel@control.zta.lab
   sudo systemctl stop spire-agent
   ```
2. Launch **Configure VLAN** as `netadmin` with valid parameters
3. Observe: the job fails at the SPIFFE verification step — cannot fetch SVID
4. **Restart the agent** when done:
   ```bash
   sudo systemctl start spire-agent
   ```

### Scenario C — Fix access by adding group membership

1. In IdM, add `neteng` to the `network-admins` group:
   ```bash
   ipa group-add-member network-admins --users=neteng
   ```
2. Launch **Configure VLAN** as `neteng` — it should now succeed
3. Remove the membership when done:
   ```bash
   ipa group-remove-member network-admins --users=neteng
   ```

---

## Playbook Flow

```
  AAP launches "Configure VLAN" job template
       │
       ▼
  Play 1 — SPIFFE Workload Identity Verification
  ──────────────────────────────────────────────
  Runs on: automation (AAP control node)
       │
       ├─ Fetch X.509 SVID from local SPIRE Agent
       │    → spiffe://zta.lab/workload/network-automation
       │
       └─ SVID proves the automation platform is legitimate
       │
       ▼
  Play 2 — OPA Policy Decision
  ────────────────────────────
  Runs on: zta_services (central)
       │
       ├─ POST to OPA with:
       │    • user + user_groups (from IdM/AAP)
       │    • spiffe_id (from SPIRE SVID)
       │    • action + vlan_id
       │
       ├─ OPA evaluates all 4 conditions
       │
       └─ ALLOW or DENY
       │
       ▼ (only if ALLOWED)
  Play 3 — Arista VLAN Configuration
  ──────────────────────────────────
  Runs on: network (ceos1, ceos2, ceos3)
       │
       └─ arista.eos.eos_vlans creates the VLAN
       │
       ▼
  Play 4 — Netbox CMDB Update
  ───────────────────────────
  Runs on: zta_services (central)
       │
       └─ Records VLAN with user + workload SPIFFE ID
```

---

## SPIFFE / SPIRE Background

[SPIFFE](https://spiffe.io/) (Secure Production Identity Framework For Everyone) provides
cryptographic identities to workloads. In this workshop:

- **SPIRE Server** runs on `central` alongside IdM and OPA
- **SPIRE Agents** run on `control` (AAP), `db`, and `vault`
- Each workload receives an **X.509 SVID** (SPIFFE Verifiable Identity Document)
- The SVID is short-lived and automatically rotated — no static secrets

The trust domain is `zta.lab`, matching the IdM domain. The registered
network automation workload identity is:

```
spiffe://zta.lab/workload/network-automation
```

---

## Discussion Points

- **Why verify the workload, not just the user?** A compromised script running outside
  AAP could impersonate a network admin. SPIFFE proves the *platform* is legitimate.
- What if `neteng` is added to `network-admins` in IdM? Does the next attempt succeed?
- What happens with a VLAN ID outside the permitted range (e.g. 5000)?
- How would you add an approval workflow before the VLAN is created?
- How does the Netbox CMDB record (with both user and SPIFFE ID) provide an audit trail?
- What if the SPIRE Agent on the AAP node is stopped? Can VLANs still be created?
- What is the difference between the outer ring (platform gate) and inner ring (runtime check)?
- Could someone bypass the outer ring by using `ansible-playbook` directly instead of AAP?

---

## Validation Checklist

- [ ] SPIRE Agent on `control` can fetch an SVID with the correct SPIFFE ID
- [ ] `neteng` is denied when attempting VLAN creation (workload passes, user fails)
- [ ] `netadmin` is allowed and the VLAN is created on the Arista cEOS switches
- [ ] Netbox is updated with the new VLAN, including the SPIFFE workload ID
- [ ] VLAN IDs outside range 100–999 are rejected by OPA
- [ ] The Arista switches show the new VLAN in `show vlan brief`
- [ ] If SPIRE Agent is stopped, the job fails at the SPIFFE verification step
- [ ] Adding `neteng` to `network-admins` in IdM allows the next attempt to succeed
