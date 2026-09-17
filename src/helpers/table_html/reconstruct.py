from __future__ import annotations
"""HTML table reconstruction helpers for pymupdf4llm.

Builds the per-page table payload consumed by the markdown/JSON renderers
(:func:`page_html_tables`) and a standalone page-to-HTML convenience
(:func:`to_html`), both driven by ``page.find_tables(use_layout=True,
union=True, refine=True)``.
"""
import pymupdf
from pymupdf.table import _html_table_scope
from .core import html_document
from .raster_lines import detect_raster_table_lines


class TablePayload(tuple):
    """Preserve the six-item public payload contract, carrying source metadata."""

    def __new__(cls, values, provenance, *, unresolved_content=()):
        payload = super().__new__(cls, values)
        payload.bbox_provenance = dict(provenance)
        payload.unresolved_content = unresolved_content
        return payload


def _raster_lines(page):
    return detect_raster_table_lines(page)


def _placement_grid_matrices(placements) -> tuple[int, int, list, list]:
    """Derive ``(row_count, col_count, cells, extract)`` from a placement grid.

    ``placements`` is a ``Table.placements`` row-major grid of ``SpanCell``
    colspan/rowspan cells. ``row_count`` is the ``<tr>`` count; ``col_count`` the
    column extent after resolving spans (the HTML column count). ``cells`` and
    ``extract`` are the ``row_count x col_count`` post-span bbox and plain-text
    matrices, ``None`` where a span covers a slot or the grid has a gap."""
    row_count = len(placements)
    # Column extent after resolving colspan/rowspan == the HTML <td>/<th> column
    # count the matrices below are shaped to.
    occupied = set()
    col_count = 0
    for row_idx, row in enumerate(placements):
        col_idx = 0
        for cell in row:
            while (row_idx, col_idx) in occupied:
                col_idx += 1
            for dr in range(cell.rowspan):
                for dc in range(cell.colspan):
                    occupied.add((row_idx + dr, col_idx + dc))
            col_idx += cell.colspan
            col_count = max(col_count, col_idx)
    # Expand the ragged post-span grid into row_count x col_count bbox and text
    # matrices, ``None`` where a span covers a slot (or a grid gap).
    bbox_grid = [[None] * col_count for _ in range(row_count)]
    text_grid = [[None] * col_count for _ in range(row_count)]
    covered = set()
    for row_idx, row in enumerate(placements):
        col_idx = 0
        for cell in row:
            while (row_idx, col_idx) in covered:
                col_idx += 1
            if col_idx >= col_count:
                break
            bbox_grid[row_idx][col_idx] = list(cell.bbox) if cell.bbox is not None else None
            text_grid[row_idx][col_idx] = cell.text
            for dr in range(cell.rowspan):
                for dc in range(cell.colspan):
                    if dr or dc:
                        covered.add((row_idx + dr, col_idx + dc))
            col_idx += cell.colspan
    return row_count, col_count, bbox_grid, text_grid


def _table_grid_matrices(tab, *, retain=False) -> tuple[int, int, list, list]:
    """Borrow matrices for one table's current structural state (read-only).

    Header tags/roles do not enter the matrices. Cell text, bbox, spans and
    row membership do: snapshot those values to detect in-place edits as well
    as grid replacement. Retain only the latest state on this Table, never a
    page/global cache. Split/refine/stitch children own independent Tables.
    Producers opt into retention; the final serializer only borrows results.
    """
    placements = tab.placements
    previous = getattr(tab, "_placement_matrices_snapshot", None)
    # Final serialization is a consumer: do not retain a first/last-use result.
    if previous is None and not retain:
        return _placement_grid_matrices(placements)
    state = tuple(tuple((tuple(c.bbox) if c.bbox is not None else None,
                         c.text, c.colspan, c.rowspan) for c in row)
                  for row in placements)
    if previous is not None and previous[0] is placements and previous[1] == state:
        return previous[2]
    result = _placement_grid_matrices(placements)
    if retain:
        tab._placement_matrices_snapshot = (placements, state, result)
    elif previous is not None:
        del tab._placement_matrices_snapshot
    return result


@_html_table_scope()
def to_html(pdf, page_index=0):
    """Reconstruct the tables on one PDF page and return them as an HTML string.

    pdf        : PDF file path (str/Path) or an already-open pymupdf.Document.
    page_index : 0-based page number.
    returns    : concatenated <table>...</table> HTML (empty string if no tables).

    When ``pdf`` is an already-open Document, the target page is derotated in
    place via ``page.remove_rotation()`` (mutates the caller-owned page).
    """
    owns_doc = not isinstance(pdf, pymupdf.Document)
    doc = pymupdf.open(pdf) if owns_doc else pdf
    try:
        page = doc[page_index]
        page.remove_rotation()
        raster_lines = _raster_lines(page)
        tf = page.find_tables(
            use_layout=True,
            union=True,
            refine=True,
            add_lines=raster_lines,
        )
        tables = [tab.to_html() for tab in (getattr(tf, "tables", None) or [])]
    finally:
        if owns_doc:
            doc.close()
    return html_document([{"html": h} for h in tables])


@_html_table_scope()
def page_html_tables(
    page: pymupdf.Page, *, include_union_evidence: bool = False
) -> list[tuple[pymupdf.Rect, str, int, int, list, list]] | tuple[
    list[tuple[pymupdf.Rect, str, int, int, list, list]], dict
]:
    """Reconstruct one already-open page's tables as payload tuples.

    By default, returns one ``(bbox, html, rows, cols, cells, extract)`` tuple
    per table, in reading order, for the markdown/JSON renderers to drive table
    emission, reading order and body-text exclusion. With the keyword-only
    ``include_union_evidence=True`` opt-in, returns ``(tables, evidence)`` from
    the same single finder call; missing or invalid evidence is represented by
    the empty-dict transport sentinel.

    * ``bbox``    -- ``tab.bbox`` (a grid-ref table keeps its reported layout box);
    * ``html``    -- ``tab.to_html()``;
    * ``rows``/``cols``/``cells``/``extract`` -- the reconstructed grid the
      ``html`` shows (see :func:`_placement_grid_matrices`): ``extract`` is the
      per-cell plain-text matrix (``None`` for span-covered slots / grid gaps)
      and ``cells`` the matching post-span bbox matrix, both ``rows x cols``.

    The caller must remove page rotation before calling. Not thread-safe on a
    shared Page: core caches word/vector extraction as attributes on the given
    ``page``, so concurrent calls must each use their own ``pymupdf.Page``.
    """
    raster_lines = _raster_lines(page)
    tf = page.find_tables(
        use_layout=True,
        union=True,
        refine=True,
        add_lines=raster_lines,
    )
    result = []
    for index, tab in enumerate(getattr(tf, "tables", None) or []):
        row_count, col_count, cells, extract = _table_grid_matrices(tab)
        provenance = dict(getattr(tab, "bbox_provenance", {}))
        provenance.setdefault("bbox_source", "unknown")
        provenance.setdefault("grid_source", "unknown")
        provenance.setdefault("bbox_operation", "unknown")
        provenance.setdefault("source_gnn_indices", [])
        provenance["table_id"] = f"p{page.number}:table:{index}"
        result.append(
            TablePayload((
                pymupdf.Rect(tab.bbox),
                tab.to_html(),
                row_count,
                col_count,
                cells,
                extract,
            ), provenance, unresolved_content=getattr(tab, "unresolved_content", ()))
        )
    if include_union_evidence:
        evidence = getattr(tf, "table_union_evidence", {})
        return result, evidence if isinstance(evidence, dict) else {}
    return result
