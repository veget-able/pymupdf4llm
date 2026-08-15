"""Chart extraction tests - no model dependencies.

A stub detector and the placeholder extractor exercise the candidate
modes and the payload-attachment contract: chart boxes stay
picture-class, no other box is touched, extracted tables render inside
the fenced chart block, and a failed extraction reproduces the baseline
output.
"""

import json
import os
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
    assert "<em>placeholder #1</em>" in md
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
