# TEST PACKAGE

**Framework:** pytest 9.x + httpx

## OVERVIEW

99 tests (57 unit + 42 integration) across 36 classes. Zero mocking. Real SQLite temp DB per test. No pytest config, no parametrize, no markers.

## STRUCTURE

```
tests/
├── conftest.py      # Fixtures: test_db_path, test_conn (21 messages, 10 sessions)
├── test_db.py       # 57 DB query tests (20 classes)
└── test_routes.py   # 42 API route tests (16 classes)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add DB query test | `tests/test_db.py` | Create `Test<FunctionName>` class, import function |
| Add API route test | `tests/test_routes.py` | Create `TestApi<Endpoint>`, use `client` fixture |
| Add test data | `tests/conftest.py` | Modify `_insert_fixture_data()`, update hardcoded assertions |

## KEY CONVENTIONS

- **100% class-based** — no standalone test functions
- **Class naming**: `Test<FunctionName>` (DB), `TestApi<Endpoint>` (routes)
- **No `@pytest.mark.parametrize`** — variations as separate methods
- **No mocking** — zero `unittest.mock` or `monkeypatch` (except 1 env-var test)
- **No `pytest.raises`** — no exception-path tests
- **Assertions**: plain `assert` statements, hard-coded fixture counts

### Fixtures
- `test_db_path` — temp `.db` file on disk (not `:memory:`), full schema + 21 messages
- `test_conn` — read-only connection (`PRAGMA query_only = 1`) with `sqlite3.Row`
- Route tests: `app_with_test_db` (fresh `FastAPI` + dependency override) + `client` (`TestClient`)
- All function-scoped (default), no shared state between tests

### Fixture Data Edge Cases (21 messages)
- Models: deepseek-v4-flash, MiniMax-M2.7, glm-4.7, gpt-5-nano, mimo-v2-pro-free
- Agents: build, oracle, explore, null (missing `agent` key)
- Null tokens, zero tokens, null cost, very high cost ($0.50)
- Nested model JSON (`$.model.modelID`), error fields, timing metadata

## MODULE-SPECIFIC ANTI-PATTERNS

- Inline imports in `test_db.py` — `TestGetAgentBreakdown` et al. re-import their function inside the class
- No parametrize — leads to method duplication (e.g., 4 date-filter methods instead of 1 parametrized test)
- Hard-coded assertion counts (`assert total_messages == 21`) break when fixture changes
- Stale comments: "not yet implemented" labels for features already implemented
- Duplicate `import json` with `# noqa: F811` workaround in conftest.py
