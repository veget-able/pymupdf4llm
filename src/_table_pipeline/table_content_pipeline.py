"""Opt-in content ownership completion on the existing V9/V10 execution path."""

from pymupdf._table_headers import HeaderRegion

from pymupdf4llm._table_pipeline.fragment_consolidation import FragmentConsolidationPipeline
from pymupdf4llm._table_pipeline.table_content_recovery import retain_unassigned, cell_ownership, readable_nodes, restore_tables


class ContentRestorationPipeline(FragmentConsolidationPipeline):
    def reject_incomplete_split(self, page, context, children, obstacles):
        """Adopt the retained parent only when it repairs failed child delivery.

        Runs after restoration/R6: before then, unresolved nodes are merely
        pending work. Parent prediction reuses the existing DeferredRows cache.
        """
        from pymupdf4llm._table_pipeline.cell_output_boundary import external_content
        from pymupdf4llm._table_pipeline.table_content_recovery import SourceNode
        from pymupdf4llm._table_pipeline.grid_reconstruct_split import refine_child, refinement_geometry
        from pymupdf._table_word_geometry import page_word_geometry
        words = page._refine_words_cache
        geometry = page_word_geometry(page, words)
        chars = children[0]._chars if children else ()
        key = context.parent_key
        outside = external_content(children + obstacles, context.source_nodes, words, key, characters=chars, word_geometry=geometry)
        if not outside or len(children) < 2:
            return None
        parent = context.parent_entry
        # The prior parent must remain available; no sibling bbox union or new
        # grid generator is a substitute for the actual pre-split alternative.
        with refinement_geometry(page) as current:
            cells = parent[1].resolve()
            meta = dict(parent.bbox_provenance, bbox_source='gnn', grid_source='tgif',
                        bbox_operation='split_recovery_rollback')
            rebuilt = refine_child(current, cells, list(parent[0]), meta, children[0])
        if len(rebuilt) != 1:
            self.events.append(dict(stage='split_recovery_admission',source_gnn_indices=list(key),
                                    status='parent-rejected',reason='parent-still-split'))
            return None
        from pymupdf4llm._table_pipeline.grid_ownership import _intersects
        if any(_intersects(c.bbox,other.bbox) for row in rebuilt[0].placements
               for c in row if c.bbox is not None for other in obstacles):
            self.events.append(dict(stage='split_recovery_admission',source_gnn_indices=list(key),
                                    status='parent-rejected',reason='other-table-collision'))
            return None
        # Validate actual produced sources, including all existing child
        # content (even source units outside the retained GNN node list).
        refs = [ref for t in children for row in t.placements for c in row
                if c.source_content is not None for ref in c.source_content.sources]
        required = [SourceNode(i,tuple(ref.bbox),ref.text) for i,ref in enumerate(refs)]
        try:
            missed = external_content(rebuilt,context.source_nodes,words,key,characters=chars, word_geometry=geometry)
            lost = external_content(rebuilt,required,words,key,characters=chars, word_geometry=geometry)
        except ValueError as exc:
            self.events.append(dict(stage='split_recovery_admission',source_gnn_indices=list(key),
                                    status='parent-rejected',reason=str(exc)))
            return None
        if missed or lost:
            self.events.append(dict(stage='split_recovery_admission',source_gnn_indices=list(key),
                                    status='parent-rejected',reason='unrecovered-source',
                                    missing=len(missed),lost=len(lost)))
            return None
        self.events.append(dict(stage='split_recovery_admission',source_gnn_indices=list(key),
                                status='rollback',children=len(children),recovered=len(outside)))
        return rebuilt

    def finalize_tables(self, page, tables):
        edges = next((t._ruling_edges for t in tables if hasattr(t, "_ruling_edges")), ())
        tables = super().finalize_tables(page, tables)
        for (pn, key), context in self.restoration_contexts.items():
            if pn != page.number or not context.source_nodes:
                continue
            before = [t for t in tables if tuple(t.bbox_provenance.get("source_gnn_indices", ())) == key]
            nodes = readable_nodes(before, context.source_nodes)
            baseline_accepted = cell_ownership(before, nodes)
            obstacles = [t for t in tables if all(t is not old for old in before)]
            failures = []
            restored, planned_accepted, decisions = restore_tables(before, nodes, obstacles=obstacles,
                words=getattr(page,"_refine_words_cache",None), edges=edges, failures=failures)
            if not set(baseline_accepted) <= set(planned_accepted):
                restored, planned_accepted, decisions = before, baseline_accepted, []
            for tab in restored:
                if all(tab is not old for old in before):
                    # Placements changed: reuse live character cache, but rerun
                    # final roles once. Previous R6 decisions belong to old cells.
                    region = HeaderRegion(top_header_rows=tab.header_rows, section_header_rows=tab.section_rows)
                    tab.placements, region = self.header.apply_roles(page, tab.placements, region)
                    tab.header_rows, tab.section_rows = region.top_header_rows, region.section_header_rows
            changed = any(all(tab is not old for old in before) for tab in restored)
            accepted = cell_ownership(restored, nodes) if changed else planned_accepted
            # Role/leaf completion can alter placements too. Admission must hold
            # for the actual post-R6 cells, not just the pre-role proposal.
            if not set(planned_accepted) <= set(accepted):
                restored, accepted, decisions = before, baseline_accepted, []
            if context.split_selected and failures:
                replacement = self.reject_incomplete_split(page, context, restored, obstacles)
                if replacement is not None:
                    restored = replacement
                    nodes = readable_nodes(restored, context.source_nodes)
                    accepted = cell_ownership(restored, nodes)
                    decisions.append(dict(operation="split_recovery_rollback", failures=failures))
            restored, residuals = retain_unassigned(
                restored, nodes, accepted, source_gnn_indices=key,
                original_nodes=context.source_nodes)
            expected = {n.index for n in context.source_nodes if n.text.strip()}
            pending = {record["node_index"] for record in residuals}
            if set(accepted) & pending or set(accepted) | pending != expected:
                raise ValueError("Incomplete final GNN content partition")
            old_ids = {id(t) for t in before}
            tables = [t for t in tables if id(t) not in old_ids] + restored
            self.events.append(
                dict(
                    stage="content_ownership",
                    source_gnn_indices=list(key),
                    nodes=len(expected),
                    cell_text=len(accepted),
                    unresolved_count=len(residuals),
                    unresolved_content=list(residuals),
                    decisions=decisions,
                    ownership=[
                        dict(node=i, table_bbox=list(restored[owner["table"]].bbox), **owner)
                        for i, owner in sorted(accepted.items())
                    ],
                    source_nodes=[
                        dict(index=n.index, bbox=list(n.bbox), text=n.text, original_text=original.text)
                        for n, original in zip(nodes, context.source_nodes)
                    ],
                )
            )
        # All parent restoration/role decisions are final before output routing.
        from pymupdf4llm._table_pipeline.cell_output_boundary import external_content
        words = getattr(page, "_refine_words_cache", None)
        characters = next((t._chars for t in tables if getattr(t, "_chars", None) is not None), ())
        for (pn, key), context in self.restoration_contexts.items():
            if pn != page.number or not context.source_nodes:
                continue
            if words is None:
                raise ValueError("Missing existing producer word cache for content delivery")
            members = [t for t in tables if tuple(t.bbox_provenance.get("source_gnn_indices", ())) == key]
            from pymupdf._table_word_geometry import page_word_geometry
            outside = external_content(tables, context.source_nodes, words, key, characters=characters,
                                       word_geometry=page_word_geometry(page, words))
            if outside and not members:
                raise ValueError("External table material has no surviving transport owner")
            if members:
                members[0].external_content = tuple(outside)
        return tables
