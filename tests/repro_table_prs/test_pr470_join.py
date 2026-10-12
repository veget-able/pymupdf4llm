"""PR 470, table continuation on two distinct tables with the same grid.

"Incurred Claims" and "Loss Ratio" are two tables stacked 10 pt apart with
identical columns. They must stay separate. On the #470 head the second one
is taken as a continuation of the first, and its title and header become body
rows. The test is skipped on main, which has no continuation logic.
"""
import pymupdf
import pytest
from pymupdf4llm.helpers import document_layout as dl

from _synth import table_dict, text_blocks

X = [50, 150, 250, 350, 450]


def make():
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    def table(y0, title, rows):
        ys = [y0]
        page.insert_text((X[2] + 4, y0 + 14), title, fontsize=9)
        ys.append(y0 + 18)
        y = y0 + 32
        for r in rows:
            for j, v in enumerate(r):
                page.insert_text((X[j] + 4, y), v, fontsize=9)
            ys.append(y + 4)
            y += 16
        y1 = ys.pop()
        return table_dict(X, y0, y1, ys[1:])

    hdr = ["Year", "Plan A", "Plan B", "Total"]
    t_a = table(100, "Incurred Claims", [hdr, ["2021", "443,771", "5,677", "449,448"], ["2022", "392,239", "6,250", "398,489"]])
    t_b = table(t_a["group_bbox"][3] + 10, "Loss Ratio", [hdr, ["2021", "78.4%", "65.9%", "78.1%"], ["2022", "81.0%", "66.0%", "80.9%"]])
    return t_a, t_b, text_blocks(page)


def test_distinct_tables_with_the_same_grid_are_not_joined():
    if not hasattr(dl, "_is_table_continuation"):
        pytest.skip("no continuation logic in this build")
    t_a, t_b, blocks = make()
    det_a = dl.get_table_details(t_a, blocks)
    state = dl._table_continuation_state(t_a, 1, 792, det_a)
    prev = state if dl._is_table_continuation(state, t_b, 1, 792) else None
    det_b = dl.get_table_details(t_b, blocks, prev_table=prev)
    assert getattr(det_b, "continuation_markdown", None) is None, (
        "second table was joined under the first:\n" + det_b.continuation_markdown
    )
    assert "Loss Ratio" in det_b.markdown
