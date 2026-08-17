"""Focused contracts for the standalone OCR language/API fix branch."""
from types import SimpleNamespace

import pymupdf


def test_empty_analyze_page_has_visible_chars():
    from pymupdf4llm.ocr.analyze_page import analyze_page

    doc = pymupdf.open()
    assert analyze_page(doc.new_page())["visible_chars"] == 0


def test_detector_recognition_forwards_requested_language(monkeypatch):
    from pymupdf4llm.ocr import exec_ocr_interface

    languages = []
    monkeypatch.setattr(
        exec_ocr_interface,
        "get_text",
        lambda _pix, _rect, *, language: languages.append(language) or "text",
    )
    result = exec_ocr_interface._recognize_detection_boxes(
        object(), [([(1, 2), (9, 2), (9, 7), (1, 7)], 0.99)], "deu"
    )
    assert result[0][1] == "text"
    assert languages == ["deu"]


def test_rapidocr_crop_adapter_reuses_existing_engine(monkeypatch):
    from pymupdf4llm.ocr import rapidocr_391_backend

    calls = []

    class Engine:
        def text_rec(self, request):
            calls.append(request.img)
            return SimpleNamespace(txts=["one", "two"])

    monkeypatch.setattr(rapidocr_391_backend, "init_engine", lambda: Engine())
    assert list(rapidocr_391_backend.recognize_crops([object(), object()])) == ["one", "two"]
    assert len(calls) == 1


def test_preflight_forwards_language_once_and_rejects_custom_callback(monkeypatch):
    from pymupdf4llm import _prior_ocr_trust_preflight as preflight
    from pymupdf4llm.ocr import rapidocr_api, rapidocr_391_backend

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "retained ocr line")
    monkeypatch.setattr(preflight, "detect_rapidocr_backend", lambda: "rapidocr")
    monkeypatch.setattr(preflight, "is_ocr_span", lambda _span: True)
    monkeypatch.setattr(rapidocr_391_backend, "recognize_crops", lambda _crops: ["different"])
    calls = []

    def callback(*_args, **kwargs):
        calls.append(kwargs["language"])

    monkeypatch.setattr(rapidocr_api, "exec_ocr", callback)
    selected = preflight.check(
        page, source="unit.pdf", page_number=0, use_ocr=True, ocr_dpi=150,
        ocr_function=callback, ocr_language="deu",
    )
    assert selected["selected"] is True
    assert selected["preflight_full_ocr_calls"] == 1
    assert calls == ["deu"]
    custom = preflight.check(
        page, source="unit.pdf", page_number=0, use_ocr=True, ocr_dpi=150,
        ocr_function=lambda *_a, **_k: None, ocr_language="deu",
    )
    assert custom["ineligible_reason"] == "nondefault_ocr_callback"


def _parse_fixture(monkeypatch):
    """Use parse_document control flow while replacing only layout backends."""
    from pymupdf4llm.helpers import document_layout

    monkeypatch.setattr(document_layout.utils, "extract_form_fields_with_pages", lambda _doc: {})
    monkeypatch.setattr(document_layout.pymupdf, "recover_text_styles", lambda *_a, **_k: None)
    monkeypatch.setattr(
        document_layout,
        "get_layout_locked",
        lambda page, **_k: setattr(page, "layout_information", [{
            "group_bbox": [0, 0, page.rect.width, page.rect.height],
            "class_name": "text", "table_grid": None,
        }]),
    )
    monkeypatch.setattr(document_layout.utils, "clean_pictures", lambda *_a: None)
    monkeypatch.setattr(document_layout.utils, "add_image_orphans", lambda *_a: None)
    monkeypatch.setattr(document_layout.utils, "find_reading_order", lambda _r, _b, order: order)
    monkeypatch.setattr(document_layout.prior_ocr_preflight, "emit", lambda _event: None)
    doc = pymupdf.open()
    doc.new_page(width=160, height=120).insert_text((16, 32), "visible source text")
    return document_layout, doc


def _event(selected=False):
    return {
        "selected": selected, "normal_full_ocr_calls": 0,
        "v3_recovery_full_ocr_calls": 0, "v3_exact_empty_skipped": False,
    }


def test_selected_preflight_suppresses_normal_and_exact_empty_reentry(monkeypatch):
    layout, doc = _parse_fixture(monkeypatch)
    event, calls = _event(True), []

    def callback(page, **kwargs):
        calls.append((page.number, kwargs))

    def selected(page, *, ocr_function, ocr_dpi, ocr_language, **_kwargs):
        ocr_function(page, dpi=ocr_dpi, language=ocr_language, keep_ocr_text=False)
        return event

    monkeypatch.setattr(layout.prior_ocr_preflight, "check", selected)
    monkeypatch.setattr(layout, "make_ocr_decision", lambda *_a: (_ for _ in ()).throw(AssertionError("normal OCR re-entry")))
    monkeypatch.setattr(layout, "_page_markdown_is_exactly_empty", lambda *_a: (_ for _ in ()).throw(AssertionError("exact-empty re-entry")))
    layout.parse_document(doc, use_ocr=True, ocr_function=callback, ocr_language="deu")
    assert len(calls) == 1
    assert event["normal_full_ocr_calls"] == 0
    assert event["v3_recovery_full_ocr_calls"] == 0
    assert event["v3_exact_empty_skipped"] is True


def test_exact_empty_reparse_uses_ocr_never_without_preflight_reentry(monkeypatch):
    layout, doc = _parse_fixture(monkeypatch)
    event, preflight_calls, callbacks = _event(), [], []
    monkeypatch.setattr(layout.prior_ocr_preflight, "check", lambda _page, **_k: preflight_calls.append(True) or event)
    monkeypatch.setattr(layout, "make_ocr_decision", lambda _page, use_ocr: (False, 1 if use_ocr is True else 0, False))
    monkeypatch.setattr(layout, "_page_markdown_is_exactly_empty", lambda *_a: True)
    layout.parse_document(doc, use_ocr=True, ocr_function=lambda page, **kwargs: callbacks.append((page.number, kwargs)))
    assert len(preflight_calls) == 1
    assert len(callbacks) == 1
    assert event["v3_recovery_full_ocr_calls"] == 1
