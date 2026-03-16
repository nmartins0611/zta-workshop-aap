# Zero Trust Architecture Workshop

Build and operate a Zero Trust Architecture using Red Hat Ansible Automation
Platform as the central orchestration layer, integrated with IdM, HashiCorp
Vault, Open Policy Agent, Netbox, and Cisco network infrastructure.

## Lab Architecture

```
                               ┌──────────────────┐
                               │   AAP Controller  │
                               │   aap.zta.lab     │
                               └────────┬─────────┘
                                        │
    ┌───────────┬───────────┬───────────┼───────────┬───────────┬───────────┐
    │           │           │           │           │           │           │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐  ┌───▼───┐  ┌───▼───┐  ┌───▼───┐  ┌───▼────────┐
│Central │  │ Vault │  │Netbox │  │ Gitea │  │ Wazuh │  │  App  │  │Cisco C8000v│
│  .zta  │  │ .zta  │  │ .zta  │  │ .zta  │  │ .zta  │  │ .zta  │  │ switch01   │
│  .lab  │  │ .lab  │  │ .lab  │  │ .lab  │  │ .lab  │  │ .lab  │  │  .zta.lab  │
│        │  │       │  │       │  │       │  │       │  │       │  │            │
│  IdM   │  │Secrets│  │ CMDB  │  │  Git  │  │ SIEM  │  │(RHEL) │  │  Network   │
│  OPA   │  │Mgmt   │  │       │  │Server │  │       │  │       │  │  Switching │
│Keycloak│  │       │  │       │  │       │  │       │  │       │  │            │
└────────┘  └───────┘  └───────┘  └───────┘  └───────┘  └───┬───┘  └───┬────────┘
                                                             │          │
                                                      ┌─────▼──┐       │
                                                      │   DB   │───────┘
                                                      │  .zta  │
                                                      │  .lab  │ VLAN 30
                                                      │(Postgres│  (Data)
                                                      └────────┘
```

## Components

| Component | Role | Host |
|-----------|------|------|
| **IdM (FreeIPA)** | Identity, LDAP, Kerberos, CA, DNS | central.zta.lab |
| **Open Policy Agent** | Policy-based authorization (deny-by-default) | central.zta.lab |
| **Keycloak** | SSO / OIDC (future use) | central.zta.lab |
| **HashiCorp Vault** | Secrets management, dynamic DB credentials | vault.zta.lab |
| **Netbox** | CMDB / source of truth for infrastructure | netbox.zta.lab |
| **Gitea** | Git server for GitOps workflows | gitea.zta.lab |
| **Wazuh** | SIEM and security monitoring | wazuh.zta.lab |
| **AAP** | Automation orchestration (workshop hub) | aap.zta.lab |
| **Cisco Catalyst 8000v** | Network switching, VLANs, ACLs | switch01.zta.lab |
| **PostgreSQL** | Application database | db.zta.lab |
| **App Server** | Sample application (RHEL) | app.zta.lab |

## Prerequisites

The following VMs must be provisioned and reachable before running any setup:

- central.zta.lab (RHEL 9 — will host IdM, Keycloak, OPA)
- vault.zta.lab (HashiCorp Vault — deployed and unsealed)
- netbox.zta.lab (Netbox — deployed with basic Cisco switch config)
- wazuh.zta.lab (Wazuh — deployed)
- gitea.zta.lab (Gitea — running with a workshop repository)
- aap.zta.lab (AAP Controller — installed)
- app.zta.lab (RHEL 9 — application server)
- db.zta.lab (RHEL 9 — database server)
- switch01.zta.lab (Cisco Catalyst 8000v)

## Lab Setup — Deploy Core ZTA Services

Before the workshop begins, the core identity and policy services must be
deployed on the central server using the
[zta-lab-idm-keycloak](../zta-lab-idm-keycloak) project.

### Step 1 — Deploy IdM, Keycloak, and OPA on central.zta.lab

```bash
cd ../zta-lab-idm-keycloak

# Edit variables (registry credentials, passwords)
vi group_vars/all.yml

# Deploy IdM + Keycloak + OPA (15-20 minutes)
ansible-playbook site.yml
```

This installs:
- Red Hat IdM (FreeIPA) with integrated DNS, CA, and Kerberos
- Red Hat build of Keycloak (RHBK) as a Podman container with IdM-signed TLS
- Open Policy Agent (OPA) as a Podman container with base ZTA policies

### Step 2 — Integrate the services

```bash
# Wire up Keycloak ↔ IdM LDAP, create users, deploy JWT policies, issue certs
ansible-playbook integrate.yml
```

This runs 8 phases: prerequisite checks, IdM user/group creation, Keycloak
LDAP federation, OIDC client setup, OPA JWT policies, token mappers,
IdM-signed certificates, and end-to-end validation.

### Step 3 — Verify the central server

```bash
ansible-playbook verify.yml
```

Confirm that IdM, Keycloak, and OPA are all running and healthy.

### Step 4 — Run workshop-specific setup

Now switch to this project and configure the remaining services:

```bash
cd ../zta-aap-workshop
```

## Workshop Sections

### Section 1 — ZTA Foundation & AAP Integration

Integrate AAP with the Zero Trust infrastructure: connect to IdM for
authentication, Vault for secrets, OPA for policy decisions, and Netbox as a
CMDB source. Create the foundational credentials, inventories, projects, and
job templates in AAP.

### Section 2 — GitOps Database Credential Management

Build an AAP workflow triggered by a code commit to Gitea. Vault issues
short-lived database credentials with least-privilege grants, the network is
configured to allow only the app server to reach the database, the application
is deployed with the dynamic credentials, and a schedule rotates them every few
minutes.

### Section 3 — OPA-Gated Server Patching

An admin attempts to patch a server through AAP. Before execution, AAP checks
OPA policy which enforces three conditions. Part 1: one condition is not met
and the job is denied. Part 2: fix the failing condition and successfully
complete patching.

### Section 4 — RBAC-Controlled Network VLAN Management

A network engineer attempts to create a VLAN to isolate a new application
layer. The request is denied because the engineer is not in the required IdM
group. A network admin in the correct group runs the same job template
successfully and updates the CMDB (Netbox) with the new VLAN.

## Getting Started (from a fresh clone)

### 1. Clone the repos

```bash
git clone <this-repo-url> zta-aap-workshop
git clone <idm-keycloak-repo-url> zta-lab-idm-keycloak
cd zta-aap-workshop
```

### 2. Install Ansible collections

```bash
ansible-galaxy collection install -r collections/requirements.yml
```

### 3. Update the inventory with your lab IPs

Edit `inventory/hosts.yml` and replace every `ansible_host` value with the
actual IP address assigned to each VM in your lab. DNS names will not resolve
until IdM is installed and `configure-dns.yml` has been run.

```bash
vi inventory/hosts.yml
```

### 4. Set required environment variables

```bash
export VAULT_TOKEN="<your-vault-root-token>"
export NETBOX_TOKEN="<your-netbox-api-token>"

# Optional — these have sensible defaults if not set:
# export DB_ADMIN_PASSWORD="postgres123!"
# export GITEA_WEBHOOK_SECRET="zta-webhook-secret"
```

### 5. Deploy core services on central.zta.lab

This step installs IdM, Keycloak, and OPA. See the
[Lab Setup](#lab-setup--deploy-core-zta-services) section above for details.

```bash
cd ../zta-lab-idm-keycloak
vi group_vars/all.yml          # set registry creds, passwords, IP
vi inventory.yml               # set central server connection details
ansible-playbook site.yml      # ~15-20 minutes
ansible-playbook integrate.yml
ansible-playbook verify.yml
cd ../zta-aap-workshop
```

### 6. Run workshop setup playbooks

These must be run **in order** — DNS first (so subsequent playbooks can
resolve hostnames), then users, secrets, database, policies, and finally
the verification.

```bash
ansible-playbook setup/configure-dns.yml
ansible-playbook setup/configure-idm-users.yml
ansible-playbook setup/configure-vault.yml
ansible-playbook setup/deploy-db-app.yml
ansible-playbook setup/configure-opa-base.yml
ansible-playbook setup/verify-lab.yml
```

### 7. Start the workshop

Open the exercise guide and begin with Section 1:

```bash
# The full exercise guide
docs/exercise-guide.md

# Or follow each section's README individually
section1/README.md
section2/README.md
section3/README.md
section4/README.md
```

## Zero Trust Principles Demonstrated

| Principle | Where |
|-----------|-------|
| **Never trust, always verify** | Every AAP job checks OPA policy before execution |
| **Least privilege** | Vault issues DB credentials with minimum required grants |
| **Short-lived credentials** | Dynamic DB users expire; scheduled rotation |
| **Micro-segmentation** | VLANs and ACLs isolate app and data tiers |
| **Identity-driven access** | IdM groups determine who can run which operations |
| **Continuous verification** | OPA evaluates policy at every request, not just at login |
| **CMDB as source of truth** | Netbox validates infrastructure state for policy decisions |
