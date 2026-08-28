"""Common OCR producer provenance contracts for PageLayout.full_ocred."""

import pymupdf


def _parse_fixture(monkeypatch):
    """Exercise real parse orchestration while keeping layout inference out of scope."""
    from pymupdf4llm.helpers import document_layout

    monkeypatch.setattr(document_layout.utils, "extract_form_fields_with_pages", lambda _doc: {})
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


def _event(selected=False, reason=None):
    return {
        "selected": selected, "ineligible_reason": reason,
        "normal_full_ocr_calls": 0, "v3_recovery_full_ocr_calls": 0,
        "v3_exact_empty_skipped": False,
    }


def test_pagelayout_full_ocred_defaults_false():
    from pymupdf4llm.helpers.document_layout import PageLayout

    assert PageLayout(1, 100, 100, []).full_ocred is False


def test_ordinary_full_ocr_marks_provenance_once(monkeypatch):
    layout, doc = _parse_fixture(monkeypatch)
    event, callbacks = _event(), []
    monkeypatch.setattr(layout.prior_ocr_preflight, "check", lambda _page, **_k: event)
    monkeypatch.setattr(layout, "make_ocr_decision", lambda *_a: (True, 0, False))

    parsed = layout.parse_document(
        doc, use_ocr=True,
        ocr_function=lambda page, **kwargs: callbacks.append((page.number, kwargs)),
    )
    assert parsed.pages[0].full_ocred is True
    assert len(callbacks) == 1
    assert event["normal_full_ocr_calls"] == 1
    assert event["v3_recovery_full_ocr_calls"] == 0


def test_selected_preflight_replacement_marks_provenance_and_blocks_reentry(monkeypatch):
    layout, doc = _parse_fixture(monkeypatch)
    event, callbacks = _event(selected=True), []

    def callback(page, **kwargs):
        callbacks.append((page.number, kwargs))

    def selected(page, *, ocr_function, ocr_dpi, ocr_language, **_kwargs):
        ocr_function(page, dpi=ocr_dpi, language=ocr_language, keep_ocr_text=False)
        return event

    monkeypatch.setattr(layout.prior_ocr_preflight, "check", selected)
    monkeypatch.setattr(layout, "make_ocr_decision", lambda *_a: (_ for _ in ()).throw(AssertionError("normal OCR re-entry")))
    monkeypatch.setattr(layout, "_page_markdown_is_exactly_empty", lambda *_a: (_ for _ in ()).throw(AssertionError("exact-empty re-entry")))
    parsed = layout.parse_document(doc, use_ocr=True, ocr_function=callback, ocr_language="deu")
    assert parsed.pages[0].full_ocred is True
    assert len(callbacks) == 1
    assert event["normal_full_ocr_calls"] == 0
    assert event["v3_recovery_full_ocr_calls"] == 0
    assert event["v3_exact_empty_skipped"] is True


def test_exact_empty_recovery_restores_provenance_after_ocr_disabled_reparse(monkeypatch):
    layout, doc = _parse_fixture(monkeypatch)
    event, preflight_calls, callbacks = _event(), [], []
    monkeypatch.setattr(layout.prior_ocr_preflight, "check", lambda _page, **_k: preflight_calls.append(True) or event)
    monkeypatch.setattr(layout, "make_ocr_decision", lambda _page, use_ocr: (False, 1 if use_ocr is True else 0, False))
    monkeypatch.setattr(layout, "_page_markdown_is_exactly_empty", lambda *_a: True)
    parsed = layout.parse_document(
        doc, use_ocr=True,
        ocr_function=lambda page, **kwargs: callbacks.append((page.number, kwargs)),
    )
    assert parsed.pages[0].full_ocred is True
    assert len(preflight_calls) == 1
    assert len(callbacks) == 1
    assert event["normal_full_ocr_calls"] == 0
    assert event["v3_recovery_full_ocr_calls"] == 1


def test_no_ocr_or_ineligible_prior_path_leaves_provenance_false(monkeypatch):
    layout, doc = _parse_fixture(monkeypatch)
    retained = _event(reason="nondefault_ocr_callback")
    callbacks = []
    monkeypatch.setattr(layout.prior_ocr_preflight, "check", lambda _page, **_k: retained)
    monkeypatch.setattr(layout, "make_ocr_decision", lambda *_a: (False, 1, False))
    parsed = layout.parse_document(
        doc, use_ocr=True,
        ocr_function=lambda page, **kwargs: callbacks.append((page.number, kwargs)),
    )
    assert parsed.pages[0].full_ocred is False
    assert callbacks == []
    assert retained["normal_full_ocr_calls"] == 0
    assert retained["v3_recovery_full_ocr_calls"] == 0
