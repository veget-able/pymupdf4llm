# Structured table consumer for draft 2.0_c

Use this 2.0-draft-c-table-20261021 branch with the identically named
`veget-able/PyMuPDF` branch. They form one review/build pair, not two alternatives.
The consolidated feature specification and build instructions are in that
repository's `docs/table-draft2c-review.md`.

This repository supplies the native HTML table consumer: deferred TGIF and
region/cell reconstruction, source-owned content restoration, final THF1/R6
header roles, raster ruling extraction, and table/picture output ownership.
It also supplies the bundled ONNX model and the standalone title alignment
contract. No benchmark package, saved prediction, dataset or ground truth is
required by the runtime.

The main 2.0 PyMuPDF build gathers this repository's tracked `src` files using
`PYMUPDF_SETUP_PATH_4LLM`. Do not build or install the old separate 4LLM package
over the integrated draft wheel. Keep `versions_file.py` generated for 2.0.

The public entry remains `to_markdown(..., table_output="html")`. Non-HTML
parsing does not activate the structured-table runtime. Original word/glyph
references determine picture text exclusion; bbox overlap alone does not prove
that text was emitted in a cell.

Two OCR/table input-boundary fixes are included:
- An empty text-culling rectangle list leaves all text visible to OCR;
  None retains the full-page text-culling default.
- Full and detection-only OCR preserve the original pre-OCR display list for
  raster ruling detection and invalidate the raster-line cache. Live OCR text
  remains available to layout/GNN, cell text extraction and all other consumers.

The exact combined sources were evaluated on PB503 and DL6489. DL bbox F1 is
81.444918% (TP1815/FP373/FN454), PB bbox F1 is 88.864143%
(TP798/FP105/FN95), and PB GTRM is 81.603774%. All match current production.
Bbox scoring uses IoU >= 0.60 and greedy one-to-one matching, not single-GT
or mAP. The stricter DL single-GT F1 is 80.682073%, also unchanged.
Final bbox, HTML, full text and raw GNN table output match production on all
6489 DL pages. PB GTRM/CON/TRM were officially rescored and match on all
503 pages, rather than inferred from HTML equality. API errors are zero;
the same eight DL HTML fallback pages remain, with no new fallback.

Compared with the table-only port, restoring the ruling input returns five
previous predictions and removes two port-only false positives. The five
returned predictions comprise one figure-panel grid, one GUI form and three
actual tables inside screenshots without corresponding Table GT. The score
match does not certify that every existing detection is correct.

The installed combined wheel passes 334 product and 27 selected native API
tests without benchmark imports. The source-only review build from clean Git
checkouts reproduces all 263 wheel file contents; native binaries remain those
of the pinned official draft. The current production deployment and Viewer are
not replaced by publishing this review branch.

The preceding 334/27 test and 263-file clean-build counts describe the original
table-only port. The A+B delivery wheel passes 338 selected tests, including
eight dedicated empty-list/None and pre-OCR pixel/cache cases. Its 157 frozen
package files match the full-evaluated A+B composition. Public API output on
21 affected/control pages (14 PB, seven DL) exactly matches that composition
in a clean installation without ParseBench or pb_table imports. No diagnostic
A+B runtime overrides are needed: both changes are installed source code.
