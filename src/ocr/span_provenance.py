"""Identify OCR text spans from source PDFs and runtime OCR write-back.

The inexpensive span-local signals cover conventional OCR layers.  Some PDF
producers instead paint ordinary text and then cover it with the scanned page.
Those layers require page context: drawing order, rendered visibility, and a
small recognition check against the pixels at the stored line positions.
"""

from __future__ import annotations

import unicodedata
from typing import Callable, Iterable

import pymupdf
from pymupdf import mupdf

from .get_culled_pixmap import get_pixmap as get_text_culled_pixmap
from .get_culled_pixmap import max_dpi_for_page


OCR_ORIGIN_SOURCE_STANDARD = "source_standard"
OCR_ORIGIN_SOURCE_NONSTANDARD = "source_nonstandard"
OCR_ORIGIN_RUNTIME = "runtime"

TESSERACT_FONT_NAME = "GlyphLessFont"
TEXT_STROKED = mupdf.FZ_STEXT_STROKED
TEXT_FILLED = mupdf.FZ_STEXT_FILLED

# Structural candidate gates.  Recognition remains the final decision, so
# these only keep normal pages away from rendering / OCR work.
MIN_LARGE_IMAGE_PAGE_FRACTION = 0.5
MIN_CHAR_IMAGE_COVERAGE = 0.8
MIN_CANDIDATE_CHARS = 20
MAX_SAMPLE_LINES = 4
MIN_LINE_CHARS = 4
MIN_RECOGNITION_AGREEMENT = 0.5
VISIBILITY_DPI = 72
RECOGNITION_DPI = 150
MAX_RENDER_PIXELS = 10_000_000

LineRecognizer = Callable[[list, str], Iterable[str] | None]
_RUNTIME_OCR_RECTS_ATTR = "_pymupdf4llm_runtime_ocr_rects"
_SOURCE_OCR_CACHE_ATTR = "_pymupdf4llm_source_ocr_cache"


def _base_font_name(span: dict) -> str:
    return str(span.get("font") or "").split("+")[-1]


def is_standard_ocr_span(span: dict) -> bool:
    """Return whether a span carries a conventional local OCR signal."""
    char_flags = span.get("char_flags")
    has_no_paint = char_flags is not None and not int(char_flags) & (
        TEXT_STROKED | TEXT_FILLED
    )
    return (
        _base_font_name(span) == TESSERACT_FONT_NAME
        or int(span.get("alpha", 255)) == 0
        or has_no_paint
    )


def is_ocr_span(span: dict) -> bool:
    """Return the unified OCR provenance bit for an extracted text span.

    Page-aware callers should first use :func:`annotate_page_ocr_spans`.
    Unannotated spans still receive the conventional local-signal fallback.
    """
    if "is_ocr" in span:
        return bool(span["is_ocr"])
    return is_standard_ocr_span(span)


def begin_runtime_ocr_record(page: pymupdf.Page) -> None:
    """Start one producer call, including the valid zero-output case."""
    setattr(page, _RUNTIME_OCR_RECTS_ATTR, [])
    # OCR write-back / redaction mutates page text and invalidates any source
    # layer decision made before the producer ran.
    if hasattr(page, _SOURCE_OCR_CACHE_ATTR):
        delattr(page, _SOURCE_OCR_CACHE_ATTR)


def has_runtime_ocr_record(page: pymupdf.Page) -> bool:
    """Return whether an OCR producer published a result on this page object."""
    return hasattr(page, _RUNTIME_OCR_RECTS_ATTR)


def record_runtime_ocr_rects(page: pymupdf.Page, rects) -> None:
    """Record OCR producer output regions for this in-process page object."""
    new_rects = [tuple(pymupdf.Rect(rect)) for rect in rects]
    previous = list(getattr(page, _RUNTIME_OCR_RECTS_ATTR, ()))
    previous.extend(new_rects)
    setattr(page, _RUNTIME_OCR_RECTS_ATTR, previous)
    if new_rects and hasattr(page, _SOURCE_OCR_CACHE_ATTR):
        delattr(page, _SOURCE_OCR_CACHE_ATTR)


def get_runtime_ocr_rects(page: pymupdf.Page) -> tuple:
    """Return regions written by an OCR producer during the current parse."""
    return tuple(getattr(page, _RUNTIME_OCR_RECTS_ATTR, ()))


def _area(rect) -> float:
    value = pymupdf.Rect(rect)
    return max(0.0, value.width) * max(0.0, value.height)


def _coverage(inner, outer) -> float:
    denominator = _area(inner)
    if not denominator:
        return 0.0
    return _area(pymupdf.Rect(inner) & pymupdf.Rect(outer)) / denominator


def _compact(text: str) -> str:
    return "".join(
        char.casefold()
        for char in unicodedata.normalize("NFC", str(text))
        if char.isalnum()
    )


def _agreement(left: str, right: str) -> float:
    left = _compact(left)
    right = _compact(right)
    left_trigrams = {
        left[index : index + 3] for index in range(max(0, len(left) - 2))
    }
    right_trigrams = {
        right[index : index + 3] for index in range(max(0, len(right) - 2))
    }
    union = left_trigrams | right_trigrams
    return len(left_trigrams & right_trigrams) / len(union) if union else 1.0


def _iter_spans(blocks):
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", ()):
            for span in line.get("spans", ()):
                yield span


def _trace_text(span: dict) -> str:
    return "".join(chr(char[0]) for char in span.get("chars", ()))


def _trace_is_standard_ocr(span: dict) -> bool:
    return (
        _base_font_name(span) == TESSERACT_FONT_NAME
        or int(span.get("type", 3)) == 3
        or float(span.get("opacity", 0.0)) <= 0.0
    )


def _hidden_text_candidates(page: pymupdf.Page) -> tuple[list[dict], float]:
    """Return painted trace spans covered by a later large image."""
    page_area = _area(page.rect)
    if not page_area:
        return [], 0.0
    image_ops = []
    for seqno, item in enumerate(page.get_bboxlog()):
        if item[0] != "fill-image":
            continue
        bbox = pymupdf.Rect(item[1]) & page.rect
        if _area(bbox) / page_area >= MIN_LARGE_IMAGE_PAGE_FRACTION:
            image_ops.append((seqno, bbox))
    if not image_ops:
        return [], 0.0

    candidates = []
    candidate_chars = 0
    ordinary_chars = 0
    for span in page.get_texttrace():
        if _trace_is_standard_ocr(span):
            continue
        text = _trace_text(span)
        relevant = [
            char_info
            for char, char_info in zip(text, span.get("chars", ()))
            if not char.isspace()
        ]
        if not relevant:
            continue
        ordinary_chars += len(relevant)
        covered = sum(
            any(
                image_seqno > int(span["seqno"])
                and _coverage(char_info[3], image_bbox)
                >= MIN_CHAR_IMAGE_COVERAGE
                for image_seqno, image_bbox in image_ops
            )
            for char_info in relevant
        )
        if covered / len(relevant) < MIN_CHAR_IMAGE_COVERAGE:
            continue
        candidates.append(
            {
                "bbox": pymupdf.Rect(span["bbox"]),
                "text": text,
                "seqno": int(span["seqno"]),
            }
        )
        candidate_chars += covered
    if candidate_chars < MIN_CANDIDATE_CHARS:
        return [], 0.0
    return candidates, candidate_chars / ordinary_chars if ordinary_chars else 0.0


def _same_render_without_text(page: pymupdf.Page, candidates: list[dict]) -> bool:
    """Verify that candidate text makes no contribution to the final pixels."""
    dpi = min(
        VISIBILITY_DPI,
        max_dpi_for_page(page.rect, max_pixels=MAX_RENDER_PIXELS),
    )
    if dpi <= 0:
        return False
    full = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    culled, _empty = get_text_culled_pixmap(
        page.get_displaylist(),
        dpi=dpi,
        rects=[candidate["bbox"] for candidate in candidates],
    )
    return (
        full.width == culled.width
        and full.height == culled.height
        and full.n == culled.n
        and full.samples == culled.samples
    )


def _candidate_matches_span(span: dict, candidates: list[dict]) -> bool:
    span_rect = pymupdf.Rect(span["bbox"])
    span_area = _area(span_rect)
    if not span_area:
        return False
    for candidate in candidates:
        candidate_rect = candidate["bbox"]
        intersection = _area(span_rect & candidate_rect)
        if not intersection:
            continue
        smaller = min(span_area, _area(candidate_rect))
        if smaller and intersection / smaller >= 0.25:
            return True
    return False


def _span_matches_rects(span: dict, rects) -> bool:
    span_rect = pymupdf.Rect(span["bbox"])
    span_area = _area(span_rect)
    if not span_area:
        return False
    for rect in rects:
        rect = pymupdf.Rect(rect)
        intersection = _area(span_rect & rect)
        smaller = min(span_area, _area(rect))
        if smaller and intersection / smaller >= 0.5:
            return True
    return False


def _store_source_cache(
    page: pymupdf.Page,
    language: str,
    result: dict,
    candidates=(),
    candidate_char_fraction: float = 0.0,
) -> None:
    nonstandard_result = {
        key: value
        for key, value in result.items()
        if key not in {
            "source_standard_spans",
            "source_nonstandard_spans",
            "runtime_spans",
        }
    }
    setattr(
        page,
        _SOURCE_OCR_CACHE_ATTR,
        {
            "language": language,
            "result": nonstandard_result,
            # Text extraction flags can shift span bboxes slightly between
            # OCR preflight, analysis and final extraction. Cache stable trace
            # geometry instead of identities from one extractDICT call.
            "candidate_bboxes": [tuple(item["bbox"]) for item in candidates],
            "all_ordinary_text_is_candidate": candidate_char_fraction >= 0.95,
        },
    )


def _candidate_lines(
    blocks,
    candidates: list[dict],
    candidate_char_fraction: float,
):
    lines = []
    matched_spans = []
    # Most scan-backed OCR pages put the complete hidden text layer below one
    # page image.  Avoid an O(extracted_spans * trace_spans) geometry join for
    # that common case.  A coarse y-grid handles genuinely mixed pages.
    all_ordinary_text_is_candidate = candidate_char_fraction >= 0.95
    y_grid = {}
    grid_size = 24.0
    if not all_ordinary_text_is_candidate:
        for index, candidate in enumerate(candidates):
            rect = candidate["bbox"]
            first = int(rect.y0 // grid_size)
            last = int(rect.y1 // grid_size)
            for bucket in range(first, last + 1):
                y_grid.setdefault(bucket, []).append(index)
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", ()):
            spans = []
            for span in line.get("spans", ()):
                if is_standard_ocr_span(span) or not str(
                    span.get("text") or ""
                ).strip():
                    continue
                if all_ordinary_text_is_candidate:
                    spans.append(span)
                    continue
                rect = pymupdf.Rect(span["bbox"])
                candidate_indices = set()
                for bucket in range(
                    int(rect.y0 // grid_size), int(rect.y1 // grid_size) + 1
                ):
                    candidate_indices.update(y_grid.get(bucket, ()))
                nearby = [candidates[index] for index in candidate_indices]
                if _candidate_matches_span(span, nearby):
                    spans.append(span)
            if not spans:
                continue
            matched_spans.extend(spans)
            text = "".join(str(span.get("text") or "") for span in spans).strip()
            if len(_compact(text)) < MIN_LINE_CHARS:
                continue
            bbox = pymupdf.Rect(spans[0]["bbox"])
            for span in spans[1:]:
                bbox |= pymupdf.Rect(span["bbox"])
            lines.append((bbox, text))
    return lines, matched_spans


def _default_line_recognizer(crops: list, language: str):
    """Recognize a few line crops while preserving optional dependencies."""
    try:
        from .detect_rapidocr import detect_rapidocr_backend

        backend = detect_rapidocr_backend()
        if backend == "rapidocr":
            from .rapidocr_391_backend import recognize_crops

            return list(recognize_crops(crops))
        if backend == "rapidocr_onnxruntime":
            from .rapidocr_onnx_backend import recognize_crops

            return list(recognize_crops(crops))
    except Exception:
        pass

    # Tesseract is the dependency-free fallback when PyMuPDF can find tessdata.
    try:
        tessdata = pymupdf.get_tessdata()
        if tessdata is None:
            return None
        outputs = []
        for crop in crops:
            height, width = crop.shape[:2]
            pixmap = pymupdf.Pixmap(
                pymupdf.csRGB,
                width,
                height,
                crop[:, :, :3].tobytes(),
                False,
            )
            kwargs = {"language": language, "tessdata": tessdata}
            try:
                data = pixmap.pdfocr_tobytes(
                    **kwargs,
                    options="tessedit_pageseg_mode=7,preserve_interword_spaces=1",
                )
            except TypeError:
                data = pixmap.pdfocr_tobytes(**kwargs)
            with pymupdf.open("pdf", data) as document:
                outputs.append(document[0].get_text().strip())
        return outputs
    except Exception:
        return None


def _recognition_check(
    page: pymupdf.Page,
    lines,
    language: str,
    line_recognizer: LineRecognizer | None,
):
    selected = sorted(lines, key=lambda item: len(_compact(item[1])), reverse=True)[
        :MAX_SAMPLE_LINES
    ]
    if not selected:
        return None, 0
    dpi = min(
        RECOGNITION_DPI,
        max_dpi_for_page(page.rect, max_pixels=MAX_RENDER_PIXELS),
    )
    if dpi <= 0:
        return None, 0
    pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    import numpy as np

    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )[:, :, :3]
    page_to_pixmap = page.rect.torect(pymupdf.Rect(pixmap.irect))
    crops = []
    expected = []
    for rect, text in selected:
        crop = pymupdf.IRect(rect * page_to_pixmap)
        crop = pymupdf.IRect(
            crop.x0 - 2,
            crop.y0 - 2,
            crop.x1 + 2,
            crop.y1 + 2,
        ) & pixmap.irect
        if crop.width < 2 or crop.height < 2:
            continue
        crops.append(image[crop.y0 : crop.y1, crop.x0 : crop.x1].copy())
        expected.append(text)
    if not crops:
        return None, 0
    recognizer = line_recognizer or _default_line_recognizer
    observed = recognizer(crops, language)
    if observed is None:
        return None, len(crops)
    observed = [str(value or "") for value in observed]
    if len(observed) != len(expected):
        return None, len(crops)
    return _agreement("\n".join(expected), "\n".join(observed)), len(crops)


def annotate_page_ocr_spans(
    page: pymupdf.Page,
    blocks,
    *,
    runtime_ocr_applied: bool = False,
    runtime_ocr_rects=None,
    language: str = "eng",
    line_recognizer: LineRecognizer | None = None,
) -> dict:
    """Add unified ``is_ocr`` / ``ocr_origin`` fields to text spans.

    ``runtime_ocr_applied`` is orchestration provenance: conventional hidden
    spans extracted immediately after this package ran OCR receive origin
    ``runtime``.  Existing conventional layers receive ``source_standard``.
    Non-standard source layers are verified conservatively and page-locally.
    """
    if runtime_ocr_rects is None:
        recorded_runtime_rects = get_runtime_ocr_rects(page)
        has_explicit_runtime_rects = has_runtime_ocr_record(page)
    else:
        recorded_runtime_rects = tuple(runtime_ocr_rects)
        has_explicit_runtime_rects = True

    standard_spans = 0
    runtime_spans = 0
    for span in _iter_spans(blocks):
        is_recorded_runtime = _span_matches_rects(
            span, recorded_runtime_rects
        )
        if is_recorded_runtime:
            span["is_ocr"] = True
            span["ocr_origin"] = OCR_ORIGIN_RUNTIME
            runtime_spans += 1
        elif is_standard_ocr_span(span):
            # A third-party callback may not publish regions. Preserve the
            # older page-level fallback only when no explicit producer record
            # exists at all.
            is_runtime_fallback = (
                runtime_ocr_applied and not has_explicit_runtime_rects
            )
            span["is_ocr"] = True
            span["ocr_origin"] = (
                OCR_ORIGIN_RUNTIME
                if is_runtime_fallback
                else OCR_ORIGIN_SOURCE_STANDARD
            )
            runtime_spans += int(is_runtime_fallback)
            standard_spans += int(not is_runtime_fallback)
        else:
            span["is_ocr"] = False
            span["ocr_origin"] = None

    result = {
        "source_standard_spans": standard_spans,
        "source_nonstandard_spans": 0,
        "runtime_spans": runtime_spans,
        "nonstandard_candidate_spans": 0,
        "nonstandard_candidate_char_fraction": 0.0,
        "nonstandard_sampled_lines": 0,
        "nonstandard_agreement": None,
        "nonstandard_status": "no_candidate",
    }
    cached = getattr(page, _SOURCE_OCR_CACHE_ATTR, None)
    if cached and cached.get("language") == language:
        candidate_bboxes = [
            {"bbox": pymupdf.Rect(rect)}
            for rect in cached["candidate_bboxes"]
        ]
        matched_count = 0
        for span in _iter_spans(blocks):
            if span.get("is_ocr") or not str(span.get("text") or "").strip():
                continue
            if not cached["all_ordinary_text_is_candidate"] and not (
                _candidate_matches_span(span, candidate_bboxes)
            ):
                continue
            span["is_ocr"] = True
            span["ocr_origin"] = OCR_ORIGIN_SOURCE_NONSTANDARD
            matched_count += 1
        result.update(cached["result"])
        result["source_nonstandard_spans"] = matched_count
        return result
    try:
        candidates, candidate_char_fraction = _hidden_text_candidates(page)
        result["nonstandard_candidate_spans"] = len(candidates)
        result["nonstandard_candidate_char_fraction"] = candidate_char_fraction
        if not candidates:
            _store_source_cache(page, language, result)
            return result
        if not _same_render_without_text(page, candidates):
            result["nonstandard_status"] = "text_contributes_to_render"
            _store_source_cache(page, language, result)
            return result
        lines, matched_spans = _candidate_lines(
            blocks,
            candidates,
            candidate_char_fraction,
        )
        agreement, sample_count = _recognition_check(
            page,
            lines,
            language,
            line_recognizer,
        )
        result["nonstandard_sampled_lines"] = sample_count
        result["nonstandard_agreement"] = agreement
        if agreement is None:
            result["nonstandard_status"] = "recognizer_unavailable"
            return result
        if agreement < MIN_RECOGNITION_AGREEMENT:
            result["nonstandard_status"] = "text_image_mismatch"
            _store_source_cache(page, language, result)
            return result
        for span in matched_spans:
            span["is_ocr"] = True
            span["ocr_origin"] = OCR_ORIGIN_SOURCE_NONSTANDARD
        result["source_nonstandard_spans"] = len(matched_spans)
        result["nonstandard_status"] = "confirmed"
        _store_source_cache(
            page,
            language,
            result,
            candidates,
            candidate_char_fraction,
        )
        return result
    except Exception as error:
        # Provenance detection is conservative: a failure must never relabel
        # native text or prevent document conversion.
        result["nonstandard_status"] = "error"
        result["nonstandard_error"] = f"{type(error).__name__}: {error}"
        return result
