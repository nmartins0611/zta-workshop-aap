# Section 4 — RBAC-Controlled Network VLAN Management

## Objective

Demonstrate identity-driven network automation. A network engineer who is not
in the correct IdM group is denied. A network admin in the `network-admins`
group succeeds and the change is recorded in Netbox as the source of truth.

## OPA Policy

The `zta.network` policy checks:

| # | Condition | What It Checks |
|---|-----------|----------------|
| 1 | **User authorized** | User is in the `network-admins` group in IdM |
| 2 | **Valid VLAN** | VLAN ID is in the permitted range (100–999) |
| 3 | **Action permitted** | Action is one of: `create_vlan`, `modify_vlan`, `delete_vlan`, `assign_port` |

## Scenario Flow

```
  Attempt 1 — Network Engineer (neteng)
  ──────────────────────────────────────
  neteng logs in → launches "Configure VLAN" template
       │
       ▼
  OPA checks groups:
    ✗ neteng is NOT in network-admins    ← DENIED
       │
       ▼
  Job fails: "user 'neteng' is not a member of network-admins group"


  Attempt 2 — Network Admin (netadmin)
  ─────────────────────────────────────
  netadmin logs in → launches same template
       │
       ▼
  OPA checks groups:
    ✓ netadmin IS in network-admins      ← ALLOWED
       │
       ▼
  VLAN created on Cisco Catalyst 8000v
       │
       ▼
  Netbox CMDB updated with new VLAN
```

## What You Will Configure in AAP

### Job Templates

| Template Name | Playbook | Purpose |
|---------------|----------|---------|
| Configure VLAN | `section4/playbooks/configure-vlan.yml` | OPA check + Cisco VLAN + Netbox |

### Extra Variables (Survey)

The template should prompt for:
- `new_vlan_id`: VLAN ID to create (e.g. `40`)
- `new_vlan_name`: VLAN name (e.g. `DMZ`)

## Steps

### Attempt 1 — Denied (Network Engineer)

1. Log into AAP as `neteng` (not a member of any group)
2. Launch the **Configure VLAN** template
3. Fill in: `new_vlan_id: 40`, `new_vlan_name: DMZ`
4. Observe the denial:
   ```
   OPA Network Policy Decision
   User:    neteng
   Action:  create_vlan
   VLAN ID: 40
   Result:  DENIED
   Reason:  user 'neteng' is not a member of network-admins group
   ```

### Attempt 2 — Allowed (Network Admin)

1. Log into AAP as `netadmin` (member of `network-admins`)
2. Launch the same **Configure VLAN** template
3. Fill in: `new_vlan_id: 40`, `new_vlan_name: DMZ`
4. Observe the success:
   ```
   OPA Network Policy Decision
   Result:  ALLOWED

   VLAN 40 (DMZ) created on switch01.zta.lab
   Netbox CMDB updated with VLAN 40
   ```
5. Verify in Netbox that VLAN 40 now appears

### Discussion Points

- What if `neteng` is added to `network-admins` in IdM? Does the next attempt succeed?
- What happens with a VLAN ID outside the permitted range (e.g. 5000)?
- How would you add an approval workflow before the VLAN is created?
- How does the Netbox CMDB record provide an audit trail?

## Validation Checklist

- [ ] `neteng` is denied when attempting VLAN creation
- [ ] `netadmin` is allowed and the VLAN is created on the Cisco switch
- [ ] Netbox is updated with the new VLAN after creation
- [ ] VLAN IDs outside range 100–999 are rejected by OPA
- [ ] The Cisco switch shows the new VLAN in `show vlan brief`
