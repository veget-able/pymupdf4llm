"""PR 470, row-0 exclusion and colspan handling on SEC-style headers.

All three tests pass on main. On the #470 head the first two fail (the group
header row, or both header rows, are hoisted out of the table) and the third
fails because the colspan rule overwrites the model's row 0 and the date line
below the group header disappears. The #471 head repairs the third case.
"""
import pymupdf
from pymupdf4llm.helpers import document_layout as dl

from _synth import cells_text, put, table_dict, table_rows, text_blocks

X = [50, 250, 325, 400, 475, 550]  # stub column + 4 value columns


def make(variant):
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # header level 1: group headers spanning two value columns each
    put(page, 0, 112, "Three Months Ended", center_in=(X[1], X[3]))
    put(page, 0, 112, "Nine Months Ended", center_in=(X[3], X[5]))
    if variant == "stub_label":
        put(page, X[0] + 2, 112, "(in millions)")
    # header level 2: one date per value column
    for j, lab in enumerate(["Sep 30, 2025", "Sep 30, 2024", "Sep 30, 2025", "Sep 30, 2024"]):
        put(page, 0, 132, lab, center_in=(X[j + 1], X[j + 2]))
    rows = [("Revenue", ["1,234", "1,100", "3,702", "3,300"]),
            ("Cost of sales", ["(600)", "(550)", "(1,800)", "(1,650)"]),
            ("Gross margin", ["634", "550", "1,902", "1,650"])]
    for i, (lab, vals) in enumerate(rows):
        y = 160 + 20 * i
        put(page, X[0] + 2, y, lab)
        for j, v in enumerate(vals):
            put(page, 0, y, v, right_at=X[j + 2] - 4)
    if variant == "group_row0":
        h = [118, 140, 165, 185]  # row 0 holds only the group headers
    else:
        h = [140, 165, 185]  # row 0 holds both header levels
    tab = table_dict(X, 100, 205, h)
    return dl.get_table_details(tab, text_blocks(page))


def test_group_header_row_stays_in_table():
    det = make("group_row0")
    rows = table_rows(det.markdown)
    assert det.row_count == 5, det.markdown
    assert "Three Months Ended" in rows[0].replace("|", ""), det.markdown


def test_two_level_header_is_not_replaced_by_a_data_row():
    det = make("two_level_row0")
    rows = table_rows(det.markdown)
    assert not rows[0].startswith("|Revenue"), det.markdown
    assert "Sep 30, 2025" in cells_text(rows[0]), det.markdown


def test_stub_label_keeps_the_date_line():
    det = make("stub_label")
    assert "Sep 30, 2025" in det.markdown, det.markdown
    assert "Revenue" in det.markdown, det.markdown
