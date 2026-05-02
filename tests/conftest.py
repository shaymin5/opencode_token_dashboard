"""pytest fixtures for testing opencode token dashboard queries.

All IDs are TEXT (matching the real database).  ``time_created`` is in
milliseconds (Unix epoch * 1000).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create the three tables matching the real opencode.db schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS project (
            id          TEXT PRIMARY KEY,
            name        TEXT,
            worktree    TEXT
        );

        CREATE TABLE IF NOT EXISTS session (
            id              TEXT PRIMARY KEY,
            project_id      TEXT REFERENCES project(id),
            title           TEXT,
            time_created    INTEGER,
            parent_id       TEXT,
            version         INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS message (
            id                TEXT PRIMARY KEY,
            session_id        TEXT REFERENCES session(id),
            data              TEXT,
            time_created      INTEGER,
            time_updated      INTEGER,
            idempotency_key   TEXT
        );

        /* Convenience index for time-based queries */
        CREATE INDEX IF NOT EXISTS idx_message_time
            ON message(session_id, time_created, id);
    """)


def _insert_fixture_data(conn: sqlite3.Connection) -> None:
    """Insert representative sample data covering edge cases.

    Projects:
      p1 — D:\\gameboy\\project-navigator   (normal)
      p2 — D:\\gameboy\\volume_balance      (normal)
      p3 — /                                 (global)
      p4 — NULL worktree                      (unknown)

    Sessions: 4 per project p1, 2 per others (10 total)
    Messages: ~21 total
    """
    import json  # noqa: F811 — needed for json.dumps in custom messages below

    # ── Projects ────────────────────────────────────────────────
    projects = [
        ("p1", None, r"D:\gameboy\project-navigator"),
        ("p2", None, r"D:\gameboy\volume_balance"),
        ("p3", None, "/"),
        ("p4", None, None),
    ]
    conn.executemany(
        "INSERT INTO project (id, name, worktree) VALUES (?, ?, ?)",
        projects,
    )

    # ── Sessions ────────────────────────────────────────────────
    sessions = [
        ("ses_a1", "p1", "Session 1-A", 1769941466263, None, 1),   # 2026-02-01
        ("ses_a2", "p1", "Session 1-B", 1769941467000, None, 1),
        ("ses_a3", "p1", "Session 1-C with parent", 1769941480000, "ses_a1", 2),
        ("ses_a4", "p1", "Session 1-D standalone", 1769941490000, None, 1),
        ("ses_b1", "p2", "Session 2-A", 1772619866263, None, 1),   # 2026-03-01
        ("ses_b2", "p2", "Session 2-B", 1772706266263, None, 1),
        ("ses_c1", "p3", "Global Session", 1775211866263, None, 1), # 2026-04-01
        ("ses_c2", "p3", "Global Session 2", 1775298266263, None, 1),
        ("ses_d1", "p4", "Unknown Session", 1777883866263, None, 1), # 2026-05-01
        ("ses_d2", "p4", "Unknown Session 2", 1777970266263, None, 1),
    ]
    conn.executemany(
        "INSERT INTO session (id, project_id, title, time_created, parent_id, version) VALUES (?, ?, ?, ?, ?, ?)",
        sessions,
    )

    # ── Messages ────────────────────────────────────────────────
    # Helper to build JSON data blob
    def msg_data(
        model: str = "deepseek-v4-flash",
        provider: str = "opencode-go",
        role: str = "assistant",
        mode: str = "build",
        agent: str = "build",
        cost: float = 0.0,
        inp: int = 100,
        out: int = 50,
        reason: int = 10,
        cache_r: int = 500,
        cache_w: int = 50,
    ) -> str:
        import json as _json

        d = {
            "modelID": model,
            "providerID": provider,
            "role": role,
            "mode": mode,
            "agent": agent,
            "cost": cost,
            "tokens": {
                "input": inp,
                "output": out,
                "reasoning": reason,
                "cache": {"read": cache_r, "write": cache_w},
            },
        }
        return _json.dumps(d)

    messages = [
        # Project p1 — project-navigator
        ("m1",  "ses_a1", msg_data(inp=1000, out=500,  reason=100,  cache_r=5000,  cache_w=500,  cost=0.05), 1769941466263),
        ("m2",  "ses_a1", msg_data(inp=2000, out=800,  reason=200,  cache_r=8000,  cache_w=600,  cost=0.08), 1769941467000),
        ("m3",  "ses_a2", msg_data(inp=500,  out=300,  reason=0,    cache_r=2000,  cache_w=100,  cost=0.02), 1769941470000),
        # Project p2 — volume_balance
        ("m4",  "ses_b1", msg_data(inp=3000, out=1200, reason=300,  cache_r=10000, cache_w=1000, cost=0.12, model="MiniMax-M2.7", provider="minimax-cn"), 1772619866263),
        ("m5",  "ses_b1", msg_data(inp=1500, out=600,  reason=50,   cache_r=6000,  cache_w=400,  cost=0.06, model="MiniMax-M2.7", provider="minimax-cn"), 1772619870000),
        ("m6",  "ses_b2", msg_data(inp=800,  out=400,  reason=0,    cache_r=3000,  cache_w=200,  cost=0.03, model="glm-4.7",     provider="zai"), 1772706266263),
        # Project p3 — Global (/)
        ("m7",  "ses_c1", msg_data(inp=200,  out=100,  reason=0,    cache_r=1000,  cache_w=0,    cost=0.0,  model="gpt-5-nano", provider="opencode"), 1775211866263),
        ("m8",  "ses_c1", msg_data(inp=300,  out=150,  reason=20,   cache_r=1500,  cache_w=0,    cost=0.0,  model="gpt-5-nano", provider="opencode"), 1775211867000),
        ("m9",  "ses_c2", msg_data(inp=100,  out=50,   reason=0,    cache_r=500,   cache_w=0,    cost=0.0,  model="gpt-5-nano", provider="opencode"), 1775298266263),
        # Project p4 — NULL worktree
        ("m10", "ses_d1", msg_data(inp=50,   out=20,   reason=0,    cache_r=200,   cache_w=50,   cost=0.0,  model="mimo-v2-pro-free", provider="opencode"), 1777883866263),
        ("m11", "ses_d1", msg_data(inp=70,   out=30,   reason=0,    cache_r=300,   cache_w=80,   cost=0.0,  model="mimo-v2-pro-free", provider="opencode"), 1777883867000),
        # Edge case: NULL tokens fields (missing entirely)
        ("m12", "ses_d2", '{"modelID":"test","providerID":"test","cost":0,"tokens":{"input":null,"output":null,"cache":{"read":null}}}', 1777970266263),
        # Edge case: very high cost
        ("m13", "ses_a2", msg_data(inp=10000, out=5000, reason=1000, cache_r=50000, cache_w=5000, cost=0.50, model="deepseek-v4-pro", provider="opencode-go"), 1769941475000),
        # ── New fixture data: edge cases and varied structures ──
        # m14 — Nested model JSON (user-message style with $.model.modelID / $.model.providerID)
        ("m14", "ses_a1", json.dumps({
            "model": {"modelID": "nested-model-v1", "providerID": "nested-provider"},
            "role": "user",
            "mode": "explore",
            "agent": "explore",
            "cost": 0.01,
            "tokens": {"input": 500, "output": 200, "reasoning": 0, "cache": {"read": 1000, "write": 100}},
        }), 1769941500000),
        # m15 — Agent "oracle" with high reasoning tokens
        ("m15", "ses_a3", msg_data(agent="oracle", inp=2000, out=1000, reason=800, cache_r=5000, cache_w=200, cost=0.15), 1769941510000),
        # m16 — Agent "explore" with moderate tokens
        ("m16", "ses_a3", msg_data(agent="explore", inp=800, out=400, reason=50, cache_r=2000, cache_w=100, cost=0.04), 1769941520000),
        # m17 — NULL agent (no `agent` field in JSON)
        ("m17", "ses_a4", json.dumps({
            "modelID": "test-no-agent",
            "providerID": "test",
            "role": "assistant",
            "mode": "build",
            "cost": 0.0,
            "tokens": {"input": 300, "output": 150, "reasoning": 0, "cache": {"read": 500, "write": 0}},
        }), 1769941530000),
        # m18 — With $.error field
        ("m18", "ses_a4", json.dumps({
            "modelID": "error-model",
            "providerID": "test",
            "role": "assistant",
            "mode": "build",
            "agent": "build",
            "error": {"name": "MessageAbortedError", "data": {"message": "aborted"}},
            "cost": 0.0,
            "tokens": {"input": 100, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}},
        }), 1769941540000),
        # m19 — With $.time.created and $.time.completed (response timing)
        ("m19", "ses_a3", json.dumps({
            "modelID": "timing-model",
            "providerID": "test",
            "role": "assistant",
            "mode": "build",
            "agent": "build",
            "cost": 0.02,
            "time": {"created": "2026-05-01T10:00:00Z", "completed": "2026-05-01T10:01:00Z"},
            "tokens": {"input": 400, "output": 200, "reasoning": 50, "cache": {"read": 1000, "write": 100}},
        }), 1769941550000),
        # m20 — Zero tokens (input=0, output=0)
        ("m20", "ses_a4", json.dumps({
            "modelID": "zero-token-model",
            "providerID": "test",
            "role": "assistant",
            "mode": "build",
            "agent": "build",
            "cost": 0.0,
            "tokens": {"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}},
        }), 1769941560000),
        # m21 — NULL cost (cost field missing)
        ("m21", "ses_a4", json.dumps({
            "modelID": "null-cost-model",
            "providerID": "test",
            "role": "assistant",
            "mode": "build",
            "agent": "build",
            "tokens": {"input": 200, "output": 100, "reasoning": 0, "cache": {"read": 300, "write": 0}},
        }), 1769941570000),
    ]
    conn.executemany(
        "INSERT INTO message (id, session_id, data, time_created) VALUES (?, ?, ?, ?)",
        messages,
    )

    conn.commit()


@pytest.fixture
def test_db_path() -> Generator[str, None, None]:
    """Create a temporary SQLite DB with fixture data, yield its path, then clean up."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    path = tmp.name

    conn = sqlite3.connect(path)
    _create_schema(conn)
    _insert_fixture_data(conn)
    conn.close()

    yield path

    Path(path).unlink(missing_ok=True)


@pytest.fixture
def test_conn(test_db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Open a read-only connection to the test DB."""
    conn = sqlite3.connect(test_db_path, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = 1")
    yield conn
    conn.close()
