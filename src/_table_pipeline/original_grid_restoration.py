"""Adopt a verified actual original-grid alternative, independently of T19."""
from dataclasses import dataclass
from types import MethodType
import pymupdf
from pymupdf import table
from pymupdf._table_headers import HeaderRegion
from pymupdf4llm.helpers.table_html.reconstruct import _table_grid_matrices, _placement_grid_matrices
from .placement_material import source_key, source_counts, placement_counts, grid_state, envelope, _cells_bbox
from .table_content_recovery import node_sources
from pymupdf import _table_union as U
from .fragment_consolidation import snapshot, revert_eligible, split_integrity_eligible
from .grid_reconstruct_split import refine_child, refinement_geometry

@dataclass(frozen=True)
class StructuralProposalTrial:
    """Actual pre-selection structure and its selected concrete alternatives.

    The runtime owns the current-page lifetime. The zero-argument callback
    refines this retained grid with the existing page material; it must not
    resolve a detector parent or execute another grid model.
    """
    original_box: tuple
    original_grid: tuple
    selected_boxes: tuple
    split_kind: str
    native_sources: tuple
    reconstruct_original: object
    selected_grids: tuple

    def __post_init__(self):
        def freeze(grid):
            if not isinstance(grid, (list, tuple)):
                raise TypeError('Structural trial requires resolved concrete cells')
            return tuple(tuple(None if cell is None else tuple(cell) for cell in row) for row in grid)
        object.__setattr__(self, 'original_box', tuple(self.original_box))
        object.__setattr__(self, 'original_grid', freeze(self.original_grid))
        object.__setattr__(self, 'selected_boxes', tuple(tuple(box) for box in self.selected_boxes))
        object.__setattr__(self, 'selected_grids', tuple(freeze(grid) for grid in self.selected_grids))
        object.__setattr__(self, 'native_sources', tuple(self.native_sources))
        if (self.split_kind not in ('union', 'physical', 'directional')
                or len(self.selected_boxes) < 2
                or len(self.selected_boxes) != len(self.selected_grids)
                or not callable(self.reconstruct_original)):
            raise ValueError('Incomplete structural proposal trial')


def _proposal_family(self, trial, tables, material):
    """Match uniquely by actual producer references and selected geometry."""
    authoritative = {source_key(r)[:3] for r in node_sources(material.sources)}
    refs = node_sources(trial.native_sources)
    units = {source_key(r)[:3] for r in refs}
    if not units or not units <= authoritative:
        return None
    box = _cells_bbox(trial.original_grid)
    if box is None or tuple(box) != trial.original_box:
        return None
    scopes = []
    for selected_box, grid in zip(trial.selected_boxes, trial.selected_grids):
        cells = [cell for row in grid for cell in row if cell is not None]
        if not cells or tuple(_cells_bbox(grid)) != selected_box:
            return None
        selected = set()
        for occurrence in trial.native_sources:
            x, y = (occurrence.bbox[0] + occurrence.bbox[2]) / 2, (occurrence.bbox[1] + occurrence.bbox[3]) / 2
            if any(c[0] <= x < c[2] and c[1] <= y < c[3] for c in cells):
                selected.update(source_key(r)[:3] for r in occurrence.sources)
        scopes.append(selected)
    family, owners = [], set()
    for tab in tables:
        current = set()
        for row in tab.placements:
            for cell in row:
                cell.validate_source_content()
                if cell.source_content is not None:
                    current.update(source_key(r)[:3] for r in node_sources((cell.source_content,)))
        if not current or not current & units:
            continue
        # A current table crossing trial scope is not a child to replace.
        if not current <= units:
            return None
        matches = [i for i, scope in enumerate(scopes) if current <= scope]
        b = envelope(tab)
        if not matches or len(matches) != 1 or b is None:
            return None
        if any(min(b[2], trial.selected_boxes[i][2]) <= max(b[0], trial.selected_boxes[i][0])
               or min(b[3], trial.selected_boxes[i][3]) <= max(b[1], trial.selected_boxes[i][1]) for i in matches):
            return None
        family.append(tab);owners.update(matches)
    if len(family) < 2 or len(owners) != len(scopes):
        return None
    return family


def _adopt_structural_trials(self, page, tables, material, kinds):
    trials = [t for t in getattr(self.runtime, 'structural_trials', ()) if t.split_kind in kinds]
    matches = [(trial, self._proposal_family(trial, tables, material)) for trial in trials]
    matches = [(trial, family) for trial, family in matches if family is not None]
    # Ambiguous/nested alternatives never acquire a priority by quality or
    # provenance. Leave them for an explicit, unique structural relation.
    ambiguous = {id(t) for i, (_, family) in enumerate(matches) for t in family
                 if any(any(t is other for other in second)
                        for j, (_, second) in enumerate(matches) if i != j)}
    for trial, family in matches:
        if any(id(t) in ambiguous for t in family):
            self.events.append(dict(stage='structural_alternative', status='preserved', reason='ambiguous_family'))
            continue
        parts = []
        for tab in family:
            part = snapshot(tab);part['bbox'] = list(envelope(tab));parts.append(part)
        parts.sort(key=lambda p: (p['bbox'][1], p['bbox'][0]))
        if trial.split_kind == 'union':
            reason = 'uniform_stack' if revert_eligible(parts) else None
        else:
            reason = split_integrity_eligible(parts)
        if reason is None:
            continue
        # Errors remain errors. A callback failure must not masquerade as
        # rejection of the alternative or a successful empty table.
        rebuilt = list(trial.reconstruct_original())
        adopted = len(rebuilt) == 1
        if adopted:
            candidate = rebuilt[0]
            service = self.runtime.header_service
            adopted = service.valid_table(self.header, candidate)
            shape = _table_grid_matrices(candidate, retain=True)[:2]
            adopted = adopted and (shape[1] == parts[0]['cols'] if trial.split_kind == 'union'
                                   else candidate.header_rows >= 1)
        if adopted:
            before, after = source_counts(family), source_counts(rebuilt)
            scope = {source_key(r)[:3] for r in node_sources(trial.native_sources)}
            others = [tab for tab in tables if all(tab is not old for old in family)]
            other_sources = {key[:3] for key in source_counts(others)}
            candidate_units = {key[:3] for key in after}
            ident = getattr(rebuilt[0], 'table_id', None)
            id_collision = ident is not None and any(getattr(t, 'table_id', None) == ident for t in others)
            adopted = (before <= after and candidate_units <= scope
                       and all(n <= max(before[key], 1) for key, n in after.items())
                       and not candidate_units & other_sources
                       and not id_collision
                       and all(rebuilt[0] is not other for other in others))
            for row in rebuilt[0].placements:
                for cell in row:
                    if cell.source_content is not None:
                        node_sources((cell.source_content,))
            b = envelope(rebuilt[0]);original = trial.original_box
            adopted = adopted and b is not None and (
                min(b[2], original[2]) > max(b[0], original[0])
                and min(b[3], original[3]) > max(b[1], original[1]))
        self.events.append(dict(stage='structural_alternative',
                                status='adopted' if adopted else 'preserved',
                                reason=reason, split_kind=trial.split_kind,
                                original_box=list(trial.original_box),
                                selected_boxes=[list(b) for b in trial.selected_boxes],
                                replaced_table_ids=[getattr(t, 'table_id', None) for t in family] if adopted else [],
                                replacement_table_ids=[getattr(t, 'table_id', None) for t in rebuilt] if adopted else [],
                                reconstruction_contract='retained_concrete_grid',
                                grid_calls_observed=None))
        if adopted:
            old_ids = {id(t) for t in family}
            tables = [t for t in tables if id(t) not in old_ids] + rebuilt
    return tables


def original_refiner(runtime,page,original,material):
    box=tuple(original[0]);grid=tuple(tuple(None if c is None else tuple(c) for c in row)
                                    for row in original[1])
    trace=dict(original.bbox_provenance)
    def reconstruct():
        # This alternative is the actual resolved input structure, not a new
        # detector-parent crop and not the union of the resulting fragments.
        runtime.stats['structural_alternative_refinements']+=1
        with refinement_geometry(page) as current:
            holder=table.Table(current,[c for row in grid for c in row if c is not None],
                               bbox=U.pymupdf.Rect(box))
            holder.textpage=None;holder._chars=material.characters
            # The retained trial is immutable; the existing refinement port
            # accepts ordinary mutable row lists. Do not pass tuple rows into
            # its type-preserving native row-consumer contract.
            working=[list(row) for row in grid]
            return refine_child(current,working,box,trace,holder)
    return reconstruct


def register_union_trials(runtime, page, selection):
    material = runtime.page_material(page)
    families=[(item.original,item.chosen,'union') for item in selection.items
              if item.split and item.chosen is not None and len(item.chosen)>=2]

    for original,selected,kind in families:
        original_grid=tuple(tuple(None if c is None else tuple(c) for c in row) for row in original[1])
        selected_grids=tuple(tuple(tuple(None if c is None else tuple(c) for c in row)
                                  for row in e[1]) for e in selected)
        selected_boxes=tuple(tuple(_cells_bbox(g)) for g in selected_grids)
        sources=tuple(material.sources_in(tuple(original[0])))
        if len(selected)<2 or kind not in ('union','physical','directional'):continue
        runtime.structural_trials.append(StructuralProposalTrial(
            original_box=tuple(original[0]),
            original_grid=original_grid,selected_boxes=selected_boxes,split_kind=kind,
            native_sources=sources,
            reconstruct_original=original_refiner(runtime,page,original,material),
            selected_grids=selected_grids))


def adopt_originals(self, page, tables, material):
    tables = self._adopt_structural_trials(page, tables, material, ('physical', 'directional'))
    return self._adopt_structural_trials(page, tables, material, ('union',))


def install(runtime):
    pipeline = runtime.pipeline
    pipeline._proposal_family = MethodType(_proposal_family, pipeline)
    pipeline._adopt_structural_trials = MethodType(_adopt_structural_trials, pipeline)
    pipeline.finalizers.append(MethodType(adopt_originals, pipeline))
    runtime.union_selection_consumer = register_union_trials
