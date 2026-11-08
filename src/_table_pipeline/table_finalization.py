"""Consume actual pending roles and sequence installed finalizers."""
import pymupdf
from pymupdf import table
from .placement_material import envelope, _cells_bbox
from .grid_reconstruct_split import refinement_geometry


class TableFinalization:
    defer_parent_roles = True

    def __init__(self, runtime):
        self.runtime = runtime
        self.errors = runtime.errors
        self.events = []
        self._pending_parent_roles = None
        self._trials = []
        self._material = None
        self.finalizers = []

    @property
    def header(self):
        return self.runtime.header

    def _begin_page(self, material):
        if material is not self._material:
            self._trials.clear()
            self._material = material

    def _make_table(self, page, grid, base, operation):
        boxes = [tuple(c.bbox) for row in grid for c in row if c.bbox is not None]
        if not boxes:
            raise ValueError('Independent table has no concrete cell geometry')
        out = table.Table(page, boxes, bbox=pymupdf.Rect(_cells_bbox([boxes])))
        out.placements = grid
        out.textpage, out._chars = base.textpage, base._chars
        # These values are transport/diagnostic annotations, never predicates.
        out.bbox_provenance = dict(getattr(base, 'bbox_provenance', {}),
                                   bbox_operation=operation)
        return out

    def _roles(self, page, tab, region):
        with refinement_geometry(page) as current:
            tab.placements, region = self.header.apply_roles(
                current, tab.placements, region, table_bbox=envelope(tab))
        tab.header_rows, tab.section_rows = region.top_header_rows, region.section_header_rows
        return tab


    def split_table(self, page, tab):
        pending = self._pending_parent_roles
        region = None
        if pending is not None:
            grid, region = pending.pop(id(tab.placements))
            if grid is not tab.placements:
                raise RuntimeError('Deferred R6 grid identity changed')
        material = self.runtime.page_material(page)
        self._begin_page(material)
        return [self._roles(page, tab, region)] if region is not None else [tab]

    def finalize_tables(self, page, tables):
        material = self.runtime.page_material(page)
        self._begin_page(material)
        for consume in self.finalizers:
            tables = consume(page, tables, material)
        return tables
