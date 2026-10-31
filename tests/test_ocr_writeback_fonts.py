"""Main-only font insertion, policy retention and source-boundary checks."""
import copy
import pymupdf as p
import pytest
from pymupdf4llm.ocr import _writeback_font as f, exec_ocr_interface as cb
from pymupdf4llm.helpers.get_text_lines import get_raw_lines
from pymupdf4llm.helpers.document_layout import get_plain_text

@pytest.mark.parametrize('text',['भारत 7/19','Latin प / 漢字','क्\u200dषि','organizația și menține','IE❤HP','∆','ț漢字ș❤','IE ❤ HP','A❤B❤C'])
def test_pdf_unicode_and_live_formatter(text):
 with p.open() as d:
  page=d.new_page();rect=p.Rect(20,20,550,60)
  f._insert_writeback(page,rect,text,f._prepare_writeback(text,rect),set())
  with p.open(stream=d.tobytes(),filetype='pdf') as saved:
   assert saved[0].get_text().strip()==text
  blocks=page.get_text('dict')['blocks'];f.annotate_mixed_writeback_spans(page,blocks)
  lines=get_raw_lines(blocks=blocks,clip=page.rect,ignore_invisible=False)
  assert get_plain_text(lines[0][1]).strip()==text

@pytest.mark.parametrize('alias',['myfont','devanagari_font','ocr_latin_font','ocr_symbol_font'])
def test_resource_alias_collision(alias):
 with p.open() as d:
  page=d.new_page();page.insert_font(fontname=alias,fontbuffer=p.Font('helv').buffer)
  page.insert_text((20,200),'KEEP',fontname=alias)
  rect=p.Rect(20,20,550,60)
  text='Latin प / 漢字' if alias=='devanagari_font' else 'ț漢字ș❤'
  plan=f._prepare_writeback(text,rect)
  aliases=f.resolve_fontnames(page,[plan])
  if alias in aliases:assert aliases[alias]!=alias
  f._insert_writeback(page,rect,text,plan,set(),aliases)
  assert text in page.get_text() and 'KEEP' in page.get_text()

def written_page(text='IE❤HP'):
 d=p.open();page=d.new_page();rect=p.Rect(20,20,550,60)
 f._insert_writeback(page,rect,text,f._prepare_writeback(text,rect),set())
 blocks=page.get_text('dict')['blocks'];f.annotate_mixed_writeback_spans(page,blocks)
 return d,page,blocks

@pytest.mark.parametrize('case',['no_owner','duplicate_owner','duplicate_span','changed_text','different_group'])
def test_uncertain_or_unrelated_spans_are_not_joined(case):
 d,page,blocks=written_page()
 if case=='no_owner':
  page._pymupdf4llm_mixed_writeback_groups=[];blocks=page.get_text('dict')['blocks'];f.annotate_mixed_writeback_spans(page,blocks)
 elif case=='duplicate_owner':
  groups=page._pymupdf4llm_mixed_writeback_groups;groups.extend(copy.deepcopy(groups));blocks=page.get_text('dict')['blocks'];f.annotate_mixed_writeback_spans(page,blocks)
 elif case=='duplicate_span':
  blocks=page.get_text('dict')['blocks'];spans=blocks[0]['lines'][0]['spans'];spans.append(copy.deepcopy(spans[0]));f.annotate_mixed_writeback_spans(page,blocks)
  assert '_ocr_mixed_run' not in spans[0] and '_ocr_mixed_run' not in spans[-1]
  d.close();return
 elif case=='changed_text':blocks[0]['lines'][0]['spans'][1]['text']='?'
 else:
  for i,s in enumerate(blocks[0]['lines'][0]['spans']):
   _,a,b,t=s['_ocr_mixed_run'];s['_ocr_mixed_run']=(i,a,b,t)
 lines=get_raw_lines(blocks=blocks,clip=page.rect,ignore_invisible=False)
 assert len(lines[0][1])>=3
 d.close()

@pytest.mark.parametrize('detection',[False,True])
@pytest.mark.parametrize('keep',[False,True])
def test_main_callback_keeps_original_policy(monkeypatch,detection,keep):
 with p.open() as d:
  page=d.new_page(width=300,height=200)
  page.insert_text((20,150),'NATIVE')
  page.insert_text((20,170),'OLD',render_mode=3)
  pix=p.Pixmap(p.csRGB,p.IRect(0,0,300,200),False);pix.clear_with(255)
  monkeypatch.setattr(cb,'get_pixmap',lambda *a,**kw:(pix,False))
  quad=[[20,20],[260,20],[260,50],[20,50]];text='IE❤HP'
  monkeypatch.setattr(cb,'TESSDATA','unused-in-controlled-rec')
  monkeypatch.setattr(cb,'get_text',lambda *a,**kw:text)
  if detection:cb.exec_ocr_detection(page,lambda img:[(quad,.99)],keep_ocr_text=keep)
  else:cb.exec_ocr_full(page,lambda img:[(quad,text,.99)],keep_ocr_text=keep)
  extracted=page.get_text()
  assert 'NATIVE' in extracted
  if keep:assert 'OLD' in extracted and text not in extracted
  else:assert 'OLD' not in extracted and text in extracted
