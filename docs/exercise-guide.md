# Zero Trust Architecture Workshop — Exercise Guide

## Ansible Automation Platform as the Policy Enforcement Point

---

## About This Workshop

This workshop demonstrates how to build and operate a Zero Trust Architecture
using **Red Hat Ansible Automation Platform** as the central **Policy
Enforcement Point (PEP)**. Every action — deploying an application, patching
a server, configuring a network VLAN — must pass through AAP, which consults
identity, policy, and infrastructure data before allowing execution.

Nothing is trusted by default. Every request is verified. Every credential is
short-lived. Every decision is auditable. And when an attack is detected, the
response is automatic.

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
7. **Respond automatically** — Revoke access when threats are detected (EDA)

AAP is uniquely positioned as the PEP because **all operational actions flow
through it**. No one SSHes directly to servers. No one manually configures
switches. Every change is an AAP job template that checks policy before
executing.

### Component Roles

| ZTA Role | Component | Function |
|----------|-----------|----------|
| **Policy Enforcement Point (PEP)** | AAP | Receives requests, enforces decisions, executes automation |
| **Policy Decision Point (PDP)** | OPA | Evaluates policy rules, returns allow/deny decisions |
| **Platform Policy Gate** | AAP Policy as Code | Blocks unauthorised job launches before playbook runs |
| **Identity Provider** | IdM (FreeIPA) | Authenticates users, manages group memberships |
| **Identity Broker** | Keycloak | OIDC/SSO federation (future use) |
| **Workload Identity** | SPIFFE/SPIRE | Cryptographic workload attestation |
| **Secrets Manager** | HashiCorp Vault | Dynamic credentials, SSH OTP, secrets storage |
| **CMDB / Source of Truth** | Netbox | Infrastructure state, device inventory, maintenance status |
| **Source Control** | Gitea | GitOps trigger, automation code repository |
| **SIEM** | Wazuh | Security event monitoring, brute-force detection |
| **Event-Driven Automation** | EDA Controller | Automated incident response triggered by Wazuh |
| **Resources** | RHEL servers, Cisco switch, PostgreSQL | Managed infrastructure |

---

## Lab Environment

### Access Information

| System | URL / Address | Credentials |
|--------|---------------|-------------|
| AAP Controller | `https://aap.zta.lab` | *provided by instructor* |
| EDA Controller | `https://aap.zta.lab` (EDA tab) | *provided by instructor* |
| IdM (FreeIPA) | `https://central.zta.lab` | admin / ansible123! |
| OPA | `http://central.zta.lab:8181` | (no auth) |
| Vault | `https://vault.zta.lab:8200` | admin / ansible123! |
| Netbox | `http://netbox.zta.lab:8000` | *token provided* |
| Gitea | `http://gitea.zta.lab:3000` | *provided by instructor* |
| Wazuh | `https://wazuh.zta.lab` | *provided by instructor* |
| Application | `http://app.zta.lab:8080` | (no auth — dashboard) |

### Workshop Users in IdM

The IdM directory is populated with 19 users across 4 teams. The exercises use
the first four accounts directly.

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
> workshop begins. Attendees should not need to run these steps.

### Duration: ~30 minutes (mostly automated)

### Step 1 — Deploy IdM, Keycloak, and OPA

```bash
cd zta-lab-idm-keycloak
vi group_vars/all.yml
vi inventory.yml
ansible-playbook site.yml          # ~15-20 minutes
ansible-playbook integrate.yml
ansible-playbook verify.yml
```

### Step 2 — Run Workshop-Specific Setup

```bash
cd /tmp/zta-workshop-aap

# Identity & DNS
ansible-playbook setup/configure-dns.yml
ansible-playbook setup/enroll-idm-clients.yml
ansible-playbook setup/configure-idm-users.yml

# Secrets & SSH OTP
ansible-playbook setup/configure-vault.yml
ansible-playbook setup/configure-vault-ssh.yml

# Database & Application
ansible-playbook setup/deploy-db-app.yml

# Policy
ansible-playbook setup/configure-opa-base.yml
ansible-playbook setup/configure-aap-policy.yml

# Workload Identity (SPIFFE/SPIRE)
ansible-playbook setup/deploy-spire.yml

# SIEM → EDA Integration
ansible-playbook setup/configure-wazuh-eda.yml
```

### Lab Preparation Checklist

- [ ] IdM, Keycloak, OPA running on central.zta.lab
- [ ] DNS records for all workshop VMs
- [ ] Workshop IdM users and groups created
- [ ] Vault configured (KV, database engine, SSH OTP engine)
- [ ] `vault-ssh` user deployed to RHEL hosts with vault-ssh-helper
- [ ] PostgreSQL and Global Telemetry Platform deployed
- [ ] OPA policies loaded (patching, network, db_access, aap_gateway)
- [ ] AAP Policy as Code configured (OPA gateway)
- [ ] SPIRE Server + Agents deployed
- [ ] Wazuh → EDA webhook integration configured
- [ ] EDA rulebook activation created in EDA Controller

---

## Section 1 — Configure ZTA Components & AAP Integration

### Learning Objectives

- Understand AAP's role as the Policy Enforcement Point
- Connect AAP to identity, secrets, policy, and CMDB systems
- Verify the ZTA infrastructure is operational
- Test Vault dynamic credentials and SSH one-time passwords
- Observe OPA deny-by-default policy decisions

### Duration: ~45 minutes

---

### Exercise 1.1 — Explore the ZTA Components

**Step 1: Log into the IdM web UI**

1. Open `https://central.zta.lab`
2. Log in as `admin` / `ansible123!`
3. Navigate to **Identity → Users** — verify the workshop users
4. Navigate to **Identity → Groups** — verify `patch-admins`, `network-admins`, `app-deployers`

> **ZTA Concept**: IdM is the *Identity Provider*. Group membership determines
> what each user can do. The PEP (AAP) checks OPA, which checks IdM groups.

**Step 2: Query OPA directly**

```bash
curl -s http://central.zta.lab:8181/v1/data/zta/patching/decision \
  -d '{"input": {"user": "ztauser", "user_groups": ["patch-admins"], "target_server": "app.zta.lab", "target_server_status": "Active", "maintenance_approved": true}}' | python3 -m json.tool
```

Result: `"allow": true`. Now try with `neteng` (no groups): `"allow": false`.

> **Key Insight**: OPA (PDP) only makes decisions. AAP (PEP) enforces them.

**Step 3: Check Vault**

```bash
export VAULT_ADDR=https://vault.zta.lab:8200
export VAULT_SKIP_VERIFY=true
vault login -method=userpass username=admin password=ansible123!
vault status
vault secrets list    # should show database/, secret/, ssh/
```

---

### Exercise 1.2 — Configure AAP Credentials

Log into AAP Controller at `https://aap.zta.lab` and create:

| Credential | Type | Key Details |
|------------|------|-------------|
| ZTA Machine Credential | Machine | Username: `rhel`, sudo |
| ZTA Vault Credential | HashiCorp Vault | URL: `https://vault.zta.lab:8200`, admin / ansible123! |
| ZTA Cisco Credential | Network | Username: `admin` |
| ZTA Gitea Credential | Source Control | Gitea username + password |

> **ZTA Concept**: Each credential is scoped to a specific purpose — this is
> least privilege applied to the automation platform itself.

---

### Exercise 1.3 — Create Inventory & Project

**Inventory from Netbox:**

1. Create `ZTA Lab Inventory`
2. Add source: Netbox → `http://netbox.zta.lab:8000`
3. Sync and verify all hosts appear

**Project from Gitea:**

1. Create `ZTA Workshop`
2. Git URL: `http://gitea.zta.lab:3000/zta-workshop/zta-app.git`
3. Sync and verify green status

---

### Exercise 1.4 — Create Verification Templates

| Template | Playbook |
|----------|----------|
| Verify ZTA Services | `section1/playbooks/verify-zta-services.yml` |
| Test Vault Integration | `section1/playbooks/test-vault-integration.yml` |
| Test Vault SSH OTP | `section1/playbooks/test-vault-ssh.yml` |
| Test OPA Policy | `section1/playbooks/test-opa-policy.yml` |

All use: `ZTA Lab Inventory` + `ZTA Machine Credential`

---

### Exercise 1.5 — Run Verification

**Verify ZTA Services** — Confirm IdM, Vault, OPA, Netbox, DNS, PostgreSQL,
and the Cisco switch are all healthy.

**Test Vault Integration** — Watch Vault generate a dynamic PostgreSQL user
with a 5-minute TTL. Run it twice — the usernames will be different.

**Test Vault SSH OTP** — Watch Vault generate one-time passwords for SSH.
The OTP works once and is then permanently consumed.

**Test OPA Policy** — Five policy tests showing allow/deny based on group
membership. OPA's deny-by-default means no rule = no access.

---

### Section 1 Checkpoint

AAP is now the PEP with connections to IdM (identity), Vault (secrets + SSH OTP),
OPA (policy), Netbox (CMDB), and Gitea (source control).

---

## Section 2 — Deploy Application with Short-Lived Credentials

### Learning Objectives

- Build an AAP workflow that deploys the application with Vault dynamic credentials
- Experience a denied deployment when using the wrong user
- Examine the OPA policy that controls access
- Successfully deploy after using the correct user

### Duration: ~45 minutes

### The Scenario

The **Global Telemetry Platform** needs to be deployed. It connects to
PostgreSQL using short-lived credentials from Vault. But first, OPA must
approve the deployment request.

---

### Exercise 2.1 — Create the Pipeline Templates

| Template | Playbook | Extra Credentials |
|----------|----------|-------------------|
| Check DB Access Policy | `section2/playbooks/check-db-policy.yml` | — |
| Create DB Credential | `section2/playbooks/create-db-credential.yml` | — |
| Configure DB Access List | `section2/playbooks/configure-db-access.yml` | ZTA Cisco Credential |
| Deploy Application | `section2/playbooks/deploy-application.yml` | — |
| Rotate DB Credentials | `section2/playbooks/rotate-credentials.yml` | — |

---

### Exercise 2.2 — Build the Workflow

Create workflow **Deploy Application Pipeline**:

```
Check DB Access Policy ──(success)──► Create DB Credential ──(success)──► Configure DB Access List ──(success)──► Deploy Application
        │
     (failure) → [Access Denied]
```

---

### Exercise 2.3 — Attempt as the Wrong User (DENIED)

1. Log into AAP as `neteng` (not in `app-deployers`)
2. Launch the **Deploy Application Pipeline**
3. The first step queries OPA and is **DENIED**:

```
OPA Database Access Decision:
  User:       neteng
  Groups:     (none)
  Decision:   DENIED
  Reason:     user 'neteng' is not authorised to request database credentials

ACCESS DENIED by OPA policy.
```

The workflow stops. Vault is never contacted. No credentials are issued. The
application is not touched.

> **ZTA Concept**: The wrong user never gets anywhere near the database. OPA
> denied the request before any secret was generated.

---

### Exercise 2.4 — Examine the Policy

The `zta.db_access` policy checks:
- Is the user in `app-deployers`?
- Is the target database `ztaapp`?
- Are permissions within bounds (SELECT, INSERT, UPDATE)?

**Fix**: Log in as `appdev` (who is in `app-deployers`).

---

### Exercise 2.5 — Deploy as the Correct User (ALLOWED)

1. Log into AAP as `appdev`
2. Launch the **Deploy Application Pipeline**
3. All four steps complete:
   - OPA: **ALLOWED**
   - Vault: dynamic PostgreSQL user created (5-minute TTL)
   - Cisco ACL: only `app.zta.lab` can reach `db.zta.lab:5432`
   - Application deployed with dynamic credentials

4. Open `http://app.zta.lab:8080` — the **Global Telemetry Platform** dashboard is live

---

### Exercise 2.6 — Observe Credential Expiry

```bash
ssh rhel@db.zta.lab
sudo -u postgres psql -c "\du" | grep v-root    # Vault user exists
# Wait 5 minutes...
sudo -u postgres psql -c "\du" | grep v-root    # Vault user is GONE
```

The application loses database access after TTL. This is Zero Trust —
credentials are ephemeral.

---

### Section 2 Checkpoint

| Principle | How AAP Enforced It |
|-----------|---------------------|
| Policy verification | OPA check is the first workflow step — wrong user blocked |
| Least privilege | Vault credentials grant only SELECT/INSERT/UPDATE |
| Micro-segmentation | Cisco ACL restricts DB access to app server only |
| Short-lived credentials | 5-minute TTL, automatically revoked by Vault |

---

## Section 3 — AAP Policy as Code: Platform-Gated Patching

### Learning Objectives

- See how AAP Policy as Code blocks a job **before the playbook runs**
- Understand the difference between platform-level and in-playbook policy
- Fix access by updating IdM group membership
- Apply a security hardening patch

### Duration: ~30 minutes

### The Scenario

A security patch needs to be applied to a RHEL server. AAP has **Policy as
Code** enabled — before any job launches, AAP checks OPA's `aap.gateway`
policy. The template name contains "Patch", so only users in `patch-admins`
can launch it. A user outside that group is blocked **at the platform level**.

### How AAP Policy as Code Works

```
  User clicks "Launch" in AAP
       │
       ▼
  AAP sends to OPA: "Can this user launch this template?"
       │
       ├── OPA: ALLOW → Playbook runs
       │
       └── OPA: DENY  → AAP blocks the job — playbook NEVER starts
```

This is different from in-playbook OPA checks (like Section 4). Here, **AAP
itself** enforces the gate. Even if the playbook had no policy check, AAP
would still block the launch.

---

### Exercise 3.1 — Create the Template

| Template | Playbook |
|----------|----------|
| Apply Security Patch | `section3/playbooks/apply-security-patch.yml` |

Survey variable: `target_host` (text, default: `app`)

**Important**: The template name contains "Patch" — this triggers the
`aap.gateway` policy to require `patch-admins` membership.

---

### Exercise 3.2 — Attempt as Wrong User (BLOCKED BY AAP)

1. Log into AAP as `neteng` (not in `patch-admins`)
2. Navigate to **Apply Security Patch** → click **Launch**
3. **AAP blocks the job immediately**:

```
DENIED at platform level: user 'neteng' is not in patch-admins
— cannot launch patching templates
```

The playbook never starts. No SSH connection. No changes. The platform
itself enforced the policy.

> **ZTA Concept**: This is platform-level enforcement. Even if someone removed
> the OPA check from the playbook code, AAP would still block the launch.

---

### Exercise 3.3 — Fix the Access

**Option A**: Log in as `ztauser` (already in `patch-admins`)

**Option B**: Add `neteng` to the group in IdM:
```bash
ipa group-add-member patch-admins --users=neteng
```

---

### Exercise 3.4 — Apply the Patch Successfully

1. Log into AAP as `ztauser`
2. Launch **Apply Security Patch** with `target_host: app`
3. AAP checks OPA → **ALLOWED** → playbook runs:

```
Security Patch Applied

  Host:      app.zta.lab
  Patch:     ZTA-SEC-2026-001

  Applied:
    ✓ Security login banner (/etc/issue + /etc/motd)
    ✓ SSH hardening (no root, max 3 auth tries)
    ✓ Password policy (12 char min, complexity)
    ✓ Audit logging (auth, identity, sudoers)
```

---

### Exercise 3.5 — Verify the Patch

```bash
ssh rhel@app.zta.lab
# You should see the security login banner

sudo sshd -T | grep -E 'permitrootlogin|maxauthtries'
# Expected: permitrootlogin no, maxauthtries 3
```

---

### Section 3 Checkpoint

| Concept | What You Saw |
|---------|--------------|
| Platform enforcement | AAP blocked the job before the playbook ran |
| Separation of duties | `neteng` cannot patch; `appdev` cannot patch; only `patch-admins` can |
| Policy as Code | OPA `aap.gateway` policy is versioned, auditable code |

---

## Section 4 — SPIFFE-Verified Network VLAN Management

### Learning Objectives

- See defence in depth with two OPA policy rings
- Understand SPIFFE/SPIRE workload identity
- Observe how both user identity AND workload identity are verified
- Update the CMDB after a network change

### Duration: ~30 minutes

### The Scenario

A VLAN needs to be created on the Cisco switch. Two defence rings protect
this operation:

1. **Outer ring** (AAP Policy as Code): Can this user launch this template?
2. **Inner ring** (in-playbook OPA): Is the SPIFFE workload identity valid?
   Is the user in `network-admins`? Is the VLAN ID in range?

---

### Exercise 4.1 — Create the Template

| Template | Playbook | Extra Credentials |
|----------|----------|-------------------|
| Configure VLAN | `section4/playbooks/configure-vlan.yml` | ZTA Cisco Credential |

Survey: `new_vlan_id` (integer, default: `200`), `new_vlan_name` (text, default: `DMZ`)

---

### Exercise 4.2 — Network Engineer (Denied)

1. Log in as `neteng` → Launch **Configure VLAN**
2. SPIFFE check passes (the platform is legitimate)
3. OPA denies: `neteng` is not in `network-admins`

```
SPIFFE ID: spiffe://zta.lab/workload/network-automation — VERIFIED ✓

OPA: DENIED — user 'neteng' is not a member of network-admins group
```

---

### Exercise 4.3 — Network Admin (Allowed)

1. Log in as `netadmin` → Launch **Configure VLAN** (VLAN 200, DMZ)
2. SPIFFE: VERIFIED ✓
3. OPA: ALLOWED ✓
4. VLAN 200 created on Cisco switch
5. Netbox CMDB updated with VLAN + SPIFFE audit trail

Verify: `show vlan brief` on the switch. Check Netbox IPAM → VLANs.

---

### Exercise 4.4 — Test Edge Cases

- **Invalid VLAN**: Try `new_vlan_id: 5000` → OPA denies (outside 100–999)
- **Stop SPIRE Agent**: `systemctl stop spire-agent` on control → job fails at SPIFFE step
- **Add neteng to group**: `ipa group-add-member network-admins --users=neteng` → retry succeeds

---

### Section 4 Checkpoint

```
User launches job
  → OUTER RING (AAP Policy as Code): Can this user launch VLAN templates? 
  → INNER RING (in-playbook OPA): SPIFFE ID + user group + VLAN range?
  → Cisco switch configured + Netbox CMDB updated
```

---

## Section 5 — Automated Incident Response (Wazuh → EDA → Vault)

### Learning Objectives

- See automated incident response triggered by a security event
- Understand the Wazuh → EDA → AAP → Vault chain
- Observe how credential revocation contains a breach
- Restore the application after investigating

### Duration: ~30 minutes

### The Scenario

An attacker brute-forces SSH on the app server. Wazuh detects it (rule 5712),
sends an alert to Event-Driven Ansible, which triggers an AAP job to **revoke
the application's database credentials in Vault** — isolating the app from
sensitive data in under 30 seconds.

```
Attacker → SSH brute force → Wazuh detects → EDA receives → AAP revokes → App isolated
  T+0s         T+10s            T+12s           T+14s          T+20s         T+25s
```

---

### Exercise 5.1 — Create the Templates

| Template | Playbook |
|----------|----------|
| Emergency: Revoke App Credentials | `section5/playbooks/revoke-app-credentials.yml` |
| Simulate Brute Force | `section5/playbooks/simulate-bruteforce.yml` |
| Restore App Credentials | `section5/playbooks/restore-app-credentials.yml` |

---

### Exercise 5.2 — Verify Pre-Attack Health

```bash
curl http://app.zta.lab:8080/health     # should be healthy
ssh rhel@db.zta.lab
sudo -u postgres psql -c "\du" | grep v-root   # Vault DB user exists
```

---

### Exercise 5.3 — Launch the Brute-Force Attack

Launch **Simulate Brute Force** from AAP. The playbook sends 10 rapid failed
SSH login attempts to `app.zta.lab`.

---

### Exercise 5.4 — Watch the Automated Response

1. **Wazuh Dashboard** (`https://wazuh.zta.lab`): Alert rule 5712 fires
2. **EDA Controller**: Event received, rulebook matched, job triggered
3. **AAP Jobs**: "Emergency: Revoke App Credentials" appears — triggered by EDA,
   no human clicked Launch
4. **Application**: `curl http://app.zta.lab:8080/health` → unhealthy or refused
5. **Database**: `\du` shows no Vault-generated users — credentials revoked

**The application has been automatically isolated from the database.**

> **ZTA Concept**: This is "assume breach" in action. The system doesn't wait
> for a human to investigate. Credential revocation happens automatically,
> limiting the blast radius.

---

### Exercise 5.5 — Restore the Application

After investigating, launch **Restore App Credentials**:

- Fresh Vault credentials issued
- Application restarted
- Health check passes

```bash
curl http://app.zta.lab:8080/health     # healthy again
```

---

### Section 5 Checkpoint

| Time | Event |
|------|-------|
| T+0s | Attack starts |
| T+12s | Wazuh fires brute-force alert |
| T+14s | EDA triggers AAP job |
| T+25s | Credentials revoked, app isolated |
| — | Human investigates, then restores |

---

## Workshop Summary

### What You Built

```
                    ┌─────────────────────────────────────┐
                    │  AAP — Policy Enforcement Point     │
                    │  EDA — Automated Incident Response   │
                    │                                     │
                    │  Every operational action flows     │
                    │  through AAP. Nothing bypasses it.  │
                    │  Threats get automatic response.    │
                    └───────┬──────────────┬──────────────┘
                            │              │
              ┌─────────────▼──┐    ┌──────▼──────────────┐
              │ OPA (PDP)      │    │ Data Sources        │
              │                │    │                     │
              │ Gateway:       │    │ IdM:   groups       │
              │  platform gate │    │ Vault: secrets/OTP  │
              │ Patching:      │    │ Netbox: state       │
              │  3 conditions  │    │ Gitea: code         │
              │ Network:       │    │ Wazuh: events       │
              │  SPIFFE + RBAC │    │ SPIRE: workload ID  │
              │ DB access:     │    │                     │
              │  group + scope │    │                     │
              └────────────────┘    └─────────────────────┘
```

### Zero Trust Principles — Where You Saw Them

| Principle | Exercise |
|-----------|----------|
| **Never trust, always verify** | Every job checks OPA before executing (all sections) |
| **Deny by default** | `neteng` denied deployment (S2), patching (S3), VLAN (S4) |
| **Least privilege** | Vault DB credentials grant only SELECT/INSERT/UPDATE (S2) |
| **Short-lived credentials** | 5-minute TTL, SSH OTP single-use (S1, S2) |
| **No standing access** | `vault-ssh` user has no password (S1) |
| **Platform enforcement** | AAP Policy as Code blocks unauthorised launches (S3) |
| **Workload identity** | SPIFFE/SPIRE proves the automation platform is legitimate (S4) |
| **Defence in depth** | Two OPA rings — platform gate + runtime check (S4) |
| **Micro-segmentation** | Cisco ACL limits DB access to app server (S2) |
| **CMDB as source of truth** | Netbox state drives decisions, updated after changes (S2, S4) |
| **Continuous monitoring** | Wazuh watches every authentication attempt (S5) |
| **Assume breach** | EDA automatically revokes credentials on attack (S5) |
| **Blast radius containment** | Credential revocation limits attacker data access (S5) |

---

## Appendix A — OPA Policy Reference

### Gateway Policy (`aap.gateway`) — Platform Level

| Template contains | Required group |
|-------------------|----------------|
| "Patch" | `patch-admins` |
| "VLAN" or "Network" | `network-admins` |
| "Deploy", "Database", "Credential" | `app-deployers` |
| "Verify", "Test", "Check" | Any authenticated user |

### Patching Policy (`zta.patching`) — Runtime Level

| Condition | Input Field | Checks |
|-----------|-------------|--------|
| User authorized | `input.user_groups` | Contains `patch-admins` |
| Server active | `input.target_server_status` | Equals `Active` |
| Maintenance approved | `input.maintenance_approved` | Is `true` |

### Network Policy (`zta.network`) — Runtime Level

| Condition | Input Field | Checks |
|-----------|-------------|--------|
| Workload verified | `input.spiffe_id` | In trusted set |
| User authorized | `input.user_groups` | Contains `network-admins` |
| Valid VLAN | `input.vlan_id` | Between 100 and 999 |
| Action permitted | `input.action` | One of: `create_vlan`, `modify_vlan`, `delete_vlan`, `assign_port` |

### Database Access Policy (`zta.db_access`) — Runtime Level

| Condition | Input Field | Checks |
|-----------|-------------|--------|
| User authorized | `input.user_groups` | Contains `app-deployers` |
| Valid target | `input.target_database` | One of: `ztaapp`, `inventory`, `monitoring` |
| Least privilege | `input.requested_permissions` | Only `SELECT`, `INSERT`, `UPDATE` |

---

## Appendix B — Troubleshooting

### OPA returns no result

```bash
curl http://central.zta.lab:8181/v1/policies
# If empty: ansible-playbook setup/configure-opa-base.yml
```

### AAP Policy as Code not blocking

```bash
curl -s http://central.zta.lab:8181/v1/data/aap/gateway/decision \
  -d '{"input":{"user":{"username":"neteng","groups":[],"is_superuser":false},"action":"launch","resource":{"name":"Apply Security Patch"}}}' | python3 -m json.tool
# Should show "allow": false
```

### Vault credentials fail

```bash
curl -k https://vault.zta.lab:8200/v1/sys/seal-status
vault list database/roles
vault list ssh/roles
```

### SPIRE Agent cannot fetch SVID

```bash
ssh rhel@control.zta.lab
sudo systemctl status spire-agent
sudo /opt/spire/bin/spire-agent api fetch x509 -socketPath /run/spire/agent/api.sock
```

### EDA not receiving Wazuh events

```bash
# Check Wazuh integration logs
ssh rhel@wazuh.zta.lab
sudo tail -f /var/ossec/logs/integrations.log

# Check EDA is listening
curl http://control.zta.lab:5000/endpoint
```

### Application health check fails after credential revocation

This is expected behaviour after Section 5. Run the restore playbook:
```bash
ansible-playbook section5/playbooks/restore-app-credentials.yml
```

### Netbox inventory sync fails

```bash
curl -H "Authorization: Token <your-token>" http://netbox.zta.lab:8000/api/status/
```

### Cisco switch unreachable

```bash
ssh admin@switch01.zta.lab
# Check cisco.ios collection is in the AAP execution environment
```
