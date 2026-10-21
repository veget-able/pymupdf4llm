"""Assign retained parent nodes to grid geometry, without deciding header roles.

Consumes final placements and retained source nodes. No document reads, model
calls, GT, filenames, or expected shapes. New cells carry neutral ``td`` roles;
the existing downstream role stage remains responsible for their semantics.
"""
from collections import defaultdict
from copy import copy
from statistics import median
import re

from pymupdf._table_spans import SpanCell
from pymupdf4llm.helpers.table_html.reconstruct import _table_grid_matrices
from pymupdf4llm._table_pipeline.fragment_consolidation import column_intervals
from pymupdf4llm._table_pipeline.union_content_recovery import _bands, _grid_rows_y, _union_box


def _intersects(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _updated(tab, rows, added_before, used):
    # Unlike content recovery's _replace, preserve section roles and never
    # classify a new row as a header. Existing cell objects are retained.
    child = copy(tab)
    child.placements = rows
    child.cells = [tuple(c.bbox) for row in rows for c in row if c.bbox is not None]
    child._bbox = tuple(_union_box(child.cells))
    child.section_rows = tuple(r + added_before for r in tab.section_rows)
    child.header_rows = 0 if added_before else tab.header_rows
    child.bbox_provenance = dict(tab.bbox_provenance,
        bbox_source='union_recovery', grid_source='mixed',
        bbox_operation='grid_node_absorption', recovery_revision='susan-grid-ownership/1',
        recovery_source_bboxes=[list(tab.bbox)],
        recovery_steps=list(tab.bbox_provenance.get('recovery_steps', [])) + ['grid_node_absorption'])
    child.grid_ownership_nodes = sorted(used)
    child.grid_roles_pending = True
    return child


def absorb_grid_nodes(tables, nodes, accepted, *, obstacles=(), failures=None):
    """Extend existing rows/columns around uniquely assignable residual nodes.

    Parent ownership is the caller's grouping contract. Match existing column
    intervals before grouping rows; distant words in one row remain together.
    Competing tables are ranked by edge distance, not traversal order.
    """
    from pymupdf4llm._table_pipeline.table_content_recovery import node_sources
    residual = [n for n in nodes if n.index not in accepted and n.text.strip()]
    if not residual or not tables:
        return list(tables), []
    placements = [c for t in tables for row in t.placements for c in row if c.bbox is not None]
    pending = []
    for n in residual:
        x, y = (n.bbox[0]+n.bbox[2])/2, (n.bbox[1]+n.bbox[3])/2
        # Existing overlapping cells require character/occurrence resolution;
        # do not duplicate their ambiguous content into a fresh cell.
        if any(c.bbox[0]-1 <= x <= c.bbox[2]+1 and c.bbox[1]-1 <= y <= c.bbox[3]+1 for c in placements):
            continue
        pending.append(n)
    if not pending:
        return list(tables), []
    geometry = []
    for t in tables:
        nr, nc, cells, texts = _table_grid_matrices(t, retain=True)
        geometry.append((nr, nc, cells, texts, column_intervals(cells), _grid_rows_y(cells)))
    vertical = defaultdict(list)
    lateral = defaultdict(list)
    for n in pending:
        x0,y0,x1,y1 = n.bbox
        cx,cy=(x0+x1)/2,(y0+y1)/2
        h=max(y1-y0,1.)
        choices=[]
        for ti,(t,g) in enumerate(zip(tables,geometry)):
            nr,nc,cells,texts,cols,rows=g
            if not nc or any(v is None for v in cols):
                continue
            b=t.bbox
            ci=[j for j,(lo,hi) in enumerate(cols) if lo-1 <= x0 and x1 <= hi+1]
            if len(ci)==1 and (y1 <= b[1] or y0 >= b[3]):
                side='above' if y1 <= b[1] else 'below'
                gap=b[1]-y1 if side=='above' else y0-b[3]
                if gap <= max(25.,5*h):
                    corridor=(x0,y0,x1,b[1]) if side=='above' else (x0,b[3],x1,y1)
                    if not any(j!=ti and _intersects(corridor,other.bbox) for j,other in enumerate(tables)):
                        choices.append((gap,ti,side,ci[0]))
            # Existing row alignment can support an external column. Several
            # external columns stay distinct through their actual x intervals.
            ri=[j for j,r in enumerate(rows) if r and r[0] <= cy < r[1]]
            if len(ri)==1 and (x1 <= b[0] or x0 >= b[2]):
                side='left' if x1 <= b[0] else 'right'
                gap=b[0]-x1 if side=='left' else x0-b[2]
                if gap <= median(hi-lo for lo,hi in cols):
                    corridor=(x0,y0,b[0],y1) if side=='left' else (b[2],y0,x1,y1)
                    if not any(j!=ti and _intersects(corridor,other.bbox) for j,other in enumerate(tables)):
                        choices.append((gap,ti,side,ri[0]))
        if not choices:
            continue
        choices.sort()
        # Equal column geometry above and below is no evidence that a free
        # inter-table row belongs to the nearer table. Keep that tie unresolved.
        best=choices[0]
        if best[2] in ('above','below') and any(
            option[2] in ('above','below') and option[2]!=best[2]
            and all(abs(a-b)<1 for a,b in zip(geometry[best[1]][4][best[3]],geometry[option[1]][4][option[3]]))
            for option in choices[1:]):
            continue
        if len(choices)>1 and abs(choices[0][0]-choices[1][0])<1.:
            continue
        gap,ti,side,slot=choices[0]
        (vertical if side in ('above','below') else lateral)[(ti,side)].append((n,slot))
    proposals={}
    decisions=[]
    for ti,t in enumerate(tables):
        if not any((ti,side) in groups for groups,sides in ((lateral,("left","right")),(vertical,("above","below"))) for side in sides):
            continue
        nr,nc,cells,texts,cols,rowbands=geometry[ti]
        blockers = [other.bbox for j,other in enumerate(tables) if j != ti] + [other.bbox for other in obstacles]
        rows=[list(row) for row in t.placements]
        used=set()
        # Lateral completion uses the original row extent. It never collapses
        # a spanning label and the next column's A/B/... labels into one column.
        for side in ('left','right'):
            items=lateral.get((ti,side),[])
            if not items or any(r is None for r in rowbands):
                continue
            intervals=_bands([(n.bbox[0],n.bbox[2]) for n,_ in items],4.)
            grouped=[[(n,ri) for n,ri in items if lo <= (n.bbox[0]+n.bbox[2])/2 <= hi] for lo,hi in intervals]
            repeated=any(len({ri for _,ri in group})>=2 for group in grouped)
            added=[[] for _ in rows]
            for (lo,hi),colitems in zip(intervals,grouped):
                # Require repeated row support before creating an external
                # column; individual labels remain unresolved, not captions.
                if len({ri for _,ri in colitems})<2 and not repeated:
                    continue
                # The entire column is proposed, including its empty middle cells.
                boxes=[(lo,band[0],hi,band[1]) for band in rowbands]
                if any(_intersects(box,other) for box in boxes for other in blockers):
                    continue
                for ri,band in enumerate(rowbands):
                    ns=sorted([n for n,r in colitems if r==ri],key=lambda n:(n.bbox[1],n.bbox[0]))
                    added[ri].append(SpanCell((lo,band[0],hi,band[1]),' '.join(n.text for n in ns),1,1,'td',sources=node_sources(ns)))
                    used.update(n.index for n in ns)
            rows=[extra+row if side=='left' else row+extra for row,extra in zip(rows,added)]
        # Vertical rows use the resulting column topology after lateral changes.
        current_cols=cols
        if used and any((ti,side) in vertical for side in ("above","below")):
            working=copy(t)
            working.placements=rows
            _,_,current_cells,_=_table_grid_matrices(working, retain=True)
            current_cols=column_intervals(current_cells)
        before=[];after=[]
        for side,destination in (('above',before),('below',after)):
            items=vertical.get((ti,side),[])
            if not items:
                continue
            bands=_bands([(n.bbox[1],n.bbox[3]) for n,_ in items],2.)
            for lo,hi in bands:
                ns=[n for n,_ in items if lo <= (n.bbox[1]+n.bbox[3])/2 <= hi]
                occupied={slot for n,slot in items if n in ns}
                repeated_columns=len(occupied)>=max(2,nc*.5)
                numeric_continuation=side=='below' and all(any(c.isdigit() for c in n.text) and re.fullmatch(r'[+\-\d.,%()]+',n.text.strip()) for n in ns)
                if not repeated_columns and not numeric_continuation:
                    continue
                newrow=[];row_used=set()
                for a,b in current_cols:
                    selected=sorted([n for n in ns if a-1<=n.bbox[0] and n.bbox[2]<=b+1],key=lambda n:n.bbox[0])
                    newrow.append(SpanCell((a,lo,b,hi),' '.join(n.text for n in selected),1,1,'td',sources=node_sources(selected)))
                    row_used.update(n.index for n in selected)
                # Validate the actual proposed grid cells, without crop padding.
                if len(row_used)!=len(ns) or any(_intersects(cell.bbox,other) for other in blockers for cell in newrow):
                    continue
                destination.append(newrow);used.update(row_used)
        if used:
            proposed_rows = before + rows + after
            old_cell_ids = {id(c) for row in t.placements for c in row}
            new_cells = [c for row in proposed_rows for c in row if id(c) not in old_cell_ids]
            # A supported row/column also creates blank cells. Do not adopt a
            # proposal that covers another unresolved source while omitting it
            # from the producer's selected inputs. Ambiguity is not resolved by
            # turning its physical position into an empty cell. Keep the prior
            # grid; the ordinary external-text boundary can then handle it.
            omitted = [n.index for n in nodes if n.index not in used and n.index not in accepted
                       and n.text.strip() and any(c.bbox[0] <= (n.bbox[0]+n.bbox[2])/2 <= c.bbox[2]
                           and c.bbox[1] <= (n.bbox[1]+n.bbox[3])/2 <= c.bbox[3] for c in new_cells)]
            if omitted:
                if failures is not None:
                    failures.append(dict(table=ti,reason="new-cell-omits-source",nodes=omitted))
                continue
            child=_updated(t,proposed_rows,len(before),used)
            proposals[ti]=child
            decisions.append(dict(operation='grid_node_absorption',table=ti,nodes=sorted(used),
                                  added_above=len(before),added_below=len(after)))
    # Validate complete proposals against sibling proposals too. Reject both
    # sides of a collision so table traversal order cannot decide ownership.
    blocked=set()
    for ti,child in proposals.items():
        old_ids={id(c) for row in tables[ti].placements for c in row}
        added=[c for row in child.placements for c in row if id(c) not in old_ids]
        for tj,other in proposals.items():
            if ti != tj and any(_intersects(c.bbox,other.bbox) for c in added):
                blocked.update((ti,tj))
    from pymupdf4llm._table_pipeline.table_content_recovery import cell_ownership
    output=list(tables)
    owners=accepted
    adopted=[]
    for decision in decisions:
        ti=decision['table']
        if ti in blocked:
            continue
        candidate=list(output)
        candidate[ti]=proposals[ti]
        verified=cell_ownership(candidate,nodes)
        planned=set(decision['nodes'])
        # Node containment/attempt logs are not proof of actual text acceptance.
        if not set(owners) <= set(verified) or not planned <= set(verified):
            continue
        if any(verified[i]['table'] != ti for i in planned):
            continue
        output,owners=candidate,verified
        adopted.append(decision)
    return output,adopted
