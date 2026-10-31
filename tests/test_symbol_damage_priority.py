"""Marker-aware symbol repair scope, render preservation and mapped writeback."""

import pymupdf as p
import pytest

from pymupdf4llm.helpers import document_layout as dl
from pymupdf4llm.ocr import OCRMode
from pymupdf4llm.ocr.symbol_repair import render,span_inventory,prepare_symbol_replacement
from pymupdf4llm.ocr.exec_ocr_interface import exec_ocr_full
from pymupdf4llm.ocr import stored_damage
from pymupdf4llm.ocr.stored_damage import assess_text,inspect_page
from pymupdf4llm.ocr.unicode_damage import damage_inventory

SYMBOL_TEXT=''.join('a'+c for c in '!"#$%&\'*+,-./:;<=>?@^_`|~')*2


def document(unicode_marker=False,marker_origin=(20,125)):
    doc=p.open();page=doc.new_page(width=750,height=180)
    page.insert_text((20,30),'NATIVE TITLE',fontsize=14)
    page.insert_text((20,80),SYMBOL_TEXT,fontsize=9)
    if unicode_marker:
        page.insert_text(marker_origin,'AXB',fontsize=9)
        font=page.insert_font(fontname='helv')
        mapping=doc.get_new_xref();doc.update_object(mapping,'<<>>')
        pairs=' '.join(f'<{i:02X}> <{0xFFFD if i==88 else i:04X}>'for i in range(32,127))
        data=('/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapType 2 def '
              '/CMapName /Damage def 1 begincodespacerange <00> <FF> endcodespacerange '
              '95 beginbfchar '+pairs+' endbfchar endcmap CMapName currentdict /CMap defineresource pop end end')
        doc.update_stream(mapping,data.encode());doc.xref_set_key(font,'ToUnicode',f'{mapping} 0 R')
        doc.reload_page(page)
    return doc


def test_page_pattern_and_short_input_contract():
    assert assess_text(SYMBOL_TEXT)['candidate']
    assert not assess_text('a!b$c%d^e&f*g+h=j?k@l#m~')['eligible']
    assert not assess_text('\n'.join('Item...........value'for _ in range(20)))['candidate']
    info=assess_text('def foo():\n    return "\ufffd"\n')
    assert not info['candidate']and len(info['unicode_marker_offsets'])==1


@pytest.mark.parametrize('unicode_marker',[False,True])
def test_marker_aware_scope_bypasses_P2_and_preserves_source_render(monkeypatch,unicode_marker):
    with document(unicode_marker=unicode_marker)as doc:
        page=doc[0];before=page.get_text()
        monkeypatch.setattr(dl.utils,'analyze_page',lambda *a,**kw:pytest.fail('Symbol candidate reached P2'))
        assert dl.make_ocr_decision(page,True)==(True,0,True)
        assert page._pymupdf4llm_ocr_damage_reason=='symbol_damage'
        rows=span_inventory(page)
        assert next(r for r in rows if r['text']=='NATIVE TITLE')['category']==('normal'if unicode_marker else'symbol_damage')
        assert next(r for r in rows if r['text']==SYMBOL_TEXT)['category']=='symbol_damage'
        pix,empty,audit=render(page)
        assert not empty and not audit['normal_glyph_filter']
        if not unicode_marker:
            assert pix.samples==page.get_pixmap(dpi=150).samples
        else:
            with p.open()as ref:
                target=ref.new_page(width=750,height=180)
                target.insert_text((20,80),SYMBOL_TEXT,fontsize=9)
                target.insert_text((20,125),'AXB',fontsize=9)
                assert pix.samples==target.get_pixmap(dpi=150).samples
        assert page.get_text()==before


@pytest.mark.parametrize('mode',[False,OCRMode.SELECT_KEEP_OLD,OCRMode.SELECT_DROP_OLD])
def test_explicit_modes_disable_symbol_extension(monkeypatch,mode):
    with document()as doc:
        page=doc[0]
        dl.make_ocr_decision(page,True)
        calls=[]
        monkeypatch.setattr(dl.utils,'analyze_page',lambda *a,**kw:calls.append(True)or dict(needs_ocr=False,ocr_spans=0,img_area=0,vec_norects=0))
        assert dl.make_ocr_decision(page,mode)[0]is False
        assert not page._pymupdf4llm_symbol_repair
        assert all(r['category']=='normal'for r in span_inventory(page))
        assert len(calls)==(0 if mode is False else 1)


@pytest.mark.parametrize('unicode_marker',[False,True])
def test_shared_Rapid_writeback_uses_marker_aware_scope(unicode_marker):
    with document(unicode_marker=unicode_marker)as doc:
        page=doc[0];dl.make_ocr_decision(page,True)
        title=[s for b in page.get_text('dict')['blocks']for l in b.get('lines',[])for s in l['spans']if s['text']=='NATIVE TITLE'][0]
        calls=[]
        def full(image):
            calls.append(image.shape)
            result=[([[40,140],[1200,140],[1200,180],[40,180]],'RESTORED BODY',.99)]
            if not unicode_marker:
                result.insert(0,([[40,25],[400,25],[400,70],[40,70]],'RESTORED TITLE',.99))
            return result
        exec_ocr_full(page,full,dpi=150,keep_ocr_text=False)
        after=page.get_text();assert after.count('RESTORED BODY')==1
        assert SYMBOL_TEXT not in after and len(calls)==1
        if unicode_marker:
            assert after.count('NATIVE TITLE')==1
            kept=[s for b in page.get_text('dict')['blocks']for l in b.get('lines',[])for s in l['spans']if s['text']=='NATIVE TITLE'][0]
            assert all(kept[k]==title[k]for k in ['font','size','origin','bbox'])
        else:
            assert 'NATIVE TITLE'not in after and after.count('RESTORED TITLE')==1


@pytest.mark.parametrize('unicode_marker',[False,True])
def test_empty_recognition_keeps_original_symbol_text(unicode_marker):
    with document(unicode_marker=unicode_marker)as doc:
        page=doc[0];dl.make_ocr_decision(page,True);before=page.get_text()
        exec_ocr_full(page,lambda image:[],dpi=150,keep_ocr_text=False)
        assert page.get_text()==before


@pytest.mark.parametrize('unicode_marker',[False,True])
def test_tesseract_adapter_applies_same_scope_without_real_recognition(monkeypatch,unicode_marker):
    from pymupdf4llm.ocr import tesseract_api as tess
    with document(unicode_marker=unicode_marker)as doc,p.open()as recognized:
        page=doc[0];dl.make_ocr_decision(page,True)
        target=recognized.new_page(width=750,height=180);target.insert_text((20,80),'RESTORED BODY')
        data=recognized.tobytes()
        class FakePixmap:
            def pdfocr_tobytes(self,language):return data
        monkeypatch.setattr(tess,'TESSDATA','mock-data')
        monkeypatch.setattr(tess,'get_pixmap',lambda *a,**kw:(FakePixmap(),False))
        monkeypatch.setattr(tess,'render_input',lambda *a,**kw:(FakePixmap(),False))
        tess.exec_ocr(page,keep_ocr_text=False)
        text=page.get_text();assert SYMBOL_TEXT not in text
        assert text.count('NATIVE TITLE')==int(unicode_marker)
        assert text.count('RESTORED BODY')==1


def test_off_page_unicode_marker_still_prevents_page_expansion():
    with document(unicode_marker=True,marker_origin=(20,1000))as doc:
        page=doc[0];damage=damage_inventory(page)
        assert damage['character_count']==damage['unusable_geometry_characters']==1
        dl.make_ocr_decision(page,True)
        assert next(s for s in span_inventory(page)if s['text']=='NATIVE TITLE')['category']=='normal'


def test_uncertain_source_alignment_never_guesses_page_targets(monkeypatch):
    class TextPage:
        def extractText(self):return SYMBOL_TEXT+'\n'
        def extractRAWDICT(self):return {'blocks':[]}
    class Page:
        def get_textpage(self,**kwargs):return TextPage()
    monkeypatch.setattr(stored_damage,'damage_inventory',lambda page:pytest.fail('Uncertain alignment reached expansion'))
    result=inspect_page(Page())
    assert result['candidate']and not result['source_alignment_exact']
    assert not result['symbol_character_keys']and not result['symbol_target_spans']


def test_page_expansion_keeps_text_clipping_glyphs():
    with document()as doc:
        page=doc[0];page.insert_text((20,50),'CLIP',fontsize=9,render_mode=4)
        dl.make_ocr_decision(page,True);plan=prepare_symbol_replacement(page)
        assert plan is not None
        clipped=[i for i,r in enumerate(plan.records)if r['render_mode']>=4]
        assert clipped and all(not plan.removable[i]for i in clipped)
        plan.apply(page)
        assert 'CLIP'in page.get_text()and SYMBOL_TEXT not in page.get_text()


def test_standalone_has_no_repair_mode_or_unicode_priority(monkeypatch):
    from pathlib import Path
    import pymupdf4llm
    assert not hasattr(OCRMode,'SELECT_REPAIR_OLD')
    assert not(Path(pymupdf4llm.__file__).parent/'ocr/unicode_priority.py').exists()
    from unicode_fixtures import damaged_page
    doc,page=damaged_page(text='AXB',hidden=False)
    with doc:
        assert not inspect_page(page)['candidate']
        monkeypatch.setattr(dl.utils,'analyze_page',lambda *a,**kw:dict(needs_ocr=False,ocr_spans=0,img_area=1,vec_norects=0))
        assert dl.make_ocr_decision(page,True)[0]is False
        assert page._pymupdf4llm_ocr_damage_reason is None


def test_off_none_keeps_main_compatibility():
    assert dl.make_ocr_decision(None,False)==(False,0,False)
