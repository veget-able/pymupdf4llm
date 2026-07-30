"""PaddleOCR-VL chart2csv handler - direct HF transformers inference.

transformers >= 5.12 supports the 'paddleocr_vl' model type natively, so
the model loads offline from the HF cache without remote code (set
HF_HUB_OFFLINE=1 to guarantee no network access).

- Prompt "Chart Recognition:" selects the model's dedicated chart task.
- Output is already pipe-separated, so only structural cleanup is
  applied - values are never re-parsed: fix_header() compensates the
  model's tendency to drop the top-left corner cell of matrix tables,
  pipe_normalize() makes the result a renderable table.
- Model and processor load once per process and are reused.
- torch/transformers are imported lazily on first call.
- Feed single-chart crops: multi-chart composite images are slow and the
  model tends to merge their tables (the extraction hook crops per
  detected region, which is what this handler expects).
"""

from __future__ import annotations

from pathlib import Path

from ._common import fix_header, pipe_normalize, resolve_device

MODEL_ID = "PaddlePaddle/PaddleOCR-VL-1.6"
PROMPT = "Chart Recognition:"
MAX_NEW_TOKENS = 2048

_MODEL = None
_PROC = None


def _load():
    global _MODEL, _PROC
    if _MODEL is None:
        # transformers v5 defaults to the fast image processor, which
        # hard-requires torchvision - check upfront for a clear message.
        missing = []
        for module in ("torch", "transformers", "torchvision", "PIL"):
            try:
                __import__(module)
            except ImportError:
                missing.append("pillow" if module == "PIL" else module)
        if missing:
            raise RuntimeError(
                "PaddleOCR-VL chart extraction needs missing packages: "
                + ", ".join(missing)
                + ". Install with 'pip install " + " ".join(missing) + "'."
            )
        from transformers import AutoModelForImageTextToText, AutoProcessor

        device, dtype = resolve_device()
        _PROC = AutoProcessor.from_pretrained(MODEL_ID)
        _MODEL = (
            AutoModelForImageTextToText.from_pretrained(MODEL_ID, dtype=dtype)
            .to(device)
            .eval()
        )
    return _MODEL, _PROC


def _infer_one(model, proc, img_path: Path) -> str:
    import torch
    from PIL import Image

    img = Image.open(str(img_path)).convert("RGB")
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": PROMPT},
            ],
        }
    ]
    inputs = proc.apply_chat_template(
        msgs,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)
    n_in = inputs["input_ids"].shape[1]
    with torch.no_grad():
        # PaddleOCR-VL ships with use_cache=False in its generation
        # config. Left alone, generate() recomputes the full sequence on
        # every decode step and runs an order of magnitude slower
        # (measured 15.3 vs 157.9 tok/s) - enable the KV cache explicitly.
        out = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            use_cache=True,
        )
    return proc.decode(out[0][n_in:], skip_special_tokens=True).strip()


def paddleocr_vl(crop_paths: list[Path]) -> list[str]:
    """One 'Chart Recognition:' inference per crop, normalized to a table."""
    model, proc = _load()
    return [
        pipe_normalize(fix_header(_infer_one(model, proc, p))) for p in crop_paths
    ]
