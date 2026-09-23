from types import SimpleNamespace

import numpy as np
import pymupdf
from pymupdf import _table_union as union
import pytest

import pymupdf4llm._table_pipeline.deferred_tgif as pipeline
from pymupdf4llm._table_pipeline.gnn_edge_evidence import EdgeCapture, capture_graph, region_edge_evidence


def graph_inputs():
    inputs = {"edge_index": np.array([[3, 1, 3, 4], [1, 3, 4, 1]], dtype=np.int64)}
    outputs = [np.zeros((5, 4)), np.array([[0., -2.], [0., 2.], [0., 1.], [0., 0.]], dtype=np.float32)]
    return inputs, outputs


def test_probabilities_match_original_softmax_without_modifying_outputs():
    inputs, outputs = graph_inputs()
    before = outputs[1].copy()
    graph = capture_graph(inputs, outputs, .55)
    exp = np.exp(before - np.max(before, axis=1, keepdims=True))
    expected = (exp / np.sum(exp, axis=1, keepdims=True))[:, 1]
    np.testing.assert_array_equal(graph["edge_prob"], expected)
    np.testing.assert_array_equal(graph["edge_kept"], expected > .55)
    np.testing.assert_array_equal(outputs[1], before)


def test_sparse_region_keeps_low_scores_direction_order_and_original_ids():
    inputs, outputs = graph_inputs()
    group = {"indicies": [3, 1], "bboxes": [[30, 0, 40, 10], [10, 0, 20, 10]]}
    evidence = region_edge_evidence(group, capture_graph(inputs, outputs, .55))
    assert evidence["node_ids"] == [3, 1]
    assert evidence["node_bboxes"] == group["bboxes"]
    assert evidence["edge_index"] == [[3, 1], [1, 3]]
    assert evidence["edge_prob"][0] < .55 < evidence["edge_prob"][1]
    assert evidence["edge_kept"] == [False, True]
    assert len(evidence["edge_prob"]) == 2  # no invented self-loops/dense pairs


def test_group_without_sampled_edges_has_empty_list_not_zero_probabilities():
    inputs, outputs = graph_inputs()
    evidence = region_edge_evidence(
        {"indicies": [0, 2], "bboxes": [[0, 0, 1, 1], [2, 2, 3, 3]]},
        capture_graph(inputs, outputs, .55),
    )
    assert evidence["edge_index"] == [[], []]
    assert evidence["edge_prob"] == evidence["edge_kept"] == []


def test_empty_graph_and_mismatched_logits():
    graph = capture_graph({"edge_index": np.empty((2, 0), dtype=int)},
                          [None, np.empty((0, 2), dtype=np.float32)], .7)
    assert graph["edge_prob"].size == 0
    with pytest.raises(ValueError, match="do not match"):
        capture_graph({"edge_index": np.zeros((2, 1), dtype=int)},
                      [None, np.empty((0, 2))], .55)


class Session:
    def __init__(self):
        self.calls = 0
        self.inputs, self.outputs = graph_inputs()

    def run(self, *args, **kwargs):
        self.calls += 1
        return self.outputs


def test_proxy_reuses_one_forward_and_resets_between_layout_calls():
    session = Session()
    inner = SimpleNamespace(session=session)
    wrapper = SimpleNamespace(_model=inner)

    def predict(page, **kwargs):
        if page == "empty":
            return []
        result = inner.session.run(None, session.inputs)
        assert result is session.outputs
        return [{"class_name": "table", "indicies": [3, 1],
                 "bboxes": [[30, 0, 40, 10], [10, 0, 20, 10]]}]

    wrapper.predict = predict
    stats = pipeline.RunStats()
    capture = EdgeCapture(wrapper, stats)
    inner.session = capture
    result = capture.predict("page", edge_threshold=.8)
    assert session.calls == stats.gnn_inference_calls == 1
    assert result[0]["_region_edge_evidence"]["edge_threshold"] == .8
    assert capture.predict("empty") == [] and capture.graph is None
    capture.predict("another")
    assert session.calls == stats.gnn_inference_calls == 2
