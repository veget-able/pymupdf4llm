# I-B: Retain original pixels for ruling detection

Status: implemented-boundary-tested. Production and Viewer are unchanged.

## Implemented behavior

Retain the existing pre-OCR display list for the ruling consumer and invalidate its raster cache in both OCR paths. Live OCR text and layout input remain unchanged.

## Source and dependencies

Branch: table-experiements/pre-ocr-ruling-image
Evaluated source commit: 3f34756bcb3da60673127426b90d1a40e365a633
Paired PyMuPDF: 1d34e04da00b7673a0b2c3f68b5a5246793a50b8
Paired pymupdf4llm: 3f34756bcb3da60673127426b90d1a40e365a633
Baseline: the frozen main pair in manifest.json. This is not the existing production stack.
No full-tree overlay or pb_table policy adapter is used. Source bytes are checked against Git.
Python sources use the pinned official draft 2.0_c native bindings/models. Native main was not rebuilt.

## Validation

Focused tests: 4 passed. Public to_markdown / parse_document+serializer parity: 3 pages.
Automatic OCR, original full pages, fixed RF+IMF1 weights, ORT/BLAS one thread.
bbox: IoU >= 0.60 one-to-one; single-GT is reported separately.
GTRM: original production ParseBench scorer source, unchanged normalization and metrics.
Selection: CURRENT v12 r5, 998 pages, 2735 bbox GT; key_value included, exclude_for_detection ignored.
Selection visible-text and per-cell evaluation contracts are preserved: 992 GTRM pages, 2724 tables.

No standalone full-corpus score is claimed for this input-only feature.
Its raster consumer is tested in F04 with this source revision explicitly merged.

## Limits and reproduction

This is measured development-corpus behavior, not independent generalization or automatic adoption.
Main does not expose raw GNN or CellSource in this public payload. Lexical deltas are diagnostics, not proof of glyph loss or preservation.
Shared CPU concurrent evaluation is not a controlled runtime A/B; no feature speed claim is made.
Local runner: scripts/analysis/run_feature_ports_20261029.py (prepare, inventory, run, score).
Selection runner: scripts/analysis/evaluate_feature_selection_20261029.py.
Page comparison: scripts/analysis/summarize_feature_ports_20261029.py.
Exact source/model/scorer/data hashes are included in evaluation-contract.json; full local raw evidence: runs/laura-feature-ports-20261029/.
Continue code and evidence commits on this branch; do not replace it with a new revision branch.
