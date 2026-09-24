# Table regression fixes: review bundle (2026-09-24)

This records the delivered Canny-based bundle through `b104403`. The subsequent
[Sobel mask replacement](raster-sobel-20260924.md) retains admission, V7, stroke
and crossing repair, and supersedes the final scores below. These historical
measurements are not claims about the later Sobel output.

This is one follow-up delivery for the paired `review/table-native-20260923`
branches. It consolidates the previously unpushed raster/stroke fixes with the
reviewed admission and V7 fixes. Intermediate rejected rules and counterexample
iterations are not separate reviewer-facing commits. The four behaviors remain
separately identifiable below. No OCR change is included.

## Feature and removal boundaries

### 1. Painted stroke geometry (PyMuPDF)

In `src/table.py::make_edges`, interpret the long perpendicular centerline of a
short, axis-aligned, solid, butt-capped, stroke-only single segment. Its painted
width must exceed the existing minimum length, while the path length is positive
and at most that minimum. Convert before clipping/length filtering; reuse the
existing drawing, `make_line` and native evidence delivery. No duplicate edge or
drawing extraction. Other caps, dash patterns and compound paths keep their
original interpretation.

Removing only this conversion restores the missing native rules; it does not
disable raster repair or candidate admission. See `stroke-rule-geometry` in the
paired PyMuPDF feature specification.

### 2. Raster crossing repair (PyMuPDF4LLM)

In `src/helpers/table_html/raster_lines.py`, use the existing horizontal mask to
bridge Canny crossing gaps only at x positions already supported by a long
vertical seed. Retain the existing gap and minimum-length parameters and merge/
admission logic. No new render, PDF extraction, OCR or model call is introduced;
two morphology operations are added. Removing this block restores the DP122
structural loss while leaving the rest of raster detection active.

### 3. Picture-contained candidate admission (PyMuPDF)

At the existing `src/_table_union.py::_union_line_candidates` admission point,
a candidate at least 80% inside a picture and no larger than that picture must
have one of these forms of support:

- all concrete cells populated;
- a complete rectangular tiled grid with at least two populated cells;
- at least two visual text bands across horizontally disjoint cells.

The last condition accepts numbers as well as letters. Bands require a common
vertical intersection covering at least half the shortest glyph height; they
do not use fixed 3pt top alignment or transitive union of glyph intervals.
Cell membership retains the half-open character-center contract. None slots
are not converted into empty-area ratios.

Reuse existing cells, CHARS and layout groups. There is no second P1 stage,
source re-extraction, chart model, post-output deletion or new framework.
The existing 2D support helper remains for other consumers and for candidates
outside the picture condition. This pre-union gate can affect grid_ref/split
as well as append, so the whole pipeline was compared.

Removing the picture-specific branch restores the prior admission policy.
Picture-containing tables larger than the image retain the old branch.
This is not a general chart/table classifier: aligned chart labels can remain
indistinguishable from table text. The 50% intersection criterion is a tested
heuristic, not a proven universal constant.

### 4. Continuous listing split restraint (PyMuPDF4LLM / V7)

In `src/_table_pipeline/v7_region_rules.py::_region_band_split`, veto a
spatial-only vertical cut when the existing nodes form two x fields: alphabetic
item names on the left and nondecreasing decimal integers on the right, with at
least two values and a larger final value. Existing interval clustering and
node centers are reused; the predicate is computed once per scan.

Independent header/period evidence, horizontal cuts and existing edge vetoes
are unchanged. Explicit value-column headers, resets and decimals do not match
this new guard. Unicode decimal integers are supported.
Remove this predicate/veto to restore the old V7 splitting; this does not remove
a false GNN parent table itself. Separate real two-column tables with continuous
integer values and only spatial boundary evidence remain ambiguous.

## Combined quality results

Baseline is the September 23 full native review composition, with the separate
reviewed OCR fixes held constant. This is not the smaller upstream PR-only
configuration, nor a later research/M1 stack.

- DP200: baseline 75 predictions, 51 matched, 24 unmatched; final 64 predictions,
  51 matched, 13 unmatched. Four GT tables remain missed.
  Table F1: **78.4615% -> 85.7143%**. Admission/V7 change seven documents relative
  to the raster/stroke-fixed baseline; with DP122 raster repair included, eight
  documents change relative to the September 23 full native baseline.
- Chart admission removes seven unmatched predictions across six documents;
  V7 removes four extra fragments on DP172, retaining the original GNN false
  parent. The original PR's thirteen unmatched predictions remain.
- Raster repair restores DP122 TEDS **0.6700721154 -> 0.8388221154** and
  TEDS-S **0.8125 -> 1.0**. All other existing matched DP scores are preserved.
- Final matched-table mean TEDS: **0.9431300450** (94.3130%). PR-only mean was
  0.9473772613 over 50 matches; the additional DP110 match scores 0.7307692308,
  explaining the lower 51-match average without regression of the prior 50.
  This average excludes unmatched tables. DP Table F1 uses HTML/TEDS matching,
  not bbox IoU.
- PB503: 909 -> 906 predictions, 854 matched unchanged, unmatched 55 -> 52.
  Only 222876fb p2/p21 and DS5795A p13 outputs change. Every page's GTRM,
  GriTS_CON and TRM is unchanged: aggregate **0.8098682258124252**,
  **0.8856166354231998**, **0.7091856091907063**, respectively.
  Counts come from HTML matching metadata, not bbox detection census.

## Compatibility, validation and limitations

- Each final isolated run completed DP200 and PB503 without failures.
  The protected admission revision is exactly output-equal to the preceding
  combined candidate on all 703 documents, not merely aggregate-equal.
- Laura independently compared all saved DP elements/chunks, PB raw/normalized
  output and official per-page metrics, and reran 52 focused contracts including
  both original review counterexamples. Full inference was supplied by Cindy;
  this independent review did not claim another new 703-document inference run.
- DP scoring reuses existing official scores when normalized HTML is identical;
  DP122 also has a separately executed official re-score. PB uses the same
  official evaluator throughout.
- Standalone native PyMuPDF, without Layout activation/OCR: the prior stroke
  comparison covered 1,669 documents / 1,671 pages. Default and use_layout=False
  each changed only BLS February 2026 p14/p15/p16 from no table to a partial 3x8
  grid. It is NOT complete body-row reconstruction and standalone output is
  NOT universally unchanged. This local set is not the earlier PR's 1,463-page
  regression list. The admission gate requires the union/layout path; V7 is
  in the companion pipeline.
- Fixed tests travel with each repository, without PB datasets. The 18 captured
  table/chart candidates remain local evidence, not a runtime dependency.
- After transplanting to the product worktrees, 198 product tests passed.
  All four modified runtime sources match the protected full-run package's AST
  after excluding docstrings; the stale picture-admission docstring was corrected.
- Fresh public-API smoke on DP036/110/122/172 exactly reproduced the protected
  full-run elements/chunks after product transplant. This covers chart admission,
  recovered-table retention, raster crossings and V7 restraint without claiming
  a redundant new full-corpus inference run.
- These are observed development/regression corpora, not fresh held-out
  generalization evidence. No full CF/VG/DocLayNet or throughput improvement
  claim is made. Retained rules and thresholds can still misclassify unseen data.
- Paired products and the reviewed compiled MuPDF/Layout were used. Separate OCR
  branch, model, 150-DPI OCR and max OCR size remain as specified in
  `docs/native-table-pipeline.md`; changing them invalidates exact score parity.

Local evidence (not included in the products):
`pb_table/runs/laura-ruling-fixes-20260924/` and
`pb_table/runs/cindy-dp-admission-20260924/`, especially
`dp-protected/evaluation.json`, `pb-protected/comparison.json`,
`normal-protection/full-comparison.json` and the independent product bundle
checks in `pb_table/runs/laura-dp-review-bundle-20260924/`.

This bundle updates existing review branches, not PRs. The repository owner
creates the PRs. Rolling research V-all/Viewer artifacts are not republished
as part of this product-branch delivery.
