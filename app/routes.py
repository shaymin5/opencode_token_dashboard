"""FastAPI router for OpenCode Token Dashboard.

Provides 5 JSON API endpoints and one HTML endpoint (index).
All DB connections are read-only and scoped per request.
"""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader
from sqlite3 import Connection

from app.db import (
    get_connection,
    get_db_path,
    get_overview_stats,
    get_tokens_by_date,
    get_tokens_by_model,
    get_tokens_by_project,
    get_cost_breakdown,
)

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
# JSON API endpoints
# ---------------------------------------------------------------------------
@router.get("/api/overview")
async def api_overview(conn: Connection = Depends(get_db)):
    """Aggregate overview statistics."""
    try:
        return get_overview_stats(conn)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to fetch overview stats: {exc}"},
        )


@router.get("/api/tokens-by-date")
async def api_tokens_by_date(
    granularity: str = Query("day", description="Aggregation period: day, week, or month"),
    conn: Connection = Depends(get_db),
):
    """Token usage aggregated by time period."""
    try:
        return get_tokens_by_date(conn, granularity=granularity)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to fetch tokens by date: {exc}"},
        )


@router.get("/api/tokens-by-model")
async def api_tokens_by_model(conn: Connection = Depends(get_db)):
    """Token usage aggregated by model + provider."""
    try:
        return get_tokens_by_model(conn)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to fetch tokens by model: {exc}"},
        )


@router.get("/api/tokens-by-project")
async def api_tokens_by_project(conn: Connection = Depends(get_db)):
    """Token usage aggregated by project."""
    try:
        return get_tokens_by_project(conn)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to fetch tokens by project: {exc}"},
        )


@router.get("/api/cost-breakdown")
async def api_cost_breakdown(conn: Connection = Depends(get_db)):
    """Cost breakdown aggregated by model + provider."""
    try:
        return get_cost_breakdown(conn)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to fetch cost breakdown: {exc}"},
        )
