# ZTA Workshop — Lab Deployment Guide

Complete step-by-step instructions for deploying the Zero Trust Architecture
workshop lab from bare VMs to a running workshop environment.

---

## Table of Contents

1. [Infrastructure Prerequisites](#1-infrastructure-prerequisites)
2. [Phase 0 — Prepare the Control Node](#2-phase-0--prepare-the-control-node)
3. [Phase 1 — Deploy IdM, Keycloak, and OPA (Upstream Project)](#3-phase-1--deploy-idm-keycloak-and-opa)
4. [Phase 2 — Deploy Workshop Services (This Repo)](#4-phase-2--deploy-workshop-services)
5. [Phase 3 — Integration and Wiring](#5-phase-3--integration-and-wiring)
6. [Phase 4 — Verify the Lab](#6-phase-4--verify-the-lab)
7. [Phase 5 — AAP Controller and EDA Configuration](#7-phase-5--aap-controller-and-eda-configuration)
8. [Phase 6 — Pre-Workshop Instructor Preparation](#8-phase-6--pre-workshop-instructor-preparation)
9. [Quick Deploy (One-Shot)](#9-quick-deploy-one-shot)
10. [Playbook Reference](#10-playbook-reference)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Infrastructure Prerequisites

### Virtual Machines

You need at minimum **3 VMs** on the same Layer 2 network. The lab is designed
for RHEL 9.x but should work on CentOS Stream 9 or Fedora.

| VM | Hostname | IP (example) | Role | Min Specs |
|----|----------|--------------|------|-----------|
| **Central** | central.zta.lab | 192.168.1.11 | IdM, OPA, Keycloak, SPIRE server, Arista cEOS switches, DB/App containers, Wazuh, Splunk | 8 vCPU, 16 GB RAM, 80 GB disk |
| **AAP Controller** | control.zta.lab | 192.168.1.10 | AAP, EDA Controller, SPIRE agent | 4 vCPU, 16 GB RAM, 40 GB disk |
| **Vault** | vault.zta.lab | 192.168.1.12 | HashiCorp Vault | 2 vCPU, 4 GB RAM, 20 GB disk |

Optional VMs (can be consolidated onto central if resources allow):

| VM | Hostname | IP (example) | Role |
|----|----------|--------------|------|
| **Netbox** | netbox.zta.lab | 192.168.1.15 | CMDB / Source of truth |
| **Wazuh** | wazuh.zta.lab | 192.168.1.13 | SIEM (if not containerised on central) |

### Network

- All VMs on `192.168.1.0/24` management network
- DNS resolution for `*.zta.lab` (IdM will serve this after Phase 1)
- Internet access from VMs for package installation and container image pulls
- Port 22 (SSH) open between all VMs

### Software Pre-installed on All VMs

- RHEL 9.x (subscribed) or CentOS Stream 9
- `podman` and `python3-podman`
- `python3` and `python3-pip`
- A user `rhel` with sudo access and password `ansible123!` (or update `inventory/hosts.ini`)

### Software Pre-installed on AAP Controller

- Ansible Automation Platform 2.4+ (Controller + EDA Controller)
- Or: `ansible-core` + `ansible-rulebook` for a CLI-only setup

### Additional Accounts and Tokens

These will be created during deployment but are listed here for reference:

| Credential | Where Created | Used By |
|------------|---------------|---------|
| IdM admin password | Phase 1 (IdM install) | All IdM operations |
| Vault root token | Phase 2 (`deploy-vault.yml`) | Vault configuration |
| Vault unseal keys | Phase 2 (`deploy-vault.yml`) | Vault unsealing |
| Netbox API token | Phase 2 (`deploy-netbox.yml`) | AAP inventory source |

---

## 2. Phase 0 — Prepare the Control Node

Run these steps on the machine where you will execute Ansible (can be the
AAP controller, central, or a separate workstation).

### Clone the repositories

```bash
# The upstream IdM/Keycloak/OPA project
git clone https://github.com/nmartins0611/zta-lab-idm-keycloak.git /tmp/zta-lab-idm-keycloak

# This workshop repo
git clone -b zta-container https://github.com/nmartins0611/zta-workshop-aap.git /tmp/zta-workshop-aap
```

### Install Ansible collections

```bash
cd /tmp/zta-workshop-aap
ansible-galaxy collection install -r collections/requirements.yml --force
```

The following collections are required:

| Collection | Purpose |
|------------|---------|
| `arista.eos` | Arista cEOS switch management |
| `ansible.netcommon` | Network device connectivity |
| `community.postgresql` | PostgreSQL database management |
| `community.general` | General modules (firewalld, podman, etc.) |
| `redhat.rhel_idm` | IdM user/group/HBAC management |
| `netbox.netbox` | Netbox CMDB seeding |
| `containers.podman` | Container lifecycle management |

### Update the inventory

Edit `inventory/hosts.ini` and replace the IP addresses with your lab IPs:

```ini
[zta_services]
central ansible_host=<YOUR_CENTRAL_IP>

[vault_servers]
vault ansible_host=<YOUR_VAULT_IP>

[automation]
control ansible_host=<YOUR_AAP_IP>

# ... update all other entries
```

### Set environment variables

```bash
# These are needed by some playbooks during setup
export VAULT_TOKEN="<will-be-set-after-vault-deploy>"
export NETBOX_TOKEN="<will-be-set-after-netbox-deploy>"
```

---

## 3. Phase 1 — Deploy IdM, Keycloak, and OPA

**Duration:** ~15-20 minutes
**Project:** `zta-lab-idm-keycloak` (separate repository)

This phase deploys the foundational identity and policy services on the
central VM:

- **IdM (FreeIPA):** Identity provider, LDAP, Kerberos, CA, DNS
- **Keycloak:** SSO / OIDC federation
- **OPA:** Open Policy Agent container

```bash
cd /tmp/zta-lab-idm-keycloak

# 1. Update the inventory and group vars for your environment
vi inventory.yml
vi group_vars/all.yml

# 2. Deploy IdM, Keycloak, and OPA
ansible-playbook site.yml          # ~15-20 minutes

# 3. Wire services together (LDAP federation, OPA policies, certs)
ansible-playbook integrate.yml

# 4. Verify everything is healthy
ansible-playbook verify.yml
```

### What this creates

- IdM server with `zta.lab` domain and Kerberos realm `ZTA.LAB`
- IdM DNS serving `*.zta.lab` records
- IdM CA (used as the trust anchor for all workshop certificates)
- Keycloak realm `zta` with LDAP federation to IdM
- OPA container on port 8181 with base ZTA policies

### Verify Phase 1

```bash
# IdM web UI
curl -k https://central.zta.lab      # Should redirect to IdM login

# OPA health
curl http://central.zta.lab:8181/health    # {"status": "ok"}

# Keycloak
curl -k https://central.zta.lab:8543       # Should respond
```

---

## 4. Phase 2 — Deploy Workshop Services

**Duration:** ~25-30 minutes
**Project:** `zta-workshop-aap` (this repository)

This phase deploys all workshop-specific services in dependency order.
You can either run the master playbook or execute each layer individually.

### Option A: Run site.yml (recommended)

```bash
cd /tmp/zta-workshop-aap
ansible-playbook setup/site.yml
```

This runs all 10 layers in order. Use tags to target specific layers:

```bash
# Only deploy the network fabric and containers
ansible-playbook setup/site.yml --tags network

# Skip verification (faster for re-runs)
ansible-playbook setup/site.yml --skip-tags verify
```

### Option B: Run Playbooks Individually

If you need more control, run each layer in order:

#### Layer 1 — Identity and DNS (~3 min)

```bash
# Register all workshop VMs in IdM DNS
ansible-playbook setup/configure-dns.yml

# Enroll Linux hosts as IdM clients (SSSD, Kerberos)
ansible-playbook setup/enroll-idm-clients.yml

# Create workshop users and functional groups
ansible-playbook setup/configure-idm-users.yml
```

Creates DNS A records for all hosts, enrolls VMs as IdM clients, and populates
IdM with 19 users across 4 teams plus functional groups (`patch-admins`,
`network-admins`, `app-deployers`, `security-ops`, `db-admins`, etc.).

#### Layer 2 — Secrets Management (~3 min)

If Vault is not yet deployed as a container:
```bash
# Deploy Vault container on central (optional — skip if Vault has its own VM)
ansible-playbook setup/deploy-vault.yml
```

Then configure Vault:
```bash
# Configure KV, database secrets engine, policies
ansible-playbook setup/configure-vault.yml

# Configure Vault SSH CA trust on RHEL hosts
ansible-playbook setup/configure-vault-ssh.yml
```

After `deploy-vault.yml` runs, note the root token from the output and set:
```bash
export VAULT_TOKEN="<root-token-from-output>"
```

Creates Vault KV secrets (Arista creds, DB admin, IdM admin), database
secrets engine with a `ztaapp-short-lived` role (5-min TTL), SSH CA signing role,
and policies for `app-deployer`, `network-admin`, `patch-admin`, `ssh-access`.

#### Layer 3 — Network Fabric and Compute (~5 min)

```bash
# Deploy 3 Arista cEOS containers (spine + 2 leaf)
ansible-playbook setup/deploy-arista.yml

# Deploy RHEL 9 containers for DB and App (with data-plane networking)
ansible-playbook setup/deploy-rhel-containers.yml
```

Creates the Arista switch fabric (ceos1 spine, ceos2 leaf-data, ceos3
leaf-app) with SSH and eAPI ports published on central. Deploys two RHEL 9
systemd containers (`db` at 10.30.0.10, `app` at 10.20.0.10) connected
to the switch fabric via internal Podman networks.

#### Layer 4 — Application Stack (~3 min)

```bash
# Deploy PostgreSQL and the Global Telemetry Platform Flask app
ansible-playbook setup/deploy-db-app.yml
```

Installs PostgreSQL on the DB container, creates the `ztaapp` database and
schema, opens firewall ports, deploys the Flask application on the App
container with a systemd service.

#### Layer 5 — CMDB (~3 min)

```bash
# Deploy Netbox (podman-compose)
ansible-playbook setup/deploy-netbox.yml

# Seed Netbox with workshop infrastructure data
ansible-playbook setup/configure-netbox.yml
```

After `deploy-netbox.yml`, note the API token and set:
```bash
export NETBOX_TOKEN="<token-from-output>"
```

Deploys Netbox on port 8880 and seeds it with sites, device roles,
manufacturers, devices (all workshop VMs and switches), IP addresses,
VLANs, and ZTA architecture tags.

#### Layer 6 — Logging and SIEM (~5 min)

```bash
# Deploy Splunk container (log aggregation)
ansible-playbook setup/deploy-splunk.yml

# Deploy Wazuh stack (indexer, manager, dashboard)
ansible-playbook setup/deploy-wazuh.yml

# Deploy Wazuh agents on managed hosts
ansible-playbook setup/deploy-wazuh-agents.yml
```

Deploys Splunk (port 8000 UI, port 8088 HEC) and the full Wazuh stack
(indexer on 9200, manager API on 55000, dashboard on 5601) as containers
on central. Installs Wazuh agents on app, db, and other managed hosts.

#### Layer 7 — Policy (~2 min)

```bash
# Deploy OPA policies (patching, network, db_access, aap_gateway)
ansible-playbook setup/configure-opa-base.yml

# Configure AAP Policy as Code (OPA gateway integration)
ansible-playbook setup/configure-aap-policy.yml

# Configure AAP LDAP authentication against IdM
ansible-playbook setup/configure-aap-ldap.yml
```

Loads all OPA Rego policies, configures the AAP controller to check OPA
before every job launch (Policy as Code), and wires AAP LDAP authentication
to the IdM directory so workshop users can log in.

#### Layer 8 — Workload Identity (~2 min)

```bash
# Deploy SPIRE server on central + agents on control, db, vault
ansible-playbook setup/deploy-spire.yml
```

Deploys the SPIRE server with trust domain `zta.lab`, registers workload
entries for network automation, database, and vault workloads, and starts
SPIRE agents on agent hosts.

#### Layer 9 — Event-Driven Automation (~1 min)

```bash
# Configure Wazuh → EDA webhook integration
ansible-playbook setup/configure-wazuh-eda.yml
```

Deploys the `custom-eda` integration script in the Wazuh manager that
forwards brute-force alerts (rules 5712, 5763, 5764) to the EDA webhook
endpoint on the AAP controller.

#### Layer 10 — Verification (~1 min)

```bash
# Run full lab verification
ansible-playbook setup/verify-lab.yml
```

Checks all 30+ services and produces a summary report. See
[Phase 4](#6-phase-4--verify-the-lab) for details.

---

## 5. Phase 3 — Integration and Wiring

**Duration:** ~5 minutes

After all services are deployed, run the integration playbook to wire
everything together (IdM certificates for services, additional OPA policies,
service cross-references):

```bash
cd /tmp/zta-workshop-aap

# Standard integration (IdM + OPA + certs)
ansible-playbook integrate.yml

# If using Keycloak for OIDC/JWT:
ansible-playbook setup/configure-keycloak.yml
```

### Optional: Splunk log aggregation

```bash
ansible-playbook setup/integrate-splunk.yml
```

Configures centralized log shipping from all hosts, containers, Vault,
Wazuh, OPA, and Arista switches to Splunk via HEC.

### Optional: Dashboard

```bash
ansible-playbook setup/deploy-dashboard.yml
```

Deploys a Python topology dashboard on central.

---

## 6. Phase 4 — Verify the Lab

```bash
ansible-playbook setup/verify-lab.yml
```

This runs non-fatal checks against every component and produces a summary:

```
╔══════════════════════════════════════════════════════════════════╗
║            ZTA Workshop — Lab Verification Report               ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                ║
║  PASSED: 31 / 31                                               ║
║                                                                ║
║  ✓  IdM                    ✓  ceos1 container                  ║
║  ✓  Kerberos               ✓  ceos2 container                  ║
║  ✓  OPA container          ✓  ceos3 container                  ║
║  ✓  Keycloak container     ✓  DB SSH (2022)                    ║
║  ✓  Splunk container       ✓  App SSH (2023)                   ║
║  ✓  Wazuh Indexer          ✓  Data-plane (app→db:5432)         ║
║  ✓  Wazuh Manager          ✓  OPA API (8181)                   ║
║  ✓  Wazuh Dashboard        ✓  Vault                            ║
║  ✓  NetBox containers      ✓  PostgreSQL                       ║
║  ✓  DB container           ✓  Application (8081)               ║
║  ✓  App container          ✓  AAP Controller                   ║
║  ...                                                           ║
║                                                                ║
║  All services operational.                                     ║
╚══════════════════════════════════════════════════════════════════╝
```

You can also run targeted checks:

```bash
# Only check Vault and database
ansible-playbook setup/verify-lab.yml --tags vault,db

# Only check containers
ansible-playbook setup/verify-lab.yml --tags containers
```

### Manual Quick-Check

```bash
# IdM
curl -sk https://central.zta.lab | head -5

# OPA
curl -s http://central.zta.lab:8181/health

# Vault
curl -s http://vault.zta.lab:8200/v1/sys/health | python3 -m json.tool

# Netbox
curl -s http://netbox.zta.lab:8880/api/status/

# Application
curl -s http://app.zta.lab:8081/health

# Wazuh
curl -sk https://central.zta.lab:55000 | head -5

# Splunk
curl -s http://central.zta.lab:8000 | head -5

# Arista cEOS
ssh -p 2001 admin@central.zta.lab show version

# AAP
curl -sk https://control.zta.lab/api/controller/v2/ping/
```

---

## 7. Phase 5 — AAP Controller and EDA Configuration

These steps are done in the AAP web UI (or via API) and are typically the
first exercises attendees perform (Section 1 of the workshop).

### Pre-configure for Attendees (Instructor)

If you want attendees to start from Section 2 (skip credential/project
setup), pre-create these in the AAP UI:

**Credentials:**

| Name | Type | Details |
|------|------|---------|
| ZTA Machine Credential | Machine | User: `rhel`, sudo enabled, linked to Vault SSH cert |
| ZTA Vault Credential | HashiCorp Vault | URL: `http://vault.zta.lab:8200`, userpass: `admin`/`ansible123!` |
| ZTA Vault SSH Credential | HashiCorp Vault Signed SSH | URL: `http://vault.zta.lab:8200`, AppRole auth |
| ZTA Arista Credential | Network | User: `admin`, Pass: `admin` |
| ZTA Gitea Credential | Source Control | Gitea user + password |

**Inventory:**

| Name | Source | URL |
|------|--------|-----|
| ZTA Lab Inventory | Netbox | `http://netbox.zta.lab:8880` (with API token) |

**Project:**

| Name | SCM Type | URL |
|------|----------|-----|
| ZTA Workshop | Git | `http://gitea.zta.lab:3000/zta-workshop/zta-app.git` |

### EDA Configuration

1. In the EDA Controller, import the rulebook `section5/eda/wazuh-credential-revoke.yml`
2. Create a **Rulebook Activation** named "Wazuh Brute Force Response"
3. Set restart policy to "On failure"
4. Enable the activation (starts listening on port 5000)

---

## 8. Phase 6 — Pre-Workshop Instructor Preparation

### Lab Preparation Checklist

Run through this checklist the day of the workshop:

- [ ] All VMs are up and reachable
- [ ] IdM, Keycloak, OPA running on central (`ipactl status`)
- [ ] DNS resolves all `*.zta.lab` names (`dig app.zta.lab`)
- [ ] Workshop IdM users and groups exist (`ipa user-find --sizelimit=0`)
- [ ] Vault unsealed and healthy (`vault status`)
- [ ] Vault engines configured (`vault secrets list`)
- [ ] RHEL hosts trust Vault SSH CA (`TrustedUserCAKeys` configured)
- [ ] Arista cEOS switches respond (`ssh -p 2001 admin@central.zta.lab`)
- [ ] DB and App containers running (`podman ps` on central)
- [ ] PostgreSQL accepting connections
- [ ] Application NOT yet deployed with credentials (Section 2 handles this)
- [ ] Netbox API accessible with data
- [ ] OPA policies loaded (`curl .../v1/policies | python3 -m json.tool`)
- [ ] AAP Policy as Code configured (OPA gateway)
- [ ] AAP LDAP auth working (log in as `ztauser`)
- [ ] SPIRE server + agents running
- [ ] Wazuh agents reporting to manager
- [ ] Wazuh → EDA webhook integration active
- [ ] EDA rulebook activation running
- [ ] `verify-lab.yml` passes all checks

### Prepare Hands-On Break/Fix Exercises

If you plan to use the hands-on failure/fix exercises (Section 3B, Section 6,
etc.), **do NOT run the break playbooks in advance**. Run each one
immediately before the corresponding exercise during the workshop.

| Exercise | Break Playbook | Fix Playbook (safety net) |
|----------|---------------|--------------------------|
| 1.8 — Certificate Trust | `section1/playbooks/break-cert-trust.yml` | `section1/playbooks/fix-cert-trust.yml` |
| 2.9 — Firewall Debugging | `section2/playbooks/break-firewall.yml` | `section2/playbooks/fix-firewall.yml` |
| 2.10 — Vault Policy Paths | `section2/playbooks/break-vault-policy.yml` | `section2/playbooks/fix-vault-policy.yml` |
| 2.11 — SELinux Contexts | `section2/playbooks/break-selinux.yml` | `section2/playbooks/fix-selinux.yml` |
| 3B — OPA Rego Authoring | `section3/playbooks/break-opa-policy.yml` | `section3/playbooks/fix-opa-policy.yml` |
| 4.5 — Arista ACL | `section4/playbooks/break-acl.yml` | `section4/playbooks/fix-acl.yml` |
| 5.7 — Wazuh Rule Tuning | (manual — no break playbook needed) | — |
| 6.3 — SSH Lockdown | `section6/playbooks/break-hbac.yml` | `section6/playbooks/fix-hbac.yml` |

---

## 9. Quick Deploy (One-Shot)

For experienced instructors who want to deploy everything in one go:

```bash
# 1. Clone both repos
git clone https://github.com/nmartins0611/zta-lab-idm-keycloak.git /tmp/zta-lab-idm-keycloak
git clone -b zta-container https://github.com/nmartins0611/zta-workshop-aap.git /tmp/zta-workshop-aap

# 2. Install collections
cd /tmp/zta-workshop-aap
ansible-galaxy collection install -r collections/requirements.yml --force

# 3. Update inventory
vi inventory/hosts.ini

# 4. Deploy IdM + Keycloak + OPA (~20 min)
cd /tmp/zta-lab-idm-keycloak
vi inventory.yml && vi group_vars/all.yml
ansible-playbook site.yml
ansible-playbook integrate.yml
ansible-playbook verify.yml

# 5. Deploy all workshop services (~30 min)
cd /tmp/zta-workshop-aap
ansible-playbook setup/site.yml

# 6. Wire services together
ansible-playbook integrate.yml

# 7. Verify
ansible-playbook setup/verify-lab.yml
```

Total time: ~50 minutes (mostly automated).

---

## 10. Playbook Reference

### Setup Playbooks (`setup/`)

| Playbook | Layer | Tags | Purpose |
|----------|-------|------|---------|
| `site.yml` | All | all tags | Master orchestrator — runs everything |
| `configure-dns.yml` | 1 | identity, dns | Register VMs in IdM DNS |
| `enroll-idm-clients.yml` | 1 | identity, idm | Enroll hosts as IdM clients |
| `configure-idm-users.yml` | 1 | identity, idm | Create users and groups |
| `deploy-vault.yml` | 2 | secrets, vault | Deploy Vault container (if needed) |
| `configure-vault.yml` | 2 | secrets, vault | Configure Vault engines and policies |
| `configure-vault-ssh.yml` | 2 | secrets, vault | Configure SSH CA trust on hosts |
| `deploy-arista.yml` | 3 | network, arista | Deploy cEOS switch fabric |
| `deploy-rhel-containers.yml` | 3 | network, containers | Deploy DB/App RHEL containers |
| `deploy-db-app.yml` | 4 | app, database | Deploy PostgreSQL and Flask app |
| `deploy-netbox.yml` | 5 | cmdb, netbox | Deploy Netbox |
| `configure-netbox.yml` | 5 | cmdb, netbox | Seed Netbox with data |
| `deploy-splunk.yml` | 6 | logging, splunk | Deploy Splunk |
| `deploy-wazuh.yml` | 6 | siem, wazuh | Deploy Wazuh stack |
| `deploy-wazuh-agents.yml` | 6 | siem, wazuh | Deploy Wazuh agents |
| `configure-opa-base.yml` | 7 | policy, opa | Load OPA policies |
| `configure-aap-policy.yml` | 7 | policy, aap | Configure AAP → OPA gateway |
| `configure-aap-ldap.yml` | 7 | policy, aap | Configure AAP → IdM LDAP |
| `deploy-spire.yml` | 8 | spire | Deploy SPIRE server + agents |
| `configure-wazuh-eda.yml` | 9 | eda, siem | Configure Wazuh → EDA webhook |
| `verify-lab.yml` | 10 | verify | Full lab verification |

### Optional Playbooks

| Playbook | Purpose |
|----------|---------|
| `integrate-splunk.yml` | Centralized log shipping to Splunk |
| `deploy-dashboard.yml` | Topology dashboard on central |
| `redeploy-keycloak.yml` | Re-deploy Keycloak with external hostname |

### SSH Lockdown Playbooks (`setup/ssh_lockdown/`)

| Playbook | Layer | Purpose |
|----------|-------|---------|
| `lockdown-all.yml` | All | Apply all 4 lockdown layers |
| `lockdown-firewall.yml` | 1 | Restrict SSH source IPs |
| `lockdown-idm-hbac.yml` | 2 | Restrict IdM user login |
| `lockdown-vault-policies.yml` | 3 | Restrict credential generation |
| `lockdown-wazuh-bypass.yml` | 4 | Detect bypass attempts |

### Section Playbooks

| Section | Playbook | Purpose |
|---------|----------|---------|
| 1 | `verify-zta-services.yml` | Health checks |
| 1 | `test-vault-integration.yml` | Dynamic DB creds |
| 1 | `test-vault-ssh.yml` | SSH certificate lifecycle |
| 1 | `test-opa-policy.yml` | Policy allow/deny |
| 2 | `check-db-policy.yml` | OPA db_access gate |
| 2 | `create-db-credential.yml` | Vault dynamic creds |
| 2 | `configure-db-access.yml` | Arista ACL |
| 2 | `deploy-application.yml` | Deploy app with creds |
| 2 | `rotate-credentials.yml` | Credential rotation |
| 3 | `apply-security-patch.yml` | SSH/audit hardening |
| 4 | `configure-vlan.yml` | SPIFFE + VLAN |
| 5 | `simulate-bruteforce.yml` | SSH brute-force sim |
| 5 | `revoke-app-credentials.yml` | Vault lease revocation |
| 5 | `restore-app-credentials.yml` | Restore after incident |

### Integration Playbooks (Repo Root)

| Playbook | Purpose |
|----------|---------|
| `integrate.yml` | Wire IdM + OPA + service certs |
| `setup/configure-keycloak.yml` | Add Keycloak OIDC + JWT OPA |

---

## 11. Troubleshooting

### Vault is sealed after reboot

Vault re-seals on every restart. Re-run the deploy playbook or unseal
manually:

```bash
ssh rhel@central.zta.lab
export VAULT_ADDR=http://localhost:8200
# Get keys from /opt/vault-data/init-keys.json
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>
```

### IdM client enrollment fails

Ensure DNS is working first:
```bash
dig central.zta.lab
```
If DNS fails, the IdM server may not be responding. Check:
```bash
ssh rhel@central.zta.lab
sudo ipactl status
```

### Containers not starting on central

Check available disk and memory:
```bash
ssh rhel@central.zta.lab
df -h
free -h
podman ps -a    # see stopped containers
podman logs <container-name>   # check why it failed
```

### Arista cEOS switches unreachable

cEOS containers take 60-90 seconds to boot fully:
```bash
ssh -p 2001 admin@central.zta.lab
# If "Connection refused", wait and retry
```

### OPA returns empty results

Policies may not be loaded:
```bash
curl http://central.zta.lab:8181/v1/policies | python3 -m json.tool
# If empty, re-run:
ansible-playbook setup/configure-opa-base.yml
```

### AAP Policy as Code not blocking

Verify the OPA gateway is configured:
```bash
curl -s http://central.zta.lab:8181/v1/data/aap/gateway/decision \
  -d '{"input":{"user":{"username":"neteng","groups":[],"is_superuser":false},"action":"launch","resource":{"name":"Apply Security Patch"}}}' \
  | python3 -m json.tool
# Should show "allow": false
```

### SPIRE agent cannot fetch SVID

```bash
ssh rhel@control.zta.lab
sudo systemctl status spire-agent
sudo /opt/spire/bin/spire-agent api fetch x509 -socketPath /run/spire/agent/api.sock
```

### EDA not receiving Wazuh events

```bash
# Check Wazuh integration logs
ssh rhel@central.zta.lab
sudo podman logs wazuh-manager 2>&1 | grep -i integrat

# Check EDA is listening
curl http://control.zta.lab:5000/endpoint
```

### Data-plane connectivity (app to DB) broken

```bash
# Test from the app container
ssh -p 2023 rhel@central.zta.lab
nc -zv 10.30.0.10 5432

# Check switch ACLs
ssh -p 2002 admin@central.zta.lab
show access-lists

# Check firewall on DB
ssh -p 2022 rhel@central.zta.lab
sudo firewall-cmd --list-all
```

### Full re-deployment

If you need to start fresh:
```bash
# Stop and remove all containers on central
ssh rhel@central.zta.lab
sudo podman rm -af
sudo podman volume prune -f

# Re-run the full deployment
cd /tmp/zta-workshop-aap
ansible-playbook setup/site.yml
```

---

## Deployment Architecture Summary

```
Phase 0          Phase 1              Phase 2                    Phase 3
────────         ────────             ────────                   ────────
Clone repos      IdM + Keycloak       Workshop services          Wire together
Install colls    + OPA                (10 layers)                + verify
Update inventory                                

                 ┌──────────┐   ┌─────────────────────┐   ┌──────────────┐
                 │ IdM      │   │ L1: Identity & DNS  │   │ integrate.yml│
                 │ Keycloak │   │ L2: Vault           │   │              │
                 │ OPA      │   │ L3: Network + VMs   │   │ verify-lab   │
                 │          │   │ L4: DB + App        │   │   .yml       │
                 │ (separate│   │ L5: Netbox          │   │              │
                 │  repo)   │   │ L6: Splunk + Wazuh  │   └──────────────┘
                 │          │   │ L7: OPA + AAP       │
                 └──────────┘   │ L8: SPIRE           │
                     ~20m       │ L9: EDA             │
                                │ L10: Verify         │
                                └─────────────────────┘
                                         ~30m                    ~5m
```

Total deployment time: **~55 minutes** (mostly unattended).
