import pymupdf

from pymupdf4llm.helpers import utils
from pymupdf4llm.helpers.document_layout import (
    LayoutBox,
    PageLayout,
    _suppress_chart_semantic_children,
)


def test_semantic_child_survives_picture_containment_filter():
    picture = (0.0, 0.0, 100.0, 100.0, "picture")
    child = (10.0, 10.0, 90.0, 20.0, "text")

    baseline = utils.find_reading_order(
        pymupdf.Rect(0, 0, 100, 100),
        [],
        [picture, child],
    )
    preserved = utils.find_reading_order(
        pymupdf.Rect(0, 0, 100, 100),
        [],
        [picture, child],
        preserve_contained=[child],
    )

    assert picture in baseline
    assert child not in baseline
    assert picture in preserved
    assert child in preserved


def test_unmarked_contained_box_is_still_filtered():
    picture = (0.0, 0.0, 100.0, 100.0, "picture")
    protected = (10.0, 10.0, 90.0, 20.0, "text")
    unmarked = (10.0, 30.0, 90.0, 40.0, "text")

    result = utils.find_reading_order(
        pymupdf.Rect(0, 0, 100, 100),
        [],
        [picture, protected, unmarked],
        preserve_contained=[protected],
    )

    assert protected in result
    assert unmarked not in result


def test_chart_veto_removes_only_explicit_semantic_children():
    chart = LayoutBox(0.0, 0.0, 100.0, 100.0, "picture")
    chart.chart = {"bbox": [0.0, 0.0, 100.0, 100.0]}
    semantic_child = LayoutBox(10.0, 10.0, 90.0, 20.0, "text")
    unmarked_text = LayoutBox(10.0, 30.0, 90.0, 40.0, "text")
    page = PageLayout(1, 100.0, 100.0, [chart, semantic_child, unmarked_text])

    _suppress_chart_semantic_children(
        page,
        [(10.0, 10.0, 90.0, 20.0, "text")],
    )

    assert chart in page.boxes
    assert semantic_child not in page.boxes
    assert unmarked_text in page.boxes


def test_nonchart_semantic_child_is_retained():
    picture = LayoutBox(0.0, 0.0, 100.0, 100.0, "picture")
    semantic_child = LayoutBox(10.0, 10.0, 90.0, 20.0, "text")
    page = PageLayout(1, 100.0, 100.0, [picture, semantic_child])

    _suppress_chart_semantic_children(
        page,
        [(10.0, 10.0, 90.0, 20.0, "text")],
    )

    assert page.boxes == [picture, semantic_child]
