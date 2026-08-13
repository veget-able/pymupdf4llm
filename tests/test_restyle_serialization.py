import pymupdf

from pymupdf4llm.helpers.document_layout import (
    _leading_bold_run_in_spans,
    get_styled_text,
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
