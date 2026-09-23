"""Accepted V7: original GNN nodes/edges -> region split -> per-region TGIF.

Used with the approved V-all component stack. V5-H is intentionally absent.
The native runtime owns the document-local deferred model and input lifetime.
"""
from types import SimpleNamespace
import numpy as np
from pymupdf import table, _table_union as union
from pymupdf4llm._table_pipeline.deferred_tgif import DeferredTGIFPipeline
from pymupdf4llm._table_pipeline.v7_region_rules import _region_band_split


def child_inputs(group, prediction, boxes):
    """Partition original nodes once; crop with BoxRFDGNN's integer convention."""
    parent = group["group_bbox"][:4]
    image, original_local_boxes = prediction.args
    texts = prediction.kwargs["texts"]
    node_boxes = np.asarray(group["bboxes"], dtype=float)
    if len(texts) != len(node_boxes):
        raise ValueError("TGIF text/node alignment mismatch")
    # Verify that the retained TGIF input really corresponds to these raw nodes.
    offset = np.array([parent[0], parent[1], parent[0], parent[1]])
    if not np.allclose(original_local_boxes + offset, node_boxes, atol=1e-4):
        raise ValueError("TGIF/page coordinate mismatch")
    centers = (node_boxes[:, :2] + node_boxes[:, 2:]) / 2
    members = [[] for _ in boxes]
    for i, (x, y) in enumerate(centers):
        owners = [j for j, b in enumerate(boxes) if b[0] <= x <= b[2] and b[1] <= y <= b[3]]
        if len(owners) != 1:
            raise ValueError("Split boxes do not uniquely partition original nodes")
        members[owners[0]].append(i)
    prepared = []
    px, py = max(0, int(parent[0])), max(0, int(parent[1]))
    for bbox, indices in zip(boxes, members):
        if not indices:
            raise ValueError("Empty region from splitter")
        x0, y0, x1, y1 = bbox
        ix0, iy0 = max(0, int(x0)), max(0, int(y0))
        ix1, iy1 = int(x1), int(y1)
        if ix0 < px or iy0 < py or ix1 > px + image.shape[1] or iy1 > py + image.shape[0]:
            raise ValueError("Child crop lies outside retained parent image")
        crop = image[iy0-py:iy1-py, ix0-px:ix1-px]
        if not crop.size:
            raise ValueError("Empty child crop")
        local = node_boxes[indices].copy() - [x0, y0, x0, y0]
        prepared.append((bbox, indices, crop, local, [texts[i] for i in indices]))
    return prepared


class HeaderRegionSplitPipeline:
    def __init__(self, model):
        self.splitter = _region_band_split
        self.events = []
        self.errors = []
        self.adapter = DeferredTGIFPipeline(model, region_resolver=self.resolve)

    def resolve(self, entry, page, evidence):
        group = entry[1].group
        prediction = group["table_grid"]
        texts = prediction.kwargs["texts"]
        nodes = [{"bbox": b, "text": t} for b, t in zip(group["bboxes"], texts)]
        ids = {nid: i for i, nid in enumerate(evidence["node_ids"])}
        edges = [{"source": ids[s], "target": ids[t], "probability": p}
                 for s, t, p in zip(*evidence["edge_index"], evidence["edge_prob"])]
        rects = [list(d["rect"]) for d in table._get_table_drawings(page)]
        try:
            boxes = self.splitter(nodes, edges, rects, list(entry[0]), strict_gate=True)
            if len(boxes) <= 1:
                return [union._TableGridEntry(entry[0], entry[1].resolve(), entry.bbox_provenance)]
            boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
            children = child_inputs(group, prediction, boxes)
            result = []
            for bbox, indices, image, local, child_texts in children:
                grid, _ = prediction.predict(image, local, texts=child_texts)
                if grid is None:
                    raise ValueError("TGIF failed on split child")
                child = dict(group, group_bbox=bbox, table_grid=grid)
                child_entry, = entry[1].original_reader(SimpleNamespace(layout_information=[child]))
                metadata = dict(entry.bbox_provenance, bbox_source="region_split",
                                bbox_operation="region_split", parent_bbox_source="gnn",
                                parent_bbox=list(entry[0]))
                result.append(union._TableGridEntry(child_entry[0], child_entry[1], metadata))
            self.events.append({"stage": "region_split", "parent_bbox": list(entry[0]),
                                "children": boxes, "node_counts": [len(c[1]) for c in children],
                                "source_gnn_indices": entry.bbox_provenance["source_gnn_indices"]})
            return result
        except Exception as exc:
            self.errors.append(f"region_split: {type(exc).__name__}: {exc}")
            raise
