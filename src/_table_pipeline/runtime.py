"""Call-scoped composition of the included table feature providers."""
from collections import Counter
from contextlib import contextmanager, nullcontext
from copy import copy
from threading import RLock

from pymupdf import table, _table_union as union
from pymupdf._table_pipeline import activate, current
from .native_page_material import PageMaterial, page_frame
from .native_preparation import NativePreparation
from .structural_inputs import StructuralInputs
from .table_finalization import TableFinalization

_LOCK = RLock()




class RetainedPrediction:
    """The real completed inference and the exact inputs that produced it."""
    def __init__(self, predict, args, kwargs, result=None):
        self.predict, self.args, self.kwargs, self.result = predict, args, kwargs, result

    def resolve(self):
        if self.result is None:
            self.result = self.predict(*self.args, **self.kwargs)
            if self.result[0] is None:
                raise RuntimeError('TGIF did not return a parent grid')
        return self.result[0]

    def __getattr__(self, name):
        return getattr(self.resolve(), name)




class NativeRoles:
    provider = 'native-main'
    def __init__(self):
        self.decisions = {}
        self.states = {}
        self.stats = Counter()
        self.events = []
        self.errors = []
        self._deferred_builds = None

    @contextmanager
    def finder_scope(self):
        yield

    @staticmethod
    def state(grid):
        return tuple(tuple((tuple(c.bbox) if c.bbox is not None else None,
                            c.text, c.colspan, c.rowspan, c.tag,
                            id(c.source_content)) for c in row) for row in grid)

    def observe(self, grid, region):
        self.decisions[id(grid)] = (grid, region)
        self.states[id(grid)] = self.state(grid)
        self.stats['observed'] += 1
        return grid, region

    def apply_roles(self, page, grid, region=None, **kwargs):
        # Run the actual extracted native role producer on this current grid.
        self.stats['producer_calls'] += 1
        return self.observe(*table._native_roles_from_placements(grid))

    def valid_table(self, tab):
        entry = self.decisions.get(id(tab.placements))
        return (entry is not None and entry[0] is tab.placements
                and self.states[id(tab.placements)] == self.state(tab.placements)
                and entry[1].top_header_rows == tab.header_rows
                and entry[1].section_header_rows == tab.section_rows)


class _CaptureSession:
    def __init__(self, original, owner):
        self.original, self.owner = original, owner

    def __getattr__(self, name):
        return getattr(self.original, name)

    def run(self, names, inputs, *args, **kwargs):
        outputs = self.original.run(names, inputs, *args, **kwargs)
        self.owner.stats['gnn_calls'] += 1
        # Diagnostic count only; detector graph values are not retained.
        return outputs


class TableRuntime:
    def __init__(self, model=None):
        self.model = self.model_owner = None
        self.stats = Counter()
        self.errors = []
        self.band_events = []
        self.recovery_events = []
        self.gate_events = []
        self.span_material = {}
        self.span_material_epochs = {}
        self._span_material_sequence = 0
        self.ruling_materials = {}
        self.rasters = {}
        self._page_materials = {}
        self.structural_trials = []
        self.structure_predict = None
        self.structure_pixel_space = None
        self.roles = NativeRoles()
        self.header = self.roles
        self.header_service = NativePreparation()
        self.structural_policy = StructuralInputs()
        self.refine_rows = self.structural_policy.refine_rows
        self.refine_table = table._native_refine_grid_tables
        if model is not None:self._bind_model(model)
        self.pipeline = TableFinalization(self)
        self.candidate_admission = None
        self.union_consumer = None
        self.parent_coherence = None
        self.union_selection_consumer = None
        self.geometry_processor = None
        self.installed_components = []
        from .components import configure
        configure(self)

    def _bind_model(self, model):
        from pymupdf.layout import get_active_provider
        provider = get_active_provider()
        if provider is not None:
            if provider.model is not model:
                raise RuntimeError("Active provider/model identity mismatch")
            self.model_owner = model
            self.model = provider.bind_runtime(self, RetainedPrediction)
            return
        # Borrow the original provider's sessions, never create a second model.
        self.model_owner = model
        self.model = copy(model)
        self.model._model = copy(model._model)
        extractor = copy(model._model.table_grid_extractor)
        self.model._model.table_grid_extractor = extractor
        original = extractor.predict
        self.model._model.session = _CaptureSession(model._model.session, self)

        def execute(*args, **kwargs):
            self.stats['tgif_calls'] += 1
            return original(*args, **kwargs)

        def retain(*args, **kwargs):
            self.stats['tgif_requested'] += 1
            return RetainedPrediction(execute, args, kwargs), []
        self.structure_predict = execute
        self.structure_pixel_space = "RGB"
        extractor.predict = retain

    def release_materials(self, keep_page=None):
        keep = page_frame(keep_page) if keep_page is not None else None
        self.rasters = {k:v for k,v in self.rasters.items() if k[0] == keep}
        self._page_materials.clear()
        self.structural_trials.clear()
        self.span_material.clear()
        self.span_material_epochs.clear()
        self.ruling_materials.clear()
        self.roles.decisions.clear()
        self.roles.states.clear()
        self.header.decisions.clear()
        self.header_service.decisions = type(self.header_service.decisions)()
        self.header._verified_transfer_store = self.header_service.decisions
        self.structural_policy.materials.clear()
        self.structural_policy.pages.clear()
        self.structural_policy.phrases.clear()
        self.structural_policy.graphic_cache.clear()
        self.structural_policy.boundaries.clear()

    def predict(self, page, **kwargs):
        from pymupdf.layout import get_active_model
        owner = get_active_model()
        if self.model is None:self._bind_model(owner)
        elif owner is not self.model_owner:raise RuntimeError('Layout provider changed during extraction')
        self.release_materials(keep_page=page)
        return self.model.predict(page, **kwargs)

    def primaries(self, page):
        return union._layout_table_grids_base(page)



    def accept_ruling_materials(self, page, edges):
        self.ruling_materials[id(page)] = tuple(edges)

    def accept_source_spans(self, page, blocks):
        self.span_material[page] = blocks
        self._span_material_sequence += 1
        self.span_material_epochs[page] = self._span_material_sequence
        from pymupdf._table_word_geometry import notify_word_character_material
        notify_word_character_material(page, blocks, self._span_material_sequence)
        self.structural_policy.accept_spans(page, blocks)


    def admit_cell_groups(self, page, groups, *, source_paths=(), source_edges=()):
        if self.candidate_admission is not None:
            return self.candidate_admission(page, groups, paths=source_paths, edges=source_edges)
        return union._union_native_admit_cell_groups(page, groups)

    def fuse(self, existing, candidates, *, page, **kwargs):
        try:
            if self.union_consumer is not None:
                return self.union_consumer(self, page, existing, candidates, **kwargs)
            selection = None
            if self.union_selection_consumer is not None:
                from .selection_material import StructureSelection
                selection = StructureSelection()
            covered = None
            if self.parent_coherence is not None:
                covered = lambda original, children, live_page: self.parent_coherence(original, children, live_page, union)
            entries = union._union_replace_append_base(list(existing), candidates, page=page,
                _selection=selection, _partition_covered=covered, **kwargs)
            if selection is not None:
                self.union_selection_consumer(self, page, selection)
            return entries
        except Exception as exc:
            self.errors.append(str(exc))
            raise


    def validate_table_sources(self, page, tables):
        self.page_material(page).validate_sources(tables)

    def accept_raster_material(self,page,image,*,scale,space):
        import numpy as np
        key=(page_frame(page),float(scale),space)
        if key not in self.rasters:
            value=np.asarray(image).copy()
            value.flags.writeable=False
            self.rasters[key]=value
            self.stats['raster_retained']+=1

    def cached_raster_material(self,page,*,scale,space):
        value=self.rasters.get((page_frame(page),float(scale),space))
        if value is None:return None
        self.stats['raster_reused']+=1
        return value.copy()  # Existing input producers retain a writable array.

    def page_material(self,page):
        key=page_frame(page)
        if key not in self._page_materials:self._page_materials[key]=PageMaterial(page,self)
        return self._page_materials[key]

    def reconstruct_region(self,page,bbox):
        if self.structure_predict is None:
            from pymupdf.layout import get_active_model
            self._bind_model(get_active_model())
        return self.page_material(page).reconstruct(bbox)

    def find_tables(self, page, **kwargs):
        with table._html_table_scope(), self.structural_policy.boundary_scope(), self.header_service.lifetime(), self.header.finder_scope():
            finder = self._find_tables_current(page, **kwargs)
            if self.header.errors:
                self.errors.extend(self.header.errors)
                raise RuntimeError(f'Header classification failed: {self.header.errors}')
            return finder

    def refine_header_band(self, page, grid):
        if self.geometry_processor is None:
            return grid
        try:
            grid, event = self.geometry_processor(page, grid)
        except Exception as exc:
            self.errors.append(str(exc))
            raise
        self.band_events.append(event)
        self.stats['band_checks'] += 1
        self.stats['band_splits'] += event['status'] == 'split'
        return grid

    def strict_span_policy(self, *args):
        return self.structural_policy.parent_merge(*args)

    def structural_boundary(self, page, cells, *, consumer='row', table_bbox=None):
        return self.structural_policy.structural_boundary(self.header_service, self.header,
            page, cells, purpose='structure' if consumer == 'row' else 'final',
            table_bbox=table_bbox)

    def build_roles(self, page, grid, region, *, table_bbox=None):
        if self.header._deferred_builds is not None:
            self.header._deferred_builds[id(grid)] = (grid, region)
            return grid, region
        return self.header.apply_roles(page, grid, region, table_bbox=table_bbox)

    def refine_tagged_table(self, page, tab, *, input_grid=None):
        grid = table._refine_cells_to_grid(tab.cells) if input_grid is None else input_grid
        def make_table(flat, was_split):
            out = table.Table(page, flat, bbox=None if was_split else tab._bbox) if flat else tab
            if hasattr(tab, 'bbox_provenance'):
                meta = dict(tab.bbox_provenance)
                if was_split:
                    meta.update(bbox_source='find_tables', bbox_operation='refine_split',
                                parent_bbox_source=meta.get('bbox_source', 'unknown'),
                                parent_bbox=list(tab.bbox))
                out.bbox_provenance = meta
            return out
        yield from table._structured_refine_grid_tables(page, grid, tab.bbox, make_table,
                                                        split_repeated_headers=True)

    def _find_tables_current(self, page, **kwargs):
        header = self.pipeline.header
        defer = bool(kwargs.get('union') and kwargs.get('refine')
                     and hasattr(header, 'defer_build_roles'))
        try:
            with header.defer_build_roles() if defer else nullcontext(None) as pending:
                finder = table.find_tables(page, **kwargs)
            if finder is None:
                raise RuntimeError('Native table finder failed during restoration')
            if not (kwargs.get('union') and kwargs.get('refine')):
                return finder
            self.pipeline._pending_parent_roles = pending
            children = [c for tab in finder.tables for c in self.pipeline.split_table(page, tab)]
            if pending:
                raise RuntimeError('Unconsumed parent role decisions')
            finder.tables = self.pipeline.finalize_tables(page, children)
            if hasattr(self, 'header_service'):
                for child in finder.tables:
                    if not self.header_service.valid_table(self.header, child):
                        raise RuntimeError('Final table lacks a verified current-grid role decision')
            if self.errors:
                raise RuntimeError(f'Table restoration failed: {self.errors}')
            return finder
        except Exception as exc:
            self.errors.append(str(exc))
            raise
        finally:
            self.pipeline._pending_parent_roles = None


@contextmanager
def structured_tables():
    if current() is not None:
        raise RuntimeError('Recursive structured table extraction is unsupported')
    with _LOCK:
        runtime = TableRuntime()
        try:
            with activate(runtime):
                yield runtime
        finally:
            runtime.release_materials()
            runtime.model = None
            runtime.model_owner = None
