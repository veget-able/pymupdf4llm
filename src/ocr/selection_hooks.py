"""Optional independent damage hooks; helper presence never enables a check."""
import importlib

def damage_enabled(mode):
    return mode is True

def run_priority_checks(page,mode):
    if page is None:return None
    page._pymupdf4llm_ocr_damage_reason=None
    page._pymupdf4llm_ocr_damage=None
    page._pymupdf4llm_unicode_repair=False
    page._pymupdf4llm_symbol_repair=False
    modules=[]
    for name in ('unicode_priority','symbol_priority'):
        full=__package__+'.'+name
        try:module=importlib.import_module(full)
        except ModuleNotFoundError as e:
            if e.name!=full:raise
            continue
        modules.append(module)
    if not damage_enabled(mode):return None
    for module in modules:
        if hasattr(module,'prepare'):module.prepare(page)
    for module in modules:
        result=module.decide(page,mode)
        if result is not None:return result
    return None
