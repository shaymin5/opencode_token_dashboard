# TEST PACKAGE

**Framework:** pytest 9.x + httpx

## OVERVIEW

117 tests (68 unit + 49 integration) across 37 classes. Zero mocking. Real SQLite temp DB per test. No pytest config, no parametrize, no markers.

## STRUCTURE

```
tests/
├── conftest.py      # Fixtures: test_db_path, test_conn (21 messages, 10 sessions)
├── test_db.py       # 68 DB query tests (20 classes)
└── test_routes.py   # 49 API route tests (17 classes)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add DB query test | `tests/test_db.py` | Create `Test<FunctionName>` class, import function |
| Add API route test | `tests/test_routes.py` | Create `TestApi<Endpoint>`, use `client` fixture |
| Add test data | `tests/conftest.py` | Modify `_insert_fixture_data()`, update hardcoded assertions |

## KEY CONVENTIONS

- **100% class-based** — no standalone test functions (even for single-method tests)
- **Class naming**: `Test<FunctionName>` (DB), `TestApi<Endpoint>` (routes); date-filter variants: `<Base>WithDateFilter`
- **No `@pytest.mark.parametrize`** — variations as separate methods (e.g., 5 date-filter methods instead of 1 parametrized test)
- **No mocking** — zero `unittest.mock` or `monkeypatch` (except 1 env-var test in `TestGetDbPath`)
- **No `pytest.raises`** — no exception-path tests for any function
- **No pytest markers** — no `@pytest.mark.skip`, `@pytest.mark.xfail`, or custom markers
- **Assertions**: plain `assert` statements, hard-coded fixture counts (brittle)

### Fixtures
- `test_db_path` — temp `.db` file on disk (not `:memory:`), full schema + 21 messages spanning 4 months
- `test_conn` — read-only connection (`PRAGMA query_only = 1`) with `sqlite3.Row`
- Route tests: `app_with_test_db` (fresh `FastAPI` + dependency override, not real `app.main`) + `client` (`TestClient`)
- All function-scoped (default), no shared state between tests

### Fixture Data Edge Cases (21 messages)
- Models: deepseek-v4-flash, MiniMax-M2.7, glm-4.7, gpt-5-nano, mimo-v2-pro-free
- Agents: build, oracle, explore, null (missing `agent` key)
- Cost: 0.0 (free), $0.50 (high), NULL (missing)
- Tokens: normal values, zeros, NULLs
- Nested model JSON (`$.model.modelID`), error fields, timing metadata
- Date range: Feb–May 2026 for date-filter testing

## MODULE-SPECIFIC ANTI-PATTERNS

- Inline imports in `test_db.py` — `TestGetAgentBreakdown` et al. re-import their function inside the class (20+ inline imports, while 9 functions are at module top-level — inconsistent hybrid)
- Stale docstring in `test_db.py:1`: says "all 7 query functions" — actually 10+ query functions plus utilities
- "Temp" test in `test_db.py:420-421` — `or len(data) == 0` clause lets it pass even when assertion fails, defeating test purpose
- No parametrize — leads to method duplication (e.g., 5 date-filter methods instead of 1 parametrized test)
- Hard-coded assertion counts (`assert total_messages == 21`) break when fixture changes
- Stale comments in `test_routes.py:425,452`: "not yet implemented" for features already implemented (unified endpoint, backward-compat redirects)
- Duplicate `import json` with `# noqa: F811` workaround in conftest.py — outer `import json` is dead code; only the inner `import json as _json` in `msg_data()` closure is needed
