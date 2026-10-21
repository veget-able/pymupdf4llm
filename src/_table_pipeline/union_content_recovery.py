"""Approved union-content-recovery (V9), behavior frozen at union-recover/r7.

Only provenance differs from the supplied algorithm. Activated process-locally
by the accepted runner; model R6 and the V8 pipeline are unchanged.
"""
import re
import unicodedata
from types import SimpleNamespace

import numpy as np




def _norm(s):
    s = unicodedata.normalize("NFKC", s).casefold()
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def _white_spans(page):
    out = []
    try:
        for blk in page.get_text("dict")["blocks"]:
            for line in blk.get("lines", []):
                for sp in line.get("spans", []):
                    if sp.get("color", 0) == 0xFFFFFF:
                        toks = {_norm(w) for w in sp["text"].split() if _norm(w)}
                        if toks:
                            out.append((sp["bbox"], toks))
    except Exception:
        pass
    return out
GAP = 25.0
XPAD = 10.0
EXP_X, EXP_Y = 45.0, 10.0


def _cluster(boxes, ex, ey):
    n = len(boxes)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            a, b = boxes[i], boxes[j]
            if (min(a[2], b[2]) - max(a[0], b[0]) > -ex and
                    min(a[3], b[3]) - max(a[1], b[1]) > -ey):
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _bands(iv, gap):
    out = []
    for lo, hi in sorted(iv):
        if out and lo <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def _gridness(boxes):
    rows = _bands([(b[1], b[3]) for b in boxes], 2.0)
    maxc = 0
    for lo, hi in rows:
        items = [b for b in boxes if lo - 1 <= (b[1] + b[3]) / 2 <= hi + 1]
        maxc = max(maxc, len(_bands([(b[0], b[2]) for b in items], 4.0)))
    return len(rows), maxc


def _union_box(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _grid_cols(grid):
    """자식 격자의 열-밴드 [(x0,x1)...] — 각 열 인덱스의 셀 x범위 합집합."""
    ncols = max(len(r) for r in grid)
    cols = []
    for j in range(ncols):
        xs = [(c[0], c[2]) for r in grid for c in [r[j] if j < len(r) else None]
              if c is not None]
        if xs:
            cols.append([min(x for x, _ in xs), max(x for _, x in xs)])
    return cols


def _grid_rows_y(grid):
    """행별 y범위 — grid 행과 1:1 정렬(빈 행은 None)."""
    ys = []
    for r in grid:
        cs = [c for c in r if c is not None]
        ys.append([min(c[1] for c in cs), max(c[3] for c in cs)] if cs else None)
    return ys


def wrap(original, events, *, complete=False):
    from pymupdf import _table_union as union

    def fused(existing, candidates, *, page, _selection=None, **kwargs):
        contexts = {}
        if complete:
            from pymupdf4llm._table_pipeline.table_content_recovery import SourceNode
            from pymupdf4llm._table_pipeline import table_restoration as restoration
            for entry in existing:
                group = getattr(entry[1], "group", None)
                if group is None:
                    raise ValueError("Content completion requires retained GNN node material")
                prediction = group["table_grid"]
                if prediction.kwargs is None:
                    raise ValueError("Ownership inputs were released before union")
                boxes, texts = group["bboxes"], prediction.kwargs["texts"]
                if len(boxes) != len(texts):
                    raise ValueError("Ownership text/node alignment mismatch")
                key = tuple(entry.bbox_provenance["source_gnn_indices"])
                ctx = restoration.RestorationContext(page.number, key, entry)
                ctx.source_nodes = tuple(SourceNode(i, tuple(float(v) for v in b), t, (page.number, *key))
                                         for i, (b, t) in enumerate(zip(boxes, texts)))
                contexts[key] = ctx
                restoration.publish(ctx)
        selection = _selection if _selection is not None else union._UnionSelection()
        entries = original(existing, candidates, page=page, _selection=selection, **kwargs)
        for key, context in contexts.items():
            context.split_selected = key in selection.split_groups
        by_parent = selection.recovery_groups
        if not by_parent:
            return entries
        parents = selection.parents
        replace, add = {}, []
        for key, children in by_parent.items():
            pe = parents.get(key)
            if pe is None or not hasattr(pe[1], "group"):
                continue
            try:
                rep, extra = _plan(pe, children, key, page, union, contexts.get(key))
            except Exception as exc:
                events.append({"page": page.number, "key": list(key),
                               "status": "error", "reason": repr(exc)})
                continue
            replace.update(rep)
            add.extend(extra)
        if not replace and not add:
            return entries
        out = [replace.get(id(e), e) for e in entries]
        out.extend(add)
        return out

    def _plan(pe, children, key, page, union, context=None):
        group = pe[1].group
        pred = group["table_grid"]
        node_boxes = np.asarray(group["bboxes"], dtype=float)
        texts = pred.kwargs["texts"]
        image, local = pred.args
        parent = group["group_bbox"][:4]
        offset = np.array([parent[0], parent[1], parent[0], parent[1]])
        if len(texts) != len(node_boxes) or not np.allclose(
                local + offset, node_boxes, atol=1e-4):
            raise ValueError("retained TGIF material mismatch")
        centers = (node_boxes[:, :2] + node_boxes[:, 2:]) / 2
        def eff_bbox(entry):
            if entry.bbox_provenance.get("bbox_operation") == "grid_ref":
                cells = [c for r in entry[1] for c in r if c is not None]
                if cells:
                    return [min(c[0] for c in cells), min(c[1] for c in cells),
                            max(c[2] for c in cells), max(c[3] for c in cells)]
            return list(entry[0])
        cbs = [eff_bbox(c) for c in children]

        def in_box(pt, b, tol=1.0):
            return b[0] - tol <= pt[0] <= b[2] + tol and b[1] - tol <= pt[1] <= b[3] + tol

        white = _white_spans(page)

        def node_is_white(i):
            b = node_boxes[i]
            x, y = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            toks = {_norm(w) for w in texts[i].split() if _norm(w)} if texts[i] else set()
            if not toks:
                return False
            for wb, wt in white:
                if wb[0] - 3 <= x <= wb[2] + 3 and wb[1] - 3 <= y <= wb[3] + 3                         and toks <= wt:
                    return True
            return False

        residual = [i for i, c in enumerate(centers)
                    if not any(in_box(c, b) for b in cbs)
                    and not node_is_white(i)]
        from pymupdf4llm._table_pipeline import table_restoration as _tr
        _ctx = context if context is not None else _tr.RestorationContext(page.number, key, pe)
        _rr = _ctx.residual_report
        _rr.residual = list(residual)
        if not residual:
            _tr.publish(_ctx)
            return {}, []
        replace, add = {}, []
        new_grids = {ci: [list(r) for r in children[ci][1]] for ci in range(len(children))}
        child_steps = {ci: [] for ci in range(len(children))}
        touched = set()
        stitched_nodes = set()
        # --- S0: grid_ref 전용 헤더 밴드 stitch (행당 노드>=3, 열밴드 50%+ 점유)
        for ci in range(len(children)):
            if children[ci].bbox_provenance.get("bbox_operation") != "grid_ref":
                continue
            b = cbs[ci]
            grid = new_grids[ci]
            band = [i for i in residual if i not in stitched_nodes
                    and b[0] - XPAD <= (node_boxes[i][0] + node_boxes[i][2]) / 2 <= b[2] + XPAD
                    and -2 <= b[1] - node_boxes[i][3]
                    and b[1] - node_boxes[i][1] < GAP + 20]
            if len(band) < 3:
                continue
            cols = _grid_cols(grid)
            rows = _bands([(node_boxes[i][1], node_boxes[i][3]) for i in band], 2.0)
            keep = []
            for lo, hi in rows:
                rn = [node_boxes[i] for i in band
                      if lo - 1 <= (node_boxes[i][1] + node_boxes[i][3]) / 2 <= hi + 1]
                occ = set()
                for nb in rn:
                    for bi, (l2, h2) in enumerate(cols):
                        if min(nb[2], h2) - max(nb[0], l2) > 0.3 * (nb[2] - nb[0]):
                            occ.add(bi)
                if len(rn) >= 3 and len(occ) >= max(2, len(cols) * 0.5):
                    keep.append((lo, hi))
            if not keep:
                continue
            newrows = [[(l2, lo, h2, hi) for l2, h2 in cols] for lo, hi in keep]
            new_grids[ci] = newrows + grid
            child_steps[ci].append("S0")
            touched.add(ci)
            used = [i for i in band if any(
                lo - 1 <= (node_boxes[i][1] + node_boxes[i][3]) / 2 <= hi + 1
                for lo, hi in keep)]
            stitched_nodes.update(used)
            _rr.attempted.update(used)
            _rr.indeterminate.update(used)
            events.append({"page": page.number, "key": list(key),
                           "status": "stitch-header-band", "child": int(ci),
                           "n_rows": len(keep), "nodes": int(len(used))})
        # --- S1: 인접 스트립 이어붙이기 (팽창 좁게: 스트립은 붙어있음)
        for comp in _cluster([node_boxes[i] for i in residual], 12.0, 4.0):
            idx = [residual[i] for i in comp]
            boxes = [node_boxes[i] for i in idx]
            cb = _union_box(boxes)
            done = False
            for ci in range(len(children)):
                b = cbs[ci]
                grid = new_grids[ci]
                xin = cb[0] >= b[0] - XPAD and cb[2] <= b[2] + XPAD
                yin = cb[1] >= b[1] - XPAD and cb[3] <= b[3] + XPAD
                if xin and (0 <= b[1] - cb[3] < GAP or 0 <= cb[1] - b[3] < GAP):
                    above = bool(cb[3] <= b[1])
                    # 내부 금지: 스트립 반대편 GAP 내에 다른 자식이 있으면 skip
                    opposite = any(
                        oj != ci and (
                            (0 <= cb[1] - cbs[oj][3] < GAP) if above
                            else (0 <= cbs[oj][1] - cb[3] < GAP))
                        and min(cb[2], cbs[oj][2]) - max(cb[0], cbs[oj][0]) > 0
                        for oj in range(len(children)))
                    if opposite:
                        continue
                    cols = _grid_cols(grid)
                    rows = _bands([(nb[1], nb[3]) for nb in boxes], 2.0)
                    # 표-행 가드: 각 행의 노드가 >=2개 열-밴드를 점유해야 채택
                    keep = []
                    for lo, hi in rows:
                        rn = [nb for nb in boxes if lo - 1 <= (nb[1] + nb[3]) / 2 <= hi + 1]
                        occ = set()
                        for nb in rn:
                            for bi, (l2, h2) in enumerate(cols):
                                if min(nb[2], h2) - max(nb[0], l2) > 0.3 * (nb[2] - nb[0]):
                                    occ.add(bi)
                        if len(occ) >= 2 and len(rn) >= 2:
                            keep.append((lo, hi))
                    if not keep:
                        continue
                    newrows = [[(l2, lo, h2, hi) for l2, h2 in cols]
                               for lo, hi in keep]
                    new_grids[ci] = (newrows + grid) if above else (grid + newrows)
                    child_steps[ci].append("S1")
                    touched.add(ci)
                    stitched_nodes.update(idx)
                    _rr.attempted.update(idx)
                    _rr.indeterminate.update(idx)
                    events.append({"page": page.number, "key": list(key),
                                   "status": "stitch-rows", "child": int(ci),
                                   "n_rows": len(keep), "nodes": int(len(idx)),
                                   "above": above})
                    done = True
                    break
                if yin and (0 <= b[0] - cb[2] < GAP or 0 <= cb[0] - b[2] < GAP):
                    left = bool(cb[2] <= b[0])
                    opposite = any(
                        oj != ci and (
                            (0 <= cb[0] - cbs[oj][2] < GAP) if left
                            else (0 <= cbs[oj][0] - cb[2] < GAP))
                        and min(cb[3], cbs[oj][3]) - max(cb[1], cbs[oj][1]) > 0
                        for oj in range(len(children)))
                    if opposite:
                        continue
                    # 스트립이 자체로 >=2열이면 독립 표 후보 — append(S2)로 넘김
                    _, strip_cols = _gridness(boxes)
                    if strip_cols >= 2:
                        continue
                    rows_y = _grid_rows_y(grid)
                    valid = [y for y in rows_y if y is not None]
                    # 표-열 가드: 노드가 >=2개의 서로 다른 격자 행에 정렬
                    hit_rows = set()
                    for nb in boxes:
                        for ri2, y in enumerate(valid):
                            if min(nb[3], y[1]) - max(nb[1], y[0]) > 0.3 * (nb[3] - nb[1]):
                                hit_rows.add(ri2)
                    covered = sum(1 for nb in boxes if any(
                        min(nb[3], hi) - max(nb[1], lo) > 0.3 * (nb[3] - nb[1])
                        for lo, hi in valid))
                    if not valid or covered / len(boxes) < 0.5 or len(hit_rows) < 2:
                        continue
                    ng = []
                    for r, y in zip(grid, rows_y):
                        r = list(r)
                        cell = (cb[0], y[0], cb[2], y[1]) if y else None
                        ng.append([cell] + r if left else r + [cell])
                    new_grids[ci] = ng
                    child_steps[ci].append("S1-prime")
                    touched.add(ci)
                    stitched_nodes.update(idx)
                    _rr.attempted.update(idx)
                    _rr.indeterminate.update(idx)
                    events.append({"page": page.number, "key": list(key),
                                   "status": "stitch-col", "child": int(ci),
                                   "nodes": int(len(idx)), "left": left})
                    done = True
                    break
            if done:
                continue
        # --- S2: 비인접 잔여의 신규 격자 추가 (비대칭 팽창)
        rem = [i for i in residual if i not in stitched_nodes]
        for comp in _cluster([node_boxes[i] for i in rem], EXP_X, EXP_Y):
            idx = [rem[i] for i in comp]
            boxes = [node_boxes[i] for i in idx]
            cb = _union_box(boxes)
            r, c = _gridness(boxes)
            if r < 2 or c < 2 or len(idx) < 4:
                events.append({"page": page.number, "key": list(key),
                               "status": "skip", "nodes": int(len(idx)),
                               "grid": [int(r), int(c)]})
                continue
            # 자식/이어붙인 영역과 겹치면 포기(안전)
            pad = 2.0
            box = [max(cb[0] - pad, parent[0]), max(cb[1] - pad, parent[1]),
                   min(cb[2] + pad, parent[2]), min(cb[3] + pad, parent[3])]
            if any(max(0, min(box[2], b[2]) - max(box[0], b[0])) *
                   max(0, min(box[3], b[3]) - max(box[1], b[1])) > 1.0
                   for b in cbs):
                events.append({"page": page.number, "key": list(key),
                               "status": "clash-skip", "box": [round(float(x), 1) for x in box]})
                continue
            px, py = max(0, int(parent[0])), max(0, int(parent[1]))
            ix0, iy0 = max(px, int(box[0])), max(py, int(box[1]))
            ix1 = min(px + image.shape[1], int(box[2]))
            iy1 = min(py + image.shape[0], int(box[3]))
            crop = image[iy0 - py:iy1 - py, ix0 - px:ix1 - px]
            if not crop.size:
                continue
            sub_local = node_boxes[idx] - [ix0, iy0, ix0, iy0]
            grid, _ = pred.predict(crop, sub_local, texts=[texts[i] for i in idx])
            if grid is None:
                events.append({"page": page.number, "key": list(key),
                               "status": "tgif-none"})
                continue
            child_group = dict(group, group_bbox=[ix0, iy0, ix1, iy1],
                               table_grid=grid)
            got = pe[1].original_reader(
                SimpleNamespace(layout_information=[child_group]))
            if len(got) != 1:
                continue
            add.append(union._entry_with_provenance(
                got[0], bbox_operation="union_recover_append",
                source_gnn_indices=list(key), bbox_source="union_recovery",
                grid_source="tgif", grid_sources=["tgif"], recovery_steps=["S2"],
                recovery_revision="union-recover/r7", recovery_parent_bbox=list(parent)))
            _rr.attempted.update(idx)
            _rr.indeterminate.update(idx)
            events.append({"page": page.number, "key": list(key),
                           "status": "append", "box": [round(float(x), 1) for x in box],
                           "nodes": int(len(idx)), "grid": [int(r), int(c)]})
        _ctx.node_bboxes = {int(i): [float(v) for v in node_boxes[i]]
                            for i, _t in _rr.handoff()}
        _tr.publish(_ctx)
        # 이어붙인 자식 재구성 (bbox = 격자 전체)
        for ci in touched:
            g = new_grids[ci]
            allc = [c for r in g for c in r if c is not None]
            nb = _union_box([[c[0], c[1], c[2], c[3]] for c in allc])
            prov = dict(children[ci].bbox_provenance)
            if prov.get("bbox_operation") == "grid_ref":
                nb = _union_box([nb, list(children[ci][0])])
            else:
                prov["bbox_operation"] = "union_split_stitched"
            if prov["bbox_operation"] == "grid_ref":
                prov["bbox_operation"] = "grid_ref_stitched"
            if not np.allclose(nb, list(children[ci][0]), rtol=0, atol=1e-9):
                prov["bbox_source"] = "union_recovery"
            prov.update(grid_source="mixed", grid_sources=["find_tables", "geometric_stitch"],
                        recovery_steps=child_steps[ci], recovery_revision="union-recover/r7",
                        recovery_parent_bbox=list(parent), recovery_base_bbox=list(children[ci][0]))
            replace[id(children[ci])] = union._TableGridEntry(
                __import__("pymupdf").Rect(nb), g, prov)
        return replace, add

    return fused
