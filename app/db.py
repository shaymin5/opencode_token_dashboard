"""Read-only SQLite query functions for OpenCode token data.

All functions receive an open sqlite3.Connection.
Every connection must have PRAGMA query_only = 1 set at open time.
"""

from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# Asia/Shanghai timezone (UTC+8, no DST)
SHANGHAI = ZoneInfo("Asia/Shanghai")

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_db_path() -> str:
    """Resolve the opencode.db path.

    Priority:
    1. OPCODE_DB_PATH environment variable
    2. %LOCALAPPDATA%/../.local/share/opencode/opencode.db  (Windows)
    3. ~/.local/share/opencode/opencode.db                   (Unix / explicit)
    """
    env = os.environ.get("OPCODE_DB_PATH")
    if env:
        return env

    # Windows: LOCALAPPDATA is typically <user>\AppData\Local
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = (
            Path(local_app_data).parent / ".local" / "share" / "opencode" / "opencode.db"
        )
        if candidate.exists():
            return str(candidate.resolve())

    # Fallback: ~/.local/share/opencode/opencode.db
    home = Path.home()
    candidate = home / ".local" / "share" / "opencode" / "opencode.db"
    if candidate.exists():
        return str(candidate.resolve())

    # Last resort: the well-known Windows absolute path
    return r"C:\Users\Shaymin\.local\share\opencode\opencode.db"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a read-only connection to opencode.db.

    Sets PRAGMA query_only = 1 to prevent accidental writes.
    """
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = 1")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _r(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _tokens(data_alias: str = "data") -> str:
    """Return a SQL snippet that extracts the tokens sub-object.

    ``data_alias`` is the table alias or sub-query column that holds
    the JSON blob (e.g. ``m.data`` or just ``data``).
    """
    d = data_alias
    return f"""
        COALESCE(CAST(json_extract({d}, '$.tokens.input'       ) AS INTEGER), 0),
        COALESCE(CAST(json_extract({d}, '$.tokens.output'      ) AS INTEGER), 0),
        COALESCE(CAST(json_extract({d}, '$.tokens.reasoning'   ) AS INTEGER), 0),
        COALESCE(CAST(json_extract({d}, '$.tokens.cache.read'  ) AS INTEGER), 0),
        COALESCE(CAST(json_extract({d}, '$.tokens.cache.write' ) AS INTEGER), 0)
    """


def _filter_token_messages(data_alias: str = "data") -> tuple[str, list]:
    """Return a SQL WHERE clause fragment that filters to token-bearing messages.

    Uses ``json_extract(data, '$.tokens.input') IS NOT NULL`` (token presence)
    rather than ``role = 'assistant'`` — defensive against future schema changes.

    Returns ``("WHERE json_extract(..., '$.tokens.input') IS NOT NULL", [])``.
    """
    d = data_alias
    return (f"WHERE json_extract({d}, '$.tokens.input') IS NOT NULL", [])


def _coalesce_model(data_alias: str = "data") -> str:
    """Return SQL snippet that coalesces both flat and nested model fields.

    Handles the JSON structure inconsistency where assistant messages use
    flat ``$.modelID`` but user messages use nested ``$.model.modelID``.
    """
    d = data_alias
    return f"COALESCE(json_extract({d}, '$.model.modelID'), json_extract({d}, '$.modelID'))"


def _coalesce_provider(data_alias: str = "data") -> str:
    """Return SQL snippet that coalesces both flat and nested provider fields."""
    d = data_alias
    return f"COALESCE(json_extract({d}, '$.model.providerID'), json_extract({d}, '$.providerID'))"


DIV_ZERO_GUARD = """
    CASE WHEN denominator > 0
    THEN CAST(numerator AS REAL) / denominator
    ELSE NULL
    END
"""


# ---------------------------------------------------------------------------
# Date filter helpers
# ---------------------------------------------------------------------------


def _iso_date_to_ms(date_str: str, end_of_day: bool = False) -> int:
    """Convert ISO date ``YYYY-MM-DD`` to milliseconds since Unix epoch.

    When ``end_of_day`` is ``True``, returns the timestamp for
    23:59:59.999999 Asia/Shanghai (inclusive upper bound for a day).
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=SHANGHAI)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return int(dt.timestamp() * 1000)


def _build_date_filter(
    start_date: str | None = None,
    end_date: str | None = None,
    col: str = "time_created",
) -> tuple[str, list[int]]:
    """Build a SQL WHERE clause fragment + params for date filtering.

    Returns ``("", [])`` when both dates are ``None``.

    The clause references the given *col* (default ``time_created``).
    ``start_date`` is inclusive from 00:00:00.000;
    ``end_date`` is inclusive through 23:59:59.999.
    """
    clauses: list[str] = []
    params: list[int] = []
    if start_date:
        clauses.append(f"{col} >= ?")
        params.append(_iso_date_to_ms(start_date))
    if end_date:
        clauses.append(f"{col} <= ?")
        params.append(_iso_date_to_ms(end_date, end_of_day=True))
    if not clauses:
        return ("", [])
    return (" AND ".join(clauses), params)


# ---------------------------------------------------------------------------
# 1. Overview stats
# ---------------------------------------------------------------------------

def get_overview_stats(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Return dashboard-level aggregate stats, optionally filtered by date range."""
    date_clause, date_params = _build_date_filter(start_date, end_date)
    sql = f"""
        SELECT
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0)
            AS total_tokens,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0) AS total_input_tokens,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0) AS total_output_tokens,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0) AS total_reasoning_tokens,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0) AS total_cache_read_tokens,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0) AS total_cache_write_tokens,
            COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0) AS total_cost,
            COUNT(DISTINCT session_id) AS total_sessions,
            COUNT(*) AS total_messages,
            COUNT(*) FILTER (WHERE CAST(json_extract(data, '$.cost') AS REAL) > 0) AS paid_messages
        FROM message
        {('WHERE ' + date_clause) if date_clause else ''}
    """
    row = conn.execute(sql, date_params).fetchone()
    return dict(row)


# ---------------------------------------------------------------------------
# 2. Tokens by date
# ---------------------------------------------------------------------------

def get_tokens_by_date(
    conn: sqlite3.Connection,
    granularity: str = "day",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Token usage aggregated by time period, optionally filtered by date range.

    Supported granularities: ``day``, ``week``, ``month``.

    **Important**: ``time_created`` is stored as milliseconds — we divide by
    1000 before passing to ``datetime()``.
    """
    fmt_map = {
        "day": "%Y-%m-%d",
        "week": "%Y-%W",
        "month": "%Y-%m",
    }
    fmt = fmt_map.get(granularity, "%Y-%m-%d")
    date_clause, date_params = _build_date_filter(start_date, end_date)

    sql = f"""
        SELECT
            strftime('{fmt}', datetime(time_created / 1000, 'unixepoch', '+8 hours')) AS date,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0) AS input,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0) AS output,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0) AS reasoning,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0) AS cache_read,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0) AS cache_write
        FROM message
        WHERE json_extract(data, '$.tokens.input') IS NOT NULL
        {('AND ' + date_clause) if date_clause else ''}
        GROUP BY date
        ORDER BY date ASC
    """
    rows = conn.execute(sql, date_params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["total"] = d["input"] + d["output"] + d["reasoning"] + d["cache_read"] + d["cache_write"]
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# 3. Tokens by model
# ---------------------------------------------------------------------------

def get_tokens_by_model(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Token usage aggregated by model + provider, optionally filtered by date range."""
    date_clause, date_params = _build_date_filter(start_date, end_date)
    sql = f"""
        SELECT
            COALESCE(json_extract(data, '$.modelID'),   'unknown')   AS model,
            COALESCE(json_extract(data, '$.providerID'), 'unknown')  AS provider,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0) AS input,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0) AS output,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0) AS reasoning,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0) AS cache_read,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0) AS cache_write,
            COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0) AS cost,
            COUNT(*) AS message_count
        FROM message
        {('WHERE ' + date_clause) if date_clause else ''}
        GROUP BY model, provider
        ORDER BY
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.output') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0)
            DESC
    """
    return [dict(r) for r in conn.execute(sql, date_params).fetchall()]


# ---------------------------------------------------------------------------
# 4. Tokens by project
# ---------------------------------------------------------------------------

def _project_name_from_worktree(worktree: str | None) -> str:
    """Derive a human-readable project name from the worktree path.

    ``project.name`` is always NULL in the DB, so we use the basename
    of the worktree path instead.
    """
    if not worktree or worktree == "/":
        return "Global"
    return os.path.basename(worktree.rstrip("/\\")) or "Unknown"


def get_tokens_by_project(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Token usage aggregated by project, optionally filtered by date range.

    ``project.name`` is always NULL in the DB — we derive the project name
    from the ``worktree`` path basename via :func:`_project_name_from_worktree`.
    """
    date_clause, date_params = _build_date_filter(start_date, end_date, col="m.time_created")
    sql = f"""
        SELECT
            p.worktree,
            COALESCE(p.name, '') AS name,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.input')       AS INTEGER)), 0) AS input,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.output')      AS INTEGER)), 0) AS output,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.reasoning')   AS INTEGER)), 0) AS reasoning,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.read')  AS INTEGER)), 0) AS cache_read,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.write') AS INTEGER)), 0) AS cache_write,
            COALESCE(SUM(CAST(json_extract(m.data, '$.cost') AS REAL)), 0) AS cost,
            COUNT(DISTINCT s.id) AS session_count
        FROM message m
        JOIN session s ON s.id = m.session_id
        JOIN project p ON p.id = s.project_id
        {('WHERE ' + date_clause) if date_clause else ''}
        GROUP BY p.id
        ORDER BY
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.input') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.output') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.reasoning') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.read') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.write') AS INTEGER)), 0)
            DESC
    """
    rows = conn.execute(sql, date_params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["project"] = _project_name_from_worktree(d.pop("worktree"))
        d.pop("name", None)
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# 5. Cost breakdown
# ---------------------------------------------------------------------------

def get_cost_breakdown(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Cost aggregated by model + provider, sorted by cost descending.
    Optionally filtered by date range.  Token count is computed inline
    in a single query (no N+1).
    """
    date_clause, date_params = _build_date_filter(start_date, end_date)
    sql = f"""
        SELECT
            COALESCE(json_extract(data, '$.modelID'),   'unknown')  AS model,
            COALESCE(json_extract(data, '$.providerID'), 'unknown') AS provider,
            COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0) AS cost,
            COUNT(*) AS message_count,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0)
            AS token_count
        FROM message
        {('WHERE ' + date_clause) if date_clause else ''}
        GROUP BY model, provider
        ORDER BY cost DESC
    """
    return [dict(r) for r in conn.execute(sql, date_params).fetchall()]


# ---------------------------------------------------------------------------
# 6–10. Placeholder stubs (implementations added in Tasks 5–9)
# ---------------------------------------------------------------------------


def get_agent_breakdown(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Token usage aggregated by agent, sorted by total_tokens descending.

    Messages without an ``agent`` field in JSON data are coalesced to
    ``'unknown'``.  Messages with NULL token fields are excluded from
    aggregation (they contribute nothing).
    """
    date_clause, date_params = _build_date_filter(start_date, end_date)
    sql = f"""
        SELECT
            COALESCE(json_extract(data, '$.agent'), 'unknown') AS agent,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0)
            AS total_tokens,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0) AS input,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0) AS output,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0) AS reasoning,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0) AS cache_read,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0) AS cache_write,
            COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0) AS cost,
            COUNT(*) AS message_count
        FROM message
        WHERE json_extract(data, '$.tokens.input') IS NOT NULL
        {('AND ' + date_clause) if date_clause else ''}
        GROUP BY agent
        ORDER BY total_tokens DESC
    """
    return [dict(r) for r in conn.execute(sql, date_params).fetchall()]


def get_model_efficiency(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Compute per-model efficiency metrics: cost/1K tokens, I/O ratio, cache hit ratio.

    Returns a list of dicts with keys:
        model, provider, total_tokens, total_cost, cost_per_1k_tokens,
        input_output_ratio, cache_hit_ratio, message_count
    """
    date_clause, date_params = _build_date_filter(start_date, end_date)
    sql = f"""
        SELECT
            {_coalesce_model()} AS model,
            {_coalesce_provider()} AS provider,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0)
            AS total_tokens,
            COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0) AS total_cost,
            CASE WHEN COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0) > 0
                 AND SUM(CAST(json_extract(data, '$.tokens.input') AS INTEGER))
                 + SUM(CAST(json_extract(data, '$.tokens.output') AS INTEGER)) > 0
            THEN (COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0) * 1000.0)
                 / (SUM(CAST(json_extract(data, '$.tokens.input') AS INTEGER))
                    + SUM(CAST(json_extract(data, '$.tokens.output') AS INTEGER)))
            ELSE NULL
            END AS cost_per_1k_tokens,
            CASE WHEN SUM(CAST(json_extract(data, '$.tokens.output') AS INTEGER)) > 0
            THEN CAST(SUM(CAST(json_extract(data, '$.tokens.input') AS INTEGER)) AS REAL)
                 / SUM(CAST(json_extract(data, '$.tokens.output') AS INTEGER))
            ELSE NULL
            END AS input_output_ratio,
            CASE WHEN SUM(CAST(json_extract(data, '$.tokens.cache.read') AS INTEGER))
                 + SUM(CAST(json_extract(data, '$.tokens.input') AS INTEGER)) > 0
            THEN CAST(SUM(CAST(json_extract(data, '$.tokens.cache.read') AS INTEGER)) AS REAL)
                 / (SUM(CAST(json_extract(data, '$.tokens.cache.read') AS INTEGER))
                    + SUM(CAST(json_extract(data, '$.tokens.input') AS INTEGER)))
            ELSE NULL
            END AS cache_hit_ratio,
            COUNT(*) AS message_count
        FROM message
        WHERE json_extract(data, '$.tokens.input') IS NOT NULL
        {('AND ' + date_clause) if date_clause else ''}
        GROUP BY model, provider
        ORDER BY total_tokens DESC
    """
    return [dict(r) for r in conn.execute(sql, date_params).fetchall()]


def get_usage_heatmap(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Return message count and token volume by day-of-week x hour (Asia/Shanghai).

    Returns flat rows with day_of_week (string '0'-'6', Sunday=0),
    hour (string '00'-'23'), message_count, total_tokens.
    Frontend pivots to 7x24 heatmap grid.
    """
    date_clause, date_params = _build_date_filter(start_date, end_date)
    sql = f"""
        SELECT
            strftime('%w', datetime(time_created / 1000, 'unixepoch', '+8 hours')) AS day_of_week,
            strftime('%H', datetime(time_created / 1000, 'unixepoch', '+8 hours')) AS hour,
            COUNT(*) AS message_count,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0)
            AS total_tokens,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0) AS input,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0) AS output,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0) AS reasoning,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0) AS cache_read,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0) AS cache_write,
            COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0) AS cost
        FROM message
        WHERE json_extract(data, '$.tokens.input') IS NOT NULL
        {('AND ' + date_clause) if date_clause else ''}
        GROUP BY day_of_week, hour
        ORDER BY day_of_week, hour
    """
    return [dict(r) for r in conn.execute(sql, date_params).fetchall()]


def get_top_sessions(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return top N sessions by total token consumption.

    JOINs message → session → project. Derives project name from worktree.
    """
    date_clause, date_params = _build_date_filter(start_date, end_date, col="m.time_created")
    sql = f"""
        SELECT
            s.id,
            s.title,
            s.time_created,
            p.worktree,
            COUNT(*) AS message_count,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.input')       AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.output')      AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.reasoning')   AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.read')  AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.write') AS INTEGER)), 0)
            AS total_tokens,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.input')       AS INTEGER)), 0) AS input,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.output')      AS INTEGER)), 0) AS output,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.reasoning')   AS INTEGER)), 0) AS reasoning,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.read')  AS INTEGER)), 0) AS cache_read,
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.write') AS INTEGER)), 0) AS cache_write,
            COALESCE(SUM(CAST(json_extract(m.data, '$.cost') AS REAL)), 0) AS total_cost
        FROM message m
        JOIN session s ON s.id = m.session_id
        JOIN project p ON p.id = s.project_id
        WHERE json_extract(m.data, '$.tokens.input') IS NOT NULL
        {('AND ' + date_clause) if date_clause else ''}
        GROUP BY s.id
        ORDER BY total_tokens DESC
        LIMIT ?
    """
    params: list[Any] = date_params + [limit]
    rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["project"] = _project_name_from_worktree(d.pop("worktree"))
        d.pop("name", None)  # project.name is always NULL
        result.append(d)
    return result


def get_cache_efficiency(
    conn: sqlite3.Connection,
    granularity: str = "day",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Return cache efficiency time-series aggregated by granularity.
    
    Supported granularities: ``day``, ``week``, ``month``.
    Computes cache_hit_ratio = cache_read / (cache_read + input) per period.
    Returns NULL when both cache_read and input are 0.
    Sorted by date ascending.
    """
    fmt_map = {
        "day": "%Y-%m-%d",
        "week": "%Y-%W",
        "month": "%Y-%m",
    }
    fmt = fmt_map.get(granularity, "%Y-%m-%d")
    date_clause, date_params = _build_date_filter(start_date, end_date)
    sql = f"""
        SELECT
            strftime('{fmt}', datetime(time_created / 1000, 'unixepoch', '+8 hours')) AS date,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0) AS cache_read,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0) AS cache_write,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0) AS input,
            CASE WHEN COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read') AS INTEGER)), 0)
                 + COALESCE(SUM(CAST(json_extract(data, '$.tokens.input') AS INTEGER)), 0) > 0
            THEN CAST(COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read') AS INTEGER)), 0) AS REAL)
                 / (COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read') AS INTEGER)), 0)
                    + COALESCE(SUM(CAST(json_extract(data, '$.tokens.input') AS INTEGER)), 0))
            ELSE NULL
            END AS cache_hit_ratio
        FROM message
        WHERE json_extract(data, '$.tokens.input') IS NOT NULL
        {('AND ' + date_clause) if date_clause else ''}
        GROUP BY date
        ORDER BY date ASC
    """
    return [dict(r) for r in conn.execute(sql, date_params).fetchall()]


# ---------------------------------------------------------------------------
# 11. Consolidated data (all views in one call)
# ---------------------------------------------------------------------------


def get_all_data(
    conn: sqlite3.Connection,
    granularity: str = "day",
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Run all 10 dashboard queries in PARALLEL and return a consolidated
    dict keyed by snake_case view name.

    Extracts the DB path from *conn*, then spawns thread-local connections
    so all queries execute concurrently (SQLite WAL mode supports concurrent
    reads).  This cuts total response time from the sum of query times to
    approximately the *max* query time.
    """
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]

    def _query(func, *args, **kw):
        """Open a fresh read-only connection and run *func* against it."""
        c = sqlite3.connect(db_path, uri=True)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA query_only = 1")
        try:
            return func(c, *args, **kw)
        finally:
            c.close()

    kwargs = {"start_date": start_date, "end_date": end_date}

    with ThreadPoolExecutor(max_workers=8) as pool:
        fut: dict[str, Any] = {}
        fut["overview"] = pool.submit(_query, get_overview_stats, **kwargs)
        fut["tokens_by_date"] = pool.submit(_query, get_tokens_by_date, granularity, **kwargs)
        fut["tokens_by_model"] = pool.submit(_query, get_tokens_by_model, **kwargs)
        fut["tokens_by_project"] = pool.submit(_query, get_tokens_by_project, **kwargs)
        fut["cost_breakdown"] = pool.submit(_query, get_cost_breakdown, **kwargs)
        fut["agent_breakdown"] = pool.submit(_query, get_agent_breakdown, **kwargs)
        fut["model_efficiency"] = pool.submit(_query, get_model_efficiency, **kwargs)
        fut["usage_heatmap"] = pool.submit(_query, get_usage_heatmap, **kwargs)
        fut["top_sessions"] = pool.submit(_query, get_top_sessions, limit=limit, **kwargs)
        fut["cache_efficiency"] = pool.submit(_query, get_cache_efficiency, granularity, **kwargs)
        return {k: f.result() for k, f in fut.items()}
