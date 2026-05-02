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
│       ├── index.html  # Main ECharts dashboard (~1600 lines, dark theme)
│       └── partials/   # 10 Jinja2 partials (cards, panels, js_*, styles, etc.)
├── tests/
│   ├── __init__.py
│   ├── conftest.py     # Test fixtures (21 messages, 10 sessions)
│   ├── test_db.py      # 57 query tests
│   └── test_routes.py  # 42 API route tests
├── .sisyphus/          # Internal planning artifacts (dev journal)
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
| Template partials | `app/templates/partials/` | 10 files: `head`, `styles`, `header`, `cards`, `panels`, `scripts`, `js_utils`, `js_charts`, `js_renderers`, `js_app` |
| Tests | `tests/test_db.py`, `tests/test_routes.py` | 57 unit + 42 integration = 99 total (class-based, no mock) |
| Project config | `pyproject.toml` | uv-managed dependencies; no linting/formatting/CI configured |

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
- **Test organization**: Class-based (34 classes), zero mocking, real SQLite temp DB per test, function-scoped fixtures
- **API dispatch**: String-based `globals().get(func_name)` dispatch in `routes.py:109` — fragile on rename
- **Jinja2**: Raw `jinja2.Environment` (not Starlette's `Jinja2Templates`) — workaround for cache-key compatibility bug

## TIMEZONE HANDLING

**All times are Asia/Shanghai (UTC+8).** The dashboard consistently displays time in East Eight Time.

### Data Source

`opencode.db` stores `time_created` as **standard Unix epoch milliseconds** (milliseconds since 1970-01-01 00:00:00 UTC). OpenCode's own UI converts these to East Eight for display — the dashboard mirrors this behavior.

### Conversion Points

| Layer | File | Mechanism |
|-------|------|-----------|
| SQL queries | `app/db.py` (3 functions) | `datetime(time_created/1000, 'unixepoch', '+8 hours')` — the `'+8 hours'` modifier shifts UTC to Asia/Shanghai |
| Python date filter | `app/db.py:_iso_date_to_ms` | `ZoneInfo("Asia/Shanghai")` — interprets user-supplied date strings (e.g. `start_date=2026-03-01`) as Asia/Shanghai midnight, then converts to UTC epoch ms for SQL comparison |
| JS date formatting | `partials/js_utils.html` | `Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' })` — formats Date objects as `YYYY-MM-DD` in Shanghai time |
| JS refresh timestamp | `partials/js_app.html` | `toLocaleString('en-US', { ..., timeZone: 'Asia/Shanghai' })` — "Last refresh" label shows Shanghai time |

### Affected SQL Queries

| Function | What changes |
|----------|-------------|
| `get_tokens_by_date` | Date grouping shifts by +8h (day boundaries at Shanghai midnight) |
| `get_usage_heatmap` | Hour-of-day reflects Shanghai clock, not UTC |
| `get_cache_efficiency` | Daily aggregation aligns to Shanghai calendar day |

### Date Filter Boundaries

The `_iso_date_to_ms()` helper converts `"YYYY-MM-DD"` to epoch milliseconds for SQL `time_created >= ?` comparisons. Because it uses `Asia/Shanghai` timezone:

- `start_date="2026-03-01"` → epoch ms for `2026-03-01 00:00:00 CST` = `2026-02-28 16:00:00 UTC`
- `end_date="2026-03-01"` (end_of_day) → epoch ms for `2026-03-01 23:59:59 CST` = `2026-03-01 15:59:59 UTC`

This ensures date range filters behave intuitively for users in East Eight Time: a filter on `2026-03-01` covers the full calendar day in Shanghai.

### Key Constant

```python
# app/db.py
from zoneinfo import ZoneInfo
SHANGHAI = ZoneInfo("Asia/Shanghai")
```

Requires `tzdata` pip package on Windows (no bundled IANA timezone DB).

## ANTI-PATTERNS (THIS PROJECT)

- No writes to opencode.db — `INSERT`/`UPDATE`/`DELETE` are forbidden
- No direct filesystem writes to the DB directory
- No long-running queries without pagination (DB is ~385MB, 22k+ messages)
- No SPA build tooling (keep it simple: one-page dashboard with embedded charts)

## COMMANDS

```bash
uv sync                          # Install dependencies
uv run python -m app.main        # Start dev server (port 20230)
uv run python -m app.main --port 8888  # Custom port
uv run pytest -v                 # Run all 99 tests
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
