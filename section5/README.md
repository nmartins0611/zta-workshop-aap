# Section 5 — Automated Incident Response: Brute Force → Wazuh → EDA → Vault Revocation

## Objective

Demonstrate automated incident response in a Zero Trust architecture. A
brute-force SSH attack is simulated against the app server. **Wazuh** (SIEM)
detects the attack and sends an alert to **Event-Driven Ansible** (EDA).
EDA automatically triggers an AAP job template that **revokes the application's
database credentials in Vault** — cutting off data access in seconds, with no
human intervention.

## Zero Trust Principles

| Principle | How This Section Demonstrates It |
|-----------|----------------------------------|
| **Assume breach** | Automated response doesn't wait for a human to investigate |
| **Continuous monitoring** | Wazuh SIEM watches every authentication attempt |
| **Automatic remediation** | EDA triggers credential revocation without manual approval |
| **Blast radius containment** | Revoking credentials limits what an attacker can access |
| **Just-in-time recovery** | Fresh credentials are only re-issued after investigation |

## Architecture

```
  ┌────────────┐     ┌──────────────┐     ┌────────────┐     ┌────────────┐
  │  Attacker  │     │  App Server  │     │   Wazuh    │     │    EDA     │
  │            │     │  app.zta.lab │     │  Manager   │     │ Controller │
  │            │     │              │     │            │     │            │
  │  SSH brute │────▶│ /var/log/    │────▶│ Rule 5712  │────▶│  Rulebook  │
  │  force     │     │   secure     │     │ (brute     │     │  matches   │
  │  attempt   │     │              │     │  force)    │     │  event     │
  └────────────┘     └──────────────┘     └─────┬──────┘     └─────┬──────┘
                                                │                   │
                                          Wazuh agent          Webhook POST
                                          detects failed       to EDA
                                          SSH logins
                                                                    │
                                                                    ▼
  ┌────────────┐     ┌──────────────┐     ┌────────────────────────────────┐
  │    App     │     │   Vault      │     │         AAP Controller         │
  │  Service   │     │              │     │                                │
  │            │     │  Revoke DB   │◀────│  Job: "Emergency: Revoke App   │
  │  STOPPED   │◀────│   lease      │     │        Credentials"            │
  │  No DB     │     │              │     │                                │
  │  access    │     │  DROP ROLE   │     │  Triggered by EDA              │
  └────────────┘     └──────────────┘     └────────────────────────────────┘
```

### Timeline

| Time | Event |
|------|-------|
| T+0s | Attacker starts brute-force SSH attempts on app.zta.lab |
| T+10s | Wazuh agent detects 5+ failed logins, sends to manager |
| T+12s | Wazuh manager fires rule 5712 (SSH brute force) |
| T+13s | Wazuh integration POSTs alert JSON to EDA webhook |
| T+14s | EDA rulebook matches the event, triggers AAP job |
| T+20s | AAP runs revocation playbook — Vault lease revoked |
| T+25s | Application stopped, database credentials gone |
| T+25s | **Attack surface eliminated in ~25 seconds** |

---

## Pre-requisites

Before running this section:

1. **Section 2 must be complete** — the application must be deployed with
   active Vault database credentials
2. **Wazuh agent** must be installed and active on `app.zta.lab`
3. **EDA Controller** must be running (or standalone `ansible-rulebook`)
4. **Wazuh→EDA integration** must be configured (`setup/configure-wazuh-eda.yml`)

---

## Exercise 5.1 — Create the AAP Job Templates

| Template Name | Playbook | Inventory | Credentials |
|---------------|----------|-----------|-------------|
| Emergency: Revoke App Credentials | `section5/playbooks/revoke-app-credentials.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Simulate Brute Force | `section5/playbooks/simulate-bruteforce.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Restore App Credentials | `section5/playbooks/restore-app-credentials.yml` | ZTA Lab Inventory | ZTA Machine Credential |

---

## Exercise 5.2 — Configure EDA Rulebook

### Option A — EDA Controller (AAP 2.5+)

1. Navigate to **EDA Controller → Rulebooks**
2. Import `section5/eda/wazuh-credential-revoke.yml`
3. Create a **Rulebook Activation**:
   - Name: `Wazuh Brute Force Response`
   - Rulebook: `wazuh-credential-revoke`
   - Decision Environment: your EDA decision environment
   - Restart policy: `On failure`
4. Enable the activation — it starts listening on port 5000

### Option B — Standalone ansible-rulebook

```bash
ssh rhel@control.zta.lab
ansible-rulebook --rulebook /tmp/zta-workshop-aap/section5/eda/wazuh-credential-revoke.yml \
  -i /tmp/zta-workshop-aap/inventory/hosts.ini \
  --verbose
```

---

## Exercise 5.3 — Verify the Application Is Healthy

Before the attack, confirm everything is working:

```bash
# Check the app is serving the dashboard
curl -s http://app.zta.lab:8080/health

# Check the database credentials are active
ssh -p 2022 rhel@central.zta.lab
sudo -u postgres psql -d ztaapp -c "\du" | grep v-root
```

You should see a healthy application and an active Vault-generated DB user.

---

## Exercise 5.4 — Launch the Brute-Force Attack

Launch **Simulate Brute Force** from AAP (or run the playbook directly):

```bash
ansible-playbook section5/playbooks/simulate-bruteforce.yml
```

**What happens:**

1. The playbook sends 10 rapid failed SSH login attempts to `app.zta.lab`
2. Each attempt uses the `vault-ssh` user with an incorrect password
3. The failed logins are recorded in `/var/log/secure` on the app server
4. The Wazuh agent detects the pattern and sends it to the Wazuh manager
5. Wazuh fires **rule 5712** (SSH brute force detected)

---

## Exercise 5.5 — Watch the Automated Response

After the brute-force simulation completes, observe the chain reaction:

### Check Wazuh Dashboard

Open `https://wazuh.zta.lab` and look for:
- Alert rule 5712: "SSHD brute force trying to get access to the system"
- Agent: `app.zta.lab`
- Level: 10 (high severity)

### Check EDA Controller

In the EDA Controller UI (or ansible-rulebook terminal output):
- Event received from Wazuh webhook
- Rule matched: `Revoke credentials on SSH brute-force detection`
- Action: `run_job_template` triggered

### Check AAP Controller

Navigate to **Jobs** — you should see:
- **Emergency: Revoke App Credentials** — triggered by EDA
- Status: Successful
- The job ran without any human clicking "Launch"

### Check the Application

```bash
curl -s http://app.zta.lab:8080/health
# Expected: connection refused or unhealthy — the app is stopped

ssh -p 2022 rhel@central.zta.lab
sudo -u postgres psql -d ztaapp -c "\du" | grep v-root
# Expected: no Vault-generated users — credentials are revoked
```

**The application has been automatically isolated from the database.**

---

## Exercise 5.6 — Restore the Application

After investigating the incident (in a real scenario), restore the
application with fresh credentials:

Launch **Restore App Credentials** from AAP:

```
Application Restored

  New DB User:  v-root-ztaapp-s-xyz789abc
  Health:       HEALTHY
  URL:          http://app.zta.lab:8080

  Fresh credentials issued. The application is back online.
```

Verify:
```bash
curl -s http://app.zta.lab:8080/health
# Expected: healthy again
```

---

## Discussion Points

- How fast was the response from attack detection to credential revocation?
- What if the attacker already had valid credentials — does revoking help?
- Why stop the application instead of just revoking credentials?
- Could EDA trigger additional responses (block IP, isolate network segment)?
- What if Wazuh itself is compromised — how do you protect the SIEM?
- How would you add a human approval step for less severe alerts?
- What's the difference between EDA Controller (AAP) and standalone ansible-rulebook?

---

## Wazuh Rules Reference

| Rule ID | Description | Level |
|---------|-------------|-------|
| 5712 | SSHD brute force trying to get access to the system | 10 |
| 5763 | SSHD brute force (multiple failed logins from same source) | 10 |
| 5764 | SSHD multiple authentication failures | 10 |

The integration triggers on all three rules. Any of these will cause
credential revocation.

---

## Validation Checklist

- [ ] Application is healthy before the attack (Section 2 deployed)
- [ ] Wazuh agent is active on app.zta.lab
- [ ] EDA rulebook activation is running (port 5000 listening)
- [ ] Brute-force simulation generates 10 failed SSH attempts
- [ ] Wazuh fires rule 5712 (visible in dashboard)
- [ ] Wazuh integration sends webhook to EDA
- [ ] EDA triggers "Emergency: Revoke App Credentials" in AAP
- [ ] Vault DB lease is revoked (no `v-root-*` user in PostgreSQL)
- [ ] Application service is stopped
- [ ] `http://app.zta.lab:8080/health` returns unhealthy or connection refused
- [ ] Restore playbook brings the application back with fresh credentials
- [ ] Total time from attack to revocation is under 30 seconds
