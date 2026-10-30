"""Model-only main replacement preserves old-layer policy and metadata."""
from pathlib import Path
import hashlib
import numpy as np
import pytest
import pymupdf as p
from pymupdf4llm.ocr import model_selector as selector
from pymupdf4llm.ocr.page_state import collect_page_state
from pymupdf4llm.ocr.imf2_roi import MODEL,residual_components
from pymupdf4llm.helpers import document_layout as dl
from pymupdf4llm.ocr import OCRMode
from unicode_fixtures import damaged_page

def test_original_weights():
    assert hashlib.sha256(MODEL.read_bytes()).hexdigest()=='185f5c068f9f057fcefb24af5df5a960de58609eee105cc9dab940e20b2aedb3'

@pytest.mark.parametrize('selected',[True,False])
def test_bool_selector_does_not_change_state(monkeypatch,selected):
    with p.open()as doc:
        page=doc.new_page();page.draw_rect(p.Rect(20,20,80,80))
        state=collect_page_state(page);before=state.metadata
        monkeypatch.setattr(selector,'select_page',lambda *a,**kw:selected)
        result=selector.analyze_page(page)
        assert result['needs_ocr']is selected and before==collect_page_state(page).metadata

def test_regular_old_layer_does_not_reach_imf2(monkeypatch):
    doc,page=damaged_page(text='normal saved text',hidden=True)
    with doc:
        monkeypatch.setattr(selector,'select_page',lambda *a,**kw:pytest.fail('Old-layer policy bypassed'))
        assert dl.make_ocr_decision(page,True)[0]is False

def test_model_does_not_install_any_correction():
    import pymupdf4llm
    root=Path(pymupdf4llm.__file__).parent/'ocr'
    assert not hasattr(OCRMode,'SELECT_REPAIR_OLD')
    for f in ['unicode_priority.py','symbol_priority.py','stored_damage.py','symbol_repair.py']:
        assert not(root/f).exists()

def test_residual_area_and_stored_mask():
    prob=np.zeros((30,30),np.float32);prob[5:10,5:13]=1
    stored=np.zeros((30,30),np.uint8)
    assert len(residual_components(prob,stored))==1
    stored[5:10,5:13]=1;assert not residual_components(prob,stored)


def test_off_none_keeps_main_compatibility():
    assert dl.make_ocr_decision(None,False)==(False,0,False)
