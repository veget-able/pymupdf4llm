"""Chart extraction callbacks (chart_function).

Plain callables, selected by reference - like the OCR backends:

    chart_function(crop_paths: list[Path]) -> list[str]

one Markdown table per crop image, in order. Heavy model dependencies
are imported lazily inside the handlers, so importing this package never
pulls in torch or transformers.

    import pymupdf4llm
    from pymupdf4llm.chart import paddleocr_vl
    md = pymupdf4llm.to_markdown(
        "doc.pdf", detect_charts=True, chart_function=paddleocr_vl
    )
"""

from .placeholder import placeholder
from .paddleocr_vl import paddleocr_vl

__all__ = ["paddleocr_vl", "placeholder"]
