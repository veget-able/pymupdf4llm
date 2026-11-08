"""Existing T18 structural consumer over shared native material."""
from collections import Counter,defaultdict
from pymupdf import table,_table_refine as refine,_table_spans as spans,_table_geometry as graphics
from pymupdf._table_geometry import _coverage
from . import line_geometry as band
from contextlib import contextmanager
from types import MethodType

def has_separator(entries,start,end,words,page,spans,segments,coverage):
    candidate=spans._span_rect_union(entries[start:end+1])
    selected=spans._span_select_words_in_rect(words,candidate,page=page)
    if not selected:return False
    y0=max(candidate.y0,min(w[1] for _,w in selected));y1=min(candidate.y1,max(w[3] for _,w in selected))
    boundaries=[entries[i].x1 for i in range(start,end)]
    for boundary in boundaries:
        intervals=[(min(a[1],b[1]),max(a[1],b[1])) for a,b in segments if abs(a[0]-b[0])<1.0 and abs((a[0]+b[0])/2-boundary)<=1.0]
        if coverage(intervals,y0,y1)>=1:return True
    return False


def independent_peer_geometry(row_idx,cols,base,body_start,entries,start,end,words,page,spans,band,child_partition):
    parts=entries[start:end+1]
    bounds=spans._span_clustered_boundaries([x for item in base for x in (item['rect'].x0,item['rect'].x1)])
    memberships=[spans._span_select_words_in_rect(words,p,page=page) for p in parts]
    if len(parts)<2 or not all(memberships):return False
    local_bounds=[parts[0].x0,*[p.x1 for p in parts]]
    all_words=[w for group in memberships for _,w in group]
    if band._word_crossings(all_words,local_bounds):return False
    ranges=[spans._span_slot_range(p,bounds) for p in parts]
    # A native span joining an existing wide parent to a populated peer does
    # not prove a new shared parent. The original parent owns its full subtree.
    if any(hi-lo>1 for lo,hi in ranges):
        proofs=[]
        for lo,hi in ranges:
            if hi-lo<=1:continue
            proof=child_partition(row_idx,(lo,hi),base,body_start,spans)
            if proof is None:return False
            if not all(spans._span_select_words_in_rect(words,spans.pymupdf.Rect(b['rect']),page=page) for b in proof['children']):return False
            proofs.append(proof)
        return bool(proofs)
    # Singleton header cells already centered on their own descendant columns
    # are independent peers, even when an over-large R6 prefix includes a body
    # row. No labels or numeric vocabulary are inspected here.
    for p,group in zip(parts,memberships):
        ws=[w for _,w in group]
        if len(ws)!=1 or len(band._cluster_lines(ws))!=1:return False
        a,b=min(w[0] for w in ws),max(w[2] for w in ws)
        if a<p.x0-1.0 or b>p.x1+1.0:return False
        if abs((a+b)/2-(p.x0+p.x1)/2)>band.CENTRE_TOLERANCE*p.width:return False
    for ri in sorted({b['row'] for b in base if row_idx<b['row']<body_start}):
        children=[b for b in base if b['row']==ri and spans._span_ranges_intersect(cols,b['cols'])]
        if sorted(b['cols'] for b in children)==ranges and all(spans._span_select_words_in_rect(words,spans.pymupdf.Rect(b['rect']),page=page) for b in children):return True
    return False


def _members(words,rect,spans,page):
    return spans._span_select_words_in_rect(words,spans.pymupdf.Rect(rect),page=page)


def phrase_groups(words,source_lines,spans,band,*,page=None):
    result=[]
    for source in source_lines:
        box=source['bbox'];selected=[]
        query=spans.pymupdf.Rect(box);height=query.height;query.y0-=height;query.y1+=height
        for i,w in spans._refine_word_candidates(page,words,query):
            if w[0]<box[0]-1 or w[2]>box[2]+1:continue
            cy=(w[1]+w[3])/2;sy=(box[1]+box[3])/2
            if not (box[1]<=cy<=box[3] or w[1]<=sy<=w[3]):continue
            selected.append((i,w))
        if not selected:continue
        ordered=sorted(selected,key=lambda p:p[1][0])
        norm=lambda t:''.join(str(t).split())
        if norm(''.join(w[4] for _,w in ordered))!=norm(source['text']):continue
        # A PDF text span may contain distant independent fields. Reuse the
        # existing line segment contract before treating it as one phrase.
        lines=band._cluster_lines([w for _,w in ordered])
        if len(lines)!=1 or len(lines[0]['segment_words'])!=1:continue
        ids=frozenset(i for i,_ in ordered)
        if ids not in result:result.append(ids)
    return result


def independent_source_phrases(old_result,row_idx,cols,base,body_start,entries,start,end,words,page,spans,band,phrase_groups):
    if not old_result:return False,'native_parent_relation'
    bounds=spans._span_clustered_boundaries([x for item in base for x in (item['rect'].x0,item['rect'].x1)])
    parts=entries[start:end+1];ranges=[spans._span_slot_range(p,bounds) for p in parts]
    members=[frozenset(i for i,_ in _members(words,p,spans,page)) for p in parts]
    combined=frozenset().union(*members)
    if any(hi-lo>1 for lo,hi in ranges):
        return (False,'source_phrase_crosses_existing_parent') if combined in phrase_groups else (True,'original_parent_and_children')
    if combined not in phrase_groups and all(m in phrase_groups for m in members):
        return True,'independent_source_phrases_and_child_slots'
    lo,hi=cols
    # An isolated pair in a parent band is not an independent leaf run. Require
    # populated one-column peers on both sides and actual child correspondence.
    neighbors=[]
    for target in [(lo-1,lo),(hi,hi+1)]:
        matches=[b for b in base if b['row']==row_idx and tuple(b['cols'])==target]
        if len(matches)!=1:return False,'source_phrase_without_leaf_run'
        b=matches[0]
        if not _members(words,b['rect'],spans,page):return False,'source_phrase_without_leaf_run'
        neighbors.append(b)
    for ri in sorted({b['row'] for b in base if row_idx<b['row']<body_start}):
        wanted=[(lo-1,lo),*ranges,(hi,hi+1)]
        children=[b for b in base if b['row']==ri and spans._span_ranges_intersect((lo-1,hi+1),b['cols'])]
        if sorted(tuple(b['cols']) for b in children)==wanted and all(_members(words,b['rect'],spans,page) for b in children):
            return True,'source_leaf_run_and_child_slots'
    return False,'no_complete_leaf_run_children'


def child_partition(row_idx, cols, base, body_start, spans):
    if row_idx>=body_start or cols[1]-cols[0]<=1:return None
    parents=[b for b in base if b['row']==row_idx and spans._span_ranges_intersect(cols,b['cols'])]
    if not parents:return None
    # The candidate parent band must end before the actual child band. Existing
    # rowspans covering that band are occupancy, not descendants of this merge.
    bottom=max(float(p['rect'][3]) for p in parents)
    for ri in sorted({b['row'] for b in base if row_idx<b['row']<body_start}):
        hits=[b for b in base if b['row']==ri and spans._span_ranges_intersect(cols,b['cols'])]
        if len(hits)<2:continue
        if any(b['cols'][0]<cols[0] or b['cols'][1]>cols[1] or float(b['rect'][1])<bottom for b in hits):continue
        ordered=sorted(hits,key=lambda b:b['cols'])
        cursor=cols[0]
        for b in ordered:
            lo,hi=b['cols']
            if lo!=cursor or hi<=lo:break
            cursor=hi
        else:
            if cursor==cols[1]:
                return dict(parent_row=row_idx,columns=cols,child_row=ri,children=tuple(ordered),
                    merge_permission=None,
                    limitation='Exact child tiling is necessary evidence; neither it nor an original coarse parent authorizes a merge.')
    return None


def prepared_phrases(self,page,words):
    source=self.materials.get(self.frame(page),{});key=(id(words),self.frame(page),len(source))
    if key not in self.phrases:
        self.phrases[key]=(words,phrase_groups(words,source.values(),spans,band,page=page))
        self.stats['phrase_productions']+=1
    assert self.phrases[key][0] is words
    return self.phrases[key][1]


def parent_merge(self,reject,reason,row_idx,cols,base,body_start,entries,start,end,words,page):
    if row_idx<body_start:
        physical=has_separator(entries,start,end,words,page,spans,self.segments(page),_coverage)
        peers=independent_peer_geometry(row_idx,cols,base,body_start,entries,start,end,words,page,spans,band,child_partition)
        independent,why=independent_source_phrases(peers,row_idx,cols,base,body_start,entries,start,end,words,page,spans,band,self.prepared_phrases(page,words))
        if physical or independent:
            self.events.append(dict(kind='native_header_partition',row=row_idx,cols=cols,physical=physical,proof=why))
            return True,'proven_parent_partition'
    return reject,reason


def install(runtime):
                runtime.structural_policy.prepared_phrases = MethodType(prepared_phrases, runtime.structural_policy)
                runtime.structural_policy.parent_merge = MethodType(parent_merge, runtime.structural_policy)
