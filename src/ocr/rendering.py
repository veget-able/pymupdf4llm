"""Main's normal-span culling, with optional selected repair targets."""
import pymupdf as p
from .page_state import is_ocr_text_for_rapid
from .get_culled_pixmap import get_pixmap,max_dpi_for_page,MAX_PIXELS,pixmap_is_empty

def collect_render_context(page):
    ids=set()
    if getattr(page,'_pymupdf4llm_symbol_repair',False):
        from .symbol_repair import target_span_ids
        ids=target_span_ids(page)
    dl=page.get_displaylist();tp=p.TextPage(dl.get_textpage(flags=p.TEXT_ACCURATE_BBOXES))
    normal=[];broken=[];old=[]
    for block in tp.extractDICT()['blocks']:
        for line in block.get('lines',[]):
            for span in line['spans']:
                identity=tuple(span['bbox']),tuple(span['origin']),span['font'],span['text']
                if is_ocr_text_for_rapid(span):old.append(span['bbox'])
                elif '\ufffd'in span['text']:broken.append(span['bbox'])
                elif identity not in ids:normal.append(span['bbox'])
    return dict(displaylist=dl,normal=normal,broken=broken,old=old,symbol_ids=ids)

def render_ocr_input(page,dpi=150,context=None):
    context=collect_render_context(page)if context is None else context
    if context['symbol_ids']:
        from .symbol_repair import render_input
        return render_input(page,context['normal'],dpi)
    if getattr(page,'_pymupdf4llm_unicode_repair',False)and not context['normal']:
        dl=context['displaylist'];used=min(dpi,max_dpi_for_page(dl.rect,MAX_PIXELS))
        pix=dl.get_pixmap(matrix=p.Matrix(used/72,used/72),colorspace=p.csRGB,alpha=False);pix.set_dpi(used,used)
        return pix,pixmap_is_empty(pix,threshold=250)
    return get_pixmap(context['displaylist'],dpi=dpi,rects=context['normal'],empty_threshold=250)
