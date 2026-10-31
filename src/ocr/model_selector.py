"""Only the page selector changes; main's old-layer policy remains first."""
from .page_state import collect_page_state
from .legacy_policy import legacy_existing_ocr_result
from .imf2_roi import select_page

def analyze_page(page,blocks=None,replace_ocr=False,ocr_dpi=200,stats=None,ignore_existing_ocr=False):
    state=collect_page_state(page,blocks)
    preserved=legacy_existing_ocr_result(page,state,replace_ocr,ignore_existing_ocr,stats)
    if preserved is not None:return preserved
    before=state.metadata
    selected=select_page(page,state,dpi=150)
    if type(selected)is not bool or state.metadata!=before:raise RuntimeError('Selector changed common contract')
    return {**state.analysis,'needs_ocr':selected,'reason':'IMF2_ROI','probability':None}
