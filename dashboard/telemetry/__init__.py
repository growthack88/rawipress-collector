"""Real, local telemetry for the RawiPress collector node.

Every reader here points at an artifact that actually exists on the box. No
SQLite article database is involved — the node is push-only — so the data
surfaces are the source registry, the collection log, the optional sent-cache,
live captures, and host metrics.
"""
from __future__ import annotations

from dashboard.telemetry.facade import Telemetry

__all__ = ["Telemetry"]
