import inspect
import math
import unicodedata

import numpy as np
import pymupdf

from .get_culled_pixmap import get_pixmap

try:
    TESSDATA = pymupdf.get_tessdata()
except Exception as e:
    TESSDATA = None

FONT = pymupdf.Font("cjk")  # this is the "Droid Sans Fallback" font
FONTNAME = "myfont"  # its reference name in the page
DEVANAGARI_FONTNAME = "devanagari_font"
DEVANAGARI_SCRIPT = pymupdf.mupdf.UCDN_SCRIPT_DEVANAGARI
REPLACEMENT_UNICODE = chr(0xFFFD)  # Unicode Replacement Character
STROKED_TEXT = pymupdf.mupdf.FZ_STEXT_STROKED
FILLED_TEXT = pymupdf.mupdf.FZ_STEXT_FILLED

_devanagari_font = None


class OCRFontCoverageError(RuntimeError):
    """Raised when no declared write-back font covers an OCR string."""


def ocr_text(span) -> bool:
    if (
        span["alpha"]
        or (span["char_flags"] & STROKED_TEXT)
        or (span["char_flags"] & FILLED_TEXT)
    ):
        return False
    return True


def adjust_width(text, fontsize, rect, font=FONT):
    """Compute matrix to adjust text width.

    We must ensure that inserted text has the width of the rectangle.
    The computed matrix will do this scaling.
    """
    tl = font.text_length(text, fontsize)
    if tl > 0:
        return pymupdf.Matrix(rect.width / tl, 1)
    return pymupdf.Matrix(1, 1)


def _contains_devanagari(text):
    return any(0x0900 <= ord(char) <= 0x097F for char in text)


def _font_covers(font, text):
    """Return whether *font* covers every non-control codepoint in *text*."""
    return all(
        unicodedata.category(char) == "Cc" or font.has_glyph(ord(char)) != 0
        for char in text
    )


def _get_devanagari_font():
    """Lazily load MuPDF's built-in Noto Serif Devanagari font."""
    global _devanagari_font
    if _devanagari_font is None:
        font = pymupdf.Font(script=DEVANAGARI_SCRIPT)
        if not _font_covers(font, "".join(map(chr, range(0x0900, 0x0980)))):
            raise OCRFontCoverageError("MuPDF Devanagari font is incomplete")
        _devanagari_font = font
    return _devanagari_font


def _select_writeback_font(text):
    """Return the declared write-back font and page resource for an OCR string.

    Existing RapidOCR write-back has always used the CJK font without a
    preflight coverage check.  Preserve that path exactly for strings that do
    not contain Devanagari: MuPDF's glyph probe is not authoritative for every
    legacy OCR result (for example U+2206).  The stricter, glyph-complete
    choice is only needed for strings which require the Devanagari fallback.
    """
    if not _contains_devanagari(text):
        return FONT, FONTNAME

    if "\x00" in text or REPLACEMENT_UNICODE in text:
        raise OCRFontCoverageError(
            "OCR output contains a forbidden control or replacement glyph"
        )
    if _font_covers(FONT, text):
        return FONT, FONTNAME
    if _contains_devanagari(text):
        font = _get_devanagari_font()
        if _font_covers(font, text):
            return font, DEVANAGARI_FONTNAME
    raise OCRFontCoverageError("no declared write-back font covers OCR output")


def _grapheme_clusters(text):
    """Return the write-back clusters that must not be split between fonts.

    OCR strings are already Unicode text, so this intentionally needs only the
    cluster extensions relevant to the two declared fonts. Combining marks,
    Devanagari virama, variation selectors, and join controls stay with the
    preceding base. A virama or ZWJ also keeps the following base in that
    cluster; ZWNJ remains with its preceding base but breaks the conjunct.
    """
    clusters = []
    attach_next = False
    for char in text:
        codepoint = ord(char)
        variation_selector = 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF
        extender = (
            unicodedata.category(char).startswith("M")
            or codepoint in (0x094D, 0x200C, 0x200D)
            or variation_selector
        )
        if not clusters:
            clusters.append(char)
        elif extender or attach_next:
            clusters[-1] += char
        else:
            clusters.append(char)
        attach_next = codepoint in (0x094D, 0x200D)
    return clusters


def _plan_mixed_devanagari_runs(text):
    """Choose maximal CJK/Devanagari font runs for a valid mixed string.

    The dynamic program minimizes font transitions. If multiple solutions have
    the same transition count, the lexicographically first CJK-preferred
    selection wins, which makes the legacy CJK choice deterministic whenever a
    cluster is covered by both declared fonts.
    """
    devanagari_font = _get_devanagari_font()
    candidates = []
    for cluster in _grapheme_clusters(text):
        choices = []
        if _font_covers(FONT, cluster):
            choices.append((FONT, FONTNAME))
        if _font_covers(devanagari_font, cluster):
            choices.append((devanagari_font, DEVANAGARI_FONTNAME))
        if not choices:
            raise OCRFontCoverageError("no declared write-back font covers OCR cluster")
        candidates.append((cluster, choices))

    # Each state stores (transition_count, CJK-preference tuple, selected runs).
    states = {}
    for cluster, choices in candidates:
        next_states = {}
        for font, fontname in choices:
            preference = 0 if fontname == FONTNAME else 1
            if not states:
                value = (0, (preference,), [(cluster, font, fontname)])
                next_states[fontname] = value
                continue
            for previous_name, (changes, preferences, selected) in states.items():
                value = (
                    changes + (previous_name != fontname),
                    preferences + (preference,),
                    selected + [(cluster, font, fontname)],
                )
                old = next_states.get(fontname)
                if old is None or value[:2] < old[:2]:
                    next_states[fontname] = value
        states = next_states

    _changes, _preferences, selected = min(states.values(), key=lambda value: value[:2])
    runs = []
    for cluster, font, fontname in selected:
        if runs and runs[-1][2] == fontname:
            runs[-1] = (runs[-1][0] + cluster, font, fontname)
        else:
            runs.append((cluster, font, fontname))
    return runs


def _plan_writeback_runs(text):
    """Return the existing single-font plan or a safe mixed-font plan."""
    if not _contains_devanagari(text):
        # Keep every legacy no-Devanagari decision and write-back path exact.
        font, fontname = _select_writeback_font(text)
        return [(text, font, fontname)]

    if "\x00" in text or REPLACEMENT_UNICODE in text:
        raise OCRFontCoverageError("OCR output contains a forbidden control or replacement glyph")
    if _font_covers(FONT, text):
        return [(text, FONT, FONTNAME)]
    devanagari_font = _get_devanagari_font()
    if _font_covers(devanagari_font, text):
        return [(text, devanagari_font, DEVANAGARI_FONTNAME)]
    return _plan_mixed_devanagari_runs(text)


def _prepare_writeback(text, rect):
    """Preflight all font runs and their finite natural widths before mutation."""
    fontsize = float(rect.height)
    if not math.isfinite(fontsize) or fontsize <= 0 or not math.isfinite(float(rect.width)) or rect.width <= 0:
        raise OCRFontCoverageError("OCR write-back rectangle has no finite positive size")
    runs = []
    natural_width = 0.0
    for run_text, font, fontname in _plan_writeback_runs(text):
        width = float(font.text_length(run_text, fontsize))
        if not math.isfinite(width) or width <= 0:
            raise OCRFontCoverageError("OCR write-back font run has no finite positive width")
        natural_width += width
        runs.append((run_text, font, fontname, width))
    if not math.isfinite(natural_width) or natural_width <= 0:
        raise OCRFontCoverageError("OCR write-back has no finite positive natural width")
    return runs, natural_width


def _insert_writeback(page, rect, text, prepared, inserted_fontnames):
    """Insert a preflighted plan, preserving the existing one-font path exactly."""
    runs, natural_width = prepared
    for _run_text, font, fontname, _width in runs:
        if fontname not in inserted_fontnames:
            page.insert_font(fontname=fontname, fontbuffer=font.buffer)
            inserted_fontnames.add(fontname)

    fontsize = rect.height
    baseline = rect.bl + (0, -0.2 * fontsize)
    if len(runs) == 1:
        # This is precisely the prior selected-font insertion operation.
        _run_text, font, fontname, _width = runs[0]
        mat = adjust_width(text, fontsize, rect, font=font)
        page.insert_text(
            baseline,
            text,
            fontsize=fontsize,
            fontname=fontname,
            morph=(rect.bl, mat),
        )
        return

    scale = rect.width / natural_width
    if not math.isfinite(scale) or scale <= 0:
        raise OCRFontCoverageError("OCR write-back scale is not finite and positive")
    cursor = baseline
    for run_text, _font, fontname, width in runs:
        page.insert_text(
            cursor,
            run_text,
            fontsize=fontsize,
            fontname=fontname,
            morph=(cursor, pymupdf.Matrix(scale, 1)),
        )
        cursor += (width * scale, 0)


# prepare for more advanced use of Tesseract by checking a function signature
sig = inspect.signature(pymupdf.Pixmap.pdfocr_tobytes)
USE_TESS_OPTIONS = "options" in sig.parameters


def get_text(pixmap, irect, language="eng"):
    """Use Tesseract to extract text from a given bounding box of the pixmap.

    The irect is expected to contain one line only, so we use
    tessedit_pageseg_mode=7.
    """
    if irect.is_empty:
        return ""
    my_irect = irect
    # these options ensure a much improved Tesseract behavior
    options = "tessedit_pageseg_mode=7,preserve_interword_spaces=1"
    this_pix = pymupdf.Pixmap(pymupdf.csRGB, my_irect)
    this_pix.copy(pixmap, my_irect)
    if USE_TESS_OPTIONS:
        # use options if pymupdf already provides this
        data = this_pix.pdfocr_tobytes(
            language=language,
            tessdata=TESSDATA,
            options=options,
        )
    else:
        data = this_pix.pdfocr_tobytes(
            language=language,
            tessdata=TESSDATA,
        )
    doc = pymupdf.open("pdf", data)
    page = doc[0]
    # escape MD relevant "|"
    return page.get_text().strip().replace("|", r"\|")


def _recognize_detection_boxes(pixmap, detections, language):
    """Recognize detector boxes with the caller's Tesseract language."""
    results = []
    for box, _score in detections:
        irect = pymupdf.IRect(
            min(point[0] for point in box),
            min(point[1] for point in box),
            max(point[0] for point in box),
            max(point[1] for point in box),
        )
        results.append((irect, get_text(pixmap, irect, language=language)))
    return results


def exec_ocr_detection(page, det_only, dpi=150, language="eng", keep_ocr_text=False):
    """This callback function performs OCR on the given page.

    It uses the "detection-only" function of some OCR engine. This function is
    expected to identify text regions and return bounding boxes.
    The actual text recognition is performed by Tesseract OCR, which is expected to be
    installed and available in the system path.
    """

    if TESSDATA is None:
        raise RuntimeError("Tesseract unavailable.")

    if not callable(det_only):
        raise RuntimeError("OCR engine unavailable - no detection callable provided.")

    """
    We ensure that legible extractable text is excluded from OCR. We render
    the page without "good" text and perform OCR on the rest.
    """
    displaylist = page.get_displaylist()
    stextpage = displaylist.get_textpage(flags=pymupdf.TEXT_ACCURATE_BBOXES)
    textpage = pymupdf.TextPage(stextpage)
    text_blocks = textpage.extractDICT()["blocks"]

    # get bboxes with multiple text categories on page
    spans = []  # bboxes with good text
    fffd_spans = []  # boxes with illegible text
    ocr_spans = []  # boxes with old OCR text
    for b in text_blocks:
        for l in b["lines"]:
            for s in l["spans"]:
                if ocr_text(s):
                    ocr_spans.append(s["bbox"])
                elif REPLACEMENT_UNICODE in s["text"]:
                    fffd_spans.append(s["bbox"])
                else:
                    # for removal of good text regions
                    spans.append(s["bbox"])
    if ocr_spans and keep_ocr_text:
        # If there are already OCR spans and the user wants to keep them, we skip OCR.
        # This is because we cannot distinguish between "good" text and "bad" OCR text.
        return

    # make a Pixmap without "good" text
    pix, empty = get_pixmap(displaylist, dpi=dpi, rects=spans, empty_threshold=250)
    if empty:
        return  # nothing to OCR, the page is empty after removing good text

    # For converting ENGINE box coordinates to page coordinates
    matrix = pymupdf.Rect(pix.irect).torect(page.rect)

    # make numpy array from pixmap
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height,
        pix.width,
        3,
    )
    """
    This calls the detection-only function of the OCR engine.
    """
    result = det_only(img)
    if not result:
        return
    if len(result[0]) != 2:
        raise RuntimeError(
            "Detection-only function must return a list of (box, score) tuples."
        )

    # Execute Tesseract's text Recognizer
    # List of Tesseract text results
    writeback_items = []

    for box, score in result:
        irect = pymupdf.IRect(
            min(p[0] for p in box),
            min(p[1] for p in box),
            max(p[0] for p in box),
            max(p[1] for p in box),
        )
        text = get_text(pix, irect, language=language)
        if not text.strip():
            continue
        rect = pymupdf.Rect(irect) * matrix
        prepared = _prepare_writeback(text, rect)
        writeback_items.append((rect, text, prepared))

    if not writeback_items:
        return

    # All font selection above is a preflight: an uncovered result must not
    # redact existing page text before the callback fails closed.
    # Remove all OCR spans and spans containing a U+FFFD.
    # The OCR engine will restore them according to its best ability.
    redaction_rects = fffd_spans + ocr_spans
    if redaction_rects:
        for sbbox in redaction_rects:
            page.add_redact_annot(sbbox)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )

    # insert the OCR font into the page
    page.insert_font(fontname=FONTNAME, fontbuffer=FONT.buffer)
    inserted_fontnames = {FONTNAME}

    for rect, text, prepared in writeback_items:
        _insert_writeback(page, rect, text, prepared, inserted_fontnames)


def exec_ocr_full(page, full_ocr, dpi=150, language=None, keep_ocr_text=False):
    """OCR callback with flexible OCR engine backend."""

    if not callable(full_ocr):
        raise RuntimeError("OCR engine is unavailable - no callable provided.")

    """
    We ensure that legible extractable text is excluded from OCR. We render
    the page without "good" text and perform OCR on the rest.
    """
    displaylist = page.get_displaylist()
    stextpage = displaylist.get_textpage(flags=pymupdf.TEXT_ACCURATE_BBOXES)
    textpage = pymupdf.TextPage(stextpage)
    text_blocks = textpage.extractDICT()["blocks"]

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
                    # for removal good text regions
                    spans.append(s["bbox"])

    if ocr_spans and keep_ocr_text:
        # If there are already OCR spans and the user wants to keep them, we skip OCR.
        # This is because we cannot distinguish between "good" text and "bad" OCR text.
        return

    # make a Pixmap without "good" text
    pix, empty = get_pixmap(displaylist, dpi=dpi, rects=spans, empty_threshold=250)
    if empty:
        return  # nothing to OCR, the page is empty after removing good text

    # Converts ENGINE box coordinates to page coordinates
    matrix = pymupdf.Rect(pix.irect).torect(page.rect)

    # make numpy array from pixmap
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height,
        pix.width,
        3,
    )

    """
    Call the OCR engine to provide full detection and recognition results.
    """
    result = full_ocr(img)
    if not result:
        return
    if len(result[0]) != 3:
        raise RuntimeError(
            "Full OCR function must return a list of (box, text, score) tuples."
        )

    # Select all write-back fonts before mutating the page. In particular, an
    # uncovered Devanagari-mixed string must fail closed rather than redact
    # existing OCR text and then write an incomplete replacement.
    writeback_items = []
    for box, text, conf in result:
        if not text.strip():
            continue
        rect = (
            pymupdf.Rect(
                min(p[0] for p in box),
                min(p[1] for p in box),
                max(p[0] for p in box),
                max(p[1] for p in box),
            )
            * matrix
        )
        prepared = _prepare_writeback(text, rect)
        writeback_items.append((rect, text, conf, prepared))

    if not writeback_items:
        return

    # Remove all OCR and illegible spans from the page.
    # The OCR engine will restore them according to its best ability.
    redaction_rects = fffd_spans + ocr_spans
    if redaction_rects:
        for sbbox in redaction_rects:
            page.add_redact_annot(sbbox)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )

    # insert the font into the page if not already present
    page.insert_font(fontname=FONTNAME, fontbuffer=FONT.buffer)
    inserted_fontnames = {FONTNAME}

    # Insert recognized text
    for rect, text, conf, prepared in writeback_items:
        _insert_writeback(page, rect, text, prepared, inserted_fontnames)
