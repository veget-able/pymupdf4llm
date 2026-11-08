"""Pure structural-trial eligibility over current cell snapshots (T20)."""
from itertools import combinations
from pymupdf4llm.helpers.table_html.reconstruct import _table_grid_matrices
from .vg_rule_primitives import _tokens, _jaccard, x_iou, column_intervals


def snapshot(tab):
    nr, nc, cells, texts = _table_grid_matrices(tab, retain=True)
    return dict(tab=tab, rows=nr, cols=nc, texts=texts, columns=column_intervals(cells),
                first=_tokens([str(t or '') for t in texts[0]]),
                depth=tab.header_rows, bbox=list(tab.bbox))


def revert_eligible(parts):
    return (len(parts) >= 3 and len({p['cols'] for p in parts}) == 1
            and all(x_iou(a['bbox'], b['bbox']) >= .7 for a, b in combinations(parts, 2))
            and all(a['bbox'][3] <= b['bbox'][1] + 1e-4 for a, b in zip(parts, parts[1:]))
            and all(_jaccard(parts[0]['first'], p['first']) < .5 for p in parts[1:]))


def split_integrity_eligible(parts):
    """H5 candidate: region-split children that cannot stand as tables.

    ``parts`` are snapshots of one parent's children, sorted top-to-bottom
    then left-to-right. Returns the reason to revert to the whole parent, or
    None:

    - stacked children (pairwise x-IoU >= .7, vertically ordered) where a
      child below the first has no header row: the split cut a header block
      from its body;
    - side-by-side children (x-disjoint, pairwise y-IoU >= .7) where a child has one column: the
      split cut a label column from its values.
    """
    if len(parts) < 2:
        return None
    stacked = (all(x_iou(a['bbox'], b['bbox']) >= .7 for a, b in combinations(parts, 2))
               and all(a['bbox'][3] <= b['bbox'][1] + 1e-4 for a, b in zip(parts, parts[1:])))
    if stacked:
        return 'headerless_child' if any(p['depth'] == 0 for p in parts[1:]) else None
    by_x = sorted(parts, key=lambda p: p['bbox'][0])
    side = all(a['bbox'][2] <= b['bbox'][0] + 1e-4 for a, b in zip(by_x, by_x[1:]))
    # Reuse the same interval overlap contract as the vertical-stack check,
    # transposing axes. X separation alone also admits diagonal/unrelated tables.
    side = side and all(x_iou([a['bbox'][1], 0, a['bbox'][3], 0],
                              [b['bbox'][1], 0, b['bbox'][3], 0]) >= .7
                        for a, b in combinations(parts, 2))
    if side:
        return 'single_column_child' if any(p['cols'] == 1 for p in parts) else None
    return None
