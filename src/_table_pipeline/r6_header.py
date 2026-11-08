"""R6 classification for structural and final live post-OCR placements."""
from dataclasses import replace, dataclass
import hashlib,json
from .header_semantic_order import posterior_title_offset,posterior_sections
from contextlib import contextmanager

import numpy as np
import onnxruntime as ort
import pymupdf
from pymupdf import table

from .placement_geometry import grid_rows, occupancy, _native_occupancy
from pymupdf import _table_spans as spans
from . import header_material as material
from .header_provider import HeaderRoles
from pymupdf4llm._table_pipeline.r6_header_contract import (
    attach_pdf_features, chars_on_page, missing_body_cap, norm, prefix_depth,
    row_features, title_rebased_features,
)


def load_session(path):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])


@dataclass(frozen=True)
class ContextProof:
    root: object
    prefix: tuple
    depth: int
    offset: int
    columns: int


class R6HeaderRoles(HeaderRoles):
    """Use the LIVE post-OCR page supplying the final table placements.

    Supplies purpose-specific boundaries before row/span consumers, then final
    roles after reconstruction. Title and section processing follows model
    inference. Process-local decisions use the current runtime service.
    """
    def __init__(self, session, page_chars=None, *, enabled=True, leaf_completion=False, role_demotion=False,
                 year_rows=False):
        super().__init__()
        self.session = session
        self.service = None
        # Optional injected characters support fixtures/historical experiments.
        # The real runner never opens a separate source PDF for R6 input.
        self.page_chars = page_chars
        self.enabled = enabled
        # H2 candidate: opt-in colspan leaf completion after the model decision.
        self.leaf_completion = leaf_completion
        # H3 candidate: opt-in demotion of unit-note / single-section header rows.
        self.role_demotion = role_demotion
        # H2 extension candidate: opt-in year/date second header line.
        self.year_rows = year_rows

        # Retain grids so callers can distinguish final children from discarded
        # parent decisions without id reuse. Does not alter the RF contract.
        self._char_cache = None

    def _characters(self, page):
        if self.page_chars is not None:
            return self.page_chars[page.number]
        if self._char_cache is None:
            # Direct apply_roles calls have no stable finder lifetime.
            return chars_on_page(page)
        # The finder runs after OCR and does not edit page text. Keep changes
        # in extraction geometry/settings separate, including post-finder child
        # refinement. Cell/grid changes alone do not change page characters.
        key = (page, page.rotation, tuple(page.rect), tuple(page.cropbox),
               pymupdf.TEXTFLAGS_RAWDICT,
               bool(pymupdf.TOOLS.set_small_glyph_heights()),
               bool(pymupdf.TOOLS.unset_quad_corrections()))
        if key not in self._char_cache:
            self._char_cache[key] = chars_on_page(page)
        return self._char_cache[key]

    def _infer_roles(self,page,grid,region,*,title_alignment=None,purpose="final",prepared_query=None,result_query=None,table_bbox=None):
        from .header_role_inference import _infer_roles
        return _infer_roles(self,page,grid,region,title_alignment=title_alignment,purpose=purpose,prepared_query=prepared_query,result_query=result_query,table_bbox=table_bbox)

    result_status = 'onnx'
    def predict_labels(self,inputs,rows,grid,queries,event,table_bbox):
        key=hashlib.sha256(inputs.tobytes()).hexdigest()
        saved=queries.get(key)
        if saved is not None and np.array_equal(saved[0],inputs):
            if self.service is not None:self.service.counters['actual_query_reuses']+=1
            return list(saved[1]),True
        output=(self.service.run_model(self.session,['label'],{'features':inputs}) if self.service is not None else self.session.run(['label'],{'features':inputs}))
        labels=output[0].tolist();queries[key]=(inputs.copy(),tuple(labels))
        return labels,False

    provider_name = 'r6'
    @property
    def transport(self):return self

    def provider_stamp(self):
        return (id(self.session),self.enabled,self.leaf_completion,self.role_demotion,self.year_rows)

    @contextmanager
    def finder_scope(self):
        previous=self._char_cache;self._char_cache={}
        try:yield
        finally:self._char_cache=previous

    def confirmed(self,event):return event.get('status')=='onnx'

    def evaluate(self,page,grid,region,*,purpose,alignment=None,prepared=None,table_bbox=None):
        packet={}
        out=self._infer_roles(page,grid,region,title_alignment=alignment,purpose=purpose,prepared_query=prepared,result_query=packet,table_bbox=table_bbox)
        return out[0],out[1],packet

    def state(self,page):
        chars=self._char_cache;words=getattr(page,'_refine_words_cache',None);text_spans=getattr(page,'_span_text_spans_cache',None)
        if chars is None or words is None or text_spans is None:return None,None
        opts=(self.enabled,self.leaf_completion,self.role_demotion,self.year_rows)
        key=(page,page.number,page.rotation,tuple(page.rect),tuple(page.cropbox),id(chars),id(words),id(text_spans),id(self.session),opts,
            pymupdf.TEXTFLAGS_RAWDICT,bool(pymupdf.TOOLS.set_small_glyph_heights()),bool(pymupdf.TOOLS.unset_quad_corrections()))
        return key,(page,chars,words,text_spans,self.session)

    def correspondence_key(self,event):
        fields=('guard_changed','role_demoted','leaf_completed','year_rows','offset','compatibility_requery','compat_input_offset','compat_dependency_end')
        return tuple((k,event.get(k)) for k in fields)

    def decision_signature(self,event):return self.title_event_signature(event)

    def same_alignment(self,left,right):return left['offset']==right['offset']

    def preserve_event(self,region,mapped,root,reason,rows,purpose):
        return dict(status='preserved',result_purpose=purpose,before=region.top_header_rows,after=mapped.top_header_rows,rows=rows,section_rows=list(mapped.section_header_rows),input_source='verified_existing_source_roles',origin_status='onnx',origin_rows=len(root.data.rows),origin_depth=root.region.top_header_rows,mapping_reason=reason,onnx_executed=False,input_offset=root.event.get('input_offset',root.event.get('offset')),offset=root.event.get('offset'),semantic_order=root.event.get('semantic_order'),compatibility_requery=root.event.get('compatibility_requery',False),compat_input_offset=root.event.get('compat_input_offset'),compat_dependency_end=root.event.get('compat_dependency_end'))

    def retain_query(self,proof,packet,origin,actual):
        proof.query_data=packet;proof.query_origin=origin if not actual and origin is not None else proof

    def valid_transfer(self,proof):
        root=proof.root or proof;context=getattr(proof,'context_proof',None)
        return context is not None and context.root is root and context.depth==proof.region.top_header_rows and context.prefix==self.service.prepared.prefix(proof.data,context.depth,norm) and context.offset==(root.event.get('compat_input_offset') if root.event.get('compatibility_requery') else root.event.get('input_offset',root.event.get('offset')))
    def correspondence(self,old,new,region,grid):
        p=self.service.prepared;mapped,reason=p.correspondence(old,new,region,spans,_native_occupancy)
        if mapped is None:return None,reason,None
        root=old.root or old
        if any(k not in root.event or root.event[k] for k in ['guard_changed','role_demoted','leaf_completed','year_rows']):return None,'origin_postprocessing_changed_depth',None
        depth=root.region.top_header_rows
        if mapped.top_header_rows!=depth:return None,'effective_header_index_context_changed',None
        prefix=p.prefix(new,depth,norm)
        if p.prefix(root.data,depth,norm)!=prefix:return None,'header_or_boundary_dependency_changed',None
        old_columns=p.geometry(root.data,_native_occupancy);columns=p.geometry(new,_native_occupancy)
        if old_columns!=columns:return None,'postprocessing_column_extent_changed',None
        from .header_semantic_order import posterior_sections,posterior_title_offset
        if root.event.get('title_alignment_transport'):
            alignment,reason=self.title_correspondence(root,new,grid)
            if alignment is None:return None,reason,None
            offset=alignment['offset'];expected_offset=root.event['input_offset']
        elif root.event.get('compatibility_requery'):
            extent=root.event['compat_dependency_end']
            # Existing prefix proof must cover both model queries, including
            # their first non-header neighbor. Wider dependencies decline reuse.
            if extent>depth:return None,'compat_first_query_dependency_outside_proved_prefix',None
            bound=min(extent+1,len(grid));first=root.event['raw_labels']
            if len(first)<bound:return None,'compat_first_query_row_correspondence_unknown',None
            labels=list(first[:bound])+[0]*(len(grid)-bound)
            sections=posterior_sections(grid,prefix_depth(labels))
            offset=posterior_title_offset(grid,labels,sections)
            expected_offset=root.event['compat_input_offset']
        else:
            offset=0
            expected_offset=root.event.get('input_offset',root.event['offset'])
        if offset!=expected_offset:return None,'effective_model_query_context_changed',None
        return mapped,'verified_sources_geometry_and_R6_dependency_context',ContextProof(root,prefix,depth,offset,columns)

    @staticmethod
    def title_event_signature(event):
        return json.dumps({k:event.get(k) for k in ['features_sha256','raw_labels','post_title_offset','input_offset','title_dependencies','result_purpose','after','offset','guard_changed','role_demoted','leaf_completed','year_rows']},sort_keys=True)

    def title_correspondence(self,old,new,grid):
        # A separate consequence of the same existing ONNX proof. This does
        # not map the old header depth or the old body's th labels.
        p=self.service.prepared;root=old.root or old;event=root.event
        offset=event.get('post_title_offset',0);deps=event.get('title_dependencies')
        if event.get('status')!='onnx' or not offset or not deps:return None,'no_post_model_title_alignment'
        if getattr(root,'title_snapshot',None)!=self.title_event_signature(event):return None,'title_alignment_event_edited'
        if self.service.prepared.scope is None or id(root.data) not in self.service.prepared.scope['metadata']:return None,'title_from_different_finder'
        if material.fingerprint(root.grid)!=root.signature:return None,'title_origin_live_cells_or_tags_edited'
        if root.data.counts!=new.counts:return None,'title_material_ownership_changed'
        extent=deps['source_extent']
        if extent>len(new.rows) or offset>=len(new.rows):return None,'title_dependency_rows_missing'
        if not deps['columns_covered_by_context']:return None,'title_column_normalization_depends_on_body'
        if p.prefix(root.data,extent-2,norm)!=p.prefix(new,extent-2,norm):return None,'title_or_related_neighbor_cells_changed'
        columns=p.geometry(root.data,_native_occupancy)
        if columns!=p.geometry(new,_native_occupancy):return None,'title_column_occupancy_changed'
        if deps['normalized_columns']!=columns:return None,'title_empty_column_normalization_not_proved'
        bounds=lambda d:spans._span_clustered_boundaries([x for row in d.rows for c in row if c.bbox is not None for x in (c.bbox[0],c.bbox[2])])
        old_bounds,new_bounds=bounds(root.data),bounds(new)
        combined=spans._span_clustered_boundaries(old_bounds+new_bounds)
        if not len(old_bounds)==len(new_bounds)==len(combined):return None,'title_column_geometry_changed'
        if any(ri+c.rowspan>offset for ri,row in enumerate(root.data.rows[:offset]) for c in row):return None,'title_span_crosses_alignment_boundary'
        return dict(offset=offset,dependencies=deps,origin_features_sha256=event['features_sha256'],
            proof='same_native_title_neighbor_sources_geometry_columns_and_live_context'),None

    def prepared_query(self,old,new,grid):
        # This borrows actual input/output material, never the other purpose's
        # role result. Exact immutable cells plus the existing live context are
        # required; changed grids may borrow only a separately proved title.
        root=old.root or old
        origin=getattr(root,'query_origin',root)
        for proof in (root,origin):
            if proof.event.get('status')!='onnx':return None
            if self.service.prepared.scope is None or id(proof.data) not in self.service.prepared.scope['metadata']:return None
            if material.fingerprint(proof.grid)!=proof.signature:return None
            if getattr(proof,'title_snapshot',None)!=self.title_event_signature(proof.event):return None
        if root.data is not new:return None
        tags=tuple(tuple(c.tag for c in row) for row in grid)
        old_tags=tuple(tuple(c.tag for c in row) for row in root.grid)
        if tags!=old_tags and any(t!='td' for row in tags for t in row):return None
        packet=getattr(root,'query_data',None)
        if packet is None:return None
        return packet,origin

