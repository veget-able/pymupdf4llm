"""V7 header-guided region split: frozen VG v13 algorithm (2026-09-10).

Imported dependency closure only. No GT, cached graphs, V5-H, or other VG
region detectors are part of this module. Independently measured as the
region-only full-503 candidate before promotion.
"""
from __future__ import annotations
import re
import statistics
from collections import defaultdict
from typing import Optional

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
) -> list[list[float]]:
    drawing_rects = drawing_rects or []
    accepted = [
        (int(e["source"]), int(e["target"]), float(e["probability"]))
        for e in edges if float(e["probability"]) > base_threshold
    ]
    centers = [((n["bbox"][0] + n["bbox"][2]) / 2,
                (n["bbox"][1] + n["bbox"][3]) / 2) for n in nodes]

    def continuing_label_value_rows(cn):
        # A repeated label in one field is not a repeated table header. When
        # the same two fields continue through a candidate gap with an ordered
        # integer value column, spatial anchors alone cannot establish a new
        # table. Independent header/border evidence remains eligible below.
        cols, _ = _cluster_intervals([
            (nodes[i]["bbox"][0], nodes[i]["bbox"][2], i) for i in cn
        ])
        if len(cols) != 2:
            return False
        labels, values = cols
        if not all(any(c.isalpha() for c in (nodes[i].get("text") or ""))
                   for i in labels):
            return False
        ordered = sorted(values, key=lambda i: centers[i][1])
        texts = [(nodes[i].get("text") or "").strip() for i in ordered]
        if len(texts) < 2 or not all(text.isdecimal() for text in texts):
            return False
        numbers = [int(text) for text in texts]
        return (numbers[0] < numbers[-1]
                and all(a <= b for a, b in zip(numbers, numbers[1:])))

    def scan(cn: list[int], axes: tuple[str, ...]):
        fired = []
        cn_set = set(cn)
        continuous_labels = continuing_label_value_rows(cn) if "y" in axes else False
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
                    family = any(
                        _jaccard(ts, other) >= 0.5
                        for cj_, other in enumerate(cluster_tokens)
                        if cj_ != ci_ and len(other) >= 3)
                    density = (len(ts) >= 4 and ci_ > 0
                               and letters[ci_ - 1] <= 1)
                    if family or density:
                        anchors.append(ci_)
                if anchors is not None:
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
                big = ([k for k, c in enumerate(cands)
                        if rhythm_ok and c[2] >= 2.0]
                       if "p2" in y_rules else [])
                if 1 <= len(big) <= 2:
                    rest = [c[0:2] for k, c in enumerate(cands) if k not in big]
                    rest_max = max((hi - lo for lo, hi in
                                    ((cands[k][0], cands[k][1]) for k in
                                     range(len(cands)) if k not in big)),
                                   default=0.0)
                    big_min = min(cands[k][1] - cands[k][0] for k in big)
                    if rest_max <= 0 or big_min >= 1.5 * rest_max:
                        for k in big:
                            spatial_ok.setdefault(k, "normal")
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
                if not veto_pass(band_lo, band_hi, 0.5):
                    continue
                if axis == "y":
                    spatial = k in spatial_ok
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
                if axis == "y" and spatial and not (header_fire or border_fire or period_fire):
                    if continuous_labels:
                        spatial = False
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
        if strict_gate and not all(_block_ok(g) for g in glist):
            final_groups.append(cn)
            continue
        # 수평 절단의 헤더 재진술 검증 (fired가 전부 y축일 때)
        if strict_gate and fired and all(a == "y" for a, _, _ in fired):
            h_ref = statistics.median(
                nodes[i]["bbox"][3] - nodes[i]["bbox"][1] for i in cn)
            if not _y_cut_header_restated(glist, h_ref):
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
# ---------------------------------------------------------------------------
# Refactored architecture: merge_detect -> split
# ---------------------------------------------------------------------------
