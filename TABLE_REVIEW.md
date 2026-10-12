# Table review branch

Review branch: review/table-native-20260923.
Base: `6e511542f672438215cbde2363199b864e772987` (benchmark source).
This branch supersedes the earlier adapter-dependent review/table-vall-20260917.
See [native product integration](docs/native-table-pipeline.md) for the current
execution contract and [shared-year header protection](docs/shared-year-header-protection-20261013.md)
for the latest region-splitting fix.

Per-feature contracts, dependencies and removal effects:
[Table feature specification](docs/table-features.md).

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

Use the matching PyMuPDF review/table-native-20260923 branch and reviewed Layout
runtime. The native HTML pipeline and header model are bundled here; pb_table
is not an inference dependency. Exact benchmark parity retains the separately
reviewed OCR composition described in the native product integration document.
The branch base differs from veget-able's current main: a later PR-base port is
not covered by benchmark parity on this pinned stack.
