#!/usr/bin/env python3
"""
Diagnose NetBox dynamic inventory (same env vars AAP injects: NETBOX_API, NETBOX_TOKEN).
Run from repo root after: export NETBOX_API=... NETBOX_TOKEN=...
"""
# #region agent log
import json
import os
import re
import subprocess
import sys
import time
from typing import Optional
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

LOG = "/home/nmartins/Development/.cursor/debug-2d3c8d.log"
SESSION = "2d3c8d"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _log(hypothesis_id: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": SESSION,
        "runId": os.environ.get("DEBUG_RUN_ID", "pre-fix"),
        "hypothesisId": hypothesis_id,
        "location": "scripts/diagnose_netbox_inventory_sync.py",
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


# #endregion


def _group_vars_netbox_url() -> Optional[str]:
    p = REPO_ROOT / "inventory" / "group_vars" / "all.yml"
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'netbox_url:\s*["\']?([^"\'\n]+)', text)
    return m.group(1).strip() if m else None


def _netbox_status_check(api_base: str, token: str) -> dict:
    url = api_base.rstrip("/") + "/api/status/"
    req = urllib.request.Request(url, method="GET")
    if token:
        req.add_header("Authorization", f"Token {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(500)
            return {
                "http_status": resp.status,
                "ok": resp.status == 200,
                "body_head": body.decode("utf-8", errors="replace")[:200],
            }
    except urllib.error.HTTPError as e:
        return {
            "http_status": e.code,
            "ok": False,
            "error": "HTTPError",
            "body_head": (e.read(300) or b"").decode("utf-8", errors="replace"),
        }
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "error_msg": str(e)[:300]}


def main() -> int:
    # #region agent log
    api = os.environ.get("NETBOX_API", "").strip()
    token_set = bool(os.environ.get("NETBOX_TOKEN", "").strip())
    parsed = urlparse(api) if api else None
    port = parsed.port if parsed and parsed.port else (80 if parsed and parsed.scheme == "http" else 443 if parsed and parsed.scheme == "https" else None)

    _log(
        "H1",
        "credential env presence (AAP injector)",
        {
            "NETBOX_API_set": bool(api),
            "NETBOX_TOKEN_set": token_set,
            "api_host": parsed.hostname if parsed else None,
            "api_port": port,
            "api_scheme": parsed.scheme if parsed else None,
        },
    )

    gv_url = _group_vars_netbox_url()
    _log(
        "H4",
        "group_vars netbox_url vs NETBOX_API port",
        {
            "group_vars_netbox_url": gv_url,
            "env_uses_port_8000": ":8000" in api if api else False,
            "env_uses_port_8880": ":8880" in api if api else False,
            "gv_uses_8000": ":8000" in (gv_url or ""),
            "gv_uses_8880": ":8880" in (gv_url or ""),
        },
    )

    r = subprocess.run(
        ["ansible-galaxy", "collection", "list"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    gal = (r.stdout or "") + (r.stderr or "")
    _log(
        "H5",
        "local ansible-galaxy netbox.netbox",
        {
            "exit_code": r.returncode,
            "netbox_netbox_present": "netbox.netbox" in gal,
        },
    )

    if not api or not token_set:
        _log("H2", "skip NetBox HTTP (missing api or token)", {})
        _log("H3", "skip ansible-inventory (missing api or token)", {})
        print(f"Set NETBOX_API and NETBOX_TOKEN, then re-run. Logs: {LOG}")
        return 2

    status = _netbox_status_check(api, os.environ.get("NETBOX_TOKEN", "").strip())
    _log("H2", "NetBox GET /api/status/", status)

    inv_dir = REPO_ROOT / "inventory"
    cfg = inv_dir / "ansible.cfg"
    env = os.environ.copy()
    env.setdefault("ANSIBLE_CONFIG", str(cfg))
    proc = subprocess.run(
        [
            "ansible-inventory",
            "-i",
            str(inv_dir / "netbox_inventory.yml"),
            "--list",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(inv_dir),
        env=env,
    )
    err = (proc.stderr or "")[:1200]
    _log(
        "H3",
        "ansible-inventory --list",
        {
            "exit_code": proc.returncode,
            "stderr_head": err,
            "stdout_bytes": len(proc.stdout or ""),
        },
    )
    # #endregion

    print(f"Diagnostics appended to {LOG}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
