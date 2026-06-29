"""Dependency-free .env loader + typed getters.

The Saudi node stays self-contained (no python-dotenv). On first access we
read a `.env` file at the project root into os.environ (without overriding
values already exported in the shell), then expose small typed getters.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

_loaded = False


def load_env(path: Path | None = None) -> None:
    """Parse KEY=VALUE lines from .env into os.environ (idempotent).

    Shell-exported vars win over the file, so launchd/env overrides work.
    Lines that are blank or start with '#' are ignored. Surrounding quotes
    on the value are stripped.
    """
    global _loaded
    if _loaded:
        return
    _loaded = True
    f = path or ENV_FILE
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get(key: str, default: str | None = None, required: bool = False) -> str | None:
    load_env()
    value = os.environ.get(key, default)
    if required and not value:
        raise RuntimeError(
            f"Missing required env var '{key}'. Set it in {ENV_FILE} "
            f"(see .env.example) or export it before running."
        )
    return value
