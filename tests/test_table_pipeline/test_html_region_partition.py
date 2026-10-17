"""The HTML consumer must reject bad ownership before child TGIF calls."""
from types import SimpleNamespace

import numpy as np
import pymupdf
import pytest

from pymupdf4llm._table_pipeline import header_region_split as html
from pymupdf4llm._table_pipeline.region_partition import partition_node_centers


def test_html_uses_the_partition_contract():
    assert html.partition_node_centers is partition_node_centers


def test_order_and_inclusive_outer_edges_preserved():
    assert partition_node_centers([(8, 10), (0, 0), (2, 4)],
                                  [[0, 0, 4, 10], [6, 0, 8, 10]]) == [[1, 2], [0]]


@pytest.mark.parametrize('centers,boxes', [
    ([(5, 5)], [[0, 0, 10, 10], [2, 2, 8, 8]]),
    ([(5, 5)], [[0, 0, 5, 10], [5, 0, 10, 10]]),
    ([(5, 5)], [[0, 0, 4, 10], [6, 0, 10, 10]]),
    ([(1, 1)], [[0, 0, 4, 10], [6, 0, 10, 10]]),
    ([], [[0, 0, 10, 10]]),
    ([(1, 1)], []),
])
def test_ambiguous_missing_or_empty_children_rejected(centers, boxes):
    assert partition_node_centers(centers, boxes) is None


def make_pipeline(monkeypatch, boxes, *, bad_alignment=False, model_error=False):
    calls = dict(parent=0, child=0)
    nodes = np.array([[0., 0., 4., 4.], [6., 0., 10., 4.]])
    local = nodes.copy()
    if bad_alignment:
        local[0, 0] += 1

    def predict(image, local, *, texts):
        calls['child'] += 1
        if model_error:
            raise RuntimeError('intentional child failure')
        return ['child-grid'], None

    pred = SimpleNamespace(args=(np.zeros((10, 10, 3)), local),
                           kwargs={'texts': ['a', 'b']}, predict=predict)
    group = dict(group_bbox=[0, 0, 10, 10], bboxes=nodes, table_grid=pred)
    parent_grid = ['parent-grid']

    def resolve():
        calls['parent'] += 1
        return parent_grid

    def reader(page):
        child = page.layout_information[0]
        return [html.union._TableGridEntry(pymupdf.Rect(child['group_bbox']),
                                          child['table_grid'], {})]

    lazy = SimpleNamespace(group=group, resolve=resolve, original_reader=reader)
    metadata = dict(source_gnn_indices=[0], bbox_source='gnn', bbox_operation='gnn_keep')
    entry = html.union._TableGridEntry(pymupdf.Rect(0, 0, 10, 10), lazy, metadata)
    pipeline = html.HeaderRegionSplitPipeline.__new__(html.HeaderRegionSplitPipeline)
    pipeline.splitter = lambda *args, **kwargs: boxes
    pipeline.events, pipeline.errors = [], []
    monkeypatch.setattr(html.table, '_get_table_drawings', lambda page: [])
    evidence = dict(node_ids=[0, 1], edge_index=[[], []], edge_prob=[])
    return pipeline, entry, evidence, calls, parent_grid


@pytest.mark.parametrize('boxes', [
    [[0, 0, 10, 10], [6, 0, 10, 10]],
    [[0, 0, 4, 10], [9, 0, 10, 10]],
    [[0, 0, 4, 10], [6, 0, 10, 10], [4.1, 0, 5.9, 10]],
])
def test_html_preserves_parent_without_child_inference(monkeypatch, boxes):
    pipeline, entry, evidence, calls, grid = make_pipeline(monkeypatch, boxes)
    output = pipeline.resolve(entry, SimpleNamespace(), evidence)
    assert len(output) == 1 and output[0][1] is grid
    assert output[0][0] == entry[0]
    assert output[0].bbox_provenance == entry.bbox_provenance
    assert calls == dict(parent=1, child=0)
    assert pipeline.events[0]['status'] == 'preserved'
    assert not pipeline.errors


def test_valid_split_still_executes_children(monkeypatch):
    pipeline, entry, evidence, calls, _ = make_pipeline(monkeypatch,
        [[0, 0, 4, 10], [6, 0, 10, 10]])
    output = pipeline.resolve(entry, SimpleNamespace(), evidence)
    assert len(output) == 2
    assert calls == dict(parent=0, child=2)
    assert pipeline.events[0]['node_counts'] == [1, 1]


@pytest.mark.parametrize('bad_alignment,model_error,exception', [
    (True, False, ValueError), (False, True, RuntimeError),
])
def test_other_errors_are_not_hidden(monkeypatch, bad_alignment, model_error, exception):
    pipeline, entry, evidence, calls, _ = make_pipeline(monkeypatch,
        [[0, 0, 4, 10], [6, 0, 10, 10]],
        bad_alignment=bad_alignment, model_error=model_error)
    with pytest.raises(exception):
        pipeline.resolve(entry, SimpleNamespace(), evidence)
    assert calls['parent'] == 0
    assert len(pipeline.errors) == 1
