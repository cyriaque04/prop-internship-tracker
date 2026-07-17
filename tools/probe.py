#!/usr/bin/env python3
"""Probe candidate ATS endpoints to discover which firms expose a public board.

Usage: python3 tools/probe.py candidates.json
Prints, for each candidate, whether it responded and how many jobs / internship
matches it has, so we can seed config/firms.json with only verified entries.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prop_tracker import ats, filters  # noqa: E402
from prop_tracker.http import HttpError  # noqa: E402


def main() -> int:
    path = sys.argv[1]
    with open(path, encoding="utf-8") as fh:
        candidates = json.load(fh)

    good = []
    for cfg in candidates:
        label = f"{cfg['name']} [{cfg['source']}]"
        try:
            jobs = ats.fetch_firm(cfg)
            matches = filters.filter_jobs(jobs)
            status = f"OK  {len(jobs):4d} jobs, {len(matches):2d} intern-match"
            good.append(cfg)
            print(f"{label:45s} {status}")
            for m in matches[:4]:
                print(f"        ↳ {m.title} | {m.location} ({'/'.join(m.categories)})")
        except HttpError as exc:
            print(f"{label:45s} -- {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"{label:45s} !! {type(exc).__name__}: {exc}")

    print(f"\n{len(good)}/{len(candidates)} candidates verified.")
    with open("tools/verified.json", "w", encoding="utf-8") as fh:
        json.dump(good, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
