"""Shared current-grid/source inputs; no row or span policy installed."""
from collections import Counter
from contextlib import contextmanager
from pymupdf import table, _table_refine as refine, _table_spans as spans, _table_geometry as graphics

def graphic_segments(paths,context,spans):
    # Reuse native stroke and filled-quadrilateral conversion. Rectangles need
    # their own sides; the existing connector helper deliberately omits them.
    result=list(context._connector_segments(paths,orthogonal=True))
    for p in paths:
        for item in p['items']:
            if item[0]!='re':continue
            r=spans.pymupdf.Rect(item[1]);r.normalize()
            if 's' in p['type']:
                result.extend([((r.x0,r.y0),(r.x0,r.y1)),((r.x1,r.y0),(r.x1,r.y1)),((r.x0,r.y0),(r.x1,r.y0)),((r.x0,r.y1),(r.x1,r.y1))])
            elif r.width<2.0 and r.height>10.0:result.append((((r.x0+r.x1)/2,r.y0),((r.x0+r.x1)/2,r.y1)))
            elif r.height<2.0 and r.width>10.0:result.append(((r.x0,(r.y0+r.y1)/2),(r.x1,(r.y0+r.y1)/2)))
    return result


class StructuralInputs:
    def __init__(self):
        self.materials={};self.pages={};self.phrases={};self.graphic_cache={};self.events=[]
        self.stats=Counter();self.boundaries={}

    @staticmethod
    def frame(page):return (id(page),page.rotation,tuple(page.rect))

    def accept_spans(self,page,blocks):
        self.pages[id(page)]=page;target=self.materials.setdefault(self.frame(page),{})
        self.stats['span_producer_deliveries']+=1
        for block in blocks:
            for line in block.get('lines',[]):
                for span in line.get('spans',[]):
                    value=span.get('text',''.join(c.get('c','') for c in span.get('chars',[])))
                    if value.strip():
                        item=dict(bbox=list(span['bbox']),text=value)
                        target[tuple(item['bbox']),value]=item

    def segments(self,page):
        paths=table._cached_table_drawings(page);key=(id(paths),page.rotation,tuple(page.rect))
        if key not in self.graphic_cache:
            # Keep the producer alive: an address alone can be reused by the
            # next page after the native drawing scope releases its list.
            self.graphic_cache[key]=(paths,graphic_segments(paths,graphics,spans))
            self.stats['graphic_segment_productions']+=1
        source,result=self.graphic_cache[key]
        assert source is paths
        return result

    @contextmanager
    def boundary_scope(self):
        previous=self.boundaries,self.graphic_cache
        self.boundaries={};self.graphic_cache={}
        try:yield
        finally:self.boundaries,self.graphic_cache=previous


    def refine_rows(self, page, cells, **kwargs):
        return refine.refine_grid_rows(page, cells, **kwargs)

    def parent_merge(self, reject, reason, *args):
        return reject, reason

    def structural_boundary(self, service, header, page, cells, *, purpose='structure', table_bbox=None):
        return table._refine_body_start_row(page, cells)
