"""Verify retained OCR text before selective reuse with optional RapidOCR support."""

from __future__ import annotations

import json
import os
import time
import unicodedata
from pathlib import Path

import pymupdf

from pymupdf4llm.ocr import OCRMode
from pymupdf4llm.ocr.analyze_page import is_ocr_span
from pymupdf4llm.ocr.detect_rapidocr import detect_rapidocr_backend


def _compact(text: str) -> str:
    return "".join(
        char.casefold()
        for char in unicodedata.normalize("NFC", text)
        if char.isalnum()
    )


def _agreement(left: str, right: str) -> float:
    left = _compact(left)
    right = _compact(right)
    left_trigrams = {left[index : index + 3] for index in range(max(0, len(left) - 2))}
    right_trigrams = {right[index : index + 3] for index in range(max(0, len(right) - 2))}
    return len(left_trigrams & right_trigrams) / len(left_trigrams | right_trigrams) if left_trigrams or right_trigrams else 1.0


def _sample_indices(count: int) -> list[int]:
    if count <= 4:
        return list(range(count))
    return sorted({round(index * (count - 1) / 3) for index in range(4)})


def _event(page, source: str, page_number: int) -> dict:
    return {
        "source": source,
        "page_number": page_number,
        "eligible": False,
        "ineligible_reason": None,
        "sampled_line_count": 0,
        "agreement_jaccard3": None,
        "selected": False,
        "preflight_wall_ns": 0,
        "replacement_ocr_wall_ns": 0,
        "preflight_full_ocr_calls": 0,
        "normal_full_ocr_calls": 0,
        "v3_recovery_full_ocr_calls": 0,
        "total_full_ocr_calls": 0,
        "v3_exact_empty_skipped": False,
        "error": None,
    }


def check(page, *, source: str, page_number: int, use_ocr, ocr_dpi: int, ocr_function, ocr_language: str):
    """Check one outer SELECT_KEEP_OLD page and possibly replace old OCR once."""
    event = _event(page, source, page_number)
    started = time.perf_counter_ns()
    try:
        if use_ocr is not True and use_ocr != OCRMode.SELECT_KEEP_OLD:
            event["ineligible_reason"] = "not_selective_ocr"
            return event
        if ocr_dpi != 150:
            event["ineligible_reason"] = "noncanonical_ocr_dpi"
            return event
        if detect_rapidocr_backend() != "rapidocr":
            event["ineligible_reason"] = "rapidocr_not_active_default"
            return event
        from pymupdf4llm.ocr.rapidocr_api import exec_ocr as default_rapidocr_exec_ocr

        if ocr_function is not default_rapidocr_exec_ocr:
            event["ineligible_reason"] = "nondefault_ocr_callback"
            return event
        import numpy as np
        from pymupdf4llm.ocr.rapidocr_391_backend import recognize_crops

        lines = []
        saw_relevant_text = False
        all_prior_ocr = True
        for block in page.get_text("dict", flags=pymupdf.TEXT_MEDIABOX_CLIP)["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                spans = [span for span in line["spans"] if span["text"].strip()]
                if not spans:
                    continue
                saw_relevant_text = True
                if not all(is_ocr_span(span) for span in spans):
                    all_prior_ocr = False
                lines.append((pymupdf.Rect(line["bbox"]), "".join(span["text"] for span in spans).strip()))
        if not saw_relevant_text:
            event["ineligible_reason"] = "no_relevant_text"
            return event
        if not all_prior_ocr:
            event["ineligible_reason"] = "mixed_or_native_text"
            return event

        event["eligible"] = True
        indices = _sample_indices(len(lines))
        event["sampled_line_count"] = len(indices)
        pix = page.get_pixmap(dpi=150, alpha=False)
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        page_to_pix = page.rect.torect(pymupdf.Rect(pix.irect))
        crops = []
        stored = []
        for index in indices:
            rect, text = lines[index]
            crop = pymupdf.IRect(rect * page_to_pix)
            crop = pymupdf.IRect(crop.x0 - 1, crop.y0 - 1, crop.x1 + 1, crop.y1 + 1) & pix.irect
            if crop.width < 2 or crop.height < 2:
                raise RuntimeError(f"invalid sampled crop at line {index}")
            crops.append(image[crop.y0 : crop.y1, crop.x0 : crop.x1].copy())
            stored.append(text)
        recognized = list(recognize_crops(crops))
        if len(recognized) != len(crops):
            raise RuntimeError("recognition count mismatch")
        event["agreement_jaccard3"] = _agreement("\n".join(stored), "\n".join(recognized))
        if event["agreement_jaccard3"] < 0.5:
            event["selected"] = True
            event["preflight_full_ocr_calls"] = 1
            replacement_started = time.perf_counter_ns()
            try:
                ocr_function(page, dpi=ocr_dpi, language=ocr_language, keep_ocr_text=False)
            except Exception as error:
                event["selected"] = False
                event["preflight_full_ocr_calls"] = 0
                event["error"] = f"replacement_ocr:{type(error).__name__}:{error}"
            finally:
                event["replacement_ocr_wall_ns"] = time.perf_counter_ns() - replacement_started
    except Exception as error:
        event["error"] = f"preflight:{type(error).__name__}:{error}"
    finally:
        event["preflight_wall_ns"] = time.perf_counter_ns() - started
    return event


def emit(event: dict) -> None:
    """Best-effort per-process append only; diagnostic IO never changes extraction."""
    event["total_full_ocr_calls"] = (
        event["preflight_full_ocr_calls"]
        + event["normal_full_ocr_calls"]
        + event["v3_recovery_full_ocr_calls"]
    )
    directory = os.environ.get("PRIOR_OCR_PREFLIGHT_TELEMETRY_DIR")
    if not directory:
        return
    try:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        with (path / f"events.{os.getpid()}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except Exception as error:
        if os.environ.get("PRIOR_OCR_PREFLIGHT_TELEMETRY_STRICT") == "1":
            raise RuntimeError(f"preflight telemetry write failed: {error}") from error
