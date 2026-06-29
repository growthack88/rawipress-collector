"""Run a live collection capture and parse the real items it returns.

This is how the dashboard shows genuine article headlines without any local
database: it shells out to ``python app.py dry-run [name]``, which fetches from
the live Saudi sources and prints the mapped ``IngestItem`` objects as JSON to
stdout (no network POST, nothing stored). We parse that JSON back into
``CapturedArticle`` rows.

The call is blocking (network-bound, can take tens of seconds) and is intended
to be driven from a Textual thread worker, never the UI thread.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime

from dashboard.telemetry.paths import ROOT


@dataclass
class CapturedArticle:
    title: str
    url: str
    body: str
    media_url: str
    posted_at: str
    source: str  # best-effort, derived from URL host

    @property
    def host(self) -> str:
        from urllib.parse import urlsplit

        return urlsplit(self.url).netloc.replace("www.", "")


@dataclass
class CaptureResult:
    ok: bool
    articles: list[CapturedArticle]
    error: str
    ran_at: datetime
    target: str  # source name or "all"


def run_capture(source: str | None = None, timeout: int = 120) -> CaptureResult:
    """Invoke ``app.py dry-run`` and parse the JSON it prints to stdout."""
    target = source or "all"
    cmd = [sys.executable, "app.py", "dry-run"]
    if source:
        cmd.append(source)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CaptureResult(False, [], f"capture timed out after {timeout}s", datetime.now(), target)
    except Exception as exc:  # pragma: no cover - defensive
        return CaptureResult(False, [], f"{type(exc).__name__}: {exc}", datetime.now(), target)

    stdout = proc.stdout.strip()
    if not stdout:
        err = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "no output"
        return CaptureResult(False, [], err, datetime.now(), target)

    try:
        items = json.loads(stdout)
    except json.JSONDecodeError:
        return CaptureResult(False, [], "could not parse capture output", datetime.now(), target)

    articles = [
        CapturedArticle(
            title=(it.get("title") or "(untitled)").strip(),
            url=it.get("original_url", ""),
            body=(it.get("body") or "").strip(),
            media_url=it.get("media_url", ""),
            posted_at=it.get("posted_at", ""),
            source=_host(it.get("original_url", "")),
        )
        for it in items
        if isinstance(it, dict)
    ]
    return CaptureResult(True, articles, "", datetime.now(), target)


def _host(url: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(url).netloc.replace("www.", "") or "?"


__all__ = ["CapturedArticle", "CaptureResult", "run_capture"]
