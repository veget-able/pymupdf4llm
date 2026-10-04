# PDF clip-backed cell restoration

## Scope and activation

- Feature: pdf-clip-cell-restoration; integrated into the existing structured HTML table pipeline, not a new numbered version.
- Paired review branch: review/table-native-20260923 in PyMuPDF and PyMuPDF4LLM.
- Baseline: PyMuPDF 37d46698 and PyMuPDF4LLM a8f0ea8d, including the approved Sobel, candidate-admission, V7 and vector fixes.
- No change to Sobel, OCR, GNN/TGIF weights, or THF1 (formerly R6) weights and feature contract.
- No activation in standalone Page.find_tables() or the plain Markdown table path.
- Implementation in the products; no pb_table import, benchmark files, saved HTML, filename rules or external monkeypatch at inference time.

## Behavior and limits

- Merge adjacent cell fragments only with corroborated painted clip ownership, ordered text correspondence, cell-local glyph positions and an unambiguous contiguous placement path. Original CellSource references retained.
- Partition a wrongly combined cell only with disjoint adjacent clip scopes and two following rows confirming the existing columns and text correspondence.
- Restore an adjacent missing row only when the existing edge row confirms its columns and the new glyphs have a unique live non-table layout owner. Already consumed glyphs distinguished from genuinely unassigned material.
- Admit a missing table only for adjacent, independently painted clip cells with complete live source ownership and the same known nonwhite background. A clip rectangle alone is not a table detector.
- Resolve rectangular backgrounds in paint order. Partial covers, including narrow fills, can invalidate uniform color; opaque complete covers can resolve earlier uncertainty.
- New cells carry actual glyph/word references. A partial word is not claimed wholesale. The known SymbolMT bullet mapping is restricted to that font and codepoint.
- Changed placements receive one final THF1 role classification before external-text routing and HTML serialization. Existing role results retained for unchanged tables.
- Nonrectangular clipping, soft masks, incompatible text transforms, unresolved encoding and unsupported paint remain unknown rather than affirmative evidence. Coordinates are derotated PDF points; glyph geometry uses baseline/advance, not an assertion about exact painted ink.
- The background-dependent empty-cell/role proposal for 1634690602 remains deferred. No exception for this filename in runtime code.

## Intervention and reuse

- Initial loss: ordinary text/line extraction discards the relation between painted glyphs and their active PDF clip scopes; subsequent grid reconstruction can separate or combine the wrong text units.
- PyMuPDF _table_clip collects the missing relation once from the already-open page. Ordinary TextPage and cached rulings cannot reconstruct that paint-stack relation. Additional page traversal required; no PDF reopen, raster render, OCR, GNN or TGIF pass.
- Reuse of finder.ruling_evidence, restricted to actual vector origins. Existing merge_edges, edges_to_intersections and intersections_to_cells build independent closed faces; no second PDF-path ruling decoder and no synthetic/raster edges treated as native enclosure proof.
- Reuse of final placements, header_leaf_completion.occupancy, SpanCell/CellSource, the live _refine_words_cache, layout_information and the existing header.apply_roles character/session cache.
- Cell and extent decisions run after the existing union/split/recovery results are final, but before external-content disposition. Earlier provisional grids can be replaced by those stages and do not establish final ownership. No serialized HTML rewriting or rerunning the grid recognizer.
- New clip geometry helpers retained separately: baseline/advance grouping, physical clip boundaries, ordered paint pieces and associated tolerances differ from existing node clustering and placement geometry. No new generic cache or reconstruction framework.
- Offline-only row/component diagnostics omitted from the shipped evidence path. Inference consumes clip payloads and corroborated cell units, not diagnostic log flags.

## Validation

- Ordinary product API, same source/runtime/OCR composition as the latest Sobel baseline; full PB503 and DP200 inference, zero failures.
- PB503 GTRM: 0.8102316394788731 -> 0.8135437812454254, +0.3312141767 percentage points.
- PB503 GriTS_CON: 0.8859359662148750 -> 0.8884677109635919.
- PB503 TRM: 0.7095931057319268 -> 0.7136856445163146.
- Six pages improved; 497 raw and normalized outputs unchanged. Seven affected tables, including two on CA2005. No page decrease in the three quality metrics.
- Evaluator HTML pairing: predictions 906 -> 907; matched 854 -> 855; unmatched predictions remain 52. These are evaluator pairing counts, not bbox IoU detection counts.
- Improved pages: Walmart Settlement p300, 637951… p1, Cost Estimating p6, SERFF CA2005, CA995, TX783. No runtime name matching.
- DP200 HTML and complete chunk text unchanged for all 200 documents. Matched 51, unmatched predictions 13, missed 4; F1 0.8571428571, matched-table TEDS 0.9469007841 unchanged.
- Initial integration exposed unbalanced soft-mask clip scopes. Fixed native begin_mask/end_mask lifecycle; final full runs have no such callback failures. Synthetic live-PDF mask and clip tests included.
- 190 focused/product contract tests passed. Built the actual PyMuPDF4LLM wheel and verified module inclusion; six positive pages plus the deferred control reproduce final-run raw and normalized outputs exactly. Native binaries reused, not rebuilt or certified for other platforms.
- Final full run precedes only formatting and removal of unused offline diagnostic fields. Installed-wheel tests cover the trimmed runtime modules. No full-wheel 503 rerun claimed.

## Cost and remaining uncertainty

- Timed clip preparation on seven live wheel-run pages: 6.5–574.5 ms/page, including native paint traversal and clip evidence construction. The 1,013-clip percent-control page is the high end. Additional placement restoration/role cost not isolated by that timer.
- These targeted timings are not a full-corpus throughput claim. No claim of zero overhead or speedup.
- PB503 is the development corpus and DP200 is a previously used regression corpus, not new held-out generalization evidence. No new CF/VG/DocLayNet quality claim.
- Some final header tags differ from the offline candidate because live THF1 reclassifies the changed placements. Official target quality deltas nevertheless reproduced exactly.

## Review and removal boundary

- PyMuPDF: src/_table_clip.py, its setup.py inclusion and native clip tests; private collector only, no default finder hook.
- PyMuPDF4LLM: clip_geometry.py, clip_evidence.py and clip_restoration.py; runtime.py preparation and the optional restore_clips callback in table_content_pipeline.py.
- To remove this feature, omit clip preparation and the restore_clips callback. Prior union, restoration, role and output routing remain usable without it. Do not delete shared CellSource or other existing algorithms.
- OCR fixes remain a separate review branch. Existing review branches retained; no PR created or remote push performed by this integration.
- Research reproduction: runs/laura-clip-product-20261004/full-02/comparison.json, dp-02/evaluation.json, wheel-cohort/verification.json, validate.py, validate_dp.py, check_wheel.py. Research data and execution artifacts excluded from product commits.
