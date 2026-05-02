"""Validate heatmap data density on real production DB."""
from app.db import get_connection
import time

conn = get_connection()
start = time.time()
rows = conn.execute("""
  SELECT strftime('%w', datetime(time_created/1000, 'unixepoch')) as dow,
         strftime('%H', datetime(time_created/1000, 'unixepoch')) as hour,
         COUNT(*) as cnt
  FROM message
  WHERE json_extract(data, '$.tokens.input') IS NOT NULL
  GROUP BY dow, hour ORDER BY dow, hour
""").fetchall()
elapsed = time.time() - start
cells = len(rows)
non_zero = sum(1 for r in rows if r['cnt'] > 0)
total_cells = 168  # 7 days * 24 hours

print(f"Cells with data: {cells}/168")
print(f"Non-zero cells: {non_zero}")
print(f"Fill rate: {non_zero/total_cells*100:.1f}%")
print(f"Query time: {elapsed:.3f}s")

# Show some sample
for r in rows[:15]:
    print(f"  dow={r['dow']} hour={r['hour']} cnt={r['cnt']}")

conn.close()
