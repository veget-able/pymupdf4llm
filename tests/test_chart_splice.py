"""Chart extraction tests - no model dependencies.

A stub detector and the placeholder extractor exercise the candidate
modes and the payload-attachment contract: chart boxes stay
picture-class, no other box is touched, extracted tables render inside
the fenced chart block, and a failed extraction reproduces the baseline
output.
"""

import json
import os
import sys
import types
from pathlib import Path

import pymupdf
import pymupdf4llm
import pytest
from pymupdf4llm.chart import paddleocr_vl, placeholder

CHART_PDF = Path(__file__).with_name("chart_sample.pdf")
CHART_BEGIN = "<!-- Start of chart table -->"

if not pymupdf4llm._use_layout:
    pytest.skip("pymupdf.layout not available", allow_module_level=True)


def stub_finder(page):
    """Fixed single region covering the sample page's chart area."""
    rect = page.rect
    return [
        {
            "bbox": (
                rect.x0 + 36,
                rect.y0 + 36,
                rect.x1 - 36,
                rect.y0 + 0.45 * rect.height,
            ),
            "score": 1.0,
        }
    ]


def test_detect_renders_fenced_chart_table():
    """Parse-time detection attaches the table, fenced apart from tables."""
    base = pymupdf4llm.to_markdown(str(CHART_PDF), header=False, footer=False)
    md = pymupdf4llm.to_markdown(
        str(CHART_PDF),
        detect_charts=stub_finder,
        chart_function=placeholder,
        header=False,
        footer=False,
    )
    assert CHART_BEGIN in md
    assert "_placeholder #1_" in md
    # nothing may disappear: every baseline line is still in the output
    for line in base.splitlines():
        if line.strip():
            assert line in md, f"baseline line lost: {line!r}"


def test_detect_json_keeps_picture_class_with_payload():
    """to_json: chart stays a picture box carrying markdown + csv."""
    js = pymupdf4llm.to_json(
        str(CHART_PDF),
        detect_charts=stub_finder,
        chart_function=placeholder,
    )
    data = json.loads(js)
    boxes = [b for p in data["pages"] for b in p["boxes"]]
    charts = [b for b in boxes if b.get("chart")]
    assert charts, "no chart payload in JSON"
    assert all(b["boxclass"] == "picture" for b in charts)
    assert all(b["chart"].get("markdown") and b["chart"].get("csv") for b in charts)
    assert not any(
        b["boxclass"] == "table" and b.get("chart") for b in boxes
    ), "chart emitted as a table box"


def test_dp0_picture_runs_after_dp0_chart_lane_and_cannot_reclaim_it():
    """DP0 Chart ownership is fixed before its Picture lane is merged."""
    events = []

    def chart_detector(page):
        events.append("dp0-chart")
        return [{"bbox": [36, 36, 576, 356], "score": 0.9}]

    def picture_detector(page):
        events.append("dp0-picture")
        return [
            {
                "bbox": [36, 36, 576, 356],
                "score": 0.95,
                "label": "picture",
            }
        ]

    data = json.loads(
        pymupdf4llm.to_json(
            str(CHART_PDF),
            detect_charts=chart_detector,
            detect_pictures=picture_detector,
            use_ocr=False,
        )
    )
    assert events == ["dp0-chart", "dp0-picture"]
    charts = [
        box
        for page in data["pages"]
        for box in page["boxes"]
        if box.get("chart")
    ]
    assert len(charts) == 1
    assert charts[0].get("picture_detection") is None


def test_dp0_picture_preserves_matched_native_bbox_and_adds_unmatched():
    """DP0 mirrors the reviewer D0 bbox contract without moving native boxes."""
    from pymupdf4llm.helpers.document_layout import (
        LayoutBox,
        PageLayout,
        _merge_picture_detections,
    )

    native = LayoutBox(10, 10, 30, 30, "picture")
    page = PageLayout(1, 100, 100, [native])

    def detector(_page):
        return [
            {"bbox": [10, 10, 30, 30], "score": 0.9, "label": "picture"},
            {"bbox": [50, 50, 70, 70], "score": 0.8, "label": "picture"},
        ]

    _merge_picture_detections(None, detector, page)
    assert [native.x0, native.y0, native.x1, native.y1] == [10, 10, 30, 30]
    assert native.picture_detection["bbox"] == [10.0, 10.0, 30.0, 30.0]
    added = [box for box in page.boxes if box is not native]
    assert len(added) == 1
    assert [added[0].x0, added[0].y0, added[0].x1, added[0].y1] == [
        50.0,
        50.0,
        70.0,
        70.0,
    ]


def test_builtin_d0_forwards_variant_without_running_dp0(monkeypatch):
    from pymupdf4llm.helpers.document_layout import _run_builtin_finder

    calls = []
    module = types.ModuleType("pymupdf.layout.chart_finder")
    module.model_path_for_variant = lambda variant: f"/models/d0-{variant}.onnx"

    def find_charts(page, *, variant, include_detector_bbox):
        calls.append((page, variant, include_detector_bbox))
        return [
            {
                "bbox": [1, 2, 3, 4],
                "detector_bbox": [1.25, 2.25, 2.75, 3.75],
                "score": 0.9,
            }
        ]

    module.find_charts = find_charts
    monkeypatch.setitem(sys.modules, module.__name__, module)
    page = object()

    charts, pictures = _run_builtin_finder(
        page,
        "d0",
        "mixed-sensitive-fp16",
    )

    assert calls == [(page, "mixed-sensitive-fp16", True)]
    assert len(charts) == 1
    assert charts[0]["detector_bbox"] == [1.25, 2.25, 2.75, 3.75]
    assert charts[0]["model_path"] == "/models/d0-mixed-sensitive-fp16.onnx"
    assert charts[0]["model_variant"] == "mixed-sensitive-fp16"
    assert charts[0]["refinement"] == "chart_finder._refine"
    assert pictures == []


def test_builtin_dp0_runs_once_and_returns_chart_then_picture(monkeypatch):
    from pymupdf4llm.helpers.document_layout import _run_builtin_finder

    calls = []
    module = types.ModuleType("pymupdf.layout.chart_picture_finder")

    module.model_path_for_variant = lambda _variant: "/models/dp0.onnx"

    def find_chart_pictures(page, *, variant, include_detector_bbox):
        calls.append((page, variant, include_detector_bbox))
        return {
            "chart": [
                {
                    "bbox": [1, 2, 3, 4],
                    "detector_bbox": [1.25, 2.25, 2.75, 3.75],
                    "score": 0.9,
                    "label": "chart",
                }
            ],
            "picture": [
                {"bbox": [5, 6, 7, 8], "score": 0.8, "label": "picture"}
            ],
            "model_variant": variant,
            "model_path": "/models/dp0.onnx",
            "providers": ["CPUExecutionProvider"],
            "refinement": {"chart": "chart-refiner", "picture": {"mode": "parent"}},
        }

    module.find_chart_pictures = find_chart_pictures
    monkeypatch.setitem(sys.modules, module.__name__, module)
    page = object()

    charts, pictures = _run_builtin_finder(page, "dp0", "weight-fp16")

    assert calls == [(page, "weight-fp16", True)]
    assert charts[0]["detector_bbox"] == [1.25, 2.25, 2.75, 3.75]
    assert charts[0]["model_variant"] == "weight-fp16"
    assert charts[0]["refinement"] == "chart-refiner"
    assert pictures[0]["model_path"] == "/models/dp0.onnx"
    assert pictures[0]["refinement"] == {"mode": "parent"}


def test_builtin_finder_mode_is_mutually_exclusive_with_callbacks():
    from pymupdf4llm.helpers.document_layout import parse_document

    with pytest.raises(ValueError, match="mutually exclusive"):
        parse_document(
            None,
            finder_mode="d0",
            detect_charts=lambda page: [],
        )


def test_builtin_finder_rejects_unknown_variant():
    from pymupdf4llm.helpers.document_layout import _run_builtin_finder

    with pytest.raises(ValueError, match="finder_variant"):
        _run_builtin_finder(object(), "d0", "unknown")


def test_dp0_removes_native_picture_parent_containing_multiple_children():
    """A native over-merge must not survive around multiple final Pictures."""
    from pymupdf4llm.helpers.document_layout import (
        LayoutBox,
        PageLayout,
        _suppress_multichild_native_picture_parents,
    )

    parent = LayoutBox(10, 10, 90, 90, "picture")
    upper = LayoutBox(8, 8, 92, 50, "picture")
    upper.chart = {"bbox": [8, 8, 92, 50]}
    lower = LayoutBox(8, 50, 92, 92, "picture")
    lower.picture_detection = {"bbox": [8, 50, 92, 92]}
    text = LayoutBox(5, 5, 15, 8, "text")
    page = PageLayout(1, 100, 100, [text, parent, upper, lower])

    removed = _suppress_multichild_native_picture_parents(page)

    assert removed == 1
    assert page.boxes == [text, upper, lower]


def test_dp0_preserves_native_picture_parent_with_only_one_child():
    """One containment relation is insufficient to suppress a native Picture."""
    from pymupdf4llm.helpers.document_layout import (
        LayoutBox,
        PageLayout,
        _suppress_multichild_native_picture_parents,
    )

    parent = LayoutBox(10, 10, 90, 90, "picture")
    child = LayoutBox(20, 20, 40, 40, "picture")
    child.chart = {"bbox": [20, 20, 40, 40]}
    page = PageLayout(1, 100, 100, [parent, child])

    removed = _suppress_multichild_native_picture_parents(page)

    assert removed == 0
    assert page.boxes == [parent, child]


def test_dp0_preserves_native_parent_with_unexplained_area():
    """Sparse child detections cannot justify dropping the native parent."""
    from pymupdf4llm.helpers.document_layout import (
        LayoutBox,
        PageLayout,
        _suppress_multichild_native_picture_parents,
    )

    parent = LayoutBox(0, 0, 100, 100, "picture")
    first = LayoutBox(0, 0, 40, 40, "picture")
    first.chart = {"bbox": [0, 0, 40, 40]}
    second = LayoutBox(60, 60, 100, 100, "picture")
    second.chart = {"bbox": [60, 60, 100, 100]}
    page = PageLayout(1, 100, 100, [parent, first, second])

    removed = _suppress_multichild_native_picture_parents(page)

    assert removed == 0
    assert page.boxes == [parent, first, second]


def test_dp0_preserves_native_parent_with_content_outside_each_child():
    """A parent textline spanning children proves residual parent ownership."""
    from pymupdf4llm.helpers.document_layout import (
        LayoutBox,
        PageLayout,
        _suppress_multichild_native_picture_parents,
    )

    parent = LayoutBox(0, 0, 100, 100, "picture")
    parent.textlines = [{"bbox": [10, 45, 90, 55], "spans": []}]
    upper = LayoutBox(0, 0, 100, 50, "picture")
    upper.chart = {"bbox": [0, 0, 100, 50]}
    lower = LayoutBox(0, 50, 100, 100, "picture")
    lower.chart = {"bbox": [0, 50, 100, 100]}
    page = PageLayout(1, 100, 100, [parent, upper, lower])

    removed = _suppress_multichild_native_picture_parents(page)

    assert removed == 0
    assert page.boxes == [parent, upper, lower]


def test_detection_ran_but_found_nothing_skips_extraction():
    """Zero detections must not fall back to feeding every picture."""

    def boom(crops):
        raise AssertionError("extractor must not run")

    md = pymupdf4llm.to_markdown(
        str(CHART_PDF),
        detect_charts=lambda page: [],
        chart_function=boom,
        header=False,
        footer=False,
    )
    base = pymupdf4llm.to_markdown(str(CHART_PDF), header=False, footer=False)
    assert md == base


def test_failure_keeps_original_output():
    """Lossless degrade: when extraction fails, output equals baseline."""

    def boom(crops):
        raise RuntimeError("chart model unavailable")

    base = pymupdf4llm.to_markdown(str(CHART_PDF), header=False, footer=False)
    diagnostics = []
    degraded = pymupdf4llm.to_markdown(
        str(CHART_PDF),
        chart_function=boom,
        chart_region="picture",
        chart_diagnostics=diagnostics,
        header=False,
        footer=False,
    )
    assert degraded == base
    assert any(d["stage"] == "chart_crop" for d in diagnostics)


def test_picture_mode_keeps_picture_content():
    """Picture mode adds the chart block and keeps the picture text."""
    base = pymupdf4llm.to_markdown(str(CHART_PDF), header=False, footer=False)
    md = pymupdf4llm.to_markdown(
        str(CHART_PDF),
        chart_function=placeholder,
        chart_region="picture",
        header=False,
        footer=False,
    )
    assert CHART_BEGIN in md
    for line in base.splitlines():
        if line.strip():
            assert line in md


@pytest.mark.skipif(
    not hasattr(pymupdf.Page, "find_charts"),
    reason="needs a PyMuPDF build with Page.find_charts()",
)
def test_parse_time_detection_flags_charts():
    """parse_document(detect_charts=True) flags chart picture boxes."""
    from pymupdf4llm.helpers.document_layout import parse_document

    parsed = parse_document(str(CHART_PDF), detect_charts=True, use_ocr=False)
    flagged = [
        b
        for page in parsed.pages
        for b in page.boxes
        if b.boxclass == "picture" and b.chart is not None
    ]
    assert flagged, "no chart-flagged picture boxes"
    assert all("score" in b.chart for b in flagged)


@pytest.mark.skipif(
    not hasattr(pymupdf.Page, "find_charts"),
    reason="needs a PyMuPDF build with Page.find_charts()",
)
def test_parse_time_detection_e2e_markdown():
    """detect_charts=True + chart_function end to end, model detector."""
    md = pymupdf4llm.to_markdown(
        str(CHART_PDF),
        detect_charts=True,
        chart_function=placeholder,
        header=False,
        footer=False,
    )
    assert CHART_BEGIN in md
    assert "_placeholder #1_" in md


@pytest.mark.skipif(
    os.environ.get("CHART_TEST_HEAVY") != "1",
    reason="heavy: PaddleOCR-VL weights + GPU inference (set CHART_TEST_HEAVY=1)",
)
def test_paddleocr_vl_real_inference():
    """Full pipeline with the real VLM - opt-in because of its weight."""
    md = pymupdf4llm.to_markdown(
        str(CHART_PDF),
        detect_charts=stub_finder,
        chart_function=paddleocr_vl,
        header=False,
        footer=False,
    )
    assert CHART_BEGIN in md
