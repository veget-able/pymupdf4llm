"""Shared placement copying/rectangle geometry, with no ownership policy."""
from copy import copy
from .grid_geometry import _union_box

def _intersects(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])

def _updated(tab, rows, added_before, used):
    # Unlike content recovery's _replace, preserve section roles and never
    # classify a new row as a header. Existing cell objects are retained.
    child = copy(tab)
    child.placements = rows
    child.cells = [tuple(c.bbox) for row in rows for c in row if c.bbox is not None]
    child._bbox = tuple(_union_box(child.cells))
    child.section_rows = tuple(r + added_before for r in tab.section_rows)
    child.header_rows = 0 if added_before else tab.header_rows
    child.bbox_provenance = dict(tab.bbox_provenance,
        bbox_source='union_recovery', grid_source='mixed',
        bbox_operation='grid_node_absorption', recovery_revision='susan-grid-ownership/1',
        recovery_source_bboxes=[list(tab.bbox)],
        recovery_steps=list(tab.bbox_provenance.get('recovery_steps', [])) + ['grid_node_absorption'])
    child.grid_ownership_nodes = sorted(used)
    child.grid_roles_pending = True
    return child
