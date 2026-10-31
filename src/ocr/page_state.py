"""Common page state and unchanged stage-specific text rules.

The OR analysis rule, Rapid AND rule and output/Tesseract rules deliberately
retain their approved meanings. This is ownership separation, not a revival
of the removed shared-span predicate or normal-character filter.
"""

import math
from types import MappingProxyType
import pymupdf
from pymupdf import mupdf

FLAGS = (
    pymupdf.TEXT_ACCURATE_BBOXES
    | pymupdf.TEXT_PRESERVE_IMAGES
    | pymupdf.TEXT_COLLECT_VECTORS
)
TYPE3_FONT_NAME = "Type3"
TESSERACT_FONT_NAME = "GlyphLessFont"
REPLACEMENT_CHARACTER = "\ufffd"
TEXT_STROKED = mupdf.FZ_STEXT_STROKED
TEXT_FILLED = mupdf.FZ_STEXT_FILLED
STROKED_TEXT = TEXT_STROKED
FILLED_TEXT = TEXT_FILLED
BLOCK_TEXT = mupdf.FZ_STEXT_BLOCK_TEXT
BLOCK_IMAGE = mupdf.FZ_STEXT_BLOCK_IMAGE
BLOCK_VECTOR = mupdf.FZ_STEXT_BLOCK_VECTOR


def is_ocr_span(span):
    """If this is an OCR text span."""
    return (
        span["font"] == TESSERACT_FONT_NAME
        or span["alpha"] == 0
        or (
            span["char_flags"] & TEXT_STROKED == 0
            and span["char_flags"] & TEXT_FILLED == 0
        )
    )


def is_ocr_text_for_rapid(span) -> bool:
    if (
        span["alpha"]
        or (span["char_flags"] & STROKED_TEXT)
        or (span["char_flags"] & FILLED_TEXT)
    ):
        return False
    return True


def is_ocr_text_for_tesseract(span) -> bool:
    if (span["char_flags"] & STROKED_TEXT) or (span["char_flags"] & FILLED_TEXT):
        return False
    return True


def is_ocr_text_for_output(span) -> bool:
    """Check if text span was created by some OCR engine.

    This is a simplified check: We actually return whether the text was neither
    stroked nor filled. This corresponds to PDF text rendering mode 3, which
    is typically used for OCR text layers. Strictly speaking it can also be
    used for other purposes than OCR. In rare cases some OCR engines might
    use other techniques to ensure the generated text layer is invisible.
    """
    if span["font"] == TESSERACT_FONT_NAME:
        # This is a safe bet for OCR by Tesseract
        return True
    if (span["char_flags"] & pymupdf.mupdf.FZ_STEXT_STROKED) or (
        span["char_flags"] & pymupdf.mupdf.FZ_STEXT_FILLED
    ):
        return False
    return True


def intersect_rects(r1, r2, bbox_only=False):
    """Speedy version using indices."""
    bbox = (max(r1[0], r2[0]), max(r1[1], r2[1]), min(r1[2], r2[2]), min(r1[3], r2[3]))
    return bbox if bbox_only else pymupdf.Rect(*bbox)


def join_rects(r1, r2, bbox_only=False):
    """Speedy version using indices."""
    bbox = (min(r1[0], r2[0]), min(r1[1], r2[1]), max(r1[2], r2[2]), max(r1[3], r2[3]))
    return bbox if bbox_only else pymupdf.Rect(*bbox)


def bbox_is_empty(bbox) -> bool:
    """Speedy version using indices."""
    return bbox[0] >= bbox[2] or bbox[1] >= bbox[3]


class PageState:
    """One correction-owned metadata instance consumed by either selector."""

    def __init__(self, blocks, analysis, context):
        self.blocks = blocks
        self.analysis = MappingProxyType(analysis)
        for name in [
            "chars_total",
            "chars_bad",
            "bad_areas",
            "txt_area",
            "img_area",
            "vec_norects",
            "image_blocks",
            "ocr_span_boxes",
        ]:
            setattr(self, name, context[name])
        self._stored_boxes = None

    @property
    def metadata(self):
        return self.analysis["ocr_spans"], not (
            self.analysis["img_area"] or self.analysis["vec_norects"]
        )

    def render_for_ocr(self, page, dpi=150):
        from .rendering import render_ocr_input

        return render_ocr_input(page, dpi=dpi)

    def stored_character_boxes(self, page):
        if self._stored_boxes is None:
            flags = (
                pymupdf.TEXTFLAGS_RAWDICT
                & ~pymupdf.TEXT_PRESERVE_IMAGES
                & ~pymupdf.TEXT_CID_FOR_UNKNOWN_UNICODE
            )
            raw = page.get_text("rawdict", flags=flags, clip=pymupdf.INFINITE_RECT())
            boxes = []
            for block in raw["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        for char in span["chars"]:
                            value, box = char["c"], char["bbox"]
                            if (
                                not value.strip()
                                or "\ufffd" in value
                                or value.startswith("<cid:")
                            ):
                                continue
                            if (
                                not all(math.isfinite(v) for v in box)
                                or box[2] <= box[0]
                                or box[3] <= box[1]
                            ):
                                continue
                            boxes.append(tuple(box))
            self._stored_boxes = tuple(boxes)
        return self._stored_boxes


def collect_page_state(page, blocks=None):
    if blocks is None:
        blocks = page.get_text("dict", flags=FLAGS, clip=pymupdf.INFINITE_RECT())[
            "blocks"
        ]
    page_rect = page.rect
    img_rect = pymupdf.EMPTY_RECT()
    txt_rect = +img_rect
    vec_rect = +img_rect
    chars_total = 0
    chars_bad = 0
    bad_areas = 0.0
    img_area = 0.0
    txt_area = 0.0
    vec_area = 0.0
    vec_norects = 0
    ocr_spans = 0
    ocr_span_boxes = []
    bad_char_boxes = []
    good_char_boxes = []
    image_blocks = []
    for b in blocks:
        bbox = intersect_rects(page_rect, b["bbox"])
        area = bbox.width * bbox.height
        if not area:
            continue
        if b["type"] == BLOCK_TEXT:
            for l in b["lines"]:
                for s in l["spans"]:
                    sr = intersect_rects(bbox, s["bbox"])
                    sr_area = sr.width * sr.height
                    if not sr_area:
                        continue
                    text = s["text"].strip()
                    if not text or text.isspace():
                        continue
                    chars_total += len(text)
                    if is_ocr_span(s):
                        ocr_spans += 1
                        ocr_span_boxes.append(s["bbox"])
                        continue
                    bad_chars = sum((1 for c in text if c == REPLACEMENT_CHARACTER))
                    chars_bad += bad_chars
                    txt_rect = join_rects(txt_rect, sr)
                    txt_area += sr_area
                    if bad_chars:
                        bad_areas += sr_area
                        bad_char_boxes.append(s["bbox"])
                    else:
                        good_char_boxes.append(s["bbox"])
            continue
        if b["type"] == BLOCK_IMAGE:
            img_rect = join_rects(img_rect, bbox)
            img_area += area
            continue
        if b["type"] == BLOCK_VECTOR:
            vec_rect = join_rects(vec_rect, bbox)
            vec_area += area
            if not b["isrect"]:
                vec_norects += 1
            continue
    covered = img_rect | txt_rect | vec_rect
    if bbox_is_empty(covered):
        return PageState(
            blocks,
            {
                "covered": covered,
                "img_joins": 0.0,
                "img_area": 0.0,
                "txt_joins": 0.0,
                "txt_area": 0.0,
                "vec_joins": 0.0,
                "vec_area": 0.0,
                "vec_norects": 0,
                "chars_total": 0,
                "chars_bad": 0,
                "bad_areas": 0.0,
                "ocr_spans": 0,
                "pixmap": None,
            },
            locals(),
        )
    cover_area = (covered[2] - covered[0]) * (covered[3] - covered[1])
    ocr_spans = ocr_spans if ocr_spans and len(good_char_boxes) == 0 else 0
    analysis = {
        "covered": covered,
        "img_joins": abs(img_rect) / cover_area if cover_area else 0.0,
        "img_area": img_area / cover_area if cover_area else 0.0,
        "txt_joins": abs(txt_rect) / cover_area if cover_area else 0.0,
        "txt_area": txt_area / cover_area if cover_area else 0.0,
        "vec_joins": abs(vec_rect) / cover_area if cover_area else 0.0,
        "vec_area": vec_area / cover_area if cover_area else 0.0,
        "chars_total": chars_total,
        "chars_bad": chars_bad,
        "bad_areas": bad_areas / cover_area if cover_area else 0.0,
        "ocr_spans": ocr_spans,
        "pixmap": None,
        "vec_norects": vec_norects,
    }
    return PageState(blocks, analysis, locals())
