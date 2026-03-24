# Section 1 — ZTA Foundation & AAP Integration

## Objective

Connect Ansible Automation Platform to the Zero Trust infrastructure so that
all subsequent automation is identity-aware, secrets-managed, and
policy-governed.

## What You Will Configure in AAP

By the end of this section, AAP will have:

1. **Credentials** for each integration point (IdM, Vault, Cisco, machines)
2. **An Inventory** sourced from Netbox (CMDB as source of truth)
3. **A Project** pointing to this workshop repository
4. **Job Templates** for verifying ZTA services and testing the integration

## Architecture

```
  ┌──────────────────────────────────────────────┐
  │                AAP Controller                 │
  │                                               │
  │  Credentials:                                 │
  │    - Machine (SSH key / password)             │
  │    - HashiCorp Vault                          │
  │    - Cisco IOS (network device)               │
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

## Steps

### Step 1 — Create Machine Credential

In AAP Controller:

1. Navigate to **Resources → Credentials → Add**
2. Name: `ZTA Machine Credential`
3. Credential Type: `Machine`
4. Username: `rhel`
5. Password: from your lab assignment
6. Privilege Escalation Method: `sudo`

### Step 2 — Create HashiCorp Vault Credential

1. Navigate to **Resources → Credentials → Add**
2. Name: `ZTA Vault Credential`
3. Credential Type: `HashiCorp Vault Secret Lookup`
4. Vault Server URL: `https://vault.zta.lab:8200`
5. Token: your Vault root token
6. API Version: `v2`

### Step 3 — Create Network Credential

1. Navigate to **Resources → Credentials → Add**
2. Name: `ZTA Cisco Credential`
3. Credential Type: `Network`
4. Username: `admin`
5. Password: retrieve from Vault (`secret/network/switch01`)

### Step 4 — Create Inventory from Netbox

1. Navigate to **Resources → Inventories → Add**
2. Name: `ZTA Lab Inventory`
3. Add a **Source**: Netbox
4. Source URL: `http://netbox.zta.lab:8000`
5. Token: your Netbox API token
6. Sync the inventory — verify all hosts appear

### Step 5 — Create Source Control Credential (Gitea)

1. Navigate to **Resources → Credentials → Add**
2. Name: `ZTA Gitea Credential`
3. Credential Type: `Source Control`
4. Username: your Gitea username
5. Password: your Gitea password or access token

### Step 6 — Create Project from Gitea

1. Navigate to **Resources → Projects → Add**
2. Name: `ZTA Workshop`
3. Source Control Type: `Git`
4. Source Control URL: `http://gitea.zta.lab:3000/zta-workshop/zta-app.git`
5. Source Control Credential: `ZTA Gitea Credential`
6. Sync the project — verify it pulls successfully

### Step 7 — Create Job Templates

Create the following job templates:

| Template Name | Playbook | Inventory | Credentials |
|---------------|----------|-----------|-------------|
| Verify ZTA Services | `section1/playbooks/verify-zta-services.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Test Vault Integration | `section1/playbooks/test-vault-integration.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Test Vault SSH OTP | `section1/playbooks/test-vault-ssh.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Test OPA Policy | `section1/playbooks/test-opa-policy.yml` | ZTA Lab Inventory | ZTA Machine Credential |

### Step 8 — Run Verification

Launch the **Verify ZTA Services** template and confirm all services report healthy.

---

## Vault SSH OTP — Short-Lived Machine Credentials

This section demonstrates one of the most powerful Zero Trust patterns:
**eliminating static machine passwords** in favour of just-in-time, single-use
credentials issued by Vault.

### How It Works

```
  ┌────────────┐        ┌─────────────┐        ┌──────────────┐
  │  Operator / │  1.    │  HashiCorp  │        │  Target RHEL │
  │  AAP Job    │───────▶│   Vault     │        │   Host       │
  │             │ Request│  (SSH OTP)  │        │              │
  │             │  OTP   │             │        │ vault-ssh    │
  │             │◀───────│ key: a7b3.. │        │   user       │
  │             │  2.    │             │        │              │
  │             │        │             │        │ vault-ssh-   │
  │             │───────────────────────────────▶│  helper      │
  │             │  3. SSH with OTP               │              │
  │             │                                │  ┌────────┐  │
  │             │        │             │◀────────│──│  PAM   │  │
  │             │        │  Validates  │  4.     │  └────────┘  │
  │             │        │   OTP ✓     │ Verify  │              │
  │             │        │  Marks used │         │  Login OK ✓  │
  └────────────┘        └─────────────┘        └──────────────┘
```

1. **Request** — The operator (or AAP job) asks Vault for an OTP:
   `vault write ssh/creds/rhel-otp ip=192.168.1.14`
2. **Issue** — Vault generates a random OTP and records it
3. **Login** — The operator SSHes as `vault-ssh` using the OTP as the password
4. **Verify** — `vault-ssh-helper` (via PAM) calls back to Vault to validate.
   Vault checks the OTP, marks it as consumed, and allows login.
5. **Expired** — Any reuse attempt is rejected. The OTP is gone.

### Zero Trust Properties

| Property | How It's Achieved |
|----------|-------------------|
| No standing access | `vault-ssh` has no static password |
| Just-in-time | OTP generated only when needed |
| Short-lived | Single-use — expires on first login |
| Least privilege | `vault-ssh` has limited sudo (status/logs only) |
| Audited | Every OTP request is logged in Vault's audit log |
| Policy-governed | Vault policy `ssh-access` controls who can request OTPs |

### Manual Demo (Outside AAP)

From the Vault server or any host with the Vault CLI:

```bash
# Generate an OTP for the app server
export VAULT_ADDR=https://vault.zta.lab:8200
export VAULT_SKIP_VERIFY=true
vault write ssh/creds/rhel-otp ip=192.168.1.14

# Use the OTP to log in
ssh vault-ssh@192.168.1.14
# Enter the OTP when prompted — you're in!

# Try the same OTP again — DENIED (single-use)
ssh vault-ssh@192.168.1.14
# Permission denied
```

---

## Validation Checklist

- [ ] Machine credential connects to all RHEL servers
- [ ] Vault credential retrieves a test secret
- [ ] Network credential connects to the Cisco switch
- [ ] Gitea credential authenticates to `gitea.zta.lab:3000`
- [ ] Netbox inventory sync shows all lab hosts
- [ ] Project syncs from Gitea successfully
- [ ] Verify ZTA Services job completes successfully
- [ ] Test Vault Integration job retrieves database credentials
- [ ] Test Vault SSH OTP job generates and uses an OTP successfully
- [ ] Test Vault SSH OTP job confirms OTP reuse is blocked
- [ ] Test OPA Policy job shows allow/deny decisions
