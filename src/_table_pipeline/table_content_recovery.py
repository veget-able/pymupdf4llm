"""Restore GNN-owned content from retained nodes and final placements.

No page reads or model calls. Cells with ambiguous structure remain unchanged;
unassigned source text is preserved as table-associated, unresolved content.
Structural decisions never read GT, page names, or a target row/column count.
"""

from collections import Counter
from copy import copy
from dataclasses import dataclass
from statistics import median
import re
import unicodedata

from pymupdf._table_spans import SpanCell, CellSource
from pymupdf.table import extract_text
from pymupdf4llm.helpers.table_html.reconstruct import _table_grid_matrices

from pymupdf4llm._table_pipeline.fragment_consolidation import column_intervals
from pymupdf4llm._table_pipeline.union_content_recovery import _bands, _grid_rows_y, _union_box


@dataclass(frozen=True)
class SourceNode:
    index: int
    bbox: tuple
    text: str
    scope: tuple = ()


def node_sources(nodes):
    """Actual retained GNN inputs selected by an approved cell producer."""
    return tuple(CellSource("gnn_node", n.index, tuple(n.bbox), n.text, n, n.scope) for n in nodes)


def _cx(box):
    return (box[0] + box[2]) / 2


def _cy(box):
    return (box[1] + box[3]) / 2


def _tokens(text):
    # Punctuation and complete numeric tokens matter; '0' is not part of '100'.
    return re.findall(r"\w+|[^\w\s]", unicodedata.normalize("NFKC", text or "").casefold())


def readable_nodes(tables, nodes):
    """Use existing finder characters to undo spacing inserted in GNN text.

    Only whitespace can change; non-whitespace characters must match exactly.
    This calls the existing table text assembler, never PDF extraction.
    """
    chars = next((t._chars for t in tables if getattr(t, "_chars", None) is not None), None)
    if chars is None:
        return nodes
    result = []
    for n in nodes:
        b = n.bbox
        selected = [
            c
            for c in chars
            if b[0] - 1 <= (c["x0"] + c["x1"]) / 2 <= b[2] + 1 and b[1] - 1 <= (c["top"] + c["bottom"]) / 2 <= b[3] + 1
        ]
        display = extract_text(selected) if selected else n.text
        if (
            re.sub(r"\s", "", display) != re.sub(r"\s", "", n.text)
            or sum(c.isspace() for c in display) >= sum(c.isspace() for c in n.text)
            and not re.search(r"[A-Za-z]", n.text)
        ):
            display = n.text
        result.append(SourceNode(n.index, n.bbox, display, n.scope))
    return tuple(result)


def _clone(cell):
    return cell.clone()


def _text(nodes):
    return " ".join(n.text.strip() for n in sorted(nodes, key=lambda n: (round(_cy(n.bbox) / 2), n.bbox[0])))


def _cell_nodes(nodes, box, tolerance=0.0):
    return [
        n
        for n in nodes
        if box[0] - tolerance <= _cx(n.bbox) < box[2] + tolerance
        and box[1] - tolerance <= _cy(n.bbox) < box[3] + tolerance
    ]


def _replace(tab, grid, operation, depth):
    child = copy(tab)
    child.placements = grid
    child.cells = [tuple(c.bbox) for row in grid for c in row if c.bbox is not None]
    child._bbox = tuple(_union_box(child.cells))
    child.header_rows = depth
    child.section_rows = ()
    child.bbox_provenance = dict(
        tab.bbox_provenance,
        bbox_source="union_recovery",
        grid_source="mixed",
        bbox_operation=operation,
        recovery_revision="content-ownership/r2",
        grid_sources=sorted(
            set(tab.bbox_provenance.get("grid_sources", [tab.bbox_provenance.get("grid_source", "unknown")]))
            | {"retained_node_geometry"}
        ),
        recovery_steps=list(tab.bbox_provenance.get("recovery_steps", ())) + [operation],
        recovery_source_bboxes=[list(tab.bbox)],
    )
    return child


def _header(nodes, columns, bottom):
    """Infer a leaf header and optional centered group labels above it.

    Multiple same-height group labels must each span at least two leaf columns.
    An isolated line above those labels is a caption, never a forced cell.
    """
    if not nodes:
        return None
    lines = _bands([(n.bbox[1], n.bbox[3]) for n in nodes], 1.0)
    width = len(columns)
    for lo, hi in lines:
        seeds = [n for n in nodes if lo <= _cy(n.bbox) <= hi]
        if len(seeds) < 2 or len(seeds) >= width:
            continue
        leaves = [n for n in nodes if n.bbox[1] > hi]
        groups = [[] for _ in columns]
        for n in leaves:
            owners = [j for j, (a, b) in enumerate(columns) if a <= _cx(n.bbox) < b]
            if len(owners) != 1:
                # A narrow stitched stub can be narrower than its header.
                j = min(range(width), key=lambda j: abs(_cx(n.bbox) - sum(columns[j]) / 2))
                if abs(_cx(n.bbox) - sum(columns[j]) / 2) > (columns[j][1] - columns[j][0]) / 2 + 3:
                    return None
                owners = [j]
            groups[owners[0]].append(n)
        if not all(groups):
            continue
        centers = [_cx(_union_box([n.bbox for n in g])) for g in groups]
        if any(a >= b for a, b in zip(centers, centers[1:])):
            continue
        pitch = median(b - a for a, b in zip(centers, centers[1:]))
        seeds.sort(key=lambda n: _cx(n.bbox))
        assigned = {}
        for seed in seeds:
            eligible = [j for j, x in enumerate(centers) if min(seeds, key=lambda n: abs(x - _cx(n.bbox))) is seed]
            choices = [
                (a, b)
                for a in eligible
                for b in eligible
                if b > a and abs((centers[a] + centers[b]) / 2 - _cx(seed.bbox)) <= pitch / 4
            ]
            if not choices:
                break
            a, b = max(choices, key=lambda p: p[1] - p[0])
            assigned[a] = (b, seed)
        else:
            row, used, j = [], set(), 0
            while j < width:
                b, seed = assigned.get(j, (j, None))
                row.append(
                    SpanCell((columns[j][0], lo, columns[b][1], hi), seed.text if seed else "", b - j + 1, 1, "th", sources=node_sources([seed] if seed else []))
                )
                if seed:
                    used.add(seed.index)
                j = b + 1
            leaf_top = min(n.bbox[1] for n in leaves)
            leaf_row = [
                SpanCell(
                    (min(a, min(n.bbox[0] for n in ns)), leaf_top, max(b, max(n.bbox[2] for n in ns)), bottom),
                    _text(ns),
                    1,
                    1,
                    "th",
                    sources=node_sources(ns),
                )
                for (a, b), ns in zip(columns, groups)
            ]
            used.update(n.index for n in leaves)
            return [row, leaf_row], used
    return None


def _horizontal_pair(left, right, nodes):
    """Join disjoint numeric bodies only with aligned rows AND shared headers."""
    if left.header_rows or right.header_rows or left.bbox[2] >= right.bbox[0]:
        return None
    ln, lc, lb, _ = _table_grid_matrices(left, retain=True)
    rn, rc, rb, _ = _table_grid_matrices(right, retain=True)
    if min(ln, rn) < 3 or min(lc, rc) < 2 or rn > ln:
        return None
    if any(c.rowspan != 1 or c.colspan != 1 for t in (left, right) for row in t.placements for c in row):
        return None
    if any(
        not re.search(r"\d", c.text or "")
        for t in (left, right)
        for row in t.placements
        for c in row
        if (c.text or "").strip()
    ):
        return None
    columns = column_intervals(lb) + column_intervals(rb)
    if any(c is None for c in columns):
        return None
    pitch = median(b - a for a, b in columns)
    if right.bbox[0] - left.bbox[2] > pitch:
        return None
    bands = _grid_rows_y(lb)
    row_map = {}
    for r, band in enumerate(_grid_rows_y(rb)):
        owners = [j for j, b in enumerate(bands) if b and b[0] <= sum(band) / 2 < b[1]]
        if len(owners) != 1 or owners[0] in row_map:
            return None
        row_map[owners[0]] = r
    if list(row_map) != list(range(min(row_map), ln)):
        return None
    top = min(left.bbox[1], right.bbox[1])
    prefix = [
        n
        for n in nodes
        if n.bbox[3] <= top
        and top - n.bbox[1] <= 2 * pitch
        and left.bbox[0] - pitch / 2 <= _cx(n.bbox) <= right.bbox[2] + 3
    ]
    header = _header(prefix, columns, top)
    if header is None:
        return None
    headers, used = header
    # A real hierarchy must cover both bodies; unrelated independent tables
    # merely aligned in y must not qualify.
    # One shared, ungrouped leading key is evidence for a common record axis.
    # Two independent numeric tables with their own centered titles and no
    # shared stub must not join just because their rows happen to align.
    if headers[0][0].text or headers[0][0].colspan != 1 or any(not c.text or c.colspan < 2 for c in headers[0][1:]):
        return None
    keys = [row[0].text for row in left.placements]
    if len(set(keys)) != len(keys) or any(not key.strip() for key in keys):
        return None
    rows = []
    for li, row in enumerate(left.placements):
        extra = (
            [_clone(c) for c in right.placements[row_map[li]]]
            if li in row_map
            else [SpanCell((a, bands[li][0], b, bands[li][1]), "", 1, 1, "td") for a, b in columns[lc:]]
        )
        rows.append([_clone(c) for c in row] + extra)
    child = _replace(left, headers + rows, "content_horizontal_join", len(headers))
    child.bbox_provenance["recovery_source_bboxes"] = [list(left.bbox), list(right.bbox)]
    child.bbox_provenance["grid_sources"] = sorted(
        set(child.bbox_provenance["grid_sources"])
        | set(right.bbox_provenance.get("grid_sources", [right.bbox_provenance.get("grid_source", "unknown")]))
    )
    return child, used


def _stub_rows(tab, nodes, neighbors=()):
    """Use repeated external row labels to recover a clipped small table.

    Requires one adjacent label column and a value at every proposed row.
    Existing numeric material is reassigned by its retained source position,
    allowing an earlier cell that merged two physical rows to be repaired.
    """
    nr, nc, cells, _ = _table_grid_matrices(tab, retain=True)
    if nr < 2 or nc < 2:
        return None
    cols = column_intervals(cells)
    if any(c is None for c in cols):
        return None
    bands = _grid_rows_y(cells)
    pitch = median(b - a for a, b in bands if b)
    missing = [
        n
        for n in nodes
        if tab.bbox[0] - median(b - a for a, b in cols) <= _cx(n.bbox) < tab.bbox[0]
        and tab.bbox[1] <= _cy(n.bbox) <= tab.bbox[3] + 1.5 * pitch
    ]
    # A row label already inside another output table is not missing material.
    # Do this before rebuilding, not by discarding duplicated text afterwards.
    missing = [
        n
        for n in missing
        if not any(
            other.bbox[0] - 1 <= _cx(n.bbox) <= other.bbox[2] + 1
            and other.bbox[1] - 1 <= _cy(n.bbox) <= other.bbox[3] + 1
            for other in neighbors
        )
    ]
    # A footer with no value aligned in the existing columns is not a row label.
    missing = [
        n
        for n in missing
        if any(tab.bbox[0] <= _cx(v.bbox) < tab.bbox[2] and abs(_cy(v.bbox) - _cy(n.bbox)) <= pitch / 3 for v in nodes)
    ]
    if len(missing) < 3:
        return None
    # Labels must form a single left-aligned column, not a neighboring table.
    if max(n.bbox[0] for n in missing) - min(n.bbox[0] for n in missing) > 3:
        return None
    missing.sort(key=lambda n: _cy(n.bbox))
    if any(_cy(b.bbox) - _cy(a.bbox) < 3 for a, b in zip(missing, missing[1:])):
        return None
    ys = [_cy(n.bbox) for n in missing]
    bounds = [tab.bbox[1]] + [(a + b) / 2 for a, b in zip(ys, ys[1:])] + [max(n.bbox[3] for n in missing) + 1]
    rows, used = [], set()
    for i, label in enumerate(missing):
        selected = [
            n for n in nodes if tab.bbox[0] <= _cx(n.bbox) < tab.bbox[2] and bounds[i] <= _cy(n.bbox) < bounds[i + 1]
        ]
        if not selected:
            return None
        row = [
            SpanCell(
                (min(n.bbox[0] for n in missing), bounds[i], tab.bbox[0], bounds[i + 1]),
                label.text,
                1,
                1,
                "th" if i == 0 else "td",
                sources=node_sources([label]),
            )
        ]
        used.add(label.index)
        for a, b in cols:
            ns = [n for n in selected if a <= _cx(n.bbox) < b]
            row.append(SpanCell((a, bounds[i], b, bounds[i + 1]), _text(ns), 1, 1, "th" if i == 0 else "td", sources=node_sources(ns)))
            used.update(n.index for n in ns)
        rows.append(row)
    original = Counter(token for row in tab.placements for c in row for token in _tokens(c.text))
    rebuilt = Counter(token for row in rows for c in row for token in _tokens(c.text))
    if original - rebuilt:
        # Partial adjacent labels cannot replace a longer existing table. Every
        # existing value must survive, even when its old cell had merged rows.
        return None
    return _replace(tab, rows, "content_stub_rows", 1), used


def cell_ownership(tables, nodes):
    """Require geometry and an unused source character sequence in final cells.

    This confirms text acceptance only, not correctness of logical cell roles.
    GNN nodes may split a word at a font boundary or omit spaces. Whitespace is
    ignored for word matching; original separators remain numeric boundaries.
    Repeated text consumes separate occurrences; bbox inclusion is insufficient.
    Multi-cell matches preserve each consumed cell fragment and its offset.
    """
    cells = [
        (ti, ri, ci, c)
        for ti, t in enumerate(tables)
        for ri, row in enumerate(t.placements)
        for ci, c in enumerate(row)
        if c.bbox is not None
    ]

    def characters(text):
        original = unicodedata.normalize("NFKC", text or "").casefold()
        offsets = [i for i, char in enumerate(original) if not char.isspace()]
        return original, offsets, [original[i] for i in offsets]

    def positions(hay, original, offsets, needle, numeric):
        # Shared by single-cell and multi-cell acceptance. None marks a
        # previously consumed character; it must never be removed or matched.
        for j in range(len(hay) - len(needle) + 1):
            if hay[j : j + len(needle)] != needle:
                continue
            if numeric and (
                (offsets[j] and original[offsets[j] - 1] in "0123456789.,")
                or (
                    offsets[j + len(needle) - 1] + 1 < len(original)
                    and original[offsets[j + len(needle) - 1] + 1] in "0123456789.,"
                )
            ):
                continue
            yield j

    originals = {id(c): characters(c.text) for _, _, _, c in cells}
    available = {key: list(value[2]) for key, value in originals.items()}
    accepted = {}
    for node in nodes:
        _, _, needle = characters(node.text)
        if not needle:
            continue
        numeric = any(char.isdigit() for char in needle) and bool(re.fullmatch(r"[+\-\d.,%()]+", "".join(needle)))
        candidates = [
            (ti, ri, ci, c)
            for ti, ri, ci, c in cells
            if c.bbox[0] - 1 <= _cx(node.bbox) <= c.bbox[2] + 1 and c.bbox[1] - 1 <= _cy(node.bbox) <= c.bbox[3] + 1
        ]
        hits = []
        for ti, ri, ci, c in candidates:
            hay = available[id(c)]
            original, offsets, _ = originals[id(c)]
            pos = next(positions(hay, original, offsets, needle, numeric), None)
            if pos is not None:
                hits.append((ti, ri, ci, c, pos))
        # Prefer a unique actual cell interior over the existing 1-point
        # tolerance. Adjacent equal-valued rows must not become ambiguous just
        # because the neighbor's expanded bbox also includes this node.
        strict = [hit for hit in hits if _cell_nodes((node,), hit[3].bbox)] if numeric else []
        if strict:
            hits = strict
        if numeric and len(hits) > 1:
            # A broad aggregate cell can overlap a specific leaf cell. Prefer
            # the unique complete-value cell only when every other match
            # geometrically contains it. Equal/adjacent cells stay ambiguous.
            exact = [hit for hit in hits if originals[id(hit[3])][2] == needle]
            if len(exact) == 1:
                box = exact[0][3].bbox
                if all(
                    h[3].bbox[0] <= box[0] and h[3].bbox[1] <= box[1]
                    and h[3].bbox[2] >= box[2] and h[3].bbox[3] >= box[3]
                    for h in hits
                ):
                    hits = exact
        if len(hits) != 1:
            continue
        ti, ri, ci, c, pos = hits[0]
        available[id(c)][pos : pos + len(needle)] = [None] * len(needle)
        accepted[node.index] = dict(
            table=ti, row=ri, cell=ci, disposition="cell_text",
            fragments=[dict(row=ri, cell=ci, start=pos, end=pos + len(needle))],
        )

    # Keep all established single-cell assignments before matching unresolved
    # source nodes across cells. A wide node must not steal their characters.
    rows = {}
    for ti, ri, ci, cell in cells:
        rows.setdefault((ti, ri), []).append((ci, cell))
    for node in nodes:
        if node.index in accepted:
            continue
        _, _, needle = characters(node.text)
        if not needle:
            continue
        numeric = any(char.isdigit() for char in needle) and bool(re.fullmatch(r"[+\-\d.,%()]+", "".join(needle)))
        plans = []
        for (ti, ri), row in rows.items():
            selected = [
                (ci, cell) for ci, cell in row
                if cell.bbox[1] - 1 <= _cy(node.bbox) <= cell.bbox[3] + 1
                and min(cell.bbox[2], node.bbox[2]) > max(cell.bbox[0], node.bbox[0])
            ]
            if len(selected) < 2 or any(
                a.bbox[2] > b.bbox[0] + 1 for (_, a), (_, b) in zip(selected, selected[1:])
            ):
                # Do not concatenate overlapping cells or unrelated tables.
                continue
            raw, offsets, hay, refs, base = [], [], [], [], 0
            for ci, cell in selected:
                original, local_offsets, chars = originals[id(cell)]
                raw.append(original)
                offsets.extend(base + offset for offset in local_offsets)
                hay.extend(available[id(cell)])
                refs.extend((ci, cell, pos) for pos in range(len(chars)))
                base += len(original) + 1  # The inter-cell separator is real for numeric boundaries.
            original = " ".join(raw)
            for pos in positions(hay, original, offsets, needle, numeric):
                fragment_refs = refs[pos : pos + len(needle)]
                if fragment_refs[0][0] == fragment_refs[-1][0]:
                    continue
                plans.append((ti, ri, fragment_refs))
                if len(plans) > 1:
                    break
            if len(plans) > 1:
                break
        if len(plans) != 1:
            continue
        ti, ri, refs = plans[0]
        fragments = []
        for ci, cell, pos in refs:
            available[id(cell)][pos] = None
            if fragments and fragments[-1]["cell"] == ci:
                fragments[-1]["end"] = pos + 1
            else:
                fragments.append(dict(row=ri, cell=ci, start=pos, end=pos + 1))
        accepted[node.index] = dict(
            table=ti, row=ri, cell=None, disposition="cell_text", fragments=fragments
        )

    # A number can be split across source nodes even though its complete value
    # is already in one cell. Keep the individual numeric-boundary guard above;
    # only admit a complete, adjacent source group into still-available ranges.
    targets = {}
    for node in nodes:
        if node.index in accepted:
            continue
        _, _, needle = characters(node.text)
        if not any(char.isdigit() for char in needle) or not re.fullmatch(r"[+\-\d.,%()]+", "".join(needle)):
            continue
        for ti, ri, ci, cell in cells:
            if not _cell_nodes((node,), cell.bbox):
                continue
            value = "".join(originals[id(cell)][2])
            if re.fullmatch(r"[$€£]?[+\-\d.,%()]+", value):
                targets[id(cell)] = (ti, ri, ci, cell)
    for ti, ri, ci, cell in targets.values():
        members = sorted(
            (n for n in _cell_nodes(nodes, cell.bbox) if n.text.strip()),
            key=lambda n: (n.bbox[0], n.index),
        )
        if len(members) < 2:
            continue
        pieces = [characters(n.text)[2] for n in members]
        if [char for piece in pieces for char in piece] != originals[id(cell)][2]:
            continue
        if min(n.bbox[3] for n in members) <= max(n.bbox[1] for n in members):
            continue
        if any(
            not -1 <= right.bbox[0] - left.bbox[2] <= 1
            # An already-owned currency sign may be separated by accounting
            # whitespace. Other fragments must be adjacent in PDF points.
            and not (left.index in accepted and "".join(pieces[i]) in ("$", "€", "£"))
            for i, (left, right) in enumerate(zip(members, members[1:]))
        ):
            continue
        if any(
            sum(bool(_cell_nodes((node,), other.bbox)) for _, _, _, other in cells) != 1
            for node in members
        ):
            continue
        plan, offset = [], 0
        for node, piece in zip(members, pieces):
            end = offset + len(piece)
            owner = dict(table=ti, row=ri, cell=ci, disposition="cell_text",
                         fragments=[dict(row=ri, cell=ci, start=offset, end=end)])
            if node.index in accepted:
                if accepted[node.index] != owner:
                    break
            elif available[id(cell)][offset:end] != piece:
                # Includes characters consumed by an owner outside this group.
                break
            else:
                plan.append((node.index, owner, offset, end))
            offset = end
        else:
            for index, owner, start, end in plan:
                available[id(cell)][start:end] = [None] * (end - start)
                accepted[index] = owner
    return accepted


def restore_tables(tables, nodes, *, obstacles=(), words=None, edges=(), failures=None):
    """Return new table objects, complete ownership, and structural decisions."""
    output = list(tables)
    decisions = []
    # Decide on originals; each fragment participates in at most one join.
    removed, replacements, used = set(), {}, set()
    for i, left in enumerate(output):
        if i in used:
            continue
        options = [
            (j, _horizontal_pair(left, right, nodes))
            for j, right in enumerate(output)
            if j != i and j not in used and right.bbox[0] > left.bbox[2]
        ]
        options = [(j, p) for j, p in options if p is not None]
        if len(options) == 1:
            j, (child, _) = options[0]
            replacements[i] = child
            removed.add(j)
            used.update((i, j))
            decisions.append(dict(operation="horizontal_join", inputs=[i, j]))
    output = [replacements.get(i, t) for i, t in enumerate(output) if i not in removed]
    for i, tab in enumerate(output):
        proposal = _stub_rows(tab, nodes, [other for j, other in enumerate(output) if i != j])
        # An isolated line above leaf labels can be either a group header or
        # a title. Source-node spacing alone cannot distinguish them. Preserve
        # existing header text and column assignments until roles are proven.
        if proposal is not None:
            output[i], _ = proposal
            decisions.append(dict(operation=output[i].bbox_provenance["bbox_operation"], table=i))
    from pymupdf4llm._table_pipeline.ruled_leading_row import recover
    for i, tab in enumerate(output):
        proposal = recover(tab, nodes, words, edges,
                           list(obstacles)+[t for j,t in enumerate(output) if i != j])
        if proposal is not None:
            output[i] = proposal
            decisions.append(dict(operation="ruled_leading_row", table=i))
    from pymupdf4llm._table_pipeline.grid_ownership import absorb_grid_nodes
    accepted = cell_ownership(output, nodes)
    output, grid_decisions = absorb_grid_nodes(output, nodes, accepted, obstacles=obstacles, failures=failures)
    decisions.extend(grid_decisions)
    if grid_decisions:
        accepted = cell_ownership(output, nodes)
    return output, accepted, decisions


def retain_unassigned(tables, nodes, accepted, *, source_gnn_indices, original_nodes=None):
    """Carry unresolved parent content without assigning a cell or layout role.

    One surviving table transports the parent's residuals to TablePayload. It
    is a carrier, not a semantic owner; the source parent/node IDs remain the
    identity. Neither table HTML nor geometric/role metadata is changed.
    """
    nodes = tuple(nodes)
    expected = {n.index for n in nodes if n.text.strip()}
    if not set(accepted) <= expected:
        raise ValueError("Cell ownership references unknown source nodes")
    originals = {n.index: n.text for n in (original_nodes if original_nodes is not None else nodes)}
    residuals = tuple(
        dict(node_index=n.index, source_gnn_indices=list(source_gnn_indices),
             bbox=list(n.bbox), text=n.text, original_text=originals[n.index],
             cell_accepted=False, semantic_role=None, emission="pending")
        for n in nodes if n.index not in accepted and n.text.strip()
    )
    if residuals and not tables:
        raise ValueError("Unresolved GNN content has no surviving output carrier")
    output = list(tables)
    for i, tab in enumerate(tables):
        records = residuals if i == 0 else ()
        if getattr(tab, "unresolved_content", ()) == records:
            continue
        child = copy(tab)
        if records:
            child.unresolved_content = records
        elif hasattr(child, "unresolved_content"):
            del child.unresolved_content
        output[i] = child
    return output, residuals
