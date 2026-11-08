"""Refine actual immutable raw-grid inputs through the active producer."""
from contextlib import contextmanager
import pymupdf
from pymupdf import table
def refine_child(page, cells, bbox, metadata, parent):
    with refinement_geometry(page) as current:
        return _refine_child(current, cells, bbox, metadata, parent)


@contextmanager
def refinement_geometry(page):
    """Restore find_tables' geometry settings for post-finder refinement."""
    old_small = bool(pymupdf.TOOLS.set_small_glyph_heights())
    old_quad = pymupdf.TOOLS.unset_quad_corrections()
    rotation = None
    try:
        pymupdf.TOOLS.set_small_glyph_heights(True)
        if page.rotation:
            page, xref, angle, mediabox = table.page_rotation_set0(page)
            rotation = (xref, angle, mediabox)
        yield page
    finally:
        pymupdf.TOOLS.set_small_glyph_heights(old_small)
        if rotation is not None:
            table.page_rotation_reset(page, *rotation)
        pymupdf.TOOLS.unset_quad_corrections(old_quad)


def _refine_child(page, cells, bbox, metadata, parent):
    """Use the selected native/R6 refinement producer on the exact fresh grid."""
    flat = [tuple(c) for row in cells for c in row if c is not None]
    if not flat:
        raise ValueError('Fresh child refinement produced no cells')
    initial = table.Table(page, flat, bbox=pymupdf.Rect(bbox))
    initial.bbox_provenance = dict(metadata)
    output = []
    for child in table._refine_grid_tables(page, initial, input_grid=cells):
        child.textpage, child._chars = parent.textpage, parent._chars
        output.append(child)
    return output

