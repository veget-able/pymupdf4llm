# Shared-year header protection

## Feature and placement

- Fixes the existing node-based region splitter in the native HTML pipeline,
  before child crops reach TGIF. This is not a new header model or a later
  merge of reconstructed tables.
- The shared-header consumer now recognizes at least two separately positioned,
  pure 19xx/20xx year labels. A text label beside one year-valued record is not
  sufficient. Existing text-header, top-three-row and horizontal-gap rules stay
  unchanged; the common tokenizer and repeated-body anchors are not broadened.
- For a shared year header, a following block without its own header stays with
  its preceding block. A later block with its own header keeps its boundary.
  This avoids the first candidate's all-or-nothing rejection, which incorrectly
  merged the lower independent table on IBM17.
- Implementation: src/_table_pipeline/v7_region_rules.py. The retained node
  text/bboxes, interval clustering and token helper are reused. No extra PDF
  extraction, OCR, GNN, TGIF or header-model pass is introduced by the decision.
- Active on the existing strict vertical-split path. No public option is added.
  Reverting this change restores the prior shared-header behavior; other split
  rules and the downstream reconstruction pipeline remain available.

## Validation and limits

- Exact implementation measured on PB503: GTRM 81.354378% -> 81.427371%,
  GriTS_CON 88.846771% -> 88.893354%, TRM 71.368564% -> 71.467968%.
  Apple27 and IBM17 improve; no page decreases on these three metrics.
  USPS50 changes provenance from reconstruct-after-split to gnn_keep with
  identical normalized output. All 503 pages complete successfully.
- Selected external 616 pages / 1,455 GT tables: final HTML bbox F1
  79.724837% -> 79.927536%. FinTabNet 88.888889% -> 92.134831%; PubTables
  and SERFF unchanged. MGM and WAB improve; all other 614 chunks are identical.
  IoU 0.60, coverage/GT >= 0.50 single-GT eligibility, then one-to-one matching.
  All selected GT are included, including 126 original detection-exclusion flags;
  these are not official whole-dataset benchmark numbers.
- Compared with product PyMuPDF a15e72d6 and PyMuPDF4LLM b86cbd9, using the
  previously reviewed independent OCR fixes and the same models/evaluator.
  No pb_table inference adapter or experimental M1 splitter is required.
- These are development comparisons, not independent generalization evidence.
  The first candidate regressed IBM17; the per-boundary correction was developed
  from that counterexample. Two year-valued body columns and independent tables
  omitting their headers remain ambiguous. Date/localized-year support is not
  expanded by this change.
- The WU number/description listing remains oversplit and is not included in
  this fix. FinTabNet V1 F1 is 92.655367%; this fix does not recover that last FP.

## Portable regression controls

- tests/test_table_pipeline/test_v7_year_headers.py uses retained node, edge and
  ruling inputs, with no PDF access or model inference. Fixtures represent MGM,
  WAB, WU and IBM17; only inputs and expected boxes are stored, not evaluator GT.
- Tests cover the two shared-year fixes, the unchanged listing, a preserved
  later independent header, the single-year-record negative, and input immutability.
- The existing five listing controls remain unchanged. PB-side controls also
  preserve Apple43, Coca107 and CA2326 split boxes.
- Product wheel verification: 174 table-pipeline tests pass. Six live API checks
  (MGM, WAB, WU, Apple27, IBM17, USPS50) exactly reproduce the measured candidate.
  Runtime Python sources match the measured candidate except build metadata;
  this packaging check does not claim a second full-503 wheel evaluation.
- Experiment records: PB runs/thf3/v7-year-guard-20261012-02, comparison.json and
  docs/table_finder/thf3-year-header-fix-20261012.md. These paths are evidence
  references only, not installation or inference dependencies.
