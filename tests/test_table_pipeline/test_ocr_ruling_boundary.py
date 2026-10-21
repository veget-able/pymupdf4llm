"""Only raster ruling pixels use pre-OCR rendering; live consumers are unchanged."""
import pymupdf
import pytest

from pymupdf4llm.ocr import exec_ocr_interface as ocr
from pymupdf4llm.ocr.get_culled_pixmap import get_pixmap
from pymupdf4llm.helpers.table_html import raster_lines


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
        captures = []
        monkeypatch.setattr(raster_lines, "_image_regions", lambda p: [p.rect])
        monkeypatch.setattr(raster_lines, "_layout_table_rects", lambda p: [])
        def detect(gray, **kwargs):
            captures.append((gray.copy(), kwargs["words"]))
            return []
        monkeypatch.setattr(raster_lines, "_detect_grid_components", detect)
        assert raster_lines.detect_raster_table_lines(page, dpi=72) == []
        assert captures[0][0].tobytes() == original.samples
        assert any(w[4] == "OCR" for w in captures[0][1])
        assert page.get_text("words") == live_words
        assert page.get_pixmap(colorspace=pymupdf.csGRAY).samples == live_pixels


def test_no_ocr_renders_live_page(monkeypatch):
    with pymupdf.open() as doc:
        page = doc.new_page(width=120, height=100)
        page.draw_line((20, 20), (100, 20))
        expected = page.get_pixmap(colorspace=pymupdf.csGRAY).samples
        monkeypatch.setattr(raster_lines, "_image_regions", lambda p: [p.rect])
        monkeypatch.setattr(raster_lines, "_layout_table_rects", lambda p: [])
        def detect(gray, **kwargs):
            assert gray.tobytes() == expected
            return []
        monkeypatch.setattr(raster_lines, "_detect_grid_components", detect)
        assert raster_lines.detect_raster_table_lines(page, dpi=72) == []

@pytest.mark.parametrize("selection", ["empty", "none", "explicit"])
def test_empty_rects_preserve_text_but_none_culls_page(selection):
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=100)
        page.insert_text((20, 50), "Native text", fontsize=14)
        original = page.get_pixmap(dpi=72)
        displaylist = page.get_displaylist()
        rects = [] if selection == "empty" else (None if selection == "none" else [page.rect])
        pix, empty = get_pixmap(displaylist, dpi=72, rects=rects)
        if selection == "empty":
            assert not empty
            assert pix.samples == original.samples
        else:
            assert empty
            assert pix.samples != original.samples
        assert page.get_pixmap(dpi=72).samples == original.samples
        assert "Native text" in page.get_text()
