"""Fetchers for the applicant tracking systems prop firms commonly use.

Each fetcher takes a firm config dict and returns a list of normalized Job
objects. Unknown/failed sources raise so the caller can log and continue.

Supported ``source`` values:
    greenhouse       - boards-api.greenhouse.io
    lever            - api.lever.co
    ashby            - api.ashbyhq.com posting-api
    smartrecruiters  - api.smartrecruiters.com
    workday          - {tenant}.myworkdayjobs.com cxs endpoint
    html             - best-effort scrape of a plain careers page
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from . import http


@dataclass
class Job:
    firm: str
    title: str
    url: str
    location: str = ""
    department: str = ""
    source: str = ""
    raw_id: str = ""
    categories: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        """Stable unique id used for de-duplication across runs."""
        base = self.raw_id or self.url or self.title
        return f"{self.firm}::{base}".lower()

    def to_dict(self) -> dict:
        return {
            "firm": self.firm,
            "title": self.title,
            "url": self.url,
            "location": self.location,
            "department": self.department,
            "source": self.source,
            "categories": self.categories,
            "uid": self.uid,
        }


# --------------------------------------------------------------------------
# Individual ATS fetchers
# --------------------------------------------------------------------------

def fetch_greenhouse(firm: str, cfg: dict) -> list[Job]:
    token = cfg["token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false"
    data = http.get_json(url)
    jobs = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        depts = ", ".join(d.get("name", "") for d in j.get("departments", []) or [])
        jobs.append(
            Job(
                firm=firm,
                title=j.get("title", "").strip(),
                url=j.get("absolute_url", ""),
                location=loc,
                department=depts,
                source="greenhouse",
                raw_id=str(j.get("id", "")),
            )
        )
    return jobs


def fetch_lever(firm: str, cfg: dict) -> list[Job]:
    company = cfg["company"]
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    data = http.get_json(url)
    jobs = []
    for j in data:
        cats = j.get("categories", {}) or {}
        commitment = cats.get("commitment", "") or ""
        team = cats.get("team", "") or ""
        jobs.append(
            Job(
                firm=firm,
                title=j.get("text", "").strip(),
                url=j.get("hostedUrl", "") or j.get("applyUrl", ""),
                location=cats.get("location", "") or "",
                # fold commitment (e.g. "Internship") + team into department
                department=" / ".join(x for x in (team, commitment) if x),
                source="lever",
                raw_id=str(j.get("id", "")),
            )
        )
    return jobs


def fetch_ashby(firm: str, cfg: dict) -> list[Job]:
    org = cfg["org"]
    url = f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=false"
    data = http.get_json(url)
    jobs = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        emp = j.get("employmentType", "") or ""
        dept = j.get("department", "") or j.get("team", "") or ""
        jobs.append(
            Job(
                firm=firm,
                title=j.get("title", "").strip(),
                url=j.get("jobUrl", "") or j.get("applyUrl", ""),
                location=j.get("location", "") or "",
                department=" / ".join(x for x in (dept, emp) if x),
                source="ashby",
                raw_id=str(j.get("id", "")),
            )
        )
    return jobs


def fetch_smartrecruiters(firm: str, cfg: dict) -> list[Job]:
    company = cfg["company"]
    jobs = []
    offset = 0
    while True:
        url = (
            f"https://api.smartrecruiters.com/v1/companies/{company}/postings"
            f"?limit=100&offset={offset}"
        )
        data = http.get_json(url)
        content = data.get("content", [])
        for j in content:
            loc = j.get("location", {}) or {}
            loc_str = ", ".join(
                x for x in (loc.get("city", ""), loc.get("country", "")) if x
            )
            dept = (j.get("department", {}) or {}).get("label", "")
            jid = j.get("id", "")
            jobs.append(
                Job(
                    firm=firm,
                    title=j.get("name", "").strip(),
                    url=f"https://jobs.smartrecruiters.com/{company}/{jid}",
                    location=loc_str,
                    department=dept,
                    source="smartrecruiters",
                    raw_id=str(jid),
                )
            )
        total = data.get("totalFound", len(content))
        offset += 100
        if offset >= total or not content:
            break
    return jobs


def fetch_workday(firm: str, cfg: dict) -> list[Job]:
    host = cfg["host"]          # e.g. optiver.wd3.myworkdayjobs.com
    tenant = cfg["tenant"]      # e.g. optiver
    site = cfg["site"]          # e.g. External
    endpoint = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    jobs = []
    offset = 0
    limit = 20
    for _ in range(20):  # hard cap: 20 pages (400 postings)
        payload = {"appliedFacets": {}, "limit": limit, "offset": offset,
                   "searchText": ""}
        data = http.post_json(endpoint, payload)
        postings = data.get("jobPostings", [])
        for j in postings:
            path = j.get("externalPath", "")
            url = f"https://{host}/en-US/{site}{path}" if path else f"https://{host}"
            loc = j.get("locationsText", "")
            jobs.append(
                Job(
                    firm=firm,
                    title=j.get("title", "").strip(),
                    url=url,
                    location=loc,
                    department="",
                    source="workday",
                    raw_id=j.get("bulletFields", [""])[0] or path,
                )
            )
        total = data.get("total", 0)
        offset += limit
        if offset >= total or not postings:
            break
    return jobs


_ANCHOR_RE = re.compile(
    r'<a\b[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def fetch_html(firm: str, cfg: dict) -> list[Job]:
    """Best-effort scrape: pull anchor links from a static careers page.

    This only works for server-rendered pages. JS-rendered boards return
    nothing here (which is why ATS sources above are strongly preferred).
    """
    base = cfg["url"]
    page = http.get_text(base)
    jobs = []
    seen = set()
    for href, inner in _ANCHOR_RE.findall(page):
        text = html_lib.unescape(_TAG_RE.sub("", inner)).strip()
        if not text or len(text) > 160:
            continue
        url = urljoin(base, href)
        if url in seen:
            continue
        seen.add(url)
        jobs.append(
            Job(
                firm=firm,
                title=text,
                url=url,
                source="html",
                raw_id=url,
            )
        )
    return jobs


_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "workday": fetch_workday,
    "html": fetch_html,
}


def fetch_firm(cfg: dict) -> list[Job]:
    """Dispatch to the correct fetcher based on cfg['source']."""
    source = cfg.get("source")
    fetcher = _FETCHERS.get(source)
    if fetcher is None:
        raise ValueError(f"Unknown source '{source}' for firm {cfg.get('name')}")
    return fetcher(cfg["name"], cfg)


def available_sources() -> list[str]:
    return sorted(_FETCHERS)
