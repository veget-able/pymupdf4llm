"""H6 candidate: split a TGIF grid's first row when it holds two text lines.

The Layout/TGIF grid tiles the table bbox vertically, so a title or parent
header line that received no grid row of its own falls into the first row's
cells together with the real header line below it, and word assignment by
cell centre then stuffs both lines into the same cells ("Zips All Attained").

This pass runs right after ``refine_grid_structure`` (before span resolution
and header decisions). It looks only at the first grid row's band (bottom =
the shortest row-0 cell: taller cells are rowspan cells the grid already
gives):

- slots whose band text is a single line centred on the band, lying inside
  the slot and not under a spanning label, are rowspan cells ('Jan.' beside
  'August / 1-15 | 16-31', 'CIDADE' beside 'EFETIVO / ENFERMARIA | QUARTO');
  their words take no part in the line analysis and their cells are kept
  whole (None in the lower row);
- the remaining page words are clustered into visual lines by y-overlap, and
  each line is cut into segments at horizontal gaps wider than 1.5 x the line
  height;
- a split is made between an upper group of lines and a lower group when
  they are vertically separated, every lower segment lies inside one grid
  column, the lower group labels at least two distinct columns, and the
  upper group has spanning segments: a segment crossing an interior column
  boundary with a single word straddling it, centred over its children (not
  starting at a column's left edge), and with at least two lower segments
  under it (a per-column label that merely straddles a shifted boundary has
  one leaf under it);
- the first row's cell rectangles are cut at the mid-gap y; the upper row is
  built with one wide cell per spanning segment (None in the covered slots).

GT-checked motivation (final-table re-identification, forced-span-top-row):
20 geometric candidates; 8 have text-matched GT colspan, 2 require direct
GT inspection, 8 have no matching span, and 2 have no GT header.
The accepted full-503 result improves six final tables on six pages.
"""


import pymupdf
from pymupdf import table

GAP_RATIO = 1.5
CENTRE_TOLERANCE = 0.15


def _cluster_lines(words):
    lines = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        cy = (w[1] + w[3]) / 2
        for line in lines:
            if line["y0"] <= cy <= line["y1"] or w[1] <= (line["y0"] + line["y1"]) / 2 <= w[3]:
                line["y0"], line["y1"] = min(line["y0"], w[1]), max(line["y1"], w[3])
                line["words"].append(w)
                break
        else:
            lines.append({"y0": w[1], "y1": w[3], "words": [w]})
    for line in lines:
        height = max(1e-6, line["y1"] - line["y0"])
        segs, cur = [], []
        for w in sorted(line["words"], key=lambda w: w[0]):
            if cur and w[0] - cur[-1][2] > GAP_RATIO * height:
                segs.append(cur)
                cur = []
            cur.append(w)
        if cur:
            segs.append(cur)
        line["segments"] = [(min(w[0] for w in s), max(w[2] for w in s)) for s in segs]
        line["segment_words"] = segs
    return sorted(lines, key=lambda l: l["y0"])


def _word_crossings(words, bounds):
    """Interior boundaries that a single word straddles: only these justify
    merging two columns. Per-column labels that merely sit close together
    ("COLL/UMPD COLL/UMPD ...") cross no boundary word-wise."""
    return {b for b in bounds[1:-1] for w in words if w[0] + 1.0 < b < w[2] - 1.0}


def _is_parent_label(x0, x1, bounds):
    """A parent label is centred over its children: it neither starts at the
    left edge of its first column nor is it a wrapped paragraph overflowing
    to the right. Reject segments that start within 2pt of a column's left
    edge unless they also end within 2pt of a column's right edge (a
    full-width title)."""
    starts_at_edge = any(abs(x0 - b) <= 2.0 for b in bounds[:-1])
    ends_at_edge = any(abs(x1 - b) <= 2.0 for b in bounds[1:])
    return not starts_at_edge or ends_at_edge


def _column_of(x0, x1, bounds):
    """Index of the column [bounds[i], bounds[i+1]) containing the segment, or
    None when the segment crosses an interior boundary."""
    for i in range(len(bounds) - 1):
        if bounds[i] - 1.0 <= x0 and x1 <= bounds[i + 1] + 1.0:
            return i
    return None


def _overlapped_columns(x0, x1, bounds, min_overlap=3.0):
    """Columns a segment reaches into by at least 3pt (or a fifth of a narrow
    column): the columns a parent label sits over, even when the label is
    narrower than its children."""
    cols = []
    for i in range(len(bounds) - 1):
        overlap = min(x1, bounds[i + 1]) - max(x0, bounds[i])
        if overlap >= min(min_overlap, 0.2 * (bounds[i + 1] - bounds[i])):
            cols.append(i)
    return cols


def _spanning_segments(line, bounds):
    """Segments of a line that are spanning labels: crossing a boundary with a
    straddling word and centred over their children."""
    out = []
    for (x0, x1), ws in zip(line["segments"], line["segment_words"]):
        if _column_of(x0, x1, bounds) is None and _word_crossings(ws, bounds) and _is_parent_label(x0, x1, bounds):
            out.append((x0, x1, ws))
    return out


def _rowspan_slots(band, slots, words, spans):
    """Slots whose band text is one line inside the slot, centred on the band
    and not under a spanning label: cells spanning both header rows. Returns
    {slot index: words}."""
    per = {}
    for w in words:
        cx = (w[0] + w[2]) / 2
        for i, s in enumerate(slots):
            if s is not None and s[0] <= cx <= s[1]:
                per.setdefault(i, []).append(w)
                break
    out = {}
    for i, ws in per.items():
        s0, s1 = slots[i]
        if any(w[0] < s0 - 1.0 or w[2] > s1 + 1.0 for w in ws):
            continue
        if any(x0 < s1 - 1.0 and x1 > s0 + 1.0 for x0, x1, _ in spans):
            continue
        if len(_cluster_lines(ws)) != 1:
            continue
        y0, y1 = min(w[1] for w in ws), max(w[3] for w in ws)
        if abs((y0 + y1) / 2 - (band.y0 + band.y1) / 2) <= CENTRE_TOLERANCE * band.height:
            out[i] = ws
    return out


def _title_extent(spanning, upper_words, lower_cols, bounds):
    """When the upper group is a single label ('Age to Age Factors' over ten
    development columns), it is a title of every leaf column it is centred
    over, not only of the columns its words straddle. Returns
    {(x0, x1): (rx0, rx1)}: the widest contiguous run of leaf columns that
    contains the label's columns and is centred on the label (within 5% of
    the run width); empty when the upper group has several labels."""
    if len(spanning) != 1:
        return {}
    x0, x1 = spanning[0]
    if any(w[0] < x0 - 1.0 or w[2] > x1 + 1.0 for w in upper_words):
        return {}
    span_cols = _overlapped_columns(x0, x1, bounds)
    leaf = set(lower_cols)
    centre = (x0 + x1) / 2
    best = None
    for i in sorted(leaf):
        for j in sorted(leaf):
            if i > j or i > span_cols[0] or j < span_cols[-1] or not all(c in leaf for c in range(i, j + 1)):
                continue
            rx0, rx1 = bounds[i], bounds[j + 1]
            if abs((rx0 + rx1) / 2 - centre) <= 0.05 * (rx1 - rx0) and (best is None or rx1 - rx0 > best[1] - best[0]):
                best = (rx0, rx1)
    if best is None or best[1] - best[0] <= x1 - x0:
        return {}
    return {spanning[0]: best}


def split_header_band(page, cells):
    """Return (new_cells, event). ``cells`` is the row-major rect grid."""
    event = {"stage": "header_band_split", "status": "no_split"}
    if not cells:
        return cells, event
    first = next((i for i, row in enumerate(cells) if any(c is not None for c in row)), None)
    if first is None:
        return cells, event
    row = cells[first]
    live = [pymupdf.Rect(c) for c in row if c is not None]
    # The row's bottom is the shortest cell's bottom: taller cells in the same
    # row are rowspan cells reaching into the next row and must not pull the
    # next row's text line into this band.
    band = pymupdf.Rect(min(r.x0 for r in live), min(r.y0 for r in live), max(r.x1 for r in live), min(r.y1 for r in live))
    if band.height < 4.0:
        return cells, event
    xs = sorted({round(float(v), 1) for r in cells for c in r if c is not None for v in (c[0], c[2])})
    bounds = [x for x in xs if band.x0 - 1.0 <= x <= band.x1 + 1.0]
    if len(bounds) < 3:
        return cells, event
    words = [w for w in table._refine_page_words(page)
             if band.x0 <= (w[0] + w[2]) / 2 <= band.x1 and band.y0 <= (w[1] + w[3]) / 2 <= band.y1]
    slots = [None if c is None else (float(c[0]), float(c[2])) for c in row]
    # Rowspan cells by text position: decided before the line analysis so a
    # centred corner label overlapping the parent line in y cannot glue the
    # two groups together.
    pre_spans = [s for l in _cluster_lines(words) for s in _spanning_segments(l, bounds)]
    rowspan = _rowspan_slots(band, slots, words, pre_spans)
    rowspan_ids = {id(w) for ws in rowspan.values() for w in ws}
    lines = _cluster_lines([w for w in words if id(w) not in rowspan_ids])
    if len(lines) < 2:
        return cells, event
    chosen = None
    for k in range(1, len(lines)):
        upper, lower = lines[:k], lines[k:]
        top_y1 = max(l["y1"] for l in upper)
        bottom_y0 = min(l["y0"] for l in lower)
        if bottom_y0 < top_y1 - 0.5:
            continue
        lower_segments = [(x0, x1) for l in lower for x0, x1 in l["segments"]]
        lower_cols = [_column_of(x0, x1, bounds) for x0, x1 in lower_segments]
        if not lower_cols or any(c is None for c in lower_cols) or len(set(lower_cols)) < 2:
            continue
        # The lower group must sit inside this band with room for its own
        # row: a line straddling the grid boundary below (a misplaced row
        # boundary) would only yield a sliver row and torn words.
        lower_h = max(l["y1"] - l["y0"] for l in lower)
        if band.y1 - bottom_y0 < 0.8 * lower_h:
            continue
        # A spanning label is a parent only with >= 2 leaf labels (distinct
        # columns) under it; a per-column label straddling a shifted boundary
        # ("COLL/UMPD" over "Earned Car") has one. Siblings share their
        # alignment: a crossing label that starts at a column's left edge
        # makes the whole line a row of left-aligned titles (side-by-side
        # tables merged into one), not a parent line.
        spanning, edge_aligned = [], False
        for l in upper:
            for (x0, x1), ws in zip(l["segments"], l["segment_words"]):
                if _column_of(x0, x1, bounds) is not None or not _word_crossings(ws, bounds):
                    continue
                if not _is_parent_label(x0, x1, bounds):
                    edge_aligned = True
                    continue
                cols = set(_overlapped_columns(x0, x1, bounds))
                leaves = {c for c in lower_cols if c in cols}
                if len(leaves) >= 2:
                    spanning.append((x0, x1))
        if not spanning or edge_aligned:
            continue
        chosen = (k, (top_y1 + bottom_y0) / 2, spanning, lower_cols)
    if chosen is None:
        return cells, event
    k, y, spanning, lower_cols = chosen
    if y - band.y0 < 3.0 or band.y1 - y < 3.0:
        return cells, event
    widen = _title_extent(spanning, [w for l in lines[:k] for w in l["words"]], lower_cols, bounds)
    # Upper row: one cell per text segment spanning the grid columns it
    # covers (a colspan cell is a wide rect with None in the covered slots,
    # exactly how Table.rows represents merged cells); columns untouched by
    # any segment keep a unit cell so the row stays aligned with the grid.
    # Only cells whose bottom is the row bottom are cut; rowspan cells (taller)
    # keep their rectangle in the upper row and are skipped in the lower row.
    # A taller cell is a rowspan corner cell (kept whole) unless it holds words
    # of the lower group itself, in which case it is cut like the others.
    lower_words = [w for l in lines[k:] for w in l["words"]]
    def holds_lower(c):
        return any(c[0] <= (w[0] + w[2]) / 2 <= c[2] and y <= (w[1] + w[3]) / 2 <= c[3] for w in lower_words)
    tall = [c is not None and ((float(c[3]) > band.y1 + 1.0 and not holds_lower(c)) or i in rowspan) for i, c in enumerate(row)]
    upper_row = [None if c is None else ([float(v) for v in c] if tall[i] else [float(c[0]), float(c[1]), float(c[2]), float(y)]) for i, c in enumerate(row)]
    covered = set(i for i, t in enumerate(tall) if t)
    for line in lines[:k]:
        for (x0, x1), ws in zip(line["segments"], line["segment_words"]):
            if not any(abs(x0 - sx0) < 0.01 and abs(x1 - sx1) < 0.01 for sx0, sx1 in spanning):
                continue
            if (x0, x1) in widen:
                # a lone title: every leaf column it is centred over
                rx0, rx1 = widen[(x0, x1)]
                run = [i for i, s in enumerate(slots) if s is not None and s[1] > rx0 + 1.0 and s[0] < rx1 - 1.0]
            else:
                crossings = _word_crossings(ws, bounds)
                # Merge only across boundaries a word straddles; a segment that
                # straddles 128 and 151 becomes one cell over those three columns.
                idx = [i for i, s in enumerate(slots) if s is not None and s[1] > x0 + 1.0 and s[0] < x1 - 1.0]
                keep = [i for i in idx if i == idx[0] or any(abs(slots[i][0] - b) <= 1.0 for b in crossings)]
                # contiguous run from the first slot through the last crossed boundary
                run = [i for i in idx if i <= max(keep)]
            if len(run) < 2 or any(i in covered for i in run):
                continue
            upper_row[run[0]] = [slots[run[0]][0], float(band.y0), slots[run[-1]][1], float(y)]
            for i in run[1:]:
                upper_row[i] = None
            covered.update(run)
    lower_row = [None if (c is None or tall[i]) else [float(c[0]), float(y), float(c[2]), float(c[3])] for i, c in enumerate(row)]
    new_cells = list(cells[:first]) + [upper_row, lower_row] + list(cells[first + 1:])
    event.update(status="split", y=round(y, 2), band=[round(v, 2) for v in band], upper_lines=k,
                 row0_before=[None if c is None else [round(v, 1) for v in c] for c in row],
                 upper_row=[None if c is None else [round(v, 1) for v in c] for c in upper_row],
                 upper_spans=[[round(c[0]), round(c[2])] for c in upper_row if c is not None and c[2] - c[0] > 0],
                 rowspan_slots={i: " ".join(w[4] for w in ws)[:30] for i, ws in rowspan.items()},
                 lower_lines=len(lines) - k,
                 upper_text=[" ".join(w[4] for w in l["words"])[:60] for l in lines[:k]])
    return new_cells, event
