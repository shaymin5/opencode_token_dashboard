# PROJECT KNOWLEDGE BASE

**Generated:** 2026-05-01
**Stack:** Python 3.13 + uv + FastAPI/Flask + SQLite (read-only) + ECharts/Chart.js

## OVERVIEW

Read-only token usage dashboard for OpenCode. Pulls data from `opencode.db` (SQLite at `~/.local/share/opencode/opencode.db`) and renders web UI with time-series token charts. Never writes to the database.

## STRUCTURE

```
opencode_token_dashboard/
├── app/                # Web application package
│   ├── __init__.py
│   ├── main.py         # Entry point (uvicorn/flask run)
│   ├── routes.py       # API endpoints
│   ├── db.py           # Read-only DB queries
│   └── templates/      # HTML templates
├── pyproject.toml      # uv project config
└── AGENTS.md
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| DB queries | `app/db.py` | SQLite read-only via `sqlite3` module |
| API endpoints | `app/routes.py` | JSON endpoints for chart data |
| Frontend | `app/templates/` | HTML + JS charts (ECharts recommended) |
| Project config | `pyproject.toml` | uv-managed dependencies |

## DATABASE SCHEMA (opencode.db)

**Key Tables for Token Data:**

| Table | Purpose | Token Fields |
|-------|---------|--------------|
| `message` | Per-message token usage | `data` JSON: `tokens.input`, `tokens.output`, `tokens.reasoning`, `tokens.cache.read/write`, `cost`, `modelID`, `providerID`, `role`, `mode`, `agent` |
| `part` | Per-part token breakdown | Same `tokens` structure as message |
| `session` | Groups messages | `project_id`, `title`, `time_created` |
| `project` | Top-level grouping | `name`, `worktree` |

**Relationship:** `project` ← `session` ← `message` (via `project_id` → `session_id`)

**Key Queries:**
- Total tokens by project, model, month, session
- Token breakdown: input vs output vs reasoning vs cache
- Cost aggregation (when available)

## CONVENTIONS

- **Read-only DB access**: Open DB with `PRAGMA query_only = 1` to enforce no writes
- **Path**: DB at `C:\Users\Shaymin\.local\share\opencode\opencode.db` (Windows); use env var or config
- **uv**: Use `uv add` for deps, `uv run` for scripts, `uv sync` for install. No pip/venv.
- **Frontend**: Server-rendered HTML with JS charting library. Avoid SPA frameworks.

## ANTI-PATTERNS (THIS PROJECT)

- No writes to opencode.db — `INSERT`/`UPDATE`/`DELETE` are forbidden
- No direct filesystem writes to the DB directory
- No long-running queries without pagination (DB is ~385MB, 22k+ messages)
- No SPA build tooling (keep it simple: one-page dashboard with embedded charts)

## COMMANDS

```bash
uv sync                          # Install dependencies
uv run python -m app.main        # Start dev server
uv add fastapi uvicorn           # Add web framework
```

## NOTES

- DB at `C:\Users\Shaymin\.local\share\opencode\opencode.db` — do not hardcode, detect via `%LOCALAPPDATA%/../.local/share/opencode/` or CLI flag
- ~22k messages across ~980 sessions, ~9 projects
- Token data covers Feb-May 2026
- Free-tier models show `cost: 0` — cost field may be sparse
