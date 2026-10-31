"""Symbol damage only: preserve and replace exactly mapped symbol targets.

Ordinary normal-text rendering remains the main bbox-culling renderer.
This module never installs a common OCR-span predicate or a normal-glyph filter.
"""
from collections import defaultdict
from difflib import SequenceMatcher
import ctypes
import pymupdf as p
from pymupdf import mupdf as m
from . import get_culled_pixmap as culling
from .stored_damage import inspect_page,span_has_symbol_damage

ORIGIN_TOLERANCE=.001

def span_identity(span):
    return tuple(span['bbox']),tuple(span['origin']),span['font'],span['text']

def span_inventory(page):
    from .exec_ocr_interface import ocr_text
    keys=(inspect_page(page)['symbol_character_keys']if getattr(page,'_pymupdf4llm_symbol_repair',False)else set())
    tp=p.TextPage(page.get_displaylist().get_textpage(flags=p.TEXT_ACCURATE_BBOXES))
    dic,raw=tp.extractDICT(),tp.extractRAWDICT();rows=[]
    for bi,(block,rblock)in enumerate(zip(dic['blocks'],raw['blocks'])):
        for li,(line,rline)in enumerate(zip(block.get('lines',[]),rblock.get('lines',[]))):
            for si,(span,rspan)in enumerate(zip(line['spans'],rline['spans'])):
                chars=rspan['chars'];assert ''.join(c['c']for c in chars)==span['text']
                target=span_has_symbol_damage(rspan,keys)
                category=('old_OCR'if ocr_text(span)else'FFFD'if '\ufffd'in span['text']else'symbol_damage'if target else'normal')
                rows.append(dict(id=f'{bi}/{li}/{si}',category=category,text=span['text'],font=span['font'],
                    bbox=span['bbox'],origin=span['origin'],alpha=span['alpha'],char_flags=span['char_flags'],chars=chars,symbol_target=target))
    return rows

def target_span_ids(page):
    if not getattr(page,'_pymupdf4llm_symbol_repair',False):return set()
    return {span_identity(row)for row in span_inventory(page)if row['symbol_target']}

def _filter_contents(page,filt):
    options=p._make_PdfFilterOptions(recurse=1,instance_forms=1,sanitize=1,sopts=filt)
    pdfpage=p._as_pdf_page(page)
    m.pdf_filter_page_contents(pdfpage.doc(),pdfpage,options)
    for annot in list(page.annots()or[]):m.pdf_filter_annot_contents(pdfpage.doc(),annot.this,options)

class SymbolGlyphFilter(m.PdfSanitizeFilterOptions2):
    """Probe glyph callbacks, or remove the explicit symbol plan; never normal text."""
    def __init__(self,inventory,transform,plan=None):
        super().__init__();self.use_virtual_text_filter()
        self.inventory=inventory;self.transform=transform;self.plan=plan;self.records=[]
    def text_filter(self,ctx,ucsbuf,ucslen,trm,ctm,bbox,tr,ca,CA):
        codes=list((ctypes.c_int*ucslen).from_address(int(ucsbuf)))if ucslen else[]
        raw=m.fz_transform_point(m.FzPoint(trm.e,trm.f),m.FzMatrix(ctm))
        pos=p.Point(raw.x,raw.y)*self.transform
        drop=False
        if self.plan is not None:
            expected,drop,reason=self.plan[len(self.records)];assert codes==expected,(codes,expected)
            if tr>=4:drop=False
        self.records.append(dict(unicode=codes,origin=[pos.x,pos.y],render_mode=tr,drop=drop))
        return int(drop)

class SymbolReplacementPlan:
    """Remove only source glyph callbacks mapped entirely to symbol targets."""
    def __init__(self, inventory, records, groups, source):
        self.inventory,self.records=inventory,records
        self.removable=[bool(indices) and all(i is not None and source[i]['target']for i in indices)
                        and record['render_mode']<4 for record,indices in zip(records,groups)]

    def apply(self,page):
        if not any(self.removable):
            return
        plan=[(record['unicode'],drop,'replace_mapped_symbol_glyphs')
              for record,drop in zip(self.records,self.removable)]
        filt=SymbolGlyphFilter(self.inventory,page.transformation_matrix,plan=plan)
        _filter_contents(page,filt)

def prepare_symbol_replacement(page):
    """Plan mapped symbol targets; do not alter explicit main KEEP/DROP."""
    if not getattr(page,'_pymupdf4llm_symbol_repair',False):
        return None
    inventory=span_inventory(page)
    if not any(row['category']=='symbol_damage'for row in inventory):
        return None
    source=[dict(c=value,target=row['category']=='symbol_damage')
            for row in inventory for char in row['chars']if not char.get('synthetic')
            for value in char['c']]
    with p.open()as copied:
        copied.insert_pdf(page.parent,from_page=page.number,to_page=page.number,annots=True,widgets=True)
        probe=SymbolGlyphFilter(inventory,copied[0].transformation_matrix)
        _filter_contents(copied[0],probe)
    callback=[];owners=[]
    for index,record in enumerate(probe.records):
        for value in record['unicode']:
            callback.append(chr(value)if 0<=value<=0x10ffff else'\ufffd');owners.append(index)
    mapping={}
    matcher=SequenceMatcher(None,''.join(c['c']for c in source),''.join(callback),autojunk=False)
    for tag,a,b,c,d in matcher.get_opcodes():
        if tag=='equal':
            mapping.update(zip(range(c,d),range(a,b)))
    groups=[[]for _ in probe.records]
    for ci,owner in enumerate(owners):groups[owner].append(mapping.get(ci))
    return SymbolReplacementPlan(inventory,probe.records,groups,source)

def render_input(page,normal_rects,dpi=150,empty_threshold=250):
    """Legacy bbox render, retaining the known symbol spans excluded from its list."""
    dl=page.get_displaylist()
    if normal_rects:
        return culling.get_pixmap(dl,dpi=dpi,rects=normal_rects,empty_threshold=empty_threshold)
    # Symbol repair may target every stored span. Empty exclusions must keep those
    # targets, rather than invoke the legacy empty-list=>cull-page shortcut.
    used=min(dpi,culling.max_dpi_for_page(dl.rect,culling.MAX_PIXELS))
    pix=dl.get_pixmap(matrix=p.Matrix(used/72,used/72),colorspace=p.csRGB,alpha=False)
    pix.set_dpi(used,used)
    return pix,culling.pixmap_is_empty(pix,threshold=empty_threshold)

def render(page,dpi=150):
    """Diagnostic rendering with the same per-stage legacy predicate as feature4."""
    from .exec_ocr_interface import ocr_text
    inventory=span_inventory(page);ids={span_identity(r)for r in inventory if r['symbol_target']}
    normal=[r['bbox']for r in inventory if not ocr_text(r)and '\ufffd'not in r['text']and span_identity(r)not in ids]
    if ids:pix,empty=render_input(page,normal,dpi)
    else:pix,empty=culling.get_pixmap(page.get_displaylist(),dpi=dpi,rects=normal,empty_threshold=250)
    return pix,empty,dict(symbol_target_spans=len(ids),normal_bbox_count=len(normal),normal_glyph_filter=False)
