"""Gate-only feature4: no new enum, normalization, renderer or writeback."""
import io
from PIL import Image
import pytest,pymupdf as p
from pymupdf4llm.helpers import document_layout as dl
from pymupdf4llm.ocr import OCRMode
from pymupdf4llm.ocr import analyze_page as analysis

@pytest.fixture
def old_page():
    with p.open()as doc:
        page=doc.new_page(width=300,height=200)
        im=io.BytesIO();Image.new('RGB',(300,200),'white').save(im,format='PNG')
        page.insert_image(page.rect,stream=im.getvalue());page.insert_text((20,50),'OLD OCR',render_mode=3)
        yield page

@pytest.mark.parametrize('score,expected',[(0.,False),(1.,True)])
def test_default_true_bypasses_only_old_gate(monkeypatch,old_page,score,expected):
    monkeypatch.setattr(analysis,'predict_ocr_probability',lambda *a:score)
    result=dl.make_ocr_decision(old_page,True)
    assert result==(expected,1,False)

@pytest.mark.parametrize('mode',[OCRMode.SELECT_KEEP_OLD,OCRMode.SELECT_DROP_OLD,OCRMode.FORCE_KEEP_OLD])
def test_explicit_modes_are_main(monkeypatch,old_page,mode):
    monkeypatch.setattr(analysis,'predict_ocr_probability',lambda *a:pytest.fail('Explicit mode changed old gate'))
    assert dl.make_ocr_decision(old_page,mode)==(False,1,False)

def test_explicit_force_drop_is_main(old_page):
    assert dl.make_ocr_decision(old_page,OCRMode.FORCE_DROP_OLD)==(True,1,False)

def test_api_and_source_modes_unchanged():
    assert list(OCRMode)==[OCRMode.NEVER,OCRMode.SELECT_DROP_OLD,OCRMode.SELECT_KEEP_OLD,OCRMode.FORCE_DROP_OLD,OCRMode.FORCE_KEEP_OLD]
    assert not hasattr(OCRMode,'SELECT_REPAIR_OLD')
    assert dl.make_ocr_decision(None,False)==(False,0,False)
