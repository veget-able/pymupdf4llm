# Table review branch

Local branch: `review/table-vall-20260917`.
Base: `6e511542f672438215cbde2363199b864e772987` (benchmark source).
No remote push or PR has been performed.

## Scope

- Raster ruling detection/virtual geometry passed to find_tables.
- Table-priority reading order, per-HTML bbox/grid provenance and union evidence.
- Grid matrix reuse, HTML header omission and source-backed external Text output.
- Original cell/word/character references survive serialization and span joins;
  output dedup uses those references instead of enlarging bbox tolerance.

`src/ocr/` has no changes on this branch. The raster consumer optionally reads
`page._pymupdf4llm_ruling_displaylist`; without it, it renders the live page.
The independent `review/ocr-input-fixes-20260917` branch supplies this snapshot
and the None/empty culling fix. Exact V-all parity uses both branches.

Use the matching PyMuPDF Table branch and the `pb_table` companion adapter/model
branch. They are required dependencies, not code silently bundled here.
See the companion review document for full-503 results and replay instructions.
The branch base differs from veget-able's current main: a later PR-base port is
not covered by benchmark parity on this pinned stack.
