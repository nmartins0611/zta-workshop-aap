# Section 5 — Automated Incident Response: Brute Force → Splunk → EDA → Vault Revocation

> **2-Hour Workshop Delivery Guide**
>
> | Exercise | Status | Est. Time |
> |----------|--------|-----------|
> | 5.1 — Create the AAP Job Templates | **Core** | 3 min |
> | 5.2 — Configure Splunk Saved Search & Alert | **Core** | 5 min |
> | 5.3 — Configure EDA Rulebook | **Core** | 3 min |
> | 5.4 — Verify the Application Is Healthy | **Core** | 2 min |
> | 5.5 — Launch the Brute-Force Attack | **Core** | 3 min |
> | 5.6 — Watch the Automated Response | **Core** | 5 min |
> | 5.7 — Restore the Application | **Core** | 3 min |
> | 5.8 — Splunk Alert Tuning | **Extended** | 10 min |
>
> For a **2-hour workshop**, complete exercises **5.1–5.7** (~25 min).
> Exercise 5.8 (alert tuning) is a bonus exercise if time permits.

## Objective

Demonstrate automated incident response in a Zero Trust architecture. A
brute-force SSH attack is simulated against the app server. **Splunk**
detects the attack via a saved search alert and sends a webhook to
**Event-Driven Ansible** (EDA). EDA automatically triggers an AAP job
template that **revokes the application's database credentials in Vault**
— cutting off data access in seconds, with no human intervention.

## Zero Trust Principles

| Principle | How This Section Demonstrates It |
|-----------|----------------------------------|
| **Assume breach** | Automated response doesn't wait for a human to investigate |
| **Continuous monitoring** | Splunk watches every authentication event forwarded from hosts |
| **Automatic remediation** | EDA triggers credential revocation without manual approval |
| **Blast radius containment** | Revoking credentials limits what an attacker can access |
| **Just-in-time recovery** | Fresh credentials are only re-issued after investigation |

## Architecture

```
  ┌────────────┐     ┌──────────────┐     ┌────────────┐     ┌────────────┐
  │  Attacker  │     │  App Server  │     │   Splunk   │     │    EDA     │
  │            │     │  app.zta.lab │     │  central   │     │ Controller │
  │            │     │              │     │  :8000     │     │            │
  │  SSH brute │────▶│ /var/log/    │────▶│  Saved     │────▶│  Rulebook  │
  │  force     │     │   secure     │     │  search    │     │  matches   │
  │  attempt   │     │              │     │  alert     │     │  event     │
  └────────────┘     └──────────────┘     └─────┬──────┘     └─────┬──────┘
                                                │                   │
                                          Splunk UF             Webhook POST
                                          forwards logs         to EDA
                                          to indexer
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
| T+10s | Splunk Universal Forwarder sends auth logs to indexer |
| T+15s | Splunk saved search fires — detects 5+ failed logins in 60 seconds |
| T+16s | Splunk webhook alert action POSTs to EDA endpoint |
| T+17s | EDA rulebook matches the event, triggers AAP job |
| T+23s | AAP runs revocation playbook — Vault lease revoked |
| T+28s | Application stopped, database credentials gone |
| T+28s | **Attack surface eliminated in ~28 seconds** |

---

## Pre-requisites

Before running this section:

1. **Section 2 must be complete** — the application must be deployed with
   active Vault database credentials
2. **Splunk** must be running on central (`http://central.zta.lab:8000`)
3. **Splunk log shipping** must be configured — `/var/log/secure` from app/db
   containers is forwarded to Splunk (`setup/integrate-splunk.yml`)
4. **EDA Controller** must be running (or standalone `ansible-rulebook`)

---

## Exercise 5.1 — Create the AAP Job Templates

| Template Name | Playbook | Inventory | Credentials |
|---------------|----------|-----------|-------------|
| Emergency: Revoke App Credentials | `section5/playbooks/revoke-app-credentials.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Simulate Brute Force | `section5/playbooks/simulate-bruteforce.yml` | ZTA Lab Inventory | ZTA Machine Credential |
| Restore App Credentials | `section5/playbooks/restore-app-credentials.yml` | ZTA Lab Inventory | ZTA Machine Credential |

---

## Exercise 5.2 — Configure the Splunk Saved Search & Alert

### Step 1 — Verify logs are arriving in Splunk

Open `http://central.zta.lab:8000` and run this search:

```
index=main sourcetype=linux_secure "Failed password"
```

You should see failed SSH login events. If not, verify `integrate-splunk.yml`
has been run and the Universal Forwarder is sending logs.

### Step 2 — Create the Saved Search

1. Navigate to **Settings → Searches, reports, and alerts → New Alert**
2. Configure:

| Field | Value |
|-------|-------|
| Title | `ZTA: SSH Brute Force Detected` |
| Search | `index=main sourcetype=linux_secure "Failed password" \| stats count by src_ip, host \| where count >= 5` |
| Time Range | Real-time, 60-second window |
| Alert type | Real-time |
| Trigger condition | Number of results > 0 |

3. Under **Trigger Actions**, click **Add Actions → Webhook**:

| Field | Value |
|-------|-------|
| URL | `http://control.zta.lab:5000/endpoint` |

4. Click **Save**

> **ZTA Concept**: Splunk acts as the detection layer. It watches authentication
> logs from all hosts and fires an alert when a brute-force pattern is detected.
> The webhook bridges SIEM to automation — no human in the loop.

### Alternative — Create via Splunk REST API

If you prefer automation over UI clicks:

```bash
curl -k -u admin:splunkpassword \
  http://central.zta.lab:8000/servicesNS/admin/search/saved/searches \
  -d name="ZTA: SSH Brute Force Detected" \
  -d search='index=main sourcetype=linux_secure "Failed password" | stats count by src_ip, host | where count >= 5' \
  -d alert_type=always \
  -d alert.severity=4 \
  -d alert.suppress=0 \
  -d dispatch.earliest_time=rt-60s \
  -d dispatch.latest_time=rt \
  -d is_scheduled=1 \
  -d cron_schedule="*/1 * * * *" \
  -d actions=webhook \
  -d 'action.webhook.param.url=http://control.zta.lab:5000/endpoint'
```

---

## Exercise 5.3 — Configure EDA Rulebook

### Option A — EDA Controller (AAP 2.5+)

1. Navigate to **EDA Controller → Rulebooks**
2. Import `section5/eda/splunk-credential-revoke.yml`
3. Create a **Rulebook Activation**:
   - Name: `Splunk Brute Force Response`
   - Rulebook: `splunk-credential-revoke`
   - Decision Environment: your EDA decision environment
   - Restart policy: `On failure`
4. Enable the activation — it starts listening on port 5000

### Option B — Standalone ansible-rulebook

```bash
ssh rhel@control.zta.lab
ansible-rulebook --rulebook /tmp/zta-workshop-aap/section5/eda/splunk-credential-revoke.yml \
  -i /tmp/zta-workshop-aap/inventory/hosts.ini \
  --verbose
```

---

## Exercise 5.4 — Verify the Application Is Healthy

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

## Exercise 5.5 — Launch the Brute-Force Attack

Launch **Simulate Brute Force** from AAP (or run the playbook directly):

```bash
ansible-playbook section5/playbooks/simulate-bruteforce.yml
```

**What happens:**

1. The playbook sends 10 rapid failed SSH login attempts to `app.zta.lab`
2. Each attempt uses the `rhel` user with an incorrect password
3. The failed logins are recorded in `/var/log/secure` on the app server
4. Splunk Universal Forwarder ships the logs to the Splunk indexer
5. Splunk saved search detects 5+ failures and fires the webhook alert

---

## Exercise 5.6 — Watch the Automated Response

After the brute-force simulation completes, observe the chain reaction:

### Check Splunk Dashboard

Open `http://central.zta.lab:8000` and run:

```
index=main sourcetype=linux_secure "Failed password" | stats count by src_ip, host | where count >= 5
```

You should see the brute-force source IP with a high failure count.

Check **Activity → Triggered Alerts** — the `ZTA: SSH Brute Force Detected`
alert should show as recently fired.

### Check EDA Controller

In the EDA Controller UI (or ansible-rulebook terminal output):
- Event received from Splunk webhook
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

## Exercise 5.7 — Restore the Application

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

---

# Extended Exercises (Longer Formats Only)

## Exercise 5.8 — Splunk Alert Tuning (Hands-On)

### The Problem

After the incident response demo, check the Splunk triggered alerts. You'll
notice the saved search may also fire on **legitimate AAP SSH connections**.
Every time AAP runs a job template, it generates SSH authentication events
that could trigger the brute-force alert.

### Step 1 — Identify the AAP controller's IP

```bash
dig +short control.zta.lab
# 192.168.1.10
```

### Step 2 — Update the Saved Search to Exclude AAP

Edit the saved search in **Settings → Searches, reports, and alerts**:

Change the search to:

```
index=main sourcetype=linux_secure "Failed password" NOT src_ip=192.168.1.10
| stats count by src_ip, host
| where count >= 5
```

The `NOT src_ip=192.168.1.10` excludes the AAP controller from brute-force
detection. Failed logins from AAP are expected (e.g., credential rotation,
connectivity tests).

### Step 3 — Test the Tuning

**Test 1 — Brute force from AAP (should NOT alert):**

Run the brute-force simulation from AAP. Check Splunk triggered alerts —
the alert should NOT fire for source IP 192.168.1.10.

**Test 2 — Brute force from another source (should alert):**

From central, manually trigger failed SSH attempts:

```bash
ssh rhel@central.zta.lab
for i in $(seq 1 10); do
  sshpass -p 'wrongpassword' ssh -o StrictHostKeyChecking=no rhel@app.zta.lab 2>/dev/null
done
```

Check Splunk — the alert SHOULD fire for central's IP (192.168.1.11).

---

## Discussion Points

- How fast was the response from attack detection to credential revocation?
- What if the attacker already had valid credentials — does revoking help?
- Why stop the application instead of just revoking credentials?
- Could EDA trigger additional responses (block IP, isolate network segment)?
- What if Splunk itself is compromised — how do you protect the SIEM?
- How would you add a human approval step for less severe alerts?
- Compare the Splunk webhook approach to Wazuh's native integration — trade-offs?

---

## Splunk Search Reference

| Search | Purpose |
|--------|---------|
| `index=main sourcetype=linux_secure "Failed password"` | All failed SSH logins |
| `... \| stats count by src_ip` | Group by attacker source IP |
| `... \| where count >= 5` | Threshold for brute-force detection |
| `index=main sourcetype=linux_secure "Accepted password"` | Successful logins |
| `index=main sourcetype=linux_secure "Accepted publickey"` | Key-based logins |

---

## Validation Checklist

- [ ] Application is healthy before the attack (Section 2 deployed)
- [ ] Splunk is receiving `/var/log/secure` logs from app/db hosts
- [ ] Splunk saved search `ZTA: SSH Brute Force Detected` is created
- [ ] Webhook action points to `http://control.zta.lab:5000/endpoint`
- [ ] EDA rulebook activation is running (port 5000 listening)
- [ ] Brute-force simulation generates 10 failed SSH attempts
- [ ] Splunk alert fires (visible in Activity → Triggered Alerts)
- [ ] Splunk webhook POSTs to EDA
- [ ] EDA triggers "Emergency: Revoke App Credentials" in AAP
- [ ] Vault DB lease is revoked (no `v-root-*` user in PostgreSQL)
- [ ] Application service is stopped
- [ ] `http://app.zta.lab:8081/health` returns unhealthy or connection refused
- [ ] Restore playbook brings the application back with fresh credentials
- [ ] Total time from attack to revocation is under 30 seconds
- [ ] (Bonus) Saved search tuned to exclude AAP controller IP
