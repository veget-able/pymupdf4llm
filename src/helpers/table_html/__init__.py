"""Thin pymupdf4llm table engine over the pymupdf core table model.

Detection, the layout/candidate union, grid refinement, cell-span resolution,
header tagging and HTML serialization all live in pymupdf core now: one
`page.find_tables(use_layout=True, union=True, refine=True)` call yields tables
with a tagged `placements` grid + header meta and a `Table.to_html()` serializer.
This subpackage is only the pymupdf4llm-side glue over that model:

* `page_html_tables(page)` -- the per-page `(bbox, html, rows, cols, cells,
  extract)` payload `pymupdf_rag.to_markdown(..., table_output="html")` and
  `document_layout` consume;
* `to_html(pdf, page_index)` -- a standalone page -> `<table>` HTML convenience.

Dependency direction (one-way, no cycles): core (the `html_document` join) is a
leaf; reconstruct -> core / pymupdf.table. Public entry points: `to_html()`,
`page_html_tables()`.
"""

from __future__ import annotations

from .reconstruct import to_html, page_html_tables

__all__ = ["to_html", "page_html_tables"]
