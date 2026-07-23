#!/usr/bin/env python3
"""Merge newly-verified firm configs into config/firms.json.

Reads the existing config plus a list of verified entries (from probe.py) and
writes a combined, de-duplicated, alphabetically-sorted config. For a firm that
already exists, the existing (curated) entry is kept; new firms are appended.

Usage: python3 tools/merge_firms.py tools/verified.json
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "firms.json")


def norm(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def main() -> int:
    with open(CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    existing = cfg.get("firms", [])

    with open(sys.argv[1], encoding="utf-8") as fh:
        verified = json.load(fh)

    by_name = {norm(f["name"]): f for f in existing}
    added = []
    for entry in verified:
        key = norm(entry["name"])
        if key not in by_name:
            # strip probe-only helper keys if any
            clean = {k: v for k, v in entry.items() if k not in ("raw",)}
            by_name[key] = clean
            added.append(entry["name"])

    merged = sorted(by_name.values(), key=lambda f: f["name"].lower())
    cfg["firms"] = merged
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"Merged: {len(existing)} existing + {len(added)} new = {len(merged)} firms.")
    if added:
        print("Added:", ", ".join(sorted(added)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
