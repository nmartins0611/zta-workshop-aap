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

---

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
