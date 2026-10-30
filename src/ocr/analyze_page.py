import os
import pprint
from pathlib import Path

import numpy as np
import pymupdf
from pymupdf import mupdf

from .compute_ocr_features import FEATURE_NAMES, compute_features

from .page_state import (
    FLAGS,
    TYPE3_FONT_NAME,
    TESSERACT_FONT_NAME,
    REPLACEMENT_CHARACTER,
    TEXT_STROKED,
    TEXT_FILLED,
    BLOCK_TEXT,
    BLOCK_IMAGE,
    BLOCK_VECTOR,
    collect_page_state,
    is_ocr_span,
    intersect_rects,
    join_rects,
    bbox_is_empty,
)

GRAY = mupdf.fz_device_gray()
# Thresholds
BAD_CHAR_THRESHOLD = 0.10  # >=10% bad chars suggests OCR

# Return 'needs_ocr' as True if probability is at least this (default 0.93):
OCR_MODEL_THRESHOLD = int(os.getenv("PYMUPDF_OCR_MODEL_THRESHOLD", 93)) / 100

# The model file is in our folder!
_MODEL_PATH = Path(__file__).parent / "ocr_decision_model.onnx"
_session = None
_input_name: str = ""


def _get_session():
    global _session, _input_name
    if _session is None:
        import onnxruntime as ort  # deferred: expensive import

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        _session = ort.InferenceSession(str(_MODEL_PATH), opts)
        _input_name = _session.get_inputs()[0].name
    return _session, _input_name


def predict_ocr_probability(features: dict) -> float:
    """Return the probability that these features require OCR."""
    session, input_name = _get_session()
    x = np.array([[features[f] for f in FEATURE_NAMES]], dtype=np.float32)
    probas = session.run(None, {input_name: x})[1]  # output[1] = probability
    return float(probas[0, 1])


def check_images(image_blocks, prob, threshold=OCR_MODEL_THRESHOLD):
    """Stage 2: Separate OCR check for large images.

    Currently not in use.

    Args:
        image_blocks: (list) image blocks in page.get_text("dict") format.
        prob: (float) OCR probability for rendered full page
        threshold: (float) probability threshold. If larger recommend OCR.

    Returns:
        bool (do OCR), probability, check count
    """
    best_prob = prob  # probability for rendered page

    for i, block in enumerate(image_blocks):
        # Iterate image blocks.
        # Make a 128x128 GRAY pixmap of the image.
        pix = pymupdf.Pixmap(block["image"])
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)
        if block["mask"]:  # Add mask if present
            mask = pymupdf.Pixmap(block["mask"])
            try:
                pix = pymupdf.Pixmap(pix, mask)
                pix = pymupdf.Pixmap(pix, 0)
            except:
                mask = None
        pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
        pix = pymupdf.Pixmap(pix, 128, 128)  # downscale Pixmap

        # compute the features and predict OCR probability
        features = compute_features([block], block["bbox"], pix)
        img_prob = predict_ocr_probability(features)
        best_prob = max(best_prob, img_prob)

        if best_prob >= threshold:
            return True, best_prob, i  # Early Exit if OCR is probable

    return False, best_prob, i


def analyze_page(
    page,
    blocks=None,
    replace_ocr=False,
    ocr_dpi=200,
    stats=None,
    ignore_existing_ocr=False,
):
    """Compatibility API; correction owns state and existing-layer policy."""
    state = collect_page_state(page, blocks)
    from .legacy_policy import legacy_existing_ocr_result

    decision = legacy_existing_ocr_result(
        page, state, replace_ocr, ignore_existing_ocr, stats
    )
    return decision if decision is not None else analyze_state(page, state, stats)


def analyze_state(page, state, stats=None):
    """P2 heuristics plus ODM; preservation policy is handled by the caller."""
    analysis = dict(state.analysis)
    if bbox_is_empty(analysis["covered"]):
        return {**analysis, "needs_ocr": False, "reason": None, "probability": None}
    blocks = state.blocks
    page_rect = page.rect
    chars_total, chars_bad = state.chars_total, state.chars_bad
    txt_area, bad_areas = state.txt_area, state.bad_areas
    img_area, vec_norects = state.img_area, state.vec_norects
    image_blocks = state.image_blocks
    if (
        chars_total
        and txt_area
        and (chars_bad / chars_total > BAD_CHAR_THRESHOLD)
        and (bad_areas / txt_area > BAD_CHAR_THRESHOLD)
    ):
        return {
            **analysis,
            "needs_ocr": True,
            "reason": "chars_bad",
            "probability": None,
        }
    if not vec_norects and (not img_area):
        return {**analysis, "needs_ocr": False, "reason": None, "probability": None}
    if isinstance(stats, dict):
        stats["model_check"] = stats.get("model_check", 0) + 1
    features = compute_features(blocks, page_rect, page)
    if isinstance(stats, dict) and stats.get("show_features"):
        pprint.pp(features)
    prob = predict_ocr_probability(features)
    needs_ocr = prob >= OCR_MODEL_THRESHOLD
    if needs_ocr:
        return {
            **analysis,
            "needs_ocr": needs_ocr,
            "reason": "img_text",
            "probability": prob,
        }
    if image_blocks:
        needs_ocr, prob, check_count = check_images(
            image_blocks, prob, OCR_MODEL_THRESHOLD
        )
        if isinstance(stats, dict):
            stats["img_checks"] = stats.get("img_checks", 0) + check_count
    return {
        **analysis,
        "needs_ocr": needs_ocr,
        "reason": "img_text" if needs_ocr else None,
        "probability": prob,
    }


if __name__ == "__main__":
    """For edbugging purposes."""
    import pprint
    import sys
    import time

    duration = 0
    ocr_pages = []
    STATISTICS = {"show_features": True}
    doc = pymupdf.open(sys.argv[1])
    print(f"OCR-Analysis for {doc.name=}")
    for page in doc:
        t0 = time.perf_counter()
        analysis = analyze_page(page, stats=STATISTICS)
        duration += time.perf_counter() - t0
        if analysis["needs_ocr"]:
            ocr_pages.append((page.number, analysis["reason"]))
    print(
        f"NEW: duration: {duration:.2f}s, per page: {duration/len(doc):.4f}s OCR: {len(ocr_pages)} pages ({len(ocr_pages)/len(doc)*100:.2f}%)"
    )
    out = open(doc.name + ".txt", "w")
    pprint.pp(ocr_pages, width=200, stream=out)
    out.close()
    pprint.pp(STATISTICS)
