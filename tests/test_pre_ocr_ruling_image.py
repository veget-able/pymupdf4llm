"""Only raster ruling pixels use pre-OCR rendering; live consumers are unchanged."""
import pymupdf
import pytest

from pymupdf4llm.ocr import exec_ocr_interface as ocr


@pytest.mark.parametrize("backend", ["full", "detection"])
@pytest.mark.parametrize("rotation", [0, 90])
def test_ruling_uses_original_pixels_and_live_words(monkeypatch, backend, rotation):
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=120)
        page.draw_rect((20, 20, 180, 100), color=(0, 0, 0))
        page.insert_text((25, 110), "Native", fontsize=8)
        page.set_rotation(rotation)
        page.remove_rotation()  # same precondition as document_layout
        original = page.get_pixmap(colorspace=pymupdf.csGRAY)
        rgb = page.get_pixmap()
        monkeypatch.setattr(ocr, "get_pixmap", lambda *a, **k: (rgb, False))
        monkeypatch.setattr(ocr, "TESSDATA", "mock")
        monkeypatch.setattr(ocr, "get_text", lambda *a, **k: "OCR 123")
        box = [[30, 30], [100, 30], [100, 48], [30, 48]]
        callback = (lambda img: [(box, "OCR 123", .99)]) if backend == "full" else (lambda img: [(box, .99)])
        page._pymupdf4llm_raster_table_lines = {"dpi": 72, "lines": ["stale"]}
        getattr(ocr, "exec_ocr_" + backend)(page, callback, dpi=72)
        assert not hasattr(page, "_pymupdf4llm_raster_table_lines")
        live_pixels = page.get_pixmap(colorspace=pymupdf.csGRAY).samples
        live_words = page.get_text("words")
        assert live_pixels != original.samples  # live OCR remains visible
        assert any(w[4] == "OCR" for w in live_words)
        stored = page._pymupdf4llm_ruling_displaylist.get_pixmap(colorspace=pymupdf.csGRAY)
        assert stored.samples == original.samples
        assert page.get_pixmap(colorspace=pymupdf.csGRAY).samples == live_pixels
