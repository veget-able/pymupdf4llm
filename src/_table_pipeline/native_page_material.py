"""Page-owned native facts. No layout classes, graph scores or group ownership."""
from dataclasses import dataclass
import numpy as np
import pymupdf
from pymupdf import table
from pymupdf._table_refine import _refine_page_words, _refine_rawdict_spans, _refine_word_candidates
from pymupdf._table_spans import CellSource


@dataclass(frozen=True)
class NativeSource:
    index: int
    bbox: tuple
    text: str
    scope: tuple
    sources: tuple
    line_scope: tuple = ()
    source_order: int = 0


def page_frame(page):
    return (id(page.parent), page.number, page.xref, tuple(page.rect),
            tuple(page.cropbox), tuple(page.mediabox), page.rotation,
            tuple(page.get_contents()))




class PageMaterial:
    def __init__(self, page, runtime):
        self.page, self.runtime = page, runtime
        self.frame = page_frame(page)
        self._words = self._sources = self._lines = self._joined_edges = None
        self._record_epoch = None
        self._span_material_token = None
        self.characters = tuple(dict(c) for c in table.CHARS)
        self.edges = tuple(runtime.ruling_materials.get(id(page), ()))

    @property
    def words(self):
        if self._words is None:
            self._words = _refine_page_words(self.page)
        elif getattr(self.page, '_refine_words_cache', None) is not self._words:
            raise RuntimeError('Native word producer changed during table policy scope')
        return self._words

    @property
    def sources(self):
        words = self.words
        records=getattr(self.page,'_table_control_glyphs',())
        epoch=(id(records),len(records))
        if self._sources is None or epoch != self._record_epoch:
            self._record_epoch=epoch
            line_material=getattr(self.page,'_refine_word_line_ids',None)
            line_ids=line_material[1] if line_material is not None and line_material[0] is words else {}
            values=[NativeSource(i, tuple(w[:4]), str(w[4]),
                (self.page.number, 'native_word'),
                (CellSource('word', i, tuple(w[:4]), str(w[4]), words),),
                line_scope=line_ids.get(i,(('native_occurrence',i),0))[0],
                source_order=line_ids.get(i,((),i))[1])
                for i,w in enumerate(words)]
            records=getattr(self.page,'_table_control_glyphs',())
            for i,record in enumerate(records):
                box=record['bbox'];cx,cy=(box[0]+box[2])/2,(box[1]+box[3])/2
                if not str(record['text']).strip() or any(w[0]<=cx<=w[2] and w[1]<=cy<=w[3] for w in words):continue
                ref=CellSource('glyph',i,tuple(box),record['text'],records,
                               (*record['font_xrefs'],record['char_index']))
                values.append(NativeSource(len(values),tuple(box),record['text'],
                              (self.page.number,'native_glyph'),(ref,),line_scope=('native_glyph',i),source_order=i))
            self._sources=tuple(values)
        return self._sources

    def sources_in(self, box):
        rect = pymupdf.Rect(box)
        result=[self.sources[i] for i,w in _refine_word_candidates(self.page,self.words,rect)
                if rect.x0 <= (w[0]+w[2])/2 < rect.x1 and rect.y0 <= (w[1]+w[3])/2 < rect.y1]
        result.extend(n for n in self.sources[len(self.words):]
                      if rect.x0 <= (n.bbox[0]+n.bbox[2])/2 < rect.x1
                      and rect.y0 <= (n.bbox[1]+n.bbox[3])/2 < rect.y1)
        return tuple(result)



    def validate_sources(self, tables):
        """Validate live producers and actual claims, without residual policy.

        This common contract does not promise that every native word inside
        a rectangular table envelope has been recovered into a cell.
        """
        from .table_content_recovery import node_sources
        node_sources(self.sources)
        for tab in tables:
            for row in tab.placements:
                for cell in row:
                    cell.validate_source_content()
                    if cell.source_content is not None:
                        node_sources((cell.source_content,))

    @property
    def span_blocks(self):
        _=self.words  # Canonical word producer already retained its span input.
        blocks=self.runtime.span_material.get(self.page)
        if blocks is None:raise RuntimeError('Missing prepared native span material')
        epoch=getattr(self.runtime,'span_material_epochs',{}).get(self.page,0)
        previous=self._span_material_token
        if previous is None or previous[0] != epoch or previous[1] is not blocks:
            self._lines=None
            self._span_material_token=(epoch,blocks)  # retain identity, not just a recycled id
        return blocks




    @property
    def lines(self):
        _=self.span_blocks
        if self._lines is None:
            result=[]
            for block in self.span_blocks:
                for line in block.get('lines',()):
                    text=''.join(span.get('text',''.join(c.get('c','') for c in span.get('chars',()))) for span in line.get('spans',()))
                    if text.strip():result.append((tuple(line['bbox']),text))
            self._lines=tuple(result)
        return self._lines

    @property
    def joined_edges(self):
        if self._joined_edges is None:
            edges=[dict(e) for e in self.edges if e.get('ruling_origin') in ('vector','raster')]
            self._joined_edges=tuple(table.merge_edges(edges, snap_x_tolerance=table.DEFAULT_SNAP_TOLERANCE,
                snap_y_tolerance=table.DEFAULT_SNAP_TOLERANCE,
                join_x_tolerance=table.DEFAULT_JOIN_TOLERANCE,
                join_y_tolerance=table.DEFAULT_JOIN_TOLERANCE)) if edges else ()
        return self._joined_edges

    def cut_is_clear(self, axis, lo, hi, box):
        """A source word or an existing continuous ruling is not a whitespace cut."""
        k=0 if axis=='x' else 1;cross=1-k;middle=(lo+hi)/2
        for s in self.sources_in(box):
            if s.bbox[k] < middle < s.bbox[k+2]:return False
        orientation='h' if axis=='x' else 'v'
        for e in self.joined_edges:
            if e['orientation']!=orientation:continue
            start,end=(e['x0'],e['x1']) if axis=='x' else (e['top'],e['bottom'])
            position=e['top'] if axis=='x' else e['x0']
            if start < lo and hi < end and box[cross] < position < box[cross+2]:return False
        return True

    def raster(self, space):
        image=self.runtime.rasters.get((self.frame,1.0,space))
        if image is None:
            # A page with no prior table crop may have only a higher-resolution
            # detector raster. This is the first required scale-one producer,
            # retained for every subsequent region, never rendered per child.
            pix=self.page.get_pixmap(matrix=pymupdf.Matrix(1,1),colorspace=pymupdf.csRGB)
            image=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
            if space=='BGR':image=np.ascontiguousarray(image[:,:,::-1])
            self.runtime.accept_raster_material(self.page,image,scale=1.,space=space)
            image=self.runtime.rasters[(self.frame,1.0,space)]
        return image

    def reconstruct(self, bbox):
        image=self.raster(self.runtime.structure_pixel_space)
        x0,y0,x1,y1=map(float,bbox)
        a,b=max(0,int(x0)),max(0,int(y0));c,d=min(image.shape[1],int(x1)),min(image.shape[0],int(y1))
        if a>=c or b>=d:raise ValueError('Empty native reconstruction crop')
        chosen=[(box,text) for box,text in self.lines if x0 <= (box[0]+box[2])/2 < x1 and y0 <= (box[1]+box[3])/2 < y1]
        if not chosen:raise ValueError('Native reconstruction has no source lines')
        boxes=np.asarray([box for box,_ in chosen],dtype=np.float32)-[x0,y0,x0,y0]
        grid,_=self.runtime.structure_predict(image[b:d,a:c],boxes,texts=[text for _,text in chosen])
        if grid is None:raise RuntimeError('Native-region TGIF produced no grid')
        h=[y0]+[float(v)+y0 for v in grid.h_lines]+[y1]
        v=[x0]+[float(q)+x0 for q in grid.v_lines]+[x1]
        return [[(v[j],h[i],v[j+1],h[i+1]) for j in range(len(v)-1)] for i in range(len(h)-1)]


