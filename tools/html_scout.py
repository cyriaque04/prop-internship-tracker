#!/usr/bin/env python3
"""Scout the no-API firms: find a reachable careers page and see what the HTML
fallback would extract. Helps decide signal vs noise before wiring them in.

Usage: python3 tools/html_scout.py tools/firm_urls_all.json
Writes tools/html_entries.json (firms with a reachable careers page).
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prop_tracker import ats, filters, http  # noqa: E402
from prop_tracker.http import HttpError       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBPATHS = ["/careers", "/careers/", "/career", "/jobs", "/join", "/join-us",
            "/about/careers", "/company/careers", "/vacancies", ""]
CAREER_HINT = ("career", "job", "vacan", "join", "intern", "position", "opening")

# No location constraint here — we want to see every internship+category hit,
# then judge. Year + summer + category still apply.
SCOUT_FILTER = filters.Filters(location_keywords=[], min_year=2027)


def scout(firm):
    name, base = firm["name"], firm["url"].rstrip("/")
    for sub in SUBPATHS:
        url = base + sub if sub else base
        try:
            page = http.get_text(url, timeout=12)
        except HttpError:
            continue
        low = page.lower()
        if not any(h in low for h in CAREER_HINT):
            continue
        jobs = ats.fetch_html(name, {"url": url})
        matches = filters.filter_jobs(jobs, SCOUT_FILTER)
        return {"name": name, "url": url, "anchors": len(jobs),
                "matches": [m.title for m in matches]}
    return {"name": name, "url": None, "anchors": 0, "matches": []}


def main() -> int:
    with open(sys.argv[1], encoding="utf-8") as fh:
        firms = json.load(fh)
    with open(os.path.join(ROOT, "config", "firms.json"), encoding="utf-8") as fh:
        have = {f["name"].lower() for f in json.load(fh)["firms"]}

    todo = [f for f in firms if f["name"].lower() not in have]
    print(f"Scouting {len(todo)} firms without an API...\n")

    entries = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        for r in pool.map(scout, todo):
            if r["url"]:
                tag = f"{r['anchors']} links"
                if r["matches"]:
                    tag += f" | MATCHES: {r['matches'][:3]}"
                print(f"{r['name']:28s} OK  {tag}")
                entries.append({"name": r["name"], "source": "html", "url": r["url"]})
            else:
                print(f"{r['name']:28s} -- no reachable careers page")

    with open(os.path.join(ROOT, "tools", "html_entries.json"), "w") as fh:
        json.dump(entries, fh, indent=2)
    n_match = sum(1 for r in entries if False)  # placeholder
    print(f"\n{len(entries)} firms have a reachable careers page → tools/html_entries.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
