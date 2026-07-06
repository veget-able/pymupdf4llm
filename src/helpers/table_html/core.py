from __future__ import annotations
"""core — the one shared util the thin engine still needs: html_document.

Text extraction, geometry, header-region rules and HTML serialization all moved
into pymupdf core (find_tables(refine=True) / Table.to_html()); the only helper
left here is the document-level join used by reconstruct.to_html()."""
from typing import Any


def html_document(tables: list[dict[str, Any]]) -> str:
    """Concatenate per-table HTML fragments into one document string.

    Joins each entry's ``"html"`` (skipping empties) with a blank line -- the
    document wrapper :func:`reconstruct.to_html` returns."""
    return "\n\n".join(str(table.get("html") or "") for table in tables if table.get("html"))
