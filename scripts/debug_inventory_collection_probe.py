#!/usr/bin/env python3
"""Debug probe: log whether netbox.netbox is visible to ansible-galaxy (local or EE-like PATH)."""
# #region agent log
import json
import os
import subprocess
import time

LOG = "/home/nmartins/Development/.cursor/debug-aa82e8.log"
SESSION = "aa82e8"


def _log(hypothesis_id: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": SESSION,
        "runId": os.environ.get("DEBUG_RUN_ID", "probe"),
        "hypothesisId": hypothesis_id,
        "location": "scripts/debug_inventory_collection_probe.py",
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


# #endregion

def main() -> None:
    # #region agent log
    r = subprocess.run(
        ["ansible-galaxy", "collection", "list"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (r.stdout or "") + (r.stderr or "")
    _log(
        "H1",
        "ansible-galaxy collection list",
        {
            "exit_code": r.returncode,
            "netbox_netbox_present": "netbox.netbox" in out,
            "output_head": out[:2500],
        },
    )
    _log(
        "H4",
        "requirements file presence",
        {
            "repo_root": os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..")
            ),
            "requirements_exists": os.path.isfile(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "collections",
                    "requirements.yml",
                )
            ),
        },
    )
    # #endregion
    print(f"Debug probe appended to {LOG}")


if __name__ == "__main__":
    main()
