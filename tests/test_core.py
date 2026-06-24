"""Core tests (Phase 8). Run: python tests/test_core.py  (or: pytest)"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.parser import canonical_url, url_id, normalize  # noqa: E402
from core import enrich, db  # noqa: E402


def test_canonical_url_strips_tracking():
    a = canonical_url("https://Ex.com/News/1/?utm_source=x&id=5#frag")
    b = canonical_url("https://ex.com/News/1?id=5")
    assert a == b, (a, b)


def test_url_id_stable():
    assert url_id("https://ex.com/a") == url_id("https://ex.com/a/")


def test_language_detection():
    assert enrich.detect_language("وزارة الاستثمار تعلن عن مشروع جديد") == "ar"
    assert enrich.detect_language("Saudi Arabia announces a new project") == "en"


def test_keywords_skip_stopwords():
    kws = enrich.extract_keywords("The economy economy economy of the kingdom grows")
    assert "economy" in kws
    assert "the" not in kws


def test_topic_classification():
    assert enrich.classify_topic("Aramco raised oil output and barrel prices", "Oil") == "Energy"
    assert enrich.classify_topic("NEOM announces Vision 2030 milestone", "NEOM") == "Vision 2030"


def test_enrich_fills_fields():
    item = normalize({"title": "Tadawul stocks rise", "url": "https://ex.com/x",
                      "content": "The Saudi stock market Tadawul saw shares rise today."}, {"name": "t", "category": "financial"})
    enrich.enrich(item, {"priority": 1})
    assert item["language"] == "en"
    assert item["keywords"]
    assert item["category"] in ("Finance", "Economy")
    assert 0 <= item["importance_score"] <= 100
    assert item["summary"]


def test_db_insert_and_dedup():
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    db.DB_PATH = tmp  # type: ignore
    db.DATA_DIR = tmp.parent  # type: ignore
    db.init_db()
    conn = db.connect()
    try:
        item = normalize({"title": "X", "url": "https://ex.com/a", "content": "hello world"}, {"name": "s"})
        item["hash"] = item["id"]
        enrich.enrich(item)
        assert db.insert_article(conn, item) is True
        assert db.insert_article(conn, item) is False  # duplicate hash
        conn.commit()
        rows, total = db.list_articles(conn)
        assert total == 1 and len(rows) == 1
    finally:
        conn.close()


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
