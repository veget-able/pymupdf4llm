"""Standalone Unicode damage works on main, with no REPAIR enum or feature4."""
import pytest
import pymupdf as p
from pymupdf4llm.helpers import document_layout as dl
from pymupdf4llm.ocr import OCRMode,unicode_damage
from pymupdf4llm.ocr.exec_ocr_interface import exec_ocr_full
from pymupdf4llm.ocr.rendering import render_ocr_input
from unicode_fixtures import damaged_page

@pytest.mark.parametrize('hidden',[False,True])
def test_damage_priority_on_main_without_repair(monkeypatch,hidden):
    assert not hasattr(OCRMode,'SELECT_REPAIR_OLD')
    doc,page=damaged_page(text='ordinary healthy text AXB',hidden=hidden)
    with doc:
        before=page.get_text()
        monkeypatch.setattr(dl.utils,'analyze_page',lambda *a,**kw:pytest.fail('Damage reached selector'))
        selected,old,only=dl.make_ocr_decision(page,True)
        assert selected and not only and old==int(hidden)
        assert page._pymupdf4llm_ocr_damage_reason=='unicode_damage'
        assert page.get_text()==before

@pytest.mark.parametrize('mode',[False,OCRMode.SELECT_KEEP_OLD,OCRMode.SELECT_DROP_OLD])
def test_explicit_main_modes_do_not_enable_new_priority(monkeypatch,mode):
    doc,page=damaged_page(hidden=True)
    with doc:
        monkeypatch.setattr(dl.utils,'analyze_page',lambda *a,**kw:dict(needs_ocr=False,ocr_spans=1,img_area=1,vec_norects=0))
        assert dl.make_ocr_decision(page,mode)[0]is False
        assert not page._pymupdf4llm_unicode_repair


def test_ufffd_only_visible_text_survives_render_and_is_replaced():
    doc,page=damaged_page(text='AXB',hidden=False)
    with doc:
        doc.update_stream(page.get_contents()[0],b'')
        assert dl.make_ocr_decision(page,True)==(True,0,True)
        pix,empty=render_ocr_input(page)
        assert not empty and pix.samples==page.get_pixmap(dpi=150).samples
        exec_ocr_full(page,lambda image:[([[30,80],[150,80],[150,120],[30,120]],'RESTORED',.99)])
        assert page.get_text().count('RESTORED')==1
        assert '\ufffd'not in page.get_text(flags=p.TEXTFLAGS_TEXT&~p.TEXT_CID_FOR_UNKNOWN_UNICODE)


def test_empty_ocr_keeps_saved_damage():
    doc,page=damaged_page(text='AXB',hidden=False)
    with doc:
        dl.make_ocr_decision(page,True);before=page.get_text()
        exec_ocr_full(page,lambda image:[])
        assert page.get_text()==before


def test_regular_saved_ocr_still_uses_main_gate(monkeypatch):
    doc,page=damaged_page(text='ordinary healthy stored text',hidden=True)
    with doc:
        assert unicode_damage.damage_inventory(page)['character_count']==0
        assert dl.make_ocr_decision(page,True)[0]is False


def test_symbol_only_does_not_get_feature6(monkeypatch):
    from pathlib import Path
    import pymupdf4llm
    assert not(Path(pymupdf4llm.__file__).parent/'ocr/symbol_priority.py').exists()
    with p.open()as doc:
        page=doc.new_page();page.insert_text((20,50),'a!b@c#d$e%f^g&h*i+j-k?l~'*4,fontsize=8)
        monkeypatch.setattr(dl.utils,'analyze_page',lambda *a,**kw:dict(needs_ocr=False,ocr_spans=0,img_area=0,vec_norects=0))
        assert dl.make_ocr_decision(page,True)[0]is False


def test_off_none_keeps_main_compatibility():
    assert dl.make_ocr_decision(None,False)==(False,0,False)
