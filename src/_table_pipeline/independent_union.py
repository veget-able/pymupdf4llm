"""Intrinsic native candidate material; final selection belongs to union."""
import pymupdf
from pymupdf import table, _table_union as U
from pymupdf._table_append_context import AppendContext

def admit_groups(page, groups, *, paths=(), edges=()):
    """One native positive admission contract, independent of Layout classes."""
    context=AppendContext(U.CHARS,edges,paths,getattr(page,'_table_ruling_image_boxes',()))
    candidates=[];kept=[];seen=set();glyphs=U._UnionGlyphIntervals(U.CHARS)
    for cells in groups:
        box=pymupdf.Rect(min(c[0] for c in cells),min(c[1] for c in cells),max(c[2] for c in cells),max(c[3] for c in cells))
        grid=[r.cells for r in U._cells_to_rows(cells)]
        if box.is_empty or not grid:continue
        key=tuple(round(x) for x in box)
        if key in seen:continue
        seen.add(key)
        support=U._union_grid_has_2d_content_support(grid,glyphs=glyphs)
        image=any(pymupdf.Rect(b).contains(box) for b in context.image_boxes)
        index=context.add(box,grid,image,support)
        kept.append(cells)
        candidates.append(U._TableGridEntry(box,grid,dict(bbox_source='find_tables',grid_source='find_tables',
            bbox_operation='line_detection',source_gnn_indices=[]),append_context=context,append_index=index))
    # These are structural proposals, not independently approved output tables.
    # The common selector registers ALL native/TGIF peers and applies the same
    # intrinsic admission contract once. Early rejection here would prevent a
    # valid weak/partial grid from competing with the coarser structure.
    return kept,candidates



def install(runtime):
    runtime.candidate_admission = admit_groups
