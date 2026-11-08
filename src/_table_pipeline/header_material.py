"""Preserve a real R6 judgment through verified material/cell correspondence.

No text classifier, header heuristic, or row/span repair is introduced. A changed
physical grid alone does not force ONNX. A proof retains the real originating
ONNX event, current source roles, immutable source references and mapped region.
"""
from collections import Counter,defaultdict
from dataclasses import dataclass,replace
import json,time


def source_key(s):
    return (s.kind,id(s.collection),int(s.index),tuple(s.bbox),s.text,
        json.dumps(s.scope,ensure_ascii=False,sort_keys=True),tuple(tuple(b) for b in s.glyph_boxes))


def fingerprint(grid):
    return tuple(tuple((tuple(c.bbox) if c.bbox is not None else None,c.text,int(c.colspan),int(c.rowspan),c.tag,
        id(c.source_content)) for c in row) for row in grid)


@dataclass(frozen=True)
class Cell:
    bbox: object
    text: str
    colspan: int
    rowspan: int
    sources: tuple
    content: object


@dataclass(frozen=True)
class Material:
    rows: tuple
    counts: object
    empty_rows: object


def material(grid):
    rows=[];counts=Counter();empty_rows={}
    for ri,row in enumerate(grid):
        saved=[]
        for c in row:
            c.validate_source_content()
            content=c.source_content
            keys=tuple(source_key(s) for s in content.sources) if content is not None else ()
            if c.text.strip() and not keys:raise ValueError('text_without_source_proof')
            counts.update(keys)
            saved.append(Cell(tuple(c.bbox) if c.bbox is not None else None,c.text,int(c.colspan),int(c.rowspan),keys,content))
        rows.append(tuple(saved))
        if not any(c.sources or c.text.strip() for c in saved):
            empty_rows[ri]=tuple((c.bbox,c.colspan,c.rowspan) for c in saved)
    return Material(tuple(rows),counts,empty_rows)


def source_roles(data,region):
    roles={}
    for ri,row in enumerate(data.rows):
        role=(ri<region.top_header_rows,ri in region.section_header_rows)
        for c in row:
            for key in c.sources:
                if key in roles and roles[key]!=role:raise ValueError('old_source_has_mixed_roles')
                roles[key]=role
    return roles


def span_geometry(data,occupancy):
    rows=[[(c.text,c.colspan,c.rowspan) for c in row] for row in data.rows]
    cells,width=occupancy(rows);occupied=set()
    for r0,r1,c0,c1,_ in cells:
        if r1>len(rows):raise ValueError('span_exceeds_rows')
        for r in range(r0,r1):
            for col in range(c0,c1):
                if (r,col) in occupied:raise ValueError('overlapping_span_occupancy')
                occupied.add((r,col))
    return width


def header_layout(data,depth,xbounds,spans):
    ranks={ri:i for i,ri in enumerate(ri for ri,row in enumerate(data.rows[:depth]) if any(c.sources or c.text.strip() for c in row))}
    groups=[]
    for ri in ranks:
        group=[]
        for c in data.rows[ri]:
            if ri+c.rowspan>depth:raise ValueError('header_span_crosses_body')
            cols=spans._span_slot_range(spans.pymupdf.Rect(c.bbox),xbounds) if c.bbox is not None else None
            cover=tuple(rank for row,rank in ranks.items() if ri<=row<ri+c.rowspan)
            group.append((frozenset(Counter(c.sources).items()),cols,cover))
        groups.append(tuple(group))
    return tuple(groups)


def correspondence(old,new,new_region,spans,occupancy):
    """Map source roles, then validate prefix, header hierarchy and section context."""
    if not old.data.counts:return None,'empty_source_set'
    if old.data.counts!=new.counts:return None,'material_multiset_changed'
    roles=[]
    for ri,row in enumerate(new.rows):
        votes={old.roles[key] for c in row for key in c.sources}
        if len(votes)>1:return None,'header_body_or_section_source_mix'
        if votes:roles.append(next(iter(votes)));continue
        matches={((oi<old.region.top_header_rows),(oi in old.region.section_header_rows))
            for oi,shape in old.data.empty_rows.items() if shape==new.empty_rows.get(ri)}
        if len(matches)!=1:return None,'empty_row_correspondence_unknown'
        roles.append(next(iter(matches)))
    depth=max((ri+1 for ri,role in enumerate(roles) if role[0]),default=0)
    if any(not role[0] for role in roles[:depth]):return None,'header_role_not_a_prefix'
    sections=tuple(ri for ri,role in enumerate(roles) if role[1])
    if sections!=tuple(new_region.section_header_rows):return None,'section_context_changed'
    try:
        span_geometry(new,occupancy)
        xbounds=spans._span_clustered_boundaries([x for data in (old.data,new) for row in data.rows for c in row if c.bbox is not None for x in (c.bbox[0],c.bbox[2])])
        if header_layout(old.data,old.region.top_header_rows,xbounds,spans)!=header_layout(new,depth,xbounds,spans):
            return None,'header_cell_or_column_correspondence_changed'
    except ValueError as error:return None,str(error)
    return replace(new_region,top_header_rows=depth),'verified_source_and_header_geometry'


@dataclass(eq=False)
class Proof:
    grid: object
    data: object
    region: object
    roles: object
    state: object
    materials: object
    signature: object
    event: object
    root: object


class Store:
    def __init__(self):self.index=defaultdict(list);self.by_grid={};self.origins=[]
    def add(self,p):
        self.index[(p.state,frozenset(p.data.counts.items()))].append(p)
        self.by_grid[id(p.grid)]=p
        if p.root is None:self.origins.append(p)

