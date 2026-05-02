# PROJECT KNOWLEDGE BASE

**Generated:** 2026-05-02
**Stack:** Python 3.13 + uv + FastAPI + SQLite (read-only) + ECharts

## OVERVIEW

Read-only token usage dashboard for OpenCode. Pulls data from `opencode.db` (SQLite at `~/.local/share/opencode/opencode.db`) and renders web UI with time-series token charts. Never writes to the database.

## STRUCTURE

```
opencode_token_dashboard/
├── app/                # Web application package
│   ├── __init__.py
│   ├── main.py         # Entry point (uvicorn)
│   ├── routes.py       # Unified /api/data?view=... endpoint (10 views)
│   ├── db.py           # 10 read-only SQLite query functions
│   └── templates/
│       └── index.html  # ECharts dashboard (~1600 lines, dark theme, 8 panels)
├── tests/
│   ├── __init__.py
│   ├── conftest.py     # Test fixtures (21 messages, 10 sessions)
│   ├── test_db.py      # 57 query tests
│   └── test_routes.py  # 42 API route tests
├── pyproject.toml      # uv project config
├── AGENTS.md
└── README.md
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| DB queries | `app/db.py` | 10 functions: 5 original + 5 new (agent breakdown, model efficiency, usage heatmap, top sessions, cache efficiency) |
| API endpoints | `app/routes.py` | Unified `/api/data?view=...` dispatches to 10 views; 5 old endpoints redirect (307) |
| Frontend | `app/templates/index.html` | Compact 2-column grid, 8 ECharts panels + 7 cards |
| Tests | `tests/test_db.py`, `tests/test_routes.py` | 57 unit + 42 integration = 99 total |
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

## API ENDPOINTS

| Method | Path | View Name | Description |
|--------|------|-----------|-------------|
| `GET` | `/` | — | Dashboard HTML page |
| `GET` | `/api/data` | `overview` | Aggregate stats (tokens, cost, sessions, messages) |
| `GET` | `/api/data` | `tokens-by-date` | Time-series by day/week/month |
| `GET` | `/api/data` | `tokens-by-model` | Tokens by model + provider |
| `GET` | `/api/data` | `tokens-by-project` | Tokens by project (from worktree) |
| `GET` | `/api/data` | `cost-breakdown` | Cost by model |
| `GET` | `/api/data` | `agent-breakdown` | Tokens by agent |
| `GET` | `/api/data` | `model-efficiency` | Cost/1K, I/O ratio, cache hit ratio per model |
| `GET` | `/api/data` | `usage-heatmap` | Day-of-week x hour grid |
| `GET` | `/api/data` | `top-sessions` | Top N sessions (limit param, default 10) |
| `GET` | `/api/data` | `cache-efficiency` | Daily cache hit ratio trend |
| `GET` | `/api/*` (old) | — | 307 redirects to `/api/data?view=...` |

## DB QUERY FUNCTIONS

| Function | Location | Purpose |
|----------|----------|---------|
| `get_overview_stats` | `app/db.py:173` | Aggregate overview (tokens, cost, sessions) |
| `get_tokens_by_date` | `app/db.py:208` | Time-series aggregation (day/week/month) |
| `get_tokens_by_model` | `app/db.py:256` | Tokens grouped by model + provider |
| `get_tokens_by_project` | `app/db.py:303` | Tokens grouped by project |
| `get_cost_breakdown` | `app/db.py:352` | Cost grouped by model + provider |
| `get_agent_breakdown` | `app/db.py:417` | Tokens grouped by agent |
| `get_model_efficiency` | `app/db.py:453` | Cost/1K, I/O ratio, cache hit ratio |
| `get_usage_heatmap` | `app/db.py:506` | Day-of-week x hour usage grid |
| `get_top_sessions` | `app/db.py:538` | Top N sessions by token consumption |
| `get_cache_efficiency` | `app/db.py:583` | Daily cache hit ratio time-series |

## FRONTEND LAYOUT

```
Layout: Compact 2-column grid (.panel-grid)
  - Sticky header with granularity toggle + date range picker
  - Row 1: 4 overview cards + 3 efficiency mini cards
  - 2-column grid: heatmap | top sessions | by model | by project | by agent | cost breakdown | cache efficiency
  - Bottom: mini time-series (150px, single total-token line)

Charting: ECharts 5.6 (CDN), dark theme
Data fetching: Unified /api/data?view=... with per-panel loading/error states
```

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

## WINDOWS CAVEATS

### Port Binding (WSAEACCES 10013)

Windows automatically reserves TCP port ranges for Hyper-V / WSL2 / Docker NAT **even when no process is listening**. Port 8000 is commonly caught in the 7954-8053 range.

```powershell
# Check excluded port ranges
netsh int ipv4 show excludedportrange protocol=tcp

# Result may show:
#   Start Port    End Port
#   ----------    --------
#   7954          8053     <- 8000 falls here!
#   8054          8153     <- 8080 falls here!
```

**Workaround**: Use a port outside all excluded ranges (e.g., 8888, 20230, or any port in 50060-59099). Provide a `--port` CLI flag so users can easily switch.

**Port priority** (implemented in `app/main.py`):
1. `--port` CLI argument
2. `PORT` environment variable
3. Hard-coded default (20230)

### Orphaned Server Processes

`Start-Process` in PowerShell launches a background process that **survives the PowerShell session**. Multiple test runs can leave orphaned `python -m app.main` processes holding ports.

```powershell
# Find orphaned server processes
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match "-m app.main" } |
  Stop-Process -Force

# Verify port is released
netstat -ano | findstr ":<port>"
```

**Prevention**: Always kill test server processes explicitly after verification. Use `Get-CimInstance` (not `Get-Process`) to inspect `CommandLine` and distinguish server processes from other Python processes.
