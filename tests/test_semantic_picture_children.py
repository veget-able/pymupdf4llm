import pymupdf

from pymupdf4llm.helpers import utils
from pymupdf4llm.helpers.get_text_lines import get_raw_lines
from pymupdf4llm.helpers.document_layout import (
    LayoutBox,
    PageLayout,
    _detach_semantic_child_text_from_pictures,
    _suppress_multichild_native_picture_parents,
    _suppress_chart_semantic_children,
    _textlines_have_visible_text,
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


def test_semantic_visible_text_check_accepts_vertical_text():
    lines = [
        {
            "bbox": [10.0, 10.0, 20.0, 90.0],
            "spans": [{"text": "VERTICAL", "dir": [0.0, -1.0]}],
        }
    ]

    assert _textlines_have_visible_text(lines)


def test_semantic_visible_text_check_rejects_empty_spans():
    assert not _textlines_have_visible_text([])
    assert not _textlines_have_visible_text([{"spans": [{"text": "  "}]}])


def test_semantic_child_takes_exact_span_ownership_from_picture():
    page_number = {
        "bbox": [0.0, 0.0, 10.0, 10.0],
        "text": "p. 22",
        "block": 1,
        "line": 0,
    }
    heading = {
        "bbox": [12.0, 0.0, 90.0, 10.0],
        "text": "Strategy",
        "block": 1,
        "line": 0,
    }
    picture = LayoutBox(0.0, 0.0, 100.0, 20.0, "picture")
    picture.textlines = [
        {"bbox": [0.0, 0.0, 90.0, 10.0], "spans": [page_number, heading]}
    ]
    child = LayoutBox(12.0, 0.0, 90.0, 10.0, "section-header")
    child.textlines = [
        {"bbox": [12.0, 0.0, 90.0, 10.0], "spans": [dict(heading)]}
    ]
    page = PageLayout(1, 100.0, 100.0, [picture, child])

    removed = _detach_semantic_child_text_from_pictures(
        page,
        [(12.0, 0.0, 90.0, 10.0, "section-header")],
    )

    assert removed == 1
    assert picture.textlines[0]["spans"] == [page_number]
    assert picture.textlines[0]["bbox"] == page_number["bbox"]
    assert child.textlines[0]["spans"][0]["text"] == "Strategy"


def test_semantic_child_does_not_change_native_parent_suppression():
    parent = LayoutBox(0.0, 0.0, 100.0, 100.0, "picture")
    upper = LayoutBox(0.0, 0.0, 100.0, 45.0, "picture")
    upper.picture_detection = {"bbox": [0.0, 0.0, 100.0, 45.0]}
    lower = LayoutBox(0.0, 55.0, 100.0, 100.0, "picture")
    lower.picture_detection = {"bbox": [0.0, 55.0, 100.0, 100.0]}
    derived_child = LayoutBox(0.0, 45.0, 100.0, 55.0, "text")
    child_marker = (0.0, 45.0, 100.0, 55.0, "text")
    page = PageLayout(
        1,
        100.0,
        100.0,
        [parent, upper, lower, derived_child],
    )

    removed = _suppress_multichild_native_picture_parents(
        page,
        ignored_layout_boxes=[child_marker],
    )

    assert removed == 1
    assert page.boxes == [upper, lower, derived_child]


def test_get_raw_lines_does_not_mutate_reused_source_blocks():
    blocks = [
        {
            "type": 0,
            "bbox": [0.0, 0.0, 40.0, 10.0],
            "lines": [
                {
                    "bbox": [0.0, 0.0, 40.0, 10.0],
                    "dir": [1.0, 0.0],
                    "spans": [
                        {
                            "bbox": [0.0, 0.0, 10.0, 10.0],
                            "text": "CO",
                            "font": "Regular",
                            "alpha": 255,
                            "size": 10.0,
                            "flags": 0,
                            "char_flags": 0,
                        },
                        {
                            "bbox": [9.5, 0.0, 40.0, 10.0],
                            "text": "2 emission intensity",
                            "font": "Regular",
                            "alpha": 255,
                            "size": 10.0,
                            "flags": 0,
                            "char_flags": 0,
                        },
                    ],
                }
            ],
        }
    ]

    first = get_raw_lines(blocks=blocks, clip=(0.0, 0.0, 40.0, 10.0))
    second = get_raw_lines(blocks=blocks, clip=(0.0, 0.0, 40.0, 10.0))

    assert first[0][1][0]["text"] == "CO2 emission intensity"
    assert second[0][1][0]["text"] == "CO2 emission intensity"
    assert [span["text"] for span in blocks[0]["lines"][0]["spans"]] == [
        "CO",
        "2 emission intensity",
    ]
    assert blocks[0]["lines"][0]["spans"][0]["bbox"] == [0.0, 0.0, 10.0, 10.0]
