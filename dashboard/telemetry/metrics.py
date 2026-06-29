"""Host and process metrics for the operations header.

Uses ``psutil`` when available and degrades gracefully if a metric can't be
read. All values are best-effort and never raise into the UI.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

try:  # psutil is a hard dep of the dashboard, but stay defensive
    import psutil
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

from dashboard.telemetry.paths import (
    ENV_FILE,
    LOG_FILE,
    SENT_CACHE_FILE,
)

_PROC_START = time.time()
_PLACEHOLDER_HINT = "__get_from"


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    mnt, _ = divmod(rem, 60)
    if d:
        return f"{d}d {h}h {mnt}m"
    if h:
        return f"{h}h {mnt}m"
    return f"{mnt}m"


@dataclass
class SentCacheStats:
    enabled: bool
    count: int
    unique_domains: int


def sent_cache_stats() -> SentCacheStats:
    """Stats from ``data/sent_urls.json`` (bandwidth dedup cache, optional)."""
    if not SENT_CACHE_FILE.exists():
        return SentCacheStats(enabled=False, count=0, unique_domains=0)
    try:
        data = json.loads(SENT_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return SentCacheStats(enabled=True, count=0, unique_domains=0)
    urls = list(data.keys()) if isinstance(data, dict) else list(data)
    domains = {urlsplit(u).netloc for u in urls if isinstance(u, str)}
    return SentCacheStats(enabled=True, count=len(urls), unique_domains=len(domains))


def ingest_configured() -> bool:
    """True if .env exists with a non-placeholder INGEST_SECRET + SUPABASE_URL."""
    if not ENV_FILE.exists():
        return False
    try:
        text = ENV_FILE.read_text(encoding="utf-8")
    except OSError:
        return False
    have_url = have_secret = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("SUPABASE_URL=") and "supabase.co" in line:
            have_url = True
        if line.startswith("INGEST_SECRET=") and _PLACEHOLDER_HINT not in line and len(line) > len("INGEST_SECRET="):
            have_secret = True
    return have_url and have_secret


@dataclass
class SystemMetrics:
    cpu_percent: float
    mem_percent: float
    mem_used: str
    mem_total: str
    host_uptime: str
    proc_uptime: str
    log_size: str
    sent_cache: SentCacheStats
    ingest_ready: bool


def system_metrics() -> SystemMetrics:
    cpu = mem_pct = 0.0
    mem_used = mem_total = "—"
    host_uptime = "—"
    if psutil is not None:
        try:
            cpu = psutil.cpu_percent(interval=None)
        except Exception:
            pass
        try:
            vm = psutil.virtual_memory()
            mem_pct = vm.percent
            mem_used = _fmt_bytes(vm.used)
            mem_total = _fmt_bytes(vm.total)
        except Exception:
            pass
        try:
            host_uptime = _fmt_duration(time.time() - psutil.boot_time())
        except Exception:
            pass

    log_size = "—"
    if LOG_FILE.exists():
        try:
            log_size = _fmt_bytes(LOG_FILE.stat().st_size)
        except OSError:
            pass

    return SystemMetrics(
        cpu_percent=cpu,
        mem_percent=mem_pct,
        mem_used=mem_used,
        mem_total=mem_total,
        host_uptime=host_uptime,
        proc_uptime=_fmt_duration(time.time() - _PROC_START),
        log_size=log_size,
        sent_cache=sent_cache_stats(),
        ingest_ready=ingest_configured(),
    )


__all__ = ["SystemMetrics", "SentCacheStats", "system_metrics", "sent_cache_stats", "ingest_configured"]
