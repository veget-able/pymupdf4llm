"""Existing T15 structural consumer over shared native material."""
from collections import Counter,defaultdict
from pymupdf import table,_table_refine as refine,_table_spans as spans,_table_geometry as graphics
from pymupdf._table_geometry import _coverage
from . import line_geometry as band
from contextlib import contextmanager
from types import MethodType

def preserve_shared(cells, proposed, words, header_count, refine, spans, band, *, page=None):
    if proposed is cells or proposed==cells:return proposed,dict(anchors=[],reason='native_no_change')
    header_count=max(1,min(int(header_count),len(cells))) if cells else 0
    body=proposed[header_count:]
    if not body:return proposed,dict(anchors=[],reason='no_body')
    # Native output is a uniform body lattice; decline any other representation.
    live=[[c for c in row if c is not None] for row in body]
    if not all(live):return proposed,dict(anchors=[],reason='nonuniform_native_body')
    xbounds=[live[0][0][0],*[c[2] for c in live[0]]]
    if not all([(c[0],c[2]) for c in row]==[(c[0],c[2]) for c in live[0]] for row in live):
        return proposed,dict(anchors=[],reason='nonuniform_columns')
    edges=[live[0][0][1],*[row[0][3] for row in live]]
    candidates=[];min_cols=max(2,(len(live[0])+1)//2)
    for ri,row in enumerate(cells[header_count:],header_count):
        for c in row:
            if c is None:continue
            # Keep the existing rounded-two-decimal column contract. This
            # intervention does not change colspan or add new boundaries.
            columns=[i for i,target in enumerate(live[0]) if round(c[0],2)==round(target[0],2) and round(c[2],2)==round(target[2],2)]
            if len(columns)!=1:continue
            col=columns[0]
            if c[1] not in edges or c[3] not in edges:continue
            lo,hi=edges.index(c[1]),edges.index(c[3])
            if hi-lo<2:continue
            rect=refine.pymupdf.Rect(c)
            selected=spans._span_select_words_in_rect(words,rect,page=page)
            if not selected or any('\n' in str(w[4]) for _,w in selected):continue
            # Existing rowspan geometry helper: one visual line, within column,
            # vertically centered over the original full cell, no new constants.
            value_words=[w for _,w in selected]
            if 0 not in band._rowspan_slots(rect,[(c[0],c[2])],value_words,[]):continue
            neighbor_evidence=[];valid=True
            for bi in range(lo,hi):
                row_rect=refine.pymupdf.Rect(xbounds[0],edges[bi],xbounds[-1],edges[bi+1])
                members=spans._span_select_words_in_rect(words,row_rect,page=page)
                observed=set()
                for wi,w in members:
                    x=(w[0]+w[2])/2
                    for ci,target in enumerate(live[bi]):
                        if ci!=col and target[0]<=x<=target[2]:observed.add(ci)
                if len(observed)<min_cols:valid=False;break
                neighbor_evidence.append(dict(body_row=bi,columns=sorted(observed)))
            if valid:
                candidates.append(dict(source_row=ri,column=col,body_rows=(lo,hi),cell=c,
                    source_word_indices=[i for i,_ in selected],neighbors=neighbor_evidence))
    # Overlapping source candidates do not gain precedence from traversal order.
    accepted=[]
    for i,candidate in enumerate(candidates):
        lo,hi=candidate['body_rows'];col=candidate['column']
        overlap=any(j!=i and other['column']==col and lo<other['body_rows'][1] and other['body_rows'][0]<hi for j,other in enumerate(candidates))
        if not overlap:accepted.append(candidate)
    if not accepted:return proposed,dict(anchors=[],reason='no_supported_shared_value')
    output=[list(row) for row in proposed]
    for candidate in accepted:
        lo,hi=candidate['body_rows'];col=candidate['column']
        output[header_count+lo][col]=candidate['cell']
        for bi in range(lo+1,hi):output[header_count+bi][col]=None
    return output,dict(anchors=[dict(source_row=c['source_row'],column=c['column'],body_rows=list(c['body_rows']),
        rectangle=list(c['cell']),source_word_indices=c['source_word_indices'],neighbors=c['neighbors']) for c in accepted],
        reason='native_records_with_shared_source_anchor')


def remove_empty_header_rows(cells,proposed,words,depth,spans,segments):
    h=max(1,min(int(depth),len(cells))) if cells else 0
    empty=[]
    for ri in range(1,h-1):
        row=[c for c in cells[ri] if c is not None]
        if not row or len({(c[1],c[3]) for c in row})!=1:continue
        y0,y1=row[0][1],row[0][3];x0=min(c[0] for c in row);x1=max(c[2] for c in row)
        band=spans.pymupdf.Rect(x0,y0,x1,y1)
        if spans._span_select_words_in_rect(words,band):continue
        # A spanning original cell owns the interval; do not delete its row.
        if any(c is not None and c[1]<y1 and c[3]>y0 for j,r in enumerate(cells) if j!=ri for c in r):continue
        neighbors=[]
        for j in [ri-1,ri+1]:
            box=spans._span_rect_union([spans.pymupdf.Rect(c) for c in cells[j] if c is not None])
            neighbors.append(bool(spans._span_select_words_in_rect(words,box)))
        if not all(neighbors):continue
        if any(abs(a[1]-b[1])<1.0 and y0<(a[1]+b[1])/2<y1 and max(a[0],b[0])>x0 and min(a[0],b[0])<x1 for a,b in segments):continue
        empty.append(ri)
    if not empty:return proposed,dict(removed=[])
    # The original protected prefix is unchanged by native row segmentation.
    assert proposed[:h]==cells[:h]
    return [r for i,r in enumerate(proposed) if i not in empty],dict(removed=empty)


def refine_rows(self,page,cells,**kwargs):
    proposed=refine.refine_grid_rows(page,cells,**kwargs)
    words=refine._refine_page_words(page)
    native,shared=preserve_shared(cells,proposed,words,kwargs['header_row_count'],refine,spans,band,page=page)
    result,empty=remove_empty_header_rows(cells,native,words,kwargs['header_row_count'],spans,self.segments(page))
    assert result==[r for i,r in enumerate(native) if i not in empty['removed']]
    self.events.append(dict(kind='ported_rows',shared=shared,empty=empty))
    return result


def install(runtime):
                runtime.structural_policy.refine_rows = MethodType(refine_rows, runtime.structural_policy)
                runtime.refine_rows = runtime.structural_policy.refine_rows
