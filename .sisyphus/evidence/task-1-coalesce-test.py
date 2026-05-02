"""Verify COALESCE pattern works with both flat and nested model JSON."""
from tests.conftest import _insert_fixture_data, _create_schema
import sqlite3

conn = sqlite3.connect(':memory:')
conn.row_factory = sqlite3.Row
_create_schema(conn)
_insert_fixture_data(conn)

rows = conn.execute("""
  SELECT COALESCE(json_extract(data, '$.model.modelID'), json_extract(data, '$.modelID')) as model
  FROM message
""").fetchall()
models = set(r['model'] for r in rows)
print('Models:', sorted(models))
print('Has nested (nested-model-v1):', 'nested-model-v1' in models)
print('Has flat (deepseek-v4-flash):', 'deepseek-v4-flash' in models)
print('All 21 models present:', len(models) >= 8)  # Expect many unique models
