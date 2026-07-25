"""Decide whether a job is a wanted internship.

A role qualifies when it is:
  1. an internship,
  2. in a target category (quant | trading | structuring),
  3. summer / undated (not another explicit season),
  4. for a wanted year (>= min_year, or undated),
  5. in a wanted location (region keywords, or unknown location).

All of this is tunable via config/filters.json (see Filters.from_config).
Matching is deliberately a little permissive: better to over-notify than miss.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ats import Job

# --- "is this an internship?" -------------------------------------------------
_INTERNSHIP_PATTERNS = [
    r"\bintern\b", r"\binterns\b", r"\binternship\b", r"\binternships\b",
    r"\bco-?op\b", r"\bsummer analyst\b",
    r"\bsummer\s+(?:20\d\d\s+)?(?:intern|internship|analyst|trader|program)",
    r"\bindustrial placement\b", r"\bplacement student\b",
]
_INTERNSHIP_RE = re.compile("|".join(_INTERNSHIP_PATTERNS), re.IGNORECASE)

# Explicit non-summer seasons; dropped unless the role also says "summer".
_NON_SUMMER_RE = re.compile(r"\b(winter|fall|autumn|spring|off[-\s]?cycle)\b",
                            re.IGNORECASE)
_SUMMER_RE = re.compile(r"\bsummer\b", re.IGNORECASE)

_YEAR_RE = re.compile(r"\b(20\d\d)\b")

# --- category keywords --------------------------------------------------------
_CATEGORY_PATTERNS = {
    "quant": re.compile(r"\bquant(?:itative|s)?\b", re.IGNORECASE),
    "trading": re.compile(r"\btrad(?:e|er|ers|ing)\b", re.IGNORECASE),
    "structuring": re.compile(
        r"\bstructur(?:e|er|ers|ing)\b|\bstructured products\b", re.IGNORECASE),
}

# --- default European location keywords --------------------------------------
EUROPE_KEYWORDS = [
    # explicitly requested
    "london", "dublin", "amsterdam", "paris",
    # other common prop-firm European hubs (cities)
    "zug", "zurich", "geneva", "frankfurt", "berlin", "munich", "milan",
    "madrid", "barcelona", "lisbon", "porto", "stockholm", "copenhagen",
    "oslo", "helsinki", "warsaw", "prague", "vienna", "brussels",
    "luxembourg", "gibraltar", "malta", "monaco", "rotterdam", "the hague",
    "manchester", "edinburgh", "cambridge", "oxford", "cluj", "sofia",
    "bratislava", "budapest", "athens", "bucharest", "tallinn", "riga",
    "vilnius", "ljubljana", "zagreb", "valletta", "nicosia", "reykjavik",
    "the hague", "eindhoven", "utrecht", "hamburg", "dusseldorf", "cork",
    # countries / regions
    "united kingdom", "uk", "england", "scotland", "ireland", "netherlands",
    "france", "germany", "switzerland", "italy", "spain", "portugal",
    "sweden", "denmark", "norway", "finland", "poland", "czech", "slovakia",
    "hungary", "greece", "austria", "belgium", "romania", "bulgaria",
    "croatia", "slovenia", "estonia", "latvia", "lithuania", "cyprus",
    "europe", "emea", "european",
]

# Explicit non-European locations. If a role names one of these and no European
# location, it's dropped — even for html firms tagged assume_europe (their global
# firm may post roles worldwide). Keeps the Europe-only requirement honest.
NON_EUROPE_KEYWORDS = [
    "singapore", "hong kong", "new york", "chicago", "san francisco",
    "sydney", "melbourne", "shanghai", "beijing", "shenzhen", "hangzhou",
    "tokyo", "osaka", "mumbai", "bangalore", "bengaluru", "gurgaon", "gurugram",
    "delhi", "hyderabad", "dubai", "abu dhabi", "toronto", "montreal",
    "houston", "austin", "boston", "los angeles", "seattle", "miami",
    "washington", "dallas", "atlanta", "seoul", "taipei", "jakarta",
    "kuala lumpur", "sao paulo", "tel aviv", "ho chi minh", "hanoi",
    "manila", "bangkok", "shenshen", "united states", "u.s.", "usa",
    "australia", "singpore", "india", "china", "japan", "brazil", "canada",
]


@dataclass
class Filters:
    categories: list[str] = field(
        default_factory=lambda: list(_CATEGORY_PATTERNS.keys()))
    require_summer: bool = True
    min_year: int | None = 2027
    location_keywords: list[str] = field(
        default_factory=lambda: list(EUROPE_KEYWORDS))
    block_keywords: list[str] = field(
        default_factory=lambda: list(NON_EUROPE_KEYWORDS))
    # keep roles whose location string is empty/unknown (rare) instead of dropping
    keep_unknown_location: bool = True

    @classmethod
    def from_config(cls, cfg: dict | None) -> "Filters":
        f = cls()
        if not cfg:
            return f
        if "categories" in cfg:
            f.categories = [c.lower() for c in cfg["categories"]]
        if "require_summer" in cfg:
            f.require_summer = bool(cfg["require_summer"])
        if "min_year" in cfg:
            f.min_year = cfg["min_year"]  # may be null to disable
        if "location_keywords" in cfg:
            f.location_keywords = [k.lower() for k in cfg["location_keywords"]]
        if "block_keywords" in cfg:
            f.block_keywords = [k.lower() for k in cfg["block_keywords"]]
        if "keep_unknown_location" in cfg:
            f.keep_unknown_location = bool(cfg["keep_unknown_location"])
        return f

    def _loc_re(self):
        if not self.location_keywords:
            return None
        pat = "|".join(r"\b" + re.escape(k) + r"\b" for k in self.location_keywords)
        return re.compile(pat, re.IGNORECASE)

    def _block_re(self):
        if not self.block_keywords:
            return None
        pat = "|".join(r"\b" + re.escape(k) + r"\b" for k in self.block_keywords)
        return re.compile(pat, re.IGNORECASE)


def _haystack(job: Job) -> str:
    return " ".join(filter(None, [job.title, job.department]))


def is_internship(job: Job) -> bool:
    return bool(_INTERNSHIP_RE.search(_haystack(job)))


def matched_categories(job: Job, filt: Filters) -> list[str]:
    text = _haystack(job)
    return [name for name in filt.categories
            if name in _CATEGORY_PATTERNS and _CATEGORY_PATTERNS[name].search(text)]


def _year_ok(job: Job, filt: Filters) -> bool:
    if filt.min_year is None:
        return True
    years = [int(y) for y in _YEAR_RE.findall(_haystack(job))]
    if not years:
        return True                    # undated → keep
    return max(years) >= filt.min_year


def _location_ok(job: Job, filt: Filters) -> bool:
    loc_re = filt._loc_re()
    if loc_re is None:
        return True
    # Look at location + title + url, since some bake the city into those.
    hay = " ".join(filter(None, [job.location, job.title, job.url]))
    if loc_re.search(hay):
        return True  # a wanted (European) location wins even if others appear
    # A named non-European location and no European one → drop (helps html firms
    # whose global parent posts worldwide, e.g. an Amsterdam firm's Singapore role).
    block_re = filt._block_re()
    if block_re and block_re.search(hay):
        return False
    # No explicit location signal anywhere.
    if job.location:
        return False  # had a location, just not a wanted one
    # Unknown location. html-source jobs only pass when the firm is European;
    # otherwise fall back to the global keep_unknown_location setting.
    if job.source == "html":
        return job.assume_europe
    return filt.keep_unknown_location


def match(job: Job, filt: Filters | None = None) -> list[str] | None:
    """Return matched categories if the job qualifies, else None."""
    filt = filt or Filters()
    if not is_internship(job):
        return None
    text = _haystack(job)
    if filt.require_summer and _NON_SUMMER_RE.search(text) and not _SUMMER_RE.search(text):
        return None
    if not _year_ok(job, filt):
        return None
    if not _location_ok(job, filt):
        return None
    cats = matched_categories(job, filt)
    return cats or None


def filter_jobs(jobs: list[Job], filt: Filters | None = None) -> list[Job]:
    filt = filt or Filters()
    out = []
    for job in jobs:
        cats = match(job, filt)
        if cats:
            job.categories = cats
            out.append(job)
    return out
