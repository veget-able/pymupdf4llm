"""PR 469, legacy path (layout off): an unruled dense table that MuPDF returns
as one text block must come out row by row.

Passes on main (one line per row). On the #469 head, with reorder_columns on
by default, the block is emitted column-major: every row label first, then
every value of column 1, and so on. A layout that keeps the row order but puts
each cell on its own line also passes.
"""
import pymupdf
import pymupdf4llm
import pytest


@pytest.fixture
def legacy_mode():
    previous = getattr(pymupdf4llm, "_use_layout", True)
    pymupdf4llm.use_layout(False)
    try:
        yield
    finally:
        pymupdf4llm.use_layout(previous)


def test_dense_table_keeps_row_order(legacy_mode):
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    X = [50, 200, 280, 360, 440]
    for j, t in enumerate(["Class", "2021", "2022", "2023", "2024"]):
        page.insert_text((X[j], 100), t, fontname="helv", fontsize=9)
    for i in range(8):
        y = 100 + 12 * (i + 1)  # 12 pt pitch keeps the table in one MuPDF block
        page.insert_text((X[0], y), f"Class {chr(65 + i)} vehicles", fontname="helv", fontsize=9)
        for j in range(1, 5):
            page.insert_text((X[j], y), f"{1.0 + 0.1 * i + 0.05 * j:.3f}", fontname="helv", fontsize=9)

    md = pymupdf4llm.to_markdown(doc, show_progress=False)
    lines = [l.strip() for l in md.splitlines() if l.strip()]
    label_a = next(i for i, l in enumerate(lines) if l.startswith("Class A vehicles"))
    label_b = next(i for i, l in enumerate(lines) if l.startswith("Class B vehicles"))
    value_a = next(i for i, l in enumerate(lines) if "1.050" in l)  # first value of row A
    assert label_a <= value_a < label_b, (
        "row A's first value is not between row A's label and row B's label:\n" + "\n".join(lines[:20])
    )
