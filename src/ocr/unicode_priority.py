"""Standalone U+FFFD priority; no REPAIR-policy or symbol feature required."""
from .unicode_damage import damage_inventory
from .page_state import collect_page_state

def decide(page,mode):
    damage=damage_inventory(page)
    if not damage['character_count']:return None
    page._pymupdf4llm_unicode_repair=True
    page._pymupdf4llm_ocr_damage_reason='unicode_damage'
    page._pymupdf4llm_ocr_damage=dict(unicode_characters=damage['character_count'],unicode_spans=damage['span_count'])
    return True,*collect_page_state(page).metadata
