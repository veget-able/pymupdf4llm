"""PR 471, grid repair on a header band whose cells all wrap at the same
line offsets ("Company / Name:", "Policy / Number:").

Passes on main. On the #471 head the repair inserts a row boundary between the
two header lines once the line pitch is 16 pt or more, so the header is cut to
"Company|Policy|Effective|Annual" and "Name:|Number:|..." becomes a body row.
"""
import pymupdf
import pytest
from pymupdf4llm.helpers import document_layout as dl

from _synth import cells_text, put, table_dict, table_rows, text_blocks

X = [50, 170, 290, 410, 530]
HEAD = [("Company", "Name:"), ("Policy", "Number:"), ("Effective", "Date:"), ("Annual", "Premium:")]
ROWS = [("Acme Insurance", "PL-1001", "2026-01-01", "1,250.00"),
        ("Beta Mutual", "PL-1002", "2026-02-15", "980.50"),
        ("Gamma Re", "PL-1003", "2026-03-01", "2,100.00")]


def make(pitch):
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    for j, (a, b) in enumerate(HEAD):
        put(page, X[j] + 4, 112, a)
        put(page, X[j] + 4, 112 + pitch, b)
    band_bottom = 112 + pitch + 6
    for i, row in enumerate(ROWS):
        for j, v in enumerate(row):
            put(page, X[j] + 4, band_bottom + 20 + 18 * i, v)
    y1 = band_bottom + 20 + 18 * len(ROWS)
    h = [band_bottom + 8] + [band_bottom + 20 + 18 * i + 6 for i in range(len(ROWS) - 1)]
    tab = table_dict(X, 100, y1, h)
    return dl.get_table_details(tab, text_blocks(page))


@pytest.mark.parametrize("pitch", [12, 16, 20])
def test_wrapped_header_band_stays_one_row(pitch):
    det = make(pitch)
    rows = table_rows(det.markdown)
    assert det.row_count == 4, f"pitch {pitch} pt:\n{det.markdown}"
    assert "Company" in cells_text(rows[0]) and "Name:" in cells_text(rows[0]), det.markdown
    assert rows[1].startswith("|Acme Insurance"), det.markdown
