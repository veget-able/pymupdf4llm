"""Isolated post-TGIF material-integrated split, without V7 pre-split or R6."""

import pymupdf
from pymupdf import table, _table_union as union
from pymupdf._table_spans import SpanCell
from pymupdf4llm.helpers.table_html.reconstruct import _placement_grid_matrices, _table_grid_matrices

from pymupdf4llm._table_pipeline.deferred_tgif import DeferredTGIFPipeline
from pymupdf4llm._table_pipeline import material_split_rules as rules


def partition_placements(placements, parts, *, shape=None):
    """Move each resolved cell once, intact. Reject cuts crossing any cell.

    Includes empty cells: no special text/GT-dependent escape hatch. The
    caller preserves the complete original table on rejected proposals.
    """
    # Internal callers already derived this shape from the unchanged grid.
    nr, nc = _placement_grid_matrices(placements)[:2] if shape is None else shape
    ownership = {}
    children = []
    for pi, part in enumerate(parts):
        r0, r1 = part["rows"]
        c0, c1 = part["cols"]
        if not (0 <= r0 < r1 <= nr and 0 <= c0 < c1 <= nc):
            raise ValueError("Invalid split row/column extent")
        children.append([[] for _ in range(r1-r0)])
        for r in range(r0, r1):
            for c in range(c0, c1):
                if (r, c) in ownership:
                    raise ValueError("Overlapping split slot ranges")
                ownership[r, c] = pi
    if len(ownership) != nr * nc:
        raise ValueError("Split ranges do not cover original grid")
    occupied = set()
    for ri, row in enumerate(placements):
        ci = 0
        for cell in row:
            while (ri, ci) in occupied:
                ci += 1
            slots = {(r, c) for r in range(ri, ri+cell.rowspan)
                     for c in range(ci, ci+cell.colspan)}
            owners = {ownership[s] for s in slots}
            if len(owners) != 1:
                return None, {"reason": "crossing_merged_cell", "row": ri, "column": ci,
                              "rowspan": cell.rowspan, "colspan": cell.colspan}
            pi = owners.pop()
            children[pi][ri-parts[pi]["rows"][0]].append(
                cell.clone())
            occupied.update(slots)
            ci += cell.colspan
    for part, child in zip(parts, children):
        r0, r1 = part["rows"]
        c0, c1 = part["cols"]
        if _placement_grid_matrices(child)[:2] != (r1-r0, c1-c0):
            raise ValueError("Child span extent changed during transfer")
    assert sum(map(len, placements)) == sum(len(row) for child in children for row in child)
    return children, None
