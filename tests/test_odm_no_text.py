"""ODM renderer isolation: glyph removal, preserved residuals, stable22 features."""
from hashlib import sha256
from pathlib import Path
import numpy as np
import pymupdf as p
import pytest
from pymupdf4llm.ocr.odm_no_text import render_page_without_normal_text
from pymupdf4llm.ocr import compute_ocr_features as features


def make_page(normal=True):
    doc=p.open();page=doc.new_page(width=320,height=240)
    with p.open()as image_doc:
        image=image_doc.new_page(width=280,height=65)
        image.insert_text((10,36),'IMAGE TEXT MUST REMAIN',fontsize=15)
        image.draw_rect((4,4,275,61),color=(0,.4,.8))
        page.insert_image((20,80,300,145),pixmap=image.get_pixmap())
    page.draw_line((20,180),(300,180),color=(.2,.7,.1),width=2)
    if normal:page.insert_text((20,44),'NORMAL STORED HEADING',fontsize=18)
    return doc


def damaged_page():
    doc=p.open();page=doc.new_page(width=320,height=240)
    page.insert_text((20,100),'AXB',fontsize=25)
    font=page.insert_font(fontname='helv');mapping=doc.get_new_xref();doc.update_object(mapping,'<<>>')
    pairs=' '.join(f'<{i:02X}> <{0xfffd if i==88 else i:04X}>'for i in range(32,127))
    cmap=('/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapType 2 def /CMapName /Test def 1 begincodespacerange <00> <FF> endcodespacerange 95 beginbfchar '+pairs+' endbfchar endcmap CMapName currentdict /CMap defineresource pop end end')
    doc.update_stream(mapping,cmap.encode());doc.xref_set_key(font,'ToUnicode',f'{mapping} 0 R');doc.reload_page(page)
    return doc


def test_removes_native_glyphs_and_preserves_image_and_vectors():
    with make_page()as source,make_page(False)as reference:
        before=source.tobytes(garbage=0,deflate=False,no_new_id=True)
        pix=render_page_without_normal_text(source[0])
        expected=reference[0].get_pixmap(dpi=72,colorspace=p.csGRAY,alpha=False)
        assert pix.n==1 and (pix.width,pix.height)==(320,240)
        assert pix.samples==expected.samples
        assert source.tobytes(garbage=0,deflate=False,no_new_id=True)==before
        assert 'NORMAL STORED HEADING'in source[0].get_text()


def test_no_normal_targets_retains_original_render(monkeypatch):
    with make_page(False)as doc:
        page=doc[0];page.insert_text((20,40),'HIDDEN OLD TEXT',render_mode=3)
        expected=page.get_pixmap(dpi=72,colorspace=p.csGRAY,alpha=False)
        monkeypatch.setattr(p.mupdf,'fz_new_pixmap_from_display_list_culling_text2',lambda *a:pytest.fail('No normal glyph targets should use original render'))
        assert render_page_without_normal_text(page).samples==expected.samples


def test_broken_glyphs_stay_when_no_normal_text():
    with damaged_page()as doc:
        page=doc[0];assert '\ufffd'in page.get_text(flags=p.TEXTFLAGS_TEXT&~p.TEXT_CID_FOR_UNKNOWN_UNICODE)
        before=page.get_pixmap(dpi=72,colorspace=p.csGRAY,alpha=False)
        assert render_page_without_normal_text(page).samples==before.samples


def test_normal_heading_removed_while_broken_span_is_preserved():
    with damaged_page()as doc,damaged_page()as ref:
        page=doc[0];page.insert_text((20,40),'NORMAL',fontname='cour',fontsize=18)
        assert render_page_without_normal_text(page).samples==ref[0].get_pixmap(dpi=72,colorspace=p.csGRAY,alpha=False).samples


def test_only_four_page_pixel_features_change(monkeypatch):
    import pymupdf4llm.ocr.odm_no_text as renderer
    with make_page()as doc:
        page=doc[0];blocks=page.get_text('dict',flags=p.TEXT_ACCURATE_BBOXES|p.TEXT_PRESERVE_IMAGES|p.TEXT_COLLECT_VECTORS)['blocks']
        filtered=features.compute_features(blocks,page.rect,page)
        monkeypatch.setattr(renderer,'render_page_without_normal_text',lambda page,dpi=72:page.get_pixmap(dpi=dpi,colorspace=p.csGRAY,alpha=False))
        original=features.compute_features(blocks,page.rect,page)
        page_names={'page_sobel_energy','page_sobel_entropy','page_sobel_var','page_white_ratio'}
        assert len(features.FEATURE_NAMES)==22 and len(filtered)==22
        for name in set(features.FEATURE_NAMES)-page_names:assert filtered[name]==original[name],name
        assert any(filtered[name]!=original[name]for name in page_names)
        assert filtered['num_spans']>0 and filtered['text_area']>0
        assert filtered['num_images']==original['num_images']==1


def test_128_grid_and_original_weights():
    import pymupdf4llm.ocr.compute_ocr_features as mod
    with make_page()as doc:
        x=features.sobel_features_page(doc[0]);assert len(x)==4 and all(np.isfinite(v)for v in x)
    assert sha256((Path(mod.__file__).parent/'ocr_decision_model.onnx').read_bytes()).hexdigest()=='f72d8975dfc650d6761f793dad424939e70bb94a27d13de8d3507033c74fa101'
