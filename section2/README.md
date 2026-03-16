# Section 2 — GitOps Database Credential Management

## Objective

Build an automated pipeline where a code commit triggers AAP to provision
short-lived database credentials via Vault, optionally configure network access
controls, deploy the application, and schedule credential rotation.

## Zero Trust Principles

- **Least privilege**: Database user gets only SELECT/INSERT/UPDATE on required tables
- **Short-lived credentials**: TTL of 5 minutes, automatically revoked by Vault
- **Just-in-time access**: Credentials created only when the deployment runs
- **Micro-segmentation**: ACL restricts database access to the app server only
- **Policy verification**: OPA validates the credential request before Vault issues it

## Architecture

```
  Developer pushes code to Gitea (gitea.zta.lab:3000)
       │
       ▼
  Gitea webhook → AAP Controller ──────────────────────────┐
       │                                                    │
       ▼                                                    │
  ┌─ AAP Workflow ─────────────────────────────────────┐    │
  │                                                    │    │
  │  Step 1: Check OPA Policy                          │    │
  │    └─ POST /v1/data/zta/db_access/decision         │    │
  │                                                    │    │
  │  Step 2: Get Dynamic DB Credential from Vault      │    │
  │    └─ vault read database/creds/ztaapp-short-lived │    │
  │                                                    │    │
  │  Step 3: Configure ACL (app → db only)             │    │
  │    └─ Cisco ACL permits app.zta.lab → db:5432      │    │
  │                                                    │    │
  │  Step 4: Deploy Application with Credentials       │    │
  │    └─ Push creds to app, restart service           │    │
  │                                                    │    │
  └────────────────────────────────────────────────────┘    │
                                                            │
  ┌─ AAP Schedule ─────────────────────────────────────┐    │
  │  Rotate credentials every 5 minutes                │    │
  │    └─ Revoke old lease, create new, push to app    │    │
  └────────────────────────────────────────────────────┘    │
```

## What You Will Configure in AAP

### Job Templates

| Template Name | Playbook | Purpose |
|---------------|----------|---------|
| Check DB Access Policy | `section2/playbooks/check-db-policy.yml` | OPA pre-check |
| Create DB Credential | `section2/playbooks/create-db-credential.yml` | Vault dynamic creds |
| Configure DB Access List | `section2/playbooks/configure-db-access.yml` | Cisco ACL for app→db |
| Deploy Application | `section2/playbooks/deploy-application.yml` | Push creds, start app |
| Rotate DB Credentials | `section2/playbooks/rotate-credentials.yml` | Revoke + recreate |

### Workflow Template

Create a **Workflow Template** named `GitOps Deploy Pipeline` that chains:

```
Check DB Access Policy ──(success)──► Create DB Credential ──(success)──► Configure DB Access List ──(success)──► Deploy Application
        │                                                                                                              
     (failure)                                                                                                         
        │                                                                                                              
        ▼                                                                                                              
    [Job Denied]                                                                                                       
```

### Webhook

Configure a webhook on the Workflow Template so a `git push` triggers the
pipeline automatically.

### Schedule

Create a schedule on the **Rotate DB Credentials** template to run every
5 minutes.

## Steps

### Step 1 — Create the Job Templates

Create each job template listed above. All use:
- Inventory: `ZTA Lab Inventory`
- Credentials: `ZTA Machine Credential` + `ZTA Vault Credential`
- The Configure DB Access List template also needs `ZTA Cisco Credential`

### Step 2 — Build the Workflow

1. Navigate to **Resources → Templates → Add → Workflow Template**
2. Name: `GitOps Deploy Pipeline`
3. Open the workflow visualiser and chain the templates in order
4. Set the link from Check DB Access Policy to Create DB Credential as **On Success**
5. Add a failure path from Check DB Access Policy to a notification or approval node

### Step 3 — Test the Workflow

Launch the workflow manually first. Observe:
- OPA allows the request (user is in `app-deployers`)
- Vault generates a short-lived PostgreSQL user
- The ACL is applied on the Cisco switch
- The application starts with the dynamic credentials
- After 5 minutes, the credentials expire

### Step 4 — Configure the Gitea Webhook

1. Edit the workflow template in AAP
2. Enable **Webhook** and select **Gitea** as the webhook service
3. Copy the **Webhook URL** and **Webhook Key** from AAP
4. In Gitea (`http://gitea.zta.lab:3000`):
   - Navigate to the `{{ gitea_org }}/{{ gitea_repo }}` repository
   - Go to **Settings → Webhooks → Add Webhook → Gitea**
   - Target URL: paste the AAP webhook URL
   - Secret: paste the AAP webhook key
   - Trigger on: **Push Events**
   - Save the webhook
5. Test by pushing a commit — the workflow should trigger automatically

### Step 5 — Set Up Credential Rotation

1. Navigate to the **Rotate DB Credentials** template
2. Click **Schedules → Add**
3. Name: `Rotate every 5 minutes`
4. Set frequency to every 5 minutes
5. Enable the schedule

## Validation Checklist

- [ ] OPA policy check returns `allow: true` for `app-deployers`
- [ ] Vault generates dynamic PostgreSQL credentials
- [ ] Cisco ACL permits `app.zta.lab` → `db.zta.lab:5432`
- [ ] Application starts and the `/health` endpoint returns healthy
- [ ] Credentials expire after TTL
- [ ] Gitea webhook triggers the AAP workflow on `git push`
- [ ] Rotation schedule creates new credentials and updates the application
