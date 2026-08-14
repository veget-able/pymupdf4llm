import pymupdf

from pymupdf4llm.helpers import utils


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
