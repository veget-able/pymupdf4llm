"""H5 split-integrity eligibility on region-split child snapshots."""

from pymupdf4llm._table_pipeline.fragment_consolidation import split_integrity_eligible
from pymupdf4llm._table_pipeline import fragment_consolidation as module
from contextlib import nullcontext
from types import SimpleNamespace as NS
import pytest


def part(bbox, depth=1, cols=3):
    return dict(bbox=list(bbox), depth=depth, cols=cols)


def test_stacked_headerless_lower_child_reverts():
    # USPS 10-k page50 shape: header block on top, 33-row body without header below.
    parts = [part((64, 91, 549, 143), depth=2, cols=4), part((64, 148, 549, 680), depth=0, cols=4)]
    assert split_integrity_eligible(parts) == 'headerless_child'


def test_stacked_children_with_headers_stay():
    parts = [part((64, 91, 549, 143), depth=2), part((64, 148, 549, 680), depth=1)]
    assert split_integrity_eligible(parts) is None


def test_headerless_first_child_is_not_a_reason():
    # SERFF TX page706 shape: a headerless preamble above a real table stays split.
    parts = [part((10, 10, 500, 60), depth=0), part((10, 70, 500, 400), depth=2)]
    assert split_integrity_eligible(parts) is None


def test_side_single_column_child_reverts():
    # VRSK page141 shape: value columns on the right, a one-column label block on the left.
    parts = [part((409, 591, 494, 666), depth=1, cols=2), part((118, 606, 394, 667), depth=1, cols=1)]
    assert split_integrity_eligible(sorted(parts, key=lambda p: (p['bbox'][1], p['bbox'][0]))) == 'single_column_child'


def test_side_multi_column_children_stay():
    # Home Depot page72 / SERFF CA page2323 shapes: side-by-side children with >= 2 columns each.
    parts = [part((19, 348, 414, 376), cols=2), part((414, 348, 493, 376), cols=2), part((493, 348, 593, 376), cols=2)]
    assert split_integrity_eligible(parts) is None


def test_mixed_layout_and_single_child_stay():
    assert split_integrity_eligible([part((0, 0, 10, 10), depth=0)]) is None
    mixed = [part((0, 0, 100, 50), depth=1), part((60, 40, 200, 90), depth=0, cols=1)]
    assert split_integrity_eligible(mixed) is None


def test_diagonal_and_barely_overlapping_children_stay():
    for lower in (200, 39):
        assert split_integrity_eligible([
            part((0, 0, 100, 40), cols=1),
            part((200, lower, 300, lower + 40)),
        ]) is None


@pytest.mark.parametrize('scenario', ['scope', 'missing', 'multiple', 'headerless', 'accept', 'cached'])
def test_actual_revert_preserves_children_on_rejection(monkeypatch, scenario):
    """Exercise the product replacement path, not just its eligibility helper."""
    parent = [0, 0, 100, 100]
    tabs = [NS(bbox=[0, 0, 100, 40], header_rows=1), NS(bbox=[0, 50, 100, 100], header_rows=0)]
    for t in tabs:
        t.bbox_provenance = dict(bbox_source='region_split', source_gnn_indices=[7], parent_bbox=parent)
    run = module.FragmentConsolidationPipeline.__new__(module.FragmentConsolidationPipeline)
    run.events = []
    run.adapter = NS(stats=NS(tgif_executed=0))
    scope = [0, 0, 100, 300] if scenario == 'scope' else parent
    run.materials = {} if scenario == 'missing' else {(0, (7,)): ({'group_bbox': scope}, None, 'reader')}
    monkeypatch.setattr(module, 'snapshot', lambda t: dict(tab=t, bbox=t.bbox, cols=3, depth=t.header_rows))
    monkeypatch.setattr(module, 'refinement_geometry', nullcontext)
    called = []

    class Rows:
        def __init__(self, group, reader):
            called.append('resolve')
        def resolve(self):
            run.adapter.stats.tgif_executed += scenario != 'cached'
            return 'preserved-grid'

    monkeypatch.setattr(module, 'DeferredRows', Rows)
    rebuilt = [NS(header_rows=0 if scenario == 'headerless' else 1, placements=[])]
    if scenario == 'multiple':
        rebuilt *= 2
    def refine(page, grid, bbox, meta, base):
        assert grid == 'preserved-grid' and bbox == parent
        assert meta['recovery_source_bboxes'] == [t.bbox for t in tabs]
        called.append('refine')
        return rebuilt
    monkeypatch.setattr(module, 'refine_child', refine)
    monkeypatch.setattr(module, '_placement_grid_matrices', lambda grid: (1, 3, [], []))
    result = run.revert_broken_splits(NS(number=0), tabs)
    if scenario in ('accept', 'cached'):
        assert result == rebuilt
        assert run.events[-1]['extra_tgif_calls'] == (scenario == 'accept')
    else:
        assert len(result) == 2 and all(a is b for a, b in zip(result, tabs))
        if scenario in ('scope', 'missing'):
            assert not called and run.adapter.stats.tgif_executed == 0
        else:
            assert run.events[-1]['status'] == 'revert-rejected'
