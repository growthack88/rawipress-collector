"""Shared HTTP session with retries, backoff, and a realistic UA.

One session is reused across collectors so connection pooling + a single
retry policy apply everywhere. Saudi gov/enterprise sites are picky about
UA and flaky under load, so retries matter.
"""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except Exception:  # very old urllib3
    Retry = None

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
        "RawiPress/2.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en;q=0.8",
}

_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is not None:
        return _session
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    if Retry is not None:
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1.5,  # 0s, 1.5s, 3s, 6s
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
    return _set(s)


def _set(s: requests.Session) -> requests.Session:
    global _session
    _session = s
    return s


def fetch(url: str, timeout: int = 25) -> requests.Response:
    resp = get_session().get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp
