"""Cell-preserving fragment join, then conservative whole-parent reconstruction.

Decisions use original post-R6 fragments, never GT, filenames, or joined roles.
The caller activates this after V9 recovery. No intermediate text is absorbed
by joins. Existing placements are copied, including their geometric spans.
"""
from collections import defaultdict
from itertools import combinations
from types import SimpleNamespace
import re

import pymupdf
from pymupdf import table
from pymupdf._table_spans import SpanCell
from pymupdf4llm.helpers.table_html.reconstruct import _placement_grid_matrices, _table_grid_matrices

from pymupdf4llm._table_pipeline.direction_reconstruct_split import DirectionReconstructSplitPipeline
from pymupdf4llm._table_pipeline.deferred_tgif import DeferredRows
from pymupdf4llm._table_pipeline.grid_reconstruct_split import refine_child, refinement_geometry
from pymupdf4llm._table_pipeline.vg_rule_primitives import _tokens, _jaccard


def x_iou(a, b):
    width = max(a[2], b[2]) - min(a[0], b[0])
    return max(0., min(a[2], b[2]) - max(a[0], b[0])) / width if width > 0 else 0.


def column_intervals(cells):
    """Tightest cell bounds per slot; preserve empty columns as None."""
    nc = max(map(len, cells), default=0)
    # Tightest cell per slot avoids treating a spanning heading as a column.
    columns = []
    for j in range(nc):
        choices = [row[j] for row in cells if row[j] is not None]
        if not choices:
            columns.append(None)
        else:
            c = min(choices, key=lambda c: c[2]-c[0])
            columns.append((c[0], c[2]))
    return columns


def snapshot(tab):
    nr, nc, cells, texts = _table_grid_matrices(tab, retain=True)
    return dict(tab=tab, rows=nr, cols=nc, texts=texts, columns=column_intervals(cells),
                first=_tokens([str(t or '') for t in texts[0]]),
                depth=tab.header_rows, bbox=list(tab.bbox))


def join_evidence(a, b):
    if (a['cols'] != b['cols'] or b['depth'] != 0
            or a['bbox'][3] > b['bbox'][1] + 1e-4
            or x_iou(a['bbox'], b['bbox']) < .7
            or _jaccard(a['first'], b['first']) >= .5):
        return None
    if any(x is None or y is None or max(abs(x[i]-y[i]) for i in (0, 1)) > 2.
           for x, y in zip(a['columns'], b['columns'])):
        return None
    # A positive record-ownership signal, not merely absence of a new header.
    end = re.fullmatch(r'\s*\((\d+)\)\s*', str(a['texts'][-1][0] or ''))
    start = re.fullmatch(r'\s*\((\d+)\)\s*', str(b['texts'][0][0] or ''))
    return 'row-continuity' if end and start and int(start[1]) == int(end[1]) + 1 else None


def revert_eligible(parts):
    return (len(parts) >= 3 and len({p['cols'] for p in parts}) == 1
            and all(x_iou(a['bbox'], b['bbox']) >= .7 for a, b in combinations(parts, 2))
            and all(a['bbox'][3] <= b['bbox'][1] + 1e-4 for a, b in zip(parts, parts[1:]))
            and all(_jaccard(parts[0]['first'], p['first']) < .5 for p in parts[1:]))


def split_integrity_eligible(parts):
    """H5 candidate: region-split children that cannot stand as tables.

    ``parts`` are snapshots of one parent's children, sorted top-to-bottom
    then left-to-right. Returns the reason to revert to the whole parent, or
    None:

    - stacked children (pairwise x-IoU >= .7, vertically ordered) where a
      child below the first has no header row: the split cut a header block
      from its body;
    - side-by-side children (x-disjoint, pairwise y-IoU >= .7) where a child has one column: the
      split cut a label column from its values.
    """
    if len(parts) < 2:
        return None
    stacked = (all(x_iou(a['bbox'], b['bbox']) >= .7 for a, b in combinations(parts, 2))
               and all(a['bbox'][3] <= b['bbox'][1] + 1e-4 for a, b in zip(parts, parts[1:])))
    if stacked:
        return 'headerless_child' if any(p['depth'] == 0 for p in parts[1:]) else None
    by_x = sorted(parts, key=lambda p: p['bbox'][0])
    side = all(a['bbox'][2] <= b['bbox'][0] + 1e-4 for a, b in zip(by_x, by_x[1:]))
    # Reuse the same interval overlap contract as the vertical-stack check,
    # transposing axes. X separation alone also admits diagonal/unrelated tables.
    side = side and all(x_iou([a['bbox'][1], 0, a['bbox'][3], 0],
                              [b['bbox'][1], 0, b['bbox'][3], 0]) >= .7
                        for a, b in combinations(parts, 2))
    if side:
        return 'single_column_child' if any(p['cols'] == 1 for p in parts) else None
    return None


def concat_placements(tables):
    """Copy original rows/cells without flattening or re-resolving spans."""
    return [[c.clone() for c in row]
            for tab in tables for row in tab.placements]


class FragmentConsolidationPipeline(DirectionReconstructSplitPipeline):
    # H5 candidate flag: revert region splits whose children cannot stand as
    # tables (headerless lower child, single-column side child). Opt-in.
    split_integrity = False

    def __init__(self, model):
        super().__init__(model)
        self.restoration_contexts = {}

    def join(self, page, parts):
        tabs = [p['tab'] for p in parts]
        grid = concat_placements(tabs)
        bbox = [min(t.bbox[0] for t in tabs), min(t.bbox[1] for t in tabs),
                max(t.bbox[2] for t in tabs), max(t.bbox[3] for t in tabs)]
        with refinement_geometry(page) as current:
            child = table.Table(current, [tuple(c.bbox) for r in grid for c in r if c.bbox],
                                bbox=pymupdf.Rect(bbox))
            # Existing R6 context only; do not introduce a new heuristic decision.
            from pymupdf._table_headers import HeaderRegion
            offset, sections = 0, []
            for tab in tabs:
                sections.extend(offset + r for r in tab.section_rows)
                offset += len(tab.placements)
            region = HeaderRegion(top_header_rows=tabs[0].header_rows,
                                  section_header_rows=tuple(sections))
            child.placements, region = self.header.apply_roles(current, grid, region)
            child.header_rows, child.section_rows = region.top_header_rows, region.section_header_rows
            child.textpage, child._chars = tabs[0].textpage, tabs[0]._chars
            child.bbox_provenance = dict(tabs[0].bbox_provenance,
                bbox_source='union_recovery', bbox_operation='fragment_join',
                recovery_revision='fragment-consolidation/r8', recovery_steps=['row-continuity-join'],
                recovery_base_bbox=list(tabs[0].bbox),
                recovery_source_bboxes=[list(t.bbox) for t in tabs])
        return child

    def finalize_tables(self, page, tables):
        # R(union recovery)이 publish한 잔여 전달 데이터를 기록(관찰). 판정 미사용.
        for (_pn, _key), _ctx in sorted(self.restoration_contexts.items()):
            if _pn != page.number:
                continue
            self.events.append(dict(
                stage='restoration_handoff', source_gnn_indices=list(_key),
                report=_ctx.residual_report.summary(),
                handoff=[{"node": i, "disposition": t, "bbox": _ctx.node_bboxes.get(i)}
                         for i, t in _ctx.residual_report.handoff()]))
        if self.split_integrity:
            tables = self.revert_broken_splits(page, tables)
        groups = defaultdict(list)
        for tab in tables:
            meta = tab.bbox_provenance
            if meta.get('bbox_operation') == 'union_split' and meta.get('source_gnn_indices'):
                groups[tuple(meta['source_gnn_indices'])].append(snapshot(tab))
        replacements, removed = {}, set()
        for key, parts in groups.items():
            parts.sort(key=lambda p: (p['bbox'][1], p['bbox'][0]))
            links = [join_evidence(a, b) for a, b in zip(parts, parts[1:])]
            joined = False
            i = 0
            while i < len(parts):
                j = i
                while j < len(links) and links[j]:
                    j += 1
                if j > i:
                    chain = parts[i:j+1]
                    child = self.join(page, chain)
                    replacements[id(chain[0]['tab'])] = child
                    removed.update(id(p['tab']) for p in chain[1:])
                    joined = True
                    self.events.append(dict(stage='fragment_consolidation', status='join',
                        source_gnn_indices=list(key), children=[p['bbox'] for p in chain],
                        bbox=list(child.bbox), evidence=links[i:j], extra_tgif_calls=0))
                i = j + 1
            # Whole-parent reconstruction would overwrite a successfully joined group.
            if joined or not revert_eligible(parts):
                continue
            ctx = self.restoration_contexts.get((page.number, key))
            parent = ctx.parent_entry if ctx is not None else None
            if parent is None:
                raise RuntimeError('Missing retained union parent for consolidation')
            with refinement_geometry(page) as current:
                cells = parent[1].resolve()
                meta = dict(parent.bbox_provenance, bbox_source='gnn', grid_source='tgif',
                    bbox_operation='uniform_stack_reconstruct', recovery_revision='fragment-consolidation/r8',
                    recovery_steps=['whole-parent-tgif'], recovery_base_bbox=list(parent[0]),
                    recovery_source_bboxes=[p['bbox'] for p in parts])
                rebuilt = refine_child(current, cells, list(parent[0]), meta, parts[0]['tab'])
            shapes = [list(_table_grid_matrices(t, retain=True)[:2]) for t in rebuilt]
            adopted = len(rebuilt) == 1 and shapes[0][1] == parts[0]['cols']
            self.events.append(dict(stage='fragment_consolidation', status='revert' if adopted else 'revert-rejected',
                source_gnn_indices=list(key), children=[p['bbox'] for p in parts],
                shapes=shapes, extra_tgif_calls=1))
            if adopted:
                replacements[id(parts[0]['tab'])] = rebuilt[0]
                removed.update(id(p['tab']) for p in parts[1:])
        return [replacements.get(id(t), t) for t in tables if id(t) not in removed]

    def revert_broken_splits(self, page, tables):
        """Whole-parent TGIF for region-split groups that fail split integrity.
        Uses the retained parent GNN group; the parent grid is resolved from
        its deferred prediction (cached if already computed)."""
        groups = defaultdict(list)
        for tab in tables:
            meta = tab.bbox_provenance
            if (meta.get('bbox_source') == 'region_split' and meta.get('source_gnn_indices')
                    and meta.get('parent_bbox')):
                key = (tuple(meta['source_gnn_indices']), tuple(round(v, 3) for v in meta['parent_bbox']))
                groups[key].append(snapshot(tab))
        replacements, removed = {}, set()
        for (key, parent_bbox), parts in groups.items():
            parts.sort(key=lambda p: (p['bbox'][1], p['bbox'][0]))
            reason = split_integrity_eligible(parts)
            if reason is None:
                continue
            material = self.materials.get((page.number, key))
            if material is None:
                self.events.append(dict(stage='split_integrity', status='no_material', reason=reason,
                                        source_gnn_indices=list(key), children=[p['bbox'] for p in parts]))
                continue
            group, _retained, reader = material
            # materials belongs to the ORIGINAL GNN group. A later split may
            # name only a subregion; never label the whole grid with that bbox.
            # Match at the existing parent grouping precision, before TGIF.
            scope = tuple(round(float(v), 3) for v in group.get('group_bbox', ())[:4])
            if scope != parent_bbox:
                self.events.append(dict(stage='split_integrity', status='scope_mismatch', reason=reason,
                    source_gnn_indices=list(key), parent_bbox=list(parent_bbox),
                    material_bbox=list(scope), children=[p['bbox'] for p in parts], extra_tgif_calls=0))
                continue
            before_tgif = self.adapter.stats.tgif_executed
            with refinement_geometry(page) as current:
                cells = DeferredRows(group, reader).resolve()
                meta = dict(parts[0]['tab'].bbox_provenance, bbox_source='gnn', grid_source='tgif',
                    bbox_operation='split_integrity_reconstruct', recovery_revision='split-integrity/h5',
                    recovery_steps=['whole-parent-tgif'], recovery_base_bbox=list(parent_bbox),
                    recovery_source_bboxes=[p['bbox'] for p in parts])
                meta.pop('parent_bbox', None)
                meta.pop('parent_bbox_source', None)
                rebuilt = refine_child(current, cells, list(parent_bbox), meta, parts[0]['tab'])
            adopted = len(rebuilt) == 1 and rebuilt[0].header_rows >= 1
            self.events.append(dict(stage='split_integrity', status='revert' if adopted else 'revert-rejected',
                reason=reason, source_gnn_indices=list(key), children=[p['bbox'] for p in parts],
                shapes=[list(_placement_grid_matrices(t.placements)[:2]) for t in rebuilt],
                extra_tgif_calls=self.adapter.stats.tgif_executed - before_tgif))
            if adopted:
                replacements[id(parts[0]['tab'])] = rebuilt[0]
                removed.update(id(p['tab']) for p in parts[1:])
        return [replacements.get(id(t), t) for t in tables if id(t) not in removed]
