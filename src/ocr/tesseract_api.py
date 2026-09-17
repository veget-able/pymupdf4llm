import pymupdf

from .get_culled_pixmap import get_pixmap
from .span_provenance import (
    annotate_page_ocr_spans,
    begin_runtime_ocr_record,
    is_ocr_span,
    record_runtime_ocr_rects,
)

TESSDATA = pymupdf.get_tessdata()
if TESSDATA is None:
    pymupdf.message(
        "Warning: Tesseract OCR is not available. No OCR text will be extracted."
    )

REPLACEMENT_UNICODE = chr(0xFFFD)  # Unicode Replacement Character


def ocr_text(span) -> bool:
    """Backward-compatible span-local OCR provenance check."""
    return is_ocr_span(span)


def exec_ocr(page, dpi=150, pixmap=None, language="eng", keep_ocr_text=False):
    """This callback function performs OCR on the given page.

    It uses RapidOCR for text region detection and Tesseract OCR for text
    recognition in each identified region (boundary box).

    If a Pixmap is provided, the DPI parameter is ignored. Otherwise, an RGB
    Pixmap is created from the page at the specified DPI.
    The DPI parameter is also used if extractable text is present.

    We ensure that legible extractable text is excluded from OCR. If present
    on page we make a temporary copy without such text and perform OCR
    on that copy.
    """
    begin_runtime_ocr_record(page)
    if TESSDATA is None:
        return
    displaylist = page.get_displaylist()
    stextpage = displaylist.get_textpage(flags=pymupdf.TEXT_ACCURATE_BBOXES)
    textpage = pymupdf.TextPage(stextpage)
    text_blocks = textpage.extractDICT()["blocks"]
    annotate_page_ocr_spans(page, text_blocks, language=language)

    # get bboxes with multiple text categories on page
    spans = []  # spans with legible text
    fffd_spans = []  # spans containing U+FFFD characters.
    ocr_spans = []  # spans with previously OCRed text

    for b in text_blocks:
        for l in b["lines"]:
            for s in l["spans"]:
                if ocr_text(s):
                    ocr_spans.append(s["bbox"])
                elif REPLACEMENT_UNICODE in s["text"]:
                    fffd_spans.append(s["bbox"])
                else:
                    spans.append(s["bbox"])
    if ocr_spans and keep_ocr_text:
        # If there are already OCR spans and the user wants to keep them, we skip OCR.
        # This is because we cannot distinguish between "good" text and "bad" OCR text.
        return
    # make a Pixmap without "good" text
    pixmap, empty = get_pixmap(displaylist, dpi=dpi, rects=spans, empty_threshold=250)
    if empty:
        return  # nothing to OCR, the page is empty after removing good text

    # OCR the (remainder of the) page and remove everything except the text
    # layer from the OCR result
    temp_pdf = pymupdf.open("pdf", pixmap.pdfocr_tobytes(language=language))
    temp_page = temp_pdf[0]
    temp_page.add_redact_annot(temp_page.rect)
    # Remove everything on the OCRed page except the detected text
    temp_page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
        text=pymupdf.PDF_REDACT_TEXT_NONE,
    )
    temp_to_page = temp_page.rect.torect(page.rect)
    runtime_rects = [
        pymupdf.Rect(span["bbox"]) * temp_to_page
        for block in temp_page.get_text("dict")["blocks"]
        if block.get("type") == 0
        for line in block.get("lines", ())
        for span in line.get("spans", ())
        if str(span.get("text") or "").strip()
    ]
    # insert the OCR text layer into the original page
    page.show_pdf_page(page.rect, temp_pdf, 0)
    record_runtime_ocr_rects(page, runtime_rects)
