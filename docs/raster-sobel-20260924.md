# Raster ruling extraction: paired Sobel edges

This replaces the mask builder inside `raster-rule-detection`, not a new detector
or version layered after extraction. Base: PyMuPDF `37d46698` and PyMuPDF4LLM
`b104403`, including protected admission, V7 listing restraint, painted vector
strokes and raster crossing repair. Only PyMuPDF4LLM runtime code changes here.
No OCR/model changes are included. The paired review branches and separate OCR
composition described in `native-table-pipeline.md` remain the benchmark setup.

## Algorithm, input and removal contract

`src/helpers/table_html/raster_lines.py::_detect_grid_components` replaces
Gaussian blur / Canny with directional 1D `[-1, 0, 1]` differences on the existing
gray crop. Absolute response >=20 establishes an edge. Opposite-sign responses
within the existing maximum rule thickness (5pt, converted to pixels with a
sampling margin) establish a thin stroke of either polarity. Crop-rim responses
are retained when the other edge may be clipped. Nonmaximum suppression thins
each directional response before the existing close/open operations.

The long-vertical-seed crossing repair uses those directional masks. Existing
24pt minimum length, gap/merge thresholds, word-overlap rejection, component
support and PDF coordinate conversion are unchanged. No new product helper,
framework, PDF extraction, rendering, OCR, GNN or TGIF invocation is added.
This fixes the earliest wrong material: the raster ruling mask, not final tables.

No public toggle is added. To remove only this change, restore this function from
`b104403`; that keeps crossing repair, candidate admission, V7 and vector fixes.
The rest of the raster extractor need not be disabled. Thresholds are empirical,
not universal accuracy guarantees. Float gradient arrays and edge pairing add
CPU/memory work; there is no throughput improvement claim.

## Latest-stack full-corpus comparison

- DP200: GT55, predicted64, matched51, FP13, FN4, F1 85.7143%, all unchanged.
  Matched-table TEDS: 0.9431300450299528 -> 0.9469007840948096 (+0.3771pp).
  Only DP110 table HTML changes: TEDS 0.730769 -> 0.923077.
  DP122 remains 0.838822. Other 199 table outputs and outside-table text match.
  TEDS excludes unmatched tables; F1 uses official HTML matching, not bbox IoU.
- PB503: GT893, predicted906, matched854, FP52, FN39, all unchanged.
  GTRM: 0.8098682258124252 -> 0.8102316394788731 (+0.03634pp).
  GriTS_CON: 0.8856166354231998 -> 0.885935966214875.
  TRM: 0.7091856091907063 -> 0.7095931057319268.
  Page metrics improve on BRWS1112/1113 only, no page metric declines.
- Raw PB output changes on four pages; normalized output on three. CA2600
  retains table HTML and picture text but swaps the first table with the picture
  text block. Its score is unchanged, not proof of reading-order correctness.
- Individual GT CON: five improve, one declines. BRWS1113's third GT scores
  0.619048 -> 0.615385 after removal of a final empty predicted row; other cell
  strings match. This is not an all-table non-regression claim.

Both full runs completed (200 + 503 pages, zero execution failures). Existing
scores are reused for DP pages with identical normalized HTML. Latest baseline
results were reused after source identity checks. These are development/regression
corpora, not new held-out evidence; no new CF/VG/DocLayNet claim is made.

## Cost and reproducibility

Four cached crops, single OpenCV thread, alternating ten samples after two
warmups: extraction median increased by 1.15-1.59x. Representative five-page API
mean increased 1119.7ms -> 1143.0ms (+23.3ms), one warmup and two samples per mode.
The small noisy API sample is not a measurement of full-corpus throughput.

Local full-run evidence (not product runtime dependencies):
`pb_table/runs/susan-sobel-latest-20260924/`: `manifest.json`, `summary.json`,
`dp-sobel/evaluation.json`, `pb-sobel/comparison.json`, `cached-cost.json`,
`cost.json`. The source algorithm matches that measured candidate; tests use
synthetic pixels rather than carrying benchmark documents into the product.

Laura rechecked all saved outputs/official per-page scores and reran 38 focused
contracts before approval. After transplant, 205 product/contract tests passed
(seven existing SWIG deprecation warnings), including eight real-pixel raster
tests. The installed product function is AST-identical to the measured candidate;
all other assembled package files are byte-identical. Fresh public API runs on
DP036/110/122/172 exactly reproduce the measured Sobel elements and chunks.
Product-transplant validation is recorded in
`pb_table/runs/laura-sobel-product-20260924/README.md`. A later product smoke is
not described as another full 703-page inference run. Rolling research V-all and
Viewer artifacts are not republished by this review-branch delivery.
