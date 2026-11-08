"""Cell-only partition proposals; no detector graph or ownership policy."""
from __future__ import annotations

import re

import statistics

from collections import Counter, defaultdict

from typing import Any, Optional

from pymupdf4llm._table_pipeline.vg_rule_primitives import (
    _cluster_intervals, _contain, _jaccard, _tokens,
)

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
            # A repeated heading supplies a boundary proposal, not proof of
            # independently populated panels. Each proposed child must retain
            # content after the heading that generated the proposal. This
            # consumes only the existing cell grid, never layout scores/nodes.
            if not all(any(any(str(value or "").strip() for value in body[gi*p:(gi+1)*p])
                           for body in extract[seed+1:]) for gi in range(k)):
                continue
            return p, k
    return None




from .placement_material import _cells_bbox
