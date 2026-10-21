"""union 분할 결정에 셀/텍스트 코히런스 억제 게이트를 추가 (로라 검토 반영 v2).

사용자 지시: 후단 revert가 아니라 기존 union 분할 결정 자체를 수정. 열수뿐
아니라 셀·텍스트 대응으로 부모 통짜 vs 괘선 자식을 판단, 불충분하면 기존
경로(분할) 유지, GNN 과병합을 union이 올바르게 분리한 사례도 보호.

로라 검토 반영(v2):
  1. **저비용 조건 선검사**: k/열수/스택/x-포함/x-정렬(전부 bbox·격자 기반)을
     먼저 통과시킨 뒤에만 비싼 부모 TGIF를 만진다(k<3 등에 추론 낭비 없음).
  2. **부모 추론 결과 재사용**: `pred.resolve()`로 result[0]를 캐시하고 args를
     복원 → 하류 resolve()가 캐시 재사용(2차 TGIF 없음)·retain 무손상.
     격자 변환은 `_layout_table_grids`(=original_reader) 재사용(복제 아님).
  3. **결측 → 기존 분할 유지**: span_mult가 None(텍스트 스팬 부재)이면 측정
     불가 → 억제 안 함. None을 0으로 강제하지 않는다(결측≠측정0 구분).
  4. **공용 헬퍼 공유**: `_jaccard`/`_tokens`(vg_rule_primitives), `x_iou`
     (fragment_consolidation), 페이지 스팬은 페이지에 캐시. 토큰화는 공용
     `_tokens`(alpha≥2 단어) 사용 — 반복 '헤더' 판별용이므로 숫자 데이터행은
     빈 집합=veto 미발화(정상).

억제(부모 gnn_keep 유지)의 양성 증거(전부 충족):
  A. k = 자식 수 >= 3
  B. 자식 열 구조 = 균일 또는 '좁은 첫 조각 + 균일 본문'(body_cols != None)
  C. 수직 스택 + 부모 폭 x-포함. 외곽선만 넘는 경우에는 부모 노드가 소유한
     공통 상단 행과 실제 span의 x-포함을 모두 확인하는 제한적 예외 허용
  D. 본문 자식 x-정렬(x_iou>=0.7)
  E. maxChildJac < 0.5  (반복 헤더 = 병렬 별개표 배제)
  --- 이하 span 품질: 자식을 먼저 검사하고 통과할 때만 부모 TGIF ---
  F. span_mult 측정 가능(부모·자식 None 아님) & parent<=max(child)+TOL
  G. 부모 격자 2d content support = True

wrap()은 union_content_recovery 와 합성되도록 원본 _union_replace_append를
감싼다(gate가 base, recovery가 그 위 → 억제된 gnn_keep은 recovery가 스킵).
"""
from types import SimpleNamespace

import pymupdf

from pymupdf4llm._table_pipeline.fragment_consolidation import column_intervals, x_iou
from pymupdf4llm._table_pipeline.vg_rule_primitives import _jaccard, _tokens

JAC_VETO = 0.5
SPAN_MULT_TOL = 1.0
# 신뢰도 상한: 셀이 이보다 많은 수평 span 그룹을 뭉치면(=극도 under-segmented)
# 통짜 재구성이 불신 → 억제 안 함. 기존 grid-ref 게이트의 span-mult>3
# "under-segmented" 판정과 같은 계열(여기선 여유 있게). 깨끗한 표는 <=3.
SPAN_MULT_CEIL = 6.0
X_CONTAIN_TOL = 3.0



def _grid_cols(grid):
    return max((len(r) for r in grid), default=0)


def body_cols(cols):
    """균일이면 그 값, '좁은 첫 조각 + 균일 본문'이면 본문 열수, 아니면 None."""
    if not cols:
        return None
    if len(set(cols)) == 1:
        return cols[0]
    body = cols[1:]
    if len(set(body)) == 1 and cols[0] < body[0] and len(body) >= 2:
        return body[0]
    return None


def _x_contained(inner, outer, tol=X_CONTAIN_TOL):
    return outer[0] - tol <= inner[0] and inner[2] <= outer[2] + tol


def _page_spans(page):
    """Reuse union's text-bearing span records, also consumed by span multiplicity."""
    from pymupdf._table_union import _union_text_span_records
    return _union_text_span_records(page)


def _first_row_cell_texts(grid, spans):
    """격자 첫 내용 행의 셀별 텍스트(공용 _tokens 입력용). 빈 행은 건너뜀."""
    for row in grid:
        cells = [c for c in row if c is not None]
        if not cells:
            continue
        cell_texts, any_text = [], False
        for cell in cells:
            rect = pymupdf.Rect(cell)
            words = [t for sr, t in spans
                     if rect.x0 <= (sr.x0 + sr.x1) / 2 < rect.x1
                     and rect.y0 <= (sr.y0 + sr.y1) / 2 < rect.y1]
            if words:
                any_text = True
            cell_texts.append(" ".join(words))
        if any_text:
            return cell_texts
    return None


def _concrete_parent_grid(parent_entry):
    """부모 통짜 격자를 concrete로 반환(추론 결과 재사용).

    eager: entry[1]이 이미 concrete list.
    deferred: entry[1]이 DeferredRows → group['table_grid'] DeferredPrediction을
    resolve()해 result[0] 캐시(하류 resolve가 재사용=2차 TGIF 없음). args는
    복원(하류 region-split retain 무손상). 격자 변환은 original_reader
    (=_layout_table_grids) 재사용.
    """
    g = parent_entry[1]
    if isinstance(g, list):
        return g
    group = getattr(g, "group", None)
    reader = getattr(g, "original_reader", None)
    if group is None or reader is None:
        return None
    pred = group.get("table_grid")
    if pred is None or getattr(pred, "args", None) is None:
        return None
    saved = (pred.args, pred.kwargs)
    try:
        pred.resolve()                       # result[0] 캐시; args 해제
    finally:
        pred.args, pred.kwargs = saved       # 하류 retain 위해 복원
    entries = reader(SimpleNamespace(layout_information=[group]))
    if len(entries) != 1:
        return None
    return entries[0][1]


def _leading_content_contained(parent, kids, page):
    """Check parent-owned leading labels before acquiring live span evidence.

    Node text is an inexpensive ownership precheck, not a replacement for the
    page-span contract used by Jaccard and multiplicity. Never mutate either.
    """
    # Strictly uniform slots, and a leading band omitted by every child.
    cols = [_grid_cols(c[1]) for c in kids]
    if len(set(cols)) != 1 or cols[0] < 2:
        return False
    pbb = list(parent[0]); top = float(kids[0][0].y0)
    if top <= pbb[1]:
        return False
    intervals = column_intervals(kids[0][1])
    if any(c is None for c in intervals):
        return False
    band = [[(x0, pbb[1], x1, top) for x0, x1 in intervals]]
    # The parent must itself own the proposed leading row. Retained GNN node
    # boxes/texts can reject missing columns without acquiring page spans.
    group = getattr(parent[1], 'group', None)
    if group is not None:
        pred = group.get('table_grid')
        inputs = getattr(pred, 'kwargs', None)
        if inputs is None:
            return False
        boxes, texts = group['bboxes'], inputs['texts']
        if len(boxes) != len(texts):
            return False
        records = [(pymupdf.Rect(b), t) for b, t in zip(boxes, texts)]
        leading = _first_row_cell_texts(band, records)
        if leading is None or not all(_tokens([t]) for t in leading):
            return False
    spans = _page_spans(page)
    texts = _first_row_cell_texts(band, spans)
    if texts is None or not all(_tokens([t]) for t in texts):
        return False
    # All live span rectangles owned by each child's bbox must fit the parent
    # in x. Preserve the existing 3pt tolerance; empty evidence is rejected.
    for child in kids:
        b = child[0]
        inside = [r for r, _ in spans if b.x0 <= (r.x0+r.x1)/2 < b.x1
                  and b.y0 <= (r.y0+r.y1)/2 < b.y1]
        if not inside or not all(_x_contained(list(r), pbb) for r in inside):
            return False
    return True


def should_suppress(parent_entry, children, page, union):
    """부모 통짜 보존(gnn_keep)의 양성 증거가 충분한가. (bool, reason).

    저비용(bbox·격자) 조건을 먼저 통과시킨 뒤에만 부모 TGIF를 만진다.
    """
    # --- A. k>=3 ---
    k = len(children)
    if k < 3:
        return False, "k<3"
    # --- B. 열 구조 ---
    cols = [_grid_cols(c[1]) for c in children]
    tgt = body_cols(cols)
    if tgt is None:
        return False, f"cols-not-uniform-or-narrow-header:{cols}"
    kids = sorted(children, key=lambda e: (float(e[0].y0), float(e[0].x0)))
    kbboxes = [list(c[0]) for c in kids]
    # --- C. 수직 스택 + 외곽선 또는 공통 상단 행/내용의 부모 폭 x-포함 ---
    if not all(a[3] <= b[1] + 1.0 for a, b in zip(kbboxes, kbboxes[1:])):
        return False, "not-vertical-stack"
    pbb = list(parent_entry[0])
    outside = not all(_x_contained(b, pbb) for b in kbboxes)
    if outside and not _leading_content_contained(parent_entry, kids, page):
        return False, "child-not-x-contained"
    # --- D. 본문 자식 x-정렬 ---
    body = kids[1:] if len(set(cols)) != 1 else kids
    bbody = [list(c[0]) for c in body]
    if not all(x_iou(bbody[0], b) >= 0.7 for b in bbody[1:]):
        return False, "body-not-x-aligned"
    # --- E. 첫행 Jaccard veto (반복 헤더 배제) ---
    spans = _page_spans(page)
    firsts = []
    for c in kids:
        cts = _first_row_cell_texts(c[1], spans)
        firsts.append(_tokens(cts) if cts else set())
    max_jac = max((_jaccard(firsts[0], f) for f in firsts[1:]), default=0.0)
    if max_jac >= JAC_VETO:
        return False, f"repeated-header-jaccard:{max_jac:.2f}"
    # --- F. 자식 span 선검사 후 필요한 부모만 TGIF 평가 ---
    # Child grids already exist. Missing/over-ceiling evidence alone rules
    # out suppression, so do not materialize the parent just to reject it.
    csm_vals = [union._union_span_multiplicity(page, c[1]) for c in kids]
    if any(v is None for v in csm_vals):
        return False, "span-mult-missing"
    csm = max(csm_vals)
    if csm > SPAN_MULT_CEIL:
        return False, f"too-under-segmented-child:csm={csm}"
    pgrid = _concrete_parent_grid(parent_entry)
    if pgrid is None:
        return False, "parent-grid-unavailable"
    if outside and _grid_cols(pgrid) != cols[0]:
        return False, "leading-band-parent-column-mismatch"
    psm = union._union_span_multiplicity(page, pgrid)
    if psm is None:
        return False, "span-mult-missing"      # Missing is not measured zero.
    if max(psm, csm) > SPAN_MULT_CEIL:
        return False, f"too-under-segmented:psm={psm},csm={csm}"  # 재구성 불신
    if psm > csm + SPAN_MULT_TOL:
        return False, f"parent-under-segmented:{psm}>{csm}"
    # --- G. 부모가 한 표로 읽힘 ---
    if not union._union_grid_has_2d_content_support(pgrid):
        return False, "parent-no-2d-support"
    return True, f"suppress(k={k},body={tgt},jac={max_jac:.2f},psm={psm},csm={csm})"


def wrap(original, events):
    from pymupdf import _table_union as union

    def gated(existing, candidates, *, page, _selection=None, **kwargs):
        selection = _selection if _selection is not None else union._UnionSelection()
        entries = original(existing, candidates, page=page, _selection=selection, **kwargs)
        by_parent = selection.split_groups
        if not by_parent:
            return entries
        parents = selection.parents
        suppress_children = set()
        keep_parents = []
        suppressed_keys = []
        for key, kids in by_parent.items():
            pe = parents.get(key)
            if pe is None:
                continue
            try:
                ok, reason = should_suppress(pe, kids, page, union)
            except Exception as exc:  # noqa: BLE001
                events.append({"page": page.number, "key": list(key),
                               "status": "gate-error", "reason": repr(exc)})
                continue
            events.append({"page": page.number, "key": list(key),
                           "status": "suppress" if ok else "split",
                           "reason": reason, "n_children": len(kids)})
            if ok:
                suppressed_keys.append(key)
                suppress_children.update(id(c) for c in kids)
                keep_parents.append(union._entry_with_provenance(pe, bbox_operation="gnn_keep"))
        if not suppress_children:
            return entries
        out = [e for e in entries if id(e) not in suppress_children]
        out.extend(keep_parents)
        for key in suppressed_keys:
            del selection.split_groups[key]
            kept = [e for e in selection.recovery_groups[key] if id(e) not in suppress_children]
            if kept:
                selection.recovery_groups[key] = kept
            else:
                del selection.recovery_groups[key]
        # A repeated provenance key can retain a later grid_ref after its early
        # split was suppressed. Match the first-surviving-entry order used by R.
        positions = {id(e): i for i, e in enumerate(out)}
        selection.recovery_groups = dict(sorted(selection.recovery_groups.items(),
            key=lambda item: positions[id(item[1][0])]))
        return out

    return gated
