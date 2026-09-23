"""Recover one omitted spanning band proved by the existing finder rulings."""
from types import SimpleNamespace
from pymupdf import Rect
from pymupdf._table_spans import SpanCell, _span_claim_text_in_rect, _span_select_words_in_rect
from pymupdf4llm.helpers.table_html.reconstruct import _table_grid_matrices
from pymupdf4llm._table_pipeline.grid_ownership import _updated, _intersects


def recover(tab, nodes, words, edges, obstacles):
    edges = [e for e in edges if e.get('ruling_origin') in ('vector','raster')]
    if words is None or not edges or not tab.placements:
        return None
    first = [c for c in tab.placements[0] if c.bbox is not None]
    if len(first) < 2:
        return None
    x0, x1 = min(c.bbox[0] for c in first), max(c.bbox[2] for c in first)
    bottom = min(c.bbox[1] for c in first)
    if any(abs(c.bbox[1] - bottom) > 1 for c in first):
        return None
    # Both rules must have the same actual width as the body. The nearest
    # preceding rule defines a single band; no bbox whitespace is filled.
    horizontal = [e for e in edges if e['orientation'] == 'h'
                  and abs(e['x0']-x0) <= 3 and abs(e['x1']-x1) <= 3]
    if not any(abs(e['top'] - bottom) <= 1 for e in horizontal):
        return None
    tops = [e['top'] for e in horizontal if e['top'] < bottom - 1]
    if not tops:
        return None
    top = max(tops)
    box = (x0,top,x1,bottom)
    if any(_intersects(box, other.bbox) for other in obstacles):
        return None
    # A rule within the band means a multi-cell row, outside this operation.
    if any(e['orientation']=='v' and x0+1 < e['x0'] < x1-1
           and min(e['bottom'],bottom)-max(e['top'],top) > 1 for e in edges):
        return None
    selected = _span_select_words_in_rect(words, Rect(box))
    if not selected or any(not Rect(box).contains(Rect(w[:4])) for _,w in selected):
        return None
    # Require one physical line, crossing a body column boundary, and actual
    # retained parent nodes in that line. No title/header semantic test here.
    if max(w[1] for _,w in selected) >= min(w[3] for _,w in selected):
        return None
    lo,hi=min(w[0] for _,w in selected),max(w[2] for _,w in selected)
    if not any(lo < c.bbox[2] < hi for c in first[:-1]):
        return None
    ns=[n for n in nodes if n.text.strip() and Rect(box).contains(Rect(n.bbox))]
    if not ns or any(not any(Rect(n.bbox).contains(Rect(w[:4])) or
                             n.bbox[0] <= (w[0]+w[2])/2 <= n.bbox[2]
                             and n.bbox[1] <= (w[1]+w[3])/2 <= n.bbox[3] for n in ns)
                     for _,w in selected):
        return None
    refs=[]
    text=_span_claim_text_in_rect(SimpleNamespace(_span_vertical_lines_cache=[]),Rect(box),words,set(),sources=refs)
    _,nc,_,_=_table_grid_matrices(tab,retain=True)
    cell=SpanCell(box,text,nc,1,'td',sources=refs)
    child=_updated(tab,[[cell]]+list(tab.placements),1,{n.index for n in ns})
    child.bbox_provenance.update(bbox_operation='ruled_leading_row',recovery_steps=list(tab.bbox_provenance.get('recovery_steps',[]))+['ruled_leading_row'])
    return child
