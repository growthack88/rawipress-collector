# Rawi Press — Saudi Intelligence Collection Engine

Continuously collect, normalize, deduplicate, and store official Saudi
information sources. This is **Phase 1**: reliable collection + storage.
No AI, embeddings, or vector DBs yet — by design.

## Quick start (any Mac — clone & run)

```bash
cd ~/Documents
git clone https://github.com/growthack88/rawipress-collector.git RawiPress
cd RawiPress

python3 -m venv .venv                 # create a virtual environment
source .venv/bin/activate             # activate it
pip install -r requirements.txt       # install deps

python app.py collect                 # collect from all enabled sources
python app.py status                  # see what was stored
```

Collected articles land in `data/raw_articles.json`; logs in `logs/collector.log`.

> Run from **inside Saudi Arabia** for best results — many Saudi gov/finance
> feeds geo-restrict or serve different content outside KSA.

## Design

Config-driven, not one-file-per-source. You add a source by adding an
object to `config/sources.json`; the engine picks the right collector by
`collection_method`. Adding source #7…#100 is a JSON edit, not new code.

```
RawiPress/
├── app.py                 # CLI entrypoint + collection engine
├── config/sources.json    # source registry (the only file you edit to add sources)
├── collectors/
│   ├── base.py            # BaseCollector: fetch() + collect() contract
│   ├── rss.py             # generic RSS/Atom  (collection_method: "rss")
│   ├── sitemap.py         # generic sitemap   (collection_method: "sitemap")
│   └── html.py            # generic HTML list (collection_method: "html")
├── utils/
│   ├── parser.py          # normalize raw -> canonical model, url canonicalization, hashing
│   ├── storage.py         # atomic JSON store (data/raw_articles.json)
│   ├── deduplicator.py    # persistent URL-hash + title-hash seen-set (data/seen.json)
│   └── logger.py          # rotating file + stdout logging (logs/collector.log)
├── deploy/
│   ├── run_collect.sh     # launchd wrapper (activates venv, runs collect)
│   └── com.rawipress.collector.plist  # launchd job, every 15 min
├── data/                  # runtime output (gitignored)
└── logs/                  # runtime logs (gitignored)
```

## Data model

Each stored item:

```json
{
  "id": "<sha1 of canonical url>",
  "source": "spa",
  "category": "government",
  "title": "",
  "url": "https://...",
  "published_at": "ISO-8601 UTC or ''",
  "content": "",
  "summary": "",
  "tags": [],
  "collected_at": "ISO-8601 UTC"
}
```

## Collector contract

Each collector implements `collect()` and returns a list of **raw** dicts
(`source, title, url, published_at, content, summary, tags`). The engine
normalizes, dedupes, and stores them — collectors only do extraction.

Collection-method priority (per strategy): API > Sitemap > RSS > HTML > PDF > Social.
HTML is last-resort (most fragile). API connectors slot in as new collector
classes registered in `collectors/__init__.py`.

## Usage

```bash
source projects/venv/bin/activate     # on the Saudi node
python app.py collect                 # run every enabled source once
python app.py source arabnews         # run one source
python app.py status                  # storage + registry summary
python app.py list                    # list configured sources
```

## Scheduling (macOS launchd, every 15 min)

On the Saudi node (`ssh saudi`):

```bash
# paths in the plist assume /Users/graphics-2/Documents/RawiPress — edit if different
cp deploy/com.rawipress.collector.plist ~/Library/LaunchAgents/
launchctl load  ~/Library/LaunchAgents/com.rawipress.collector.plist
launchctl start com.rawipress.collector          # run once now
launchctl list | grep rawipress                  # confirm it's loaded
tail -f logs/collector.log                        # watch it work
```

## Adding a source

Append to `config/sources.json`:

```jsonc
// RSS
{ "name": "okaz", "display_name": "Okaz", "category": "media",
  "source_url": "https://www.okaz.com.sa",
  "collection_method": "rss", "rss_url": "https://www.okaz.com.sa/rss",
  "priority": 2, "enabled": true }

// Sitemap (optional: sitemap_max_urls, sitemap_url_contains)
{ "name": "cma", "category": "financial",
  "collection_method": "sitemap", "sitemap_url": "https://cma.org.sa/sitemap.xml",
  "sitemap_url_contains": "/news", "sitemap_max_urls": 100,
  "priority": 1, "enabled": true }

// HTML scrape (CSS selectors)
{ "name": "example", "category": "media",
  "collection_method": "html",
  "list_url": "https://example.com/news",
  "item_selector": "article.card", "title_selector": "h2 a",
  "summary_selector": ".excerpt",
  "priority": 3, "enabled": true }
```

## Important: run from inside Saudi Arabia

Many Saudi gov/finance sites geo-restrict or serve different markup outside
KSA. RSS feeds that 403/404 or parse as malformed from elsewhere typically
behave correctly on the in-country node. Treat the Saudi node as the source
of truth for what works; `"verified": true` in the registry marks feeds
confirmed from inside KSA.

## Roadmap

1. ✅ Collectors + storage (this)   2. Postgres/Supabase   3. Dedup at scale
4. Tagging   5. Arabic NLP   6. AI summaries   7. Search   8. Public API   9. Dashboard
