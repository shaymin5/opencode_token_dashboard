# Heatmap Data Density Validation

**Date**: 2026-05-02
**Database**: Real opencode.db

## Results

| Metric | Value |
|--------|-------|
| Total cells (7×24) | 168 |
| Cells with data | 86 |
| Non-zero cells | 86 |
| Fill rate | 51.2% |
| Query time | 0.168s |

## Assessment

- **Fill rate**: 51.2% — borderline sparse. Above 50% means the heatmap will show visible patterns, but many cells will be dark.
- **Performance**: Very fast (168ms) — no concerns.
- **Plan Impact**: Proceed with heatmap at lower visual priority as per plan. Consider larger cells or aggregating to 2-hour buckets if fill rate proves too sparse in visual testing.

## Raw Data Sample

```
dow=0 hour=02 cnt=209   dow=0 hour=03 cnt=402   dow=0 hour=04 cnt=131
dow=0 hour=05 cnt=301   dow=0 hour=06 cnt=153   dow=0 hour=07 cnt=273
dow=0 hour=08 cnt=268   dow=0 hour=09 cnt=406   dow=0 hour=10 cnt=616
dow=0 hour=11 cnt=495   dow=0 hour=12 cnt=603   dow=0 hour=13 cnt=433
dow=0 hour=14 cnt=451   dow=0 hour=15 cnt=641   dow=0 hour=16 cnt=553
```
