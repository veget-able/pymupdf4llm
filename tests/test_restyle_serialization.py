import pymupdf

from pymupdf4llm.helpers.document_layout import (
    _leading_bold_run_in_spans,
    text_to_md,
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


def test_code_run_is_cut_at_a_decoration_transition():
    # A code span is literal: an underline crossing part of a code run must
    # cut the run so the tags render outside the backticks (audit case).
    spans = [
        _span("A", 0, 10, flags=8),
        _span("B", 10, 20, flags=8, char_flags=16 | 2),
        _span("C", 20, 30, flags=8),
    ]
    output, _ = get_styled_text(spans)
    assert output == "`A`<u>`B`</u>`C` "


def test_flanking_invalid_italic_marker_upgrades_to_html():
    # Inside a continuing underline run no tags separate the italic marker
    # from the neighbouring words, so "_" would be literal intra-word;
    # the run must fall back to HTML emphasis (audit case).
    spans = [
        _span("BOARD", 0, 30, char_flags=16 | 2),
        _span("/", 30, 33, flags=2, char_flags=16 | 2),
        _span("COMMISSION", 33, 90, char_flags=16 | 2),
    ]
    output, _ = get_styled_text(spans)
    assert output == "<u>BOARD<em>/</em>COMMISSION</u> "


def _sized_span(text, x0, x1, y0, y1, *, font="Helvetica", size=10.0,
                flags=0, char_flags=16, line=0):
    return {
        "text": text,
        "bbox": pymupdf.Rect(x0, y0, x1, y1),
        "origin": (x0, y1 - 1),
        "size": size,
        "flags": flags,
        "char_flags": char_flags,
        "font": font,
        "block": 0,
        "line": line,
        "_reconstructed_line": line,
    }


def _textline(*spans):
    rect = pymupdf.Rect(spans[0]["bbox"])
    for s in spans[1:]:
        rect |= pymupdf.Rect(s["bbox"])
    return {"spans": list(spans), "bbox": tuple(rect)}


def test_heading_splits_at_a_font_signature_boundary():
    underline = 16 | pymupdf.mupdf.FZ_STEXT_UNDERLINE
    title = _textline(_sized_span(
        "SAFE IN THE ARMS JESUS", 0, 200, 0, 24,
        font="Avenir-BlackOblique", size=24.0, char_flags=underline, line=0))
    subtitle = _textline(_sized_span(
        "THE GREAT SAMARITAN", 20, 150, 26, 39,
        font="Avenir-HeavyOblique", size=13.0, char_flags=underline, line=1))
    output = section_hdr_to_md(1, [title, subtitle])
    assert output == (
        "# <u>SAFE IN THE ARMS JESUS</u> \n\n"
        "# <u>THE GREAT SAMARITAN</u> \n\n"
    )


def test_heading_keeps_a_same_font_wrap_merged():
    first = _textline(_sized_span(
        "TWO MEMBERS OF THE", 0, 120, 0, 12, size=12.0, line=0))
    second = _textline(_sized_span(
        "PUBLIC REGULATION COMMISSION", 0, 170, 14, 26, size=12.0, line=1))
    output = section_hdr_to_md(2, [first, second])
    assert output == "## TWO MEMBERS OF THE PUBLIC REGULATION COMMISSION \n\n"


def test_body_splits_at_a_font_signature_boundary():
    label = _textline(_sized_span(
        "Narcotics Anonymous SA", 0, 120, 0, 12,
        font="Roboto-Regular", size=10.0, line=0))
    number = _textline(_sized_span(
        "083 900 MY NA", 0, 90, 14, 28, font="Roboto-BoldCondensed",
        size=12.0, flags=pymupdf.TEXT_FONT_BOLD, line=1))
    output = text_to_md([label, number])
    assert output == "Narcotics Anonymous SA \n\n**083 900 MY NA** \n\n"


def test_same_row_font_change_stays_merged():
    left = _textline(_sized_span(
        "Hong Kong", 0, 60, 0, 12, font="MSungHK", size=12.0, line=0))
    right = _textline(_sized_span(
        "Lulea", 80, 120, 0, 12, font="Helvetica-Bold", size=14.0,
        flags=pymupdf.TEXT_FONT_BOLD, line=0))
    output = text_to_md([left, right])
    assert output == "Hong Kong **Lulea** \n\n"


def test_body_impure_emphasis_line_stays_merged():
    # A bold run covering most of a wrapped line flips its dominant
    # fontname, but the line is not font-pure - the paragraph must not
    # be split there.
    plain = _textline(_sized_span(
        "Because forest fires pose a threat", 0, 200, 0, 24,
        font="Calibri-Italic", size=24.0,
        flags=pymupdf.TEXT_FONT_ITALIC, line=0))
    emphasized = _textline(
        _sized_span("time), the ", 0, 40, 26, 50, font="Calibri-Italic",
                    size=24.0, flags=pymupdf.TEXT_FONT_ITALIC, line=1),
        _sized_span("USFS needs a better system", 40, 160, 26, 50,
                    font="Calibri-BoldItalic", size=24.0,
                    flags=pymupdf.TEXT_FONT_ITALIC | pymupdf.TEXT_FONT_BOLD,
                    line=1),
        _sized_span(". In addition,", 160, 200, 26, 50,
                    font="Calibri-Italic", size=24.0,
                    flags=pymupdf.TEXT_FONT_ITALIC, line=1))
    output = text_to_md([plain, emphasized])
    assert output.count("\n\n") == 1  # one paragraph, no split


def test_body_full_line_label_change_splits():
    # A font-pure Roman -> Bold line transition is a label/subheading
    # boundary and splits even without a size change.
    body = _textline(_sized_span(
        "Provides the main insurance cover", 0, 180, 0, 12,
        font="Calibri", size=9.0, line=0))
    label = _textline(_sized_span(
        "Other buildings", 0, 90, 14, 26, font="Calibri-Bold", size=9.0,
        flags=pymupdf.TEXT_FONT_BOLD, line=1))
    output = text_to_md([body, label])
    assert output == "Provides the main insurance cover \n\n**Other buildings** \n\n"


def test_embedded_ocr_layer_keeps_real_font_identity():
    # An embedded OCR text layer (invisible, but with recognized
    # fontnames) is not synthetic - a fontname change still splits.
    first = _textline(_sized_span(
        "VANDENHERIK", 0, 120, 0, 15, font="TimesNewRomanPS-BoldMT",
        size=15.3, char_flags=0, line=0))
    second = _textline(_sized_span(
        "SLIEDRECHT", 0, 110, 17, 32, font="Arial-BoldMT", size=15.0,
        char_flags=0, line=1))
    output = text_to_md([first, second])
    assert output.count("\n\n") == 2  # split into two blocks


def test_ocr_box_height_jitter_stays_merged():
    first = _textline(_sized_span(
        "Delays in the supplier's", 0, 150, 0, 13, font="Droid Sans Fallback Regular",
        size=13.0, char_flags=0, line=0))
    second = _textline(_sized_span(
        "performance", 0, 80, 15, 27, font="Droid Sans Fallback Regular",
        size=12.2, char_flags=0, line=1))
    output = section_hdr_to_md(2, [first, second])
    assert output == "## Delays in the supplier's performance \n\n"


def test_ocr_scale_contrast_still_splits():
    title = _textline(_sized_span(
        "ARCHIVE NOTICE", 0, 150, 0, 24, font="Droid Sans Fallback Regular",
        size=24.0, char_flags=0, line=0))
    body = _textline(_sized_span(
        "Details of the retention policy", 0, 180, 26, 37,
        font="Droid Sans Fallback Regular", size=11.0, char_flags=0, line=1))
    output = section_hdr_to_md(2, [title, body])
    assert output == (
        "## ARCHIVE NOTICE \n\n"
        "## Details of the retention policy \n\n"
    )


def test_body_run_crossing_emphasis_stays_merged():
    # The bold run starts at the end of the previous line and continues
    # onto the next - the change does not coincide with the line break,
    # so this is inline emphasis and the paragraph must not split, even
    # though the next line is fully bold.
    plain = _textline(
        _sized_span("for other nations; c", 0, 160, 0, 24,
                    font="Calibri-Italic", size=24.0,
                    flags=pymupdf.TEXT_FONT_ITALIC, line=0),
        _sized_span("ollect", 160, 200, 0, 24,
                    font="Calibri-BoldItalic", size=24.0,
                    flags=pymupdf.TEXT_FONT_ITALIC | pymupdf.TEXT_FONT_BOLD,
                    line=0))
    emphasized = _textline(_sized_span(
        "statistical data on fire outbreaks", 0, 180, 26, 50,
        font="Calibri-BoldItalic", size=24.0,
        flags=pymupdf.TEXT_FONT_ITALIC | pymupdf.TEXT_FONT_BOLD, line=1))
    output = text_to_md([plain, emphasized])
    assert output.count("\n\n") == 1


def test_body_label_after_mixed_line_still_splits():
    # Only the breaking side must be font-pure: a "Date: value" mixed
    # line does not stop the following bold "Subject:" label from
    # becoming its own block.
    mixed = _textline(
        _sized_span("Date:", 0, 30, 0, 14, font="TimesNewRomanPS-BoldMT",
                    size=14.0, flags=pymupdf.TEXT_FONT_BOLD, line=0),
        _sized_span("  April 22, 2025 and some more text", 30, 190, 0, 14,
                    font="TimesNewRomanPSMT", size=14.0, line=0))
    label = _textline(_sized_span(
        "Subject: UPDATE", 0, 100, 16, 30, font="TimesNewRomanPS-BoldMT",
        size=14.0, flags=pymupdf.TEXT_FONT_BOLD, line=1))
    output = text_to_md([mixed, label])
    assert output.count("\n\n") == 2
