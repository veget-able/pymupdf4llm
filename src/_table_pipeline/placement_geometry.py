"""Shared placement rows/occupancy, with the existing producer and scope."""

def _native_occupancy(rows):
    """Resolve ragged span rows into (r0, r1, c0, c1, text) cells and a column
    count, exactly as an HTML renderer places them: ``rows`` is row-major and
    each entry is ``(text, colspan, rowspan)``."""
    occupied, cells = set(), []
    for ri, row in enumerate(rows):
        ci = 0
        for text, cs, rs in row:
            cs, rs = max(1, int(cs)), max(1, int(rs))
            while (ri, ci) in occupied:
                ci += 1
            for rj in range(ri, ri + rs):
                for cj in range(ci, ci + cs):
                    occupied.add((rj, cj))
            cells.append((ri, ri + rs, ci, ci + cs, " ".join(str(text or "").split())))
            ci += cs
    ncols = max((c for _, c in occupied), default=-1) + 1
    return cells, ncols


def _native_grid_rows(grid):
    """Adapt a SpanCell placement grid to ``leaf_completion_depth`` rows."""
    return [[(cell.text, cell.colspan, cell.rowspan) for cell in row] for row in grid]


def occupancy(rows):
    from pymupdf._table_pipeline import current
    runtime=current()
    return runtime.header_service.occupancy(rows, _native_occupancy) if runtime is not None else _native_occupancy(rows)


def grid_rows(grid):
    from pymupdf._table_pipeline import current
    runtime=current()
    return runtime.header_service.span_rows(grid, _native_grid_rows) if runtime is not None else _native_grid_rows(grid)

