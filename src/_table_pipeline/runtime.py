"""Native HTML table lifecycle: union, region/grid restoration, then R6 roles.

The algorithms are the reviewed table-source-delivery composition. No benchmark
data, saved outputs, external adapters, or ground truth is loaded. Native MuPDF
geometry settings are process-global, so product HTML calls are serialized;
parallel applications should use independent worker processes.
"""
from contextlib import contextmanager, nullcontext
from functools import lru_cache
from pathlib import Path
from threading import RLock

from pymupdf import table, _table_union as union
from pymupdf._table_pipeline import activate, current

from .header_band_split import split_header_band
from .r6_header import R6HeaderRoles, load_session
from .table_content_pipeline import ContentRestorationPipeline
from . import union_content_recovery, union_split_coherence

_LOCK = RLock()


@lru_cache(maxsize=1)
def header_session():
    return load_session(Path(__file__).with_name('models') / 'fang-header-rf-r6.onnx')


class TableRuntime:
    def __init__(self, model, session):
        self.pipeline = ContentRestorationPipeline(model)
        self.pipeline.split_integrity = True
        self.pipeline.header = R6HeaderRoles(
            session, leaf_completion=True, role_demotion=True, year_rows=True)
        self.recovery_events = []
        self.gate_events = []
        self.band_events = []
        self.errors = []
        gate = union_split_coherence.wrap(union._union_replace_append_base, self.gate_events)
        self._recover = union_content_recovery.wrap(gate, self.recovery_events, complete=True)

    def predict(self, page, **kwargs):
        return self.pipeline.adapter.predict(page, **kwargs)

    def fuse(self, existing, candidates, *, page, **kwargs):
        try:
            entries = self._recover(existing, candidates, page=page, **kwargs)
            for event in self.recovery_events + self.gate_events:
                if event.get('status') in ('error', 'gate-error'):
                    raise RuntimeError(f'Table restoration failed: {event}')
            return self.pipeline.adapter.resolve_entries(entries, page)
        except Exception as exc:
            self.errors.append(str(exc))
            raise

    def refine_header_band(self, page, grid):
        # Do not silently accept an unrefined result on an algorithm error.
        try:
            grid, event = split_header_band(page, grid)
        except Exception as exc:
            self.errors.append(str(exc))
            raise
        self.band_events.append(event)
        return grid

    def build_roles(self, page, grid, region):
        header = self.pipeline.header
        if header._deferred_builds is not None:
            header._deferred_builds[id(grid)] = (grid, region)
            return grid, region
        return header.apply_roles(page, grid, region)

    def find_tables(self, page, **kwargs):
        pipeline = self.pipeline
        header = pipeline.header
        previous_cache = header._char_cache
        previous_pending = getattr(pipeline, '_pending_parent_roles', None)
        header._char_cache = {}
        defer = bool(kwargs.get('union') and kwargs.get('refine'))
        try:
            with header.defer_build_roles() if defer else nullcontext(None) as pending:
                finder = table.find_tables(page, **kwargs)
            failures = [event for event in self.recovery_events + self.gate_events
                        if event.get('status') in ('error', 'gate-error')]
            if self.errors or failures:
                # Native find_tables may turn an internal exception into None.
                # A failed restoration must not become a successful empty page.
                raise RuntimeError(f'Table restoration failed: {self.errors or failures}')
            if header.errors:
                raise RuntimeError(f'Header classification failed: {header.errors}')
            if finder is None or not defer:
                return finder
            pipeline._pending_parent_roles = pending
            children = [child for tab in finder.tables for child in pipeline.split_table(page, tab)]
            if pending:
                raise RuntimeError('Unconsumed parent header decisions')
            finder.tables = pipeline.finalize_tables(page, children)
            for child in finder.tables:
                grid, decision = header.decisions[id(child.placements)]
                if grid is not child.placements or decision['status'] != 'onnx':
                    raise RuntimeError('Final table lacks an ONNX header decision')
            return finder
        finally:
            header._char_cache = previous_cache
            pipeline._pending_parent_roles = previous_pending


@contextmanager
def structured_tables():
    if current() is not None:
        raise RuntimeError('Recursive HTML table extraction is not supported')
    with _LOCK:
        from pymupdf.layout.DocumentLayoutAnalyzer import get_model
        runtime = TableRuntime(get_model(), header_session())
        with activate(runtime):
            yield runtime
