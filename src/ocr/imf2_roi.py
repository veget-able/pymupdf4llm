"""Page-only OCR selection from residual IMF2 text outside stored characters.

This selector does not invoke P2/ODM, Rapid, recognition, or the GNN. Its boxes
never crop or filter downstream OCR. Model and preprocessing are independent
of the layout model currently used by the GNN.
"""

from functools import lru_cache
from pathlib import Path
import math

import numpy as np

from ._imf_preprocess import resize_image, to_gray

TEXT_PROBABILITY = 0.5
STORED_CHARACTER_PADDING = 2
MIN_RESIDUAL_PIXELS = 40
MODEL = Path(__file__).with_name("models") / "feature_imf2.onnx"


@lru_cache(maxsize=1)
def _session():
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    return ort.InferenceSession(str(MODEL), options, providers=["CPUExecutionProvider"])


def stored_character_mask(state, page, shape):
    """Rasterize the common state's eligible stored boxes on the IMF2 grid."""
    mask = np.zeros(shape, np.uint8)
    height, width = shape
    rect = page.rect
    for box in state.stored_character_boxes(page):
        x0 = max(0, min(width, math.floor((box[0] - rect.x0) * width / rect.width)))
        x1 = max(0, min(width, math.ceil((box[2] - rect.x0) * width / rect.width)))
        y0 = max(0, min(height, math.floor((box[1] - rect.y0) * height / rect.height)))
        y1 = max(0, min(height, math.ceil((box[3] - rect.y0) * height / rect.height)))
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = 1
    return mask


def residual_components(text_probability, stored):
    import cv2

    covered = cv2.dilate(
        stored, np.ones((2 * STORED_CHARACTER_PADDING + 1,) * 2, np.uint8)
    )
    residual = ((text_probability >= TEXT_PROBABILITY) & ~covered.astype(bool)).astype(
        np.uint8
    )
    count, _, stats, _ = cv2.connectedComponentsWithStats(residual, connectivity=8)
    return [
        tuple(int(x) for x in stats[i])
        for i in range(1, count)
        if stats[i, cv2.CC_STAT_AREA] >= MIN_RESIDUAL_PIXELS
    ]


def select_page(page, state, dpi=150):
    """Return a page boolean; no page or saved-text mutation."""
    pixmap, empty = state.render_for_ocr(page, dpi=dpi)
    if empty:
        return False
    rgb = np.frombuffer(pixmap.samples, np.uint8).reshape(
        pixmap.height, pixmap.width, 3
    )
    # The fixed low-range guard precedes min/max normalization. Do not add the
    # rejected resize-rounding correction or any new area/coverage threshold.
    gray = to_gray(resize_image(rgb, (300, 300))).astype(np.float32)
    low, high = gray.min(), gray.max()
    if float(high - low) <= 1:
        return False
    tensor = ((gray - low) / (high - low + 1e-8))[None, None]
    session = _session()
    outputs = session.run(None, {session.get_inputs()[0].name: tensor})
    names = [output.name for output in session.get_outputs()]
    logits = outputs[names.index("text_logits")][0]
    exponential = np.exp(logits - logits.max(axis=0, keepdims=True))
    probability = (exponential / exponential.sum(axis=0, keepdims=True))[1]
    return bool(
        residual_components(
            probability, stored_character_mask(state, page, probability.shape)
        )
    )
