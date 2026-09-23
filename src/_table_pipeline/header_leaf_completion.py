"""Colspan leaf completion for final header roles (H2 candidate).

After the final header depth is decided, a header cell that spans several
columns and has no single-column label under any of those columns leaves the
column keys unresolved. This rule extends the header prefix over the following
row only when that row reads as the missing leaf-label row:

- the row has one single-column, non-empty cell under every column of at
  least one such unresolved span (a spanning body cell resolves nothing);
- no numeric cell sits under a column that already has a leaf label;
- the row is not a full-width single cell (a title or section row);
- the next row does not repeat the row's column occupancy and numeric
  pattern (that would make the row the first record of a regular body).

The rule reads only the predicted grid's own text and spans; no geometry,
GT, file names or scores. It never shrinks the header. The same function
serves the offline HTML replay so product and replay stay identical.
"""

import re

_NUMERIC = re.compile(r"^[\s$€£(),.%\-–—+0-9/:]+$")


def is_numeric(text):
    return bool(text) and bool(_NUMERIC.match(text)) and any(ch.isdigit() for ch in text)


def occupancy(rows):
    """Resolve ragged span rows into (r0, r1, c0, c1, text) cells and a column
    count, exactly as an HTML renderer places them: ``rows`` is row-major and
    each entry is ``(text, colspan, rowspan)``."""
    occupied, cells = set(), []
    for ri, row in enumerate(rows):
        ci = 0
        for text, cs, rs in row:
            cs, rs = max(1, int(cs)), max(1, int(rs))
            while (ri, ci) in occupied:
                ci += 1
            for rj in range(ri, ri + rs):
                for cj in range(ci, ci + cs):
                    occupied.add((rj, cj))
            cells.append((ri, ri + rs, ci, ci + cs, " ".join(str(text or "").split())))
            ci += cs
    ncols = max((c for _, c in occupied), default=-1) + 1
    return cells, ncols


def row_shape(cells, r, ncols):
    shape = [""] * ncols
    for r0, r1, c0, c1, text in cells:
        if r0 <= r < r1 and text:
            kind = "num" if is_numeric(text) else "text"
            for cj in range(c0, min(c1, ncols)):
                shape[cj] = kind
    return tuple(shape)


def leaf_completion_depth(rows, depth, cells=None):
    """Return the header depth after leaf completion, ``depth`` if unchanged.
    ``cells`` may be a precomputed ``occupancy(rows)`` result."""
    cells, ncols = occupancy(rows) if cells is None else cells
    nrows = len(rows)
    if not 0 < depth < nrows or ncols < 2:
        return depth
    while depth < nrows:
        header = [c for c in cells if c[1] <= depth]
        leaf_cols = {c0 for _, _, c0, c1, text in header if text and c1 - c0 == 1}
        spans = [
            (c0, c1)
            for _, _, c0, c1, text in header
            if text and 1 < c1 - c0 < ncols and not any(cj in leaf_cols for cj in range(c0, c1))
        ]
        if not spans:
            break
        span_cols = {cj for c0, c1 in spans for cj in range(c0, c1)}
        row = [(c0, c1, text) for r0, _, c0, c1, text in cells if r0 == depth and text]
        if not row or (len(row) == 1 and row[0][1] - row[0][0] == ncols):
            break
        unit_cols = {c0 for c0, c1, _ in row if c1 - c0 == 1}
        if not any(all(cj in unit_cols for cj in range(c0, c1)) for c0, c1 in spans):
            break
        if any(is_numeric(t) and any(cj in leaf_cols - span_cols for cj in range(c0, c1)) for c0, c1, t in row):
            break
        if depth + 1 < nrows and row_shape(cells, depth, ncols) == row_shape(cells, depth + 1, ncols):
            break
        depth += 1
    return depth


_YEAR = re.compile(r"^(19|20)\d{2}$")
_DATE = re.compile(
    r"^\d{1,2}\s*/\s*\d{1,2}\s*/\s*(19|20)?\d{2}$|^(19|20)\d{2}\s*[-/]\s*\d{1,2}$|^\d{1,2}\s*/\s*(19|20)\d{2}$"
)


def is_year_or_date(text):
    t = str(text or "").strip()
    return bool(_YEAR.match(t) or _DATE.match(t))


# Parentheses are presentation, never evidence of units. Match the whole
# unwrapped expression so a record name cannot pass via a unit-like prefix.
_SCALE = r"(?:millions?|thousands?|billions?|hundreds?|'?000s?|mm|bn|k)"
_CURRENCY = r"(?:us\$|usd|eur|gbp|dollars?|[$€£¥₩])"
_UNIT_NOTE = re.compile(
    r"(?:(?:" + _CURRENCY + r")\s*(?:in\s+)?|in\s+)?" + _SCALE,
    re.IGNORECASE,
)


def is_unit_note(text):
    """A first-column cell that annotates the header rather than naming a
    record: "(in millions)", "$ in millions", "in thousands". A bare label
    such as "Contract A" is a record name and is not a unit note."""
    t = str(text or "").strip()
    if t.startswith('(') and t.endswith(')'):
        t = t[1:-1].strip()
    return bool(t) and _UNIT_NOTE.fullmatch(t) is not None


def year_row_depth(rows, depth, cells=None):
    """H2 extension: include a year/date row under labeled header columns.

    Extends over row ``depth`` when its cells outside column 0 are at least
    two years or dates, each under a labeled header column, column 0 is empty
    or a unit note (never a record name such as "Contract A"), and the next
    row has content (a record or a section label such as "Revenue") whose
    value cells, if any, are not another year row; a blank next row fails. GT treats these rows as the second header line
    ("(1) Acc Yr" / "12/31/2014", "Consolidated" / "2024"). Never shrinks."""
    cells, ncols = occupancy(rows) if cells is None else cells
    nrows = len(rows)
    if not 0 < depth < nrows - 1 or ncols < 3:
        return depth
    while depth < nrows - 1:
        row = [(c0, c1, t) for r0, _, c0, c1, t in cells if r0 == depth and t]
        values = [(c0, c1, t) for c0, c1, t in row if c0 > 0]
        first = [t for c0, _, t in row if c0 == 0]
        if len(values) < 2 or not all(is_year_or_date(t) for _, _, t in values):
            break
        if first and not is_unit_note(first[0]):
            break  # A named first column is a record, not a header note.
        labeled = {cj for r0, r1, c0, c1, t in cells if r1 <= depth and t for cj in range(c0, c1)}
        if not all(any(cj in labeled for cj in range(c0, c1)) for c0, c1, _ in values):
            break
        nxt_all = [t for r0, _, c0, c1, t in cells if r0 == depth + 1 and t]
        nxt_vals = [t for r0, _, c0, c1, t in cells if r0 == depth + 1 and t and c0 > 0]
        if not nxt_all or (nxt_vals and all(is_year_or_date(t) for t in nxt_vals)):
            break  # The next row must exist with content (a record or a section
            # label), and its value cells must not be another year row.
        depth += 1
    return depth


def grid_rows(grid):
    """Adapt a SpanCell placement grid to ``leaf_completion_depth`` rows."""
    return [[(cell.text, cell.colspan, cell.rowspan) for cell in row] for row in grid]
