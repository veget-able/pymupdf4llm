"""Clip evidence from live paint ownership and the existing ruling converter.

Purpose-specific cell evidence, never an unconditional table/rowspan decision.
"""

from collections import defaultdict
import statistics
import unicodedata
from .clip_geometry import area, intersect, key, lines_from_runs, inside, prepare, text_columns, PageText


def invalid_text(text):
    return any(c == "\ufffd" or unicodedata.category(c) == "Co" for c in text)


def neighbor(a, b, axis, tol=1.0):
    other = 1 - axis
    return (
        min(abs(a[axis + 2] - b[axis]), abs(b[axis + 2] - a[axis])) <= tol
        and min(a[other + 2], b[other + 2]) - max(a[other], b[other]) > tol
    )


def wrapping(gs, box):
    """Positive word-wrap evidence, not 'multiple baselines imply one cell'.

    Each next line's first word must not fit in the preceding line's remaining
    width. Left-aligned starts and bounded baseline gaps exclude centered or
    right-aligned stacks of short numbers. Intentional short newlines stay
    candidates; failing this check does not prove separate cells.
    """
    gs = [g for g in gs if key(g["text"])]
    ls = lines_from_runs(gs)
    if len(ls) < 2:
        return dict(accept=False, transitions=0, supported=0, reason="not_multiline")
    size = statistics.median(g["size"] for g in gs)
    groups = [[] for _ in ls]
    for g in gs:
        groups[min(range(len(ls)), key=lambda i: abs(ls[i]["y"] - g["y"]))].append(g)
    support = 0
    for prev, nxt, ng in zip(ls, ls[1:], groups[1:]):
        ng = sorted(ng, key=lambda g: g["x0"])
        first = [ng[0]]
        for g in ng[1:]:
            if g["x0"] - first[-1]["x1"] > 0.18 * size:
                break
            first.append(g)
        width = max(g["x1"] for g in first) - first[0]["x0"]
        left = max(abs(prev["x0"] - box[0]), abs(nxt["x0"] - box[0])) <= size
        vertical = 0 < nxt["y"] - prev["y"] <= 1.8 * size
        overflow = prev["x1"] + 0.25 * size + width > box[2] - 0.1 * size
        support += bool(left and vertical and overflow)
    return dict(accept=support == len(ls) - 1, transitions=len(ls) - 1, supported=support, reason="word_wrap_geometry")


def terminal_faces(faces):
    """A enclosing frame is context, not a second cell owning inner glyphs.

    Remove strict containers, not intersecting peer faces. Uncovered text in a
    removed frame stays unresolved; it is not assigned to a child by proximity.
    """
    return [
        a
        for i, a in enumerate(faces)
        if not any(
            i != j
            and area(b) < area(a) - 1
            and all((a[k] <= b[k] + 0.01 if k < 2 else a[k] >= b[k] - 0.01) for k in range(4))
            for j, b in enumerate(faces)
        )
    ]


def analyze(glyphs, clips, rect, native, line_height=10.0):
    """Return payloads (glyph IDs, groups, evidence IDs), not merely log flags."""
    gs = glyphs
    nonblank = {i for i, g in enumerate(gs) if key(g["text"])}
    text_index = PageText(gs)
    content = [c for c in clips if nonblank.intersection(c["scoped_glyph_ids"])]
    geometry = prepare(content, max(0.1, line_height), 3.0)
    faces = terminal_faces(native["faces"])
    events = native.get("events", [])
    face_ids = [{i for i in nonblank if inside(gs[i], b, -0.05)} for b in faces]
    # A glyph on a border is not automatically assigned to both sides.
    memberships = defaultdict(list)
    for fi, ids in enumerate(face_ids):
        for i in ids:
            memberships[i].append(fi)
    rows = []
    face_sources = defaultdict(list)
    for c in clips:
        ids = nonblank.intersection(c["scoped_glyph_ids"])
        b = c["bbox"]
        text = " ".join(l["text"] for l in lines_from_runs([gs[i] for i in sorted(ids)]))
        ei = [
            i
            for i, e in enumerate(events)
            if e["bbox"] is not None and max(abs(x - y) for x, y in zip(b, e["bbox"])) < 0.02
        ]
        unknown = not ei or any(events[i]["unknown_text"] or events[i]["unknown_paint"] for i in ei)
        clean = bool(ids) and not unknown and not invalid_text(text)
        pw = (
            area(intersect(b, rect)) / max(area(rect), 1e-9) >= 0.9
            and (b[2] - b[0]) >= 0.95 * (rect[2] - rect[0])
            and (b[3] - b[1]) >= 0.95 * (rect[3] - rect[1])
        )
        # Pagewide scope still exists; only its semantic grouping is disabled.
        fid = sorted({f for i in ids for f in memberships[i]})
        complete_owner = len(fid) == 1 and ids <= face_ids[fid[0]]
        gi = geometry["by_id"].get(c["index"])
        repeat = geometry["repeat"][gi] if gi is not None else {}
        cols = text_columns([gs[i] for i in sorted(ids)])
        reasons = []
        if unknown:
            reasons.append("incomplete_or_unmatched_paint_scope")
        if invalid_text(text):
            reasons.append("encoding_unresolved")
        if not ids:
            reasons.append("no_nonblank_scoped_text")
        if pw:
            reasons.append("pagewide_context_only")
        role = "candidate" if clean and not pw else "unknown"
        cell = role
        row = role
        if role == "candidate" and len(fid) > 1:
            cell = "conflict"
            reasons.append("scoped_text_crosses_native_faces")
        if clean and not pw and complete_owner:
            face_sources[fid[0]].append(c["index"])
        rows.append(
            dict(
                index=c["index"],
                bbox=b,
                event_ids=ei,
                glyph_ids=sorted(ids),
                text=text,
                scope="supported" if clean else "unknown",
                pagewide=pw,
                lines=len(lines_from_runs([gs[i] for i in sorted(ids)])),
                roles=dict(region=role, row=row, cell=cell),
                reasons=reasons,
                native_faces=fid,
                vertical_repeat=repeat.get("vertical", 0),
                horizontal_repeat=repeat.get("horizontal", 0),
                projected_columns=len(cols),
                semantic_table=False,
                force_structure=False,
            )
        )
    byid = {r["index"]: r for r in rows}
    units = []
    for fi, sources in face_sources.items():
        ids = set().union(*(set(byid[i]["glyph_ids"]) for i in sources))
        complete = (
            ids == face_ids[fi]
            and bool(ids)
            and all(len(memberships[i]) == 1 for i in ids)
            and not text_index.cuts_word(ids)
        )
        unit = dict(
            index=len(units),
            face=fi,
            bbox=faces[fi],
            clip_ids=sources,
            glyph_ids=sorted(ids),
            text=" ".join(l["text"] for l in lines_from_runs([gs[i] for i in sorted(ids)])),
            lines=len(lines_from_runs([gs[i] for i in sorted(ids)])),
            state="candidate",
            reasons=[] if complete else ["frame_text_not_fully_owned"],
            complete=complete,
        )
        unit["evidence"] = "native_face"
        unit["wrapping"] = wrapping([gs[i] for i in sorted(ids)], faces[fi])
        units.append(unit)
    for u in units:
        hs = [v["index"] for v in units if v != u and neighbor(u["bbox"], v["bbox"], 0)]
        vs = [v["index"] for v in units if v != u and neighbor(u["bbox"], v["bbox"], 1)]
        u["horizontal_neighbors"] = hs
        u["vertical_neighbors"] = vs
        # Independent enclosure plus local 2D structure. A lone paragraph box
        # is retained as a candidate, not promoted to a cell.
        cols = text_columns([gs[i] for i in u["glyph_ids"]])
        if u["complete"] and hs and vs and len(cols) == 1 and (u["lines"] == 1 or u["wrapping"]["accept"]):
            u["state"] = "corroborated"
            u["reasons"].append("native_closed_face_and_complete_clip_text_in_2d_layout")
        # Same two/three baselines in every neighbor can be separate logical
        # rows inside a coarse frame. Preserve the ambiguity, not a hard merge.
        ys = [l["y"] for l in lines_from_runs([gs[i] for i in u["glyph_ids"]])]
        peers = [
            v
            for v in units
            if v["index"] in hs and abs(v["bbox"][1] - u["bbox"][1]) <= 1 and abs(v["bbox"][3] - u["bbox"][3]) <= 1
        ]
        patterns = [[l["y"] for l in lines_from_runs([gs[i] for i in v["glyph_ids"]])] for v in peers]
        tol = 0.35 * statistics.median(gs[i]["size"] for i in u["glyph_ids"])
        synchronized = (
            bool(peers)
            and len(ys) > 1
            and all(len(p) == len(ys) and max(abs(a - b) for a, b in zip(ys, p)) <= tol for p in patterns)
        )
        if synchronized:
            u["state"] = "candidate"
            u["reasons"].append("synchronized_lines_logical_rows_unresolved")
        # A coarse native frame is not permission to erase a competing vertical
        # clip partition. Vertical fragments such as Basic / Limits may still
        # be collected; side-by-side independent scopes remain ambiguous.
        sources = [byid[i] for i in u["clip_ids"]]
        sideways = any(
            not (set(a["glyph_ids"]) & set(b["glyph_ids"]))
            and min(a["bbox"][2], b["bbox"][2]) - max(a["bbox"][0], b["bbox"][0]) <= 0
            for i, a in enumerate(sources)
            for b in sources[i + 1 :]
        )
        if sideways:
            u["state"] = "candidate"
            u["reasons"].append("competing_side_by_side_clip_partition")
        for ci in u["clip_ids"]:
            r = byid[ci]
            r["cell_unit"] = u["index"]
            if set(r["glyph_ids"]) == set(u["glyph_ids"]):
                r["roles"]["cell"] = u["state"]
            else:
                r["roles"]["cell"] = "conflict"
                r["reasons"].append("partial_native_face_use_joint_text_unit")
    # Borderless branch: independent text flow complements 2D clip repetition.
    # The grouping uses actual painted glyphs; rectangular inclusion alone is
    # insufficient. Padding stability is intentionally NOT required.
    existing = {tuple(u["glyph_ids"]) for u in units if u["state"] == "corroborated"}
    for r in rows:
        if (
            r["roles"]["cell"] != "candidate"
            or r["projected_columns"] != 1
            or min(r["vertical_repeat"], r["horizontal_repeat"]) < 2
        ):
            continue
        own = set(r["glyph_ids"])
        w = wrapping([gs[i] for i in r["glyph_ids"]], r["bbox"])
        r["wrapping"] = w
        full = {i for i in text_index.query(r["bbox"], 0) if i in nonblank} == own
        if not w["accept"] or not full or text_index.cuts_word(own):
            continue
        # Nested/coincident clip variants must not multiply evidence units.
        if tuple(r["glyph_ids"]) in existing:
            continue
        u = dict(
            index=len(units),
            face=None,
            bbox=r["bbox"],
            clip_ids=[r["index"]],
            glyph_ids=r["glyph_ids"],
            text=r["text"],
            lines=r["lines"],
            state="corroborated",
            complete=True,
            evidence="clip_grid_and_word_wrap",
            wrapping=w,
            reasons=["actual_scope_complete_2d_repetition_word_wrap"],
            horizontal_neighbors=[],
            vertical_neighbors=[],
        )
        units.append(u)
        existing.add(tuple(r["glyph_ids"]))
        r["cell_unit"] = u["index"]
        r["roles"]["cell"] = "corroborated"
    return dict(clips=rows, cell_units=units)
