"""OCR preserves original pixels without changing live OCR writeback."""
import pymupdf
import pytest
from pymupdf4llm.ocr import exec_ocr_interface as ocr


@pytest.mark.parametrize('backend', ['full', 'detection'])
@pytest.mark.parametrize('rotation', [0, 90])
def test_original_pixels_are_separate_from_live_ocr(monkeypatch, backend, rotation):
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=120)
        page.draw_rect((20, 20, 180, 100))
        page.insert_text((25, 110), 'Native', fontsize=8)
        page.set_rotation(rotation)
        page.remove_rotation()
        before = page.get_pixmap(colorspace=pymupdf.csGRAY).samples
        rgb = page.get_pixmap()
        monkeypatch.setattr(ocr, 'get_pixmap', lambda *a, **k: (rgb, False))
        monkeypatch.setattr(ocr, 'TESSDATA', 'mock')
        monkeypatch.setattr(ocr, 'get_text', lambda *a, **k: 'OCR 123')
        box = [[30, 30], [100, 30], [100, 48], [30, 48]]
        callback = (lambda img: [(box, 'OCR 123', .99)]) if backend == 'full' else (lambda img: [(box, .99)])
        getattr(ocr, 'exec_ocr_' + backend)(page, callback, dpi=72)
        saved = page._pymupdf4llm_ruling_displaylist
        assert saved.get_pixmap(colorspace=pymupdf.csGRAY).samples == before
        assert page.get_pixmap(colorspace=pymupdf.csGRAY).samples != before
        assert any(w[4] == 'OCR' for w in page.get_text('words'))
        # Repeated OCR must not replace the pre-first-writeback snapshot.
        getattr(ocr, 'exec_ocr_' + backend)(page, callback, dpi=72)
        assert page._pymupdf4llm_ruling_displaylist is saved
