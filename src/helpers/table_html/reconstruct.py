from __future__ import annotations
"""reconstruct — thin pymupdf4llm glue over the pymupdf core table model.

Detection, the layout/candidate union, grid refinement, cell-span resolution,
header tagging and single-pass HTML serialization all live in pymupdf core now:
one ``page.find_tables(use_layout=True, union=True, refine=True)`` call returns
the fused tables, each already carrying a tagged ``placements`` grid (SpanCell
colspan/rowspan + ``th``/``td`` tag), its header meta and a ``Table.to_html()``
serializer, plus a union-preserved ``Table.bbox``. This module only assembles
the document-integration payload (:func:`page_html_tables`) and the standalone
:func:`to_html` convenience. Depends on core (the ``html_document`` join) and
pymupdf.table.
"""
import pymupdf
from .core import html_document


def _placement_grid_matrices(placements) -> tuple[int, int, list, list]:
    """Derive ``(row_count, col_count, cells, extract)`` from a core placement grid.

    ``placements`` is a table's ``Table.placements`` -- the row-major grid of
    tagged ``SpanCell`` colspan/rowspan placements from
    ``find_tables(refine=True)``. ``row_count`` is the source ``<tr>`` count (one
    placement row per row); ``col_count`` the column extent after resolving
    colspan/rowspan (== the html column count). ``cells`` and ``extract`` are the
    ``row_count x col_count`` post-span matrices the html describes: each
    placement's ``[x0, y0, x1, y1]`` bbox / its plain text at its slot, ``None``
    for a slot a span covers (or a grid gap)."""
    row_count = len(placements)
    # Column extent after resolving colspan/rowspan. The placement grid is either
    # gated on this equalling the raw row width or padded to it (flat fallback),
    # so it is the html <td>/<th> column count the matrices below are shaped to.
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


def to_html(pdf, page_index=0):
    """Reconstruct the tables on one PDF page and return them as an HTML string.

    pdf        : PDF file path (str/Path) or an already-open pymupdf.Document.
    page_index : 0-based page number.
    returns    : concatenated <table>...</table> HTML (empty string if no tables).

    Detection + the layout/candidate union + refinement + header-tagged
    serialization all live in pymupdf core: ``find_tables(union=True,
    refine=True)`` returns the fused tables in build order, each with a
    ``to_html()`` serializer.

    Note: this is the standalone entry point and owns page derotation, so when
    ``pdf`` is an already-open Document it mutates that caller-owned page via
    ``page.remove_rotation()`` (removing any page rotation in place).
    """
    owns_doc = not isinstance(pdf, pymupdf.Document)
    doc = pymupdf.open(pdf) if owns_doc else pdf
    try:
        page = doc[page_index]
        page.remove_rotation()
        tf = page.find_tables(use_layout=True, union=True, refine=True)
        tables = [tab.to_html() for tab in (getattr(tf, "tables", None) or [])]
    finally:
        if owns_doc:
            doc.close()
    return html_document([{"html": h} for h in tables])


def page_html_tables(page: pymupdf.Page) -> list[tuple[pymupdf.Rect, str, int, int, list, list]]:
    """Reconstruct one already-open page's tables as ``(bbox, html, rows, cols, cells, extract)`` tuples.

    Detection + the layout/candidate union + grid refinement + header-tagged
    cell-span resolution + HTML serialization now all live in pymupdf core: a
    single ``page.find_tables(use_layout=True, union=True, refine=True)`` returns
    the fused tables (layout order, then appended line-based candidates), each
    already carrying its tagged ``placements`` and a ``to_html()`` serializer.
    This wraps each into the payload the markdown/json renderers drive table
    emission, reading order and body-text exclusion from:

    * ``bbox``    -- ``tab.bbox``, union-preserved (a grid-ref table keeps its
      reported layout box);
    * ``html``    -- ``tab.to_html()``;
    * ``rows``/``cols``/``cells``/``extract`` -- the reconstructed (rendered) grid
      the ``html`` shows, derived from ``tab.placements`` (see
      :func:`_placement_grid_matrices`): ``extract`` is the per-cell plain-text
      matrix (``None`` for span-covered slots / grid gaps) and ``cells`` the
      matching post-span bbox matrix, both ``rows x cols``.

    Page-level detection+reconstruction seam used by
    ``pymupdf_rag.to_markdown(..., table_output="html")`` and
    ``document_layout.parse_document``; same delegation as :func:`to_html`, on a
    caller-owned page (the caller already removed page rotation before this seam),
    without concatenation so callers keep each table's location and shape.

    Not thread-safe on a shared Page: core caches word/vector extraction as
    attributes on the given ``page`` object, so concurrent calls must each use
    their own ``pymupdf.Page`` instance.
    """
    tf = page.find_tables(use_layout=True, union=True, refine=True)
    result = []
    for tab in (getattr(tf, "tables", None) or []):
        row_count, col_count, cells, extract = _placement_grid_matrices(tab.placements)
        result.append(
            (
                pymupdf.Rect(tab.bbox),
                tab.to_html(),
                row_count,
                col_count,
                cells,
                extract,
            )
        )
    return result
