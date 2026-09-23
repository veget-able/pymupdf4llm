"""Product lifecycle contracts, independent of the benchmark repository."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest
import pymupdf
from pymupdf import _table_pipeline as hooks
from pymupdf4llm._table_pipeline import runtime
from pymupdf4llm._table_pipeline.deferred_tgif import DeferredPrediction, DeferredTGIFPipeline
from pymupdf4llm._table_pipeline.table_restoration import RestorationContext, publish


def test_scope_resets_on_exception_and_rejects_nesting():
    assert hooks.current() is None
    with pytest.raises(ValueError):
        with hooks.activate(object()) as _:
            active = hooks.current()
            with pytest.raises(RuntimeError, match='Nested'):
                with hooks.activate(object()):
                    pass
            assert hooks.current() is active
            with ThreadPoolExecutor(1) as pool:
                assert pool.submit(hooks.current).result() is None
            raise ValueError('caller failure')
    assert hooks.current() is None


def test_deferred_model_view_does_not_patch_original_and_reuses_prediction():
    calls = []
    def predict(image):
        calls.append(image)
        return np.array([[1, 2]]), []
    extractor = SimpleNamespace(predict=predict)
    session = object()
    model = SimpleNamespace(_model=SimpleNamespace(table_grid_extractor=extractor, session=session))
    first, second = DeferredTGIFPipeline(model), DeferredTGIFPipeline(model)
    assert model._model.table_grid_extractor is extractor
    assert extractor.predict is predict and model._model.session is session
    pending, _ = first.model._model.table_grid_extractor.predict('image')
    assert isinstance(pending, DeferredPrediction) and not calls
    assert pending.resolve() is pending.resolve()
    assert calls == ['image'] and first.stats.tgif_executed == 1
    assert second.stats.tgif_executed == 0


def test_parent_delivery_is_call_local():
    one, two = [SimpleNamespace(pipeline=SimpleNamespace(restoration_contexts={})) for _ in range(2)]
    context = RestorationContext(0, (1,), object())
    with hooks.activate(one):
        publish(context)
    with hooks.activate(two):
        assert not two.pipeline.restoration_contexts
    publish(context)  # No active consumer: no global retained ledger.
    assert one.pipeline.restoration_contexts[(0, (1,))] is context


def test_bundled_model_contract():
    session = runtime.header_session()
    assert session is runtime.header_session()
    entry = session.get_inputs()[0]
    assert entry.name == 'features' and entry.type == 'tensor(double)'
    assert entry.shape[-1] == 19
    assert session.run(['label'], {'features': np.zeros((1, 19), dtype=np.float64)})[0].shape == (1,)


def test_html_parser_activates_and_plain_parser_does_not(monkeypatch):
    from pymupdf4llm.helpers import document_layout as module
    calls = []
    @contextmanager
    def enter():
        with hooks.activate('native'):
            calls.append('enter')
            yield
    monkeypatch.setattr(runtime, 'structured_tables', enter)
    monkeypatch.setattr(module, '_parse_document_impl', lambda *a, **k: hooks.current())
    assert module.parse_document(None, render_html_tables=False) is None
    assert not calls
    assert module.parse_document(None, render_html_tables=True) == 'native'
    assert hooks.current() is None and calls == ['enter']


def test_native_refine_boundary_calls_consumer(monkeypatch):
    seen = []
    class Consumer:
        def build_roles(self, page, grid, region):
            seen.append((grid, region))
            return grid, region
    with pymupdf.open() as doc:
        page = doc.new_page()
        with hooks.activate(Consumer()):
            pymupdf.table._refine_build_placements(page, [], 0)
    assert len(seen) == 1


def test_failure_cannot_become_empty_success(monkeypatch):
    obj = runtime.TableRuntime.__new__(runtime.TableRuntime)
    header = SimpleNamespace(_char_cache=None, errors=[])
    obj.pipeline = SimpleNamespace(header=header)
    obj.errors, obj.gate_events, obj.recovery_events = [], [], []
    def fail(page, **kwargs):
        obj.errors.append('native caught refinement failure')
        return None
    monkeypatch.setattr(runtime.table, 'find_tables', fail)
    with pytest.raises(RuntimeError, match='refinement failure'):
        obj.find_tables(None)
    assert header._char_cache is None


def test_repeated_product_html_calls_release_context():
    import pymupdf4llm
    from pymupdf.layout.DocumentLayoutAnalyzer import get_model
    model = get_model()
    session, extractor = model._model.session, model._model.table_grid_extractor
    predict = extractor.predict
    with pymupdf.open() as doc:
        for _ in range(2):
            page = doc.new_page()
            page.insert_text((60, 60), 'Item              Amount')
            page.insert_text((60, 85), 'Apples            12')
        first = pymupdf4llm.to_markdown(doc, table_output='html', show_progress=False, use_ocr=False)
        second = pymupdf4llm.to_markdown(doc, table_output='html', show_progress=False, use_ocr=False)
    assert first == second
    assert hooks.current() is None
    assert model._model.session is session and model._model.table_grid_extractor is extractor
    assert extractor.predict == predict
