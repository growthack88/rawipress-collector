# Rawi Press v2 — Saudi News Intelligence Platform

From a simple RSS collector to a collection → enrichment → storage → dashboard →
API platform for official Saudi sources. Pure-Python intelligence layer (no ML
deps, no API keys) so the in-KSA node stays self-contained.

```
collect ─▶ normalize ─▶ enrich (AI-lite) ─▶ SQLite ─▶ Dashboard + REST API
 RSS/Sitemap/HTML       lang·summary·keywords        WAL    FastAPI + Jinja
 (full article text)    entities·topic·sentiment             dark "Bloomberg" UI
                        importance score
```

## Quick start

```bash
cd ~/Documents
git clone https://github.com/growthack88/rawipress-collector.git RawiPress && cd RawiPress
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python app.py collect          # collect + enrich + store
python app.py serve            # dashboard at http://127.0.0.1:8787
```

> On the Saudi node, the existing `projects/venv` already has the collection
> deps — just `pip install fastapi uvicorn jinja2 python-dateutil` into it,
> or use a fresh `.venv` as above. Run from **inside KSA** — feeds geo-block.

## CLI

```bash
python app.py collect              # all enabled sources
python app.py source spa           # one source
python app.py status               # storage + per-source health
python app.py list                 # configured sources
python app.py serve [host] [port]  # dashboard + API (default 127.0.0.1:8787)
python app.py schedule [minutes]   # foreground auto-collector (default 15)
python app.py initdb               # create schema
python app.py migrate [path]       # import legacy raw_articles.json
```

## Architecture

```
RawiPress/
├── app.py                      # CLI dispatcher
├── config/sources.json         # source registry (add a source = JSON edit)
├── collectors/                 # extraction (return raw dicts)
│   ├── base.py                 #   shared retry session
│   ├── rss.py                  #   robust: feedparser → lenient xml → HTML fallback
│   ├── sitemap.py              #   walks sitemap → fetches + extracts each article
│   ├── html.py                 #   config-driven CSS scraper (last resort)
│   └── article.py              #   readability-lite content/date/author extractor
├── core/                       # the platform
│   ├── db.py                   #   SQLite schema + DAO (4 tables, WAL)
│   ├── enrich.py               #   intelligence: lang/summary/keywords/entities/topic/sentiment/importance
│   └── pipeline.py             #   collect→normalize→enrich→store→log→health→stats
├── utils/                      # parser (normalize/canonical url/hash), http (retries), logger, dedup
├── web/                        # FastAPI app
│   ├── server.py               #   REST API + dashboard routes
│   ├── templates/              #   home, articles, article, sources, analytics, logs
│   └── static/                 #   style.css (dark emerald), analytics.js (Chart.js)
├── tests/test_core.py          # unit tests (run: python tests/test_core.py)
├── deploy/                     # deploy.sh, run_collect.sh, launchd plist
└── data/  logs/                # runtime (gitignored): rawipress.db, collector.log
```

## Database schema (SQLite — `data/rawipress.db`)

| table | purpose | key columns |
|---|---|---|
| **articles** | enriched articles | id, **hash** (unique=dedup), source, title, url, content, summary, published_at, collected_at, category, language, tags, keywords, entities, author, sentiment, importance_score |
| **sources** | registry + health | name, method, priority, enabled, last_collected_at, last_status, last_error, total_collected, success_count, failure_count |
| **collection_logs** | per-run audit | run_id, source, started_at, finished_at, duration_ms, fetched, new_count, status, error |
| **statistics** | daily snapshots | day, total, by_source, by_category, by_language |

Dedup is enforced by the UNIQUE `hash` (canonical-URL sha1). Indexes on
source / published_at / category / language / collected_at.

## Intelligence layer (Phase 3)

Pure Python, bilingual AR/EN, offline:
- **language** — Arabic-glyph ratio
- **summary** — extractive (keyword-ranked sentences); pluggable LLM hook via `enrich.set_llm_summarizer()`
- **keywords** — frequency minus AR+EN stopwords
- **entities** — Saudi org/location gazetteers + titled-person heuristic
- **topic** — bilingual keyword gazetteer (Economy, Energy, Finance, Government, Vision 2030, AI, Sports, …)
- **sentiment** — AR+EN polarity lexicon
- **importance_score** — source priority + content depth + entity richness (0–100)

## Dashboard (Phases 4–5)

Dark, executive, terminal-inspired (black + emerald — Bloomberg/Palantir feel):
- **Overview** — KPIs (total, today, sources, success rate), top sources/categories, latest feed
- **Articles** — search + source/topic/lang/date filters, sort, pagination, detail view (summary, keywords, entities, full text)
- **Source Monitor** — status, last collection, success/fail counts, last error
- **Analytics** — by day / source / category / language charts, trending keywords, top entities
- **Collection Logs** — every run with duration, fetched/new, errors

## REST API (Phase 6)

`/api/articles` (filters+pagination) · `/api/articles/{id}` · `/api/sources` ·
`/api/stats` · `/api/search?q=` · `/api/dashboard`

## Scheduling (Phase 7)

```bash
# launchd (recommended on the node) — every 15 min
cp deploy/com.rawipress.collector.plist ~/Library/LaunchAgents/   # edit paths first
launchctl load ~/Library/LaunchAgents/com.rawipress.collector.plist
# or, simplest: foreground loop
python app.py schedule 15
```

## Scaling to 100+ sources (next steps)

1. **Registry as data** — sources already config-driven; move `sources.json`
   into the `sources` table + an admin form so non-devs can add feeds.
2. **Concurrency** — collectors are independent; run them in a thread/process
   pool with a politeness rate-limit per domain.
3. **Postgres/Supabase** — swap `core/db.py` (same DAO interface) when SQLite
   write contention shows; add full-text search (FTS5 now, tsvector later).
4. **Per-source scheduling** — honor `crawl_frequency` instead of all-on-each-tick.
5. **Article extraction tuning** — per-source content selectors for sites the
   generic extractor misses; add PDF + API collectors (new classes in `collectors/__init__.py`).
6. **LLM summaries** — wire `enrich.set_llm_summarizer()` to Claude for the
   top-N by importance_score (cost-controlled).
7. **Alerting** — source health → notify on consecutive failures.
