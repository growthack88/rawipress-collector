"""Rawi Press dashboard + REST API (Phases 4 & 6), FastAPI + Jinja2.

Run:  python app.py serve         (or: uvicorn web.server:app --reload)
Dash: http://127.0.0.1:8787/
API:  /api/articles /api/articles/{id} /api/sources /api/stats /api/search /api/dashboard
"""
from __future__ import annotations

import math
from pathlib import Path

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import db

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Rawi Press Intelligence API", version="2.0")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


def _conn():
    return db.connect()


# --------------------------------------------------------------------- API ---
@app.get("/api/dashboard")
def api_dashboard():
    conn = _conn()
    try:
        data = db.dashboard_stats(conn)
        data["by_day"] = db.articles_by_day(conn, 14)
        data["trending_keywords"] = db.trending_keywords(conn, 25)
        data["top_entities"] = db.top_entities(conn, 15)
        return JSONResponse(data)
    finally:
        conn.close()


@app.get("/api/stats")
def api_stats():
    conn = _conn()
    try:
        return JSONResponse(db.dashboard_stats(conn))
    finally:
        conn.close()


@app.get("/api/sources")
def api_sources():
    conn = _conn()
    try:
        return JSONResponse(db.list_sources(conn))
    finally:
        conn.close()


@app.get("/api/articles")
def api_articles(
    q: str = "", source: str = "", category: str = "", language: str = "",
    date_from: str = "", date_to: str = "",
    sort: str = "collected_at", order: str = "desc",
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
):
    conn = _conn()
    try:
        rows, total = db.list_articles(
            conn, q=q, source=source, category=category, language=language,
            date_from=date_from, date_to=date_to, sort=sort, order=order,
            limit=page_size, offset=(page - 1) * page_size,
        )
        return JSONResponse({"total": total, "page": page, "page_size": page_size, "items": rows})
    finally:
        conn.close()


@app.get("/api/articles/{article_id}")
def api_article(article_id: int):
    conn = _conn()
    try:
        art = db.get_article(conn, article_id)
        return JSONResponse(art) if art else JSONResponse({"error": "not found"}, status_code=404)
    finally:
        conn.close()


@app.get("/api/search")
def api_search(q: str = "", page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    return api_articles(q=q, page=page, page_size=page_size)


# ------------------------------------------------------------------- pages ---
@app.get("/", response_class=HTMLResponse)
def page_home(request: Request):
    conn = _conn()
    try:
        stats = db.dashboard_stats(conn)
        recent, _ = db.list_articles(conn, limit=10)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "home.html", {"active": "home", "stats": stats, "recent": recent}
    )


@app.get("/articles", response_class=HTMLResponse)
def page_articles(
    request: Request,
    q: str = "", source: str = "", category: str = "", language: str = "",
    date_from: str = "", date_to: str = "",
    sort: str = "collected_at", order: str = "desc", page: int = Query(1, ge=1),
):
    page_size = 25
    conn = _conn()
    try:
        rows, total = db.list_articles(
            conn, q=q, source=source, category=category, language=language,
            date_from=date_from, date_to=date_to, sort=sort, order=order,
            limit=page_size, offset=(page - 1) * page_size,
        )
        sources = db.list_sources(conn)
        cats = list(db.dashboard_stats(conn)["by_category"].keys())
    finally:
        conn.close()
    pages = max(1, math.ceil(total / page_size))
    return templates.TemplateResponse(request, "articles.html", {
        "active": "articles", "rows": rows, "total": total,
        "page": page, "pages": pages, "sources": sources, "cats": cats,
        "f": {"q": q, "source": source, "category": category, "language": language,
              "date_from": date_from, "date_to": date_to, "sort": sort, "order": order},
    })


@app.get("/article/{article_id}", response_class=HTMLResponse)
def page_article(request: Request, article_id: int):
    conn = _conn()
    try:
        art = db.get_article(conn, article_id)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "article.html", {"active": "articles", "a": art}
    )


@app.get("/sources", response_class=HTMLResponse)
def page_sources(request: Request):
    conn = _conn()
    try:
        sources = db.list_sources(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "sources.html", {"active": "sources", "sources": sources}
    )


@app.get("/analytics", response_class=HTMLResponse)
def page_analytics(request: Request):
    return templates.TemplateResponse(request, "analytics.html", {"active": "analytics"})


@app.get("/logs", response_class=HTMLResponse)
def page_logs(request: Request):
    conn = _conn()
    try:
        logs = db.list_logs(conn, 150)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "logs.html", {"active": "logs", "logs": logs}
    )
