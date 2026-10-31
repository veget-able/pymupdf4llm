"""Approved integration contracts; Unicode priority is explicitly excluded."""
import copy
import pymupdf as p
import pytest
from pymupdf4llm.helpers import document_layout as dl
from pymupdf4llm.helpers.get_text_lines import get_raw_lines
from pymupdf4llm.ocr import OCRMode,model_selector
from pymupdf4llm.ocr.exec_ocr_interface import exec_ocr_full
from pymupdf4llm.ocr import _writeback_font as fonts
from pymupdf4llm.ocr.symbol_repair import span_inventory
from unicode_fixtures import damaged_page
from test_symbol_damage_priority import document as symbol_document
from pymupdf4llm.ocr import exec_ocr_interface as callback

def old_page():
 d=p.open();page=d.new_page(width=300,height=240)
 page.insert_text((20,40),'STORED',render_mode=3)
 image=p.Pixmap(p.csRGB,p.IRect(0,0,100,100),False);image.clear_with(220)
 page.insert_image(p.Rect(10,70,180,220),pixmap=image)
 return d,page

@pytest.mark.parametrize('selected',[False,True])
def test_default_old_layer_bypass_reaches_imf2_and_uses_its_bool(monkeypatch,selected):
 with old_page()[0]as d:
  page=d[0];calls=[]
  monkeypatch.setattr(model_selector,'select_page',lambda *a,**kw:calls.append(True)or selected)
  assert dl.make_ocr_decision(page,True)[0]is selected
  assert calls==[True]

@pytest.mark.parametrize('mode',[OCRMode.SELECT_KEEP_OLD,OCRMode.SELECT_DROP_OLD,OCRMode.FORCE_KEEP_OLD])
def test_explicit_old_modes_retain_main_gate(monkeypatch,mode):
 with old_page()[0]as d:
  monkeypatch.setattr(model_selector,'select_page',lambda *a,**kw:pytest.fail('Explicit old-layer mode reached IMF2'))
  assert dl.make_ocr_decision(d[0],mode)[0]is False
  assert not d[0].__dict__.get('_pymupdf4llm_unicode_repair',False)

def test_force_drop_retains_main_force_contract(monkeypatch):
 with old_page()[0]as d:
  monkeypatch.setattr(model_selector,'select_page',lambda *a,**kw:pytest.fail('Old layer should be classified before model'))
  assert dl.make_ocr_decision(d[0],OCRMode.FORCE_DROP_OLD)[0]is True

@pytest.mark.parametrize('hidden',[False,True])
def test_unicode_priority_is_excluded_and_model_keeps_deciding(monkeypatch,hidden):
 d,page=damaged_page(text='ordinary healthy text AXB',hidden=hidden)
 with d:
  calls=[]
  monkeypatch.setattr(model_selector,'select_page',lambda *a,**kw:calls.append(True)or False)
  assert dl.make_ocr_decision(page,True)[0]is False
  assert calls==[True]
  assert page._pymupdf4llm_ocr_damage_reason is None
  assert not page._pymupdf4llm_unicode_repair
  assert page._pymupdf4llm_symbol_repair

@pytest.mark.parametrize('marker',[False,True])
def test_combined_target_scope_render_replacement_and_mixed_fonts(monkeypatch,marker):
 with symbol_document(unicode_marker=marker)as d:
  page=d[0]
  monkeypatch.setattr(model_selector,'select_page',lambda *a,**kw:pytest.fail('Damaged content reached model'))
  assert dl.make_ocr_decision(page,True)[0]
  assert page._pymupdf4llm_ocr_damage_reason=='symbol_damage'
  title=next(s for s in span_inventory(page)if s['text']=='NATIVE TITLE')
  assert title['category']==('normal'if marker else'symbol_damage')
  before=page.get_text();calls=[]
  def recognize(image):
   calls.append(image.shape)
   return [([[40,140],[1200,140],[1200,180],[40,180]],'ț漢字ș❤',.99)]
  exec_ocr_full(page,recognize)
  text=page.get_text();assert len(calls)==1 and text.count('ț漢字ș❤')==1
  assert 'NATIVE TITLE'in text if marker else 'NATIVE TITLE'not in text
  assert '\ufffd'not in page.get_text(flags=p.TEXTFLAGS_TEXT&~p.TEXT_CID_FOR_UNKNOWN_UNICODE)
  blocks=page.get_text('dict')['blocks'];fonts.annotate_mixed_writeback_spans(page,blocks)
  lines=get_raw_lines(blocks=blocks,clip=page.rect,ignore_invisible=False)
  assert any(s['text']=='ț漢字ș❤'for _,spans in lines for s in spans)

@pytest.mark.parametrize('marker',[False,True])
def test_combined_empty_recognition_preserves_saved_content(marker):
 with symbol_document(unicode_marker=marker)as d:
  page=d[0];dl.make_ocr_decision(page,True);before=page.get_text()
  exec_ocr_full(page,lambda image:[])
  assert page.get_text()==before

def test_no_deferred_api_or_direct_rec_added():
 assert not hasattr(OCRMode,'SELECT_REPAIR_OLD')
 import importlib.util
 assert importlib.util.find_spec('pymupdf4llm.ocr.unicode_priority')is None
 assert dl.make_ocr_decision(None,False)==(False,0,False)

@pytest.mark.parametrize('detection',[False,True])
@pytest.mark.parametrize('keep',[False,True])
def test_common_callback_retains_native_and_explicit_old_text_policy(monkeypatch,detection,keep):
 with p.open()as d:
  page=d.new_page(width=300,height=200)
  page.insert_text((20,150),'NATIVE');page.insert_text((20,170),'OLD',render_mode=3)
  pix=p.Pixmap(p.csRGB,p.IRect(0,0,300,200),False);pix.clear_with(255)
  monkeypatch.setattr(callback,'get_pixmap',lambda *a,**kw:(pix,False))
  monkeypatch.setattr(callback,'render_input',lambda *a,**kw:(pix,False))
  monkeypatch.setattr(callback,'TESSDATA','controlled-recognition')
  monkeypatch.setattr(callback,'get_text',lambda *a,**kw:'IE❤HP')
  quad=[[20,20],[260,20],[260,50],[20,50]]
  if detection:callback.exec_ocr_detection(page,lambda image:[(quad,.99)],keep_ocr_text=keep)
  else:callback.exec_ocr_full(page,lambda image:[(quad,'IE❤HP',.99)],keep_ocr_text=keep)
  text=page.get_text();assert 'NATIVE'in text
  assert ('OLD'in text)==keep
  assert ('IE❤HP'in text)==(not keep)
