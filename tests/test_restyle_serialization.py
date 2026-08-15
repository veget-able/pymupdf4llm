import pymupdf
import pytest

import pymupdf4llm.helpers.document_layout as document_layout

from pymupdf4llm.helpers.document_layout import (
    LayoutBox,
    PageLayout,
    ParsedDocument,
    _page_code_regions,
    _leading_bold_run_in_spans,
    get_styled_text,
    list_item_to_md,
    picture_text_to_md,
    section_hdr_to_md,
)


def _span(text, x0, x1, *, flags=0, char_flags=16, script=None):
    span = {
        "text": text,
        "bbox": pymupdf.Rect(x0, 0, x1, 10),
        "origin": (x0, 9),
        "size": 10,
        "flags": flags,
        "char_flags": char_flags,
        "font": "Helvetica",
        "block": 0,
        "line": 0,
        "_reconstructed_line": 0,
    }
    if script:
        span["script"] = script
    return span


def _code_line(parts, y=0, *, cell=5, indent=0, flags=0):
    spans = []
    x = indent
    for text, gap in parts:
        x += gap * cell
        spans.append(_span(text, x, x + len(text) * cell, flags=flags))
        spans[-1]["bbox"] = pymupdf.Rect(x, y, x + len(text) * cell, y + 10)
        spans[-1]["origin"] = (x, y + 9)
        x += len(text) * cell
    return {"bbox": pymupdf.Rect(indent, y, x, y + 10), "spans": spans}


def _code_box(lines, y0, *, boxclass="text", width_inlier=1.0):
    advance_count = sum(
        max(0, len(span["text"]) - 1)
        for line in lines
        for span in line["spans"]
    )
    return LayoutBox(
        0,
        y0,
        160,
        y0 + max(10, len(lines) * 12),
        boxclass,
        textlines=lines,
        code_cell_width=5,
        code_width_inlier=width_inlier,
        code_advance_count=advance_count,
    )


class _DetectorOutput:
    def __init__(self, label, group="code"):
        self.label = label
        self.group = group


class _DetectorResult:
    def __init__(self, label, group="code"):
        self.output = _DetectorOutput(label, group)


class _Detector:
    def __init__(self, label="python", group="code"):
        self.label = label
        self.group = group
        self.calls = []

    def identify_bytes(self, value):
        self.calls.append(value)
        return _DetectorResult(self.label, self.group)


def test_style_boundary_does_not_invent_a_word_space():
    spans = [
        _span("Gener", 0, 25),
        _span(
            "al",
            25,
            35,
            char_flags=16 | pymupdf.mupdf.FZ_STEXT_STRIKEOUT,
        ),
    ]
    output, _ = get_styled_text(spans)
    assert output == "Gener~~al~~ "


def test_visual_gap_remains_a_space():
    spans = [
        _span("General", 0, 35),
        _span(
            "style",
            40,
            65,
            char_flags=16 | pymupdf.mupdf.FZ_STEXT_STRIKEOUT,
        ),
    ]
    output, _ = get_styled_text(spans)
    assert output == "General ~~style~~ "


def test_script_metadata_is_serialized_and_attached():
    spans = [
        _span("H", 0, 7),
        _span("2", 7, 12, script="subscript"),
        _span("O", 12, 20),
    ]
    output, _ = get_styled_text(spans)
    assert output == "H<sub>2</sub>O "


def test_recovered_script_is_not_serialized_in_a_heading_number():
    spans = [
        _span("5", 0, 5, script="superscript"),
        _span("Fund Type", 6, 45),
    ]
    output = section_hdr_to_md(1, [{"spans": spans}])
    assert output == "# 5 Fund Type \n\n"


def test_all_caps_bold_run_in_title_is_separated_from_body():
    spans = [
        _span("COUNTY OFFICES", 0, 50, flags=pymupdf.TEXT_FONT_BOLD),
        _span("THREE COMMISSIONERS", 51, 120, flags=pymupdf.TEXT_FONT_BOLD),
        _span("District 2", 121, 165),
    ]
    assert _leading_bold_run_in_spans([{"spans": spans}]) == 2


def test_common_bold_stays_open_across_an_underline_transition():
    spans = [
        _span("A", 0, 5, flags=pymupdf.TEXT_FONT_BOLD),
        _span(
            "B",
            5,
            10,
            flags=pymupdf.TEXT_FONT_BOLD,
            char_flags=16 | pymupdf.mupdf.FZ_STEXT_UNDERLINE,
        ),
    ]
    output, _ = get_styled_text(spans)
    assert output == "**A<u>B</u>** "


def test_common_bold_stays_open_across_an_intraword_italic_transition():
    spans = [
        _span("A", 0, 5, flags=pymupdf.TEXT_FONT_BOLD),
        _span(
            "B",
            5,
            10,
            flags=pymupdf.TEXT_FONT_BOLD | pymupdf.TEXT_FONT_ITALIC,
        ),
        _span("C", 10, 15, flags=pymupdf.TEXT_FONT_BOLD),
    ]
    output, _ = get_styled_text(spans)
    assert output == "**A*B*C** "


def test_crossing_bold_and_italic_runs_use_unambiguous_html_emphasis():
    spans = [
        _span(
            "A",
            0,
            5,
            flags=pymupdf.TEXT_FONT_BOLD | pymupdf.TEXT_FONT_ITALIC,
        ),
        _span("B", 5, 10, flags=pymupdf.TEXT_FONT_ITALIC),
    ]
    output, _ = get_styled_text(spans)
    assert output == "**<em>A</em>**<em>B</em> "


def test_intraword_italic_uses_a_renderable_delimiter():
    spans = [
        _span("pre", 0, 15),
        _span("mid", 15, 30, flags=pymupdf.TEXT_FONT_ITALIC),
        _span("post", 30, 50),
    ]
    output, _ = get_styled_text(spans)
    assert output == "pre*mid*post "


def test_literal_style_delimiters_are_not_consumed_as_serializer_state():
    spans = [
        _span("literal**", 0, 40),
        _span("bold", 40, 60, flags=pymupdf.TEXT_FONT_BOLD),
    ]
    output, _ = get_styled_text(spans)
    assert output == r"literal\*\***bold** "


def test_literal_underscore_selects_a_noncolliding_italic_delimiter():
    spans = [
        _span("literal_", 0, 35),
        _span("italic", 35, 65, flags=pymupdf.TEXT_FONT_ITALIC),
    ]
    output, _ = get_styled_text(spans)
    assert output == "literal_*italic* "


def test_inline_code_uses_a_fence_longer_than_its_backticks():
    spans = [
        _span("a`b", 0, 20, flags=pymupdf.TEXT_FONT_MONOSPACED),
    ]
    output, _ = get_styled_text(spans)
    assert output == "``a`b`` "


def test_inline_code_padding_wraps_the_whole_run_not_each_span():
    spans = [
        _span("`a", 0, 10, flags=pymupdf.TEXT_FONT_MONOSPACED),
        _span("b`", 10, 20, flags=pymupdf.TEXT_FONT_MONOSPACED),
    ]
    output, _ = get_styled_text(spans)
    assert output == "`` `a b` `` "


def test_whitespace_only_styled_span_does_not_emit_an_empty_wrapper():
    spans = [
        _span("A", 0, 5),
        _span(
            "   ",
            5,
            8,
            char_flags=16 | pymupdf.mupdf.FZ_STEXT_UNDERLINE,
        ),
        _span("B", 8, 13),
    ]
    output, _ = get_styled_text(spans)
    assert output == "A B "


def test_list_bullet_removal_preserves_separator_and_does_not_mutate_input():
    spans = [
        _span(
            "- Commercial Operator Handbook for permit holders in ",
            0,
            250,
            flags=pymupdf.TEXT_FONT_ITALIC,
        ),
        _span(
            "Western Australia",
            249.99,
            330,
            flags=pymupdf.TEXT_FONT_ITALIC,
            char_flags=16 | pymupdf.mupdf.FZ_STEXT_UNDERLINE,
        ),
    ]
    original = spans[0]["text"]
    output = list_item_to_md(
        [{"bbox": pymupdf.Rect(0, 0, 330, 10), "spans": spans}], 1
    )
    assert output == (
        "- _Commercial Operator Handbook for permit holders in "
        "<u>Western Australia</u>_ \n\n"
    )
    assert spans[0]["text"] == original


def test_picture_text_serializes_available_style_metadata():
    spans = [
        _span(
            "signed",
            0,
            30,
            char_flags=16 | pymupdf.mupdf.FZ_STEXT_UNDERLINE,
        )
    ]
    output = picture_text_to_md([{"spans": spans}])
    assert output == (
        "<!-- Start of picture text -->\n"
        "<u>signed</u><br><!-- End of picture text -->\n\n"
    )


def test_underline_is_closed_before_intraword_italic_opens():
    underline = 16 | pymupdf.mupdf.FZ_STEXT_UNDERLINE
    spans = [
        _span("BOARD", 0, 25, char_flags=underline),
        _span(
            "/",
            25,
            30,
            flags=pymupdf.TEXT_FONT_ITALIC,
            char_flags=underline,
        ),
        _span("COMMISSION", 30, 80, char_flags=underline),
    ]
    output, _ = get_styled_text(spans)
    assert output == "<u>BOARD</u>_<u>/</u>_<u>COMMISSION</u> "

    markdown = pytest.importorskip("markdown")
    rendered = markdown.markdown(output)
    assert "_" not in rendered
    assert "<em><u>/</u></em>" in rendered


def test_inline_code_is_closed_before_underline_opens():
    spans = [
        _span("A", 0, 5, flags=pymupdf.TEXT_FONT_MONOSPACED),
        _span(
            "B",
            5,
            10,
            flags=pymupdf.TEXT_FONT_MONOSPACED,
            char_flags=16 | pymupdf.mupdf.FZ_STEXT_UNDERLINE,
        ),
        _span("C", 10, 15, flags=pymupdf.TEXT_FONT_MONOSPACED),
    ]
    output, _ = get_styled_text(spans)
    assert output == "`A`<u>`B`</u>`C` "

    markdown = pytest.importorskip("markdown")
    rendered = markdown.markdown(output)
    assert "&lt;u&gt;" not in rendered
    assert "<u><code>B</code></u>" in rendered


def test_process_local_detector_is_lazy_reused_and_recreated_after_fork(monkeypatch):
    created = []

    def factory():
        detector = _Detector()
        created.append(detector)
        return detector

    monkeypatch.setattr(document_layout, "_new_code_detector", factory)
    monkeypatch.setattr(document_layout, "_CODE_DETECTOR", None)
    monkeypatch.setattr(document_layout, "_CODE_DETECTOR_PID", None)
    monkeypatch.setattr(document_layout.os, "getpid", lambda: 101)

    first = document_layout._get_code_detector()
    second = document_layout._get_code_detector()
    assert first is second
    assert len(created) == 1

    monkeypatch.setattr(document_layout.os, "getpid", lambda: 202)
    child = document_layout._get_code_detector()
    assert child is not first
    assert len(created) == 2


def test_fixed_pitch_fragments_coalesce_and_restore_a_geometric_space(monkeypatch):
    detector = _Detector("python")
    monkeypatch.setattr(document_layout, "_get_code_detector", lambda: detector)
    boxes = [
        _code_box(
            [_code_line([("if value not", 0), ("in items:", 1)], y=0)],
            0,
        ),
        _code_box([_code_line([("print(value)", 0)], y=12, indent=5)], 12),
        # This short control box is a supporter, not a seed, and must not split
        # the surrounding fixed-pitch region.
        _code_box([_code_line([("else:", 0)], y=24)], 24),
        _code_box([_code_line([("print('missing')", 0)], y=36, indent=5)], 36),
    ]
    regions = _page_code_regions(boxes)
    assert tuple(regions) == (0,)
    assert regions[0].indices == (0, 1, 2, 3)
    assert len(detector.calls) == 1
    assert b"not in items:" in detector.calls[0]

    document = ParsedDocument(
        pages=[PageLayout(1, 200, 200, boxes)],
        toc=[],
        metadata={},
    )
    output = document.to_markdown()
    assert output.count("```python") == 1
    assert "if value not in items:" in output
    assert "else:" in output


def test_fixed_pitch_prose_does_not_initialize_the_detector(monkeypatch):
    def fail_if_called():
        raise AssertionError("language detector must remain lazy")

    monkeypatch.setattr(document_layout, "_get_code_detector", fail_if_called)
    boxes = [
        _code_box(
            [_code_line([("This is fixed pitch prose without code syntax.", 0)])],
            0,
        )
    ]
    assert _page_code_regions(boxes) == {}


def test_detector_abstention_does_not_invent_a_recovered_code_block(monkeypatch):
    detector = _Detector("txt", group="text")
    monkeypatch.setattr(document_layout, "_get_code_detector", lambda: detector)
    boxes = [_code_box([_code_line([("value = ordinary", 0)])], 0)]
    assert _page_code_regions(boxes) == {}
    assert len(detector.calls) == 1


def test_proportional_code_like_text_does_not_reach_the_detector(monkeypatch):
    def fail_if_called():
        raise AssertionError("proportional text must fail the glyph-advance gate")

    monkeypatch.setattr(document_layout, "_get_code_detector", fail_if_called)
    boxes = [
        _code_box(
            [_code_line([("ordinary prose value = another value", 0)])],
            0,
            width_inlier=0.4,
        )
    ]
    assert _page_code_regions(boxes) == {}


def test_fully_ocred_page_does_not_run_native_code_recovery(monkeypatch):
    def fail_if_called():
        raise AssertionError("OCR page must not invoke the language detector")

    monkeypatch.setattr(document_layout, "_get_code_detector", fail_if_called)
    boxes = [_code_box([_code_line([("value = 1", 0)])], 0)]
    document = ParsedDocument(
        pages=[PageLayout(1, 200, 200, boxes, full_ocred=True)],
        toc=[],
        metadata={},
    )
    assert "```" not in document.to_markdown()
