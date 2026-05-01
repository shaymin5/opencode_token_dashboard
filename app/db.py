"""Read-only SQLite query functions for OpenCode token data.

All functions receive an open sqlite3.Connection.
Every connection must have PRAGMA query_only = 1 set at open time.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any


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


# ---------------------------------------------------------------------------
# 1. Overview stats
# ---------------------------------------------------------------------------

def get_overview_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return dashboard-level aggregate stats."""
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
    """
    row = conn.execute(sql).fetchone()
    return dict(row)


# ---------------------------------------------------------------------------
# 2. Tokens by date
# ---------------------------------------------------------------------------

def get_tokens_by_date(
    conn: sqlite3.Connection, granularity: str = "day"
) -> list[dict[str, Any]]:
    """Token usage aggregated by time period.

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

    sql = f"""
        SELECT
            strftime('{fmt}', datetime(time_created / 1000, 'unixepoch')) AS date,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0) AS input,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0) AS output,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0) AS reasoning,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0) AS cache_read,
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0) AS cache_write
        FROM message
        WHERE json_extract(data, '$.tokens.input') IS NOT NULL
        GROUP BY date
        ORDER BY date ASC
    """
    rows = conn.execute(sql).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["total"] = d["input"] + d["output"] + d["reasoning"] + d["cache_read"] + d["cache_write"]
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# 3. Tokens by model
# ---------------------------------------------------------------------------

def get_tokens_by_model(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Token usage aggregated by model + provider."""
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
        GROUP BY model, provider
        ORDER BY
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.output') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0)
            DESC
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


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


def get_tokens_by_project(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Token usage aggregated by project.

    ``project.name`` is always NULL in the DB — we derive the project name
    from the ``worktree`` path basename via :func:`_project_name_from_worktree`.
    """
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
        GROUP BY p.id
        ORDER BY
            COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.input') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.output') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.reasoning') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.read') AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(m.data, '$.tokens.cache.write') AS INTEGER)), 0)
            DESC
    """
    rows = conn.execute(sql).fetchall()
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

def get_cost_breakdown(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Cost aggregated by model + provider, sorted by cost descending."""
    sql = """
        SELECT
            COALESCE(json_extract(data, '$.modelID'),   'unknown')  AS model,
            COALESCE(json_extract(data, '$.providerID'), 'unknown') AS provider,
            COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0) AS cost,
            COUNT(*) AS message_count
        FROM message
        GROUP BY model, provider
        ORDER BY cost DESC
    """
    rows = conn.execute(sql).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["token_count"] = _get_model_token_count(conn, d["model"], d["provider"])
        result.append(d)
    return result


def _get_model_token_count(
    conn: sqlite3.Connection, model: str, provider: str
) -> int:
    """Return total tokens for a given model + provider pair."""
    sql = """
        SELECT
            COALESCE(SUM(CAST(json_extract(data, '$.tokens.input')       AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.output')      AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.reasoning')   AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.read')  AS INTEGER)), 0)
            + COALESCE(SUM(CAST(json_extract(data, '$.tokens.cache.write') AS INTEGER)), 0)
            AS token_count
        FROM message
        WHERE json_extract(data, '$.modelID') = ?
          AND json_extract(data, '$.providerID') = ?
    """
    row = conn.execute(sql, (model, provider)).fetchone()
    return row["token_count"] if row else 0
