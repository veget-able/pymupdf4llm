"""Regression tests for form-widget page ownership after save/reopen."""

import pymupdf

from pymupdf4llm.helpers.utils import extract_form_fields_with_pages


def _add_text_widget(page, name, value):
    widget = pymupdf.Widget()
    widget.field_name = name
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_value = value
    widget.rect = pymupdf.Rect(16, 16, 144, 40)
    page.add_widget(widget)


def _saved_reopened(tmp_path, setup):
    doc = pymupdf.open()
    setup(doc)
    path = tmp_path / "widgets.pdf"
    doc.save(path)
    doc.close()
    return pymupdf.open(path)


def test_terminal_widget_without_p_uses_page_widget_ownership(tmp_path):
    def setup(doc):
        _add_text_widget(doc.new_page(), "customer.name", "Ada")

    reopened = _saved_reopened(tmp_path, setup)
    fields = extract_form_fields_with_pages(reopened, xrefs=True)
    field = fields["customer.name"]
    assert field["field_value"] == "Ada"
    assert field["pages"] == [0]
    assert field["terminal"] is True
    assert isinstance(field["xref"], int)


def test_terminal_widget_explicit_p_keeps_fast_path(tmp_path):
    def setup(doc):
        page = doc.new_page()
        _add_text_widget(page, "customer.name", "Ada")
        doc.xref_set_key(page.first_widget.xref, "P", f"{page.xref} 0 R")

    reopened = _saved_reopened(tmp_path, setup)
    assert extract_form_fields_with_pages(reopened)["customer.name"]["pages"] == [0]


def test_flat_shared_name_widgets_merge_page_ownership_after_reopen(tmp_path):
    def setup(doc):
        _add_text_widget(doc.new_page(), "shared", "Off")
        _add_text_widget(doc.new_page(), "shared", "On")

    reopened = _saved_reopened(tmp_path, setup)
    fields = extract_form_fields_with_pages(reopened, xrefs=True)
    assert fields["shared"]["pages"] == [0, 1]
    assert fields["shared"]["field_value"] == "On"
    assert isinstance(fields["shared"]["xref"], list)
