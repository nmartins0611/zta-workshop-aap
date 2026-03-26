# Section 3 — AAP Policy as Code: Platform-Gated Patching

## Objective

Demonstrate how AAP **Policy as Code** prevents unauthorised users from even
**launching** a job template. The OPA gateway policy (`aap.gateway`) evaluates
every launch request at the platform level — before the playbook runs. A user
not in `patch-admins` tries to apply a security patch and is blocked
immediately by AAP. After fixing the group membership, the patch succeeds.

## Zero Trust Principles

| Principle | How This Section Demonstrates It |
|-----------|----------------------------------|
| **Platform-level enforcement** | AAP checks OPA before the playbook starts — no bypass possible |
| **Deny by default** | No group membership = no launch permission |
| **Identity-driven access** | IdM group (`patch-admins`) controls who can patch |
| **Separation of duties** | Network admins cannot patch; patch admins cannot create VLANs |
| **Audit trail** | AAP logs every denied launch attempt |

## How AAP Policy as Code Works

```
  User clicks "Launch" in AAP
       │
       ▼
  ┌─────────────────────────────────────────────────────┐
  │  AAP Controller                                     │
  │                                                     │
  │  Before running ANY playbook, AAP sends a request   │
  │  to OPA with:                                       │
  │    • user (username, groups, is_superuser)           │
  │    • action ("launch")                              │
  │    • resource (template name, type)                  │
  │                                                     │
  │          POST → OPA (aap.gateway)                   │
  │                                                     │
  └─────────────────────────┬───────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
           OPA: ALLOW              OPA: DENY
                │                       │
                ▼                       ▼
         Playbook runs          AAP blocks the job
         normally               User sees "DENIED"
                                Playbook never starts
```

The gateway policy matches template names to required groups:

| Template name contains | Required IdM group |
|------------------------|--------------------|
| "Patch" | `patch-admins` |
| "VLAN" or "Network" | `network-admins` |
| "Deploy", "Database", "Credential" | `app-deployers` |
| "Verify", "Test", "Check" | Any authenticated user |

---

## The Patch

The security patch (`apply-security-patch.yml`) deploys:

1. **Login banner** — Legal warning on `/etc/issue` and `/etc/motd`
2. **SSH hardening** — Disable root login, limit auth attempts to 3
3. **Password policy** — 12-character minimum with complexity requirements
4. **Audit logging** — Monitor authentication, identity files, and sudoers

---

## Exercise 3.1 — Create the Job Template

| Template Name | Playbook | Inventory | Credentials |
|---------------|----------|-----------|-------------|
| Apply Security Patch | `section3/playbooks/apply-security-patch.yml` | ZTA Lab Inventory | ZTA Machine Credential |

The template should prompt for:
- `target_host`: hostname to patch (e.g. `app`)

**Important:** The template name contains "Patch" — this is what triggers
the `aap.gateway` policy to require `patch-admins` membership.

---

## Exercise 3.2 — Attempt as Wrong User (BLOCKED BY AAP)

1. Log into AAP as `neteng` (network engineer — **not** in `patch-admins`)
2. Navigate to the **Apply Security Patch** template
3. Click **Launch**

**What happens:**

AAP sends the launch request to OPA. The `aap.gateway` policy evaluates:

```
Template: "Apply Security Patch"  → contains "patch"  → requires patch-admins
User:     neteng                  → groups: []         → NOT in patch-admins

Result: DENIED at platform level
```

**AAP blocks the job entirely.** The playbook never starts. No SSH connection
to the target. No changes. `neteng` sees a denial message in the AAP UI.

This is different from an in-playbook policy check (like Section 4) — here
the **platform itself** enforces the gate. Even if someone modified the
playbook to remove a policy check, AAP would still block the launch.

---

## Exercise 3.3 — Fix the Access

**Option A** — Log in as a user already in `patch-admins`:

Use `ztauser` or `jsmith` (both are in `patch-admins` per the IdM configuration).

**Option B** — Add the user to the group in IdM:

```bash
ssh rhel@central.zta.lab
sudo ipa group-add-member patch-admins --users=neteng
```

---

## Exercise 3.4 — Apply the Patch Successfully

1. Log into AAP as `ztauser` (member of `patch-admins`)
2. Launch **Apply Security Patch** with `target_host: app`
3. AAP checks OPA — `ztauser` is in `patch-admins` — **ALLOWED**
4. The playbook runs and applies all four hardening measures:

```
Security Patch Applied

  Host:      app.zta.lab
  Patch:     ZTA-SEC-2026-001

  Applied:
    ✓ Security login banner (/etc/issue + /etc/motd)
    ✓ SSH hardening (no root, max 3 auth tries)
    ✓ Password policy (12 char min, complexity)
    ✓ Audit logging (auth, identity, sudoers)

  This patch was authorised by AAP Policy as Code.
  Only users in 'patch-admins' can launch this template.
```

---

## Exercise 3.5 — Verify the Patch Was Applied

SSH into the patched server and confirm:

```bash
ssh -p 2023 rhel@central.zta.lab
```

You should see the new login banner immediately. Then check:

```bash
# Verify SSH hardening
sudo sshd -T | grep -E 'permitrootlogin|maxauthtries|permitemptypasswords'
# Expected: permitrootlogin no, maxauthtries 3, permitemptypasswords no

# Verify password policy
cat /etc/security/pwquality.conf.d/zta-policy.conf

# Verify audit rules
sudo auditctl -l | grep zta
```

---

## Exercise 3.6 — Test Other Scenarios

### Scenario A — `appdev` tries to patch

1. Log in as `appdev` (in `app-deployers`, **not** `patch-admins`)
2. Try to launch **Apply Security Patch**
3. Result: **BLOCKED** — `app-deployers` cannot launch patching templates

### Scenario B — Remove group membership

1. Remove `neteng` from `patch-admins` (if you added them in Exercise 3.3):
   ```bash
   ipa group-remove-member patch-admins --users=neteng
   ```
2. Try to launch as `neteng` again — **BLOCKED** (back to denied)

### Scenario C — Separation of duties

Notice that `netadmin` (in `network-admins`) **cannot** launch patching
templates, and `ztauser` (in `patch-admins`) **can** launch patching but
different groups control different operations. This is separation of duties
enforced by policy.

---

## Discussion Points

- How is this different from AAP's built-in RBAC? (Answer: OPA policies are
  code, versioned in Git, and can encode arbitrary logic beyond simple roles)
- What if someone renames the template to avoid the policy? (Answer: the policy
  can also match on template ID, inventory, or other attributes)
- Could you add a time-of-day restriction? (Yes — OPA can check `time.now_ns()`)
- What's the difference between platform-level gating (this section) and
  in-playbook OPA checks (Section 4)?

---

## Validation Checklist

- [ ] `neteng` (not in `patch-admins`) is **blocked by AAP** before the playbook runs
- [ ] AAP UI shows the denial — the job never starts
- [ ] `ztauser` (in `patch-admins`) launches successfully
- [ ] Login banner is visible when SSH-ing to the patched server
- [ ] SSH hardening is applied (root login disabled, max 3 auth tries)
- [ ] Password policy is deployed
- [ ] Audit rules are active
- [ ] `appdev` cannot launch patching templates (separation of duties)
