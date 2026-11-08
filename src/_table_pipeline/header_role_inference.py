"""Existing live row preparation, title order and role postrules, shared once.

Moved from frozen R6 _infer_roles. Provider-specific inputs/prediction and
transport remain outside this module. No independent header depth estimator.
"""
from dataclasses import replace
import hashlib
import numpy as np
from pymupdf import table
from .header_semantic_order import posterior_title_offset,posterior_sections
from .placement_geometry import grid_rows,occupancy
from .r6_header_contract import attach_pdf_features,norm,row_features,title_rebased_features,prefix_depth,missing_body_cap

def _infer_roles(self, page, grid, region, *, title_alignment=None, purpose="final", prepared_query=None, result_query=None, table_bbox=None):
    if purpose not in ("structure","final"):raise ValueError("Unknown header result purpose")
    if purpose=="structure":title_alignment=None
    if not self.enabled:
        return grid, region
    event = {"result_purpose":purpose,"before": region.top_header_rows, "after": region.top_header_rows,
             "rows": len(grid), "section_rows": list(region.section_header_rows),
             "input_source": "live_post_ocr" if self.page_chars is None else "injected"}
    self.decisions[id(grid)] = (grid, event)
    try:
        if not grid:
            raise ValueError("empty_grid")
        if prepared_query is not None:
            rows=prepared_query['rows']
        else:
            current_chars = self._characters(page)
            rows = [[attach_pdf_features({"text": norm(c.text), "bbox": c.bbox},
                                         current_chars)
                     for c in row if norm(c.text)] for row in grid]
    except ValueError as error:
        event.update(status="fallback", reason=str(error))
        self.events.append(event)
        return grid, region
    except Exception as error:
        self.errors.append(repr(error))
        raise
    try:
        features = prepared_query['features'] if prepared_query is not None else row_features(rows)
        queries=dict(prepared_query['queries']) if prepared_query is not None else {}
        query_reuses=0
        def predict(inputs):
            nonlocal query_reuses
            labels,reused=self.predict_labels(inputs,rows,grid,queries,event,table_bbox)
            query_reuses+=int(reused)
            return labels
        input_region=(region.top_header_rows,tuple(region.section_header_rows))
        input_tags=[[c.tag for c in row] for row in grid]
        title_dependencies=dict(title_alignment['dependencies']) if title_alignment is not None else {}
        offset = 0 if purpose=='structure' or title_alignment is None else title_alignment['offset']
        inputs = np.asarray(title_rebased_features(features, offset), dtype=np.float64)
        labels = predict(inputs)
        actual_input_offset=offset
        raw_prefix=offset+prefix_depth(labels)
        if title_alignment is None:
            # Full input rows correspond one-to-one to these placements.
            # No re-extraction or ONNX call for the title-view index shift.
            sections=posterior_sections(grid,prefix_depth(labels))
            offset=posterior_title_offset(grid,labels,sections,dependencies=title_dependencies)
            raw_depth=offset+prefix_depth(labels[offset:])
            title_offset=offset
            if purpose=="structure":offset=0;raw_depth=raw_prefix
        else:
            raw_depth=offset+prefix_depth(labels)
            title_offset=offset
        event.update(semantic_order='post_model_title_section',input_offset=actual_input_offset,
            input_region=list(input_region),input_tags=input_tags,
            features_sha256=hashlib.sha256(inputs.tobytes()).hexdigest(),
            features_shape=list(inputs.shape),raw_labels=labels,raw_prefix=raw_prefix,
            post_title_offset=title_offset,
            row_correspondence=list(range(actual_input_offset,len(grid))),
            input_row_text=[[c['text'] for c in row] for row in rows])
        # Title alignment compatibility: the first inference still reads
        # every live row without title/section semantic bootstrap. Reuse the
        # already prepared 19 features; no PDF/character/feature extraction.
        event.update(title_alignment_transport=title_alignment is not None,title_dependencies=title_dependencies,
            title_transport_proof=title_alignment['proof'] if title_alignment else None,
            title_origin_features_sha256=title_alignment['origin_features_sha256'] if title_alignment else None)
        event['compatibility_requery']=False
        event['prepared_features_reused']=prepared_query is not None
        if purpose=="final" and offset>0 and title_alignment is None:
            compat_inputs=np.asarray(title_rebased_features(features,offset),dtype=np.float64)
            if not np.array_equal(compat_inputs,inputs):
                first_aligned_depth=raw_depth
                compat_labels=predict(compat_inputs)
                raw_depth=offset+prefix_depth(compat_labels)
                event.update(compatibility_requery=True,compat_input_offset=offset,
                    compat_dependency_end=max(raw_prefix,first_aligned_depth),
                    compat_features_sha256=hashlib.sha256(compat_inputs.tobytes()).hexdigest(),
                    compat_features_shape=list(compat_inputs.shape),compat_labels=compat_labels,
                    compat_row_correspondence=list(range(offset,len(grid))),
                    compat_prefix_before=first_aligned_depth,compat_prefix_after=raw_depth,
                    compat_labels_changed=compat_labels!=labels[offset:],
                    compat_prefix_changed=raw_depth!=first_aligned_depth,
                    prepared_19_features_reused=True,compat_extra_onnx_calls=1)
        capped = missing_body_cap(rows, raw_depth, offset)
        depth = demoted = capped
        span_rows = grid_rows(grid)
        # One occupancy resolution of the grid shared by H3 and H2.
        cells = occupancy(span_rows) if (self.role_demotion or self.leaf_completion or self.year_rows) else None
        if self.role_demotion:
            from .header_role_demotion import demotion_depth
            # Over-tag demotion first: drop trailing common-note and
            # section rows the model tagged as header.
            depth = demoted = demotion_depth(span_rows, capped, cells)
        if self.leaf_completion:
            from .header_leaf_completion import leaf_completion_depth
            # Merged-header leaf-label completion: extend over the row
            # that supplies single-column labels under unresolved
            # colspan parents, using the grid's own spans. The existing
            # None/N/A body cap is the final word: a completed row of
            # missing-value tokens is capped again, never re-promoted.
            depth = missing_body_cap(rows, leaf_completion_depth(span_rows, demoted, cells), offset)
        completed = depth
        if self.year_rows:
            from .header_leaf_completion import year_row_depth
            # Year/date second header line under labeled columns; the
            # None/N/A cap stays final here as well.
            depth = missing_body_cap(rows, year_row_depth(span_rows, completed, cells), offset)
        if result_query is not None:result_query.update(rows=rows,features=features,queries=queries)
        event['actual_query_reuses']=query_reuses
        event.update(status=self.result_status, after=depth, offset=offset,
                     guard_changed=capped != raw_depth,
                     role_demoted=demoted != capped,
                     leaf_completed=completed != demoted,
                     year_rows=depth != completed)
        self.events.append(event)
        sections=posterior_sections(grid,depth)
        event['post_section_rows']=list(sections)
        region = replace(region, top_header_rows=depth,section_header_rows=sections)
        return table._refine_tag_grid(grid, depth), region
    except Exception as error:
        # Finder catches exceptions internally: explicitly fail the run
        # after inference rather than silently publishing partial output.
        self.errors.append(repr(error))
        raise
