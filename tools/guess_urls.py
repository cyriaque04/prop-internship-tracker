#!/usr/bin/env python3
"""Guess and verify homepage URLs for firms that came without one.

For each firm we build candidate domains from the name and test which one
actually responds, so the discovery/scout pipeline has a URL to work with.
Writes tools/firm_urls_v2.json (resolved) and prints the misses.
"""
from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prop_tracker import http  # noqa: E402
from prop_tracker.http import HttpError  # noqa: E402

STOP = {"llc", "inc", "sa", "ag", "ltd", "plc", "lp", "llp", "co", "company",
        "capital", "management", "partners", "group", "trading", "research",
        "securities", "advisors", "asset", "investments", "investment",
        "technologies", "technology", "fund", "commodities", "international",
        "factory", "the", "and"}

TLDS = [".com", ".io", ".co", ".ai", ".net"]


def candidates(name: str):
    # strip parentheticals like "(BAM)"
    name = re.sub(r"\(.*?\)", "", name)
    words = re.findall(r"[a-z0-9]+", name.lower())
    core = [w for w in words if w not in STOP] or words
    stems = []
    stems.append("".join(words))
    stems.append("".join(core))
    stems.append("-".join(core))
    if len(core) >= 2:
        stems.append("".join(core[:2]))
    seen, out = set(), []
    for stem in stems:
        if not stem or stem in seen:
            continue
        seen.add(stem)
        for tld in TLDS:
            out.append(stem + tld)
    return out[:12]


def resolve(firm: dict):
    name = firm["name"]
    for dom in candidates(name):
        for pre in ("https://www.", "https://"):
            url = pre + dom
            try:
                http.get_text(url, timeout=8)
                return {"name": name, "url": url}
            except HttpError:
                continue
    return {"name": name, "url": None}


def main() -> int:
    with open(sys.argv[1], encoding="utf-8") as fh:
        firms = json.load(fh)
    # skip obvious near-duplicates of firms we already track
    skip = {"headlands technologies"}
    firms = [f for f in firms if f["name"].lower() not in skip]

    resolved, misses = [], []
    with ThreadPoolExecutor(max_workers=20) as pool:
        for r in pool.map(resolve, firms):
            if r["url"]:
                resolved.append(r)
            else:
                misses.append(r["name"])

    json.dump(resolved, open("tools/firm_urls_v2.json", "w"), indent=2, ensure_ascii=False)
    print(f"Resolved {len(resolved)}/{len(firms)} firm URLs → tools/firm_urls_v2.json")
    print(f"\nCould not resolve ({len(misses)}):")
    for m in misses:
        print("  -", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
