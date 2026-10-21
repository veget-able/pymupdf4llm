# Structured table consumer for draft 2.0_c

Use this `review/table-draft2c-20261021` branch with the identically named
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
that text was emitted in a cell. OCR producer changes are not included here.

Measured table-only results (same PB503 / DL6489 manifests): DL bbox F1
81.499775%, PB bbox F1 88.429290%, PB GTRM 80.648183%. Bbox scoring uses
IoU >= 0.60, greedy one-to-one matching, not single-GT or mAP. Previous
production scores are 81.444918%, 88.864143%, and 81.603774%, respectively.
The PB difference is reproduced by the omitted OCR producer fixes; an isolated
PB503 diagnostic with both fixes reproduces production text/HTML exactly.
Those fixes are not silently bundled into this table branch. See the paired
PyMuPDF review document for the counts, fallback cases and validation limits.

The installed combined wheel passes 334 product and 27 selected native API
tests without benchmark imports. The source-only review build from clean Git
checkouts reproduces all 263 wheel file contents; native binaries remain those
of the pinned official draft. The current production deployment and Viewer are
not replaced by publishing this review branch.
