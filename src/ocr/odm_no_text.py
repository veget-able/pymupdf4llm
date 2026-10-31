"""Render ODM page pixels without main's normal stored text glyphs.

This changes no selection/preservation/replacement policy. Structural features
and embedded-image features still describe the original PDF. No white boxes,
content rewriting, new damage priority, model weights or thresholds are used.
"""

import pymupdf
from pymupdf import mupdf

from .exec_ocr_interface import ocr_text


def render_page_without_normal_text(page, dpi=72):
    """Return a grayscale page pixmap, using the main Rapid span categories.

    Only non-OCR-like spans without U+FFFD enter the glyph exclusion list.
    With an empty list retain the original render, including damaged glyphs;
    this is the unchanged ODM input for a page with no normal text to exclude.
    Images/vectors are not covered or removed. DPI and page geometry are the
    original ODM settings, independent of the later OCR render/pixel cap.
    """
    displaylist = page.get_displaylist()
    textpage = pymupdf.TextPage(
        displaylist.get_textpage(flags=pymupdf.TEXT_ACCURATE_BBOXES)
    )
    rects = [
        span['bbox']
        for block in textpage.extractDICT()['blocks']
        for line in block.get('lines', [])
        for span in line['spans']
        if not ocr_text(span) and '\ufffd' not in span['text']
    ]
    if not rects:
        return page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    matrix = mupdf.fz_make_matrix(dpi / 72, 0, 0, dpi / 72, 0, 0)
    pixmap = mupdf.fz_new_pixmap_from_display_list_culling_text2(
        displaylist, matrix, mupdf.fz_device_gray(), 0,
        [mupdf.ll_fz_make_rect(*rect) for rect in rects],
    )
    result = pymupdf.Pixmap(pixmap, 0)
    result.set_dpi(dpi, dpi)
    return result
