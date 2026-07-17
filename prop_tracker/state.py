"""Persistent de-duplication state.

Stores the set of job uids we have already alerted on, so the same posting is
never sent twice across the 3x/day runs. The file is committed back to the repo
so state survives across fresh cloud runs.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

STATE_VERSION = 1


def load(path: str) -> dict:
    if not os.path.exists(path):
        return {"version": STATE_VERSION, "seen": {}, "last_run": None}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("seen", {})
    data.setdefault("version", STATE_VERSION)
    return data


def save(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def is_seen(state: dict, uid: str) -> bool:
    return uid in state["seen"]


def mark_seen(state: dict, uid: str, meta: dict | None = None) -> None:
    state["seen"][uid] = {
        "first_seen": datetime.now(timezone.utc).isoformat(),
        **(meta or {}),
    }
