"""VG table_region_postprocess 공유 순수 helper (사본 공용화, 2026-09-12).

두 프로즌 사본(material_split_rules, v7_region_rules)에서 AST 동일이 확인된
_tokens/_jaccard/_contain/_cluster_intervals를 verbatim 추출했다. VG 라이브
원본 및 2026-09-10 스냅숏과도 AST 동일. 규칙 본체는 각 사본에 유지된다.
"""
from __future__ import annotations
import re
from typing import Optional


def _tokens(texts: list[Optional[str]]) -> set[str]:
    out: set[str] = set()
    for text in texts:
        for word in re.findall(r"[a-zA-Z가-힣]{2,}", (text or "").lower()):
            out.add(word)
    return out

def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0

def _contain(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a) if a else 0.0

def _cluster_intervals(intervals: list[tuple[float, float, int]]):
    clusters: list[list[int]] = []
    bounds: list[list[float]] = []
    for lo, hi, idx in sorted(intervals):
        if bounds and lo <= bounds[-1][1]:
            bounds[-1][1] = max(bounds[-1][1], hi)
            clusters[-1].append(idx)
        else:
            bounds.append([lo, hi])
            clusters.append([idx])
    return clusters, bounds


def x_iou(a, b):
    width = max(a[2], b[2]) - min(a[0], b[0])
    return max(0., min(a[2], b[2]) - max(a[0], b[0])) / width if width > 0 else 0.


def column_intervals(cells):
    """Tightest cell bounds per slot; preserve empty columns as None."""
    nc = max(map(len, cells), default=0)
    # Tightest cell per slot avoids treating a spanning heading as a column.
    columns = []
    for j in range(nc):
        choices = [row[j] for row in cells if row[j] is not None]
        if not choices:
            columns.append(None)
        else:
            c = min(choices, key=lambda c: c[2]-c[0])
            columns.append((c[0], c[2]))
    return columns

