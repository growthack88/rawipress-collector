# Rawi Press — Saudi Collector

A **push-only** collector that runs on a Mac **inside Saudi Arabia** (most Saudi
news sites geo-block non-KSA IPs) and POSTs raw articles + X posts to the cloud
`ingest` edge function. It does **not** store, summarize, deduplicate, extract
entities, or render anything — the cloud pipeline does all of that.

```
[Saudi sites + X]  →  COLLECTOR (KSA, this repo)  →  POST raw items
                                                       ↓
                         Supabase /functions/v1/ingest
                         (dedup → AI summarize → entities → story → store)
                                                       ↓
                                    web app reads & displays
```

The collector is the only component inside KSA. It PUSHES. Everything else
(database, AI, website) lives in the cloud and only READS. **Never add
storage/summarization/translation/entity logic here.**

## Quick start

```bash
cd ~/Documents
git clone https://github.com/growthack88/rawipress-collector.git RawiPress && cd RawiPress
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then fill in the secrets (see below)
python app.py dry-run arabnews   # map items, print JSON, no POST
python app.py collect            # collect news + social, POST to ingest
```

Run from **inside KSA** — Saudi feeds geo-block elsewhere.

## Secrets (`.env`, gitignored)

| var | where to get it |
|---|---|
| `SUPABASE_URL` | `https://uiwblgqhpjhbtmlgnfkk.supabase.co` |
| `INGEST_SECRET` | Supabase → Edge Functions → secrets |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API |
| `X_BEARER_TOKEN` / `APIFY_TOKEN` / `NITTER_INSTANCES` | one X fetch method (optional) |

The device is Tailscale-only and trusted, so holding the service key locally is
acceptable — just never commit `.env`.

## CLI

```bash
python app.py collect              # news + social once → POST to ingest
python app.py news                 # news sources only
python app.py social               # X/social channels only
python app.py source <name>        # one source/channel by name
python app.py dry-run [name]       # map to IngestItems + print JSON, no POST
python app.py list                 # configured sources + channels (chan:✓/✗)
python app.py schedule [min]       # foreground auto-collector (default 15)
```

Logs go to stderr + `logs/collector.log`; `dry-run` prints clean JSON to stdout
(`python app.py dry-run arabnews | jq`).

## How to add a source

1. **Create the channel in Supabase first.** Every item is tagged with a
   `channel_id` = the uuid of a row in `source_channels`. Create the `Source`,
   then a `Channel` per feed/handle, with **`ingest_method = 'ksa_collector'`**
   and `is_active = true`. Via SQL editor:

   ```sql
   insert into source_channels (source_id, platform, handle, channel_url, ingest_method, is_active)
   values ('<source_uuid>', 'rss', null, 'https://www.arabnews.com/rss.xml', 'ksa_collector', true)
   returning id;     -- paste this id into config/sources.json
   ```

   `ingest_method='ksa_collector'` keeps the retired cloud pullers from
   double-ingesting these channels.

2. **Add the entry to `config/sources.json`** with that `channel_id`:

   ```jsonc
   // news[] — collection_method: rss | sitemap | html
   { "name": "arabnews", "channel_id": "PASTE-UUID", "collection_method": "rss",
     "rss_url": "https://www.arabnews.com/rss.xml", "enabled": true,
     "fetch_full_content": true }     // follow links for full body (RSS only)

   // social[] — platform 'x'; cloud stores these as social_post automatically
   { "name": "saudinews50_x", "channel_id": "PASTE-UUID", "platform": "x",
     "handle": "SaudiNews50", "max_posts": 30, "enabled": true }
   ```

   Sources with `channel_id: null` are **skipped with a warning** — wire them up
   when the channel exists.

## The ingest contract

`POST {SUPABASE_URL}/functions/v1/ingest` with headers `X-Ingest-Secret` and
`Authorization: Bearer <service role key>`, body
`{"channel_id": "<uuid>", "items": [IngestItem, ...]}` (≤25 items/batch,
auto-chunked). Response: `{found, new, skipped}`.

**IngestItem** (only `original_url` required): `original_url`, `title`, `body`
(full text), `media_url`, `media_type` (`image|video`), `posted_at` (ISO-8601
UTC), `raw_engagement` (social). The cloud dedups on
`sha256(normalized_url + lowercased_title)`, so re-sending is safe and cheap.

## Architecture

```
RawiPress/
├── app.py                    # CLI dispatcher
├── config/sources.json       # news[] + social[] registry (add a source = JSON edit)
├── collectors/               # extraction only (return raw dicts) — REUSED
│   ├── rss.py                #   feedparser → lenient xml → HTML fallback; opt-in full-body fetch
│   ├── sitemap.py            #   walk sitemap → fetch + extract each article (full body)
│   ├── html.py               #   config-driven CSS scraper (last resort)
│   ├── article.py            #   readability-lite content/date/author/image extractor
│   └── social_x.py           #   X via API v2 / Apify / Nitter (pluggable fetch_x_posts)
├── core/
│   ├── pipeline.py           #   collect → map to IngestItem → POST (news + social)
│   ├── ingest_client.py      #   POST batches to /functions/v1/ingest (retry on 5xx)
│   ├── sent_cache.py         #   optional local already-sent cache (RAWI_SENT_CACHE=1)
│   └── env.py                #   .env loader + typed getters (no python-dotenv)
├── utils/                    # parser (normalize/canonical url/iso dates), http (retries), logger
├── tests/test_core.py        # mapping + batching tests (python tests/test_core.py)
├── deploy/                   # deploy.sh, run_collect.sh, launchd plist (every 15 min)
└── logs/                     # runtime (gitignored)
```

## Deploy on the Saudi node

```bash
bash deploy/deploy.sh      # rsync code to saudi:~/Documents/RawiPress + smoke test
# enable the 15-min schedule:
cp deploy/com.rawipress.collector.plist ~/Library/LaunchAgents/   # edit paths first
launchctl load ~/Library/LaunchAgents/com.rawipress.collector.plist
```

`deploy.sh` never touches the node's `data/`, `logs/`, or venv. The launchd job
runs `deploy/run_collect.sh` (→ `app.py collect`) every 15 min.

## Acceptance tests

1. **Dry run** — `app.py dry-run arabnews` prints IngestItems; every one has
   `original_url` + non-empty `body`. ✅
2. **Live batch** — with a real `channel_id`, `app.py source arabnews` returns
   `{found,new,...}` and rows appear in the review queue.
3. **Dedup** — run a source twice; the second run returns `new: 0`.
4. **Social** — `app.py source <x-channel>` → items appear as `social_post`.
5. **Failure isolation** — a bad source logs an error; the rest of the run
   completes. ✅
