# APP PACKAGE

**Stack:** FastAPI + Jinja2 + SQLite (read-only)

## OVERVIEW

Web application package: FastAPI routes, read-only SQLite queries, Jinja2 templates. Never writes to DB.

## STRUCTURE

```
app/
├── main.py         # Entry point (uvicorn + argparse + lifespan)
├── routes.py       # Unified /api/data?view=... (11 views) + 5 redirects
├── db.py           # 10 read-only SQL query functions + 5 helpers
├── templates/
│   ├── index.html  # Dashboard skeleton (16 lines, includes 10 partials)
│   └── partials/   # 10 componentized Jinja2 partials
└── static/         # Vendored ECharts assets
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add DB query | `app/db.py` | Follow pattern: `def get_*(conn, start_date=None, end_date=None) -> dict` |
| Add API route | `app/routes.py` | Register in `VIEW_DISPATCH`, add handler in `api_data()` switch |
| Modify templates | `app/templates/` | `index.html` for skeleton; `partials/` for component partials |
| Change port/startup | `app/main.py` | Port: CLI arg > env var > 20230 |

## KEY PATTERNS

### DB Queries (`db.py`)
- Signature: `def get_*(conn: Connection, start_date=None, end_date=None) -> dict`
- JSON extraction via `json_extract()` with `COALESCE(CAST(... AS INTEGER), 0)` defensive defaults
- Time conversion: `datetime(time_created/1000, 'unixepoch', '+8 hours')` for Asia/Shanghai
- Token-presence filter: `WHERE json_extract(data, '$.tokens.input') IS NOT NULL`
- Read-only: `PRAGMA query_only = 1` + `PRAGMA journal_mode = WAL` per connection
- Helpers: `_tokens(path)`, `_build_date_filter()`, `_iso_date_to_ms()`, `_coalesce_model()`, `_coalesce_provider()`

### Routes (`routes.py`)
- Unified dispatch via `VIEW_DISPATCH` dict (string → function name → `globals().get(lookup)`)
- Raw `jinja2.Environment` (not Starlette's `Jinja2Templates`) — cache-key compatibility workaround
- Per-request DB connection via FastAPI dependency injection (`get_db`)
- Backward-compat redirects (307) for old `/api/*` endpoints

### Templates
- 2-column grid layout, ECharts 5.6 (CDN dark theme)
- Partials naming: `styles.html`, `cards.html`, `panels.html`, `js_charts.html`, `js_renderers.html`, `js_app.html`, `js_utils.html`, `head.html`, `header.html`, `scripts.html`
- Chart container IDs: `<name>-chart`, card container IDs: `<name>-cards`

## MODULE-SPECIFIC ANTI-PATTERNS

- `globals().get(func_name)` dispatch at `routes.py:111` — fragile on function rename
- No Pydantic models — all params are raw strings, no response validation
- Sync `sqlite3` called from `async def` routes — runs in FastAPI thread pool
- 5 near-identical redirect handlers — DRY violation
- `_coalesce_model()` underused — `get_tokens_by_model` and `get_cost_breakdown` miss nested model JSON
- `_filter_token_messages()` exists but is never called (dead code)
- Hardcoded user path fallback in `get_db_path()` (line 52)
