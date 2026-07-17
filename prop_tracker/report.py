"""Human-readable Markdown report of the current matching openings."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .ats import Job


def write_report(path: str, matches: list[Job], errors: list[tuple[str, str]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Prop-firm summer internships — quant / trading / structuring",
        "",
        f"_Last updated: {now}_",
        "",
        f"**{len(matches)} matching open role(s)** across tracked firms.",
        "",
    ]

    by_firm: dict[str, list[Job]] = {}
    for j in matches:
        by_firm.setdefault(j.firm, []).append(j)

    for firm in sorted(by_firm):
        lines.append(f"## {firm}")
        for j in sorted(by_firm[firm], key=lambda x: x.title):
            cats = ", ".join(j.categories)
            loc = f" — {j.location}" if j.location else ""
            lines.append(f"- [{j.title}]({j.url}){loc}  _({cats})_")
        lines.append("")

    if errors:
        lines.append("## ⚠️ Firms that could not be checked this run")
        for firm, msg in errors:
            lines.append(f"- **{firm}**: {msg}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
