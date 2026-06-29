# RawiPress Terminal OS

A fullscreen [Textual](https://textual.textualize.io/) **operations center** for
the Saudi collector node — Palantir / Bloomberg-terminal aesthetic, real data,
no fake animation.

```bash
cd ~/Documents/RawiPress
source .venv/bin/activate
pip install -r requirements.txt      # adds textual, rich, psutil
python dashboard/app.py
```

## What it shows — and where the data is real

This node is **push-only**: it fetches from Saudi sources and POSTs raw items to
the cloud `ingest` pipeline. It keeps **no local article database** — the
articles live in cloud Supabase. So this dashboard is a *monitoring console for
the box itself*, and every panel is wired to a real local artifact:

| Surface | Real source |
|---|---|
| Live statistics, source health | `config/sources.json` (the registry) |
| Activity feed, analytics, logs, success rate | `logs/collector.log` (parsed) |
| Sent-cache stats | `data/sent_urls.json` (if `RAWI_SENT_CACHE=1`) |
| **Live Capture** (Articles screen) | `python app.py dry-run` run on demand — real headlines fetched live, nothing stored |
| CPU / memory / uptime | `psutil` |

> There is intentionally **no SQLite layer**. Adding one would violate the
> collector's "never store locally" rule. The Articles screen gets genuine
> article text by running a live capture, not by reading a database.

## Screens & keys

| Key | Screen | |
|---|---|---|
| `D` | Dashboard | logo, live stats, activity feed, source health |
| `A` | Articles | live capture of real headlines + detail pane |
| `S` | Sources | full registry with reconciled health, filterable |
| `L` | Logs | colour-coded live tail of `collector.log` |
| `T` | Analytics | top sources, by-category, hourly throughput, success/fail |
| `G` | Settings | ingest readiness, registry, paths |
| `/` | Search | filter sources / captured articles |
| `R` | Collect | run a live capture (background, non-blocking) |
| `F` | Refresh | force a telemetry re-read |
| `Q` | Quit | |

Statistics, feed and metrics refresh at **1 Hz**; tables rebuild every few
seconds so they don't fight your cursor. The log is only re-parsed when the
collector actually writes to it (mtime-cached).

## Architecture

```
dashboard/
  app.py                 RawiTerminalApp — theme, bindings, modes, capture worker
  css/rawi.tcss          operations-center theme (#09090B / emerald / blue …)
  telemetry/             read-only data layer (the only place that touches disk)
    paths.py             canonical file locations
    sources.py           parse + model config/sources.json
    logs.py              parse collector.log -> runs, per-source status, feed, analytics
    metrics.py           psutil host/process metrics + sent-cache + ingest readiness
    collector.py         run `app.py dry-run` and parse the live items it returns
    facade.py            Telemetry — mtime-cached entry point the UI calls
  widgets/               reusable Rich/Textual widgets (header, stats, activity,
                         health, source_table, charts, feed, card)
  screens/               one file per screen (+ search modal, refresh base)
```

The telemetry layer is pure and importable on its own — handy for testing:

```python
from dashboard.telemetry import Telemetry
t = Telemetry()
print(t.registry().total, t.log().success_rate, t.metrics().cpu_percent)
```
