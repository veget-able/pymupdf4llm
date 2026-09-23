"""Experimental V7 plus one grid-guided split with fresh child TGIF/refine."""
from types import SimpleNamespace
from contextlib import contextmanager

import numpy as np
import pymupdf
from pymupdf import table
from pymupdf4llm.helpers.table_html.reconstruct import _table_grid_matrices

from pymupdf4llm._table_pipeline.header_region_split import HeaderRegionSplitPipeline, child_inputs
from pymupdf4llm._table_pipeline.material_region_split import partition_placements
from pymupdf4llm._table_pipeline import material_split_rules as rules


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
    """Run the approved structural, V5, span and header sequence on fresh cells."""
    def make_child(flat, split):
        if not flat:
            raise ValueError("Fresh child refinement produced no cells")
        child = table.Table(page, flat, bbox=None if split else pymupdf.Rect(bbox))
        child.bbox_provenance = dict(metadata)
        if split:
            child.bbox_provenance.update(bbox_source="find_tables", bbox_operation="refine_split",
                parent_bbox_source=metadata["bbox_source"], parent_bbox=list(bbox))
        return child

    output = []
    for child in table._refine_grid_tables(
        page, cells, bbox, make_child, split_repeated_headers=True,
    ):
        child.textpage, child._chars = parent.textpage, parent._chars
        output.append(child)
    return output


def prepare_children(material, tab_bbox, parts):
    group, prediction, _ = material
    node_boxes = np.asarray(group["bboxes"])
    centers = (node_boxes[:, :2] + node_boxes[:, 2:]) / 2
    indices = [i for i, (x, y) in enumerate(centers)
               if tab_bbox[0] <= x <= tab_bbox[2] and tab_bbox[1] <= y <= tab_bbox[3]]
    subset = dict(group, bboxes=node_boxes[indices])
    image, local = prediction.args
    retained = SimpleNamespace(args=(image, local[indices]),
        kwargs={"texts": [prediction.kwargs["texts"][i] for i in indices]})
    parent = group["group_bbox"]
    boxes = [[max(p["bbox"][0], parent[0]), max(p["bbox"][1], parent[1]),
              min(p["bbox"][2], parent[2]), min(p["bbox"][3], parent[3])] for p in parts]
    # Existing V7 helper enforces one owner per original node and nonempty crops.
    return child_inputs(subset, retained, boxes)


class GridReconstructSplitPipeline(HeaderRegionSplitPipeline):
    def __init__(self, model):
        super().__init__(model)
        self.materials = {}

    def resolve(self, entry, page, evidence):
        group = entry[1].group
        prediction = group["table_grid"]
        # Retain references before DeferredPrediction.resolve releases inputs.
        retained = SimpleNamespace(predict=prediction.predict, args=prediction.args,
                                   kwargs=prediction.kwargs)
        key = (page.number, tuple(entry.bbox_provenance["source_gnn_indices"]))
        self.materials[key] = (dict(group), retained, entry[1].original_reader)
        return super().resolve(entry, page, evidence)

    def split_table(self, page, tab):
        meta = tab.bbox_provenance
        material = self.materials.get((page.number, tuple(meta.get("source_gnn_indices", []))))
        if material is None or meta.get("grid_source") != "tgif":
            return [tab]
        nr, nc, cells, texts = _table_grid_matrices(tab, retain=True)
        structure = {"bbox": list(tab.bbox), "cells": cells, "extract": texts}
        # Node splitting has already run under V7. Only additive grid signals.
        grid_signals = {}
        detection = rules.merge_detect([], [], [], list(tab.bbox), structure=structure, grid_signals=grid_signals)
        if not detection["merged"]:
            return [tab]
        parts = rules.grid_split(structure, nodes=[], edges=[], drawing_rects=[],
                                 grid_signals=grid_signals)
        event = {"stage": "grid_reconstruct_split", "parent_bbox": list(tab.bbox),
                 "parent_shape": [nr, nc], "detection": detection, "proposals": parts,
                 "source_gnn_indices": meta["source_gnn_indices"]}
        if len(parts) <= 1:
            self.events.append({**event, "status": "no_grid_boundary"})
            return [tab]
        grids, rejected = partition_placements(tab.placements, parts, shape=(nr, nc))
        if rejected:
            self.events.append({**event, "status": "preserved", **rejected})
            return [tab]
        sliced = self.slice_children(page, tab, parts, grids, event)
        if sliced is not None:
            return sliced
        try:
            prepared = prepare_children(material, tab.bbox, parts)
        except ValueError as exc:
            # Invalid/ambiguous geometric ownership must not lose or duplicate nodes.
            self.events.append({**event, "status": "preserved", "reason": str(exc)})
            return [tab]
        group, prediction, reader = material
        output = []
        for bbox, indices, image, local, texts in prepared:
            grid, _ = prediction.predict(image, local, texts=texts)
            if grid is None:
                raise ValueError("TGIF failed on grid-guided child")
            child_group = dict(group, group_bbox=bbox, table_grid=grid)
            entry, = reader(SimpleNamespace(layout_information=[child_group]))
            metadata = dict(meta, bbox_source="region_split", grid_source="tgif",
                bbox_operation="grid_split_reconstruct", parent_bbox_source=meta["bbox_source"],
                parent_bbox=list(tab.bbox))
            output.extend(refine_child(page, entry[1], bbox, metadata, tab))
        self.events.append({**event, "status": "split", "children": [list(t.bbox) for t in output],
                            "node_counts": [len(c[1]) for c in prepared],
                            "extra_tgif_calls": len(prepared)})
        return output

    def slice_children(self, page, tab, parts, grids, event):
        """Default candidate always reconstructs. Directional subclass may slice."""
        return None
