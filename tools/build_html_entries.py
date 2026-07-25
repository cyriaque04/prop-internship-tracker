#!/usr/bin/env python3
"""Turn scouted careers pages (tools/html_entries.json) into firm configs,
auto-tagging assume_europe so unknown-location html jobs respect Europe-only.

assume_europe = European ccTLD in the URL, or a known European-HQ firm.
Edit any entry's assume_europe by hand later if a guess is wrong.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EU_TLDS = (".nl", ".co.uk", "//uk", ".uk/", ".de", ".fr", ".ie", ".ch", ".es",
           ".it", ".se", ".dk", ".no", ".fi", ".pl", ".eu", ".be", ".at",
           ".pt", ".cz", ".com.cy")

# European-HQ firms that use a generic (.com/.io) domain.
EUROPEAN_FIRMS = {
    "imc trading", "amplify trading", "g-research", "marshall wace",
    "squarepoint capital", "b2c2", "gsr", "wintermute", "woorton", "d2x",
    "otc flow", "deep blue capital", "ora traders", "keyquant", "all options",
    "webb traders", "northpool", "nino options", "323 trading", "priogen energy",
    # v2 additions (clearly European HQ)
    "optiver", "wincent", "abc arbitrage", "aarhus trading", "apolis sam",
    "arfima trading", "aureas finance", "danske commodities", "aros commodities",
    "incommodities", "incommodities asset management", "brevan howard",
    "capital fund management (cfm)", "cfm", "glencore", "vitol", "trafigura",
    "gunvor group", "invemo capital ag", "ethflow", "axinoss",
}

# Skip: duplicate of an already-tracked firm (same board), or not useful.
SKIP = {"allston trading"}


def is_europe(name: str, url: str) -> bool:
    if name.lower() in EUROPEAN_FIRMS:
        return True
    u = url.lower().rstrip("/") + "/"
    return any(t in u for t in EU_TLDS)


def main() -> int:
    with open(os.path.join(ROOT, "tools", "html_entries.json")) as fh:
        scouted = json.load(fh)

    out = []
    eu = 0
    for e in scouted:
        if e["name"].lower() in SKIP:
            continue
        europe = is_europe(e["name"], e["url"])
        eu += europe
        out.append({"name": e["name"], "source": "html", "url": e["url"],
                    "assume_europe": europe})

    with open(os.path.join(ROOT, "tools", "html_firms.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"{len(out)} html firms ({eu} tagged European) → tools/html_firms.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
