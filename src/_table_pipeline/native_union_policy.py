"""Original union feature algorithms with explicit native input contracts.

The input adapter supplies structural model proposals; the line finder supplies
refinement proposals. Neither class labels nor detector node ownership is read.
"""
from .selection_material import Selection, StructureSelection
from pymupdf import table, _table_union as U










def concrete(entry):
    """Strip the proposal envelope down to its actual resolved cell bounds."""
    cells=[tuple(c) for row in entry[1] for c in row if c is not None]
    if not cells:return None
    box=U.pymupdf.Rect(min(c[0] for c in cells),min(c[1] for c in cells),
                       max(c[2] for c in cells),max(c[3] for c in cells))
    return U._TableGridEntry(box,entry[1],dict(entry.bbox_provenance),
        **{k:getattr(entry,k) for k in ('append_only','append_context','append_index',
                                      'append_materials') if hasattr(entry,k)})





def fuse(runtime,page,existing,candidates,**kwargs):
    material=runtime.page_material(page)
    existing=[e for e in map(concrete,existing) if e is not None]
    candidates=[e for e in map(concrete,candidates) if e is not None]
    selection=StructureSelection()

    def partition_covered(original,children,live_page):
        # Same existing coverage contract, now on actual native occurrences.
        nodes=material.sources_in(tuple(original[0]))
        centers=[((s.bbox[0]+s.bbox[2])/2,(s.bbox[1]+s.bbox[3])/2) for s in nodes]
        accounted=sum(not any(b[0]<=x<b[2] for b,_ in children)
                      or any(b[0]<=x<b[2] and b[1]<=y<b[3] for b,_ in children)
                      for x,y in centers)
        if centers and accounted*2 < len(centers):return False
        if runtime.parent_coherence is not None:
            return runtime.parent_coherence(original, children, live_page, U)
        return True

    # Reuse the actual product primitive; do not replace its distinct
    # refinement/split/append responsibilities with a new quality ranking.
    entries=U._union_replace_append_base(existing,candidates,page=page,
        grid_ref=kwargs['grid_ref'],grid_ref_iou=kwargs['grid_ref_iou'],
        span_mult_gate=kwargs['span_mult_gate'],span_mult_threshold=kwargs['span_mult_threshold'],
        _selection=selection,_partition_covered=partition_covered)

    if runtime.union_selection_consumer is not None:
        runtime.union_selection_consumer(runtime, page, selection)
    return entries



def install(runtime):
    from types import MethodType
    from .proposal_adapter import model_table_proposals
    runtime.union_consumer = fuse
    runtime.primaries = MethodType(lambda self, page: model_table_proposals(page), runtime)
