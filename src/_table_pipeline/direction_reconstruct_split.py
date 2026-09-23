"""Q5 + pure horizontal placement slicing; other splits keep fresh TGIF."""
import pymupdf
from pymupdf import table

from pymupdf4llm._table_pipeline.grid_reconstruct_split import GridReconstructSplitPipeline, refinement_geometry


def pure_horizontal(parts, row_count, col_count):
    """Use actual disjoint column ranges, never the detector summary alone."""
    if len(parts) < 2 or any(tuple(p["rows"]) != (0, row_count) for p in parts):
        return False
    ranges = sorted(tuple(p["cols"]) for p in parts)
    return (ranges[0][0] == 0 and ranges[-1][1] == col_count
            and all(a < b for a, b in ranges)
            and all(left[1] == right[0] for left, right in zip(ranges, ranges[1:])))


class DirectionReconstructSplitPipeline(GridReconstructSplitPipeline):
    defer_parent_roles = True

    def split_table(self, page, tab):
        pending = getattr(self, "_pending_parent_roles", None)
        if pending is None:
            return super().split_table(page, tab)
        grid, region = pending.pop(id(tab.placements))
        if grid is not tab.placements:
            raise RuntimeError("Deferred R6 grid identity changed")
        children = super().split_table(page, tab)
        if any(child is tab for child in children):
            # Native find_tables restored rotation and text geometry on return.
            # Reuse the existing post-finder refinement scope for this same grid.
            with refinement_geometry(page) as current:
                tab.placements, region = self.header.apply_roles(current, grid, region)
            tab.header_rows, tab.section_rows = region.top_header_rows, region.section_header_rows
        # Replaced parents have no downstream role consumer. Fresh/reused child
        # cells already received their own R6 call in the existing split path.
        return children

    def slice_children(self, page, tab, parts, grids, event):
        nr, nc = event["parent_shape"]
        if not pure_horizontal(parts, nr, nc):
            return None  # Vertical/mixed split: existing child TGIF + refine.
        with refinement_geometry(page) as current:
            return self._slice_children(current, tab, parts, grids, event)

    def _slice_children(self, page, tab, parts, grids, event):
        children = []
        for part, grid in zip(parts, grids):
            cells = [tuple(c.bbox) for row in grid for c in row if c.bbox is not None]
            child = table.Table(page, cells, bbox=pymupdf.Rect(part["bbox"]))
            # Re-evaluate each child's header using the same frozen R6 contract.
            # The preliminary region supplies existing title/section context,
            # not the final header depth. Never inherit the parent's R6 labels.
            region = table.find_header_region(table._refine_placements_text_grid(grid))
            table._refine_tag_grid(grid, region.top_header_rows)
            child.placements, region = self.header.apply_roles(page, grid, region)
            child.header_rows, child.section_rows = region.top_header_rows, region.section_header_rows
            child.textpage, child._chars = tab.textpage, tab._chars
            child.bbox_provenance = dict(tab.bbox_provenance, bbox_source="region_split",
                grid_source="tgif", bbox_operation="grid_split_slice",
                parent_bbox_source=tab.bbox_provenance["bbox_source"], parent_bbox=list(tab.bbox))
            children.append(child)
        self.events.append({**event, "status": "split", "reconstruction": "placement_slice",
                            "extra_tgif_calls": 0, "children": [list(t.bbox) for t in children]})
        return children
