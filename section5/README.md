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
curl -s http://app.zta.lab:8081/health

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
2. Each attempt uses the `rhel` user with an incorrect password
3. The failed logins are recorded in `/var/log/secure` on the app server
4. The Wazuh agent detects the pattern and sends it to the Wazuh manager
5. Wazuh fires **rule 5712** (SSH brute force detected)

---

## Exercise 5.5 — Watch the Automated Response

After the brute-force simulation completes, observe the chain reaction:

### Check Wazuh Dashboard

Open `http://wazuh.zta.lab:5601` (resolves to central — Wazuh runs as a container) and look for:
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
curl -s http://app.zta.lab:8081/health
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
  URL:          http://app.zta.lab:8081

  Fresh credentials issued. The application is back online.
```

Verify:
```bash
curl -s http://app.zta.lab:8081/health
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
- [ ] `http://app.zta.lab:8081/health` returns unhealthy or connection refused
- [ ] Restore playbook brings the application back with fresh credentials
- [ ] Total time from attack to revocation is under 30 seconds

---

# Exercise 5.7 — Wazuh Alert Tuning & Custom Rule Writing (Hands-On)

## The Scenario

After the incident response demo, look at the Wazuh dashboard. You'll notice
that Wazuh is also alerting on **legitimate AAP SSH connections**. Every time
AAP runs a job template, it generates SSH authentication events that can
trigger false positive alerts. In a production environment, this alert noise
would drown out real threats.

You must write a **custom Wazuh rule** to suppress false positives from the
AAP controller while keeping alerts active for genuinely suspicious traffic.

## Duration: ~25 minutes

---

## Step 1 — Identify the False Positives

Open the Wazuh Dashboard at `http://wazuh.zta.lab:5601`.

Navigate to **Security events** and filter for SSH-related alerts. You'll
see a mix of:
- **Legitimate:** AAP controller (192.168.1.10) connecting to managed hosts
- **Malicious:** The brute-force simulation from the previous exercise

Both are generating alerts. In a production environment with hundreds of
AAP jobs per day, the real attacks would be buried.

---

## Step 2 — Examine the Existing Rules

SSH to the Wazuh manager and look at the brute-force rule:

```bash
ssh rhel@central.zta.lab
sudo podman exec -it wazuh-manager bash

# Find the brute-force rule definition
grep -A 10 'id="5712"' /var/ossec/ruleset/rules/0095-sshd_rules.xml
```

You'll see:
```xml
<rule id="5712" level="10" frequency="8" timeframe="120" ignore="60">
  <if_matched_sid>5710</if_matched_sid>
  <description>SSHD brute force trying to get access to the system.</description>
  ...
</rule>
```

This rule fires when there are 8+ failed SSH attempts within 120 seconds.
It doesn't distinguish between AAP automation and an actual attacker.

---

## Step 3 — Write a Custom Exclusion Rule

Create a custom rule that suppresses brute-force alerts when the source IP
is the AAP controller:

```bash
# Still inside the wazuh-manager container:
cat >> /var/ossec/etc/rules/local_rules.xml << 'RULES'

<!-- ZTA Workshop: Suppress false positives from AAP controller -->
<group name="local,sshd,zta_tuning">

  <!-- AAP controller SSH activity — informational only (suppress alert) -->
  <rule id="100030" level="0">
    <if_sid>5712</if_sid>
    <srcip>192.168.1.10</srcip>
    <description>Suppressed: SSH brute-force alert from AAP controller (expected automation traffic)</description>
  </rule>

  <!-- Same for the 5763/5764 variants -->
  <rule id="100031" level="0">
    <if_sid>5763</if_sid>
    <srcip>192.168.1.10</srcip>
    <description>Suppressed: SSH auth failures from AAP controller (expected)</description>
  </rule>

  <rule id="100032" level="0">
    <if_sid>5764</if_sid>
    <srcip>192.168.1.10</srcip>
    <description>Suppressed: SSH multiple auth failures from AAP controller (expected)</description>
  </rule>

</group>
RULES
```

**Key points about this rule:**
- `level="0"` means the alert is suppressed (not logged as an alert)
- `<if_sid>5712</if_sid>` means this rule only triggers when rule 5712 fires
- `<srcip>192.168.1.10</srcip>` scopes it to the AAP controller IP only
- Alerts from ANY OTHER source IP still fire at level 10

---

## Step 4 — Validate and Reload

```bash
# Test the rule syntax (inside the container)
/var/ossec/bin/wazuh-analysisd -t
# Expected: No errors

# Restart the Wazuh manager to load new rules
exit   # Exit the container shell
sudo podman restart wazuh-manager
```

Wait 30 seconds for Wazuh to reload.

---

## Step 5 — Verify the Tuning

**Test 1 — Simulate brute force from AAP (should NOT alert):**

Run the brute-force simulation playbook from AAP. Check the Wazuh dashboard
— rule 5712 should NOT fire for source IP 192.168.1.10.

**Test 2 — Simulate brute force from a different source (should alert):**

From a different host (e.g., central), manually trigger failed SSH attempts:

```bash
ssh rhel@central.zta.lab
for i in $(seq 1 10); do
  sshpass -p 'wrongpassword' ssh -o StrictHostKeyChecking=no rhel@app.zta.lab 2>/dev/null
done
```

Check the Wazuh dashboard — rule 5712 SHOULD fire for central's IP
(192.168.1.11), since the exclusion only applies to the AAP controller.

---

## Step 6 — Advanced: Write a Detection Rule

Instead of just suppressing, write a rule that **detects when someone tries
to impersonate AAP** by SSH-ing from a non-AAP source to many hosts rapidly:

```bash
sudo podman exec -it wazuh-manager bash
cat >> /var/ossec/etc/rules/local_rules.xml << 'RULES'

<!-- Detect potential AAP impersonation — rapid SSH from non-AAP source -->
<rule id="100035" level="12" frequency="5" timeframe="60">
  <if_matched_sid>5715</if_matched_sid>
  <srcip>!192.168.1.10</srcip>
  <srcip>!192.168.1.11</srcip>
  <description>ZTA: Rapid SSH logins from non-automation source $(srcip) — possible AAP impersonation</description>
  <group>authentication_success,zta_suspicious</group>
</rule>

RULES
```

Reload Wazuh and test.

---

## Wazuh Tuning Discussion Points

- How do you balance alert sensitivity vs. false positive volume?
- What if the AAP controller IP changes — how do you keep the rule updated?
- Could you use a Wazuh CDB list instead of hardcoded IPs?
- Should suppressed events still be logged (just not alerted)?
- How would you test rule changes in a staging environment?

## Wazuh Tuning Validation Checklist

- [ ] Existing rules examined (`grep 5712` shows rule definition)
- [ ] Custom exclusion rule written with `level="0"` for AAP source IP
- [ ] `wazuh-analysisd -t` passes syntax check
- [ ] Wazuh manager restarted and rules loaded
- [ ] Brute force from AAP IP does NOT generate level-10 alert
- [ ] Brute force from other IPs STILL generates level-10 alert
- [ ] (Bonus) Impersonation detection rule written and tested
