"""FastAPI router for OpenCode Token Dashboard.

Provides 5 JSON API endpoints and one HTML endpoint (index).
All DB connections are read-only and scoped per request.
"""

from collections.abc import Iterator
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from jinja2 import Environment, FileSystemLoader
from sqlite3 import Connection

from app.db import (
    get_all_data,
    get_connection,
    get_db_path,
    get_overview_stats,
    get_tokens_by_date,
    get_tokens_by_model,
    get_tokens_by_project,
    get_cost_breakdown,
    get_agent_breakdown,
    get_model_efficiency,
    get_usage_heatmap,
    get_top_sessions,
    get_cache_efficiency,
)

ViewName = Literal[
    "overview", "tokens-by-date", "tokens-by-model", "tokens-by-project",
    "cost-breakdown", "agent-breakdown", "model-efficiency", "usage-heatmap",
    "top-sessions", "cache-efficiency", "all",
]

VIEW_DISPATCH: dict[str, str] = {
    "all": "get_all_data",
    "overview": "get_overview_stats",
    "tokens-by-date": "get_tokens_by_date",
    "tokens-by-model": "get_tokens_by_model",
    "tokens-by-project": "get_tokens_by_project",
    "cost-breakdown": "get_cost_breakdown",
    "agent-breakdown": "get_agent_breakdown",
    "model-efficiency": "get_model_efficiency",
    "usage-heatmap": "get_usage_heatmap",
    "top-sessions": "get_top_sessions",
    "cache-efficiency": "get_cache_efficiency",
}

router = APIRouter()

# Use raw Jinja2 instead of Starlette's Jinja2Templates to avoid
# cache-key compatibility issues with Jinja2 3.1.x + Starlette.
_jinja_env = Environment(
    loader=FileSystemLoader("app/templates"),
    auto_reload=False,
    enable_async=False,
)
_jinja_template = _jinja_env.get_template("index.html")


# ---------------------------------------------------------------------------
# Dependency — per-request read-only DB connection
# ---------------------------------------------------------------------------
def get_db() -> Iterator[Connection]:
    """Yield a read-only SQLite connection, closed when the request ends."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------
@router.get("/")
async def index(request: Request):
    """Render the main dashboard page."""
    html = _jinja_template.render({"db_path": get_db_path()})
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Favicon
# ---------------------------------------------------------------------------
@router.get("/favicon.ico")
async def favicon():
    """Serve the SVG favicon."""
    import os
    svg_path = os.path.join(os.path.dirname(__file__), "static", "favicon.svg")
    try:
        with open(svg_path, "rb") as f:
            return Response(content=f.read(), media_type="image/svg+xml")
    except FileNotFoundError:
        return Response(status_code=204)


# ---------------------------------------------------------------------------
# JSON API endpoints — unified dispatch
# ---------------------------------------------------------------------------
@router.get("/api/data")
async def api_data(
    view: str | None = Query(None, description="Data view name"),
    granularity: str = Query("day", description="Aggregation period: day, week, or month"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(10, description="Maximum results (for top-sessions view)"),
    conn: Connection = Depends(get_db),
):
    """Unified data endpoint. Dispatch based on `view` parameter."""
    if view is None:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing required 'view' query parameter"},
        )
    if view not in VIEW_DISPATCH:
        valid = list(VIEW_DISPATCH.keys())
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown view '{view}'. Valid views: {valid}"},
        )

    func_name = VIEW_DISPATCH[view]
    func = globals().get(func_name)
    if func is None:
        return JSONResponse(
            status_code=500,
            content={"error": f"Query function '{func_name}' not found"},
        )

    try:
        if view == "all":
            return func(conn, granularity=granularity, start_date=start_date, end_date=end_date, limit=limit)
        elif view == "tokens-by-date":
            return func(conn, granularity=granularity, start_date=start_date, end_date=end_date)
        elif view == "top-sessions":
            return func(conn, start_date=start_date, end_date=end_date, limit=limit)
        elif view == "cache-efficiency":
            return func(conn, granularity=granularity, start_date=start_date, end_date=end_date)
        else:
            return func(conn, start_date=start_date, end_date=end_date)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to fetch {view}: {exc}"},
        )


# ---------------------------------------------------------------------------
# Backward-compatible 307 redirects
# ---------------------------------------------------------------------------
@router.get("/api/overview")
async def api_overview_redirect(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    url = "/api/data?view=overview"
    if start_date:
        url += f"&start_date={start_date}"
    if end_date:
        url += f"&end_date={end_date}"
    return RedirectResponse(url=url, status_code=307)


@router.get("/api/tokens-by-date")
async def api_tokens_by_date_redirect(
    granularity: str = Query("day"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    url = f"/api/data?view=tokens-by-date&granularity={granularity}"
    if start_date:
        url += f"&start_date={start_date}"
    if end_date:
        url += f"&end_date={end_date}"
    return RedirectResponse(url=url, status_code=307)


@router.get("/api/tokens-by-model")
async def api_tokens_by_model_redirect(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    url = "/api/data?view=tokens-by-model"
    if start_date:
        url += f"&start_date={start_date}"
    if end_date:
        url += f"&end_date={end_date}"
    return RedirectResponse(url=url, status_code=307)


@router.get("/api/tokens-by-project")
async def api_tokens_by_project_redirect(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    url = "/api/data?view=tokens-by-project"
    if start_date:
        url += f"&start_date={start_date}"
    if end_date:
        url += f"&end_date={end_date}"
    return RedirectResponse(url=url, status_code=307)


@router.get("/api/cost-breakdown")
async def api_cost_breakdown_redirect(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    url = "/api/data?view=cost-breakdown"
    if start_date:
        url += f"&start_date={start_date}"
    if end_date:
        url += f"&end_date={end_date}"
    return RedirectResponse(url=url, status_code=307)
