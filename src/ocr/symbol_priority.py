"""Standalone symbol damage; Unicode inventory is data, not feature5."""
from .stored_damage import inspect_page
from .page_state import collect_page_state

def prepare(page):page._pymupdf4llm_symbol_repair=True

def decide(page,mode):
    result=inspect_page(page)
    if not result['candidate']:return None
    page._pymupdf4llm_ocr_damage_reason='symbol_damage'
    page._pymupdf4llm_ocr_damage=dict(symbol_ratio=result['symbol_ratio'],body_nonspace=result['nonspace'],target_spans=result['symbol_target_spans'],source_alignment_exact=result['source_alignment_exact'])
    return True,*collect_page_state(page).metadata
