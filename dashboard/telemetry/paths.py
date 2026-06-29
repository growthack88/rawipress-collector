"""Canonical filesystem locations for the collector node.

Everything is resolved relative to the repo root (the parent of the
``dashboard`` package) so the dashboard works regardless of the current
working directory.
"""
from __future__ import annotations

from pathlib import Path

# dashboard/telemetry/paths.py -> repo root is three parents up.
ROOT: Path = Path(__file__).resolve().parents[2]

CONFIG_DIR: Path = ROOT / "config"
DATA_DIR: Path = ROOT / "data"
LOGS_DIR: Path = ROOT / "logs"

SOURCES_FILE: Path = CONFIG_DIR / "sources.json"
LOG_FILE: Path = LOGS_DIR / "collector.log"
SENT_CACHE_FILE: Path = DATA_DIR / "sent_urls.json"
ENV_FILE: Path = ROOT / ".env"
APP_ENTRY: Path = ROOT / "app.py"

__all__ = [
    "ROOT",
    "CONFIG_DIR",
    "DATA_DIR",
    "LOGS_DIR",
    "SOURCES_FILE",
    "LOG_FILE",
    "SENT_CACHE_FILE",
    "ENV_FILE",
    "APP_ENTRY",
]
