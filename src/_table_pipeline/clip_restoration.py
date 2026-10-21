"""Restore clip-backed cells on final placements, before HTML serialization.

The final topology is required: union and region splitting can replace earlier
grids. Original producer references survive merges; split/new cells carry the
selected live word/glyph references. Changed grids get one THF1 reclassification.
No benchmark artifacts, HTML rewriting, PDF reopening or grid inference.
"""

from collections import Counter, defaultdict
from copy import copy
from statistics import median
import unicodedata

from pymupdf import table
from pymupdf._table_clip import collect, area, intersect
from pymupdf._table_spans import SpanCell, CellSource
from pymupdf._table_headers import HeaderRegion

from .clip_evidence import analyze
from .clip_geometry import compact, key, lines_from_runs, inside, background
from .header_leaf_completion import occupancy


def records(grid):
    cells = [c for row in grid for c in row]
    slots, width = occupancy([[(c.text, c.colspan, c.rowspan) for c in row] for row in grid])
    return [
        dict(row=r, col=c, rowspan=rr - r, colspan=cc - c, text=x.text, tag=x.tag, cell=x, index=i)
        for i, ((r, rr, c, cc, _), x) in enumerate(zip(slots, cells))
    ], width


def clip_rows(clips):
    unique = {}
    for c in clips:
        if (
            c["scope"] != "supported"
            or c["pagewide"]
            or not c["glyph_ids"]
            or "scoped_text_crosses_native_faces" in c["reasons"]
        ):
            continue
        unique.setdefault(tuple(c["glyph_ids"]), c)
    rows = []
    for c in sorted(unique.values(), key=lambda c: (c["bbox"][1], c["bbox"][0])):
        choices = [r for r in rows if max(abs(c["bbox"][k] - r[0]["bbox"][k]) for k in (1, 3)) <= 1]
        if len(choices) == 1:
            choices[0].append(c)
        elif not choices:
            rows.append([c])
    for row in rows:
        row.sort(key=lambda c: c["bbox"][0])
    return rows


def contiguous(cells, target):
    found = {}
    for axis in ("row", "col"):
        other = "col" if axis == "row" else "row"
        span, os = axis + "span", other + "span"
        lookup = defaultdict(list)
        for i, c in enumerate(cells):
            lookup[c[axis], c[other], c[os]].append(i)
        for i, c in enumerate(cells):
            token = compact(c["text"])
            if not token or not target.startswith(token):
                continue
            ids = [i]
            while len(token) < len(target):
                nxt = lookup.get((c[axis] + c[span], c[other], c[os]), [])
                if len(nxt) != 1:
                    break
                (j,) = nxt
                c = cells[j]
                ids.append(j)
                token += compact(c["text"])
                if not target.startswith(token):
                    break
            if token == target and len(ids) > 1 and sum(bool(compact(cells[j]["text"])) for j in ids) > 1:
                found[tuple(ids)] = axis
    return list(found.items())


def union_box(boxes):
    return tuple(min(b[k] for b in boxes) if k < 2 else max(b[k] for b in boxes) for k in range(4))


def source_cell(clip, glyphs, words, tag="td"):
    ids = clip["glyph_ids"]
    gs = [glyphs[i] for i in ids]
    text = "\n".join(line["text"] for line in lines_from_runs(gs))
    refs = []
    for i in ids:
        g = glyphs[i]
        if not g["text"].strip():
            continue
        value = "•" if g["text"] == "\uf0b7" and g["font"].split("+")[-1] == "SymbolMT" else g["text"]
        b = (g["x0"], g["y"] - g["size"], g["x1"], g["y"])
        refs.append(CellSource("glyph", i, b, value, glyphs))
    # Exact existing word identity is delivered to the renderer as well. A
    # partly owned word is not claimed wholesale by the new cell.
    own = set(ids)
    for i, w in enumerate(words):
        contained = {j for j, g in enumerate(glyphs) if key(g["text"]) and inside(g, w[:4], 0.1)}
        if contained and contained <= own:
            refs.append(CellSource("word", i, tuple(w[:4]), str(w[4]), words))
    if "\uf0b7" in text and all(g["text"] != "\uf0b7" or g["font"].split("+")[-1] == "SymbolMT" for g in gs):
        text = text.replace("\uf0b7", "•")
    return SpanCell(tuple(clip["bbox"]), text, 1, 1, tag, sources=refs)


def restore_grid(tab, units, rows, glyphs, words):
    cells, width = records(tab.placements)
    plans = []
    for unit in units:
        target = compact(unit["text"])
        if any(compact(c["text"]) == target for c in cells):
            continue
        found = contiguous(cells, target)
        if len(found) != 1:
            continue
        ids, axis = found[0]
        if len({cells[i]["tag"] for i in ids}) != 1:
            continue
        # Text equality is not ownership: require the scoped glyphs to lie in
        # these cells, not a repeated phrase elsewhere in the same table.
        boxes = [cells[i]["cell"].bbox for i in ids]
        if any(b is None for b in boxes) or not all(
            any(inside(glyphs[j], b, 1.5) for b in boxes) for j in unit["glyph_ids"]
        ):
            continue
        original = [cells[i]["cell"] for i in ids]
        if any(c.source_content is None for c in original):
            continue
        merged = SpanCell(
            union_box(boxes),
            "\n".join(c.text for c in original),
            sum(c.colspan for c in original) if axis == "col" else original[0].colspan,
            sum(c.rowspan for c in original) if axis == "row" else original[0].rowspan,
            original[0].tag,
            sources=[s for c in original for s in c.source_content.sources],
        )
        plans.append((ids, [merged], "clip_merge"))
    for i, cell in enumerate(cells):
        if cell["rowspan"] != 1 or cell["colspan"] < 2:
            continue
        options = []
        for ri, row in enumerate(rows):
            if len(row) != cell["colspan"] or compact("".join(c["text"] for c in row)) != compact(cell["text"]):
                continue
            if any(set(a["glyph_ids"]) & set(b["glyph_ids"]) for j, a in enumerate(row) for b in row[j + 1 :]):
                continue
            if any(abs(a["bbox"][2] - b["bbox"][0]) > 2 for a, b in zip(row, row[1:])):
                continue
            supported = 0
            for offset in (1, 2):
                if ri + offset >= len(rows):
                    break
                nxt = rows[ri + offset]
                peers = sorted(
                    [
                        c
                        for c in cells
                        if c["row"] == cell["row"] + offset and cell["col"] <= c["col"] < cell["col"] + cell["colspan"]
                    ],
                    key=lambda c: c["col"],
                )
                if len(nxt) != len(row) or len(peers) != len(row):
                    break
                if any(
                    c["colspan"] != 1 or c["rowspan"] != 1 or compact(c["text"]) != compact(d["text"])
                    for c, d in zip(peers, nxt)
                ):
                    break
                if any(max(abs(a["bbox"][k] - b["bbox"][k]) for k in (0, 2)) > 2 for a, b in zip(row, nxt)):
                    break
                supported += 1
            if supported == 2:
                options.append(row)
        if len(options) == 1:
            plans.append(((i,), [source_cell(c, glyphs, words, cell["tag"]) for c in options[0]], "clip_partition"))
    usage = Counter(i for ids, _, _ in plans for i in ids)
    plans = [p for p in plans if all(usage[i] == 1 for i in p[0])]
    if not plans:
        return tab.placements, []
    replacements = {ids[0]: cs for ids, cs, _ in plans}
    removed = {i for ids, _, _ in plans for i in ids[1:]}
    grid = [[] for _ in tab.placements]
    for i, c in enumerate(cells):
        if i not in removed:
            grid[c["row"]].extend(replacements.get(i, [c["cell"].clone()]))
    after, after_width = records(grid)
    if width != after_width or Counter(compact("".join(c["text"] for c in after))) != Counter(
        compact("".join(c["text"] for c in cells))
    ):
        raise ValueError("Clip restoration changed grid dimensions or source content")
    return grid, [kind for _, _, kind in plans]


def prepare(page, finder):
    raw = collect(page)
    if not raw["clips"]:
        return raw, None
    # Reuse converted real evidence. Never reconstruct lines from PDF paths.
    edges = [e for e in finder.ruling_evidence if e.get("ruling_origin") == "vector"]
    merged = table.merge_edges(edges, 1, 1, 1, 1)
    faces = table.intersections_to_cells(table.edges_to_intersections(merged, 1, 1))
    line_height = median(g["size"] for g in raw["glyphs"]) if raw["glyphs"] else 10.0
    evidence = analyze(
        raw["glyphs"], raw["clips"], tuple(page.rect), dict(faces=faces, events=raw["events"], images=[]), line_height
    )
    return raw, evidence


def source_group(page, ids, glyphs, consumed=()):
    """Unique live layout source, before markdown exists. No string search."""
    matches = []
    own = {i for i in ids if key(glyphs[i]["text"])}
    for i, group in enumerate(page.layout_information or ()):
        if group.get("class_name") == "table" or not group.get("group_bbox"):
            continue
        b = group["group_bbox"][:4]
        contained = {j for j, g in enumerate(glyphs) if key(g["text"]) and inside(g, b, 1.5)}
        if contained - set(consumed) == own:
            matches.append(i)
    return matches[0] if len(matches) == 1 else None


def region_plans(page, tables, evidence, raw, owners):
    """Extent and new-region decisions share the same final ownership context."""
    gs = raw["glyphs"]
    rows = clip_rows(evidence["clips"])
    plans = []
    refs = [
        s
        for t in tables
        for row in t.placements
        for c in row
        if c.source_content is not None
        for s in c.source_content.sources
    ]
    consumed = {j for j, g in enumerate(gs) if key(g["text"]) and any(inside(g, s.bbox, 1.5) for s in refs)}
    for ti, tab in enumerate(tables):
        cells, width = records(tab.placements)
        if width < 2:
            continue
        for side, ri in [("before", 0), ("after", len(tab.placements) - 1)]:
            edge = sorted([c for c in cells if c["row"] == ri], key=lambda c: c["col"])
            if len(edge) != width or any(c["rowspan"] != 1 or c["colspan"] != 1 for c in edge):
                continue
            anchors = [
                row
                for row in rows
                if len(row) == width
                and all(
                    owners(c["glyph_ids"]) == [ti] and compact(c["text"]) == compact(e["text"])
                    for c, e in zip(row, edge)
                )
            ]
            if len(anchors) != 1:
                continue
            anchor = anchors[0]
            for row in rows:
                if len(row) != width or any(owners(c["glyph_ids"]) for c in row):
                    continue
                if any(max(abs(a["bbox"][k] - b["bbox"][k]) for k in (0, 2)) > 2 for a, b in zip(row, anchor)):
                    continue
                gap = (
                    anchor[0]["bbox"][1] - row[0]["bbox"][3]
                    if side == "before"
                    else row[0]["bbox"][1] - anchor[0]["bbox"][3]
                )
                if not 0 <= gap <= 2 or any(abs(a["bbox"][2] - b["bbox"][0]) > 2 for a, b in zip(row, row[1:])):
                    continue
                ids = [j for c in row for j in c["glyph_ids"]]
                if len(ids) != len(set(ids)) or source_group(page, ids, gs, consumed) is None:
                    continue
                plans.append(dict(table=ti, row=row, side=side, ids=ids, kind="clip_extend_row"))
    # A new region needs two independently painted, adjacent cells, complete
    # live source ownership and known equal shading. Clip existence is not a
    # table classifier. Unknown glyph encodings are never guessed.
    eligible = []
    for c in evidence["clips"]:
        if owners(c["glyph_ids"]):
            continue
        if c["scope"] == "supported":
            eligible.append(c)
        elif set(c["reasons"]) == {"encoding_unresolved"} and all(
            not (g["text"] == "\ufffd" or any(unicodedata.category(ch) == "Co" for ch in g["text"]))
            or (g["text"] == "\uf0b7" and g["font"].split("+")[-1] == "SymbolMT")
            for g in (gs[j] for j in c["glyph_ids"])
        ):
            eligible.append(dict(c, scope="supported"))
    for row in clip_rows(eligible):
        chunks = []
        for c in row:
            if not chunks or abs(chunks[-1][-1]["bbox"][2] - c["bbox"][0]) > 2:
                chunks.append([])
            chunks[-1].append(c)
        for group in chunks:
            if len(group) < 2:
                continue
            b = union_box([c["bbox"] for c in group])
            if any(area(intersect(b, t.bbox)) > 0 for t in tables):
                continue
            ids = [j for c in group for j in c["glyph_ids"]]
            if len(ids) != len(set(ids)) or source_group(page, ids, gs) is None:
                continue
            colors = [background(c["bbox"], raw["backgrounds"]) for c in group]
            if any(c is None for c in colors) or min(colors[0]) >= 0.95:
                continue
            if any(max(abs(x - y) for x, y in zip(c, colors[0])) > 0.02 for c in colors):
                continue
            plans.append(dict(table=None, row=group, ids=ids, kind="clip_create_table"))
    counts = Counter(i for p in plans for i in p["ids"])
    return [p for p in plans if all(counts[i] == 1 for i in p["ids"])]


def restore(page, tables, raw, evidence, header):
    if evidence is None:
        return tables
    glyphs = raw["glyphs"]
    words = getattr(page, "_refine_words_cache", ())
    boxes = [t.bbox for t in tables]

    def owners(ids):
        return (
            [i for i, b in enumerate(boxes) if sum(inside(glyphs[j], b, 1.5) for j in ids) / len(ids) >= 0.95]
            if ids
            else []
        )

    units = defaultdict(list)
    clips = defaultdict(list)
    for unit in evidence["cell_units"]:
        own = owners(unit["glyph_ids"])
        if unit["state"] == "corroborated" and len(own) == 1:
            units[own[0]].append(unit)
    for c in evidence["clips"]:
        own = owners(c["glyph_ids"])
        if len(own) == 1:
            clips[own[0]].append(c)
    regions = region_plans(page, tables, evidence, raw, owners)
    result = []
    for i, tab in enumerate(tables):
        grid, actions = restore_grid(tab, units[i], clip_rows(clips[i]), glyphs, words)
        extensions = [p for p in regions if p["table"] == i]
        if extensions:
            grid = [[c.clone() for c in row] for row in grid]
            for p in extensions:
                row = [source_cell(c, glyphs, words) for c in p["row"]]
                grid.insert(0 if p["side"] == "before" else len(grid), row)
                actions.append(p["kind"])
        if not actions:
            result.append(tab)
            continue
        child = copy(tab)
        child.placements, region = header.apply_roles(
            page, grid, HeaderRegion(top_header_rows=tab.header_rows, section_header_rows=tab.section_rows)
        )
        child.header_rows, child.section_rows = region.top_header_rows, region.section_header_rows
        child.cells = [c.bbox for row in grid for c in row if c.bbox is not None]
        if extensions:
            child._bbox = union_box([tab.bbox] + [c["bbox"] for p in extensions for c in p["row"]])
        child.bbox_provenance = dict(
            tab.bbox_provenance,
            grid_source="mixed",
            clip_restoration=actions,
            grid_sources=sorted(
                set(tab.bbox_provenance.get("grid_sources", [tab.bbox_provenance.get("grid_source", "unknown")]))
                | {"pdf_clip"}
            ),
        )
        result.append(child)
    for p in regions:
        if p["table"] is not None:
            continue
        grid = [[source_cell(c, glyphs, words) for c in p["row"]]]
        child = table.Table(page, [c.bbox for c in grid[0]])
        child.placements, region = header.apply_roles(
            page, grid, HeaderRegion(top_header_rows=0, section_header_rows=())
        )
        child.header_rows, child.section_rows = region.top_header_rows, region.section_header_rows
        child.bbox_provenance = dict(
            bbox_source="pdf_clip",
            grid_source="pdf_clip",
            bbox_operation="clip_create_table",
            source_gnn_indices=[],
            clip_restoration=[p["kind"]],
        )
        result.append(child)
    return result
