"""Frozen 2026-09-11 corrected VG material-integrated split rules.

Experimental replacement candidate, not approved V7. Only dependency closure
from pb_visual_grounding/table_region_postprocess.py; no GT or runtime caches.
"""
from __future__ import annotations
import re
import statistics
from collections import Counter, defaultdict
from typing import Any, Optional

from pymupdf4llm._table_pipeline.vg_rule_primitives import (
    _cluster_intervals, _contain, _jaccard, _tokens,
)

_MIN_COMPONENT_NODES = 6

_MAX_ITER = 3


def _region_band_split(
    nodes: list[dict],
    edges: list[dict],
    drawing_rects: Optional[list[list[float]]],
    bbox: list[float],
    base_threshold: float = 0.55,
    max_depth: int = _MAX_ITER,
    record: Optional[list] = None,
    strict_gate: bool = False,
    header_repeat: bool = False,
    y_rules: tuple = ("p1",),  # 2026-09-10: gap(P2) 제거 — P1'(반복+밀도+연도 가족) 단독이 우세
    rf_verifier=None,  # callable(below_nodes) -> bool: 경계 아래 블록의 헤더다움 검증
    rf_mode: str = "off",  # off / gate_p2 (P2 후보를 RF 관문으로 부활) / gate_all
    ablate: frozenset = frozenset(),  # 규칙 절제: family/density/year/shared_hdr/veto/block_gate
) -> list[list[float]]:
    drawing_rects = drawing_rects or []
    accepted = [
        (int(e["source"]), int(e["target"]), float(e["probability"]))
        for e in edges if float(e["probability"]) > base_threshold
    ]
    centers = [((n["bbox"][0] + n["bbox"][2]) / 2,
                (n["bbox"][1] + n["bbox"][3]) / 2) for n in nodes]

    def scan(cn: list[int], axes: tuple[str, ...]):
        fired = []
        cn_set = set(cn)
        for axis, lo_i, hi_i in (("y", 1, 3), ("x", 0, 2)):
            if axis not in axes:
                continue
            members = cn
            if axis == "x":
                # 광폭 노드(영역 폭 60%+: 산문·주석·전폭 제목)는 x 후보
                # 생성에서 제외 — 이들이 열 클러스터를 하나로 이어버려
                # 가로 병합의 열 구조가 보이지 않게 된다. (partition에는
                # 그대로 포함되어 중심 위치로 블록에 배속된다.)
                w0 = min(nodes[i]["bbox"][0] for i in cn)
                w1 = max(nodes[i]["bbox"][2] for i in cn)
                width = max(w1 - w0, 1e-9)
                members = [i for i in cn
                           if nodes[i]["bbox"][2] - nodes[i]["bbox"][0]
                           < 0.6 * width] or cn
            clusters, bounds = _cluster_intervals(
                [(nodes[i]["bbox"][lo_i], nodes[i]["bbox"][hi_i], i)
                 for i in members])
            gaps = [bounds[k + 1][0] - bounds[k][1] for k in range(len(clusters) - 1)]
            gaps = [g for g in gaps if g > 0]
            if not gaps or len(clusters) < 2:
                continue
            med_gap = statistics.median(gaps)
            rhythm_ok = len(gaps) >= 3
            cluster_tokens = [
                _tokens([nodes[i].get("text") for i in c]) for c in clusters]
            lead_tokens = cluster_tokens[0]
            comp_h = (max(nodes[i]["bbox"][3] for i in cn)
                      - min(nodes[i]["bbox"][1] for i in cn))
            cands = []
            for k in range(len(clusters) - 1):
                gap = bounds[k + 1][0] - bounds[k][1]
                if gap <= 0:
                    continue
                band_lo, band_hi = bounds[k][1], bounds[k + 1][0]
                rhythm = gap / med_gap if med_gap > 0 else 0.0
                next_tokens = cluster_tokens[k + 1]
                header_sim = _jaccard(lead_tokens, next_tokens)
                header_contain = _contain(next_tokens, lead_tokens)
                border = False
                if axis == "x":
                    for rect in drawing_rects:
                        rw, rh = rect[2] - rect[0], rect[3] - rect[1]
                        if rh >= 0.4 * comp_h and rw <= 5.0 and \
                                band_lo - 4 <= rect[0] <= band_hi + 4:
                            border = True
                            break
                cands.append((band_lo, band_hi, rhythm, next_tokens,
                              header_sim, header_contain, border))
            border_family = sum(1 for c in cands if c[6]) >= 3
            header_family = sum(1 for c in cands if c[4] >= 0.65) >= 3

            def veto_pass(band_lo, band_hi, threshold=0.5):
                crossing = []
                for i, j, p in accepted:
                    if i not in cn_set or j not in cn_set:
                        continue
                    ci = centers[i][1] if axis == "y" else centers[i][0]
                    cj = centers[j][1] if axis == "y" else centers[j][0]
                    if (ci <= band_lo and cj >= band_hi) or \
                            (cj <= band_lo and ci >= band_hi):
                        crossing.append(p)
                frac95 = (sum(1 for p in crossing if p >= 0.95) / len(crossing)
                          if crossing else None)
                return frac95 is None or frac95 < threshold

            # spatial-y의 영역 수준 재설계: band 고립 판정 대신
            # P1(반복 anchor) ∪ P2(소수 돌출 gap 계층)만 spatial로 인정.
            spatial_ok: dict[int, str] = {}
            if axis == "y":
                # P1(패턴 anchor): 헤더 행은 완전 반복이 아니라 (a) 유사
                # 가족(Jaccard>=0.5의 다른 문자행 존재) 또는 (b) 문자 밀도
                # 전이(숫자 행 다음의 문자 풍부 행)로 식별한다. 연속 anchor
                # 사이 최대 gap이 표 경계다.
                letters = [len(ts) for ts in cluster_tokens]
                # 연도-행 토큰: 재무 헤더("2025|2024|2023")는 문자 토큰이
                # 없어 가족 대조에서 배제되던 것을 연도 전용 토큰으로 포섭
                # (수량-변형 동형: 열 수가 달라져도 가족 유사로 잡힘)
                year_tokens = [
                    {w for w in re.findall(r"\b(?:19|20)\d{2}\b",
                                           " ".join((nodes[i].get("text") or "")
                                                    for i in c))}
                    for c in clusters]
                anchors = [] if "p1" in y_rules else None
                for ci_, ts in enumerate(cluster_tokens) if anchors is not None else []:
                    if len(ts) < 3:
                        continue
                    family = ("family" not in ablate) and any(
                        _jaccard(ts, other) >= 0.5
                        for cj_, other in enumerate(cluster_tokens)
                        if cj_ != ci_ and len(other) >= 3)
                    density = ("density" not in ablate) and (
                        len(ts) >= 4 and ci_ > 0 and letters[ci_ - 1] <= 1)
                    if family or density:
                        anchors.append(ci_)
                if anchors is not None and "year" not in ablate:
                    for ci_, ys in enumerate(year_tokens):
                        if ci_ in anchors or len(ys) < 2:
                            continue
                        if any(len(o) >= 2 and _jaccard(ys, o) >= 0.5
                               for cj_, o in enumerate(year_tokens)
                               if cj_ != ci_):
                            anchors.append(ci_)
                    anchors.sort()
                # 연속 붙은 anchor(제목+헤더 행 등)는 블록 시작 하나로 축약
                starts = [a for i, a in enumerate(anchors or [])
                          if i == 0 or a - anchors[i - 1] > 1]
                if len(starts) >= 2:
                    for a_prev, a_next in zip(starts, starts[1:]):
                        ks = [k for k in range(a_prev, a_next)
                              if k < len(cands)]
                        if not ks:
                            continue
                        k_best = max(
                            ks, key=lambda k: bounds[k + 1][0] - bounds[k][1])
                        if bounds[k_best + 1][0] - bounds[k_best][1] > 0:
                            spatial_ok[k_best] = "normal"
                # P2: 리듬>=2 gap이 1~2개뿐이고, 나머지 gap 대비 뚜렷한
                #     계층 분리를 이룰 때만 인정 (단일 표의 구획 gap은
                #     다수·동질이라 여기서 탈락한다).
                p2_active = ("p2" in y_rules) or (
                    rf_mode == "gate_p2" and rf_verifier is not None)
                big = ([k for k, c in enumerate(cands)
                        if rhythm_ok and c[2] >= 2.0]
                       if p2_active else [])
                if 1 <= len(big) <= 2:
                    rest = [c[0:2] for k, c in enumerate(cands) if k not in big]
                    rest_max = max((hi - lo for lo, hi in
                                    ((cands[k][0], cands[k][1]) for k in
                                     range(len(cands)) if k not in big)),
                                   default=0.0)
                    big_min = min(cands[k][1] - cands[k][0] for k in big)
                    if rest_max <= 0 or big_min >= 1.5 * rest_max:
                        tag = ("rf" if ("p2" not in y_rules
                                        and rf_mode == "gate_p2")
                               else "normal")
                        for k in big:
                            spatial_ok.setdefault(k, tag)
            else:
                # 역할 분리 확정(Table_Split_Architecture_Role_Separation.md,
                # 2026-09-10): x축 반복 절단 경로(열 토큰 가족 anchor +
                # strong veto 완화)는 제거 — 가로 반복형 병합은 refine의
                # V5-H(격자 위 반복 헤더 분리) 소관. region_split의 x축은
                # 소표본 절대 gap 예외(이질 좌우, FBLB162류)만 유지한다.

                # y-정렬 헤더 반복(실험 경로, 기본 비활성 — 2026-09-10
                # 실측에서 v9' 대비 순증 없음: 회수 53<57/오판 25>23/
                # held-out 3>2. 분절 결손·소그룹 반복 등 투표 정제 미완):
                # 같은 행 안에서 같은 토큰 패턴의 분절이 x로 k회 반복되면
                # 그 사이 gap이 표 경계다.
                h_med_x = statistics.median(
                    nodes[i]["bbox"][3] - nodes[i]["bbox"][1] for i in cn)
                rows_cl, _ = _cluster_intervals(
                    [(nodes[i]["bbox"][1], nodes[i]["bbox"][3], i) for i in cn])
                votes: dict[int, list] = {}
                for row in (rows_cl if header_repeat else []):
                    ordered = sorted(row, key=lambda i: nodes[i]["bbox"][0])
                    if len(ordered) < 2:
                        continue
                    segs: list[list[int]] = [[ordered[0]]]
                    for i in ordered[1:]:
                        prev = segs[-1][-1]
                        if nodes[i]["bbox"][0] - nodes[prev]["bbox"][2] \
                                >= 2.0 * h_med_x:
                            segs.append([i])
                        else:
                            segs[-1].append(i)
                    if len(segs) < 2:
                        continue
                    stoks = [_tokens([nodes[i].get("text") for i in s])
                             for s in segs]
                    # 헤더다움: 선두 분절이 문자 토큰 2개 이상이어야
                    # ("Yes|No"·"라벨 값" 류 반복 행 배제)
                    if len(stoks[0]) < 2:
                        continue
                    sim = [si for si, ts in enumerate(stoks)
                           if si == 0 or (len(ts) >= 1
                                          and _jaccard(ts, stoks[0]) >= 0.5)]
                    if len(sim) < 2:
                        continue
                    seg_gaps = []
                    for a, b in zip(sim, sim[1:]):
                        lo_ = max(nodes[i]["bbox"][2] for i in segs[a])
                        hi_ = min(nodes[i]["bbox"][0] for i in segs[b])
                        if hi_ > lo_:
                            seg_gaps.append((lo_, hi_))
                    if not seg_gaps:
                        continue
                    med_sg = statistics.median(h - l for l, h in seg_gaps)
                    reg_w = (max(nodes[i]["bbox"][2] for i in cn)
                             - min(nodes[i]["bbox"][0] for i in cn))
                    for lo_, hi_ in seg_gaps:
                        # 표 내부 소그룹 반복 방어: 그 행의 분절 gap 중앙값
                        # 대비 돌출한 gap만 경계 후보 (분절 2개면 그대로)
                        if len(seg_gaps) >= 3 and hi_ - lo_ < 1.5 * med_sg:
                            continue
                        # 경계 띠는 행높이 규모의 공백 — 표 폭 규모(영역
                        # 폭 25%+)의 gap은 분절 결손 오류이므로 기각
                        if hi_ - lo_ >= 0.25 * reg_w:
                            continue
                        votes.setdefault(0, []).append((lo_, hi_, len(sim)))
                all_votes = sorted(votes.get(0, []),
                                   key=lambda v: (v[0] + v[1]) / 2)
                groups_v: list[list] = []
                for v in all_votes:
                    mid = (v[0] + v[1]) / 2
                    if groups_v and mid - (groups_v[-1][-1][0]
                                           + groups_v[-1][-1][1]) / 2 \
                            <= max(2.0 * h_med_x, 6.0):
                        groups_v[-1].append(v)
                    else:
                        groups_v.append([v])
                already = [(lo_, hi_) for a_, lo_, hi_ in fired if a_ == "x"]
                for vs in groups_v:
                    lo_ = statistics.median(v[0] for v in vs)
                    hi_ = statistics.median(v[1] for v in vs)
                    kmax = max(v[2] for v in vs)
                    # 강한 증거에서만 발화: 분절 3회+ 반복 또는 복수 행이
                    # 같은 위치에 정렬. anchor 경로가 이미 발화한 band와
                    # 겹치면 중복 발화하지 않는다.
                    if not (kmax >= 3 or len(vs) >= 2):
                        continue
                    mid = (lo_ + hi_) / 2
                    if any(alo - 2 <= mid <= ahi + 2 for alo, ahi in already):
                        continue
                    if veto_pass(lo_, hi_, 0.9):
                        fired.append((axis, lo_, hi_))
                        if record is not None:
                            record.append({
                                "axis": axis, "lo": lo_, "hi": hi_,
                                "rhythm": None, "spatial": True,
                                "header": True, "border": False,
                                "period": False, "n_nodes": len(cn)})

            for k, (band_lo, band_hi, rhythm, next_tokens, header_sim,
                    header_contain, border) in enumerate(cands):
                if "veto" not in ablate and not veto_pass(band_lo, band_hi, 0.5):
                    continue
                if axis == "y":
                    spatial = k in spatial_ok
                    if spatial and rf_verifier is not None and (
                            spatial_ok.get(k) == "rf" or rf_mode == "gate_all"):
                        below = [i for i in cn if centers[i][1] >= band_hi]
                        spatial = bool(rf_verifier([nodes[i] for i in below]))
                else:
                    # x축은 소표본 절대 gap 예외만(이질 좌우 병합):
                    # x gap이 1~2개뿐이라 리듬이 정의되지 않을 때 행높이의
                    # 3배 이상 공백이면 후보 — 블록 표다움 게이트가
                    # 라벨열/값열 오분할을 걸러준다. (리듬·반복 기반 x
                    # 절단은 역할 분리에 따라 refine 소관으로 제거됨)
                    h_med = statistics.median(
                        nodes[i]["bbox"][3] - nodes[i]["bbox"][1] for i in cn)
                    spatial = (not rhythm_ok
                               and band_hi - band_lo >= 3.0 * h_med)
                header_fire = (header_sim >= 0.65 and len(next_tokens) >= 2
                               and (not header_family or rhythm >= 1.5))
                border_fire = (border and (header_sim >= 0.3 or rhythm >= 1.2)
                               and (not border_family or rhythm >= 1.5))
                period_fire = (len(next_tokens) >= 2 and header_contain >= 0.7
                               and rhythm >= 1.0)
                if spatial or header_fire or border_fire or period_fire:
                    fired.append((axis, band_lo, band_hi))
                    if record is not None:
                        record.append({
                            "axis": axis, "lo": band_lo, "hi": band_hi,
                            "rhythm": round(rhythm, 2),
                            "spatial": spatial, "header": header_fire,
                            "border": border_fire, "period": period_fire,
                            "n_nodes": len(cn)})
        return fired

    def _block_ok(g: list[int]) -> bool:
        """분할 블록의 표다움: 2행 x 2열 이상으로 구조화돼야 한다.

        열 증거는 두 층위 — (a) node 수준 x 클러스터 2개 이상, (b) 행이
        단일 node로 추출된 표(dot leader·광폭 공백으로 셀이 이어진 경우)는
        node 내부의 열 구분자 타이포그래피를 열 증거로 인정한다.
        """
        if len(g) < 2:
            return False
        rows_cl, _ = _cluster_intervals(
            [(nodes[i]["bbox"][1], nodes[i]["bbox"][3], i) for i in g])
        if len(rows_cl) < 2:
            return False
        x0 = min(nodes[i]["bbox"][0] for i in g)
        x1 = max(nodes[i]["bbox"][2] for i in g)
        width = max(x1 - x0, 1e-9)
        narrow = [i for i in g
                  if nodes[i]["bbox"][2] - nodes[i]["bbox"][0] < 0.6 * width] or g
        cols_cl, _ = _cluster_intervals(
            [(nodes[i]["bbox"][0], nodes[i]["bbox"][2], i) for i in narrow])
        if len(cols_cl) >= 2:
            return True
        texted = [(nodes[i].get("text") or "") for i in g]
        texted = [t for t in texted if len(t.strip()) >= 4]
        if not texted:
            return False
        with_sep = sum(1 for t in texted
                       if re.search(r"\.{3,}|\s{3,}\S|\t", t))
        return with_sep / len(texted) >= 0.5

    def _row_segments(row_nodes: list[int], h_ref: float) -> list[set]:
        ordered = sorted(row_nodes, key=lambda i: nodes[i]["bbox"][0])
        segs: list[list[int]] = [[ordered[0]]] if ordered else []
        for i in ordered[1:]:
            if nodes[i]["bbox"][0] - nodes[segs[-1][-1]]["bbox"][2] \
                    >= 2.0 * h_ref:
                segs.append([i])
            else:
                segs[-1].append(i)
        out = []
        for s in segs:
            ts = _tokens([nodes[i].get("text") for i in s])
            if ts:
                out.append(ts)
        return out

    def _top_header_row(g: list[int], h_ref: float, top_n: int = 3):
        """블록/영역 상단 top_n행 중 다열 헤더 후보 행(비어있지 않은
        분절 >= 2; 연도 등 숫자 헤더 포함)의 토큰 합집합. 없으면 None."""
        rows_cl, _ = _cluster_intervals(
            [(nodes[i]["bbox"][1], nodes[i]["bbox"][3], i) for i in g])
        for row in rows_cl[:top_n]:
            segs = _row_segments(row, h_ref)
            if len(segs) >= 2:
                return set().union(*segs)
        return None

    def _y_cut_header_restated(glist: list[list[int]], h_ref: float) -> bool:
        """공유 헤더 방어: 영역 상단에 '문자 다열 헤더'가 존재하는데
        아래 블록들이 자체 문자 다열 행 없이 그 헤더에 의존(공유)하면
        단일 표의 섹션 여백이므로 수평 절단을 기각한다 (10-K류).
        영역 상단 헤더가 숫자(연도) 등으로 문자 다열이 아니면 검사
        비적용 — 이질 스택은 헤더가 재진술되지 않는 것이 정상이므로
        전칭 재진술을 요구하지 않는다."""
        ordered = sorted(glist, key=lambda g: min(
            nodes[i]["bbox"][1] for i in g))
        region_header = _top_header_row(
            [i for g in ordered for i in g], h_ref)
        if region_header is None:
            return True
        for blk in ordered[1:]:
            if _top_header_row(blk, h_ref, top_n=3) is None:
                return False
        return True

    _PERP = {"y": "x", "x": "y"}
    final_groups: list[list[int]] = []
    queue: list[tuple[list[int], tuple[str, ...], int]] = [
        (list(range(len(nodes))), ("y", "x"), 0)]
    while queue:
        cn, axes, depth = queue.pop()
        if depth >= max_depth or len(cn) < _MIN_COMPONENT_NODES:
            final_groups.append(cn)
            continue
        fired = scan(cn, axes)
        if not fired:
            final_groups.append(cn)
            continue
        groups: dict[tuple, list[int]] = defaultdict(list)
        for i in cn:
            sig = []
            for axis, lo, hi in fired:
                c = centers[i][1] if axis == "y" else centers[i][0]
                sig.append(c > (lo + hi) / 2)
            groups[tuple(sig)].append(i)
        if len(groups) == 1:
            final_groups.append(cn)
            continue
        # 표답지 않은 조각(제목·각주·파편)은 절단을 막는 대신 가장 가까운
        # 이웃 블록에 병합한다 — 옳은 절단을 파편 하나가 무효화하지 않도록.
        # strict_gate=True면 v3 방식(하나라도 실패 시 절단 전체 반려).
        # (크기 조건부 완화는 2026-09-10 실측 기각: 소형 스트립 패턴이
        #  진짜 스택과 단일 표에 공유되어 held-out 오판을 되사온다.)
        glist = list(groups.values())
        if strict_gate and "block_gate" not in ablate and not all(
                _block_ok(g) for g in glist):
            final_groups.append(cn)
            continue
        # 수평 절단의 헤더 재진술 검증 (fired가 전부 y축일 때)
        if strict_gate and fired and all(a == "y" for a, _, _ in fired):
            h_ref = statistics.median(
                nodes[i]["bbox"][3] - nodes[i]["bbox"][1] for i in cn)
            if "shared_hdr" not in ablate and not _y_cut_header_restated(glist, h_ref):
                final_groups.append(cn)
                continue
        def _center(g):
            return (sum((nodes[i]["bbox"][0] + nodes[i]["bbox"][2]) / 2
                        for i in g) / len(g),
                    sum((nodes[i]["bbox"][1] + nodes[i]["bbox"][3]) / 2
                        for i in g) / len(g))
        changed = True
        while changed and len(glist) > 1:
            changed = False
            for gi_, g in enumerate(glist):
                if _block_ok(g):
                    continue
                cx, cy = _center(g)
                near = min((j for j in range(len(glist)) if j != gi_),
                           key=lambda j: (abs(_center(glist[j])[0] - cx)
                                          + abs(_center(glist[j])[1] - cy)))
                glist[near] = glist[near] + g
                del glist[gi_]
                changed = True
                break
        if len(glist) == 1:
            final_groups.append(cn)
            continue
        child_axes = tuple({_PERP[a] for a, _, _ in fired})
        for g in glist:
            queue.append((g, child_axes, depth + 1))
    if len(final_groups) == 1:
        return [list(bbox)]
    return [[min(nodes[i]["bbox"][0] for i in g),
             min(nodes[i]["bbox"][1] for i in g),
             max(nodes[i]["bbox"][2] for i in g),
             max(nodes[i]["bbox"][3] for i in g)] for g in final_groups]

def merge_detect(
    nodes: list[dict],
    edges: list[dict],
    drawing_rects: Optional[list[list[float]]],
    bbox: list[float],
    base_threshold: float = 0.55,
    structure: Optional[dict] = None,
    *, grid_signals: Optional[dict] = None,
) -> dict[str, Any]:
    """Region-level merge detection using ALL available materials.

    - 세로/2D: node/edge material (_region_band_split) — node가 열 붕괴 없이
      세밀.
    - 가로/이형: grid material (structure의 extract/cells) — node로는 열
      클러스터가 붕괴해 미검출되는 것을 격자가 잡는다. structure 미제공 시
      (셀 복원 前) node만 사용.

    Returns {merged, direction, n_blocks, source}.
    grid_signals, when supplied, receives actual grid results for an immediate
    grid_split call on the same unchanged structure (including empty results).
    """
    # node 재료: 세로 경계
    sub = _region_band_split(
        nodes, edges, drawing_rects, bbox,
        base_threshold=base_threshold, max_depth=1, strict_gate=True)
    node_merged = len(sub) > 1

    grid_h = grid_v = False
    if structure is not None:
        horizontal = grid_hsplit_repeated(structure["extract"])
        vertical = grid_vsplit_heteromorphic(structure["extract"])
        grid_h, grid_v = bool(horizontal), bool(vertical)
        if grid_signals is not None:
            grid_signals.update(horizontal=horizontal, vertical=vertical)

    if not (node_merged or grid_h or grid_v):
        return {"merged": False, "direction": None, "n_blocks": 1,
                "source": None}

    if node_merged:
        xs = sorted((b[0] + b[2]) / 2 for b in sub)
        ys = sorted((b[1] + b[3]) / 2 for b in sub)
        sx, sy = xs[-1] - xs[0], ys[-1] - ys[0]
        direction = ("가로" if sx > sy * 1.5 else
                     "세로" if sy > sx * 1.5 else "2d")
        n = len(sub)
        source = "node"
        # 격자 가로가 추가로 발화하면 2D로 승격
        if grid_h and direction == "세로":
            direction, source = "2d", "node+grid"
    elif grid_h:
        direction, n, source = "가로", 2, "grid"
    else:  # grid_v
        direction, n, source = "세로", 2, "grid"
    return {"merged": True, "direction": direction, "n_blocks": n,
            "source": source}

def region_split_v2(
    nodes: list[dict],
    edges: list[dict],
    drawing_rects: Optional[list[list[float]]],
    bbox: list[float],
    base_threshold: float = 0.55,
    structure: Optional[dict] = None,
) -> dict[str, Any]:
    """merge_detect -> split composition.

    structure(격자) 제공 시 재료-통합 경로: detection·split 모두 node+격자를
    사용(grid_split). 미제공 시 node-only(호환).
    Returns {"regions": [bbox...], "detection": merge_detect result}.
    """
    grid_signals = {}
    detection = merge_detect(nodes, edges, drawing_rects, bbox,
                             base_threshold=base_threshold, structure=structure,
                             grid_signals=grid_signals)
    if not detection["merged"]:
        return {"regions": [list(bbox)], "detection": detection}
    if structure is not None:
        subs = grid_split(structure, horizontal=True,
                          nodes=nodes, edges=edges, drawing_rects=drawing_rects,
                          grid_signals=grid_signals)
        return {"regions": [s["bbox"] for s in subs], "detection": detection}
    regions = _region_band_split(
        nodes, edges, drawing_rects, bbox,
        base_threshold=base_threshold, strict_gate=True)
    return {"regions": regions, "detection": detection}

def _cell_type(text: str) -> str:
    compact = re.sub(r"\s", "", text or "")
    if compact and all(ch in "0123456789.%,()$-" for ch in compact):
        return "N"
    return "A" if re.search("[A-Za-z]", compact) else "."

def _row_alpha_tokens(row: list) -> set:
    out: set = set()
    for c in row:
        for w in re.findall(r"[a-zA-Z가-힣]{2,}", (c or "").lower()):
            out.add(w)
    return out

def grid_vsplit_heteromorphic(extract: list, max_lead_rank: int = 3) -> list[int]:
    """세로 이형 분할 — 격자에서 '문자-우세 헤더 행'이 재출현하는 위치를
    표 경계로 반환(0-기반 행 인덱스; 그 행부터 새 표). 없으면 [].

    - 헤더 후보 행 = 비어있지 않은 셀 중 문자형(A) ≥2 이고 A ≥ 숫자형(N).
    - 선두 헤더와 alpha 토큰 Jaccard ≥ 0.4 (반복/유사 가족) 또는, 선두
      헤더 토큰의 절반 이상 포함(부분 재출현) → 경계.
    - 첫 헤더 이후 최소 3행 간격을 둬 인접 헤더 행 연쇄를 하나로 축약.
    - 상단-헤더 가드(max_lead_rank): 선두 헤더 후보가 비어있지 않은 행 기준
      상위 max_lead_rank행 안에 없으면 전면 기각. 진짜 이형 스택의 선두
      헤더는 표 상단에 있다 — 첫 후보가 본문 깊숙이서야 나타나면 그것은
      헤더가 아니라 라벨-값 본문의 반복 필드 가족이며("Data as of:" 류,
      CA2029 52×5 오검: 첫 후보가 20번째 행), 재출현 판정의 기준 자체가
      무효다.
    """
    if not extract:
        return []
    header_rows = []
    nonempty_rank = -1
    lead_rank = None
    for ri, row in enumerate(extract):
        filled = [(c or "").strip() for c in row if (c or "").strip()]
        if not filled:
            continue
        nonempty_rank += 1
        na = sum(1 for c in filled if _cell_type(c) == "A")
        nn = sum(1 for c in filled if _cell_type(c) == "N")
        if na >= 2 and na >= nn:
            if lead_rank is None:
                lead_rank = nonempty_rank
            header_rows.append((ri, _row_alpha_tokens(row)))
    if len(header_rows) < 2:
        return []
    if lead_rank is None or lead_rank >= max_lead_rank:
        return []
    # 데이터-텍스트 표 방어: 숫자-우세 본문 행이 절반 미만이면 텍스트 목록
    # (성분표·자회사 목록 등)이므로 헤더 재출현 판정을 적용하지 않는다.
    numeric_rows = 0
    body_rows = 0
    for row in extract:
        filled = [(c or "").strip() for c in row if (c or "").strip()]
        if not filled:
            continue
        body_rows += 1
        nn = sum(1 for c in filled if _cell_type(c) == "N")
        if nn >= max(2, len(filled) // 2):
            numeric_rows += 1
    if body_rows == 0 or numeric_rows / body_rows < 0.5:
        return []
    lead = header_rows[0][1]
    if len(lead) < 2:
        return []
    cuts = []
    for ri, toks in header_rows[1:]:
        if len(toks) < 2:
            continue
        jac = len(toks & lead) / len(toks | lead) if (toks | lead) else 0.0
        contain = len(toks & lead) / len(lead) if lead else 0.0
        if jac >= 0.4 or contain >= 0.5:
            if not cuts or ri - cuts[-1] >= 3:
                cuts.append(ri)
    # 각 구간 최소 3행 보장
    bounds = [0, *cuts, len(extract)]
    if any(b - a < 3 for a, b in zip(bounds, bounds[1:])):
        return []
    return cuts

def grid_hsplit_repeated(extract: list, guard_shared_title: bool = True):
    """가로 반복 헤더 분할(V5-H, 검토 대상) — 선두 3행 중 한 행이 p-셀
    패턴의 정확 k회 반복(k*p=cols, p>=2, 문자 셀 포함)이면 (p, k) 반환.

    guard_shared_title: 회색지대 방어 — seed 바로 위 행에 그룹별 서로 다른
    상위 제목이 있으면(blackrock류 '상이 상위헤더 + 동일 하위헤더') 억제.
    단 상위 행이 없거나 모든 그룹이 동일 제목이면 통과.
    """
    if not extract:
        return None
    cols = max((len(r) for r in extract), default=0)
    if cols < 4:
        return None
    for seed in range(min(3, len(extract))):
        row = [(c or "").strip().casefold() for c in extract[seed]]
        if len(row) != cols:
            continue
        for p in range(2, cols // 2 + 1):
            if cols % p or (cols // p) < 2:
                continue
            k = cols // p
            pattern = row[:p]
            if not all(row[i * p:(i + 1) * p] == pattern for i in range(1, k)):
                continue
            nonempty = [c for c in pattern if c]
            if not nonempty or not any(
                    any(ch.isalpha() for ch in c) for c in nonempty):
                continue
            if guard_shared_title and seed > 0:
                above = [(c or "").strip().casefold() for c in extract[seed - 1]]
                if len(above) == cols:
                    groups = set()
                    for gi in range(k):
                        seg = " ".join(c for c in above[gi * p:(gi + 1) * p] if c)
                        if seg:
                            groups.add(seg)
                    if len(groups) >= 2:
                        continue  # 그룹별 상이 상위 제목 → 회색지대, 억제
            return p, k
    return None

def _grid_header_rows(extract: list) -> list[int]:
    """문자-우세 헤더 후보 행 인덱스 (비어있지 않은 셀 중 문자형>=2, 문자>=숫자)."""
    out = []
    for ri, row in enumerate(extract):
        filled = [(c or "").strip() for c in row if (c or "").strip()]
        if not filled:
            continue
        na = sum(1 for c in filled if _cell_type(c) == "A")
        nn = sum(1 for c in filled if _cell_type(c) == "N")
        if na >= 2 and na >= nn:
            out.append(ri)
    return out

def _grid_vcuts(extract: list) -> list[int]:
    """세로 경계 행 = 헤더 행 재출현(선두 헤더와 Jaccard>=0.4 또는 포함>=0.5).
    v13의 반복가족/밀도/연도 anchor를 격자 위 단일 규칙으로 대체.
    숫자-본문 가드: 숫자-우세 본문 행이 절반 미만이면 텍스트 목록 → 미분할."""
    hdr = _grid_header_rows(extract)
    if len(hdr) < 2:
        return []
    body = numeric = 0
    for row in extract:
        filled = [(c or "").strip() for c in row if (c or "").strip()]
        if not filled:
            continue
        body += 1
        if sum(1 for c in filled if _cell_type(c) == "N") >= max(2, len(filled) // 2):
            numeric += 1
    if body == 0 or numeric / body < 0.5:
        return []
    lead = _row_alpha_tokens(extract[hdr[0]])
    if len(lead) < 2:
        return []
    cuts = []
    for ri in hdr[1:]:
        toks = _row_alpha_tokens(extract[ri])
        if len(toks) < 2:
            continue
        jac = len(toks & lead) / len(toks | lead) if (toks | lead) else 0.0
        contain = len(toks & lead) / len(lead) if lead else 0.0
        if (jac >= 0.4 or contain >= 0.5) and (not cuts or ri - cuts[-1] >= 3):
            cuts.append(ri)
    bounds = [0, *cuts, len(extract)]
    if any(b - a < 3 for a, b in zip(bounds, bounds[1:])):
        return []
    return cuts

def _cells_bbox(cells_slice) -> Optional[list]:
    xs = [c for r in cells_slice for c in r if c]
    if not xs:
        return None
    return [min(c[0] for c in xs), min(c[1] for c in xs),
            max(c[2] for c in xs), max(c[3] for c in xs)]

def _grid_vsplit_heteromorphic_if(extract: list) -> list[int]:
    """grid_vsplit_heteromorphic 래퍼(내부 재사용). 이름만 분리."""
    return grid_vsplit_heteromorphic(extract)

def grid_split(structure: dict, horizontal: bool = True,
               nodes: Optional[list] = None, edges: Optional[list] = None,
               drawing_rects: Optional[list] = None,
               *, grid_signals: Optional[dict] = None) -> list[dict]:
    """통합 분할 (refine 위치, 재료-올바름):
    - 세로: **원재료 node/edge** (_region_band_split) — node가 열 붕괴 없이
      더 세밀. nodes/edges 미제공 시에만 격자 헤더-재출현(_grid_vcuts)로 대체.
    - 가로: **격자 재료** (grid_hsplit_repeated) — node로는 열 클러스터 붕괴.
    반환: [{"bbox", "rows":(r0,r1), "cols":(c0,c1)}].
    """
    # Signals belong to this unchanged whole grid. Node search has a different
    # depth from merge_detect; child blocks have different text. Recompute both.
    extract = structure["extract"]
    cells = structure["cells"]
    ncols = max((len(r) for r in extract), default=0)

    # 격자 행의 y 중심 (없는 행은 None → 인접값 보간으로 배속)
    row_cy = [
        (sum((c[1] + c[3]) / 2 for c in row if c) / max(sum(1 for c in row if c), 1))
        if any(row) else None
        for row in cells]

    def _map_node_boxes_to_cuts(boxes: list) -> list[int]:
        """각 격자 행을 세로 정렬 node 자식에 배속(행 중심이 가장 가까운
        자식), 배속이 바뀌는 지점을 절단 행으로 반환. 격자가 경계 구간을
        gap 없이 연속 행으로 복원해도(node 경계가 행 '안'에 떨어져도) 견고."""
        sb = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)
        ymid = [(b[1] + b[3]) / 2 for b in sb]

        def child_of(cy: float) -> int:
            # 자식 y-범위에 포함되면 그 자식, 아니면 중심이 가장 가까운 자식
            for ci, b in enumerate(sb):
                if b[1] - 2 <= cy <= b[3] + 2:
                    return ci
            return min(range(len(sb)), key=lambda ci: abs(ymid[ci] - cy))

        # 유효 행에 배속 부여 (None 행은 직전 배속 상속)
        assign = []
        last = 0
        for cy in row_cy:
            if cy is None:
                assign.append(last)
            else:
                last = child_of(cy)
                assign.append(last)
        cuts = []
        for ri in range(1, len(assign)):
            if assign[ri] != assign[ri - 1] and (not cuts or ri - cuts[-1] >= 1):
                cuts.append(ri)
        return cuts

    # 1) 세로 분할 — node 경계(원재료) ∪ 격자 이형(헤더 재출현)
    vcuts: list[int] = []
    if nodes is not None and edges is not None:
        boxes = _region_band_split(nodes, edges, drawing_rects or [],
                                   structure["bbox"], strict_gate=True)
        if len(boxes) > 1:
            vcuts.extend(_map_node_boxes_to_cuts(boxes))
    # 격자 이형 경계는 node 유무와 무관하게 합집합(검토 지적 2 수정):
    # merge_detect가 격자로 잡은 이형 병합이 실제 분할에 도달하도록.
    vertical = (grid_signals["vertical"] if grid_signals is not None
                else _grid_vsplit_heteromorphic_if(extract))
    for ri in vertical:
        if ri not in vcuts:
            vcuts.append(ri)
    if not vcuts and not (nodes is not None and edges is not None):
        vcuts = _grid_vcuts(extract)
    vbounds = [0, *sorted(set(vcuts)), len(extract)]
    vblocks = [(a, b) for a, b in zip(vbounds, vbounds[1:]) if b > a]
    out = []
    for r0, r1 in vblocks:
        sub = extract[r0:r1]
        # 2) 가로 분할 (반복 열-그룹, 회색지대 가드)
        if horizontal and grid_signals is not None and r0 == 0 and r1 == len(extract):
            hr = grid_signals["horizontal"]
        else:
            hr = grid_hsplit_repeated(sub) if horizontal else None
        if hr:
            p, k = hr
            for gi in range(k):
                c0, c1 = gi * p, min((gi + 1) * p, ncols)
                bb = _cells_bbox([row[c0:c1] for row in cells[r0:r1]])
                if bb:
                    out.append({"bbox": bb, "rows": (r0, r1), "cols": (c0, c1)})
        else:
            bb = _cells_bbox(cells[r0:r1])
            if bb:
                out.append({"bbox": bb, "rows": (r0, r1), "cols": (0, ncols)})
    if not out:
        bb = _cells_bbox(cells)
        return [{"bbox": bb or structure["bbox"], "rows": (0, len(extract)),
                 "cols": (0, ncols)}]
    return out
