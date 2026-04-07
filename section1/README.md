# Section 1 — Configure ZTA Components & AAP Integration

**AsciiDoc lab:** [`lab/index.adoc`](lab/index.adoc)

> **2-Hour Workshop Delivery Guide**
>
> | Exercise | Status | Est. Time |
> |----------|--------|-----------|
> | 1.1 — Configure AAP Credentials | **Core** | 10 min |
> | 1.2 — Configure Inventory & Project | **Core** | 5 min |
> | 1.3 — Create Job Templates | **Core** | 3 min |
> | 1.4 — Verify All ZTA Services | **Core** | 2 min |
> | 1.5 — Test Vault Dynamic Credentials | **Core** | 3 min |
> | 1.6 — Test Vault SSH Signed Certificates | **Core** | 3 min |
> | 1.7 — Test OPA Policy Decisions | **Core** | 2 min |
> | 1.8 — Certificate Trust Chain Debugging | **Extended** | 25 min |
>
> For a **2-hour workshop**, complete exercises **1.1–1.7** (~25 min).
> Skip exercise 1.8 unless you have extra time or are running a longer format.

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
| **No standing access** | Vault SSH signed certificates replace static keys |
| **Least privilege** | Vault policies scope secrets to specific roles |
| **Policy-driven access** | OPA deny-by-default with explicit allow rules |

## Architecture

```
  ┌───────────────────────────────────────────────────┐
  │                 AAP Controller                     │
  │                                                   │
  │  Credentials (all Vault-sourced at runtime):      │
  │    - Machine    ← Vault KV: secret/machine/rhel   │
  │    - Arista     ← Vault KV: secret/network/arista │
  │    - Vault SSH  ← Vault AppRole: ssh/sign/*       │
  │    - NetBox     ← Custom type (env injection)     │
  │                                                   │
  │  Inventory:                                       │
  │    - Static or synced from Netbox                 │
  │                                                   │
  │  Templates:                                       │
  │    - Verify ZTA Services                          │
  │    - Test Vault Integration                       │
  │    - Test Vault SSH Certificates                  │
  │    - Test OPA Policy Check                        │
  └──────┬───────────┬──────────┬─────────────────────┘
         │           │          │
    ┌────▼───┐  ┌───▼────┐  ┌─▼──────────┐  ┌────────────┐
    │  IdM   │  │ Vault  │  │   OPA      │  │  Netbox    │
    │central │  │vault   │  │ central    │  │ netbox     │
    └────────┘  └────────┘  └────────────┘  └────────────┘
```

---

## Exercise 1.1 — Configure AAP Credentials (Vault-Sourced)

In a Zero Trust environment, **no secrets are stored in the automation
platform itself**. All credentials are sourced from HashiCorp Vault at job
runtime. The only credential with a stored password is the Vault lookup
credential — it bootstraps the entire trust chain.

```
  Vault (single source of truth for all secrets)
    │
    ├─→ ZTA Vault Credential         ← bootstrap (only stored password)
    │     │
    │     ├─→ ZTA Machine Credential  ← password pulled from Vault KV at runtime
    │     │
    │     └─→ ZTA Arista Credential   ← username/password pulled from Vault KV
    │
    ├─→ ZTA Vault SSH Credential      ← AppRole signs ephemeral SSH certs
    │
    └─→ ZTA NetBox Credential         ← API token (custom credential type)
```

### Step 1 — Verify Vault Secrets Are Populated

Before creating AAP credentials, confirm the secrets exist in Vault:

```bash
export VAULT_ADDR=http://vault.zta.lab:8200
vault login -method=userpass username=admin password=ansible123!

# Machine credentials (SSH user for managed hosts)
vault kv get secret/machine/rhel
# Expected: password = ansible123!

# Network device credentials (Arista cEOS switches)
vault kv get secret/network/arista
# Expected: username = admin, password = admin

# Database admin credentials
vault kv get secret/db/admin
# Expected: username = postgres, password = postgres123!
```

> **ZTA Concept**: Every credential lives in Vault. If Vault is sealed or
> unreachable, AAP cannot retrieve secrets — jobs fail safe rather than
> falling back to stored passwords.

---

### Step 2 — Create the Vault Lookup Credential (Bootstrap)

This is the **only credential with a directly stored password**. It
authenticates to Vault so that all other credentials can pull their
secrets at runtime.

1. Navigate to **Resources → Credentials → Add**
2. Configure:

| Field | Value |
|-------|-------|
| Name | `ZTA Vault Credential` |
| Credential Type | `HashiCorp Vault Secret Lookup` |
| Vault Server URL | `http://vault.zta.lab:8200` |
| Username | `admin` |
| Password | `ansible123!` |
| API Version | `v2` |

3. Click **Save**

> **Why userpass?** For the workshop, Vault uses username/password auth.
> In production, you would use AppRole, TLS certificates, or OIDC — never
> a static password.

---

### Step 3 — Create the Machine Credential (Vault-Sourced)

This credential authenticates AAP to managed RHEL hosts. Instead of
storing the password in AAP, it is **looked up from Vault** every time
a job runs.

1. Navigate to **Resources → Credentials → Add**
2. Configure the base fields:

| Field | Value |
|-------|-------|
| Name | `ZTA Machine Credential` |
| Credential Type | `Machine` |
| Username | `rhel` |
| Privilege Escalation Method | `sudo` |

3. **Do NOT type a password.** Instead, click the **key icon** (🔑) next
   to the **Password** field. This opens the **External Secret Lookup**
   dialog.

4. Configure the external lookup:

| Field | Value |
|-------|-------|
| Credential | `ZTA Vault Credential` |
| Secret Path | `secret/data/machine/rhel` |
| Secret Key | `password` |

5. Click **OK** to confirm the lookup

6. Repeat for the **Privilege Escalation Password** field:
   - Click the **key icon** next to **Privilege Escalation Password**
   - Credential: `ZTA Vault Credential`
   - Secret Path: `secret/data/machine/rhel`
   - Secret Key: `become_password`
   - Click **OK**

7. Click **Save**

> **What just happened?** The Password and Become Password fields now show
> a key icon instead of dots. AAP will call Vault's KV API at
> `secret/data/machine/rhel` when a job launches, retrieve the current
> password, and inject it into the SSH connection. If you rotate the
> password in Vault, the next job automatically uses the new value — no
> AAP changes needed.

**Verify it works:**

```bash
# Change the password in Vault to confirm AAP reads dynamically
vault kv put secret/machine/rhel password=ansible123! become_password=ansible123!
```

---

### Step 4 — Create the Arista Network Credential (Vault-Sourced)

The Arista cEOS switch credentials are already stored in Vault at
`secret/network/arista` (populated by `setup/configure-vault.yml`).

1. Navigate to **Resources → Credentials → Add**
2. Configure the base fields:

| Field | Value |
|-------|-------|
| Name | `ZTA Arista Credential` |
| Credential Type | `Network` |

3. Click the **key icon** next to **Username**:

| Field | Value |
|-------|-------|
| Credential | `ZTA Vault Credential` |
| Secret Path | `secret/data/network/arista` |
| Secret Key | `username` |

4. Click the **key icon** next to **Password**:

| Field | Value |
|-------|-------|
| Credential | `ZTA Vault Credential` |
| Secret Path | `secret/data/network/arista` |
| Secret Key | `password` |

5. Click **Save**

> **ZTA Concept**: Even the network device credentials come from Vault.
> No AAP admin can see the switch password — it is resolved at runtime
> and never stored in AAP's database.

---

### Step 5 — Create the NetBox CMDB Credential

> **Note**: The `NetBox` credential type is pre-created by the setup playbook
> (`setup/configure-aap-netbox.yml`). If it is missing, expand the manual
> steps below.

1. Navigate to **Resources → Credentials → Add**
2. Configure:

| Field | Value |
|-------|-------|
| Name | `ZTA NetBox Credential` |
| Credential Type | `NetBox` |
| NetBox URL | `http://netbox.zta.lab:8880` |
| API Token | `0123456789abcdef0123456789abcdef01234567` |

3. Click **Save**

> **How the credential type works**: The `NetBox` credential type injects two
> environment variables into every job that uses it:
>
> | Env var | Value |
> |---------|-------|
> | `NETBOX_API` | The NetBox URL |
> | `NETBOX_TOKEN` | The API token (secret) |
>
> These are auto-detected by the `netbox.netbox.nb_inventory` plugin and by
> all `netbox.netbox` collection modules, so playbooks never need hardcoded
> NetBox credentials.

<details>
<summary><strong>Manual: Create the NetBox credential type from scratch</strong></summary>

If the setup playbook has not been run, create the credential type first:

1. Navigate to **Administration → Credential Types → Add**
2. Name: `NetBox`
3. **Input Configuration** (paste as YAML):

```yaml
fields:
  - id: netbox_url
    label: NetBox URL
    type: string
    help_text: "Full URL (e.g. http://netbox.zta.lab:8880)"
  - id: netbox_token
    label: API Token
    type: string
    secret: true
required:
  - netbox_url
  - netbox_token
```

4. **Injector Configuration** (paste as YAML):

```yaml
env:
  NETBOX_API: "{{ netbox_url }}"
  NETBOX_TOKEN: "{{ netbox_token }}"
```

5. Click **Save**
6. Now return to the steps above to create the credential

</details>

---

### Step 6 — Vault SSH Signed Certificate Credential (Instructor Pre-configured)

> **Note**: This credential is pre-created by the instructor using
> `setup/configure-aap-credentials.yml`. It uses Vault AppRole
> authentication — not username/password — so it cannot be created
> through the AAP UI alone.

The `ZTA Vault SSH Credential` enables AAP to request **ephemeral SSH
certificates** from Vault's SSH CA engine. When a job template uses this
credential, AAP:

1. Authenticates to Vault via AppRole (role-id + secret-id)
2. Generates a temporary SSH keypair
3. Sends the public key to Vault for signing
4. Receives a time-bound certificate (30 min TTL)
5. Uses the signed certificate to SSH into the target host
6. The certificate expires — no persistent keys on disk

```bash
# Verify the SSH CA is configured
vault read ssh/config/ca
# Expected: public_key = ssh-rsa AAAA...

# Verify the signing role exists
vault read ssh/roles/ssh-signer
# Expected: allowed_users = rhel,aap-service, ttl = 30m
```

To see this in action, run **Exercise 1.6 — Test Vault SSH Certificates**.

---

### Credential Summary

| Credential | Type | Secret Source | Vault Path |
|-----------|------|---------------|------------|
| ZTA Vault Credential | HashiCorp Vault Lookup | Stored (bootstrap) | — |
| ZTA Machine Credential | Machine | **Vault KV** (runtime) | `secret/data/machine/rhel` |
| ZTA Arista Credential | Network | **Vault KV** (runtime) | `secret/data/network/arista` |
| ZTA NetBox Credential | NetBox (custom) | Stored (API token) | — |
| ZTA Vault SSH Credential | Vault Signed SSH | **Vault AppRole** | `ssh/sign/ssh-signer` |

> **Key takeaway**: Only the Vault lookup credential and the NetBox token
> are stored in AAP. The Machine and Arista passwords are **never in
> AAP's database** — they are fetched from Vault at the moment a job
> launches. This is the Zero Trust principle of *no standing access*
> applied to the automation platform itself.

---

## Exercise 1.2 — Configure Inventory & Project

### Project from Gitea (create first — the inventory source depends on it)

1. Navigate to **Resources → Projects → Add**
2. Name: `ZTA Workshop`
3. Source Control Type: `Git`
4. Source Control URL: `http://gitea.zta.lab:3000/zta-workshop/zta-app.git`
5. Source Control Credential: `ZTA Gitea Credential`
6. Click **Save** and wait for the sync to complete (green status)

### Inventory from NetBox

**Step 1 — Create the inventory**

1. Navigate to **Resources → Inventories → Add → Add inventory**
2. Name: `ZTA Lab Inventory`
3. Organization: `Default`
4. Click **Save**

**Step 2 — Add the NetBox inventory source**

1. Inside the `ZTA Lab Inventory`, go to the **Sources** tab
2. Click **Add**
3. Configure:

| Field | Value |
|-------|-------|
| Name | `NetBox CMDB` |
| Source | `Sourced from a Project` |
| Project | `ZTA Workshop` |
| Inventory file | `inventory/netbox_inventory.yml` |
| Credential | `ZTA NetBox Credential` (type: NetBox) |

4. Under **Update options**, enable:
   - **Overwrite** — replace hosts on each sync (NetBox is the source of truth)
   - **Update on launch** — re-sync before every job that uses this inventory
5. Click **Save**

**Step 3 — Sync and verify**

1. Click the **Sync** (refresh) button on the `NetBox CMDB` source
2. Wait for the sync to complete (green status)
3. Go to the **Hosts** tab — you should see all workshop devices:

| Host | Device Role |
|------|-------------|
| `central.zta.lab` | Identity Provider |
| `control.zta.lab` | Automation Controller |
| `vault.zta.lab` | Secrets Manager |
| `wazuh.zta.lab` | Security Appliance |
| `netbox.zta.lab` | CMDB Server |
| `app.zta.lab` | Application Server |
| `db.zta.lab` | Application Server |
| `ceos1.zta.lab` | Network Switch |
| `ceos2.zta.lab` | Network Switch |
| `ceos3.zta.lab` | Network Switch |

4. Go to the **Groups** tab — verify groups were created by device role,
   site, tag, and platform (e.g. `device_role_identity_provider`,
   `tag_zero_trust`, `platform_rhel_9`)

> **ZTA Concept**: The inventory is sourced from the CMDB — not a static file.
> If a device is decommissioned in NetBox, it disappears from AAP on the next
> sync. NetBox is the *single source of truth* for infrastructure state.

**Troubleshooting**

If the sync fails:

```bash
# Verify NetBox is reachable and the token works
curl -s -H "Authorization: Token 0123456789abcdef0123456789abcdef01234567" \
  http://netbox.zta.lab:8880/api/dcim/devices/ | python3 -m json.tool

# Verify the netbox.netbox collection is in the AAP execution environment
# (check the EE image used by the project)
```

---

## Exercise 1.3 — Create Job Templates

| Template Name | Playbook | Inventory | Credentials |
|---------------|----------|-----------|-------------|
| Verify ZTA Services | `section1/playbooks/verify-zta-services.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Test Vault Integration | `section1/playbooks/test-vault-integration.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Test Vault SSH Certificates | `section1/playbooks/test-vault-ssh.yml` | ZTA Lab Inventory | ZTA Machine Credential |
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

## Exercise 1.6 — Test Vault SSH Signed Certificates

Launch **Test Vault SSH Certificates**.

Each RHEL host trusts the Vault SSH Certificate Authority. The only way to
authenticate via certificate is with a key signed by Vault. No static SSH
keys are distributed — every certificate is generated on demand, time-bound,
and scoped to specific principals.

**What to observe:**

- An ephemeral keypair is generated and signed by Vault's SSH CA
- Certificate details are displayed (TTL, valid principals, serial number)
- SSH login to `app` and `db` hosts succeeds using the signed certificate
- The certificate has a 30-minute TTL (configurable)

### Manual Demo

```bash
export VAULT_ADDR=http://vault.zta.lab:8200
export VAULT_SKIP_VERIFY=true
vault login -method=userpass username=admin password=ansible123!

# Generate an ephemeral keypair
ssh-keygen -t rsa -b 2048 -f /tmp/ephemeral -N '' -q

# Sign the public key with Vault
vault write -field=signed_key ssh/sign/ssh-signer \
  public_key=@/tmp/ephemeral.pub valid_principals=rhel > /tmp/ephemeral-cert.pub

# Inspect the certificate
ssh-keygen -L -f /tmp/ephemeral-cert.pub

# SSH using the signed certificate
ssh -i /tmp/ephemeral -o CertificateFile=/tmp/ephemeral-cert.pub \
  -p 2023 rhel@192.168.1.11

# Clean up
rm -f /tmp/ephemeral /tmp/ephemeral.pub /tmp/ephemeral-cert.pub
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

- [ ] Vault Credential created (bootstrap — only stored password)
- [ ] Machine Credential created with Vault KV external lookup (key icon visible)
- [ ] Arista Credential created with Vault KV external lookup (key icon visible)
- [ ] NetBox Credential created with custom credential type
- [ ] Vault SSH Credential present (instructor pre-configured)
- [ ] Netbox inventory synced with all lab hosts
- [ ] Gitea project synced successfully
- [ ] Verify ZTA Services — all services healthy
- [ ] Vault Integration — dynamic DB credentials generated and revoked
- [ ] Vault SSH Certificates — signed cert login works, certificate details visible
- [ ] OPA Policy — correct allow/deny for each scenario

---

# Extended Exercises (Longer Formats Only)

# Exercise 1.8 — Certificate Trust Chain Debugging (Hands-On)

## The Scenario

A test HTTPS endpoint has been deployed on central, but it was set up with
a **self-signed certificate** instead of one issued by the IdM CA. Any client
that trusts the IdM CA will reject the connection because the certificate
issuer is unknown.

You must diagnose the TLS failure, identify the wrong certificate authority,
and fix it by requesting a proper certificate from IdM.

> **Instructor:** Run `ansible-playbook section1/playbooks/break-cert-trust.yml`

## Duration: ~25 minutes

---

## Step 1 — Observe the TLS Failure

Try to reach the test endpoint:

```bash
curl https://central.zta.lab:9443/
```

You'll get an error:
```
curl: (60) SSL certificate problem: self-signed certificate
```

Even with `-v` (verbose), curl tells you the certificate is not trusted:
```bash
curl -v https://central.zta.lab:9443/ 2>&1 | grep -i "ssl\|issuer\|verify"
```

---

## Step 2 — Inspect the Certificate

Use `openssl` to examine the certificate the server is presenting:

```bash
echo | openssl s_client -connect central.zta.lab:9443 2>/dev/null | \
  openssl x509 -text -noout | grep -E "Issuer|Subject|Not "
```

You'll see:
```
Issuer: CN = central.zta.lab, O = Self-Signed, OU = NOT-IDM-CA
Subject: CN = central.zta.lab, O = Self-Signed, OU = NOT-IDM-CA
Not Before: ...
Not After : ...
```

The **Issuer** is "Self-Signed / NOT-IDM-CA". This certificate was not
issued by the IdM CA, so any client that trusts the IdM CA will reject it.

**Compare with a working service** (the IdM web UI itself):

```bash
echo | openssl s_client -connect central.zta.lab:443 2>/dev/null | \
  openssl x509 -text -noout | grep -E "Issuer|Subject"
```

You'll see the IdM CA as the issuer — this is the trusted chain.

---

## Step 3 — Understand the Trust Chain

In a Zero Trust environment, the IdM CA is the **trust anchor**. All
services should present certificates signed by this CA. When a service
uses a self-signed cert:

- **Automated clients** (like Ansible, curl) reject the connection
- **Other services** cannot verify the identity of the endpoint
- **The service is effectively untrusted** in the ZTA fabric

The IdM CA certificate is available at `/etc/ipa/ca.crt` on enrolled hosts.
You can verify this:

```bash
ssh rhel@central.zta.lab
cat /etc/ipa/ca.crt | openssl x509 -text -noout | grep "Issuer"
```

---

## Step 4 — Fix: Request a Certificate from IdM

SSH to central and request a proper certificate using `ipa-getcert`:

```bash
ssh rhel@central.zta.lab

# Request a certificate from the IdM CA
sudo ipa-getcert request \
  -K HTTP/central.zta.lab \
  -D central.zta.lab \
  -f /etc/pki/tls/certs/zta-test-idm.crt \
  -k /etc/pki/tls/private/zta-test-idm.key \
  -N CN=central.zta.lab \
  -w

# Check the request status
sudo ipa-getcert list | grep -A5 "zta-test"
# Expected: status: MONITORING (certificate issued and tracked)
```

---

## Step 5 — Reconfigure the Endpoint

Update the test endpoint to use the new IdM-signed certificate:

```bash
# Edit the test endpoint script
sudo vi /opt/zta-test-https.py
```

Change the cert paths from:
```python
ctx.load_cert_chain(
    '/etc/pki/tls/certs/zta-test-selfsigned.crt',
    '/etc/pki/tls/private/zta-test-selfsigned.key'
)
```

To:
```python
ctx.load_cert_chain(
    '/etc/pki/tls/certs/zta-test-idm.crt',
    '/etc/pki/tls/private/zta-test-idm.key'
)
```

Restart the service:
```bash
sudo systemctl restart zta-test-https
```

---

## Step 6 — Verify the Fix

```bash
# From any IdM-enrolled host (which trusts the IdM CA):
curl https://central.zta.lab:9443/
# Expected: {"status": "ok", "service": "zta-test-endpoint", ...}

# Verify the certificate chain
echo | openssl s_client -connect central.zta.lab:9443 2>/dev/null | \
  openssl x509 -text -noout | grep "Issuer"
# Expected: Issuer shows the IdM CA, not "Self-Signed"
```

---

## ZTA Lesson

Zero Trust requires **verified identity for services**, not just users.
A self-signed certificate means the service cannot prove its identity to
clients. In a ZTA environment:

- All service certificates should be issued by the organisation's CA (IdM)
- `ipa-getcert` automates certificate lifecycle (request, renew, track)
- Expired or untrusted certificates break service-to-service communication
- Certificate monitoring (`ipa-getcert list`) is part of operational hygiene

## Certificate Trust Validation Checklist

- [ ] `curl https://central.zta.lab:9443/` fails with TLS error
- [ ] `openssl s_client` shows "Self-Signed" issuer
- [ ] Comparison with working IdM service shows the correct CA
- [ ] `ipa-getcert request` issues a new cert from the IdM CA
- [ ] Test endpoint reconfigured with the IdM-signed cert
- [ ] `curl https://central.zta.lab:9443/` succeeds after fix
- [ ] `openssl` confirms the IdM CA is now the issuer
