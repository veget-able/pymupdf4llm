"""Directional placement split with mandatory immediate/final rollback."""
from collections import Counter
from dataclasses import dataclass
from types import MethodType
import pymupdf
from pymupdf import table
from pymupdf._table_headers import HeaderRegion
from pymupdf4llm.helpers.table_html.reconstruct import _table_grid_matrices, _placement_grid_matrices
from .placement_material import source_key, source_counts, placement_counts, grid_state, envelope, _cells_bbox
from .table_content_recovery import node_sources
from .material_region_split import partition_placements
from .material_split_rules import grid_hsplit_repeated, grid_vsplit_heteromorphic

def split_parts(cells, texts, material):
    """Existing grid proposals, admitted only across native-material cuts.

    No graph-band detector or header-only fallback. The existing C01 proposal
    already requires body content in every repeated panel. The shared material
    cut check additionally excludes continuous native words/rulings.
    """
    nr = len(texts)
    nc = max(map(len, texts), default=0)
    if not nr or not nc:
        return []
    cuts = grid_vsplit_heteromorphic(texts)
    bounds = [0, *cuts, nr]
    for cut in cuts:
        above, below = _cells_bbox(cells[:cut]), _cells_bbox(cells[cut:])
        whole = _cells_bbox(cells)
        if (not above or not below or above[3] > below[1]
                or not material.cut_is_clear('y', above[3], below[1], whole)):
            return []
    parts = []
    for r0, r1 in zip(bounds, bounds[1:]):
        repeat = grid_hsplit_repeated(texts[r0:r1])
        columns = [(0, nc)] if repeat is None else [
            (i * repeat[0], (i + 1) * repeat[0]) for i in range(repeat[1])]
        blocks = [_cells_bbox([row[c0:c1] for row in cells[r0:r1]]) for c0, c1 in columns]
        whole = _cells_bbox(cells[r0:r1])
        if any(box is None for box in blocks):
            return []
        for left, right in zip(blocks, blocks[1:]):
            if (left[2] > right[0]
                    or not material.cut_is_clear('x', left[2], right[0], whole)):
                return []
        parts.extend(dict(rows=(r0, r1), cols=cols, bbox=box)
                     for cols, box in zip(columns, blocks))
    return parts if len(parts) > 1 else []


@dataclass
class SplitTrial:
    before: object
    placements: Counter
    sources: Counter
    child_ids: tuple
    child_states: tuple

    def conserved(self, children):
        return (placement_counts(children) == self.placements
                and source_counts(children) == self.sources
                and {id(c): grid_state(c.placements) for c in children} == dict(self.child_states))


def split_table(self, page, tab):
    pending = self._pending_parent_roles
    region = None
    if pending is not None:
        grid, region = pending.pop(id(tab.placements))
        if grid is not tab.placements:
            raise RuntimeError('Deferred R6 grid identity changed')
    nr, nc, cells, texts = _table_grid_matrices(tab, retain=True)
    material = self.runtime.page_material(page)
    self._begin_page(material)
    parts = split_parts(cells, texts, material)
    if not parts:
        return [self._roles(page, tab, region)] if region is not None else [tab]
    grids, rejected = partition_placements(tab.placements, parts, shape=(nr, nc))
    if rejected:
        self.events.append(dict(stage='independent_split', status='preserved', **rejected))
        return [self._roles(page, tab, region)] if region is not None else [tab]
    before = self._make_table(page, [[c.clone() for c in row] for row in tab.placements],
                              tab, 'current_grid_snapshot')
    before.header_rows, before.section_rows = tab.header_rows, tab.section_rows
    expected = [grid_state(grid) for grid in grids]
    children = [self._roles(page, self._make_table(page, grid, tab, 'placement_split'),
                            HeaderRegion(top_header_rows=0, section_header_rows=())) for grid in grids]
    trial = SplitTrial(before, placement_counts([before]), source_counts([before]),
                       tuple(map(id, children)),
                       tuple((id(child), state) for child, state in zip(children, expected)))
    if not trial.conserved(children):
        self.events.append(dict(stage='independent_split', status='rollback',
                                reason='placement_or_source_conservation'))
        return [self._roles(page, before, region or HeaderRegion(
            top_header_rows=0, section_header_rows=()))]
    self._trials.append(trial)
    self.events.append(dict(stage='independent_split', status='split',
                            parent_shape=[nr, nc], proposals=parts,
                            children=[list(envelope(c)) for c in children], extra_grid_calls=0))
    return children


def finish_split_trials(self, page, tables, material):
    # Validate actual split output before structural alternatives or ruled recovery.
    for trial in self._trials:
        members = [t for t in tables if id(t) in trial.child_ids]
        if not trial.conserved(members):
            tables = [t for t in tables if id(t) not in trial.child_ids]
            tables.append(self._roles(page, trial.before, HeaderRegion(
                top_header_rows=trial.before.header_rows, section_header_rows=trial.before.section_rows)))
            self.events.append(dict(stage='independent_split', status='rollback',
                                    reason='final_placement_or_source_conservation'))
    self._trials.clear()
    return tables

def install(runtime):
    pipeline = runtime.pipeline
    pipeline.split_table = MethodType(split_table, pipeline)
    pipeline.finalizers.append(MethodType(finish_split_trials, pipeline))
