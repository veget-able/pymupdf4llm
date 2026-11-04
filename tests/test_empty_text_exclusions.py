"""Rendering exclusions must not discard unresolved glyphs when the list is empty."""
import pytest
import pymupdf as p
from pymupdf4llm.ocr.get_culled_pixmap import get_pixmap


def broken_text_pdf(text='ABCD', normal=False):
    """Preserve Latin glyphs but make their actual PDF Unicode mapping unresolved."""
    with p.open() as doc:
        page = doc.new_page(width=300, height=180)
        font = page.insert_font(fontname='helv')
        page.insert_text((30, 90), text, fontname='helv', fontsize=25)
        if normal:
            page.insert_text((30, 40), 'STORED NORMAL', fontname='cour', fontsize=15)
        codes = sorted(set(text.encode('ascii')))
        cmap = ('/CIDInit /ProcSet findresource begin 12 dict begin begincmap '
                '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def '
                '/CMapName /Broken def /CMapType 2 def '
                '1 begincodespacerange <00> <ff> endcodespacerange '
                f'{len(codes)} beginbfchar ' + ' '.join(f'<{code:02x}> <fffd>' for code in codes) +
                ' endbfchar endcmap CMapName currentdict /CMap defineresource pop end end').encode()
        xref = doc.get_new_xref()
        doc.update_object(xref, '<<>>')
        doc.update_stream(xref, cmap)
        doc.xref_set_key(font, 'ToUnicode', f'{xref} 0 R')
        return doc.tobytes()


def scan_png():
    with p.open() as doc:
        page = doc.new_page(width=300, height=180)
        page.insert_text((30, 90), 'SCANNED BODY', fontsize=20)
        return page.get_pixmap(dpi=72).tobytes('png')


@pytest.mark.parametrize('kind', ['native', 'broken', 'image', 'old_layer', 'nested_form', 'blank'])
def test_empty_exclusions_preserve_original_display_list(kind):
    doc = p.open(stream=broken_text_pdf(), filetype='pdf') if kind == 'broken' else p.open()
    with doc:
        page = doc[0] if len(doc) else doc.new_page(width=300, height=180)
        if kind in ('image', 'old_layer'):
            page.insert_image(page.rect, stream=scan_png())
        if kind == 'native':
            page.insert_text((30, 90), 'STORED NATIVE', fontsize=20)
        if kind == 'old_layer':
            page.insert_text((30, 90), 'STORED OCR', fontsize=20, render_mode=3)
        if kind == 'nested_form':
            with p.open(stream=broken_text_pdf(), filetype='pdf') as source:
                page.show_pdf_page(page.rect, source, 0)
        if kind == 'broken':
            assert page.get_text(flags=p.TEXTFLAGS_TEXT & ~p.TEXT_CID_FOR_UNKNOWN_UNICODE).count('\ufffd') == 4
        display = page.get_displaylist()
        expected = display.get_pixmap(matrix=p.Matrix(150/72, 150/72), colorspace=p.csRGB, alpha=False)
        actual, empty = get_pixmap(display, dpi=150, rects=[])
        assert actual.samples == expected.samples
        assert (actual.xres, actual.yres) == (150, 150)
        assert empty == (kind == 'blank')


def test_none_and_full_page_still_exclude_all_text():
    with p.open(stream=broken_text_pdf(), filetype='pdf') as doc:
        display = doc[0].get_displaylist()
        default, default_empty = get_pixmap(display)
        explicit, explicit_empty = get_pixmap(display, rects=[display.rect])
        original, original_empty = get_pixmap(display, rects=[])
        assert default.samples == explicit.samples
        assert default_empty and explicit_empty and not original_empty
        assert original.samples != explicit.samples


def test_nonempty_normal_exclusions_leave_broken_glyphs():
    with p.open(stream=broken_text_pdf(normal=True), filetype='pdf') as doc:
        page = doc[0]
        display = page.get_displaylist()
        blocks = p.TextPage(display.get_textpage(flags=p.TEXT_ACCURATE_BBOXES)).extractDICT()['blocks']
        spans = [span for block in blocks for line in block.get('lines', []) for span in line['spans']]
        normal = [span['bbox'] for span in spans if '\ufffd' not in span['text']]
        assert len(normal) == 1
        actual, empty = get_pixmap(display, rects=normal)
        broken = next(span['bbox'] for span in spans if '\ufffd' in span['text'])
        x0, y0, x1, y1 = p.Rect(broken) * p.Matrix(150/72, 150/72)
        x0, y0, x1, y1 = int(x0), int(y0), int(x1)+1, int(y1)+1
        original = display.get_pixmap(matrix=p.Matrix(150/72, 150/72), colorspace=p.csRGB, alpha=False)
        for row in range(y0, min(y1, actual.height)):
            start, end = (row*actual.width+x0)*3, (row*actual.width+x1)*3
            assert actual.samples[start:end] == original.samples[start:end]
        assert not empty


def test_empty_exclusions_keep_existing_dpi_cap(monkeypatch):
    from pymupdf4llm.ocr import get_culled_pixmap as rendering
    with p.open(stream=broken_text_pdf(), filetype='pdf') as doc:
        display = doc[0].get_displaylist()
        monkeypatch.setattr(rendering, 'MAX_PIXELS', 20_000)
        used = rendering.max_dpi_for_page(display.rect, 20_000)
        actual, empty = get_pixmap(display, dpi=150, rects=[])
        expected = display.get_pixmap(matrix=p.Matrix(used/72, used/72), colorspace=p.csRGB, alpha=False)
        assert actual.samples == expected.samples
        assert actual.xres == actual.yres == used
        assert not empty
