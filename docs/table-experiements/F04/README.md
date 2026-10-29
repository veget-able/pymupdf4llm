# F04: Supply raster ruling evidence to the existing table path

Status: implemented-evaluated. Production and Viewer are unchanged.

## Implemented behavior

Reuse the production Sobel paired-edge detector and pass its lines to both HTML reconstruction entry points. Keep its constants and pixel/word handling unchanged. Uses I-B original pixels and live OCR words; no R6, admission, ownership, or general output policies are imported.

## Source and dependencies

Branch: table-experiements/f04-raster-ruling
Evaluated source commit: 474d5533873164a70ac3436b18239bd29d8d79f5
Paired PyMuPDF: 1d34e04da00b7673a0b2c3f68b5a5246793a50b8
Paired pymupdf4llm: 474d5533873164a70ac3436b18239bd29d8d79f5
Baseline: the frozen main pair in manifest.json. This is not the existing production stack.
No full-tree overlay or pb_table policy adapter is used. Source bytes are checked against Git.
Python sources use the pinned official draft 2.0_c native bindings/models. Native main was not rebuilt.

## Validation

Focused tests: 13 passed. Public to_markdown / parse_document+serializer parity: 3 pages.
Automatic OCR, original full pages, fixed RF+IMF1 weights, ORT/BLAS one thread.
bbox: IoU >= 0.60 one-to-one; single-GT is reported separately.
GTRM: original production ParseBench scorer source, unchanged normalization and metrics.
Selection: CURRENT v12 r5, 998 pages, 2735 bbox GT; key_value included, exclude_for_detection ignored.
Selection visible-text and per-cell evaluation contracts are preserved: 992 GTRM pages, 2724 tables.

Full actual API evaluation: PB503 + DL6489 + Selection998, 7,990 successful page runs for this variant.
All improved/regressed and score-neutral changed pages are in evaluation-20261029/*.tsv; full identities and before/after metrics are in the compressed ledgers.
PB verdicts (any metric or bbox count/GT identity): {'improved': 4, 'regressed': 0}.
DL verdicts (bbox count/GT identity): {'improved': 2, 'regressed': 21}.
Selection verdicts: {'improved': 2, 'regressed': 1, 'output_only': 2}.
A page can be both improved and regressed when components or GT identities differ.
Empty-GT pages with new FP are regressions even if their page F1 remains zero.

Dependency: I-B only. Main already has the necessary line input and union/refine APIs; B1/F02 are not merged.
No I-A change is included. This is F04+I-B versus main, not a separately isolated detector-only ablation.
New DL false positives include plot panels, a container photograph and a corrosion illustration.
Some GT-unmatched additions are actual forms/specification content; do not equate every GT FP with a non-table.
amt_general_handbook p326 retains the user-confirmed GT-disagreement classification.
Admission F05 interaction has not been tested; do not claim it fixes these cases.

## Limits and reproduction

This is measured development-corpus behavior, not independent generalization or automatic adoption.
Main does not expose raw GNN or CellSource in this public payload. Lexical deltas are diagnostics, not proof of glyph loss or preservation.
Shared CPU concurrent evaluation is not a controlled runtime A/B; no feature speed claim is made.
Local runner: scripts/analysis/run_feature_ports_20261029.py (prepare, inventory, run, score).
Selection runner: scripts/analysis/evaluate_feature_selection_20261029.py.
Page comparison: scripts/analysis/summarize_feature_ports_20261029.py.
Exact source/model/scorer/data hashes are included in evaluation-contract.json; full local raw evidence: runs/laura-feature-ports-20261029/.
Continue code and evidence commits on this branch; do not replace it with a new revision branch.
