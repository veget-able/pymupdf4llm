import pymupdf

from pymupdf4llm.helpers.document_layout import (
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
