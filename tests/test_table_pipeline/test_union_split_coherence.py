"""코히런스 억제 게이트의 순수 로직 단위 테스트 (모델 불필요).

should_suppress 를 가짜 부모/자식 entry로 호출. page._page_spans 를 우회하기 위해
텍스트 신호(첫행 토큰)는 각 자식 grid 셀에 직접 대응되는 fake span으로 주입.
"""
import sys
from pathlib import Path
from types import SimpleNamespace


import pymupdf  # noqa: E402
from pymupdf4llm._table_pipeline import union_split_coherence as G  # noqa: E402


class Rect(tuple):
    def __new__(cls, b):
        o = super().__new__(cls, b)
        return o
    @property
    def x0(self): return self[0]
    @property
    def y0(self): return self[1]
    @property
    def x1(self): return self[2]
    @property
    def y1(self): return self[3]


def entry(bbox, grid):
    e = SimpleNamespace()
    e_tuple = (Rect(bbox), grid)
    ns = SimpleNamespace(bbox=bbox, grid=grid)
    # entry[0], entry[1] 접근용 튜플 래퍼
    class E(tuple):
        bbox_provenance = {}
    obj = E((Rect(bbox), grid))
    return obj


def one_row_grid(x0, y0, x1, y1, ncols, words):
    """1행 ncols 격자 + 각 셀 중심에 단어 배치(fake span 생성용)."""
    w = (x1 - x0) / ncols
    cells, spans = [], []
    for j in range(ncols):
        cx0, cx1 = x0 + j * w, x0 + (j + 1) * w
        cells.append((cx0, y0, cx1, y1))
        if j < len(words):
            spans.append((pymupdf.Rect((cx0 + 2, y0 + 2, cx0 + 10, y1 - 2)), words[j]))
    return [cells], spans


def make_children(specs):
    """specs: [(y0, ncols, words)] -> children entries + 합친 fake spans."""
    kids, allspans = [], []
    for (y0, ncols, words) in specs:
        grid, spans = one_row_grid(24, y0, 588, y0 + 20, ncols, words)
        kids.append(entry([24, y0, 588, y0 + 20], grid))
        allspans.extend(spans)
    return kids, allspans


class FakeUnion:
    """union 헬퍼 stub — span_mult/2d-support는 로직 분기만 태움."""
    def __init__(self, span_mult=1.0, support=True):
        self._sm, self._sup = span_mult, support
    def _union_span_multiplicity(self, page, grid):
        return self._sm
    def _union_grid_has_2d_content_support(self, grid):
        return self._sup
    def _entry_with_provenance(self, e, **kw):
        return e


def run(children_specs, parent_bbox=(24, 100, 588, 460), parent_span=2.0,
        child_span=3.0, support=True):
    kids, spans = make_children(children_specs)
    parent = entry(list(parent_bbox), [[(24, 100, 588, 120)]])
    page = SimpleNamespace(number=0)
    # _page_spans 를 주입된 fake span으로 치환
    orig = G._page_spans
    G._page_spans = lambda _p: spans
    # span_mult: 부모/자식 구분 위해 grid 참조로 분기 (None = 결측)
    def sm(_p, grid):
        return parent_span if grid is parent[1] else child_span
    fu = SimpleNamespace(
        _union_span_multiplicity=sm,
        _union_grid_has_2d_content_support=lambda g: support,
        _entry_with_provenance=lambda e, **k: e)
    try:
        return G.should_suppress(parent, kids, page, fu)
    finally:
        G._page_spans = orig


def test_body_cols():
    assert G.body_cols([3, 3, 3]) == 3
    assert G.body_cols([2, 3, 3, 3]) == 3      # 좁은 헤더 + 균일 본문
    assert G.body_cols([3, 5, 4]) is None
    assert G.body_cols([5, 2, 2]) is None      # 상단이 더 넓음


DISTINCT = [["alpha", "beta", "gamma"], ["delta", "epsilon", "zeta"],
            ["eta", "theta", "iota"], ["kappa", "lambda", "mu"],
            ["nu", "xi", "omicron"]]


def test_suppress_coca68_like():
    # 좁은 헤더(2열) + 균일 본문(3열) ×5, 첫행 토큰 서로 다름 -> 억제
    specs = [(120, 2, ["year", "prior"])] + \
            [(180 + i * 50, 3, DISTINCT[i]) for i in range(5)]
    ok, reason = run(specs, parent_span=2.0, child_span=3.0)
    assert ok, reason


def test_protect_span_mult_missing():
    # span_mult 결측(None) -> 억제 안 함 (결측 != 측정0)
    specs = [(120 + i * 60, 3, DISTINCT[i]) for i in range(3)]
    ok, reason = run(specs, parent_span=None, child_span=1.0)
    assert not ok and "span-mult-missing" in reason, reason


def test_protect_repeated_header():
    # 균일 3열 ×3, 첫행 동일(반복헤더) -> Jaccard veto
    specs = [(120 + i * 60, 3, ["name", "class", "symbol"]) for i in range(3)]
    ok, reason = run(specs)
    assert not ok and "jaccard" in reason, reason


def test_protect_k_lt_3():
    specs = [(120, 3, ["a", "b", "c"]), (200, 3, ["d", "e", "f"])]
    ok, reason = run(specs)
    assert not ok and "k<3" in reason, reason


def test_protect_non_uniform():
    specs = [(120, 4, ["a"]), (200, 2, ["b"]), (280, 17, ["c"])]
    ok, reason = run(specs)
    assert not ok and "cols-not-uniform" in reason, reason


def test_protect_parent_under_segmented():
    # 부모 span_mult 크게 -> 부모가 열 뭉갬 -> 분할 정당
    specs = [(120 + i * 60, 3, DISTINCT[i]) for i in range(3)]
    ok, reason = run(specs, parent_span=5.0, child_span=1.0)
    assert not ok and "under-segmented" in reason, reason


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)

def test_span_quality_ceiling():
    specs = [(120 + i * 60, 3, DISTINCT[i]) for i in range(3)]
    ok, reason = run(specs, parent_span=14.0, child_span=24.0)
    assert not ok and "too-under-segmented" in reason


def test_low_cost_rejection_never_resolves_parent(monkeypatch):
    def forbidden(_parent):
        raise AssertionError("unnecessary TGIF")
    monkeypatch.setattr(G, "_concrete_parent_grid", forbidden)
    ok, reason = run([(120, 3, ["alpha"]), (180, 3, ["beta"])])
    assert not ok and reason == "k<3"


def test_parent_prediction_cached_and_inputs_preserved():
    from pymupdf4llm._table_pipeline.deferred_tgif import DeferredPrediction
    calls = []
    prediction = DeferredPrediction(
        lambda *a, **kw: (calls.append((a, kw)) or SimpleNamespace(h_lines=[], v_lines=[]), []),
        ("image", "boxes"), {"texts": ["alpha"]})
    args, kwargs = prediction.args, prediction.kwargs
    group = {"table_grid": prediction}
    concrete = [[(0, 0, 100, 100)]]
    def reader(page):
        assert page.layout_information[0] is group
        group["table_grid"].resolve()
        return [(None, concrete)]
    parent = (None, SimpleNamespace(group=group, original_reader=reader))
    assert G._concrete_parent_grid(parent) is concrete
    assert prediction.args is args and prediction.kwargs is kwargs
    assert G._concrete_parent_grid(parent) is concrete
    prediction.resolve()  # downstream consumer: no second inference
    assert len(calls) == 1


def test_span_extraction_shared_in_both_consumer_orders():
    from pymupdf import _table_union as union
    for rects_first in (False, True):
        class Page:
            calls = 0
            def get_text(self, fmt):
                self.calls += 1
                return {"blocks": [{"lines": [{"spans": [
                    {"bbox": [0, 0, 10, 10], "text": "  alpha  "},
                    {"bbox": [1, 1, 1, 1], "text": "empty rectangle"},
                    {"bbox": [0, 0, 10, 10], "text": "   "},
                ]}]}]}
        page = Page()
        if rects_first:
            union._union_text_span_rects(page)
        records = G._page_spans(page)
        rects = union._union_text_span_rects(page)
        assert len(records) == 2 and len(rects) == 1
        assert records[0][1] == "alpha"
        assert G._page_spans(page) is records
        assert page.calls == 1
