"""services/agent/activity.py — structured activity log (logs/activity.jsonl).

Every tool execution, judge call, and dispatch is appended here so the
console's Logs viewer can show what the team actually did.
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict

MONOREPO_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = Path(
    os.environ.get("BUSINESS_ACTIVITY_LOG", MONOREPO_ROOT / "logs" / "activity.jsonl")
)

_lock = threading.Lock()


def log_event(kind: str, **fields: Any) -> None:
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, **fields}
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _lock, open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:  # noqa: BLE001 — logging must never break execution
        pass
