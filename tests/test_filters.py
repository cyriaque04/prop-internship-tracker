#!/usr/bin/env python3
"""Filter logic tests. Run: python3 tests/test_filters.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prop_tracker.ats import Job                 # noqa: E402
from prop_tracker.filters import Filters, match  # noqa: E402


def J(title, department="", location=""):
    return Job(firm="X", title=title, url="u", department=department, location=location)


# --- category / season logic (no location or year constraints) ----------------
CAT = Filters(min_year=None, location_keywords=[])

CAT_CASES = [
    ("Quantitative Trader Intern - Summer 2027", "", ["quant", "trading"]),
    ("Summer Intern 2027 - Quantitative Researcher (PhD)", "", ["quant"]),
    ("2027 Summer Internship - Trading (Equities)", "", ["trading"]),
    ("Structuring Summer Analyst", "", ["structuring"]),
    ("Quantitative Research Intern", "", ["quant"]),
    ("Trading Internship", "", ["trading"]),
    ("Quant Trading Intern", "Structured Products", ["quant", "trading", "structuring"]),
    ("Quantitative Research Intern - Winter 2027", "", None),
    ("Trading Intern (Fall)", "", None),
    ("Quant Intern - Spring Off-cycle", "", None),
    ("Summer/Fall Quant Intern", "", ["quant"]),
    ("Senior Quantitative Researcher", "", None),
    ("Head of Trading", "", None),
    ("Internal Audit Manager", "", None),
    ("International Equities Trader", "", None),
    ("Software Engineering Intern", "Infrastructure", None),
    ("HR Summer Intern", "People", None),
]

# --- Europe + 2027 defaults ---------------------------------------------------
EU = Filters()  # defaults: summer only, min_year 2027, Europe keywords

EU_CASES = [
    # (title, location, expected)
    ("Quantitative Trader Intern - Summer 2027", "London", ["quant", "trading"]),
    ("Quantitative Research Intern", "Dublin, Ireland", ["quant"]),
    ("Quant Intern", "Amsterdam; Paris", ["quant"]),
    # US / Asia locations dropped
    ("Quantitative Trader Intern - Summer 2027", "New York", None),
    ("Quantitative Research Intern", "Chicago; New York", None),
    ("Trading Intern", "Hong Kong", None),
    # multi-location with one European hub is kept
    ("Quantitative Researcher, Intern (Summer 2027)", "Chicago; London", ["quant"]),
    # stale year dropped even in Europe
    ("Quantitative Trader Intern - Summer 2026", "London", None),
    ("Quant Research Intern (to December 2026)", "London", None),
    # unknown location kept (keep_unknown_location=True)
    ("Quantitative Research Intern", "", ["quant"]),
]


def run(name, filt, cases, loc_arg=False):
    fails = 0
    for row in cases:
        if loc_arg:
            title, location, expected = row
            got = match(J(title, location=location), filt)
        else:
            title, dept, expected = row
            got = match(J(title, department=dept), filt)
        ok = (set(got) if got else None) == (set(expected) if expected else None)
        if not ok:
            fails += 1
            print(f"FAIL [{name}]: {title!r} → got {got}, expected {expected}")
    print(f"[{name}] {len(cases) - fails}/{len(cases)} passed.")
    return fails


def main() -> int:
    fails = run("category", CAT, CAT_CASES)
    fails += run("europe+year", EU, EU_CASES, loc_arg=True)
    print("ALL PASS" if not fails else f"{fails} FAILURES")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
