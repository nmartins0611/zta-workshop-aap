# Zero Trust Architecture Workshop — Exercise Guide

## Ansible Automation Platform as the Policy Enforcement Point

---

## About This Workshop

This workshop demonstrates how to build and operate a Zero Trust Architecture
using **Red Hat Ansible Automation Platform** as the central **Policy
Enforcement Point (PEP)**. Every action — patching a server, provisioning
database credentials, configuring a network VLAN — must pass through AAP, which
consults identity, policy, and infrastructure data before allowing execution.

Nothing is trusted by default. Every request is verified. Every credential is
short-lived. Every decision is auditable.

---

## Zero Trust Architecture — NIST SP 800-207 Alignment

This workshop maps directly to the NIST Zero Trust Architecture model:

```
                        ┌─────────────────────────┐
                        │    Policy Decision       │
                        │    Point (PDP)           │
                        │                          │
                        │    Open Policy Agent     │
                        │    (OPA)                 │
                        └────────────┬────────────┘
                                     │
                              Policy Decisions
                              (allow / deny)
                                     │
┌──────────┐              ┌──────────▼──────────┐              ┌──────────────┐
│          │   Request    │                     │   Enforce    │              │
│  Subject ├─────────────►│  Policy Enforcement │─────────────►│   Resource   │
│  (User)  │              │  Point (PEP)        │              │              │
│          │◄─────────────┤                     │◄─────────────┤  Server, DB, │
│          │   Response   │  Ansible Automation │   Result     │  Network,    │
└──────────┘              │  Platform (AAP)     │              │  Application │
                          └──────────┬──────────┘              └──────────────┘
                                     │
                          Consults data sources
                    ┌────────────┼────────────┐
                    │            │            │
              ┌─────▼────┐ ┌────▼─────┐ ┌───▼──────┐
              │   IdM    │ │  Vault   │ │  Netbox  │
              │Identity  │ │ Secrets  │ │  CMDB    │
              │Provider  │ │ Manager  │ │ (SoT)   │
              └──────────┘ └──────────┘ └──────────┘
```

### How AAP Acts as the PEP

In a traditional network, a firewall is the PEP — it sits between users and
resources and enforces access decisions. In a Zero Trust Architecture, the PEP
must do more than just allow or block network traffic. It must:

1. **Verify identity** — Who is making this request? (IdM / Keycloak)
2. **Check policy** — Is this action allowed given the current context? (OPA)
3. **Use least privilege** — Grant only the minimum access needed (Vault)
4. **Validate state** — Is the target resource in a valid state? (Netbox CMDB)
5. **Enforce the decision** — Execute or deny the automation (AAP)
6. **Log everything** — Maintain an audit trail (Wazuh / AAP logs)

AAP is uniquely positioned as the PEP because **all operational actions flow
through it**. No one SSHes directly to servers. No one manually configures
switches. Every change is an AAP job template that checks policy before
executing.

### Component Roles

| ZTA Role | Component | Function |
|----------|-----------|----------|
| **Policy Enforcement Point (PEP)** | AAP | Receives requests, enforces decisions, executes automation |
| **Policy Decision Point (PDP)** | OPA | Evaluates policy rules, returns allow/deny decisions |
| **Identity Provider** | IdM (FreeIPA) | Authenticates users, manages group memberships |
| **Identity Broker** | Keycloak | OIDC/SSO federation (future use) |
| **Secrets Manager** | HashiCorp Vault | Dynamic credentials, secrets storage |
| **CMDB / Source of Truth** | Netbox | Infrastructure state, device inventory, maintenance status |
| **Source Control** | Gitea | GitOps trigger, automation code repository |
| **SIEM** | Wazuh | Security event monitoring, audit logging |
| **Resources** | RHEL servers, Cisco switch, PostgreSQL | Managed infrastructure |

---

## Lab Environment

### Access Information

| System | URL / Address | Credentials |
|--------|---------------|-------------|
| AAP Controller | `https://aap.zta.lab` | *provided by instructor* |
| IdM (FreeIPA) | `https://central.zta.lab` | admin / ansible123! |
| OPA | `http://central.zta.lab:8181` | (no auth) |
| Vault | `https://vault.zta.lab:8200` | *root token provided* |
| Netbox | `http://netbox.zta.lab:8000` | *token provided* |
| Gitea | `http://gitea.zta.lab:3000` | *provided by instructor* |
| Wazuh | `https://wazuh.zta.lab` | *provided by instructor* |

### Workshop Users in IdM

The IdM directory is populated with 19 users (plus 2 service accounts) across 4 teams, mimicking a
real-world organisation. The exercises use the first four accounts directly,
but the full directory makes the environment realistic when browsing IdM or
querying LDAP.

**Primary scenario accounts:**

| Username | Groups | Role in Exercises |
|----------|--------|-------------------|
| `ztauser` | zta-admins, patch-admins, app-deployers | General admin — can patch and deploy |
| `netadmin` | zta-admins, network-admins | Network admin — can configure VLANs |
| `appdev` | app-deployers | App developer — can trigger deployments |
| `neteng` | *(none)* | Network engineer — **will be denied** |

**Infrastructure team (`team-infrastructure`):**

| Username | Name | Title | Functional Groups |
|----------|------|-------|-------------------|
| `jsmith` | James Smith | Infrastructure Team Lead | zta-admins, patch-admins, change-approvers |
| `rwilson` | Robert Wilson | Senior Sysadmin | patch-admins |
| `nobrien` | Nora O'Brien | DBA | db-admins, patch-admins |
| `djohnson` | David Johnson | Network Architect | network-admins, change-approvers |
| `agarcia` | Ana Garcia | Network Engineer | network-admins |

**DevOps team (`team-devops`):**

| Username | Name | Title | Functional Groups |
|----------|------|-------|-------------------|
| `lkim` | Lisa Kim | DevOps Lead | zta-admins, app-deployers, change-approvers |
| `mchen` | Michael Chen | DevOps Engineer | app-deployers, patch-admins |
| `ksato` | Kenji Sato | Platform Engineer | app-deployers, patch-admins |

**Security team (`team-security`):**

| Username | Name | Title | Functional Groups |
|----------|------|-------|-------------------|
| `mrodriguez` | Maria Rodriguez | Security Lead | zta-admins, security-ops, change-approvers |
| `spatel` | Sarah Patel | Security Analyst | security-ops |
| `fnguyen` | Felix Nguyen | SOC Analyst | security-ops |

**Application team (`team-applications`):**

| Username | Name | Title | Functional Groups |
|----------|------|-------|-------------------|
| `twright` | Tom Wright | Junior Developer | app-deployers |
| `ebell` | Emma Bell | Senior Developer | app-deployers |
| `cmorales` | Carlos Morales | QA Engineer | *(none — read-only)* |
| `pryan` | Patricia Ryan | Release Manager | app-deployers, change-approvers |

All passwords: `ansible123!`

---

## Lab Preparation — Deploy Core ZTA Services

> **Note for instructors**: This section must be completed *before* the
> workshop begins. It deploys IdM, Keycloak, and OPA on the central server
> and then configures the workshop-specific services (Vault secrets, IdM
> users, database, OPA policies). Attendees should not need to run these steps.

### Duration: ~30 minutes (mostly automated)

### Step 1 — Deploy IdM, Keycloak, and OPA

The [zta-lab-idm-keycloak](../zta-lab-idm-keycloak) project provisions the
core identity and policy services on `central.zta.lab`.

```bash
cd zta-lab-idm-keycloak

# Review and update variables (registry credentials, passwords, IP)
vi group_vars/all.yml
vi inventory.yml

# Deploy IdM + Keycloak + OPA on central.zta.lab (15-20 minutes)
ansible-playbook site.yml
```

**What `site.yml` does:**

| Phase | What It Installs |
|-------|------------------|
| 1 — System Prep | Hostname, `/etc/hosts`, IdM packages, firewall ports |
| 2 — IdM Install | `ipa-server-install` with integrated DNS, Kerberos, CA |
| 3 — DNS Records | A records for `keycloak.zta.lab`, `opa.zta.lab`, and all lab hosts |
| 4 — Container Runtime | Podman, registry login for `registry.redhat.io` |
| 5 — Keycloak | RHBK container with IdM-signed TLS certificate |
| 6 — OPA | OPA container with default ZTA authorization policy |
| 7 — OPA Tests | Validates policy engine with deny/allow test cases |
| 8 — Summary | Prints access URLs and credentials |

### Step 2 — Integrate the Services

```bash
# Wire up Keycloak ↔ IdM LDAP federation, create users, deploy JWT policies
ansible-playbook integrate.yml
```

**What `integrate.yml` does:**

| Phase | What It Configures |
|-------|---------------------|
| 1 — Prerequisites | Verifies IdM, Keycloak, OPA are running |
| 2 — IdM Users | Creates `keycloak-svc` bind user, `ztauser`, `zta-admins` group |
| 3 — Keycloak LDAP | Creates ZTA realm, LDAP federation pointing to IdM |
| 4 — OIDC Client | Creates `zta-app` client with redirect URIs |
| 5 — OPA JWT | Deploys JWT-aware policy using Keycloak's JWKS endpoint |
| 6 — Token Mapper | Adds `groups` claim to JWT tokens |
| 7 — Certificates | Issues IdM-signed certs for wazuh.zta.lab, aap.zta.lab |
| 8 — Validation | Tests token acquisition and OPA decision end-to-end |

### Step 3 — Verify the Central Server

```bash
ansible-playbook verify.yml
```

Confirm all services on central.zta.lab are healthy before proceeding.

### Step 4 — Add DNS Records for Workshop VMs

Since IdM now manages the `zta.lab` DNS zone, register all workshop VMs so
that `*.zta.lab` names resolve. Before running this, update `inventory/hosts.yml`
with the actual IP addresses assigned to each VM in your lab.

```bash
cd ../zta-aap-workshop
ansible-playbook setup/configure-dns.yml
```

This adds A records for vault, netbox, gitea, wazuh, aap, app, db, and
switch01 in the IdM DNS zone.

> **Important**: Point each workshop VM's `/etc/resolv.conf` nameserver to
> `central.zta.lab` so all `*.zta.lab` names resolve via IdM DNS.

### Step 5 — Run Workshop-Specific Setup

```bash
# Create workshop IdM users and groups (patch-admins, network-admins, etc.)
ansible-playbook setup/configure-idm-users.yml

# Configure Vault secrets engines, policies, and base secrets
ansible-playbook setup/configure-vault.yml

# Deploy PostgreSQL and the sample Flask application
ansible-playbook setup/deploy-db-app.yml

# Deploy workshop OPA policies (patching, network, db_access)
ansible-playbook setup/configure-opa-base.yml

# Verify everything is ready
ansible-playbook setup/verify-lab.yml
```

### Lab Preparation Checklist

- [ ] `site.yml` completed — IdM, Keycloak, OPA running on central.zta.lab
- [ ] `integrate.yml` completed — Keycloak ↔ IdM ↔ OPA wired up
- [ ] DNS records added for all workshop VMs
- [ ] All workshop VMs resolve `*.zta.lab` via IdM DNS
- [ ] Workshop IdM users created (ztauser, netadmin, appdev, neteng)
- [ ] Vault configured with KV + database secrets engines
- [ ] PostgreSQL running on db.zta.lab with the `ztaapp` database
- [ ] Sample application deployed on app.zta.lab
- [ ] OPA workshop policies loaded (patching, network, db_access)
- [ ] `verify-lab.yml` passes all checks

Once all checks pass, the lab is ready for attendees.

---

## Section 1 — ZTA Foundation & AAP Integration

### Learning Objectives

- Understand AAP's role as the Policy Enforcement Point
- Connect AAP to identity, secrets, policy, and CMDB systems
- Verify the ZTA infrastructure is operational
- Observe how AAP mediates between users and OPA policy decisions

### Duration: ~45 minutes

---

### Exercise 1.1 — Explore the ZTA Components

Before configuring AAP, take a few minutes to understand what each component
does and verify they are running.

**Step 1: Log into the IdM web UI**

1. Open `https://central.zta.lab` in your browser
2. Log in as `admin` / `ansible123!`
3. Navigate to **Identity → Users** — you should see the workshop users
4. Navigate to **Identity → Groups** — verify the groups exist:
   - `zta-admins`
   - `patch-admins`
   - `network-admins`
   - `app-deployers`

> **ZTA Concept**: IdM is the *Identity Provider*. These groups determine what
> each user is authorised to do. The PEP (AAP) will query the PDP (OPA), which
> checks group membership before allowing any action.

**Step 2: Query OPA directly**

From a terminal with access to the lab network, run:

```bash
curl -s http://central.zta.lab:8181/v1/data/zta/patching/decision \
  -d '{
    "input": {
      "user": "ztauser",
      "user_groups": ["zta-admins", "patch-admins"],
      "target_server": "app.zta.lab",
      "target_server_status": "Active",
      "maintenance_approved": true
    }
  }' | python3 -m json.tool
```

You should see:

```json
{
  "result": {
    "allow": true,
    "conditions": {
      "user_authorized": true,
      "server_active": true,
      "maintenance_approved": true
    },
    "reason": "all conditions met"
  }
}
```

Now try with a user who is NOT in `patch-admins`:

```bash
curl -s http://central.zta.lab:8181/v1/data/zta/patching/decision \
  -d '{
    "input": {
      "user": "neteng",
      "user_groups": [],
      "target_server": "app.zta.lab",
      "target_server_status": "Active",
      "maintenance_approved": true
    }
  }' | python3 -m json.tool
```

Result: `"allow": false`. This is OPA acting as the PDP — it makes the
*decision*. But OPA alone doesn't enforce anything. That is AAP's job.

> **Key Insight**: OPA (PDP) only makes decisions. AAP (PEP) enforces them.
> Without AAP checking OPA before every action, the policies are meaningless.

**Step 3: Check Vault**

```bash
export VAULT_ADDR=https://vault.zta.lab:8200
export VAULT_SKIP_VERIFY=true
vault status
```

Verify Vault is unsealed and the secrets engines are enabled:

```bash
vault secrets list
```

You should see `database/` and `secret/` engines.

**Step 4: Check Netbox**

Open `http://netbox.zta.lab:8000` and verify the Cisco switch is listed under
**Devices**.

---

### Exercise 1.2 — Configure AAP Credentials

Now configure AAP to authenticate with every component in the ZTA stack. This
is the first step in making AAP the central enforcement point — it needs
trusted connections to all systems.

**Log into AAP Controller at `https://aap.zta.lab`**

**Step 1: Machine Credential**

This allows AAP to SSH into managed RHEL servers.

1. Navigate to **Resources → Credentials → Add**
2. Fill in:
   - **Name**: `ZTA Machine Credential`
   - **Credential Type**: Machine
   - **Username**: `rhel`
   - **Password**: *(from your lab assignment)*
   - **Privilege Escalation Method**: sudo
3. Click **Save**

**Step 2: Vault Credential**

This allows AAP to retrieve secrets from Vault.

1. Navigate to **Resources → Credentials → Add**
2. Fill in:
   - **Name**: `ZTA Vault Credential`
   - **Credential Type**: HashiCorp Vault Secret Lookup
   - **Server URL**: `https://vault.zta.lab:8200`
   - **Token**: *(your Vault root token)*
   - **API Version**: v2
3. Click **Save**

**Step 3: Network Credential**

This allows AAP to configure the Cisco switch.

1. Navigate to **Resources → Credentials → Add**
2. Fill in:
   - **Name**: `ZTA Cisco Credential`
   - **Credential Type**: Network
   - **Username**: `admin`
   - **Password**: *(retrieve from Vault: `secret/network/switch01`)*
3. Click **Save**

**Step 4: Source Control Credential**

This allows AAP to pull playbooks from Gitea.

1. Navigate to **Resources → Credentials → Add**
2. Fill in:
   - **Name**: `ZTA Gitea Credential`
   - **Credential Type**: Source Control
   - **Username**: *(your Gitea username)*
   - **Password**: *(your Gitea password or token)*
3. Click **Save**

> **ZTA Concept**: The PEP must have authenticated, auditable connections to
> every system it manages. Each credential is scoped to a specific purpose —
> machine access, secrets, network, source control. This is the principle of
> *least privilege applied to the automation platform itself*.

---

### Exercise 1.3 — Create Inventory from Netbox

In Zero Trust, you don't maintain static lists of servers. The CMDB is the
**source of truth** for what infrastructure exists and its current state.

1. Navigate to **Resources → Inventories → Add → Add Inventory**
2. Fill in:
   - **Name**: `ZTA Lab Inventory`
3. Click **Save**
4. Go to the **Sources** tab → **Add**
5. Fill in:
   - **Name**: `Netbox Sync`
   - **Source**: NetBox
   - **Source URL**: `http://netbox.zta.lab:8000`
   - **Token**: *(your Netbox API token)*
6. Click **Save**, then click **Sync**
7. Verify all lab hosts appear in the inventory

> **ZTA Concept**: Dynamic inventory from the CMDB means the PEP always has an
> accurate picture of the infrastructure. If a server is decommissioned in
> Netbox, it disappears from AAP's inventory — you cannot automate against
> something that doesn't exist in the source of truth.

---

### Exercise 1.4 — Create Project from Gitea

1. Navigate to **Resources → Projects → Add**
2. Fill in:
   - **Name**: `ZTA Workshop`
   - **Source Control Type**: Git
   - **Source Control URL**: `http://gitea.zta.lab:3000/zta-workshop/zta-app.git`
   - **Source Control Credential**: `ZTA Gitea Credential`
3. Click **Save**
4. Wait for the project sync to complete (green status)

---

### Exercise 1.5 — Create Verification Job Templates

Create three job templates:

| Field | Verify ZTA Services | Test Vault | Test OPA |
|-------|---------------------|------------|----------|
| **Name** | Verify ZTA Services | Test Vault Integration | Test OPA Policy |
| **Job Type** | Run | Run | Run |
| **Inventory** | ZTA Lab Inventory | ZTA Lab Inventory | ZTA Lab Inventory |
| **Project** | ZTA Workshop | ZTA Workshop | ZTA Workshop |
| **Playbook** | `section1/playbooks/verify-zta-services.yml` | `section1/playbooks/test-vault-integration.yml` | `section1/playbooks/test-opa-policy.yml` |
| **Credentials** | ZTA Machine Credential | ZTA Machine Credential | ZTA Machine Credential |

---

### Exercise 1.6 — Run the Verification Templates

**Launch "Verify ZTA Services"**

1. Click the rocket icon next to the template
2. Watch the job output
3. Confirm all services report healthy:
   - IdM: RUNNING
   - Vault: HEALTHY (unsealed)
   - OPA: HEALTHY (policies loaded)
   - Netbox: ACCESSIBLE
   - Kerberos: OK
   - DNS: ALL RECORDS RESOLVE

**Launch "Test Vault Integration"**

1. Watch the job output
2. Observe that Vault generates a **dynamic database credential**:
   - A temporary PostgreSQL username is created
   - It has a short TTL (300 seconds)
   - It is revoked at the end of the test

> **ZTA Concept**: Vault generates *ephemeral, just-in-time* credentials. No
> standing access exists. This is the Zero Trust principle of short-lived
> credentials.

**Launch "Test OPA Policy"**

1. Watch the job output
2. Observe five policy test results — some allowed, some denied
3. Note how each decision explains *why* it was allowed or denied

> **ZTA Concept**: This is the PEP (AAP) consulting the PDP (OPA) for every
> action. The same playbook produces different results based on who runs it and
> the current state of the infrastructure.

---

### Section 1 Checkpoint

You have now configured AAP as the Policy Enforcement Point with connections to:

- **IdM** — identity and group membership
- **Vault** — secrets and dynamic credentials
- **OPA** — policy decisions
- **Netbox** — infrastructure state (CMDB)
- **Gitea** — automation source code

Every subsequent exercise flows through AAP. No direct access to resources.

---

## Section 2 — GitOps Database Credential Management

### Learning Objectives

- Build an AAP workflow that implements a GitOps deployment pipeline
- Use Vault to issue short-lived database credentials with least privilege
- Configure network micro-segmentation (ACL) as part of the pipeline
- Set up automated credential rotation

### Duration: ~45 minutes

### The Scenario

An application team needs to deploy their app. The app connects to a
PostgreSQL database on a separate network segment. In a Zero Trust model:

- The app gets **no standing database access**
- Credentials are created **just in time** with **minimum grants**
- Network access is opened **only between the app and the database**
- Credentials are **rotated every 5 minutes**
- A code push to Gitea **triggers the entire pipeline automatically**

---

### Exercise 2.1 — Create Pipeline Job Templates

Create each of these templates in AAP:

**Template 1: Check DB Access Policy**

| Field | Value |
|-------|-------|
| Name | Check DB Access Policy |
| Playbook | `section2/playbooks/check-db-policy.yml` |
| Inventory | ZTA Lab Inventory |
| Credentials | ZTA Machine Credential |

**Template 2: Create DB Credential**

| Field | Value |
|-------|-------|
| Name | Create DB Credential |
| Playbook | `section2/playbooks/create-db-credential.yml` |
| Inventory | ZTA Lab Inventory |
| Credentials | ZTA Machine Credential |

**Template 3: Configure DB Access List**

| Field | Value |
|-------|-------|
| Name | Configure DB Access List |
| Playbook | `section2/playbooks/configure-db-access.yml` |
| Inventory | ZTA Lab Inventory |
| Credentials | ZTA Machine Credential, ZTA Cisco Credential |

**Template 4: Deploy Application**

| Field | Value |
|-------|-------|
| Name | Deploy Application |
| Playbook | `section2/playbooks/deploy-application.yml` |
| Inventory | ZTA Lab Inventory |
| Credentials | ZTA Machine Credential |

**Template 5: Rotate DB Credentials**

| Field | Value |
|-------|-------|
| Name | Rotate DB Credentials |
| Playbook | `section2/playbooks/rotate-credentials.yml` |
| Inventory | ZTA Lab Inventory |
| Credentials | ZTA Machine Credential |

---

### Exercise 2.2 — Build the Workflow

This is where AAP's role as the PEP becomes most visible. The workflow
enforces a strict sequence: policy check → credential issuance → network
config → deployment.

1. Navigate to **Resources → Templates → Add → Add workflow template**
2. **Name**: `GitOps Deploy Pipeline`
3. Click **Save**, then open the **Visualizer**
4. Build the workflow:

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Check DB Access  │────►│ Create DB        │────►│ Configure DB     │────►│ Deploy           │
│ Policy           │ On  │ Credential       │ On  │ Access List      │ On  │ Application      │
│                  │Succ │                  │Succ │                  │Succ │                  │
└────────┬─────────┘     └──────────────────┘     └──────────────────┘     └──────────────────┘
         │
         │ On Failure
         ▼
   [Pipeline Halted — Policy Denied]
```

5. Click **Save** on the visualizer

> **ZTA Concept**: The first node in the workflow is the policy gate. If OPA
> denies the request, the entire pipeline halts. No credentials are issued, no
> network changes are made, no deployment occurs. This is the PEP enforcing
> the PDP's decision.

---

### Exercise 2.3 — Test the Pipeline Manually

1. Launch the **GitOps Deploy Pipeline** workflow
2. Watch each step execute in sequence
3. In the job output, observe:
   - **Step 1**: OPA allows the request (user is in `app-deployers`)
   - **Step 2**: Vault creates a dynamic PostgreSQL user with SELECT/INSERT/UPDATE only
   - **Step 3**: A Cisco ACL is applied allowing only `app.zta.lab` → `db.zta.lab:5432`
   - **Step 4**: The application starts with the dynamic credentials

4. After the pipeline completes, verify the application:

```bash
curl http://app.zta.lab:8080/health
```

Expected: `{"status": "healthy", "database": "connected"}`

```bash
curl http://app.zta.lab:8080/data
```

Expected: JSON data from the database

> **Discussion**: The database user that was just created will expire in 5
> minutes. After that, the application will lose database access until
> credentials are rotated. This is *by design* — no standing access.

---

### Exercise 2.4 — Configure the Gitea Webhook

Now connect Gitea to AAP so that a `git push` triggers the pipeline
automatically.

**In AAP:**

1. Edit the **GitOps Deploy Pipeline** workflow template
2. Check **Enable Webhook**
3. Select **Gitea** as the Webhook Service
4. Copy the **Webhook URL** and **Webhook Key**

**In Gitea (`http://gitea.zta.lab:3000`):**

1. Navigate to the workshop repository
2. Go to **Settings → Webhooks → Add Webhook → Gitea**
3. **Target URL**: paste the AAP webhook URL
4. **Secret**: paste the AAP webhook key
5. **Trigger On**: Push Events
6. Click **Add Webhook**

---

### Exercise 2.5 — Trigger via Git Push

1. Clone the repository (or use the Gitea web editor)
2. Make a small change (edit a comment, update a version)
3. Commit and push:

```bash
git add .
git commit -m "trigger deployment"
git push
```

4. Switch to AAP — you should see the **GitOps Deploy Pipeline** workflow
   launch automatically
5. Watch the pipeline execute end-to-end

> **ZTA Concept**: This is GitOps with Zero Trust. The code change is the
> *request*. AAP is the *PEP* that intercepts it. OPA is the *PDP* that
> decides if it's allowed. Vault provides *just-in-time credentials*. The
> Cisco switch provides *micro-segmentation*. Every layer is verified.

---

### Exercise 2.6 — Set Up Credential Rotation

1. Navigate to the **Rotate DB Credentials** template
2. Click **Schedules → Add**
3. Fill in:
   - **Name**: `Rotate every 5 minutes`
   - **Start date/time**: now
   - **Frequency**: Minute — every 5 minutes
4. Enable the schedule
5. Wait 5-10 minutes and check AAP's **Jobs** view — you should see rotation
   jobs running automatically
6. Verify the application stays healthy after each rotation:

```bash
curl http://app.zta.lab:8080/health
```

> **ZTA Concept**: Credential rotation is not optional in Zero Trust. If a
> credential is compromised, its window of usefulness is measured in minutes,
> not months.

---

### Section 2 Checkpoint

The deployment pipeline demonstrates four Zero Trust principles enforced by
AAP as the PEP:

| Principle | How AAP Enforces It |
|-----------|---------------------|
| Policy verification | OPA policy check is the first workflow step |
| Least privilege | Vault credentials grant only SELECT/INSERT/UPDATE |
| Micro-segmentation | Cisco ACL restricts DB access to the app server only |
| Short-lived credentials | 5-minute TTL with automated rotation |

---

## Section 3 — OPA-Gated Server Patching

### Learning Objectives

- See how the PEP (AAP) enforces the PDP's (OPA) deny decision
- Understand multi-condition policy evaluation
- Fix a failing policy condition and re-run successfully

### Duration: ~30 minutes

### The Scenario

An administrator needs to patch a RHEL server. In a traditional environment,
they would SSH in and run `dnf update`. In Zero Trust, the operation must pass
through the PEP (AAP), which checks the PDP (OPA) against three conditions.

---

### Exercise 3.1 — Create the Patching Template

1. Navigate to **Resources → Templates → Add → Add job template**
2. Fill in:
   - **Name**: `Patch Server`
   - **Playbook**: `section3/playbooks/patch-server.yml`
   - **Inventory**: ZTA Lab Inventory
   - **Credentials**: ZTA Machine Credential
3. Under **Variables** → check **Prompt on launch**
4. Click **Save**
5. Go to the **Survey** tab → **Add**:
   - **Question**: Target host to patch
   - **Answer variable name**: `target_host`
   - **Answer type**: Text
   - **Default answer**: `app`
6. Enable the survey

---

### Exercise 3.2 — Part 1: The Denied Patch

**Before running**, verify the current state in Netbox:

1. Open `http://netbox.zta.lab:8000`
2. Find the `app` device
3. Check the **Custom Fields** — `maintenance_approved` should be `false`

**Now run the job:**

1. Log into AAP as `ztauser` (or use the current session)
2. Launch the **Patch Server** template
3. Set `target_host` to `app`
4. Click **Launch**

**Watch the job output carefully.** You will see:

```
OPA Patching Policy Decision

  User:    ztauser
  Target:  app.zta.lab
  Result:  DENIED

  Conditions:
    User in patch-admins:    PASS
    Server active in CMDB:   PASS
    Maintenance approved:    FAIL

  DENIED: maintenance window has not been approved
```

The job **fails**. No packages are installed. No changes are made to the
server.

> **ZTA Concept**: This is the PEP in action. The user is authenticated (IdM),
> the policy was checked (OPA), and the decision was *deny*. AAP enforced that
> decision by halting the playbook. The target server was never touched.

**Question for discussion**: What would happen if someone bypassed AAP and
SSH'ed directly to the server to run `dnf update`? How would you prevent that
in a real Zero Trust environment?

---

### Exercise 3.3 — Fix the Failing Condition

The OPA policy told us exactly what failed: `maintenance_approved` is not true.
To fix this, update the CMDB:

1. Open Netbox at `http://netbox.zta.lab:8000`
2. Navigate to **Devices → app**
3. Edit the device
4. Set the custom field `maintenance_approved` to **true**
5. Save

> **ZTA Concept**: The policy is data-driven. You don't modify the policy to
> allow this one patch — you update the *source of truth* (Netbox) to reflect
> that a maintenance window has been approved. The policy remains unchanged and
> applies consistently to all future requests.

---

### Exercise 3.4 — Part 2: Successful Patching

1. Return to AAP
2. Launch the **Patch Server** template again with `target_host: app`
3. Watch the job output:

```
OPA Patching Policy Decision

  User:    ztauser
  Target:  app.zta.lab
  Result:  ALLOWED

  Conditions:
    User in patch-admins:    PASS
    Server active in CMDB:   PASS
    Maintenance approved:    PASS

  all conditions met

OPA policy check PASSED — proceeding with patching

Installing security updates...
X packages updated

Patching Complete
  Host:     app.zta.lab
  Updates:  X packages
  Reboot:   Not required
```

The patch completes successfully.

---

### Exercise 3.5 — Bonus: Test Other Denial Scenarios

Try these additional tests to see how OPA responds to different conditions:

**Test A — Wrong user group**

1. Create extra variables to simulate a different user:
   ```yaml
   patching_user: neteng
   patching_user_groups: []
   ```
2. Launch the template — the job should fail with:
   `DENIED: user is not a member of patch-admins group`

**Test B — Server not in CMDB**

1. Set `target_host` to a hostname that doesn't exist in Netbox
2. The job should fail with:
   `Target server 'nonexistent' not found in Netbox CMDB`

> **ZTA Concept**: The deny-by-default posture means *every* condition must be
> met. Failing any single check blocks the entire operation.

---

### Section 3 Checkpoint

The patching exercise demonstrated the PEP/PDP relationship:

```
  User Request          PEP (AAP)              PDP (OPA)           Data Sources
  ───────────          ──────────             ──────────          ─────────────
  "Patch app" ───────► AAP receives ────────► OPA evaluates ◄──── IdM: groups
                       request                3 conditions  ◄──── Netbox: status
                                                            ◄──── Netbox: maint.
                       ◄──── deny ◄───────── Result: deny
                       AAP halts job
                       Server untouched

  (fix Netbox)

  "Patch app" ───────► AAP receives ────────► OPA evaluates ◄──── IdM: groups
                       request                3 conditions  ◄──── Netbox: status
                                                            ◄──── Netbox: maint.
                       ◄──── allow ◄──────── Result: allow
                       AAP runs patching
                       Server updated
```

---

## Section 4 — RBAC-Controlled Network VLAN Management

### Learning Objectives

- See identity-driven access control for network automation
- Understand how IdM group membership controls who can modify network infrastructure
- Update the CMDB after a change to maintain the source of truth

### Duration: ~30 minutes

### The Scenario

A new application tier needs network isolation. A VLAN must be created on the
Cisco Catalyst 8000v switch. Two people will attempt this:

1. **`neteng`** — a network engineer who is NOT in the `network-admins` group
2. **`netadmin`** — a network admin who IS in the `network-admins` group

Only the authorised user should succeed.

---

### Exercise 4.1 — Create the VLAN Template

1. Navigate to **Resources → Templates → Add → Add job template**
2. Fill in:
   - **Name**: `Configure VLAN`
   - **Playbook**: `section4/playbooks/configure-vlan.yml`
   - **Inventory**: ZTA Lab Inventory
   - **Credentials**: ZTA Machine Credential, ZTA Cisco Credential
3. Check **Prompt on launch** for Variables
4. Click **Save**
5. Go to the **Survey** tab → **Add** two questions:

   **Question 1:**
   - Question: VLAN ID
   - Variable: `new_vlan_id`
   - Type: Integer
   - Default: `40`

   **Question 2:**
   - Question: VLAN Name
   - Variable: `new_vlan_name`
   - Type: Text
   - Default: `DMZ`

6. Enable the survey

---

### Exercise 4.2 — Attempt 1: Network Engineer (Denied)

1. Set extra variables to simulate the `neteng` user:
   ```yaml
   network_user: neteng
   network_user_groups: []
   ```
2. Launch the **Configure VLAN** template
3. Set VLAN ID: `40`, VLAN Name: `DMZ`
4. Watch the job output:

```
OPA Network Policy Decision

  User:    neteng
  Action:  create_vlan
  VLAN ID: 40
  Name:    DMZ
  Result:  DENIED

  Conditions:
    User in network-admins: FAIL
    Valid VLAN ID:          PASS
    Action permitted:       PASS

  DENIED: user 'neteng' is not a member of network-admins group
```

The job fails. The switch is untouched. No VLAN is created.

> **ZTA Concept**: Identity is the new perimeter. It doesn't matter that
> `neteng` has network knowledge or even credentials to the switch. Without
> the correct IdM group membership, the PEP (AAP) will not execute the
> automation.

---

### Exercise 4.3 — Attempt 2: Network Admin (Allowed)

1. Set extra variables to simulate the `netadmin` user:
   ```yaml
   network_user: netadmin
   network_user_groups:
     - zta-admins
     - network-admins
   ```
2. Launch the **Configure VLAN** template again
3. Set VLAN ID: `40`, VLAN Name: `DMZ`
4. Watch the job output:

```
OPA Network Policy Decision

  User:    netadmin
  Action:  create_vlan
  VLAN ID: 40
  Result:  ALLOWED

  all conditions met

VLAN 40 (DMZ) created on switch01.zta.lab

VLAN Configuration Complete
  VLAN    40 (DMZ)
  Switch:  switch01.zta.lab
  Netbox:  Created
  User:    netadmin
```

5. Verify on the switch (via AAP or directly):
   ```
   show vlan brief
   ```
   VLAN 40 should appear.

6. Verify in Netbox at `http://netbox.zta.lab:8000`:
   - Navigate to **IPAM → VLANs**
   - VLAN 40 (DMZ) should be listed with the description showing it was
     created via the ZTA Workshop by `netadmin`

> **ZTA Concept**: The CMDB update closes the loop. The change is not only
> executed but *recorded* in the source of truth. Future policy decisions can
> reference this data. If someone queries "does VLAN 40 exist?", Netbox has
> the answer — and it was populated automatically by the PEP.

---

### Exercise 4.4 — Bonus: Test Invalid VLAN Range

Try creating a VLAN with an ID outside the permitted range:

1. Launch the template with `new_vlan_id: 5000`
2. OPA should deny it:
   `DENIED: VLAN ID 5000 is outside the permitted range (100-999)`

> **ZTA Concept**: Policy is not just about *who* — it's about *what*. Even an
> authorised network admin cannot create any arbitrary VLAN. The policy
> constrains the *scope* of what is permitted.

---

### Section 4 Checkpoint

This exercise demonstrated the complete ZTA enforcement flow:

1. **Authentication**: User identity verified via IdM
2. **Authorization**: OPA checks group membership and action validity
3. **Enforcement**: AAP executes or denies based on OPA's decision
4. **Execution**: Cisco switch is configured
5. **Recording**: Netbox CMDB is updated as the source of truth
6. **Auditability**: AAP logs the entire operation — who, what, when, outcome

---

## Workshop Summary

### What You Built

```
                    ┌─────────────────────────────────────┐
                    │  AAP — Policy Enforcement Point     │
                    │                                     │
                    │  Every operational action flows     │
                    │  through AAP. Nothing bypasses it.  │
                    └───────┬──────────────┬──────────────┘
                            │              │
              ┌─────────────▼──┐    ┌──────▼──────────────┐
              │ OPA (PDP)      │    │ Data Sources        │
              │                │    │                     │
              │ Patching:      │    │ IdM:   groups       │
              │  3 conditions  │    │ Vault: secrets      │
              │ Network:       │    │ Netbox: state       │
              │  group + range │    │ Gitea: code         │
              │ DB access:     │    │ Wazuh: events       │
              │  group + scope │    │                     │
              └────────────────┘    └─────────────────────┘
```

### Zero Trust Principles — Where You Saw Them

| Principle | Exercise |
|-----------|----------|
| **Never trust, always verify** | Every job template checks OPA before executing (all sections) |
| **Deny by default** | `neteng` denied VLAN creation; patch denied without maintenance window |
| **Least privilege** | Vault DB credentials grant only SELECT/INSERT/UPDATE |
| **Short-lived credentials** | 5-minute TTL with rotation schedule (Section 2) |
| **Micro-segmentation** | Cisco ACL limits DB access to the app server (Section 2) |
| **Identity-driven access** | IdM groups determine patching, network, and deployment rights |
| **Continuous verification** | Policy checked at every request, not just at login |
| **CMDB as source of truth** | Netbox state drives OPA decisions (Section 3); updated after changes (Section 4) |

### AAP as the PEP — Why It Works

Traditional Zero Trust architectures focus on network-level enforcement —
firewalls, proxies, micro-segmentation. But operational tasks like patching,
provisioning, and configuration don't flow through a firewall. They need an
**operational PEP** — something that sits between the human operator and the
infrastructure and enforces policy on every action.

AAP fills this role because:

1. **All automation runs through it** — No one SSHes to servers directly
2. **It integrates with identity** — AAP knows who is running the job
3. **It consults policy** — Playbooks query OPA before taking action
4. **It uses dynamic secrets** — Vault credentials are created just-in-time
5. **It validates state** — Netbox data drives policy decisions
6. **It logs everything** — Full audit trail of every action and outcome
7. **It enforces workflows** — Multi-step pipelines with policy gates

This is Zero Trust for operations — not just for network traffic.

---

## Appendix A — OPA Policy Reference

### Patching Policy (`zta.patching`)

| Condition | Input Field | Checks |
|-----------|-------------|--------|
| User authorized | `input.user_groups` | Contains `patch-admins` |
| Server active | `input.target_server_status` | Equals `Active` |
| Maintenance approved | `input.maintenance_approved` | Is `true` |

### Network Policy (`zta.network`)

| Condition | Input Field | Checks |
|-----------|-------------|--------|
| User authorized | `input.user_groups` | Contains `network-admins` |
| Valid VLAN | `input.vlan_id` | Between 100 and 999 |
| Action permitted | `input.action` | One of: `create_vlan`, `modify_vlan`, `delete_vlan`, `assign_port` |

### Database Access Policy (`zta.db_access`)

| Condition | Input Field | Checks |
|-----------|-------------|--------|
| User authorized | `input.user_groups` | Contains `app-deployers` |
| Valid target | `input.target_database` | One of: `ztaapp`, `inventory`, `monitoring` |
| Least privilege | `input.requested_permissions` | Only `SELECT`, `INSERT`, `UPDATE` |

---

## Appendix B — Troubleshooting

### OPA returns no result

Check that policies are loaded:
```bash
curl http://central.zta.lab:8181/v1/policies
```

If empty, run the setup playbook:
```bash
ansible-playbook setup/configure-opa-base.yml
```

### Vault credentials fail

Verify Vault is unsealed:
```bash
curl -k https://vault.zta.lab:8200/v1/sys/seal-status
```

Verify the database secrets engine is configured:
```bash
vault list database/roles
```

### Netbox inventory sync fails

Check the Netbox API token is valid:
```bash
curl -H "Authorization: Token <your-token>" http://netbox.zta.lab:8000/api/status/
```

### Cisco switch unreachable

Verify the switch responds to SSH:
```bash
ssh admin@switch01.zta.lab
```

Check that the `cisco.ios` collection is installed in the AAP execution
environment.

### Application health check fails after credential rotation

Check the application logs:
```bash
journalctl -u ztaapp -n 50
```

Verify the environment file has been updated:
```bash
cat /opt/ztaapp/env
```
