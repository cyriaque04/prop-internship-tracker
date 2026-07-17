#!/usr/bin/env python3
"""Entry point: check tracked prop firms for new summer internships.

Typical usage:
    python3 check.py                 # full run: fetch, alert on new, save state
    python3 check.py --dry-run       # fetch + report, but no WhatsApp / no state change
    python3 check.py --firm "Jane Street" --show-all   # debug one firm

Config lives in config/firms.json. WhatsApp creds come from the environment
(CALLMEBOT_PHONE / CALLMEBOT_APIKEY); see .env.example.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Allow running as a plain script (no install / no PYTHONPATH needed).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prop_tracker import ats, filters, notify, report, state  # noqa: E402
from prop_tracker.http import HttpError  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(ROOT, "config", "firms.json")
DEFAULT_FILTERS = os.path.join(ROOT, "config", "filters.json")
DEFAULT_STATE = os.path.join(ROOT, "state", "seen_jobs.json")
DEFAULT_REPORT = os.path.join(ROOT, "reports", "latest.md")


def load_env_file(path: str) -> None:
    """Minimal .env loader (KEY=VALUE lines). Real env vars take precedence."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def load_config(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    firms = data.get("firms", data if isinstance(data, list) else [])
    return [f for f in firms if not f.get("disabled")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--filters", default=DEFAULT_FILTERS)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--env", default=os.path.join(ROOT, ".env"))
    parser.add_argument("--dry-run", action="store_true",
                        help="No WhatsApp, no state write. Just fetch + report.")
    parser.add_argument("--seed", action="store_true",
                        help="Baseline mode: record all current matches as seen "
                             "WITHOUT sending WhatsApp. Run once before scheduling "
                             "so you only get alerted on future new postings.")
    parser.add_argument("--firm", action="append", default=None,
                        help="Only check firm(s) with this name (repeatable).")
    parser.add_argument("--show-all", action="store_true",
                        help="Print every fetched job (debug), not just matches.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    load_env_file(args.env)

    def log(*a):
        if not args.quiet:
            print(*a, file=sys.stderr)

    firms = load_config(args.config)
    if args.firm:
        wanted = {f.lower() for f in args.firm}
        firms = [f for f in firms if f["name"].lower() in wanted]
    if not firms:
        log("No firms to check (check --config / --firm).")
        return 1

    filt_cfg = None
    if os.path.exists(args.filters):
        with open(args.filters, encoding="utf-8") as fh:
            filt_cfg = json.load(fh)
    filt = filters.Filters.from_config(filt_cfg)
    loc = "any" if not filt.location_keywords else f"{len(filt.location_keywords)} region kw"
    log(f"Filters: categories={filt.categories}, summer_only={filt.require_summer}, "
        f"min_year={filt.min_year}, location={loc}")

    st = state.load(args.state)

    all_matches: list[ats.Job] = []
    new_matches: list[ats.Job] = []
    errors: list[tuple[str, str]] = []
    total_fetched = 0

    for cfg in firms:
        name = cfg["name"]
        try:
            jobs = ats.fetch_firm(cfg)
            total_fetched += len(jobs)
            if args.show_all:
                for j in jobs:
                    print(f"    [{j.source}] {j.title} | {j.location} | {j.url}")
            matches = filters.filter_jobs(jobs, filt)
            all_matches.extend(matches)
            fresh = [j for j in matches if not state.is_seen(st, j.uid)]
            new_matches.extend(fresh)
            log(f"  {name:28s} {len(jobs):4d} jobs → {len(matches):2d} match, "
                f"{len(fresh):2d} new")
        except (HttpError, ValueError, KeyError) as exc:
            errors.append((name, str(exc)))
            log(f"  {name:28s} ERROR: {exc}")
        time.sleep(0.3)  # be polite to the endpoints

    log(f"\nFetched {total_fetched} jobs across {len(firms)} firms.")
    log(f"{len(all_matches)} matching open role(s), {len(new_matches)} NEW.")

    # Report reflects everything currently open, regardless of dry-run.
    report.write_report(args.report, all_matches, errors)
    log(f"Report written to {args.report}")

    if new_matches:
        for j in new_matches:
            print(f"NEW: {j.firm} — {j.title} ({'/'.join(j.categories)}) {j.url}")

    if args.dry_run:
        log("Dry run: no WhatsApp sent, state not updated.")
        return 0

    if args.seed:
        for j in all_matches:
            state.mark_seen(st, j.uid,
                            {"firm": j.firm, "title": j.title, "url": j.url})
        state.save(args.state, st)
        log(f"Seeded baseline: {len(all_matches)} current match(es) marked seen "
            f"(no WhatsApp sent). State saved to {args.state}.")
        return 0

    # Only roles we actually delivered get marked seen, so a failed/skipped
    # alert is retried on the next run instead of being silently swallowed.
    delivered: list[ats.Job] = []
    if new_matches:
        if notify.whatsapp_configured():
            delivered = notify.notify_new(new_matches)
            if len(delivered) == len(new_matches):
                log(f"WhatsApp: sent {len(delivered)} new role(s).")
            else:
                log(f"WhatsApp: sent {len(delivered)}/{len(new_matches)}; "
                    f"{len(new_matches) - len(delivered)} will be retried next run.")
        else:
            log("WhatsApp not configured (set CALLMEBOT_PHONE/CALLMEBOT_APIKEY); "
                "not sending and not marking seen (use --seed to baseline).")

    for j in delivered:
        state.mark_seen(st, j.uid, {"firm": j.firm, "title": j.title, "url": j.url})
    state.save(args.state, st)
    log(f"State saved to {args.state} ({len(delivered)} newly marked seen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
