# Zero Trust Architecture Workshop

Build and operate a Zero Trust Architecture using Red Hat Ansible Automation
Platform as the central orchestration layer, integrated with IdM, HashiCorp
Vault, Open Policy Agent, SPIFFE/SPIRE, Wazuh, Event-Driven Ansible, Netbox,
and Arista cEOS network infrastructure.

## Lab Architecture

```
                                        ┌──────────────────┐
                                        │   AAP Controller  │
                                        │   aap.zta.lab     │
                                        │   EDA Controller  │
                                        └────────┬─────────┘
                                                 │
          ┌──────────┬──────────┬────────────────┼───────────┬──────────┐
          │          │          │                 │           │          │
     ┌────▼───┐ ┌───▼───┐ ┌───▼───┐        ┌───▼───┐  ┌───▼───┐ ┌───▼───┐
     │ Vault  │ │Netbox │ │ Gitea │        │Central │  │Splunk │ │Wazuh  │
     │  .zta  │ │ .zta  │ │ .zta  │        │  .zta  │  │(cont) │ │(cont) │
     │  .lab  │ │ .lab  │ │ .lab  │        │  .lab  │  │       │ │       │
     │        │ │       │ │       │        │        │  │       │ │       │
     │Secrets │ │ CMDB  │ │  Git  │        │  IdM   │  │       │ │       │
     │SSH OTP │ │       │ │Server │        │  OPA   │  │       │ │       │
     └────────┘ └───────┘ └───────┘        │Keycloak│  └───────┘ └───────┘
          │          │          │           │ SPIRE  │
          │          │          │           └───┬────┘
          │          │          │               │
    192.168.1.0/24 management network          │ host-level services
    ───────────────────────────────────────────┤
                                               │
                                     ┌─────────┴─────────┐
                                     │   Central VM       │
                                     │  (192.168.1.11)    │
                                     │                    │
                                     │  ┌──────────────┐  │
                                     │  │ ceos1 (spine)│  │
                                     │  │      │       │  │
                                     │  │ ceos2  ceos3 │  │
                                     │  │(data) (app)  │  │
                                     │  └──┬───────┬───┘  │
                                     │     │       │      │
                                     │  ┌──▼──┐ ┌──▼──┐   │
                                     │  │ DB  │ │ App │   │
                                     │  │10.30│ │10.20│   │
                                     │  │.0.10│ │.0.10│   │
                                     │  └─────┘ └─────┘   │
                                     └────────────────────┘
```

## Components

| Component | Role | Host |
|-----------|------|------|
| **IdM (FreeIPA)** | Identity, LDAP, Kerberos, CA, DNS | central.zta.lab |
| **Open Policy Agent** | Policy-based authorisation (deny-by-default) | central.zta.lab |
| **Keycloak** | SSO / OIDC (future use) | central.zta.lab |
| **SPIRE Server** | Trust root for SPIFFE workload identity | central.zta.lab |
| **SPIRE Agents** | Workload attestation, SVID issuance | control, db, vault |
| **HashiCorp Vault** | Secrets management, dynamic DB creds, SSH OTP | vault.zta.lab (own VM) |
| **Netbox** | CMDB / source of truth for infrastructure | netbox.zta.lab (own VM) |
| **Gitea** | Git server for GitOps workflows | gitea.zta.lab |
| **Splunk** | Log aggregation, security analytics | central.zta.lab (container) |
| **Wazuh** | SIEM, vulnerability scanning, brute-force detection | central.zta.lab (container) |
| **AAP Controller** | Automation orchestration (Policy Enforcement Point) | aap.zta.lab (own VM) |
| **EDA Controller** | Event-Driven Ansible (automated incident response) | aap.zta.lab (own VM) |
| **Arista cEOS** | 3-switch fabric (spine + 2 leaf), VLANs, ACLs | central.zta.lab (containers) |
| **PostgreSQL** | Application database | central.zta.lab (RHEL container, 10.30.0.10) |
| **App Server** | Global Telemetry Platform (Flask) | central.zta.lab (RHEL container, 10.20.0.10) |

## Network Architecture

**Management plane** (`192.168.1.0/24`):
All VMs (central, AAP, Vault, Netbox) on this network. External VMs reach
containers via published ports on central's management IP.

**Data plane** (internal Podman networks, routed via Arista cEOS):
- `net2` = `10.30.0.0/24` (data-tier) — DB container, ceos2 gateway
- `net3` = `10.20.0.0/24` (app-tier) — App container, ceos3 gateway
- ACLs on switches control cross-tier traffic

---

## Workshop Sections

### Section 1 — Configure ZTA Components & AAP Integration

Configure AAP and connect it to the Zero Trust infrastructure: IdM for
identity, Vault for secrets (including SSH one-time passwords), OPA for
policy decisions, Netbox as a CMDB, and Gitea for source control. Verify
all services are healthy.

### Section 2 — Deploy Application with Short-Lived Credentials

Attempt to deploy the **Global Telemetry Platform** as the wrong user — OPA
denies the request. Examine the policy, use the correct user, and deploy
with short-lived Vault database credentials. Observe credential expiry.

### Section 3 — AAP Policy as Code: Platform-Gated Patching

AAP **Policy as Code** blocks a security patch from even launching when the
user is not in `patch-admins`. Fix the group membership and successfully
apply a security hardening patch (login banner, SSH hardening, password
policy, audit logging).

### Section 4 — SPIFFE-Verified Network VLAN Management

Create a VLAN through two OPA policy rings: the **outer ring** (AAP gateway)
checks whether the user can launch the template, and the **inner ring**
(in-playbook) validates the SPIFFE workload identity, user group, VLAN range,
and action.

### Section 5 — Automated Incident Response (Wazuh → EDA → Vault)

Simulate a brute-force SSH attack on the app server. **Wazuh** detects the
attack, sends an alert to **Event-Driven Ansible**, which automatically
triggers an AAP job to **revoke the application's database credentials** in
Vault — isolating the application from sensitive data in under 30 seconds.

---

## Getting Started

### 1. Clone the repo

```bash
git clone -b zta-container https://github.com/nmartins0611/zta-workshop-aap.git /tmp/zta-workshop-aap
cd /tmp/zta-workshop-aap
```

### 2. Install Ansible collections

```bash
ansible-galaxy collection install -r collections/requirements.yml
```

### 3. Update the inventory

Edit `inventory/hosts.ini` and replace `ansible_host` values with your lab IPs.

### 4. Set environment variables

```bash
export VAULT_TOKEN="<your-vault-token>"   # or log in with: vault login -method=userpass username=admin password=ansible123!
export NETBOX_TOKEN="<your-netbox-api-token>"
```

### 5. Deploy core services

```bash
# From the zta-lab-idm-keycloak project:
ansible-playbook site.yml          # IdM + Keycloak + OPA (~15-20 min)
ansible-playbook integrate.yml     # Wire services together
ansible-playbook verify.yml        # Verify health
```

### 6. Run workshop setup playbooks

```bash
cd /tmp/zta-workshop-aap

# Identity & DNS
ansible-playbook setup/configure-dns.yml
ansible-playbook setup/enroll-idm-clients.yml
ansible-playbook setup/configure-idm-users.yml

# Secrets & SSH OTP
ansible-playbook setup/configure-vault.yml
ansible-playbook setup/configure-vault-ssh.yml

# Arista cEOS switch fabric
ansible-playbook setup/deploy-arista.yml

# RHEL containers (DB + App) — connected to switch fabric
ansible-playbook setup/deploy-rhel-containers.yml

# Database & Application (targets RHEL containers)
ansible-playbook setup/deploy-db-app.yml

# Splunk & Wazuh (containers on central)
ansible-playbook setup/deploy-splunk.yml
ansible-playbook setup/deploy-wazuh.yml

# Policy
ansible-playbook setup/configure-opa-base.yml
ansible-playbook setup/configure-aap-policy.yml

# Workload Identity (SPIFFE/SPIRE)
ansible-playbook setup/deploy-spire.yml

# SIEM → EDA Integration
ansible-playbook setup/configure-wazuh-eda.yml

# Verify everything
ansible-playbook setup/verify-lab.yml
```

### 7. Start the workshop

```
section1/README.md   — Configure & Verify
section2/README.md   — Deploy App with Short-Lived Credentials
section3/README.md   — AAP Policy as Code: Patching
section4/README.md   — SPIFFE-Verified VLAN Management
section5/README.md   — Automated Incident Response (EDA)
```

---

## Zero Trust Principles Demonstrated

| Principle | Where |
|-----------|-------|
| **Never trust, always verify** | Every AAP job checks OPA policy before execution |
| **Least privilege** | Vault issues DB credentials with minimum grants |
| **Short-lived credentials** | Dynamic DB users expire; SSH OTPs are single-use |
| **No standing access** | `vault-ssh` user has no password — only Vault OTPs |
| **Deny by default** | OPA blocks all actions unless explicitly allowed |
| **Identity-driven access** | IdM groups control who can run which operations |
| **Workload identity** | SPIFFE/SPIRE proves the automation platform is legitimate |
| **Platform enforcement** | AAP Policy as Code blocks unauthorised launches |
| **Micro-segmentation** | Arista ACLs isolate app and data tiers on the switch fabric |
| **Continuous monitoring** | Wazuh watches every authentication attempt |
| **Assume breach** | EDA automatically revokes credentials on attack detection |
| **Blast radius containment** | Credential revocation limits attacker data access |
| **CMDB as source of truth** | Netbox validates infrastructure state for policy |
| **GitOps** | Code push triggers automated, policy-governed pipelines |
