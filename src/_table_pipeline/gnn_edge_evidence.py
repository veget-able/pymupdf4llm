"""Capture existing GNN outputs for region_split, without another inference.

The session proxy returns the original outputs unchanged. Sparse, directed
candidate edges retain their original node IDs and order, including low scores.
"""
import numpy as np


def capture_graph(inputs, outputs, threshold):
    edge_index = np.asarray(inputs["edge_index"])
    logits = np.asarray(outputs[1])
    if edge_index.ndim != 2 or edge_index.shape[0] != 2:
        raise ValueError("GNN edge_index must have shape (2, E)")
    if logits.shape != (edge_index.shape[1], 2):
        raise ValueError("GNN binary edge logits do not match candidate edges")
    if not np.issubdtype(edge_index.dtype, np.integer):
        raise ValueError("GNN edge IDs must be integers")
    if not np.isfinite(logits).all() or not np.isfinite(threshold):
        raise ValueError("Non-finite GNN edge evidence")
    # Match BoxRFDGNN's softmax, including dtype and strict > comparison.
    exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
    probabilities = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
    return {
        "edge_index": edge_index.copy(),
        "edge_prob": probabilities[:, 1].copy(),
        "edge_kept": (probabilities[:, 1] > threshold).copy(),
        "edge_threshold": float(threshold),
    }


def region_edge_evidence(group, graph):
    """Restrict to sampled edges whose BOTH endpoints belong to this group."""
    node_ids = [int(i) for i in group["indicies"]]
    bboxes = np.asarray(group["bboxes"], dtype=float).reshape(-1, 4)
    if len(node_ids) != len(bboxes) or len(set(node_ids)) != len(node_ids):
        raise ValueError("Layout node IDs and original node bboxes must align")
    if not np.isfinite(bboxes).all():
        raise ValueError("Non-finite node bbox")
    edges = graph["edge_index"]
    selected = np.isin(edges[0], node_ids) & np.isin(edges[1], node_ids)
    return {
        "node_ids": node_ids,
        "node_bboxes": bboxes.tolist(),
        "edge_index": edges[:, selected].tolist(),
        "edge_prob": graph["edge_prob"][selected].tolist(),
        "edge_kept": graph["edge_kept"][selected].tolist(),
        "edge_threshold": graph["edge_threshold"],
    }


class EdgeCapture:
    """Scoped by DeferredTGIFPipeline; reset on EVERY page/layout invocation."""
    def __init__(self, model, stats):
        self.model = model
        self.stats = stats
        self.original_session = model._model.session
        self.graph = None
        self.threshold = 0.55

    def __getattr__(self, name):
        return getattr(self.original_session, name)

    def run(self, output_names, inputs, *args, **kwargs):
        outputs = self.original_session.run(output_names, inputs, *args, **kwargs)
        self.stats.gnn_inference_calls += 1
        if self.graph is not None:
            raise RuntimeError("Expected one GNN inference per layout invocation")
        self.graph = capture_graph(inputs, outputs, self.threshold)
        return outputs

    def predict(self, page, *args, **kwargs):
        self.graph = None
        self.threshold = kwargs.get("edge_threshold", 0.55)
        groups = self.model.predict(page, *args, **kwargs)
        for group in groups:
            if not isinstance(group, dict) or group.get("class_name") != "table":
                continue
            if self.graph is None:
                raise RuntimeError("No GNN probabilities captured for this layout invocation")
            group["_region_edge_evidence"] = region_edge_evidence(group, self.graph)
        return groups
