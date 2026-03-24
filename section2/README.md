# Section 2 — Deploy Application with Short-Lived Database Credentials

## Objective

Deploy the **Global Telemetry Platform** application using short-lived database
credentials from Vault. First, attempt the deployment as the **wrong user** —
OPA denies the request. Then examine the policy, use the correct user (or fix
the group membership), and successfully deploy.

## Zero Trust Principles

| Principle | How This Section Demonstrates It |
|-----------|----------------------------------|
| **Deny by default** | OPA blocks the deployment until the user is explicitly authorised |
| **Least privilege** | Vault DB credentials grant only SELECT/INSERT/UPDATE |
| **Short-lived credentials** | Dynamic DB user expires after 5-minute TTL |
| **Just-in-time access** | Credentials only created when the deployment runs |
| **Micro-segmentation** | Cisco ACL restricts database access to the app server only |

## Architecture

```
  ┌─ AAP Workflow ─────────────────────────────────────┐
  │                                                    │
  │  Step 1: Check OPA Policy                          │
  │    └─ Is this user in 'app-deployers'?             │
  │    └─ DENIED → job stops                           │
  │    └─ ALLOWED → continue                           │
  │                                                    │
  │  Step 2: Get Dynamic DB Credential from Vault      │
  │    └─ vault read database/creds/ztaapp-short-lived │
  │    └─ TTL: 5 minutes, auto-revoked                 │
  │                                                    │
  │  Step 3: Configure ACL (app → db only)             │
  │    └─ Cisco ACL: PERMIT app → db:5432              │
  │    └─           DENY   * → db:5432                 │
  │                                                    │
  │  Step 4: Deploy Application with Credentials       │
  │    └─ Push creds to app, restart GTP service       │
  │                                                    │
  └────────────────────────────────────────────────────┘
```

---

## Exercise 2.1 — Create the Job Templates

All templates use **Inventory:** `ZTA Lab Inventory` and **Credentials:** `ZTA Machine Credential`.

| Template Name | Playbook | Extra Credentials |
|---------------|----------|-------------------|
| Check DB Access Policy | `section2/playbooks/check-db-policy.yml` | — |
| Create DB Credential | `section2/playbooks/create-db-credential.yml` | — |
| Configure DB Access List | `section2/playbooks/configure-db-access.yml` | `ZTA Cisco Credential` |
| Deploy Application | `section2/playbooks/deploy-application.yml` | — |
| Rotate DB Credentials | `section2/playbooks/rotate-credentials.yml` | — |

---

## Exercise 2.2 — Build the Deployment Workflow

Create a **Workflow Template** named `Deploy Application Pipeline`:

```
Check DB Access Policy ──(success)──► Create DB Credential ──(success)──► Configure DB Access List ──(success)──► Deploy Application
        │
     (failure)
        │
        ▼
   [Access Denied]
```

---

## Exercise 2.3 — Attempt Deployment as the Wrong User (DENIED)

1. Log into AAP as `neteng` (a network engineer — **not** in `app-deployers`)
2. Launch the **Deploy Application Pipeline** workflow
3. The first step (**Check DB Access Policy**) queries OPA:

```
OPA Database Access Decision:
  User:       neteng
  Groups:     (none)
  Database:   ztaapp
  Decision:   DENIED
  Reason:     user 'neteng' is not authorised to request database credentials

ACCESS DENIED by OPA policy.
```

4. The workflow stops — Vault is never contacted, no credentials are issued,
   the application is not touched

**Key takeaway:** OPA denied the request before any secret was generated.
The wrong user never gets anywhere near the database.

---

## Exercise 2.4 — Examine the Policy

Look at the OPA policy that blocked the request. Open
`opa-policies/db_access.rego` (or query OPA directly):

The `zta.db_access` policy checks:
- Is the user in the `app-deployers` group?
- Is the target database `ztaapp`?
- Are the requested permissions within bounds (SELECT, INSERT, UPDATE)?

**Fix option A** — Use the correct user:
Log in as `appdev` (who is in `app-deployers`)

**Fix option B** — Add the user to the group in IdM:
```bash
ipa group-add-member app-deployers --users=neteng
```

---

## Exercise 2.5 — Deploy as the Correct User (ALLOWED)

1. Log into AAP as `appdev` (member of `app-deployers`)
2. Launch the **Deploy Application Pipeline** workflow
3. Watch all four steps complete:

**Step 1 — OPA Policy Check:**
```
Decision:   ALLOWED
OPA policy check passed — proceeding with credential issuance
```

**Step 2 — Vault Dynamic Credentials:**
```
Dynamic database credentials created:
  Username: v-root-ztaapp-s-abc123def
  TTL:      300s
  Lease:    database/creds/ztaapp-short-lived/...
```

**Step 3 — Network ACL:**
```
Network micro-segmentation applied:
  ACL: ZTA-APP-TO-DB
  PERMIT: app.zta.lab → db.zta.lab:5432
  DENY:   any → db.zta.lab:5432
```

**Step 4 — Application Deployed:**
```
Application deployed successfully:
  URL:     http://app.zta.lab:8080
  Health:  ok
  DB User: v-root-ztaapp-s-abc123def (dynamic, short-lived)
```

4. Open `http://app.zta.lab:8080` in your browser — the **Global Telemetry
   Platform** dashboard should be live

---

## Exercise 2.6 — Observe Credential Expiry

1. SSH into the database server and list PostgreSQL users:
   ```bash
   ssh rhel@db.zta.lab
   sudo -u postgres psql -c "\du"
   ```
   You should see the Vault-generated user (e.g. `v-root-ztaapp-s-...`)

2. Wait 5 minutes (the TTL) and check again:
   ```bash
   sudo -u postgres psql -c "\du"
   ```
   The user is **gone** — Vault automatically revoked it

3. Check the application health:
   ```
   curl http://app.zta.lab:8080/health
   ```
   The app should now report unhealthy — it lost its database connection

This demonstrates Zero Trust: credentials are ephemeral. If not rotated,
access is automatically removed.

---

## Exercise 2.7 — Set Up Credential Rotation (Optional)

1. Navigate to the **Rotate DB Credentials** template
2. Click **Schedules → Add**
3. Name: `Rotate every 5 minutes`
4. Set frequency to every 5 minutes

The rotation job revokes old credentials, issues new ones from Vault, and
restarts the application — keeping it healthy continuously.

---

## Exercise 2.8 — Wire Up Gitea Webhook (Optional)

1. Edit the `Deploy Application Pipeline` workflow template
2. Enable **Webhook** → select **Gitea**
3. Copy the webhook URL and key
4. In Gitea (`http://gitea.zta.lab:3000`): add a webhook pointing to AAP
5. Push a commit — the pipeline triggers automatically

---

## Discussion Points

- What happened when `neteng` tried to deploy? Did they ever see credentials?
- Why does OPA check happen **before** Vault, not after?
- What happens to the application when credentials expire?
- Why is the Cisco ACL important if credentials are already short-lived?
- If you added `neteng` to `app-deployers` in IdM, what changes?

---

## Validation Checklist

- [ ] Wrong user (`neteng`) is denied by OPA — workflow stops at step 1
- [ ] Correct user (`appdev`) passes OPA — full workflow completes
- [ ] Vault generates dynamic PostgreSQL credentials with unique username
- [ ] Cisco ACL permits only `app.zta.lab` → `db.zta.lab:5432`
- [ ] Application dashboard loads at `http://app.zta.lab:8080`
- [ ] Credentials disappear from PostgreSQL after TTL expires
- [ ] Application loses DB access when credentials expire
