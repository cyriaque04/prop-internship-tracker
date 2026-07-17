"""Tiny HTTP helpers built on the standard library (no external deps).

Every request sends a browser-like User-Agent because several applicant
tracking systems reject the default Python urllib agent.
"""

from __future__ import annotations

import gzip
import json
import ssl
import urllib.error
import urllib.request
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 prop-internship-tracker/1.0"
)

DEFAULT_TIMEOUT = 25

# Some sites have imperfect certificate chains; we only read public job data,
# so fall back to an unverified context rather than failing the whole run.
_UNVERIFIED = ssl._create_unverified_context()


class HttpError(Exception):
    """Raised when a request cannot be completed."""


def _read(resp) -> bytes:
    data = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip":
        data = gzip.decompress(data)
    return data


def _request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        "Accept-Encoding": "gzip",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)

    def _open(ctx):
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return _read(resp).decode("utf-8", errors="replace")

    try:
        try:
            return _open(None)  # default (verified) context
        except (ssl.SSLError, urllib.error.URLError) as exc:
            # A TLS-intercepting proxy (or missing local CA bundle) surfaces as
            # an SSLError, sometimes wrapped inside URLError.reason. Since we
            # only read public job data, retry without cert verification.
            reason = getattr(exc, "reason", exc)
            if isinstance(exc, ssl.SSLError) or isinstance(reason, ssl.SSLError):
                return _open(_UNVERIFIED)
            raise
    except urllib.error.HTTPError as exc:  # 4xx / 5xx
        raise HttpError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise HttpError(f"URL error for {url}: {exc.reason}") from exc
    except Exception as exc:  # noqa: BLE001 - surface anything else uniformly
        raise HttpError(f"Request failed for {url}: {exc}") from exc


def get_text(url: str, *, headers: dict[str, str] | None = None,
             timeout: int = DEFAULT_TIMEOUT) -> str:
    return _request(url, headers=headers, timeout=timeout)


def get_json(url: str, *, headers: dict[str, str] | None = None,
             timeout: int = DEFAULT_TIMEOUT) -> Any:
    return json.loads(_request(url, headers=headers, timeout=timeout))


def post_json(url: str, payload: dict[str, Any], *,
              headers: dict[str, str] | None = None,
              timeout: int = DEFAULT_TIMEOUT) -> Any:
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    return json.loads(
        _request(url, method="POST", data=body, headers=hdrs, timeout=timeout)
    )
