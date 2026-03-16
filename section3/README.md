# Section 3 — OPA-Gated Server Patching

## Objective

Demonstrate policy-driven access control by attempting to patch a server
through AAP. OPA enforces three conditions — when any condition is not met,
the job is denied. The attendee then fixes the failing condition and
successfully completes patching.

## OPA Policy — Three Conditions

The `zta.patching` policy requires **all three** conditions to be true:

| # | Condition | What It Checks |
|---|-----------|----------------|
| 1 | **User authorized** | User is a member of the `patch-admins` group in IdM |
| 2 | **Server active** | Target server has status `Active` in Netbox (CMDB) |
| 3 | **Maintenance approved** | The `maintenance_approved` custom field in Netbox is `true` |

## Scenario Flow

```
  Part 1 — Job Denied
  ────────────────────
  Admin logs in → launches "Patch Server" template
       │
       ▼
  AAP runs pre-check → queries OPA
       │
       ▼
  OPA evaluates 3 conditions:
    ✓ User in patch-admins
    ✓ Server status: Active
    ✗ maintenance_approved: false     ← FAILS
       │
       ▼
  Job DENIED — "maintenance window not approved"


  Part 2 — Fix & Succeed
  ───────────────────────
  Admin updates Netbox → sets maintenance_approved = true
       │
       ▼
  Admin re-launches "Patch Server" template
       │
       ▼
  OPA evaluates 3 conditions:
    ✓ User in patch-admins
    ✓ Server status: Active
    ✓ maintenance_approved: true      ← NOW PASSES
       │
       ▼
  Patching proceeds → packages updated → reboot if needed
```

## What You Will Configure in AAP

### Job Templates

| Template Name | Playbook | Purpose |
|---------------|----------|---------|
| Patch Server | `section3/playbooks/patch-server.yml` | OPA pre-check + patching |

### Extra Variables

The template should prompt for:
- `target_host`: hostname to patch (e.g. `app`)

## Steps

### Part 1 — The Denied Patch

1. Verify the `maintenance_approved` field in Netbox is set to `false` for `app.zta.lab`
2. Log into AAP as `ztauser` (who is in `patch-admins`)
3. Launch the **Patch Server** template with `target_host: app`
4. Observe the job output — OPA denies the request:
   ```
   DENIED: maintenance window has not been approved
   Conditions:
     user_authorized:      true
     server_active:        true
     maintenance_approved: false
   ```
5. The job fails — no patching occurs

### Part 2 — Fix and Succeed

1. Open Netbox and navigate to the `app.zta.lab` device
2. Set the custom field `maintenance_approved` to `true`
3. Re-launch the **Patch Server** template with the same parameters
4. Observe the job output — all three OPA conditions pass
5. Patching runs successfully:
   ```
   OPA policy check PASSED — all conditions met
   Installing security updates...
   X packages updated
   Patching complete
   ```

### Discussion Points

- What happens if you log in as `neteng` (not in `patch-admins`)?
- What if the server status in Netbox is `Planned` instead of `Active`?
- How would you add a fourth condition (e.g. time-of-day maintenance window)?

## Validation Checklist

- [ ] Part 1: Job is denied when `maintenance_approved` is false
- [ ] The denial message clearly shows which condition failed
- [ ] Part 2: Updating Netbox causes the next run to succeed
- [ ] Patching actually installs updates on the target server
- [ ] A user not in `patch-admins` is denied regardless of other conditions
