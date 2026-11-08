"""Actual placement/source facts shared by their consumers."""
from collections import Counter
from typing import Optional


def _cells_bbox(cells_slice) -> Optional[list]:
    xs = [c for r in cells_slice for c in r if c]
    if not xs:
        return None
    return [min(c[0] for c in xs), min(c[1] for c in xs),
            max(c[2] for c in xs), max(c[3] for c in xs)]


def source_key(ref):
    return (ref.kind, id(ref.collection), ref.index, tuple(ref.scope),
            tuple(ref.bbox), ref.text, tuple(map(tuple, ref.glyph_boxes)))


def source_counts(tables):
    result = Counter()
    for tab in tables:
        for row in tab.placements:
            for cell in row:
                cell.validate_source_content()
                if cell.source_content is not None:
                    result.update(source_key(ref) for ref in cell.source_content.sources)
    return result


def placement_counts(tables):
    return Counter((tuple(cell.bbox) if cell.bbox is not None else None,
                    cell.rowspan, cell.colspan, cell.text,
                    tuple(source_key(ref) for ref in cell.source_content.sources)
                    if cell.source_content is not None else None)
                   for tab in tables for row in tab.placements for cell in row)


def grid_state(grid):
    return tuple(tuple((tuple(c.bbox) if c.bbox is not None else None,
                        c.rowspan, c.colspan, c.text,
                        tuple(source_key(ref) for ref in c.source_content.sources)
                        if c.source_content is not None else None)
                       for c in row) for row in grid)


def envelope(tab):
    boxes = [cell.bbox for row in tab.placements for cell in row if cell.bbox is not None]
    return tuple(_cells_bbox([boxes])) if boxes else None

