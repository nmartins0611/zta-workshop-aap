# Section 4 — SPIFFE-Verified, RBAC-Controlled Network VLAN Management

## Objective

Demonstrate **defense in depth** for network automation: a VLAN change must be
authorized by **both** a verified workload identity (SPIFFE) and an authorized
user identity (IdM). OPA evaluates both layers before the Cisco switch is
touched and the CMDB updated.

## Zero Trust Layers

| Layer | Technology | What It Proves |
|-------|------------|----------------|
| **Workload identity** | SPIFFE / SPIRE | The automation platform itself is cryptographically attested — not a rogue script |
| **User identity** | IdM (FreeIPA) | The human requesting the change is in the `network-admins` group |
| **Policy decision** | OPA | Both identities plus VLAN/action constraints are evaluated in one decision |
| **Enforcement** | AAP | The job template only proceeds if OPA returns `allow: true` |
| **Audit trail** | Netbox CMDB | The VLAN record includes both the user and the workload SPIFFE ID |

## OPA Policy

The `zta.network` policy checks **four conditions** — all must pass:

| # | Condition | What It Checks |
|---|-----------|----------------|
| 1 | **Workload verified** | Caller's SPIFFE ID is in the trusted set (`spiffe://zta.lab/workload/network-automation`) |
| 2 | **User authorized** | User is in the `network-admins` group in IdM |
| 3 | **Valid VLAN** | VLAN ID is in the permitted range (100–999) |
| 4 | **Action permitted** | Action is one of: `create_vlan`, `modify_vlan`, `delete_vlan`, `assign_port` |

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
  Play 3 — Cisco VLAN Configuration
  ─────────────────────────────────
  Runs on: network (switch01)
       │
       └─ cisco.ios.ios_vlans creates the VLAN
       │
       ▼
  Play 4 — Netbox CMDB Update
  ───────────────────────────
  Runs on: zta_services (central)
       │
       └─ Records VLAN with user + workload SPIFFE ID
```

## Scenario Flow

### Attempt 1 — Denied (Network Engineer)

```
  neteng logs in → launches "Configure VLAN" template
       │
       ▼
  SPIFFE: workload identity verified ✓
  (the platform is legitimate, but the USER is not authorized)
       │
       ▼
  OPA checks:
    ✓ Workload verified (spiffe://zta.lab/workload/network-automation)
    ✗ neteng is NOT in network-admins    ← DENIED
       │
       ▼
  Job fails: "user 'neteng' is not a member of network-admins group"
```

### Attempt 2 — Allowed (Network Admin)

```
  netadmin logs in → launches same template
       │
       ▼
  SPIFFE: workload identity verified ✓
       │
       ▼
  OPA checks:
    ✓ Workload verified
    ✓ netadmin IS in network-admins      ← ALLOWED
       │
       ▼
  VLAN created on Cisco Catalyst 8000v
  Netbox CMDB updated with VLAN + SPIFFE audit trail
```

## What You Will Configure in AAP

### Job Templates

| Template Name | Playbook | Purpose |
|---------------|----------|---------|
| Configure VLAN | `section4/playbooks/configure-vlan.yml` | SPIFFE verify + OPA check + Cisco VLAN + Netbox |

### Extra Variables (Survey)

The template should prompt for:
- `new_vlan_id`: VLAN ID to create (e.g. `40`)
- `new_vlan_name`: VLAN name (e.g. `DMZ`)

## Steps

### Attempt 1 — Denied (Network Engineer)

1. Log into AAP as `neteng` (not a member of any group)
2. Launch the **Configure VLAN** template
3. Fill in: `new_vlan_id: 40`, `new_vlan_name: DMZ`
4. Observe the output — the SPIFFE check passes but OPA denies:
   ```
   SPIFFE Workload Identity Verification
   SPIFFE ID: spiffe://zta.lab/workload/network-automation
   Status:    VERIFIED ✓

   OPA Network Policy Decision
   User:      neteng
   SPIFFE ID: spiffe://zta.lab/workload/network-automation
   Result:    DENIED
   Workload verified:     PASS
   User in network-admins: FAIL
   Reason:  user 'neteng' is not a member of network-admins group
   ```

### Attempt 2 — Allowed (Network Admin)

1. Log into AAP as `netadmin` (member of `network-admins`)
2. Launch the same **Configure VLAN** template
3. Fill in: `new_vlan_id: 40`, `new_vlan_name: DMZ`
4. Observe the success:
   ```
   SPIFFE Workload Identity Verification
   SPIFFE ID: spiffe://zta.lab/workload/network-automation
   Status:    VERIFIED ✓

   OPA Network Policy Decision
   Result:    ALLOWED
   All conditions: PASS

   VLAN 40 (DMZ) created on switch01.zta.lab
   Netbox CMDB updated — includes SPIFFE audit trail
   ```
5. Verify in Netbox that VLAN 40 now appears with the SPIFFE workload ID in the description

## Discussion Points

- **Why verify the workload, not just the user?** A compromised script running outside
  AAP could impersonate a network admin. SPIFFE proves the *platform* is legitimate.
- What if `neteng` is added to `network-admins` in IdM? Does the next attempt succeed?
- What happens with a VLAN ID outside the permitted range (e.g. 5000)?
- How would you add an approval workflow before the VLAN is created?
- How does the Netbox CMDB record (with both user and SPIFFE ID) provide an audit trail?
- What if the SPIRE Agent on the AAP node is stopped? Can VLANs still be created?

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

## Validation Checklist

- [ ] SPIRE Agent on `control` can fetch an SVID with the correct SPIFFE ID
- [ ] `neteng` is denied when attempting VLAN creation (workload passes, user fails)
- [ ] `netadmin` is allowed and the VLAN is created on the Cisco switch
- [ ] Netbox is updated with the new VLAN, including the SPIFFE workload ID
- [ ] VLAN IDs outside range 100–999 are rejected by OPA
- [ ] The Cisco switch shows the new VLAN in `show vlan brief`
- [ ] If SPIRE Agent is stopped, the job fails at the SPIFFE verification step
