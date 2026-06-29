"""RawiPress Terminal OS — a fullscreen Textual operations center for the
Saudi collector node.

This dashboard is read-only telemetry for *this* collector node. The node is
push-only (it POSTs to the cloud ingest pipeline and stores no article
database locally), so the dashboard surfaces what genuinely lives on the box:

  * the source registry          (config/sources.json)
  * collection-run history       (logs/collector.log)
  * the local sent-cache         (data/sent_urls.json, if enabled)
  * live collection captures     (python app.py dry-run, on demand)
  * system + process metrics     (psutil)

Run it with::

    cd ~/Documents/RawiPress
    source .venv/bin/activate
    python dashboard/app.py
"""

__all__ = ["__version__"]
__version__ = "1.0.0"
