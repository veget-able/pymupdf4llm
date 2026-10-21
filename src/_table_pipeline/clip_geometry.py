"""Clip-scope geometry contracts, separated from benchmark I/O.

Baseline/advance units are PDF points, not glyph ink. These tolerances differ
from placement/node clustering; sharing those algorithms would change behavior.
"""

from bisect import bisect_left, bisect_right
import statistics
import unicodedata
import numpy as np
from pymupdf._table_clip import area, intersect


def key(text):
    return "".join(unicodedata.normalize("NFKC", text).split())


def compact(text):
    return key(text).casefold()


def inside(g, box, pad=0.0):
    return box[0] - pad <= (g["x0"] + g["x1"]) / 2 <= box[2] + pad and box[1] - pad <= g["y"] <= box[3] + pad


def lines_from_runs(runs):
    """Cluster by baseline, not glyph top; preserve source spaces within each run."""
    uniq = {tuple(round(x[k], 3) for k in ("x0", "x1", "y", "size")) + (x["text"],): x for x in runs if x["text"]}
    groups = []
    for run in sorted(uniq.values(), key=lambda x: (x["y"], x["x0"])):
        tol = max(0.5, run["size"] * 0.2)
        choices = [(abs(run["y"] - g[0]["y"]), i) for i, g in enumerate(groups) if abs(run["y"] - g[0]["y"]) <= tol]
        if choices:
            groups[min(choices)[1]].append(run)
        else:
            groups.append([run])
    out = []
    for group in groups:
        ordered = sorted(group, key=lambda x: (x["x0"], x["x1"]))
        text = ""
        right = None
        size = 0
        for x in ordered:
            if (
                right is not None
                and x["x0"] - right > max(0.8, min(size, x["size"]) * 0.15)
                and text
                and not text[-1].isspace()
                and not x["text"].startswith(" ")
            ):
                text += " "
            text += x["text"]
            right = max(right or x["x1"], x["x1"])
            size = x["size"]
        if text.strip():
            out.append(
                dict(
                    text=text.strip(),
                    y=sum(x["y"] for x in group) / len(group),
                    size=max(x["size"] for x in group),
                    x0=min(x["x0"] for x in group),
                    x1=max(x["x1"] for x in group),
                )
            )
    return out


def text_columns(gs):
    """Persistent whitespace separates projected glyph columns; no GT."""
    if not gs:
        return []
    size = statistics.median(g["size"] for g in gs)
    bands = []
    for g in sorted(gs, key=lambda g: (g["x0"], g["x1"])):
        if not bands or g["x0"] - bands[-1]["right"] > 1.5 * size:
            bands.append(dict(right=g["x1"], glyphs=[]))
        bands[-1]["right"] = max(bands[-1]["right"], g["x1"])
        bands[-1]["glyphs"].append(g)
    return [
        dict(text=" ".join(l["text"] for l in lines_from_runs(b["glyphs"])), lines=len(lines_from_runs(b["glyphs"])))
        for b in bands
    ]


class PageText:
    def __init__(self, glyphs):
        self.glyphs = glyphs
        self.ids = sorted((i for i, g in enumerate(glyphs) if key(g["text"])), key=lambda i: glyphs[i]["y"])
        self.ys = [glyphs[i]["y"] for i in self.ids]
        groups = []
        for i in sorted(range(len(glyphs)), key=lambda i: (glyphs[i]["y"], glyphs[i]["x0"])):
            g = glyphs[i]
            choices = [
                (abs(g["y"] - glyphs[v[0]]["y"]), j)
                for j, v in enumerate(groups)
                if abs(g["y"] - glyphs[v[0]]["y"]) <= max(0.5, g["size"] * 0.2)
            ]
            if choices:
                groups[min(choices)[1]].append(i)
            else:
                groups.append([i])
        self.word_edges = []
        for group in groups:
            ids = sorted(group, key=lambda i: (glyphs[i]["x0"], glyphs[i]["x1"]))
            for i, j in zip(ids, ids[1:]):
                a, b = (glyphs[i], glyphs[j])
                gap = b["x0"] - a["x1"]
                if (
                    key(a["text"])
                    and key(b["text"])
                    and (-min(a["size"], b["size"]) * 0.1 <= gap <= max(0.8, min(a["size"], b["size"]) * 0.15))
                ):
                    self.word_edges.append((i, j))

    def query(self, box, pad=0.0):
        lo, hi = (bisect_left(self.ys, box[1] - pad), bisect_right(self.ys, box[3] + pad))
        return [
            i
            for i in self.ids[lo:hi]
            if box[0] - pad <= (self.glyphs[i]["x0"] + self.glyphs[i]["x1"]) / 2 <= box[2] + pad
        ]

    def cuts_word(self, ids):
        own = set(ids)
        return any(((i in own) != (j in own) for i, j in self.word_edges))


def prepare(clips, line_height, tolerance=3.0):
    boxes = [c["bbox"] for c in clips]
    n = len(boxes)
    out = {
        "clips": clips,
        "line_height": line_height,
        "tol": tolerance,
        "by_id": {c["index"]: i for i, c in enumerate(clips)},
    }
    if not n:
        return dict(out, boxes=[], row={}, col={}, repeat=[])
    a = np.asarray(boxes, dtype=float)
    width = np.maximum(0.001, a[:, 2] - a[:, 0])
    height = np.maximum(0.001, a[:, 3] - a[:, 1])
    xgap = np.maximum(0, np.maximum(a[:, None, 0] - a[None, :, 2], a[None, :, 0] - a[:, None, 2]))
    ygap = np.maximum(0, np.maximum(a[:, None, 1] - a[None, :, 3], a[None, :, 1] - a[:, None, 3]))
    # Require disjoint bands, so repeated painting/near-identical boxes do not count.
    vd = (
        (np.abs(a[:, None, 0] - a[None, :, 0]) <= tolerance)
        & (np.abs(a[:, None, 2] - a[None, :, 2]) <= tolerance)
        & (
            np.abs((a[:, 1] + a[:, 3])[:, None] - (a[:, 1] + a[:, 3])[None, :]) / 2
            >= np.minimum(height[:, None], height[None, :]) * 0.8
        )
        & (ygap <= 3 * line_height)
    )
    hd = (
        (np.abs(a[:, None, 1] - a[None, :, 1]) <= tolerance)
        & (np.abs(a[:, None, 3] - a[None, :, 3]) <= tolerance)
        & (
            np.abs((a[:, 0] + a[:, 2])[:, None] - (a[:, 0] + a[:, 2])[None, :]) / 2
            >= np.minimum(width[:, None], width[None, :]) * 0.8
        )
        & (xgap <= 3 * line_height)
    )
    # Count distinct neighbor bands rather than repeated near-identical geometry.
    repeat = []
    for i in range(n):

        def distinct(vals):
            bands = []
            for v in sorted(vals):
                if not bands or v - bands[-1] > 0.1:
                    bands.append(v)
            return len(bands)

        repeat.append(
            dict(
                vertical=distinct([(a[j, 1] + a[j, 3]) / 2 for j in np.flatnonzero(vd[i])]),
                horizontal=distinct([(a[j, 0] + a[j, 2]) / 2 for j in np.flatnonzero(hd[i])]),
            )
        )
    return dict(out, boxes=boxes, repeat=repeat)


def background(box, paints):
    """Resolve visible rectangular paint in draw order; mixed/unknown defers.

    Split visible fragments, not colors weighted by area. Even a small later
    partial cover matters. A later opaque cover may hide earlier uncertainty.
    Only 0.0001pt coordinate serialization noise is snapped at the query edge.
    """
    if area(box) <= 0:
        return None
    pieces = [(list(box), [1.0, 1.0, 1.0])]
    for p in paints:
        b = list(p["bbox"])
        for axis in (0, 1):
            for edge in (axis, axis + 2):
                for bound in (box[axis], box[axis + 2]):
                    if abs(b[edge] - bound) <= 0.0001:
                        b[edge] = bound
        if area(intersect(box, b)) <= 0:
            continue
        next_pieces = []
        for r, color in pieces:
            q = intersect(r, b)
            if area(q) <= 0:
                next_pieces.append((r, color))
                continue
            for rem in (
                [r[0], r[1], q[0], r[3]],
                [q[2], r[1], r[2], r[3]],
                [q[0], r[1], q[2], q[1]],
                [q[0], q[3], q[2], r[3]],
            ):
                if area(rem) > 0:
                    next_pieces.append((rem, color))
            next_pieces.append((q, p["color"] if p["known"] else None))
        pieces = next_pieces
    colors = [c for _, c in pieces]
    if any(c is None or len(c) != 3 for c in colors):
        return None
    if any(max(abs(a - b) for a, b in zip(c, colors[0])) > 1e-6 for c in colors):
        return None
    return colors[0]
