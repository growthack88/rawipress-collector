"""Core tests for the push-only collector. Run: python tests/test_core.py (or pytest)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.parser import canonical_url, url_id, to_iso, normalize  # noqa: E402
from core import pipeline, ingest_client  # noqa: E402


def test_canonical_url_strips_tracking():
    a = canonical_url("https://Ex.com/News/1/?utm_source=x&id=5#frag")
    b = canonical_url("https://ex.com/News/1?id=5")
    assert a == b, (a, b)


def test_url_id_stable():
    assert url_id("https://ex.com/a") == url_id("https://ex.com/a/")


def test_to_iso_parses_string_dates():
    # +03:00 (KSA) converts to UTC; unparseable -> "" (cloud defaults to now)
    assert to_iso("2026-06-29T10:00:00+03:00") == "2026-06-29T07:00:00+00:00"
    assert to_iso("not a date") == ""
    assert to_iso("") == ""


def test_news_to_ingest_shape():
    raw = [{
        "url": "https://ex.com/a?utm_source=x",
        "title": "  Hello  ",
        "content": "Full article body text here.",
        "summary": "snippet",
        "published_at": "2026-06-29T10:00:00+03:00",
        "image": "https://ex.com/i.jpg",
    }]
    items = pipeline.news_to_ingest(raw, {"name": "t", "category": "media"})
    assert len(items) == 1
    it = items[0]
    assert it["original_url"] == "https://ex.com/a"           # tracking stripped
    assert it["title"] == "Hello"
    assert it["body"] == "Full article body text here."        # content preferred
    assert it["media_url"] == "https://ex.com/i.jpg"
    assert it["media_type"] == "image"
    assert it["posted_at"] == "2026-06-29T07:00:00+00:00"      # UTC


def test_news_to_ingest_drops_empty_optionals():
    raw = [{"url": "https://ex.com/b", "title": "T", "content": "Body"}]
    it = pipeline.news_to_ingest(raw, {"name": "t"})[0]
    assert "media_url" not in it and "media_type" not in it and "posted_at" not in it
    assert it["original_url"] and it["body"] == "Body"


def test_news_to_ingest_skips_urlless():
    raw = [{"url": "", "title": "no url"}, {"url": "https://ex.com/c", "title": "ok", "content": "x"}]
    items = pipeline.news_to_ingest(raw, {"name": "t"})
    assert len(items) == 1 and items[0]["original_url"] == "https://ex.com/c"


def test_social_to_ingest_shape():
    posts = [{
        "url": "https://x.com/h/status/123",
        "text": "x" * 120,
        "posted_at": "2026-06-29T10:00:00Z",
        "image": "https://x.com/m.jpg",
        "media_type": "image",
        "engagement": {"likes": 12, "retweets": 3},
    }]
    it = pipeline.social_to_ingest(posts)[0]
    assert it["original_url"] == "https://x.com/h/status/123"
    assert len(it["title"]) == 80                              # title truncated
    assert it["body"] == "x" * 120
    assert it["raw_engagement"] == {"likes": 12, "retweets": 3}


def test_ingest_client_batches(monkeypatch=None):
    # Stub the per-batch POST and confirm chunking + aggregation (no network).
    calls = []

    def fake_post_batch(endpoint, headers, channel_id, items):
        calls.append(len(items))
        return {"found": len(items), "new": len(items), "skipped": 0}

    ingest_client._post_batch = fake_post_batch  # type: ignore
    ingest_client._endpoint = lambda: "http://x"  # type: ignore
    ingest_client._headers = lambda: {}           # type: ignore

    items = [{"original_url": f"https://e/{i}"} for i in range(60)]
    totals = ingest_client.post_items("chan-uuid", items)
    assert calls == [25, 25, 10]                   # MAX_BATCH chunking
    assert totals == {"found": 60, "new": 60, "skipped": 0}


def _run():
    fns = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    return passed == len(fns)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
