"""Header over-tag demotion for final header roles (H3 candidate).

After the R6 header decision, the header prefix sometimes swallows a row that
is not a column label row. Two shapes are demoted, from the last header row
upward, never below one header row:

- common note: outside column 0 the row carries exactly one parenthesized
  group, e.g. "(in millions)" in one cell or split over cells as "(in" /
  "millions)" or "(dollars" / "in thousands)", and that group contains a word.
  Per-column parenthesized labels such as "(Actual)" / "(Budget)" form one
  group per column and stay; "(1) (2)" / "(A) (B)" indices stay too.
- section label: exactly one non-empty cell, in column 0 and narrower than
  the table, while the header above labels other columns but has no label in
  column 0. A first-column header wrapped over two rows ("Accident" /
  "Year") or a unit under its label ("Sleeve length" / "(mm)") has a label
  above and stays.

The rule reads only the predicted grid's text and spans. Rows are row-major
``(text, colspan, rowspan)`` triples as in ``header_leaf_completion``; a
precomputed ``occupancy`` result may be passed to avoid recomputation.
"""

import re

from pymupdf4llm._table_pipeline.header_leaf_completion import occupancy

_WORD = re.compile(r"[^\W\d_]{2,}")


def _row(cells, r):
    return [(c0, c1, text) for r0, _, c0, c1, text in cells if r0 == r]


def _labels_above(cells, r):
    return {cj for r0, r1, c0, c1, text in cells if r1 <= r and text for cj in range(c0, c1)}


def is_common_note_row(cells, ncols, r):
    texts = [t for c0, _, t in _row(cells, r) if t and c0 > 0]
    if not texts:
        return False
    joined = " ".join(texts).strip()
    one_group = joined.startswith("(") and joined.endswith(")") and joined.count("(") == 1 and joined.count(")") == 1
    return one_group and _WORD.search(joined) is not None and len(_labels_above(cells, r) - {0}) >= 2


def is_section_row(cells, ncols, r):
    texts = [(c0, c1, t) for c0, c1, t in _row(cells, r) if t]
    if len(texts) != 1:
        return False
    c0, c1, _ = texts[0]
    if c0 != 0 or c1 - c0 >= ncols:
        return False
    above = _labels_above(cells, r)
    return 0 not in above and bool(above - set(range(c1)))


def demotion_depth(rows, depth, cells=None):
    """Return the header depth after demoting trailing note/section rows."""
    if cells is None:
        cells = occupancy(rows)
    cells, ncols = cells
    if ncols < 2:
        return depth
    while depth > 1 and (is_common_note_row(cells, ncols, depth - 1) or is_section_row(cells, ncols, depth - 1)):
        depth -= 1
    return depth
