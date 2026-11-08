"""Explicit runtime-owned preparation and existing R6 decision transport.

No experiment adapter is imported here. Native cell/source objects and the
existing PreparedCorrespondence own the data. Consumers pass their native
producer directly; current runtime scope supplies lifetime and proof context.
"""
from collections import Counter,defaultdict
from contextlib import contextmanager
import time,json,hashlib
import pymupdf
from pymupdf import table,_table_spans as spans
from . import header_material as material
from .header_prepared import PreparedCorrespondence
from .placement_geometry import _native_occupancy
from pymupdf._table_headers import HeaderRegion


class HeaderService:
    def __init__(self):
        self.prepared=PreparedCorrespondence()
        self.stats=Counter();self.counters=Counter();self.transfer=Counter()
        self.preparation_stats=Counter();self.events=[];self.stage='final'
        self.refinements=[];self.decisions=material.Store()

    @contextmanager
    def lifetime(self):
        with self.prepared.lifetime():yield

    @contextmanager
    def refinement_scope(self):
        self.refinements.append(dict(placements={},regions={}))
        try:yield
        finally:self.refinements.pop()

    def cache(self,name):
        scope=self.prepared.scope
        return scope.setdefault('service_'+name,{}) if scope is not None else None

    def view(self,name,key,produce):
        cache=self.cache(name);self.stats[name+'_requests']+=1
        if cache is not None and key in cache:
            self.stats[name+'_reuse']+=1;return cache[key]
        tick=time.perf_counter_ns();out=produce()
        self.stats[name+'_producer_ns']+=time.perf_counter_ns()-tick;self.stats[name+'_produced']+=1
        if cache is not None:cache[key]=out
        return out

    def text_grid(self,grid,produce):
        key=tuple(tuple(c.text for c in row) for row in grid)
        return self.view('text_grid',key,lambda:produce(grid))

    def span_rows(self,grid,produce):
        key=tuple(tuple((c.text,c.colspan,c.rowspan) for c in row) for row in grid)
        return self.view('span_rows',key,lambda:produce(grid))

    def occupancy(self,rows,produce):
        return self.view('occupancy',tuple(tuple(row) for row in rows),lambda:produce(rows))

    def matrices(self,grid,produce):
        key=tuple(tuple((tuple(c.bbox) if c.bbox is not None else None,c.text,c.colspan,c.rowspan) for c in row) for row in grid)
        return self.view('matrices',key,lambda:produce(grid))

    @staticmethod
    def placement_state(page,cells):
        words=getattr(page,'_refine_words_cache',None);text_spans=getattr(page,'_span_text_spans_cache',None)
        if words is None or text_spans is None:return None
        return (page,page.number,page.rotation,tuple(page.rect),tuple(page.cropbox),
            pymupdf.TEXTFLAGS_WORDS,pymupdf.TEXTFLAGS_DICT,pymupdf.TEXTFLAGS_RAWDICT,
            bool(pymupdf.TOOLS.set_small_glyph_heights()),bool(pymupdf.TOOLS.unset_quad_corrections()),
            id(words),len(words),id(text_spans),len(text_spans),
            tuple(tuple(None if c is None else tuple(c) for c in row) for row in cells))

    def placements(self,page,cells,produce,*,strict_colspan=False,header_row_count=None):
        stats=self.preparation_stats
        if strict_colspan or not self.refinements:
            stats['strict_or_outside_calls']+=1
            grid=produce(page,cells,strict_colspan=strict_colspan,header_row_count=header_row_count)
        else:
            stats['preliminary_requests']+=1;tick=time.perf_counter_ns()
            try:
                key=self.placement_state(page,cells);cache=self.refinements[-1]['placements']
                entry=cache.get(key) if key is not None else None
                if entry is not None:
                    stats['reuse_hits']+=1;stats['cloned_cells']+=sum(map(len,entry[0]))
                    assert entry[1] is page._refine_words_cache and entry[2] is page._span_text_spans_cache
                    grid=[[c.clone() for c in row] for row in entry[0]]
                else:
                    stats['producer_calls']+=1;grid=produce(page,cells,strict_colspan=False,header_row_count=header_row_count)
                    key=self.placement_state(page,cells)
                    if key is not None:
                        cache[key]=([[c.clone() for c in row] for row in grid],page._refine_words_cache,page._span_text_spans_cache)
                        stats['stored_states']+=1;stats['peak_scope_states']=max(stats['peak_scope_states'],len(cache))
            finally:stats['preliminary_ns']+=time.perf_counter_ns()-tick
        if self.prepared.scope is not None:
            self.prepared.stats['placement_metadata_consumers']+=1;self.prepared.prepare(grid)
        return grid

    def bootstrap_region(self,rows,produce):
        produce=lambda rows:HeaderRegion(0,())
        if not self.refinements:return produce(rows)
        stats=self.preparation_stats;stats['region_requests']+=1;tick=time.perf_counter_ns()
        try:
            key=tuple(tuple(row) for row in rows);cache=self.refinements[-1]['regions']
            if key in cache:stats['region_hits']+=1;return cache[key]
            stats['region_producer_calls']+=1;out=produce(rows);cache[key]=out
            stats['maximum_region_states']=max(stats['maximum_region_states'],len(cache));return out
        finally:stats['region_ns']+=time.perf_counter_ns()-tick


    def state(self,header,page):
        key,refs=header.state(page)
        if key is None:return None,None
        return (id(header),header.provider_stamp(),id(self.prepared.scope),key),(header,refs)

    def signature(self,grid):
        self.stats['live_signature_produced']+=1;return material.fingerprint(grid)

    def correspondence(self,header,old,new,region,grid):
        root=old.root or old
        key=(id(old.data),old.region.top_header_rows,tuple(old.region.section_header_rows),id(new),region.top_header_rows,tuple(region.section_header_rows),id(root),header.transport.correspondence_key(root.event))
        cache=self.cache('proof');self.stats['proof_requests']+=1
        if cache is not None and key in cache:self.stats['proof_reuse']+=1;return cache[key]
        started=time.perf_counter_ns();out=header.transport.correspondence(old,new,region,grid)
        self.stats['proof_produced']+=1;self.stats['proof_producer_ns']+=time.perf_counter_ns()-started
        if cache is not None:cache[key]=out
        return out

    def run_model(self,session,*args,**kwargs):
        started=time.perf_counter_ns()
        try:return session.run(*args,**kwargs)
        finally:
            self.counters[self.stage+'_onnx_calls']+=1;self.counters[self.stage+'_onnx_ns']+=time.perf_counter_ns()-started

    def apply_roles(self,header,page,grid,region,*,purpose="final",table_bbox=None):
        started=time.perf_counter_ns();self.stats['header_service_requests']+=1
        try:
            out=self._apply_roles(header,page,grid,region,purpose=purpose,table_bbox=table_bbox)
            event=header.decisions.get(id(out[0]),(None,{}))[1];self.stats['header_result_'+event.get('status','unknown')]+=1
            return out
        finally:
            elapsed=time.perf_counter_ns()-started;self.stats['header_service_ns']+=elapsed;self.counters[self.stage+'_role_ns']+=elapsed

    def _apply_roles(self,header,page,grid,region,*,purpose,table_bbox=None):
        if purpose not in ('structure','final'):raise ValueError('Unknown header result purpose')
        p=self.prepared;stage=self.stage;self.transfer[stage+'_requests']+=1;started=time.perf_counter_ns();key,refs=self.state(header,page)
        store=self.decisions;header._verified_transfer_store=store
        transport=header.transport
        previous=store.by_grid.get(id(grid))
        if previous is not None and previous.grid is grid and (previous.event.get('result_purpose')!=purpose or getattr(previous,'provider',None) is not header or previous.state!=key):
            # The immutable source/content remains shared. A second purpose's
            # mutable tags cannot edit the still-live first judgment's view.
            grid=[[cell.clone() for cell in row] for row in grid]
            self.stats['cross_purpose_mutable_views']+=1
        new=None;failure='no_same_material_decision';title_hint=None;title_conflict=False;title_rejections=Counter();query=None;query_origin=None
        if key is not None:
            try:new=p.material(grid)
            except ValueError as error:failure=str(error)
            if new is not None and transport is not None:
                for old in reversed(store.index.get((key,frozenset(new.counts.items())),())):
                    root=old.root or old
                    live=root in store.origins and any(e is root.event for e in header.events)
                    live=live and material.fingerprint(root.grid)==root.signature and material.fingerprint(old.grid)==old.signature and getattr(root,'title_snapshot',None)==header.decision_signature(root.event)
                    if not live:
                        self.transfer['rejected_live_decision_edited']+=1
                        continue
                    if live:
                        if query is None:
                            borrowed=transport.prepared_query(old,new,grid)
                            if borrowed is not None:query,query_origin=borrowed
                        if purpose=='final':
                            alignment,why=transport.title_correspondence(root,new,grid)
                            if alignment is not None and title_hint is None:title_hint=alignment
                            elif alignment is not None and not transport.same_alignment(alignment,title_hint):title_conflict=True
                            elif why:title_rejections[why]+=1
                    if root.event.get('result_purpose')!=purpose:
                        self.transfer['rejected_cross_purpose_'+str(root.event.get('result_purpose'))+'_to_'+purpose]+=1
                        continue
                    mapped,reason,context=self.correspondence(header,old,new,region,grid)
                    if mapped is None:failure=reason;continue
                    tagged=table._refine_tag_grid(grid,mapped.top_header_rows)
                    event=transport.preserve_event(region,mapped,root,reason,len(grid),purpose)
                    proof=material.Proof(tagged,new,mapped,p.roles(new,mapped),key,refs,self.signature(tagged),event,root)
                    proof.provider=header;proof.provider_stamp=header.provider_stamp()
                    store.add(proof);header.decisions[id(tagged)]=(tagged,event);header.events.append(event)
                    self.events.append(dict(event,observed_stage=stage,seconds=(time.perf_counter_ns()-started)/1e9))
                    proof.context_proof=context;event['dependency_context_verified']=True;self.events[-1]['dependency_context_verified']=True
                    self.transfer[stage+'_transfers']+=1;self.transfer[stage+'_validation_ns']+=time.perf_counter_ns()-started
                    return tagged,mapped
        else:failure='no_stable_post_ocr_material_context'
        self.transfer['rejected_'+failure]+=1;self.transfer[stage+'_validation_ns']+=time.perf_counter_ns()-started
        self.transfer[stage+('_model_attempts' if transport is not None else '_provider_evaluations')]+=1;before=self.counters[stage+'_onnx_calls'];tick=time.perf_counter_ns()
        if title_conflict:title_hint=None;title_rejections['ambiguous_verified_title_alignments']+=1
        input_kw={'table_bbox':table_bbox} if table_bbox is not None else {}
        tagged,predicted,result_query=header.evaluate(page,grid,region,purpose=purpose,alignment=title_hint,prepared=query,**input_kw)
        event=header.decisions.get(id(tagged),(None,{}))[1];event['title_transport_rejections']=dict(title_rejections)
        actual=self.counters[stage+'_onnx_calls']-before;event['actual_onnx_calls']=actual;event['onnx_executed']=bool(actual)
        event['provider']=header.provider_name
        event['input_state']=hashlib.sha256(repr((key,material.fingerprint(tagged))).encode()).hexdigest()
        event['provider_stamp']=repr(header.provider_stamp())
        event['live_signature']=hashlib.sha256(repr(material.fingerprint(tagged)).encode()).hexdigest()
        self.events.append(dict(event,observed_stage=stage,seconds=(time.perf_counter_ns()-tick)/1e9))
        self.transfer[stage+'_model_calls']+=actual
        if not actual and transport is not None:
            self.transfer[stage+('_actual_query_reuses' if result_query else '_unsupported_inputs')]+=1
        elif transport is None:
            self.transfer[stage+('_provider_confirmed' if header.confirmed(event) else '_provider_unconfirmed')]+=1
        if key is not None and header.confirmed(event):
            try:
                data=new if tagged is grid and new is not None else p.material(tagged)
                p.geometry(data,_native_occupancy);roles=p.roles(data,predicted)
            except ValueError as error:self.transfer['unstorable_'+str(error)]+=1
            else:
                proof=material.Proof(tagged,data,predicted,roles,key,refs,self.signature(tagged),event,None)
                proof.title_snapshot=header.decision_signature(event)
                proof.provider=header;proof.provider_stamp=header.provider_stamp()
                if transport is not None:transport.retain_query(proof,result_query,query_origin,actual)
                store.add(proof)
        return tagged,predicted

    def valid(self,header,grid,event,*,purpose=None):
        self.stats['decision_validation_requests']+=1
        if purpose is not None and event.get('result_purpose')!=purpose:return False
        entry=header.decisions.get(id(grid))
        if entry is None or entry[0] is not grid or entry[1] is not event:return False
        store=getattr(header,'_verified_transfer_store',None);proof=store.by_grid.get(id(grid)) if store else None
        if proof is not None and (getattr(proof,'provider',None) is not header or getattr(proof,'provider_stamp',None)!=header.provider_stamp()):return False
        if header.confirmed(event):
            if event.get('provider')!=header.provider_name or event.get('provider_stamp')!=repr(header.provider_stamp()):return False
            if event.get('live_signature')!=hashlib.sha256(repr(material.fingerprint(grid)).encode()).hexdigest():return False
            return proof is None or (proof.grid is grid and proof.event is event and proof.signature==self.signature(grid) and getattr(proof,'title_snapshot',None)==header.decision_signature(event))
        if event.get('status')!='preserved' or header.transport is None:return False
        if proof is None or proof.grid is not grid or proof.event is not event or proof.signature!=self.signature(grid):return False
        root=proof.root or proof
        if root.event.get('result_purpose')!=event.get('result_purpose'):return False
        if material.fingerprint(root.grid)!=root.signature or getattr(root,'title_snapshot',None)!=header.decision_signature(root.event):return False
        if root not in store.origins or not header.confirmed(root.event) or not any(e is root.event for e in header.events):return False
        return header.transport.valid_transfer(proof)

    def valid_table(self,header,tab):
        self.stats['table_validation_requests']+=1;entry=header.decisions.get(id(tab.placements))
        if entry is None or not self.valid(header,tab.placements,entry[1],purpose='final'):return False
        if header.confirmed(entry[1]):return True
        proof=header._verified_transfer_store.by_grid[id(tab.placements)]
        return tab.header_rows==proof.region.top_header_rows and tuple(tab.section_rows)==tuple(proof.region.section_header_rows)
