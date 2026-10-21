"""H3 over-tag demotion: rule behavior on grids and the R6 wiring order."""

from unittest.mock import patch

import numpy as np
import pymupdf
from pymupdf import table
from pymupdf._table_headers import HeaderRegion
from pymupdf._table_spans import SpanCell

from pymupdf4llm._table_pipeline import r6_header
from pymupdf4llm._table_pipeline.header_role_demotion import demotion_depth


def rows(*specs):
    out = []
    for spec in specs:
        row = []
        for cell in spec:
            if isinstance(cell, tuple):
                text, cs, *rest = cell
                row.append((text, cs, rest[0] if rest else 1))
            else:
                row.append((cell, 1, 1))
        out.append(row)
    return out


def test_split_unit_note_row_is_demoted():
    grid = rows(["", "February 1, 2025", "February 3, 2024"], ["", "(in", "millions)"], ["Senior Secured Debt", "$ 425", "$ 389"])
    assert demotion_depth(grid, 2) == 1


def test_unit_note_with_leading_label_is_demoted():
    grid = rows(["", "2009", "2010", "2011"], ["Secured debt", "", "(dollars", "in thousands)"], ["Fixed Rate", "$ 95", "$134", "$551"])
    assert demotion_depth(grid, 2) == 1


def test_column_index_notes_without_words_stay():
    grid = rows(["Accident Year", "Countrywide", "DCC Ratio"], ["", "(1)", "(4) = (2) / (1)"], ["2016", "33,848", "12.4%"])
    assert demotion_depth(grid, 2) == 2
    letters = rows(["", "Calendar Year", "Earned Premium"], ["Column", "(A)", "(B)"], ["Formula", "", "+(B)[-1]"])
    assert demotion_depth(letters, 2) == 2


def test_single_section_label_is_demoted():
    grid = rows(["", "February 1, 2025", "February 3, 2024"], ["ASSETS", "", ""], ["Current Assets:", "", ""], ["Cash", "$ 227", "$ 270"])
    assert demotion_depth(grid, 2) == 1


def test_per_column_parenthesized_labels_stay():
    # Review counterexample 1: "(Actual)" / "(Budget)" are column labels.
    grid = rows(["", "2025", "2025"], ["", "(Actual)", "(Budget)"], ["Revenue", "100", "110"])
    assert demotion_depth(grid, 2) == 2
    single = rows(["", "2025", "2024"], ["", "(in millions)", ""], ["Revenue", "100", "110"])
    assert demotion_depth(single, 2) == 1


def test_wrapped_first_column_header_stays():
    # Review counterexample 2: "Accident" / "Year" is one wrapped label.
    grid = rows(["Accident", "Earned", "Incurred"], ["Year", "", ""], ["2016", "100", "80"])
    assert demotion_depth(grid, 2) == 2
    assert demotion_depth(rows(["", "Earned", "Incurred"], ["Total", "", ""], ["2016", "100", "80"]), 2) == 1


def test_wrapped_unit_in_first_column_stays():
    grid = rows(["Sleeve length", "Clearance (μm)", ("Offset (mm)", 4)], ["(mm)", "", "", "", "", ""], ["", "", "6", "7", "8", "9"])
    assert demotion_depth(grid, 2) == 2


def test_full_width_single_cell_is_not_a_section_here():
    grid = rows(["A", "B"], [("Totals", 2)], ["1", "2"])
    assert demotion_depth(grid, 2) == 2


def test_never_below_one_row_and_repeats_upward():
    grid = rows(["", "2024", "2023"], ["", "(in", "millions)"], ["ASSETS", "", ""], ["Cash", "1", "2"])
    assert demotion_depth(grid, 3) == 1
    assert demotion_depth(rows(["ASSETS", "", ""], ["Cash", "1", "2"]), 1) == 1
    assert demotion_depth([], 0) == 0


def page_with_text(doc):
    page = doc.new_page(width=320, height=300)
    for y, texts in ((75, ["", "Feb 2025", "Feb 2024"]), (105, ["", "(in", "millions)"]), (135, ["Cash", "$ 227", "$ 270"])):
        for x, text in zip((25, 115, 215), texts):
            if text:
                page.insert_text((x, y), text, fontsize=12)
    return page


class TwoRowSession:
    def run(self, names, values):
        n = len(values["features"])
        return [np.array([1, 1] + [0] * (n - 2), dtype=int)]


def r6_grid():
    return [
        [SpanCell((20, 60, 100, 80), "", 1, 1), SpanCell((110, 60, 200, 80), "Feb 2025", 1, 1), SpanCell((210, 60, 300, 80), "Feb 2024", 1, 1)],
        [SpanCell((20, 90, 100, 110), "", 1, 1), SpanCell((110, 90, 200, 110), "(in", 1, 1), SpanCell((210, 90, 300, 110), "millions)", 1, 1)],
        [SpanCell((20, 120, 100, 140), "Cash", 1, 1), SpanCell((110, 120, 200, 140), "$ 227", 1, 1), SpanCell((210, 120, 300, 140), "$ 270", 1, 1)],
    ]


def test_precomputed_occupancy_matches_recomputation():
    from pymupdf4llm._table_pipeline.header_leaf_completion import occupancy
    grid = rows(["", "2024", "2023"], ["", "(in", "millions)"], ["ASSETS", "", ""], ["Cash", "1", "2"])
    assert demotion_depth(grid, 3, occupancy(grid)) == demotion_depth(grid, 3) == 1


def test_r6_wiring_demotes_after_model_and_records_event():
    for enabled, expected in ((True, 1), (False, 2)):
        roles = r6_header.R6HeaderRoles(TwoRowSession(), role_demotion=enabled)
        grid, region = r6_grid(), HeaderRegion(2, ())
        with pymupdf.open() as doc:
            page = page_with_text(doc)
            tagged, out = roles.apply_roles(page, grid, region)
        assert out.top_header_rows == expected
        assert [c.tag for c in tagged[1]] == (["td"] * 3 if enabled else ["th"] * 3)
        event = roles.events[-1]
        assert event["after"] == expected and event["role_demoted"] is enabled and event["leaf_completed"] is False
