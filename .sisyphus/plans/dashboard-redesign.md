# Dashboard Redesign — Compact + Multi-Dimensional

## TL;DR

> **Quick Summary**: Redesign the single-page token dashboard from a single oversized time-series chart into a compact multi-panel layout with 8 new data dimensions (agent breakdown, model efficiency, usage heatmap, top sessions, cache efficiency). Refactor 5 separate API endpoints into one unified `/api/data?view=...` endpoint with backward-compatible redirects.
>
> **Deliverables**:
> - Unified API endpoint `/api/data` with 10 view types
> - 8 new db query functions (TDD: tests before implementation)
> - Complete frontend rewrite: compact 2-column grid, 8 panels + mini time-series + sticky header
> - Backward-compatible redirects for 5 old API endpoints
> - ~25 new tests (unit + integration)
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 (fixtures) → Task 2 (validate) → Tasks 5-8 (core queries) → Task 9 (unified endpoint) → Task 13 (frontend rewrite)

---

## Context

### Original Request
Two problems: (1) Dashboard layout is unintuitive — a single oversized 380px time-series chart dominates the page, showing limited info. (2) Dimensions are monotonous — only date/model/project/cost, missing agent, mode, role, efficiency, patterns.

### Interview Summary
**Key Discussions**:
- **Layout**: Compact Dashboard approach. Time-series shrunk to 150px mini-chart at page bottom. Above-the-fold: overview cards + model efficiency cards + usage heatmap + top sessions leaderboard + model/project/agent/cost panels in 2-column grid. Scroll for deeper panels.
- **Dimensions**: All three categories — per-model efficiency ($/1K tokens, I/O ratio), role/agent breakdown (agent bar chart, merged agent+mode), trends & patterns (heatmap, cache efficiency).
- **API Strategy**: Refactor to unified `/api/data?view=...` endpoint. Old 5 endpoints preserved as 307 redirects.
- **Test Strategy**: TDD — RED-GREEN-REFACTOR. Use existing pytest + httpx infrastructure.

**Research Findings**:
- DB has 22,797 messages (20,744 assistant), 1,031 sessions, 10 projects, Feb-May 2026
- 20 distinct agents, 15 models, 7 providers, 2 roles (assistant/user)
- Cache read: 833M tokens (96.7% of all tokens) — never shown in current dashboard
- JSON structure inconsistency: assistant uses flat `$.modelID`, user uses nested `$.model.modelID` — must coalesce
- Cost sparse: only 15% of messages have non-zero cost
- Response time data available from `$.time.created` / `$.time.completed` (avg 17s)

### Metis Review
**Identified Gaps** (addressed):
1. **Backward compatibility**: Old endpoints preserved as 307 redirects to `/api/data?view=...`
2. **Token-message filter**: Use `WHERE json_extract(data, '$.tokens.input') IS NOT NULL` (token presence) rather than `role = 'assistant'` — defensive against future schema changes
3. **Mini-chart series**: Show total tokens only (single line) at 150px, not 5 stacked series. Too small for multi-series.
4. **Agent vs Mode**: Merged into single "By Agent" panel (95% overlap, no need for two)
5. **Heatmap validation**: Pre-implementation task to verify data density on real DB — 4 months may yield sparse heatmap
6. **Scope cuts**: Session productivity, error rate chart, response time chart excluded from v1. Error rate + response time shown as overview card stats only.
7. **Div-by-zero guards**: Cache efficiency and cost efficiency queries include `CASE WHEN denominator > 0` guards
8. **Null agent**: `COALESCE(json_extract(data, '$.agent'), 'unknown')` in all agent queries

---

## Work Objectives

### Core Objective
Transform the dashboard from a single-oversized-chart layout into a compact, information-dense multi-panel layout that surfaces 8 new data dimensions while preserving all existing functionality.

### Concrete Deliverables
- `app/db.py` — 8 new query functions + 2 enhanced existing functions
- `app/routes.py` — unified `/api/data` endpoint with 10 views + 5 redirect wrappers
- `app/templates/index.html` — complete frontend rewrite (layout + charts)
- `tests/test_db.py` — ~15 new unit tests
- `tests/test_routes.py` — ~10 new integration tests

### Definition of Done
- [ ] `uv run pytest -v` → ALL tests pass (existing 45 + new ~25)
- [ ] `uv run python -m app.main` → page loads, all panels render at 1080p
- [ ] Old endpoints (`/api/overview`, etc.) return 307 redirect to `/api/data?view=...`
- [ ] New endpoint `/api/data?view=agent-breakdown` returns correct JSON
- [ ] Mini time-series renders at exactly 150px height with readable single-line chart
- [ ] All panels render loading/error states correctly

### Must Have
- Unified `/api/data?view=...` endpoint with 10 view types
- 307 redirects for all 5 old endpoints
- Compact 2-column grid layout (2 panels per row)
- Overview cards (4) + model efficiency cards (3 mini)
- Usage heatmap (hour × day-of-week)
- Top sessions leaderboard (top 10)
- By Agent breakdown chart
- Cache efficiency trend chart
- Mini time-series (150px, total tokens only)
- TDD: all new queries tested before implementation
- `COALESCE` for both flat and nested JSON model/provider fields

### Must NOT Have (Guardrails)
- **MUST NOT** remove or rename any existing API endpoint (307 redirects only)
- **MUST NOT** add new Python dependencies to `pyproject.toml`
- **MUST NOT** introduce build/bundling for frontend (keep CDN ECharts)
- **MUST NOT** touch `main.py` (port resolution, lifespan, uvicorn setup)
- **MUST NOT** restructure `tests/conftest.py` fixture approach
- **MUST NOT** add drill-down/cross-filtering interactivity between panels
- **MUST NOT** add real-time updates, WebSocket, polling
- **MUST NOT** add theme toggle (dark only)
- **MUST NOT** add new responsive breakpoints beyond existing
- **EXCLUDE from v1**: session productivity (unverified fields), error rate chart, response time chart, mode breakdown (merged with agent)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES — pytest + httpx + 45 existing tests
- **Automated tests**: TDD — RED-GREEN-REFACTOR
- **Framework**: pytest with in-memory SQLite test fixtures

### QA Policy
Every task includes agent-executed QA scenarios.
- **Backend**: `uv run pytest -v` for unit + integration tests
- **API**: `curl` against running server for endpoint verification
- **Frontend**: Playwright for visual verification (layout, chart rendering, loading/error states)
- **Evidence**: `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundations — fixtures + validation + type defs):
├── Task 1: Expand test fixtures (TDD prep)
├── Task 2: Validate heatmap data density on real DB
├── Task 3: Unified query helper + view type definitions
└── Task 4: Write failing tests for ALL new query functions (TDD RED phase)

Wave 2 (Backend — queries + unified endpoint, MAX PARALLEL):
├── Task 5: Implement get_agent_breakdown query (depends: 3, 4)
├── Task 6: Implement get_model_efficiency query (depends: 3, 4)
├── Task 7: Implement get_usage_heatmap query (depends: 2, 3, 4)
├── Task 8: Implement get_top_sessions query (depends: 3, 4)
├── Task 9: Implement get_cache_efficiency query (depends: 3, 4)
└── Task 10: Implement unified /api/data endpoint + redirects (depends: 5-9)

Wave 3 (Frontend — complete rewrite, MAX PARALLEL for independent panels):
├── Task 11: Layout skeleton + CSS grid + sticky header (depends: none)
├── Task 12: Overview cards + model efficiency cards (depends: 10, 11)
├── Task 13: Heatmap panel (depends: 10, 11)
├── Task 14: Top sessions panel (depends: 10, 11)
├── Task 15: By Model + By Project panels (depends: 10, 11)
├── Task 16: By Agent + Cost Breakdown panels (depends: 10, 11)
├── Task 17: Cache efficiency + Mini time-series panels (depends: 10, 11)
└── Task 18: Wire up JS: data fetching, granularity, date range, resize (depends: 12-17)

Wave FINAL (Verification, 4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high + playwright)
└── Task F4: Scope fidelity check (deep)
```

**Critical Path**: Task 1 → Task 3 → Task 4 → Tasks 5-9 → Task 10 → Task 18 → F1-F4
**Parallel Speedup**: ~65% faster than sequential (3 backend queries run in parallel, 7 frontend panels in parallel)
**Max Concurrent**: 7 (Wave 3)

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

- [x] 1. **Expand test fixtures for new dimensions (TDD prep)**

  **What to do**:
  - Add fixture messages with nested JSON `{"model":{"providerID":"minimax-cn","modelID":"MiniMax-M2.5"}}` (user-message style) to test COALESCE logic — current fixtures only have flat `modelID`
  - Add fixture messages with `$.agent` = `"build"`, `"oracle"`, `"explore"`, and NULL (no agent field)
  - Add fixture messages with `$.error` = `{"name":"MessageAbortedError","data":{"message":"aborted"}}`
  - Add fixture messages with `$.time.created` and `$.time.completed` for response time calculations
  - Add fixture messages with `$.tokens.input = 0, $.tokens.output = 0` (empty token case)
  - Add fixture messages with `$.cost = 0` and NULL cost
  - Add fixture sessions with `parent_id IS NULL` and `parent_id IS NOT NULL`, varied `version` values
  - Ensure existing 45 tests still pass after fixture expansion (verify with `uv run pytest -v`)

  **Must NOT do**:
  - Don't change the `conftest.py` structure (keep `_create_schema()`, `sample_db()` approach)
  - Don't remove or rename any existing fixture data
  - Don't add `part` table data (part not needed for this plan)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward fixture data creation — pattern-matching existing conftest.py structure
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (blocks ALL subsequent tasks — foundation layer)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 2-10 (all backend tests depend on fixtures)
  - **Blocked By**: None (can start immediately)

  **References**:
  - `tests/conftest.py` — Full fixture structure to match: `_create_schema()`, `_insert_fixture_data()` function, existing message/session/project insertion pattern. Must follow the exact same insertion style.
  - `tests/test_db.py` — All 25 existing test functions — understand what data they expect so new fixtures don't break them
  - `app/db.py:74-87` — `_tokens()` helper and `json_extract` patterns used in queries, to ensure fixture JSON matches extraction format

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_db.py -v` → 25 existing tests PASS (no regressions)
  - [ ] New fixture messages with nested `model.modelID` exist and are queryable
  - [ ] New fixture messages with `agent`, `error`, `time.created/completed` exist
  - [ ] New fixture messages with edge cases (NULL agent, zero tokens, zero cost) exist

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Existing tests pass after fixture expansion
    Tool: Bash
    Preconditions: Expanded conftest.py committed
    Steps:
      1. uv run pytest tests/test_db.py -v --tb=short
      2. Verify output shows "25 passed"
    Expected Result: All 25 existing tests pass. Zero failures, zero errors.
    Failure Indicators: Any test failure or error (check stack trace for which fixture broke which test)
    Evidence: .sisyphus/evidence/task-1-existing-tests-pass.txt

  Scenario: New fixtures are queryable with COALESCE pattern
    Tool: Bash
    Preconditions: Expanded conftest.py committed
    Steps:
      1. uv run python -c "
      from tests.conftest import sample_db
      conn = sample_db()
      rows = conn.execute('''
        SELECT COALESCE(json_extract(data, '\$.model.modelID'), json_extract(data, '\$.modelID')) as model
        FROM message
      ''').fetchall()
      models = [r['model'] for r in rows]
      print('Models:', set(models))
      "
      2. Verify output includes both flat and nested model names
    Expected Result: Both flat modelID and nested model.modelID values appear in the model set
    Failure Indicators: Only one pattern's models appear — COALESCE not working
    Evidence: .sisyphus/evidence/task-1-coalesce-models.txt
  ```

  **Commit**: YES (groups with Task 3)
  - Message: `test(conftest): expand fixtures for new dimensions (nested JSON, agent, error, timing)`
  - Files: `tests/conftest.py`
  - Pre-commit: `uv run pytest tests/test_db.py -v`

- [x] 2. **Validate heatmap data density on real production DB**

  **What to do**:
  - Run exploratory queries against the real `opencode.db` at `C:\Users\Shaymin\.local\share\opencode\opencode.db`
  - Query: `SELECT strftime('%w', datetime(time_created/1000, 'unixepoch')) as dow, strftime('%H', datetime(time_created/1000, 'unixepoch')) as hour, COUNT(*) as cnt FROM message WHERE json_extract(data, '$.tokens.input') IS NOT NULL GROUP BY dow, hour ORDER BY dow, hour`
  - Count how many cells have data (non-zero count). 7 × 24 = 168 possible cells
  - Report sparsity: if more than 50% of cells are zero, the heatmap will look mostly blank
  - If sparse, note this finding — the plan will proceed with the heatmap but at a lower visual priority
  - Also test query performance: time the query execution
  - Report findings by writing a summary to `.sisyphus/evidence/task-2-heatmap-validation.md`

  **Must NOT do**:
  - Don't modify the real DB (read-only!)
  - Don't hardcode results — just report findings

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single exploratory query against real DB with report
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Task 3 (independent)
  - **Parallel Group**: Wave 1 (with Task 3)
  - **Blocks**: Task 7 (heatmap query implementation — data density affects panel placement)
  - **Blocked By**: Task 1 (fixtures)

  **References**:
  - `app/db.py:51-63` — `get_connection()` for connecting to real DB with `PRAGMA query_only = 1`
  - `app/db.py:95-131` — `_iso_date_to_ms()` and `_build_date_filter()` patterns for date handling

  **Acceptance Criteria**:
  - [ ] Heatmap query runs against real DB and returns results
  - [ ] Cell count and sparsity percentage documented
  - [ ] Query execution time documented
  - [ ] Findings report saved to `.sisyphus/evidence/task-2-heatmap-validation.md`

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Heatmap query returns valid data from real DB
    Tool: Bash
    Preconditions: Real opencode.db accessible at expected path
    Steps:
      1. uv run python -c "
      from app.db import get_connection, get_db_path
      conn = get_connection()
      rows = conn.execute('''
        SELECT strftime('%w', datetime(time_created/1000, 'unixepoch')) as dow,
               strftime('%H', datetime(time_created/1000, 'unixepoch')) as hour,
               COUNT(*) as cnt
        FROM message
        WHERE json_extract(data, '\$.tokens.input') IS NOT NULL
        GROUP BY dow, hour ORDER BY dow, hour
      ''').fetchall()
      cells = len(rows)
      non_zero = sum(1 for r in rows if r['cnt'] > 0)
      print(f'Cells with data: {cells}/168')
      print(f'Non-zero cells: {non_zero}')
      print(f'Fill rate: {non_zero/168*100:.1f}%')
      "
      2. Verify output shows fill rate percentage
    Expected Result: Query completes without error, fill rate reported
    Failure Indicators: DB not found, query timeout (>5s), all-zero result
    Evidence: .sisyphus/evidence/task-2-heatmap-validation.md
  ```

  **Commit**: NO (findings only, no code changes)

- [x] 3. **Add unified query helpers + view type definitions**

  **What to do**:
  - In `app/db.py`, add `_filter_token_messages()` helper that returns `("WHERE json_extract(data, '$.tokens.input') IS NOT NULL", [])` — canonical filter for token-bearing messages. Defensive against future schema changes (doesn't rely on `role` field)
  - Add `_coalesce_model()` SQL snippet: `COALESCE(json_extract(data, '$.model.modelID'), json_extract(data, '$.modelID'))`
  - Add `_coalesce_provider()` SQL snippet: `COALESCE(json_extract(data, '$.model.providerID'), json_extract(data, '$.providerID'))`
  - Add `DIV_ZERO_GUARD` constant: `CASE WHEN denominator > 0 THEN numerator / denominator ELSE NULL END` pattern
  - In `app/routes.py`, define a `VIEW_NAMES` constant: `Literal["overview", "tokens-by-date", "tokens-by-model", "tokens-by-project", "cost-breakdown", "agent-breakdown", "model-efficiency", "usage-heatmap", "top-sessions", "cache-efficiency"]`
  - Define `VIEW_DISPATCH` dict mapping view names to query functions
  - Enhance `_build_date_filter` to accept optional token-filter injection

  **Must NOT do**:
  - Don't change the function signatures of existing query functions (they use `(conn, start_date, end_date)`)
  - Don't add `role`-based filtering (use token presence)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small helper functions and type definitions with clear patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Task 2 (independent)
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Tasks 5-10 (all query functions use these helpers)
  - **Blocked By**: Task 1 (fixtures — verification of COALESCE pattern)

  **References**:
  - `app/db.py:69-87` — `_tokens()` SQL snippet helper — follow same pattern for new helpers
  - `app/db.py:95-131` — `_build_date_filter()` — understand current signature before enhancing
  - `app/routes.py:7-23` — Current imports and router setup — understand where VIEW_DISPATCH fits

  **Acceptance Criteria**:
  - [ ] `_coalesce_model()` returns correct SQL snippet
  - [ ] `_filter_token_messages()` returns correct WHERE clause
  - [ ] `VIEW_NAMES` Literal type includes all 10 view names
  - [ ] Existing 45 tests still pass (helpers don't break anything)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: COALESCE helpers produce correct SQL
    Tool: Bash
    Preconditions: Helpers added to db.py
    Steps:
      1. uv run python -c "
      from app.db import _coalesce_model, _coalesce_provider
      print('Model:', _coalesce_model())
      print('Provider:', _coalesce_provider())
      "
      2. Verify output contains COALESCE(json_extract(...), json_extract(...)) SQL
    Expected Result: Both helpers return valid SQL snippets with COALESCE
    Failure Indicators: Syntax error, missing COALESCE, wrong JSON paths
    Evidence: .sisyphus/evidence/task-3-coalesce-output.txt

  Scenario: Existing tests pass after helper addition
    Tool: Bash
    Preconditions: Helpers added, no existing query logic changed
    Steps:
      1. uv run pytest tests/test_db.py -v --tb=short
      2. Verify 25 passed
    Expected Result: All existing tests pass
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-3-existing-tests.txt
  ```

  **Commit**: YES (groups with Task 1)
  - Message: `feat(db): add COALESCE helpers, token filter, view type definitions`
  - Files: `app/db.py`, `app/routes.py`

- [x] 4. **Write failing tests for ALL new query functions (TDD RED phase)**

  **What to do**:
  - In `tests/test_db.py`, write test classes for each of the 6 new query functions (Tasks 5-9) — tests should FAIL initially since functions don't exist yet
  - `TestGetAgentBreakdown`: verify sorted descending by total tokens, agent names are strings, empty date range returns empty, NULL agent → "unknown"
  - `TestGetModelEfficiency`: verify cost_per_1k_tokens is positive float, input_output_ratio is > 0, free models (cost=0) show 0.00, div-by-zero models handled
  - `TestGetUsageHeatmap`: verify 2D array or row-based format with dow/hour/count, empty date returns empty
  - `TestGetTopSessions`: verify limit=N returns at most N rows, sorted descending by tokens, includes session title and project name
  - `TestGetCacheEfficiency`: verify cache_hit_ratio in 0-1 range, date ordered ascending, NULL when both cache.read and input are 0
  - `TestUnifiedEndpoint`: verify view="overview" returns 200, view="invalid" returns 400 with error, missing view returns 400
  - `TestBackwardCompatibility`: verify GET /api/overview returns 307 redirect, Location header points to /api/data?view=overview

  **Must NOT do**:
  - Don't implement the actual query functions yet (TDD: tests FAIL first)
  - Don't test against real DB — use test fixtures only
  - Don't test frontend behavior (these are backend tests only)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Test writing following existing test patterns in test_db.py
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 3 helpers for import, blocks all implementation tasks)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 5-10 (TDD: implementation follows failing tests)
  - **Blocked By**: Tasks 1, 3

  **References**:
  - `tests/test_db.py:1-50` — Existing test class patterns: `TestGetOverviewStats`, `TestGetTokensByDate` — copy structure
  - `tests/conftest.py` — Fixture function `sample_db()` — understand what data is available for assertions
  - `app/db.py:137-165` — `get_overview_stats()` return shape — understand dict key patterns for new queries

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_db.py -v` → "N failed" (tests fail because functions don't exist — expected)
  - [ ] Test class `TestGetAgentBreakdown` exists with at least 3 test methods
  - [ ] Test class `TestGetModelEfficiency` exists with at least 3 test methods
  - [ ] Test class `TestGetUsageHeatmap` exists with at least 2 test methods
  - [ ] Test class `TestGetTopSessions` exists with at least 2 test methods
  - [ ] Test class `TestGetCacheEfficiency` exists with at least 2 test methods

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: TDD RED — tests fail as expected
    Tool: Bash
    Preconditions: Test classes written, query functions NOT implemented
    Steps:
      1. uv run pytest tests/test_db.py -v --tb=line 2>&1 | findstr /C:"FAILED" /C:"ERROR"
      2. Count FAILED lines
    Expected Result: >= 10 test failures (all new tests fail, existing 25 still pass)
    Failure Indicators: All tests pass (query functions implemented too early — TDD violation)
    Evidence: .sisyphus/evidence/task-4-tdd-red.txt
  ```

  **Commit**: YES
  - Message: `test(db): add failing tests for 6 new query functions (TDD RED)`
  - Files: `tests/test_db.py`
  - Pre-commit: `uv run pytest tests/test_db.py -v --tb=line` (expected: N failures)

- [x] 5. **Implement `get_agent_breakdown` query + route view**

  **What to do**:
  - In `app/db.py`: Implement `get_agent_breakdown(conn, start_date, end_date)` → list[dict]
  - SQL: `SELECT COALESCE(json_extract(data, '$.agent'), 'unknown') AS agent, SUM(...) AS total_tokens, SUM(input) AS input, SUM(output) AS output, SUM(reasoning) AS reasoning, SUM(cache_read) AS cache_read, SUM(cache_write) AS cache_write, COUNT(*) AS message_count FROM message WHERE [token_filter] AND [date_filter] GROUP BY agent ORDER BY total_tokens DESC`
  - Use `_coalesce_model()` helper (even though not needed for agents, keep consistency), `_filter_token_messages()`, `_build_date_filter()`
  - In `app/routes.py`: Add `"agent-breakdown"` entry to `VIEW_DISPATCH` dict mapping to `get_agent_breakdown`
  - In `tests/test_db.py`: Verify `TestGetAgentBreakdown` tests now PASS (TDD GREEN)
  - Add integration tests in `tests/test_routes.py`: `GET /api/data?view=agent-breakdown` → 200 with expected shape

  **Must NOT do**:
  - Don't separate agent and mode into two queries (merged into one)
  - Don't include user messages (filter by token presence)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single query function following existing patterns, route dispatch entry, tests already written
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 6, 7, 8, 9 (all independent query functions)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10 (unified endpoint depends on all query views being registered)
  - **Blocked By**: Tasks 3, 4

  **References**:
  - `app/db.py:220-249` — `get_tokens_by_model()` — identical pattern: GROUP BY with COALESCE, SUM tokens, COUNT messages, date filter, ORDER BY DESC. Copy this pattern exactly.
  - `app/db.py:95-131` — `_build_date_filter()` — already understands this
  - `app/routes.py:61-74` — `api_overview()` — route pattern: `start_date: str | None = Query(None)`, try/except, `conn: Connection = Depends(get_db)`

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_db.py::TestGetAgentBreakdown -v` → all tests PASS
  - [ ] Agent names include "unknown" for NULL agent messages
  - [ ] Results sorted by total_tokens descending
  - [ ] Date filtering works (start_date, end_date, both, neither)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: TDD GREEN — agent breakdown tests pass
    Tool: Bash
    Preconditions: get_agent_breakdown implemented
    Steps:
      1. uv run pytest tests/test_db.py::TestGetAgentBreakdown -v
      2. Verify "X passed" with zero failures
    Expected Result: All agent breakdown tests pass
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-5-agent-tests.txt

  Scenario: API endpoint returns valid JSON
    Tool: Bash (curl)
    Preconditions: Server running on port 20230
    Steps:
      1. curl -s http://127.0.0.1:20230/api/data?view=agent-breakdown | python -m json.tool
      2. Verify first element has keys: agent, total_tokens, input, output, reasoning, cache_read, cache_write, message_count
      3. curl -s http://127.0.0.1:20230/api/data?view=agent-breakdown&start_date=2026-03-01&end_date=2026-03-31
      4. Verify filtered results differ from unfiltered (fewer agents or lower totals)
    Expected Result: Valid JSON array, sorted descending, date filtering works
    Failure Indicators: 500 error, empty array, wrong sort order
    Evidence: .sisyphus/evidence/task-5-agent-api.json
  ```

  **Commit**: YES
  - Message: `feat(db): add get_agent_breakdown query + route view`
  - Files: `app/db.py`, `app/routes.py`, `tests/test_db.py` (removed expectedFailure markers), `tests/test_routes.py`

- [x] 6. **Implement `get_model_efficiency` query + route view**

  **What to do**:
  - In `app/db.py`: Implement `get_model_efficiency(conn, start_date, end_date)` → list[dict]
  - Compute per model: `cost_per_1k_tokens = (SUM(cost) * 1000.0) / NULLIF(SUM(input) + SUM(output), 0)`, `input_output_ratio = CAST(SUM(input) AS REAL) / NULLIF(SUM(output), 0)`, `cache_hit_ratio = CAST(SUM(cache_read) AS REAL) / NULLIF(SUM(cache_read) + SUM(input), 0)`, `total_tokens`, `total_cost`, `message_count`
  - Use DIV_ZERO_GUARD pattern for all ratios
  - `GROUP BY model, provider` with `_coalesce_model()` and `_coalesce_provider()`
  - `ORDER BY total_tokens DESC`
  - Register view in `VIEW_DISPATCH`
  - Make `TestGetModelEfficiency` tests pass

  **Must NOT do**:
  - Don't compute efficiency for individual messages — use SUM aggregation per model
  - Don't hardcode model names

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Aggregation query with division guards, similar to cost_breakdown pattern
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 5, 7, 8, 9
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 3, 4

  **References**:
  - `app/db.py:220-249` — `get_tokens_by_model()` — uses same GROUP BY model+provider, same COALESCE pattern. Adapt.
  - `app/db.py:316-345` — `get_cost_breakdown()` — cost aggregation pattern, uses sub-query for token count

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_db.py::TestGetModelEfficiency -v` → all tests PASS
  - [ ] `cost_per_1k_tokens` is NULL for free models (cost=0)
  - [ ] `input_output_ratio` is positive for models with output > 0
  - [ ] `cache_hit_ratio` is in 0-1 range (or NULL for div-by-zero)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Model efficiency via API returns correct ratios
    Tool: Bash (curl)
    Preconditions: Server running
    Steps:
      1. curl -s http://127.0.0.1:20230/api/data?view=model-efficiency | python -c "
      import json, sys
      data = json.load(sys.stdin)
      for m in data:
          print(f'{m[\"model\"]}: \${m[\"cost_per_1k_tokens\"]}/1K tokens, I/O={m[\"input_output_ratio\"]}, cache={m[\"cache_hit_ratio\"]}')
      "
      2. Verify output shows per-model stats
    Expected Result: Each model row has cost_per_1k_tokens, input_output_ratio, cache_hit_ratio
    Failure Indicators: Division by zero errors (NULL expected, not crash)
    Evidence: .sisyphus/evidence/task-6-efficiency-api.txt
  ```

  **Commit**: YES
  - Message: `feat(db): add get_model_efficiency query with cost/I-O/cache ratios`
  - Files: `app/db.py`, `app/routes.py`, `tests/test_db.py`, `tests/test_routes.py`

- [x] 7. **Implement `get_usage_heatmap` query + route view**

  **What to do**:
  - In `app/db.py`: Implement `get_usage_heatmap(conn, start_date, end_date)` → list[dict]
  - SQL: `SELECT strftime('%w', datetime(time_created/1000, 'unixepoch')) AS day_of_week, strftime('%H', datetime(time_created/1000, 'unixepoch')) AS hour, COUNT(*) AS message_count, SUM(...) AS total_tokens FROM message WHERE [token_filter] AND [date_filter] GROUP BY day_of_week, hour ORDER BY day_of_week, hour`
  - Return as flat array of `{day_of_week, hour, message_count, total_tokens}` — frontend will pivot to 7×24 grid
  - Day 0 = Sunday, Hour 0-23 = UTC
  - Register view in `VIEW_DISPATCH`
  - Make `TestGetUsageHeatmap` tests pass
  - If Task 2 found sparse data, note in the route docstring that UTC timezone applies

  **Must NOT do**:
  - Don't pre-pivot to 2D array (keep flat, let frontend pivot)
  - Don't convert to local timezone (document UTC)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single strftime-based aggregation query, straightforward GROUP BY
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 5, 6, 8, 9
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 2, 3, 4

  **References**:
  - `app/db.py:172-213` — `get_tokens_by_date()` — uses `strftime(fmt, datetime(time_created/1000, 'unixepoch'))` pattern. Adapt for day-of-week + hour.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_db.py::TestGetUsageHeatmap -v` → all tests PASS
  - [ ] Returns rows with day_of_week (0-6), hour (0-23), message_count, total_tokens
  - [ ] Date filtering works

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Heatmap API returns flat grid data
    Tool: Bash (curl)
    Preconditions: Server running
    Steps:
      1. curl -s http://127.0.0.1:20230/api/data?view=usage-heatmap | python -c "
      import json, sys
      data = json.load(sys.stdin)
      print(f'Rows: {len(data)}')
      days = set(r['day_of_week'] for r in data)
      hours = set(r['hour'] for r in data)
      print(f'Days covered: {sorted(days)}')
      print(f'Hours covered: {sorted(hours)}')
      "
      2. Verify output shows rows, days 0-6, hours 0-23
    Expected Result: 7×24=168 possible cells, days are '0'-'6', hours '00'-'23'
    Failure Indicators: Empty array, missing day/hour, or wrong type (should be strings)
    Evidence: .sisyphus/evidence/task-7-heatmap-api.txt
  ```

  **Commit**: YES
  - Message: `feat(db): add get_usage_heatmap query (day-of-week × hour grid)`
  - Files: `app/db.py`, `app/routes.py`, `tests/test_db.py`, `tests/test_routes.py`

- [x] 8. **Implement `get_top_sessions` query + route view**

  **What to do**:
  - In `app/db.py`: Implement `get_top_sessions(conn, start_date, end_date, limit=10)` → list[dict]
  - SQL: JOIN message → session → project. `SELECT s.id, s.title, p.worktree, COUNT(m.id) AS message_count, SUM(...) AS total_tokens, SUM(cost) AS total_cost FROM message m JOIN session s ON s.id = m.session_id JOIN project p ON p.id = s.project_id WHERE [token_filter] AND [date_filter] GROUP BY s.id ORDER BY total_tokens DESC LIMIT ?`
  - Derive project name from worktree using existing `_project_name_from_worktree()` helper
  - Include session `time_created` for date context
  - Register view in `VIEW_DISPATCH`, accept optional `limit` query param (default 10, max 50)
  - Make `TestGetTopSessions` tests pass

  **Must NOT do**:
  - Don't include user-only sessions (filter by token presence)
  - Don't show raw worktree path — use derived project name

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: JOIN-based query with LIMIT, following project query patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 5, 6, 7, 9
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 3, 4

  **References**:
  - `app/db.py:267-309` — `get_tokens_by_project()` — uses same 3-table JOIN pattern (message → session → project), same `_project_name_from_worktree()`. Adapt for per-session GROUP BY.
  - `app/db.py:256-265` — `_project_name_from_worktree()` — reuse this exact helper

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_db.py::TestGetTopSessions -v` → all tests PASS
  - [ ] Returns at most `limit` rows
  - [ ] Sorted by total_tokens descending
  - [ ] Includes session title, project name, message_count, total_cost

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Top sessions API with custom limit
    Tool: Bash (curl)
    Preconditions: Server running
    Steps:
      1. curl -s "http://127.0.0.1:20230/api/data?view=top-sessions&limit=5" | python -c "
      import json, sys
      data = json.load(sys.stdin)
      print(f'Rows: {len(data)}')
      for s in data:
          print(f'{s[\"title\"]}: {s[\"total_tokens\"]} tokens ({s[\"project\"]})')
      "
      2. Verify output shows exactly 5 rows, sorted by total_tokens descending
    Expected Result: 5 sessions, sorted, with title/project/tokens fields
    Failure Indicators: More than limit rows, wrong sort order, missing fields
    Evidence: .sisyphus/evidence/task-8-top-sessions-api.txt
  ```

  **Commit**: YES
  - Message: `feat(db): add get_top_sessions query with JOIN (message + session + project)`
  - Files: `app/db.py`, `app/routes.py`, `tests/test_db.py`, `tests/test_routes.py`

- [x] 9. **Implement `get_cache_efficiency` query + route view**

  **What to do**:
  - In `app/db.py`: Implement `get_cache_efficiency(conn, start_date, end_date)` → list[dict]
  - Time-series query: `SELECT strftime('%Y-%m-%d', datetime(time_created/1000, 'unixepoch')) AS date, SUM(cache_read) AS cache_read, SUM(cache_write) AS cache_write, SUM(input) AS input, CASE WHEN (SUM(cache_read) + SUM(input)) > 0 THEN CAST(SUM(cache_read) AS REAL) / (SUM(cache_read) + SUM(input)) ELSE NULL END AS cache_hit_ratio FROM message WHERE [token_filter] AND [date_filter] GROUP BY date ORDER BY date ASC`
  - Return daily cache hit ratio + absolute cache volumes
  - Register view in `VIEW_DISPATCH`
  - Make `TestGetCacheEfficiency` tests pass

  **Must NOT do**:
  - Don't compute ratio client-side — do it in SQL with DIV_ZERO_GUARD
  - Don't aggregate at week/month level (keep daily for trend granularity)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Time-series query with ratio calculation, same pattern as get_tokens_by_date
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 5, 6, 7, 8
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 3, 4

  **References**:
  - `app/db.py:172-213` — `get_tokens_by_date()` — same strftime-based daily aggregation pattern. Copy and adapt for cache-specific fields.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_db.py::TestGetCacheEfficiency -v` → all tests PASS
  - [ ] `cache_hit_ratio` is NULL when cache_read + input = 0
  - [ ] `cache_hit_ratio` is between 0 and 1 (inclusive) when defined
  - [ ] Date sorted ascending

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Cache efficiency via API
    Tool: Bash (curl)
    Preconditions: Server running
    Steps:
      1. curl -s http://127.0.0.1:20230/api/data?view=cache-efficiency | python -c "
      import json, sys
      data = json.load(sys.stdin)
      for d in data[-3:]:
          print(f'{d[\"date\"]}: cache_hit={d[\"cache_hit_ratio\"]}, read={d[\"cache_read\"]}, input={d[\"input\"]}')
      "
      2. Verify cache_hit_ratio values are in 0-1 range or None
    Expected Result: Array of daily rows with cache_hit_ratio field
    Failure Indicators: Ratio > 1 (logic error), all None (data issue)
    Evidence: .sisyphus/evidence/task-9-cache-api.txt
  ```

  **Commit**: YES
  - Message: `feat(db): add get_cache_efficiency query with daily cache hit ratio`
  - Files: `app/db.py`, `app/routes.py`, `tests/test_db.py`, `tests/test_routes.py`

- [x] 10. **Implement unified `/api/data` endpoint + backward-compatible redirects**

  **What to do**:
  - In `app/routes.py`: Replace 5 existing route functions with a single `@router.get("/api/data")` endpoint
  - Accept `view: str = Query(..., description="Data view: overview, tokens-by-date, ...")`, `granularity`, `start_date`, `end_date`, `limit` as optional params
  - Dispatch via `VIEW_DISPATCH` dict — if view not found, return `JSONResponse(400, {"error": f"Unknown view '{view}'. Valid views: {list(VIEW_DISPATCH.keys())}"})`
  - Pass appropriate params to each query function (granularity → tokens-by-date, limit → top-sessions)
  - Add 5 redirect wrapper routes for backward compatibility:
    - `@router.get("/api/overview")` → `RedirectResponse(url="/api/data?view=overview", status_code=307)`
    - Same pattern for `/api/tokens-by-date`, `/api/tokens-by-model`, `/api/tokens-by-project`, `/api/cost-breakdown`
  - Pass query params through to redirect URL
  - Make `TestUnifiedEndpoint` and `TestBackwardCompatibility` tests pass

  **Must NOT do**:
  - Don't delete old endpoint logic — they become redirect wrappers
  - Don't change the `get_db` dependency injection pattern

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Route consolidation — straightforward FastAPI route changes, no new logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on all query functions being registered)
  - **Parallel Group**: Wave 2 (last task)
  - **Blocks**: Tasks 12-18 (frontend needs unified API)
  - **Blocked By**: Tasks 5, 6, 7, 8, 9

  **References**:
  - `app/routes.py:51-139` — All existing route definitions — understand every endpoint before refactoring
  - `app/routes.py:39-45` — `get_db()` dependency — keep this exact pattern
  - `app/routes.py:9-10` — `from fastapi import ... Query, Request` — RedirectResponse needs to be added to imports

  **Acceptance Criteria**:
  - [ ] `GET /api/data?view=overview` → 200 with overview JSON
  - [ ] `GET /api/data?view=agent-breakdown` → 200 with agent breakdown JSON
  - [ ] `GET /api/data?view=invalid` → 400 with error message listing valid views
  - [ ] `GET /api/data` (no view param) → 400 with error
  - [ ] `GET /api/overview` → 307 redirect to `/api/data?view=overview`
  - [ ] All 5 old endpoints return 307 with correct Location header
  - [ ] `uv run pytest tests/test_routes.py -v` → all tests pass (existing 20 + new ~10)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Unified endpoint serves all views
    Tool: Bash (curl)
    Preconditions: Server running
    Steps:
      1. for view in overview agent-breakdown model-efficiency usage-heatmap top-sessions cache-efficiency; do
           status=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:20230/api/data?view=$view")
           echo "$view: $status"
         done
      2. Verify all return 200
    Expected Result: All 6 views return 200
    Failure Indicators: Any 400 or 500 status
    Evidence: .sisyphus/evidence/task-10-all-views.txt

  Scenario: Backward-compatible redirects work
    Tool: Bash (curl)
    Preconditions: Server running
    Steps:
      1. curl -s -o /dev/null -w "overview: %{http_code} → %{redirect_url}\n" -L http://127.0.0.1:20230/api/overview
      2. Repeat for tokens-by-date, tokens-by-model, tokens-by-project, cost-breakdown
      3. Verify all return 307 and redirect to /api/data?view=...
    Expected Result: All 5 old endpoints return 307 with correct Location
    Failure Indicators: 404 (endpoint removed), 200 (didn't redirect), wrong Location
    Evidence: .sisyphus/evidence/task-10-redirects.txt

  Scenario: Invalid view returns helpful error
    Tool: Bash (curl)
    Preconditions: Server running
    Steps:
      1. curl -s http://127.0.0.1:20230/api/data?view=nonexistent | python -m json.tool
      2. Verify response contains "error" key and lists valid views
    Expected Result: 400 status, JSON with error message listing valid views
    Failure Indicators: 500 crash, empty error, no valid views listed
    Evidence: .sisyphus/evidence/task-10-invalid-view.json
  ```

  **Commit**: YES
  - Message: `refactor(routes): unify 5 endpoints into /api/data?view=... with 307 redirects`
  - Files: `app/routes.py`, `tests/test_routes.py`

- [x] 11. **Frontend layout skeleton: CSS grid + sticky header + panel placeholders**

  **What to do**:
  - Rewrite `app/templates/index.html` — replace existing layout with new compact grid
  - **Sticky header**: Keep existing header structure (title, DB path, granularity toggle, date range) but make `position: sticky; top: 0; z-index: 100`
  - **Overview cards row**: 4 cards + 3 model efficiency mini cards in a single row: `grid-template-columns: repeat(4, 1fr)` for main cards, `repeat(3, 1fr)` for mini cards, or combined `repeat(7, 1fr)`
  - **Main grid**: `display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-md)` for all panels
  - **Panel slots**: Create empty placeholder divs with proper IDs for: heatmap (`heatmap-chart`), top-sessions (`top-sessions-chart`), by-model (`model-chart`, keep existing ID), by-project (`project-chart`), by-agent (`agent-chart`), cost-breakdown (`cost-chart`), cache-efficiency (`cache-chart`), mini-time-series (`mini-ts-chart`)
  - Each panel follows consistent pattern: `.chart-container.half` (280px height) with `.chart-overlay` for loading/error states and `.chart-inner` for ECharts
  - **Mini time-series at bottom**: `.chart-container.mini` (150px height), full-width, below the 2-column grid
  - Keep dark theme CSS variables intact, add only layout changes
  - Keep existing responsive breakpoints (1200px, 768px), verify grid stacks to 1 column

  **Must NOT do**:
  - Don't add JavaScript/chart rendering logic yet (just HTML+CSS skeleton)
  - Don't remove the header controls (granularity toggle, date range presets)
  - Don't change the `_jinja_env` template loading in routes.py

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES — layout skeleton has no JS dependencies
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 12-18
  - **Blocked By**: None (pure HTML+CSS)

  **References**:
  - `app/templates/index.html:1-456` — Full CSS: variables, design tokens, header, chart containers. Preserve system while reflowing.
  - `app/templates/index.html:458-591` — HTML body structure — understand what elements exist
  - `app/templates/index.html:62-66` — Header CSS `.header` — adapt to `position: sticky`

  **Acceptance Criteria**:
  - [ ] Page loads with sticky header + overview cards + 2-column grid of 6 panel placeholders + mini TS placeholder
  - [ ] At 1920px: 2 columns for panels
  - [ ] At 1024px: 1 column for panels
  - [ ] No horizontal scrollbar at any width
  - [ ] Dark theme colors preserved
  - [ ] Each panel has loading overlay with "Loading..." text

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Layout renders all panel slots at 1080p
    Tool: Playwright
    Preconditions: Server running on port 20230
    Steps:
      1. page.setViewportSize({ width: 1920, height: 1080 })
      2. page.goto('http://127.0.0.1:20230')
      3. page.waitForLoadState('networkidle')
      4. Count elements matching '.chart-container' -> expect >= 8
      5. page.screenshot({ path: '.sisyphus/evidence/task-11-layout-1080p.png', fullPage: true })
    Expected Result: 8+ chart containers visible, no horizontal scrollbar, sticky header
    Failure Indicators: < 8 containers, horizontal scrollbar, header not sticky
    Evidence: .sisyphus/evidence/task-11-layout-1080p.png

  Scenario: Responsive layout at 1024px
    Tool: Playwright
    Preconditions: Server running
    Steps:
      1. page.setViewportSize({ width: 1024, height: 768 })
      2. page.goto('http://127.0.0.1:20230')
      3. page.screenshot({ path: '.sisyphus/evidence/task-11-layout-1024px.png', fullPage: true })
    Expected Result: Panels stack 1 column, no horizontal scroll
    Evidence: .sisyphus/evidence/task-11-layout-1024px.png
  ```

  **Commit**: YES
  - Message: `feat(ui): compact grid layout skeleton with sticky header and 8 panel slots`
  - Files: `app/templates/index.html`

- [x] 12. **Frontend: Overview cards + Model efficiency mini cards**

  **What to do**:
  - Add 3 new mini efficiency cards: Avg Cost/1K tokens, Cache Hit Rate, Top Agent
  - Fetch from `/api/data?view=model-efficiency` — compute weighted avg cost/1K, fetch from `/api/data?view=cache-efficiency` for overall ratio, fetch from `/api/data?view=agent-breakdown` for #1 agent
  - Use existing card CSS (`.card`, `.card-icon`, `.card-value`, `.card-label`)
  - Cards update on date range change via `loadAllData()`

  **Recommended Agent Profile**: `visual-engineering` | **Skills**: []
  **Parallelization**: YES — with Tasks 13-17 | **Wave 3** | **Blocks**: Task 18 | **Blocked By**: 10, 11

  **References**:
  - `app/templates/index.html:502-524` — Existing overview card HTML — replicate pattern
  - `app/templates/index.html:718-743` — `loadOverview()` JS — data binding pattern
  - `app/templates/index.html:600-618` — `fmtNum()`, `fmtCost()` — reuse

  **Acceptance Criteria**:
  - [ ] 7 cards visible (4 original + 3 new)
  - [ ] Avg Cost/1K shows dollar amount, Cache Hit Rate shows %, Top Agent shows name + share
  - [ ] Cards update on date range change

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: All 7 cards populated
    Tool: Playwright
    Preconditions: Server running
    Steps:
      1. page.goto('http://127.0.0.1:20230')
      2. page.waitForSelector('.card-value', { timeout: 10000 })
      3. Count .card -> expect 7
      4. Verify no card-value is '--' or 'Error'
      5. page.screenshot({ path: '.sisyphus/evidence/task-12-cards.png' })
    Evidence: .sisyphus/evidence/task-12-cards.png
  ```

  **Commit**: YES
  - Message: `feat(ui): add model efficiency mini cards (cost/1K, cache rate, top agent)`
  - Files: `app/templates/index.html`

- [x] 13. **Frontend: Usage heatmap panel (ECharts heatmap)**

  **What to do**:
  - Fetch `/api/data?view=usage-heatmap`, pivot `[{day_of_week, hour, total_tokens}]` to `[day, hour, value]`
  - X-axis: 24 hours (labeled "00:00"–"23:00"), Y-axis: 7 days (Sun–Sat, Sunday top)
  - ECharts `visualMap` dark-blue-to-green color scale, 280px height
  - Tooltip: "Sunday 14:00 — 12.5K tokens", UTC label on axis
  - Zero cells = dark background

  **Recommended Agent Profile**: `visual-engineering` | **Skills**: []
  **Parallelization**: YES — with 12, 14-17 | **Wave 3** | **Blocks**: 18 | **Blocked By**: 10, 11

  **References**:
  - `app/templates/index.html:686-708` — `baseOption()` wrapper
  - ECharts heatmap: `https://echarts.apache.org/en/option.html#series-heatmap`

  **Acceptance Criteria**: Heatmap 7×24, color proportional to volume, tooltip with data, UTC labeled

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Heatmap renders and tooltip works
    Tool: Playwright
    Steps:
      1. page.goto('http://127.0.0.1:20230')
      2. page.waitForSelector('#heatmap-chart canvas', { timeout: 10000 })
      3. page.screenshot({ path: '.sisyphus/evidence/task-13-heatmap.png' })
    Evidence: .sisyphus/evidence/task-13-heatmap.png
  ```

  **Commit**: YES
  - Message: `feat(ui): add usage heatmap panel (day × hour, ECharts heatmap)`
  - Files: `app/templates/index.html`

- [x] 14. **Frontend: Top sessions leaderboard panel**

  **What to do**:
  - Fetch `/api/data?view=top-sessions&limit=10`, render horizontal bar chart
  - Bars labeled with session title (truncated 50 chars), colored by project
  - Tooltip: full title, project, input/output/reasoning/cache breakdown, message count, cost
  - Sorted ascending (most tokens at top), 280px height

  **Recommended Agent Profile**: `visual-engineering` | **Skills**: []
  **Parallelization**: YES — with 12-13, 15-17 | **Wave 3** | **Blocks**: 18 | **Blocked By**: 10, 11

  **References**:
  - `app/templates/index.html:831-920` — `renderModelBreakdown()` — identical horizontal bar pattern

  **Acceptance Criteria**: 10 bars, sorted by tokens, tooltip shows full breakdown

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Top sessions renders 10 bars
    Tool: Playwright
    Steps:
      1. page.goto('http://127.0.0.1:20230')
      2. page.waitForSelector('#top-sessions-chart canvas', { timeout: 10000 })
      3. page.screenshot({ path: '.sisyphus/evidence/task-14-top-sessions.png' })
    Evidence: .sisyphus/evidence/task-14-top-sessions.png
  ```

  **Commit**: YES
  - Message: `feat(ui): add top sessions leaderboard panel`
  - Files: `app/templates/index.html`

- [x] 15. **Frontend: By Model + By Project panels (preserved, compacted)**

  **What to do**:
  - Adapt existing `renderModelBreakdown()` and `renderProjectBreakdown()` to new layout
  - Fetch from `/api/data?view=tokens-by-model` and `/api/data?view=tokens-by-project` (same data, new API path)
  - Shrink from 360px to 280px height to fit 2-column grid
  - Reduce `barMaxWidth` from 24 to 18 for denser display
  - Keep all existing features: provider-colored bars, tooltip with full breakdown, sorted ascending
  - Y-axis labels truncated to 140px (down from 170px) to fit narrower panel

  **Must NOT do**:
  - Don't change the chart type or data structure
  - Don't remove the existing tooltip details

  **Recommended Agent Profile**: `visual-engineering` | **Skills**: []
  **Parallelization**: YES — with 12-14, 16-17 | **Wave 3** | **Blocks**: 18 | **Blocked By**: 10, 11

  **References**:
  - `app/templates/index.html:831-999` — `renderModelBreakdown()` + `renderProjectBreakdown()` — adapt these exactly

  **Acceptance Criteria**: Both charts render at 280px, data matches old endpoints, tooltips intact

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Model + Project charts render correctly
    Tool: Playwright
    Steps:
      1. page.goto('http://127.0.0.1:20230')
      2. page.waitForSelector('#model-chart canvas, #project-chart canvas', { timeout: 10000 })
      3. Verify both chart heights = 280px
      4. page.screenshot({ path: '.sisyphus/evidence/task-15-model-project.png' })
    Evidence: .sisyphus/evidence/task-15-model-project.png
  ```

  **Commit**: YES
  - Message: `feat(ui): adapt model + project charts to compact 280px panels`
  - Files: `app/templates/index.html`

- [x] 16. **Frontend: By Agent + Cost Breakdown panels**

  **What to do**:
  - **By Agent**: New horizontal bar chart — fetch `/api/data?view=agent-breakdown`, render like model breakdown but grouped by agent. Color by agent name with distinct palette.
  - **Cost Breakdown**: Adapt existing `renderCostBreakdown()` — fetch from `/api/data?view=cost-breakdown`, shrink to 280px, reduce `barMaxWidth` to 18
  - Both panels in the same 2-column row, 280px height each
  - Agent tooltip: agent name, input/output/reasoning/cache tokens, message count

  **Must NOT do**:
  - Don't separate agent and mode (merged per Metis feedback)

  **Recommended Agent Profile**: `visual-engineering` | **Skills**: []
  **Parallelization**: YES — with 12-15, 17 | **Wave 3** | **Blocks**: 18 | **Blocked By**: 10, 11

  **References**:
  - `app/templates/index.html:831-920` — `renderModelBreakdown()` — same pattern for agent chart
  - `app/templates/index.html:1001-1083` — `renderCostBreakdown()` — adapt API path + height

  **Acceptance Criteria**: Agent chart shows 20 agents sorted by tokens, cost chart matches old data

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Agent + Cost panels render
    Tool: Playwright
    Steps:
      1. page.goto('http://127.0.0.1:20230')
      2. page.waitForSelector('#agent-chart canvas, #cost-chart canvas', { timeout: 10000 })
      3. page.screenshot({ path: '.sisyphus/evidence/task-16-agent-cost.png' })
    Evidence: .sisyphus/evidence/task-16-agent-cost.png
  ```

  **Commit**: YES
  - Message: `feat(ui): add agent breakdown chart + compact cost breakdown`
  - Files: `app/templates/index.html`

- [x] 17. **Frontend: Cache efficiency trend + Mini time-series panels**

  **What to do**:
  - **Cache efficiency trend**: Line chart — fetch `/api/data?view=cache-efficiency`, plot `cache_hit_ratio` as line (green), `cache_read` as area (blue), `input` as area (orange). Shows trend over time. 280px height.
  - **Mini time-series**: Shrink existing 5-series stacked area to 150px single-line chart. Fetch `/api/data?view=tokens-by-date&granularity=day`. Show only `total` (sum of all token types) as a single smooth line. Legend hidden. X-axis labels compressed. Clicking the mini-chart does NOT expand it (no drill-down per guardrails). Full-width below the 2-column grid.

  **Must NOT do**:
  - Don't show 5 stacked series at 150px (unreadable per Metis)
  - Don't add click-to-expand interactivity

  **Recommended Agent Profile**: `visual-engineering` | **Skills**: []
  **Parallelization**: YES — with 12-16 | **Wave 3** | **Blocks**: 18 | **Blocked By**: 10, 11

  **References**:
  - `app/templates/index.html:746-829` — `renderTimeSeries()` — shrink and simplify for mini chart
  - `app/db.py:172-213` — `get_tokens_by_date()` — data source for time-series

  **Acceptance Criteria**: Cache line chart shows hit ratio trend, mini chart is 150px with single total-tokens line

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Mini time-series is exactly 150px
    Tool: Playwright
    Steps:
      1. page.goto('http://127.0.0.1:20230')
      2. page.waitForSelector('#mini-ts-chart canvas', { timeout: 10000 })
      3. const h = await page.evaluate(() => document.getElementById('mini-ts-chart').offsetHeight)
      4. Verify h = 150 (within 5px tolerance)
      5. page.screenshot({ path: '.sisyphus/evidence/task-17-mini-ts.png' })
    Evidence: .sisyphus/evidence/task-17-mini-ts.png
  ```

  **Commit**: YES
  - Message: `feat(ui): add cache efficiency trend chart + shrink time-series to 150px mini`
  - Files: `app/templates/index.html`

- [x] 18. **Frontend: Wire up JS — data fetching, granularity, date range, resize**

  **What to do**:
  - Update `loadAllData()` to fetch from unified `/api/data?view=...` instead of 5 separate endpoints
  - Map granularity toggle to update time-series mini chart (`/api/data?view=tokens-by-date&granularity=...`)
  - Map date range presets + custom inputs to re-fetch ALL panels (overview, all 9 charts)
  - Ensure all `showOverlay()` / `hideOverlays()` calls work for all 9+ chart instances
  - Update `initChart()` calls for all new chart IDs
  - Keep debounced window resize handler that calls `.resize()` on all chart instances
  - Remove old endpoint-specific fetch functions (`loadOverview()`, `loadTimeSeries()`, etc.) and consolidate into `loadAllData()`
  - Add error handling: if any `/api/data` call fails, show error overlay on that specific panel only
  - Update `apiFetch()` to use new base path `/api/data`

  **Must NOT do**:
  - Don't change the granularity toggle or date range preset HTML structure
  - Don't add polling/auto-refresh

  **Recommended Agent Profile**: `visual-engineering` | **Skills**: []
  **Parallelization**: NO (depends on all panels being implemented) | **Wave 3 (last)** | **Blocked By**: 12-17

  **References**:
  - `app/templates/index.html:596-1234` — Entire JS section — understand all state management, fetch functions, event handlers, resize handler before consolidating
  - `app/templates/index.html:1085-1134` — `loadAllData()` — primary function to refactor
  - `app/templates/index.html:1136-1164` — Granularity toggle handler
  - `app/templates/index.html:1166-1200` — Date range preset handler
  - `app/templates/index.html:1217-1223` — Resize handler

  **Acceptance Criteria**:
  - [ ] Page loads: all 9 charts + 7 cards fetch data and render without JS errors
  - [ ] Granularity toggle updates mini time-series only
  - [ ] Date range change updates ALL panels
  - [ ] Window resize triggers `.resize()` on all charts
  - [ ] Zero `console.error` on initial load
  - [ ] Loading overlays appear then disappear for each panel
  - [ ] Error overlays appear on failed API calls (per-panel, not global)

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Full page load without JS errors
    Tool: Playwright
    Preconditions: Server running
    Steps:
      1. page.on('console', msg => { if (msg.type() === 'error') console.log('CONSOLE ERROR:', msg.text()) })
      2. page.goto('http://127.0.0.1:20230')
      3. page.waitForLoadState('networkidle')
      4. page.waitForTimeout(3000)  // let all charts render
      5. Verify zero console errors
      6. page.screenshot({ path: '.sisyphus/evidence/task-18-full-page.png', fullPage: true })
    Expected Result: All panels populated, no console errors
    Failure Indicators: Any console.error, missing charts, "Error loading data" overlays
    Evidence: .sisyphus/evidence/task-18-full-page.png

  Scenario: Date range change updates all panels
    Tool: Playwright
    Steps:
      1. page.goto('http://127.0.0.1:20230')
      2. page.waitForLoadState('networkidle')
      3. page.click('#range-presets button[data-range="7d"]')
      4. page.waitForTimeout(2000)
      5. Verify overview card values changed
      6. page.screenshot({ path: '.sisyphus/evidence/task-18-date-range.png', fullPage: true })
    Expected Result: All panels refresh with filtered data
    Evidence: .sisyphus/evidence/task-18-date-range.png

  Scenario: Granularity toggle updates mini time-series
    Tool: Playwright
    Steps:
      1. page.goto('http://127.0.0.1:20230')
      2. page.waitForLoadState('networkidle')
      3. page.click('#granularity-toggle button[data-granularity="month"]')
      4. page.waitForTimeout(2000)
      5. Verify mini time-series axis labels changed to monthly
      6. Verify other panels did NOT reload (no flash/flicker)
    Expected Result: Only time-series updates, other panels unchanged
    Evidence: .sisyphus/evidence/task-18-granularity.png
  ```

  **Commit**: YES
  - Message: `feat(ui): wire up unified data fetching, granularity/date/resize handlers for all panels`
  - Files: `app/templates/index.html`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for violations. Check evidence files exist in `.sisyphus/evidence/`.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [18/18] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run pytest -v` (all tests pass). Review all changed files for: `console.log` in prod, commented-out code, unused imports, hardcoded paths. Check Python typing, SQL injection surface.
  Output: `Tests [N pass/N fail] | Lint [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill)
  Start from clean state (`uv run python -m app.main`). Execute ALL QA scenarios from every task. Test: page load, date range change, granularity toggle, resize to 1024px, invalid API view. Test edge cases: empty DB, single data point. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec. Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [18/18 compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Wave | Tasks | Commit Message | Files |
|------|-------|---------------|-------|
| 1 | 1, 3 | `test(conftest): expand fixtures + feat(db): add COALESCE helpers and view types` | `tests/conftest.py`, `app/db.py`, `app/routes.py` |
| 1 | 2 | (no commit — findings only) | — |
| 1 | 4 | `test(db): add failing tests for 6 new query functions (TDD RED)` | `tests/test_db.py` |
| 2 | 5 | `feat(db): add get_agent_breakdown query + route view` | `app/db.py`, `app/routes.py`, `tests/test_db.py`, `tests/test_routes.py` |
| 2 | 6 | `feat(db): add get_model_efficiency query with cost/I-O/cache ratios` | `app/db.py`, `app/routes.py`, `tests/test_db.py`, `tests/test_routes.py` |
| 2 | 7 | `feat(db): add get_usage_heatmap query (day-of-week x hour grid)` | `app/db.py`, `app/routes.py`, `tests/test_db.py`, `tests/test_routes.py` |
| 2 | 8 | `feat(db): add get_top_sessions query with session+project JOIN` | `app/db.py`, `app/routes.py`, `tests/test_db.py`, `tests/test_routes.py` |
| 2 | 9 | `feat(db): add get_cache_efficiency query with daily cache hit ratio` | `app/db.py`, `app/routes.py`, `tests/test_db.py`, `tests/test_routes.py` |
| 2 | 10 | `refactor(routes): unify 5 endpoints into /api/data?view=... with 307 redirects` | `app/routes.py`, `tests/test_routes.py` |
| 3 | 11 | `feat(ui): compact grid layout skeleton with sticky header and 8 panel slots` | `app/templates/index.html` |
| 3 | 12-17 | `feat(ui): add all new chart panels (efficiency cards, heatmap, sessions, agent, cache, mini-TS)` | `app/templates/index.html` |
| 3 | 18 | `feat(ui): wire up unified data fetching, granularity/date/resize handlers` | `app/templates/index.html` |

**Pre-commit check for ALL commits**: `uv run pytest -v` must pass (with TDD RED phase expected to have N failing tests before GREEN).

---

## Success Criteria

### Verification Commands
```bash
# All tests pass
uv run pytest -v
# Expected: N passed, 0 failed (after GREEN phase)

# Server starts without errors
uv run python -m app.main --port 20231
# Expected: [startup] OK - database file exists

# Unified API works
curl -s http://127.0.0.1:20231/api/data?view=overview | python -m json.tool
# Expected: JSON with total_tokens, total_cost, etc.

# Backward compatibility
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:20231/api/overview
# Expected: 307

# New views return data
curl -s http://127.0.0.1:20231/api/data?view=agent-breakdown | python -m json.tool
# Expected: JSON array with agent, total_tokens, etc.
```

### Final Checklist
- [x] All 18 implementation tasks completed
- [x] All "Must Have" present (unified endpoint, redirects, compact layout, 8+ new dimensions)
- [x] All "Must NOT Have" absent (no new deps, no main.py changes, no drill-down/polling/theme toggle, no session productivity/error-rate/response-time charts)
- [x] 45 existing tests + ~25 new tests = ~70 tests all passing (99 total)
- [x] Dashboard loads without JS errors at 1080p, 1024px
- [x] Time-series mini chart exactly 150px height
- [x] All panels show loading → data transitions correctly
- [x] Date range filtering updates all panels consistently
- [x] Backward-compatible: all 5 old endpoints return 307 redirects
- [x] F1-F4 verification wave all APPROVE
