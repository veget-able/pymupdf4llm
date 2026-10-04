"""Source/geometry contracts, independent of PB filenames and annotations."""

from types import SimpleNamespace

from pymupdf._table_spans import SpanCell, CellSource
from pymupdf4llm._table_pipeline.clip_geometry import background
from pymupdf4llm._table_pipeline.clip_restoration import restore_grid, source_group


def test_partial_background_and_draw_order():
    full = dict(bbox=[0, 0, 100, 100], color=[0.5] * 3, known=True)
    half = dict(bbox=[0, 0, 50, 100], color=[1.0] * 3, known=True)
    assert background(full["bbox"], [full, half]) is None
    assert background(full["bbox"], [half, full]) == [0.5] * 3
    thin = dict(half, bbox=[0, 0, 0.01, 100])
    assert background(full["bbox"], [full, thin]) is None


def test_unknown_paint_requires_complete_cover():
    unknown = dict(bbox=[0, 0, 10, 10], color=[], known=False)
    cover = dict(bbox=[0, 0, 10, 10], color=[0.5] * 3, known=True)
    assert background(cover["bbox"], [cover, unknown]) is None
    assert background(cover["bbox"], [unknown, cover]) == [0.5] * 3


def test_source_group_rejects_foreign_glyphs_and_ambiguous_owners():
    gs = [dict(x0=1, x1=3, y=5, text="A"), dict(x0=5, x1=7, y=5, text="B")]
    group = dict(class_name="text", group_bbox=[0, 0, 10, 10])
    page = SimpleNamespace(layout_information=[group])
    assert source_group(page, [0], gs) is None
    assert source_group(page, [0, 1], gs) == 0
    page.layout_information.append(group)
    assert source_group(page, [0, 1], gs) is None


def test_merge_preserves_sources_and_span_slots():
    collection = []
    a = SpanCell((0, 0, 50, 10), "Alpha", 1, 1, sources=[CellSource("word", 0, (0, 0, 50, 10), "Alpha", collection)])
    b = SpanCell((0, 10, 50, 20), "Beta", 1, 1, sources=[CellSource("word", 1, (0, 10, 50, 20), "Beta", collection)])
    tab = SimpleNamespace(placements=[[a], [b]])
    gs = [dict(x0=1, x1=2, y=5, text="Alpha"), dict(x0=1, x1=2, y=15, text="Beta")]
    unit = dict(text="Alpha Beta", glyph_ids=[0, 1])
    grid, actions = restore_grid(tab, [unit], [], gs, [])
    assert actions == ["clip_merge"]
    assert grid[0][0].rowspan == 2 and grid[1] == []
    assert len(grid[0][0].source_content.sources) == 2
    assert grid[0][0].source_content.sources[0].collection is collection
    assert len(tab.placements[1]) == 1


def test_repeated_phrase_at_different_location_is_not_ownership():
    a = SpanCell((0, 0, 10, 10), "Alpha", 1, 1, sources=[])
    b = SpanCell((10, 0, 20, 10), "Beta", 1, 1, sources=[])
    tab = SimpleNamespace(placements=[[a, b]])
    gs = [dict(x0=100, x1=110, y=100, text="Alpha Beta")]
    grid, actions = restore_grid(tab, [dict(text="Alpha Beta", glyph_ids=[0])], [], gs, [])
    assert grid is tab.placements and not actions


def test_numeric_permutation_cannot_merge():
    a = SpanCell((0, 0, 10, 10), "A 13", 1, 1, sources=[])
    b = SpanCell((10, 0, 20, 10), "B 24", 1, 1, sources=[])
    tab = SimpleNamespace(placements=[[a, b]])
    grid, actions = restore_grid(tab, [dict(text="A 12 B 34", glyph_ids=[0])], [], [], [])
    assert grid is tab.placements and not actions
