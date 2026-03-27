"""
ZTA Workshop — Live Topology Dashboard
Serves a real-time status page for every component in the lab.
"""

import socket
import ssl
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request
from urllib.error import URLError

from flask import Flask, jsonify, render_template

app = Flask(__name__)

TIMEOUT = 4  # seconds for each probe

# ---------------------------------------------------------------------------
# Component definitions — mirrors the architecture diagram
# ---------------------------------------------------------------------------
COMPONENTS = [
    # ── Management Plane VMs ──────────────────────────────────────────────
    {
        "id": "aap",
        "name": "AAP Controller",
        "group": "mgmt",
        "ip": "192.168.1.10",
        "details": "EDA :5000",
        "checks": [
            {"type": "https", "url": "https://192.168.1.10", "label": "Web UI"},
        ],
    },
    {
        "id": "central",
        "name": "Central VM",
        "group": "mgmt",
        "ip": "192.168.1.11",
        "details": "IdM \u2022 OPA \u2022 SPIRE",
        "checks": [
            {"type": "tcp", "host": "192.168.1.11", "port": 22, "label": "SSH"},
        ],
    },
    {
        "id": "vault",
        "name": "Vault",
        "group": "mgmt",
        "ip": "192.168.1.12",
        "details": "Secrets :8200",
        "checks": [
            {"type": "http", "url": "http://192.168.1.12:8200/v1/sys/health", "label": "Vault API"},
        ],
    },
    {
        "id": "netbox",
        "name": "Netbox",
        "group": "mgmt",
        "ip": "192.168.1.15",
        "details": "CMDB :8880",
        "checks": [
            {"type": "http", "url": "http://192.168.1.15:8880", "label": "Web UI"},
        ],
    },
    # ── Services on Central ───────────────────────────────────────────────
    {
        "id": "idm",
        "name": "IdM (FreeIPA)",
        "group": "services",
        "details": "LDAP \u2022 DNS",
        "checks": [
            {"type": "https", "url": "https://192.168.1.11/ipa/ui/", "label": "Web UI"},
            {"type": "tcp", "host": "192.168.1.11", "port": 389, "label": "LDAP"},
        ],
    },
    {
        "id": "opa",
        "name": "OPA (PDP)",
        "group": "services",
        "details": "Policies :8181",
        "checks": [
            {"type": "http", "url": "http://192.168.1.11:8181/health", "label": "Health"},
        ],
    },
    {
        "id": "keycloak",
        "name": "Keycloak",
        "group": "services",
        "details": "SSO :8443",
        "checks": [
            {"type": "https", "url": "https://192.168.1.11:8543", "label": "Web UI"},
        ],
    },
    {
        "id": "wazuh",
        "name": "Wazuh",
        "group": "services",
        "details": "SIEM",
        "checks": [
            {"type": "https", "url": "https://192.168.1.11:5601", "label": "Dashboard"},
        ],
    },
    {
        "id": "splunk",
        "name": "Splunk",
        "group": "services",
        "details": "Log Analytics :8000",
        "checks": [
            {"type": "http", "url": "http://192.168.1.11:8000", "label": "Web UI"},
        ],
    },
    {
        "id": "gitea",
        "name": "Gitea",
        "group": "services",
        "details": "Git :3000",
        "checks": [
            {"type": "http", "url": "http://192.168.1.11:3000", "label": "Web UI"},
        ],
    },
    # ── Arista cEOS Switches ──────────────────────────────────────────────
    {
        "id": "ceos1",
        "name": "ceos1 (SPINE)",
        "group": "switches",
        "details": "10.10.0.1 \u2022 10.20.0.254",
        "checks": [
            {"type": "tcp", "host": "192.168.1.11", "port": 2001, "label": "SSH"},
            {"type": "http", "url": "http://192.168.1.11:6031", "label": "eAPI"},
        ],
    },
    {
        "id": "ceos2",
        "name": "ceos2 (LEAF)",
        "group": "switches",
        "details": "10.10.0.2 \u2022 10.30.0.1",
        "checks": [
            {"type": "tcp", "host": "192.168.1.11", "port": 2002, "label": "SSH"},
            {"type": "http", "url": "http://192.168.1.11:6032", "label": "eAPI"},
        ],
    },
    {
        "id": "ceos3",
        "name": "ceos3 (LEAF)",
        "group": "switches",
        "details": "10.20.0.1",
        "checks": [
            {"type": "tcp", "host": "192.168.1.11", "port": 2003, "label": "SSH"},
            {"type": "http", "url": "http://192.168.1.11:6033", "label": "eAPI"},
        ],
    },
    # ── Workload Containers ───────────────────────────────────────────────
    {
        "id": "db",
        "name": "DB Container",
        "group": "workloads",
        "details": "db.zta.lab \u2022 10.30.0.10:5432",
        "checks": [
            {"type": "tcp", "host": "192.168.1.11", "port": 5432, "label": "PostgreSQL"},
            {"type": "tcp", "host": "192.168.1.11", "port": 2022, "label": "SSH"},
        ],
    },
    {
        "id": "app",
        "name": "App Container",
        "group": "workloads",
        "details": "app.zta.lab \u2022 10.20.0.10:8081",
        "checks": [
            {"type": "http", "url": "http://192.168.1.11:8081/health", "label": "Health"},
            {"type": "tcp", "host": "192.168.1.11", "port": 2023, "label": "SSH"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Probe functions
# ---------------------------------------------------------------------------
def _check_tcp(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return True
    except (OSError, socket.timeout):
        return False


def _check_http(url: str) -> bool:
    ctx = ssl.create_unverified_context()
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            return r.status < 500
    except Exception:
        return False


def _run_check(check: dict) -> dict:
    ctype = check["type"]
    ok = False
    if ctype == "tcp":
        ok = _check_tcp(check["host"], check["port"])
    elif ctype in ("http", "https"):
        ok = _check_http(check["url"])
    return {"label": check["label"], "ok": ok}


# ---------------------------------------------------------------------------
# Cached status — refreshed in background thread
# ---------------------------------------------------------------------------
_status_cache: dict = {}
_cache_lock = threading.Lock()


def _refresh_status():
    """Run all health checks concurrently and update the cache."""
    results = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {}
        for comp in COMPONENTS:
            comp_futures = []
            for chk in comp["checks"]:
                f = pool.submit(_run_check, chk)
                futures[f] = (comp["id"], chk["label"])
                comp_futures.append(f)

        check_results: dict[str, list] = {}
        for f in as_completed(futures):
            comp_id, label = futures[f]
            if comp_id not in check_results:
                check_results[comp_id] = []
            check_results[comp_id].append(f.result())

    for comp in COMPONENTS:
        cid = comp["id"]
        checks = check_results.get(cid, [])
        all_ok = all(c["ok"] for c in checks) if checks else False
        any_ok = any(c["ok"] for c in checks) if checks else False

        if all_ok:
            status = "healthy"
        elif any_ok:
            status = "degraded"
        else:
            status = "down"

        results[cid] = {
            "id": cid,
            "name": comp["name"],
            "group": comp["group"],
            "details": comp.get("details", ""),
            "ip": comp.get("ip", ""),
            "status": status,
            "checks": checks,
        }

    with _cache_lock:
        _status_cache.update(results)
        _status_cache["_ts"] = time.time()


def _background_poller():
    while True:
        try:
            _refresh_status()
        except Exception:
            pass
        time.sleep(10)


# Start background thread on import
_poller = threading.Thread(target=_background_poller, daemon=True)
_poller.start()
# Also run one synchronous pass so the first request has data
_refresh_status()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    with _cache_lock:
        return jsonify(_status_cache)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
