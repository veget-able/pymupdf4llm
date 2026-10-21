"""H2 colspan leaf completion: rule behavior on grids and the R6 wiring."""

from unittest.mock import patch

import numpy as np
import pymupdf
import pytest
from pymupdf import table
from pymupdf._table_headers import HeaderRegion
from pymupdf._table_spans import SpanCell

from pymupdf4llm._table_pipeline import r6_header
from pymupdf4llm._table_pipeline.header_leaf_completion import grid_rows, is_numeric, is_unit_note, is_year_or_date, leaf_completion_depth, occupancy, year_row_depth


def rows(*specs):
    """Each spec is a list of cells: text or (text, colspan) or (text, colspan, rowspan)."""
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


def test_occupancy_places_spans_like_html():
    cells, ncols = occupancy(rows([("A", 2), "B"], ["a1", "a2", "b"]))
    assert ncols == 3
    assert (0, 1, 0, 2, "A") in cells and (0, 1, 2, 3, "B") in cells
    assert (1, 2, 1, 2, "a2") in cells


def test_occupancy_respects_rowspan_from_previous_rows():
    cells, ncols = occupancy(rows([("R", 1, 2), "x"], ["y"]))
    assert ncols == 2
    assert (1, 2, 1, 2, "y") in cells  # "y" is pushed right of the rowspan.


def test_numeric_detection():
    assert is_numeric("$ 34,550") and is_numeric("2.0%") and is_numeric("(1,234)") and is_numeric("44-45, 47")
    assert not is_numeric("Age") and not is_numeric("GRM31CR71A106KA0") and not is_numeric("") and not is_numeric("--")


def test_parent_span_with_leaf_row_extends_one_row():
    # AZ LIC page47 shape: Territory*4 over four codes, then numeric body.
    grid = rows(
        [("Protection - Construction", 6)],
        ["Construction", "PPC", ("Territory", 4)],
        ["", "", "46", "44-45, 47", "40, 42-43", "41"],
        ["Masonry", "1", "0.870", "0.840", "0.810", "0.790"],
        ["", "2", "0.880", "0.850", "0.830", "0.800"],
    )
    assert leaf_completion_depth(grid, 2) == 3


def test_two_level_parent_completes_only_until_leaves_exist():
    grid = rows(
        ["Attained", ("Non-Tobacco", 2), ("Tobacco", 2)],
        ["Age", "Female", "Male", "Female", "Male"],
        ["0-64", "N/A", "N/A", "N/A", "N/A"],
        ["65", "1.0", "1.1", "1.2", "1.3"],
    )
    assert leaf_completion_depth(grid, 1) == 2
    assert leaf_completion_depth(grid, 2) == 2  # already complete: unchanged


def test_first_record_with_numbers_under_leaf_columns_is_not_a_header():
    # Walmart shape: Change*2 unresolved but "$21.9" sits under leaf FY'24Q4.
    grid = rows(
        ["Sam's Club", "FY24Q4", "FY23Q4", ("Change", 2)],
        ["Net sales", "$21.9", "$21.4", "$0.4", "2.0%"],
        ["Net sales ex", "$19.4", "$18.8", "$0.6", "3.3%"],
    )
    assert leaf_completion_depth(grid, 1) == 1


def test_spanning_body_cell_does_not_resolve_a_span():
    grid = rows(
        ["Step", ("Rating Algorithm", 6), "PLA"],
        ["OPP1.01", ("Claim Frequency", 6), "#"],
        ["OPP1.02", ("Claim Frequency", 6), "X"],
    )
    assert leaf_completion_depth(grid, 1) == 1


def test_full_width_span_is_a_title_not_a_parent():
    grid = rows(
        [("Focus area: Innovation", 5)],
        ["CT4", "Research", "1. Perform", "Clinical", "Human"],
        ["CT5", "Other", "2. Do", "Trial", "Vet"],
    )
    assert leaf_completion_depth(grid, 1) == 1


def test_row_repeated_by_next_row_is_the_first_record():
    # SERFF CA page56 shape: "20%","20%" under a span, next row identical shape.
    grid = rows(
        ["", ("Range of Modification", 2)],
        ["Risk Characteristic", ("Credit to Debit", 2)],
        ["Classification", "20%", "20%"],
        ["Employees", "20%", "20%"],
    )
    assert leaf_completion_depth(grid, 2) == 2


def test_never_shrinks_and_handles_edge_depths():
    grid = rows([("A", 2)], ["a", "b"], ["1", "2"])
    assert leaf_completion_depth(grid, 0) == 0
    assert leaf_completion_depth(grid, 3) == 3
    assert leaf_completion_depth([], 0) == 0
    assert leaf_completion_depth(rows([("Only", 1)], ["x"]), 1) == 1  # single column


def test_blank_header_column_accepts_a_text_label_below():
    # llama shape: blank first header, "pass@" label appears in the leaf row.
    grid = rows(
        ["", "Params", ("HumanEval", 2), ("MBPP", 2)],
        ["pass@", "", "@1", "@100", "@1", "@80"],
        ["LaMDA", "137B", "14.0", "47.3", "14.8", "62.4"],
    )
    assert leaf_completion_depth(grid, 1) == 2


def test_year_or_date_detection():
    assert all(is_year_or_date(t) for t in ("2024", "12/31/2014", "12 / 2000", "2015-06"))
    assert not any(is_year_or_date(t) for t in ("20104", "$1,000", "1-10", "vs. 2014", "12 / 24", "Q1", ""))


def test_year_row_under_labeled_columns_joins_header():
    grid = rows(["", "(1) Acc Yr", "(2) Acc Yr"], ["", "12/31/2014", "12/31/2015"], ["Bodily Injury", "6,366,867", "7,277,711"])
    assert year_row_depth(grid, 1) == 2
    unit = rows(["", "Walmart", "Consolidated"], ["(Dollars in millions)", "2024", "2023"], ["Operating income", "$ 4,909", "$ 27,012"])
    assert year_row_depth(unit, 1) == 2
    currency = rows(["", "December", "September"], ["$ in millions", "2024", "2024"], ["Total HQLA", "$ 407,348", "$ 434,256"])
    assert year_row_depth(currency, 1) == 2


def test_unit_note_detection():
    assert all(is_unit_note(t) for t in ("(in millions)", "(Dollars in millions)", "$ in millions", "in thousands", "In millions", "US$ in millions", "$ millions", "(millions)", "( in thousands )"))
    # Review counterexamples: parenthesis, currency or "in" alone do not make a unit note.
    assert not any(is_unit_note(t) for t in ("(A) Contract", "In progress", "US$ bond", "Contract A", "Revenue", "Selected LDFs", "Coverages", "", "(Contract A)", "(A)", "(US$ bond)", "in millions of contracts", "$ millions bond", "(in millions", "in millions)"))


def test_named_first_record_with_years_is_not_a_header():
    # Review counterexample: "Contract A / 2023 / 2024" under "계약명 / 시작일 / 종료일".
    # The next row is not a year row, so only the first-column protection can stop this.
    grid = rows(["계약명", "시작일", "종료일"], ["Contract A", "2023", "2024"], ["Contract B", "Pending", "Pending"])
    assert year_row_depth(grid, 1) == 1
    for name in ("(A) Contract", "In progress", "US$ bond", "(Contract A)", "(A)", "(US$ bond)"):
        assert year_row_depth(rows(["계약명", "시작일", "종료일"], [name, "2023", "2024"], ["Contract B", "Pending", "Pending"]), 1) == 1
    note = rows(["", "시작일", "종료일"], ["(in millions)", "2023", "2024"], ["Contract B", "Pending", "Pending"])
    assert year_row_depth(note, 1) == 2


def test_next_row_must_hold_real_data():
    # Review counterexample: an empty next row must not count as a record.
    blank_next = rows(["", "(1) Acc Yr", "(2) Acc Yr"], ["", "12/31/2014", "12/31/2015"], ["", "", ""], ["Bodily Injury", "6,366,867", "7,277,711"])
    assert year_row_depth(blank_next, 1) == 1
    # A section label below ("Revenue" / blanks) is content: USPS, Walmart, Goldman shapes.
    label_only_next = rows(["", "A", "B"], ["", "2024", "2023"], ["Revenue", "", ""], ["Cash", "1", "2"])
    assert year_row_depth(label_only_next, 1) == 2
    more_years = rows(["", "A", "B"], ["", "2024", "2023"], ["", "2022", "2021"], ["Cash", "1", "2"])
    assert year_row_depth(more_years, 1) == 1


def test_year_row_needs_labels_above_and_a_record_below():
    unlabeled = rows(["", "", ""], ["", "2024", "2023"], ["Revenue", "1", "2"])
    assert year_row_depth(unlabeled, 1) == 1
    series = rows(["", "A", "B"], ["", "2024", "2023"], ["", "2022", "2021"], ["x", "1", "2"])
    assert year_row_depth(series, 1) == 1  # a second year row: a year series, not a header line
    first_col_year = rows(["Year", "A", "B"], ["2024", "2023", "2022"], ["2025", "1", "2"])
    assert year_row_depth(first_col_year, 1) == 1  # column 0 numeric: time-series body
    assert year_row_depth(grid := rows(["A", "B"], ["2024", "2023"], ["1", "2"]), 1) == 1  # < 3 columns
    assert year_row_depth([], 0) == 0


def test_grid_rows_adapts_span_cells():
    grid = [[SpanCell((0, 0, 1, 1), "A", 2, 1, "th")], [SpanCell(None, "a", 1, 1), SpanCell(None, "b", 1, 1)]]
    assert grid_rows(grid) == [[("A", 2, 1)], [("a", 1, 1), ("b", 1, 1)]]


def page_with_text(doc):
    page = doc.new_page(width=320, height=300)
    for y, texts in ((75, ["Construction", "Territory", ""]), (105, ["", "46", "41"]), (135, ["Masonry", "0.87", "0.79"])):
        for x, text in zip((25, 115, 215), texts):
            if text:
                page.insert_text((x, y), text, fontsize=12)
    return page


class Session:
    """Model says only the first row is header."""

    def run(self, names, values):
        n = len(values["features"])
        return [np.array([1] + [0] * (n - 1), dtype=int)]


def r6_grid():
    # A leaf column (Construction) beside a two-column parent (Territory): the
    # first row is not a full-width title, so no leading-title offset applies.
    return [
        [SpanCell((20, 60, 100, 80), "Construction", 1, 1), SpanCell((110, 60, 300, 80), "Territory", 2, 1)],
        [SpanCell((20, 90, 100, 110), "", 1, 1), SpanCell((110, 90, 200, 110), "46", 1, 1), SpanCell((210, 90, 300, 110), "41", 1, 1)],
        [SpanCell((20, 120, 100, 140), "Masonry", 1, 1), SpanCell((110, 120, 200, 140), "0.87", 1, 1), SpanCell((210, 120, 300, 140), "0.79", 1, 1)],
    ]


def page_with_missing_tokens(doc):
    page = doc.new_page(width=320, height=300)
    for y, texts in ((75, ["Construction", "Territory", ""]), (105, ["", "N/A", "None"]), (135, ["Masonry", "0.87", "0.79"])):
        for x, text in zip((25, 115, 215), texts):
            if text:
                page.insert_text((x, y), text, fontsize=12)
    return page


class TwoRowSession:
    """Model says the first two rows are header."""

    def run(self, names, values):
        n = len(values["features"])
        return [np.array([1, 1] + [0] * (n - 2), dtype=int)]


def test_missing_token_cap_is_final_after_leaf_completion():
    # Counterexample from review: R6 depth 2 -> None/N/A cap 1 -> H2 must not
    # re-promote the missing-token row even though it resolves the span.
    grid = r6_grid()
    grid[1][1].text, grid[1][2].text = "N/A", "None"
    roles = r6_header.R6HeaderRoles(TwoRowSession(), leaf_completion=True)
    region = HeaderRegion(2, ())
    with pymupdf.open() as doc:
        page = page_with_missing_tokens(doc)
        tagged, out = roles.apply_roles(page, grid, region)
    assert out.top_header_rows == 1
    assert [c.tag for c in tagged[1]] == ["td"] * 3
    event = roles.events[-1]
    assert event["after"] == 1 and event["guard_changed"] is True and event["leaf_completed"] is False
    # The pure rule alone would have extended: the cap, not the rule, decides.
    assert leaf_completion_depth(grid_rows(grid), 1) == 2


@pytest.mark.parametrize("enabled, expected", [(True, 2), (False, 1)])
def test_r6_wiring_applies_leaf_completion_after_model(enabled, expected):
    roles = r6_header.R6HeaderRoles(Session(), leaf_completion=enabled)
    grid, region = r6_grid(), HeaderRegion(1, ())
    with pymupdf.open() as doc:
        page = page_with_text(doc)
        tagged, out = roles.apply_roles(page, grid, region)
    assert out.top_header_rows == expected
    assert [c.tag for c in tagged[1]] == (["th"] * 3 if enabled else ["td"] * 3)
    event = roles.events[-1]
    assert event["status"] == "onnx" and event["after"] == expected and event["offset"] == 0
    assert event["leaf_completed"] is enabled and event["guard_changed"] is False
