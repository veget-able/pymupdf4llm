"""Post-model title alignment and section annotation on existing placements."""
from pymupdf._table_headers import section_header_rows
from .r6_header_contract import (_placement_title_input,leading_removed,prefix_depth)
from .header_title_alignment import aligned_data

def posterior_title_offset(grid,labels,sections,*,dependencies=None):
    # Material/source ownership remains unchanged. Only the existing title view
    # sees the actual model's individual row roles, including td title candidates.
    view=[[c.clone() for c in row] for row in grid]
    for ri,row in enumerate(view):
        for c in row:c.tag='th' if labels[ri] else 'td'
    raw,nonempty=_placement_title_input(view,sections)
    if not nonempty or not nonempty[0]:return 0
    k=leading_removed(raw.data,aligned_data(raw,1,dependencies=dependencies))
    # The old k<=heuristic_depth gate is the removed input dependency. Actual
    # model row tags now supply the title helper's header membership instead.
    return k if k is not None and 0<k<len(labels) and all(nonempty[:k]) else 0

def posterior_sections(grid,depth):
    return tuple(section_header_rows([[c.text for c in row] for row in grid],depth))
