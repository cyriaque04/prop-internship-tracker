"""WhatsApp notifications via CallMeBot + a plain-text fallback.

CallMeBot is a free personal-use relay: you authorize your own number once and
receive an API key, then messages are sent with a single HTTPS GET. Credentials
come from the environment so nothing secret is committed:

    CALLMEBOT_PHONE   e.g. +33612345678   (your WhatsApp number, with country code)
    CALLMEBOT_APIKEY  the key CallMeBot sent you
"""

from __future__ import annotations

import os
import urllib.parse

from . import http
from .ats import Job
from .http import HttpError

CALLMEBOT_ENDPOINT = "https://api.callmebot.com/whatsapp.php"


def whatsapp_configured() -> bool:
    return bool(os.environ.get("CALLMEBOT_PHONE") and
               os.environ.get("CALLMEBOT_APIKEY"))


def send_whatsapp(text: str) -> None:
    phone = os.environ["CALLMEBOT_PHONE"]
    apikey = os.environ["CALLMEBOT_APIKEY"]
    params = urllib.parse.urlencode(
        {"phone": phone, "text": text, "apikey": apikey}
    )
    # CallMeBot returns HTML; a non-2xx raises HttpError which the caller logs.
    http.get_text(f"{CALLMEBOT_ENDPOINT}?{params}")


def format_job_line(job: Job) -> str:
    bits = [f"• {job.firm} — {job.title}"]
    if job.location:
        bits.append(f"  📍 {job.location}")
    cats = "/".join(job.categories)
    if cats:
        bits.append(f"  🏷 {cats}")
    bits.append(f"  🔗 {job.url}")
    return "\n".join(bits)


def format_digest(new_jobs: list[Job]) -> str:
    n = len(new_jobs)
    header = f"🚨 {n} new prop internship{'s' if n != 1 else ''} (quant/trading/structuring)"
    body = "\n\n".join(format_job_line(j) for j in new_jobs)
    return f"{header}\n\n{body}"


def notify_new(new_jobs: list[Job]) -> list[Job]:
    """Send WhatsApp digests for new jobs, chunked to stay under length limits.

    Returns the list of jobs that were successfully delivered. If a chunk fails,
    delivery stops and the already-sent jobs are returned, so the caller can mark
    only those as seen and retry the rest on the next run.
    """
    sent: list[Job] = []
    batch = 6
    for i in range(0, len(new_jobs), batch):
        chunk = new_jobs[i:i + batch]
        try:
            send_whatsapp(format_digest(chunk))
            sent.extend(chunk)
        except HttpError:
            break
    return sent
