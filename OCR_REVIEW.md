# Independent OCR input fixes

Local branch: `review/ocr-input-fixes-20260917`.
Base: `6e511542f672438215cbde2363199b864e772987`.
No Table implementation changes, remote push or PR are included.

Independent OCR contracts and removal effects:
[OCR feature specification](docs/ocr-features.md).

1. `rects=[]` means no native spans are culled; `rects=None` retains the existing
   full-text culling behavior. Replacement-glyph input is not erased merely
   because its culling list is empty. This is not a new /ToUnicode-only trigger.
2. Immediately before OCR writeback, retain the original display list on the
   same page as `_pymupdf4llm_ruling_displaylist`, once. Live OCR text and pixels
   remain available to existing consumers. The Table branch independently uses
   this optional input only for raster ruling pixels.

The producer has no Table import/dependency. Tests cover None/empty behavior,
both OCR backends, rotation normalization and repeated OCR snapshot lifetime.
The combined validation branch is disposable composition, not the submission
branch. See the pb_table companion review document for composition results.
