"""H6 header band split on synthetic pages and grids."""

import pymupdf
from pymupdf import table

from pymupdf4llm._table_pipeline import header_band_split as hbs


def page_with(doc, lines):
    page = doc.new_page(width=400, height=300)
    for y, items in lines:
        for item in items:
            x, text = item[0], item[1]
            page.insert_text((x, y), text, fontsize=item[2] if len(item) > 2 else 10)
    return page


def grid(rows_y, cols_x):
    return [[[cols_x[i], y0, cols_x[i + 1], y1] for i in range(len(cols_x) - 1)] for y0, y1 in rows_y]


COLS = [20, 120, 220, 320]


def test_parent_line_above_leaf_labels_is_split_into_its_own_row():
    # Row 0 band (y 40-80) holds "Non-Tobacco" (x ~140-260, crossing the 220 boundary, over Female and Male) above
    # the leaf labels "Age | Female | Male" (y~72). TX964 shape.
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(150, "Non-Tobacco", 16)]), (74, [(25, "Age"), (125, "Female"), (225, "Male")]), (100, [(25, "65"), (125, "1.0"), (225, "1.1")])])
        cells = grid([(40, 80), (85, 110)], COLS)
        out, event = hbs.split_header_band(page, cells)
    assert event["status"] == "split" and 52 < event["y"] < 74
    assert len(out) == 3 and abs(out[0][0][3] - event["y"]) < 0.01 and out[0][0][3] == out[1][0][1]
    assert out[2] == cells[1]
    # "Non-Tobacco" (x ~150-240) straddles the 220 boundary: one wide cell over columns 1-2, slot 2 becomes None.
    assert out[0][1][0] == 120 and out[0][1][2] == 320 and out[0][2] is None and out[0][0][2] == 120


def test_title_above_header_is_split():
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(100, "Zips 750-753, 760-762", 14)]), (74, [(25, "Attained"), (125, "Mode"), (225, "Plan F")]), (100, [(25, "65"), (125, "Annual"), (225, "$465")])])
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], COLS))
    assert event["status"] == "split" and len(out) == 3


def test_two_line_wrapped_header_within_columns_is_left_alone():
    # "Attained" / "Age" stacked inside column 0: no upper segment crosses a boundary.
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(25, "Attained"), (125, "Plan"), (225, "Mode")]), (74, [(25, "Age"), (125, "F")]), (100, [(25, "65"), (125, "1.0")])])
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], COLS))
    assert event["status"] == "no_split" and out is not None and len(out) == 2


def test_single_line_row_and_crossing_lower_line_are_left_alone():
    with pymupdf.open() as doc:
        page = page_with(doc, [(60, [(25, "Age"), (125, "Female"), (225, "Male")]), (100, [(25, "65"), (125, "1.0")])])
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], COLS))
        assert event["status"] == "no_split"
        # Both lines cross boundaries (paragraph text): no split.
        page2 = page_with(doc, [(52, [(60, "Some long introductory sentence here")]), (74, [(60, "and its continuation line as well")]), (100, [(25, "65"), (125, "1.0")])])
        out2, event2 = hbs.split_header_band(page2, grid([(40, 80), (85, 110)], COLS))
        assert event2["status"] == "no_split"


def test_per_column_labels_glued_together_are_not_one_span():
    # BRWS page953 shape: "COLL/UMPD" over every column, close together: no word crosses a boundary.
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(30, "COLL/UMPD"), (130, "COLL/UMPD"), (230, "COLL/UMPD")]), (74, [(25, "Years"), (125, "Loss"), (225, "Count")]), (100, [(25, "1"), (125, "2"), (225, "3")])])
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], COLS))
    assert event["status"] == "no_split"


def test_wrapped_paragraph_overflowing_its_column_is_not_a_parent():
    # Overflow shape: a long cell text starts at its column's left edge and overflows rightwards, with a
    # word straddling the boundary (exercises _is_parent_label). The real 1657221585 pages are already
    # excluded earlier because no single word straddles a boundary there.
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(20, "1.11.19"), (121, "Product obtained from the production of")]), (74, [(121, "starch"), (221, "> 85 %")]), (100, [(25, "1.11.20"), (125, "x"), (225, "y")])])
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], COLS))
    assert event["status"] == "no_split"


def test_misaligned_per_column_labels_straddling_shifted_boundaries_are_not_parents():
    # BRWS page990 shape: identical labels over every column, each straddling a shifted boundary,
    # with one wrapped leaf ("Earned Car", "Indicated") under it: a parent needs >= 2 leaves.
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(100, "COLL/UMPD"), (200, "COLL/UMPD"), (300, "COLL/UMPD")]), (74, [(25, "Years"), (225, "Count")]), (100, [(25, "1"), (125, "2"), (225, "3"), (325, "4")])])
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], [20, 120, 220, 320, 420]))
    assert event["status"] == "no_split"


def test_several_parents_each_straddling_a_boundary_are_split():
    # PrintableRules shape: five parents on one line ("August ... December"), each over two leaves;
    # the line straddles five boundaries yet is a parent line, not per-column labels.
    cols = [20, 70, 120, 170, 220, 270, 320]
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(100, "August"), (200, "Sept.")]), (74, [(75, "1-15"), (125, "16-31"), (175, "1-15"), (225, "16-31")]), (100, [(25, "1"), (75, "2"), (125, "3"), (175, "4"), (225, "5"), (275, "6")])])
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], cols))
    assert event["status"] == "split"
    assert out[0][1][0] == 70 and out[0][1][2] == 170 and out[0][2] is None
    assert out[0][3][0] == 170 and out[0][3][2] == 270 and out[0][4] is None


def test_tall_cell_holding_the_lower_line_is_cut_too():
    # PrintableRules shape: short cells for Jan-July, a taller cell for "August" over "1-15 | 16-31".
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(25, "Days"), (125, "Jan."), (240, "August", 14)]), (74, [(225, "1-15"), (275, "16-31")]), (100, [(25, "1"), (125, "2"), (225, "3"), (275, "4")])])
        # Short cells span both lines (40-80); the August cells are taller (40-95) but hold the lower line.
        cells = [[[20, 40, 120, 80], [120, 40, 220, 80], [220, 40, 270, 95], [270, 40, 320, 95]], [[20, 85, 120, 110], [120, 85, 220, 110], [220, 95, 270, 110], [270, 95, 320, 110]]]
        out, event = hbs.split_header_band(page, cells)
    assert event["status"] == "split" and abs(out[0][2][3] - event["y"]) < 0.01 and out[0][3] is None and out[1][2] is not None


def test_lower_line_straddling_the_grid_boundary_is_not_split():
    # PrintableRules shape: the lower line's words hang over the row boundary; a sliver row would tear them.
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(150, "Non-Tobacco", 16)]), (79, [(125, "Female"), (225, "Male")]), (100, [(25, "65"), (125, "1.0"), (225, "1.1")])])
        out, event = hbs.split_header_band(page, grid([(40, 78), (78, 110)], COLS))
    assert event["status"] == "no_split"


def test_rowspan_corner_cell_does_not_pull_next_line_into_the_band():
    # SERFF CA page569 shape: the grid already has the parent row; the corner
    # cell "Territory" spans both header rows. Nothing to split.
    with pymupdf.open() as doc:
        page = page_with(doc, [(60, [(25, "Territory"), (150, "Executive", 16)]), (84, [(125, "Current"), (225, "Proposed")]), (110, [(25, "1"), (125, "2"), (225, "3")])])
        cells = [[[20, 40, 120, 95], [120, 40, 220, 70], [220, 40, 320, 70]], [None, [120, 70, 220, 95], [220, 70, 320, 95]], [[20, 100, 120, 120], [120, 100, 220, 120], [220, 100, 320, 120]]]
        out, event = hbs.split_header_band(page, cells)
    assert event["status"] == "no_split"


def test_centred_label_beside_a_parent_is_kept_as_a_rowspan_cell():
    # PrintableRules shape: "Jan." sits vertically centred on the band beside "August" over "1-15 | 16-31".
    # Its cell is kept whole (rowspan) instead of being cut into "Jan." / "".
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(200, "August", 14)]), (64, [(30, "Jan.")]), (74, [(130, "1-15"), (230, "16-31")]), (100, [(25, "1"), (125, "2"), (225, "3")])])
        cells = grid([(40, 80), (85, 110)], COLS)
        out, event = hbs.split_header_band(page, cells)
    assert event["status"] == "split" and event["rowspan_slots"] == {0: "Jan."}
    assert out[0][0] == [20.0, 40.0, 120.0, 80.0] and out[1][0] is None
    assert out[0][1][0] == 120 and out[0][1][2] == 320 and out[0][2] is None
    assert out[1][1] is not None and out[1][2] is not None


def test_leaf_under_a_parent_is_not_a_rowspan_cell_even_when_centred():
    # The centred line is under the parent "August": it is the first wrapped leaf line, not a rowspan cell.
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(200, "August", 14)]), (68, [(130, "1-15"), (230, "16-")]), (79, [(230, "31")]), (100, [(25, "1"), (125, "2"), (225, "3")])])
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], COLS))
    assert event["status"] == "split" and event["rowspan_slots"] == {}


def test_centred_corner_labels_overlapping_the_parent_line_do_not_block_the_split():
    # tabular_2 shape: "CIDADE" / "NOME" are centred rowspan corners whose boxes overlap the taller
    # parent line "EFETIVO" in y; without setting them aside the two groups are not y-separated.
    cols = [20, 120, 220, 320, 420]
    with pymupdf.open() as doc:
        page = page_with(doc, [(56, [(280, "EFETIVO", 16)]), (63, [(30, "CIDADE"), (130, "NOME")]), (76, [(230, "ENF."), (330, "QUARTO")]), (100, [(25, "1"), (125, "2"), (225, "3"), (325, "4")])])
        words = [w for w in page.get_text("words") if w[3] < 90]
        parent = next(w for w in words if w[4] == "EFETIVO"); corner = next(w for w in words if w[4] == "CIDADE")
        assert corner[1] < parent[3]  # the shapes really overlap in y
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], cols))
    assert event["status"] == "split" and set(event["rowspan_slots"].values()) == {"CIDADE", "NOME"}
    assert out[1][0] is None and out[1][1] is None and out[0][2][2] == 420 and out[0][3] is None


def test_left_aligned_sibling_title_disqualifies_the_line():
    # TX810 shape: side-by-side tables merged into one; their titles are left-aligned at column edges.
    # One title happens to be centred, but its sibling starts at a column's left edge: no parent line.
    cols = [20, 70, 120, 170, 220, 270, 320]
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(21, "Zips All Others"), (185, "Zips 750-753")]), (74, [(25, "Age"), (75, "Mode"), (125, "Plan"), (175, "Age"), (225, "Mode"), (275, "Plan")]), (100, [(25, "1"), (75, "2"), (125, "3"), (175, "4"), (225, "5"), (275, "6")])])
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], cols))
    assert event["status"] == "no_split"


def test_lone_title_is_widened_over_the_leaf_columns_it_is_centred_on():
    # CA2475 shape: "Age-to-Age" straddles two boundaries but is the title of all five development
    # columns (70-320, centred on it), not of the row-key column "Year" on the left.
    cols = [20, 70, 120, 170, 220, 270, 320]
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(167, "Age-to-Age", 11)]), (74, [(25, "Year"), (75, "12"), (125, "24"), (175, "36"), (225, "48"), (275, "60")]), (100, [(25, "1"), (75, "2"), (125, "3"), (175, "4"), (225, "5"), (275, "6")])])
        title = next(w for w in page.get_text("words") if w[4] == "Age-to-Age")
        assert title[0] < 170 < title[2] and title[0] < 220 < title[2] and abs((title[0] + title[2]) / 2 - 195) < 3
        out, event = hbs.split_header_band(page, grid([(40, 80), (85, 110)], cols))
    assert event["status"] == "split"
    assert out[0][0][2] == 70  # "Year" column keeps its own (empty) cell above
    assert out[0][1][0] == 70 and out[0][1][2] == 320 and all(out[0][i] is None for i in range(2, 6))


def test_gaps_and_empty_grids():
    with pymupdf.open() as doc:
        page = page_with(doc, [(52, [(150, "Non-Tobacco", 16)]), (74, [(25, "Age"), (125, "Female"), (225, "Male")])])
        cells = grid([(40, 80), (85, 110)], COLS)
        cells[0][0] = None  # a gap in row 0 (outside the parent span) stays a gap in both new rows
        out, event = hbs.split_header_band(page, cells)
        assert event["status"] == "split" and out[0][0] is None and out[1][0] is None
        assert hbs.split_header_band(page, [])[1]["status"] == "no_split"
