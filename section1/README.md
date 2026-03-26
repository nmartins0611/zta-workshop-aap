# Section 1 — Configure ZTA Components & AAP Integration

## Objective

Configure Ansible Automation Platform and connect it to the Zero Trust
infrastructure. By the end of this section, AAP will be integrated with
IdM (identity), Vault (secrets), OPA (policy), Netbox (CMDB), and Gitea
(source control). You will verify every service is healthy and test the
integrations.

## Zero Trust Principles

| Principle | How This Section Demonstrates It |
|-----------|----------------------------------|
| **Never trust, always verify** | Every service health is checked, not assumed |
| **Short-lived credentials** | Vault dynamic DB credentials expire after TTL |
| **No standing access** | SSH OTP replaces static machine passwords |
| **Least privilege** | Vault policies scope secrets to specific roles |
| **Policy-driven access** | OPA deny-by-default with explicit allow rules |

## Architecture

```
  ┌──────────────────────────────────────────────┐
  │                AAP Controller                 │
  │                                               │
  │  Credentials:                                 │
  │    - Machine (SSH key / password)             │
  │    - HashiCorp Vault                          │
  │    - Arista EOS (network device)               │
  │    - Gitea source control                     │
  │                                               │
  │  Inventory:                                   │
  │    - Synced from Netbox                       │
  │                                               │
  │  Project:                                     │
  │    - Git → Gitea (gitea.zta.lab:3000)         │
  │                                               │
  │  Templates:                                   │
  │    - Verify ZTA Services                      │
  │    - Test Vault Integration                   │
  │    - Test Vault SSH OTP                       │
  │    - Test OPA Policy Check                    │
  └──────┬───────────┬──────────┬────────────────┘
         │           │          │
    ┌────▼───┐  ┌───▼────┐  ┌─▼──────────┐  ┌────────────┐
    │  IdM   │  │ Vault  │  │   OPA      │  │  Netbox    │
    │central │  │vault   │  │ central    │  │ netbox     │
    └────────┘  └────────┘  └────────────┘  └────────────┘
```

---

## Exercise 1.1 — Configure AAP Credentials

### Machine Credential

1. Navigate to **Resources → Credentials → Add**
2. Name: `ZTA Machine Credential`
3. Credential Type: `Machine`
4. Username: `rhel`
5. Password: from your lab assignment
6. Privilege Escalation Method: `sudo`

### HashiCorp Vault Credential

1. Navigate to **Resources → Credentials → Add**
2. Name: `ZTA Vault Credential`
3. Credential Type: `HashiCorp Vault Secret Lookup`
4. Vault Server URL: `https://vault.zta.lab:8200`
5. Username: `admin`
6. Password: `ansible123!`
7. API Version: `v2`

### Network Credential

1. Navigate to **Resources → Credentials → Add**
2. Name: `ZTA Arista Credential`
3. Credential Type: `Network`
4. Username: `admin`
5. Password: `admin` (or retrieve from Vault: `secret/network/arista`)

### Source Control Credential (Gitea)

1. Navigate to **Resources → Credentials → Add**
2. Name: `ZTA Gitea Credential`
3. Credential Type: `Source Control`
4. Username: your Gitea username
5. Password: your Gitea password or access token

---

## Exercise 1.2 — Configure Inventory & Project

### Inventory from Netbox

1. Navigate to **Resources → Inventories → Add**
2. Name: `ZTA Lab Inventory`
3. Add a **Source**: Netbox
4. Source URL: `http://netbox.zta.lab:8880`
5. Token: your Netbox API token
6. Sync the inventory — verify all hosts appear

### Project from Gitea

1. Navigate to **Resources → Projects → Add**
2. Name: `ZTA Workshop`
3. Source Control Type: `Git`
4. Source Control URL: `http://gitea.zta.lab:3000/zta-workshop/zta-app.git`
5. Source Control Credential: `ZTA Gitea Credential`
6. Sync the project — verify it pulls successfully

---

## Exercise 1.3 — Create Job Templates

| Template Name | Playbook | Inventory | Credentials |
|---------------|----------|-----------|-------------|
| Verify ZTA Services | `section1/playbooks/verify-zta-services.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Test Vault Integration | `section1/playbooks/test-vault-integration.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Test Vault SSH OTP | `section1/playbooks/test-vault-ssh.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Test OPA Policy | `section1/playbooks/test-opa-policy.yml` | ZTA Lab Inventory | ZTA Machine Credential |

---

## Exercise 1.4 — Verify All ZTA Services

Launch **Verify ZTA Services** and confirm every component is healthy:

- IdM (FreeIPA): `RUNNING`
- Vault: healthy and unsealed
- OPA: loaded policies
- Netbox: API accessible
- Kerberos: TGT obtainable
- DNS: all `*.zta.lab` names resolve
- PostgreSQL: running and accepts queries
- Arista cEOS switches: respond with EOS facts

---

## Exercise 1.5 — Test Vault Dynamic Credentials

Launch **Test Vault Integration**.

**What to observe:**

- A KV secret is read from Vault (`secret/network/arista`)
- A dynamic PostgreSQL user is generated with a 5-minute TTL
- The username is randomised (e.g. `v-root-ztaapp-s-...`)
- The credentials are immediately revoked at the end

Run the template twice — the usernames will be different each time. Vault
never reuses credentials.

---

## Exercise 1.6 — Test Vault SSH OTP

Launch **Test Vault SSH OTP**.

A `vault-ssh` user exists on each RHEL host with **no static password**. The
only way to log in is via a Vault-issued one-time password.

**What to observe:**

- OTPs are generated for the `app` and `db` hosts
- First use: SSH login succeeds
- Second use (same OTP): **login denied** — single-use enforced

### Manual Demo

```bash
export VAULT_ADDR=http://vault.zta.lab:8200
export VAULT_SKIP_VERIFY=true
vault login -method=userpass username=admin password=ansible123!

vault write ssh/creds/rhel-otp ip=192.168.1.11     # get an OTP for central (containers)
ssh -p 2023 vault-ssh@192.168.1.11                  # works once (app container)
ssh -p 2023 vault-ssh@192.168.1.11                  # denied
```

---

## Exercise 1.7 — Test OPA Policy Decisions

Launch **Test OPA Policy**.

| Test | Scenario | Expected |
|------|----------|----------|
| 1 | Patch — authorised user, all conditions met | ALLOWED |
| 2 | Patch — user not in `patch-admins` | DENIED |
| 3 | VLAN — network admin, valid VLAN | ALLOWED |
| 4 | VLAN — engineer not in `network-admins` | DENIED |
| 5 | DB access — app deployer, valid request | ALLOWED |

OPA uses **deny-by-default**: no explicit allow rule = no access. Group
membership in IdM determines what each user can do.

---

## Validation Checklist

- [ ] All credentials created in AAP
- [ ] Netbox inventory synced with all lab hosts
- [ ] Gitea project synced successfully
- [ ] Verify ZTA Services — all services healthy
- [ ] Vault Integration — dynamic DB credentials generated and revoked
- [ ] Vault SSH OTP — single-use login works, reuse blocked
- [ ] OPA Policy — correct allow/deny for each scenario
