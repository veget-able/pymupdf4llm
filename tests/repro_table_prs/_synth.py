"""Helpers shared by the synthetic repro tests.

The tests build a small PDF page with pymupdf, hand it a table grid in the
shape the layout model would produce, and call get_table_details() directly.
No layout model or OCR is involved, so the tests run anywhere pymupdf runs.
"""
from types import SimpleNamespace

import pymupdf
from pymupdf4llm.helpers import document_layout as dl


def put(page, x, y, text, size=9, center_in=None, right_at=None):
    """Insert text; center it between two x values or right-align it."""
    if center_in is not None:
        w = pymupdf.get_text_length(text, fontname="helv", fontsize=size)
        x = (center_in[0] + center_in[1]) / 2 - w / 2
    elif right_at is not None:
        w = pymupdf.get_text_length(text, fontname="helv", fontsize=size)
        x = right_at - w
    page.insert_text((x, y), text, fontname="helv", fontsize=size)


def table_dict(x_cols, y0, y1, h_lines):
    """A layout-style table dict: bbox plus interior boundaries relative to it."""
    grid = SimpleNamespace(
        h_lines=[v - y0 for v in h_lines],
        v_lines=[v - x_cols[0] for v in x_cols[1:-1]],
    )
    return {"group_bbox": (x_cols[0], y0, x_cols[-1], y1), "table_grid": grid}


def text_blocks(page):
    tp = page.get_textpage(flags=dl.FLAGS, clip=pymupdf.INFINITE_RECT())
    return [b for b in tp.extractRAWDICT()["blocks"] if b["type"] == 0]


def table_rows(markdown):
    """The '|' rows of a Markdown table without the separator row."""
    return [l for l in markdown.splitlines() if l.startswith("|") and not set(l) <= set("|-: ")]


def cells_text(row):
    return row.replace("|", " ").replace("<br>", " ")
