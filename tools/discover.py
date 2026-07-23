#!/usr/bin/env python3
"""Auto-detect which ATS a firm uses by scraping its careers page(s).

Input: JSON list of {"name": ..., "url": ...} (homepage or careers URL).
For each firm we fetch the URL (and a few common careers sub-paths) and search
the HTML for ATS signatures, printing a ready-to-paste firms.json entry.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prop_tracker import http  # noqa: E402
from prop_tracker.http import HttpError  # noqa: E402

PATTERNS = [
    # Explicit ?for= token first so embed URLs yield the real board id.
    # Handles .../embed/job_board?for=X and .../embed/job_board/js?for=X
    ("greenhouse", re.compile(r"greenhouse[^\"'\s]*?[?&]for=([a-z0-9_]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9_]+)", re.I)),
    # Generic board URL, but never capture the literal "embed" path segment.
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?!embed\b)([a-z0-9_]+)", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/([a-z0-9\-]+)", re.I)),
    ("lever", re.compile(r"api\.lever\.co/v0/postings/([a-z0-9\-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-z0-9\-]+)", re.I)),
    ("ashby", re.compile(r"ashbyhq\.com/job-board/([a-z0-9\-]+)", re.I)),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([A-Za-z0-9]+)", re.I)),
    ("smartrecruiters", re.compile(r"careers\.smartrecruiters\.com/([A-Za-z0-9]+)", re.I)),
    ("workday", re.compile(r"([a-z0-9\-]+)\.(wd\d+)\.myworkdayjobs\.com/([A-Za-z0-9_\-/]+)", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/([a-z0-9\-]+)", re.I)),
    ("recruitee", re.compile(r"([a-z0-9\-]+)\.recruitee\.com", re.I)),
    ("teamtailor", re.compile(r"([a-z0-9\-]+)\.teamtailor\.com", re.I)),
]

SUBPATHS = ["", "/careers", "/careers/", "/jobs", "/join", "/join-us",
            "/about/careers"]


def detect(text: str):
    hits = []
    for source, pat in PATTERNS:
        for m in pat.findall(text):
            hits.append((source, m))
    return hits


def build_entry(name, source, m):
    if source == "greenhouse":
        return {"name": name, "source": "greenhouse", "token": m}
    if source == "lever":
        return {"name": name, "source": "lever", "company": m}
    if source == "ashby":
        return {"name": name, "source": "ashby", "org": m}
    if source == "smartrecruiters":
        return {"name": name, "source": "smartrecruiters", "company": m}
    if source == "workday":
        tenant, dc, rest = m
        site = rest.strip("/").split("/")[-1]
        return {"name": name, "source": "workday",
                "host": f"{tenant}.{dc}.myworkdayjobs.com",
                "tenant": tenant, "site": site}
    if source == "workable":
        return {"name": name, "source": "workable", "account": m}
    if source == "recruitee":
        return {"name": name, "source": "recruitee", "company": m}
    return {"name": name, "source": source, "raw": m}


def detect_firm(firm: dict):
    name = firm["name"]
    base = firm["url"].rstrip("/")
    tried = SUBPATHS if firm.get("probe_subpaths", True) else [""]
    for sub in tried:
        url = base + sub if sub else base
        try:
            text = http.get_text(url, timeout=12)
        except HttpError:
            continue
        hits = detect(text)
        if hits:
            source, m = hits[0]
            return build_entry(name, source, m), url
    return None, None


def main() -> int:
    from concurrent.futures import ThreadPoolExecutor

    with open(sys.argv[1], encoding="utf-8") as fh:
        firms = json.load(fh)
    workers = int(os.environ.get("DISCOVER_WORKERS", "12"))

    found = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = pool.map(detect_firm, firms)
        for firm, (entry, url) in zip(firms, results):
            if entry:
                found.append(entry)
                src = entry["source"]
                tok = entry.get("token") or entry.get("company") or \
                    entry.get("org") or entry.get("tenant") or entry.get("raw")
                print(f"{firm['name']:30s} → {src}: {tok}   (via {url})")
            else:
                print(f"{firm['name']:30s} → (no ATS signature found)")

    with open("tools/discovered.json", "w", encoding="utf-8") as fh:
        json.dump(found, fh, indent=2)
    print(f"\nDetected {len(found)}/{len(firms)} firms. Wrote tools/discovered.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
