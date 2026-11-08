"""Shared grid-band geometry; no union or restoration policy."""

def _bands(iv, gap):
    out = []
    for lo, hi in sorted(iv):
        if out and lo <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out

def _union_box(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]

def _grid_rows_y(grid):
    """행별 y범위 — grid 행과 1:1 정렬(빈 행은 None)."""
    ys = []
    for r in grid:
        cs = [c for c in r if c is not None]
        ys.append([min(c[1] for c in cs), max(c[3] for c in cs)] if cs else None)
    return ys


def _leaf_intervals(intervals):
    """Disjoint bands for NEW cells; leave existing placements untouched.

    Tightest spanning anchors are not leaf partitions. Reuse native boundary
    clustering only when the proposed intervals overlap, and abstain when the
    existing logical slot count cannot be represented by those boundaries.
    """
    if not intervals or any(v is None for v in intervals):
        return intervals
    if any(lo >= hi for lo, hi in intervals):
        return [None] * len(intervals)
    if all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])):
        return intervals
    if any(a[0] > b[0] for a, b in zip(intervals, intervals[1:])):
        return [None] * len(intervals)
    from pymupdf._table_spans import _span_clustered_boundaries
    boundaries = _span_clustered_boundaries([x for band in intervals for x in band])
    if len(boundaries) != len(intervals) + 1:
        return [None] * len(intervals)
    return list(zip(boundaries, boundaries[1:]))
