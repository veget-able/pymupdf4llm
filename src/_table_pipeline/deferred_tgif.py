"""Delayed TGIF on a document-local model view, reusing union/refine/HTML.

Weights and sessions are shared; method bindings and captured page inputs are
local. The original cached Layout model is never patched.
"""
from dataclasses import dataclass, field
from time import perf_counter
from types import SimpleNamespace

import pymupdf
from pymupdf import _table_union as union


def region_split(region, *, edge_evidence=None):
    """Placeholder: preserve the original region, without any split heuristic."""
    return [region]


@dataclass
class RunStats:
    tgif_requested: int = 0
    tgif_executed: int = 0
    tgif_seconds: float = 0.0
    region_split_calls: int = 0
    gnn_inference_calls: int = 0
    region_split_inputs: list = field(default_factory=list)
    routes: list = field(default_factory=list)


class DeferredPrediction:
    def __init__(self, predict, args, kwargs):
        self.predict = predict
        self.args = args
        self.kwargs = kwargs
        self.result = None

    def resolve(self):
        if self.result is None:
            result = self.predict(*self.args, **self.kwargs)
            if result[0] is None:
                raise RuntimeError("TGIF returned None: primary eligibility parity is not established")
            self.result = result
            self.args = self.kwargs = None
        return self.result[0]

    def __getattr__(self, name):
        return getattr(self.resolve(), name)


class DeferredRows:
    def __init__(self, group, original_reader):
        self.group = group
        self.original_reader = original_reader

    def resolve(self):
        group = dict(self.group)
        group["table_grid"] = self.group["table_grid"].resolve()
        entries = self.original_reader(SimpleNamespace(layout_information=[group]))
        if len(entries) != 1:
            raise RuntimeError("Deferred TGIF did not produce one original primary")
        return entries[0][1]


class DeferredTGIFPipeline:
    """Per-document model view; never replace shared model/session methods."""
    def __init__(self, model, *, region_resolver=None):
        from copy import copy
        from .gnn_edge_evidence import EdgeCapture
        self.stats = RunStats()
        self.region_resolver = region_resolver
        self.model = copy(model)
        self.model._model = copy(model._model)
        extractor = copy(model._model.table_grid_extractor)
        original_predict = extractor.predict
        self.model._model.table_grid_extractor = extractor
        def execute(*args, **kwargs):
            self.stats.tgif_executed += 1
            start = perf_counter()
            try:
                return original_predict(*args, **kwargs)
            finally:
                self.stats.tgif_seconds += perf_counter() - start
        def predict(*args, **kwargs):
            self.stats.tgif_requested += 1
            return DeferredPrediction(execute, args, kwargs), []
        extractor.predict = predict
        self.capture = EdgeCapture(self.model, self.stats)
        self.model._model.session = self.capture

    def predict(self, page, **kwargs):
        return self.capture.predict(page, **kwargs)

    def primaries(self, page):
        original_reader = union._layout_table_grids_base
        entries = []
        for index, group in enumerate(page.layout_information or []):
            if not isinstance(group, dict) or group.get("class_name") != "table":
                continue
            prediction = group.get("table_grid")
            if isinstance(prediction, DeferredPrediction):
                if not group.get("group_bbox"):
                    continue
                entries.append(union._TableGridEntry(
                    pymupdf.Rect(group["group_bbox"][:4]), DeferredRows(group, original_reader),
                    {"bbox_source": "gnn", "grid_source": "tgif", "bbox_operation": "gnn_detection",
                     "source_gnn_indices": [index]}))
            else:
                for entry in original_reader(SimpleNamespace(layout_information=[group])):
                    entries.append(union._entry_with_provenance(entry, source_gnn_indices=[index]))
        return entries

    def resolve_entries(self, entries, page):
        resolved = []
        for entry in entries:
            metadata = entry.bbox_provenance
            self.stats.routes.append({"bbox": list(entry[0]), **metadata})
            if isinstance(entry[1], DeferredRows):
                if metadata["bbox_operation"] != "gnn_keep":
                    raise RuntimeError("Unresolved grid outside gnn_keep")
                self.stats.region_split_calls += 1
                evidence = entry[1].group.get("_region_edge_evidence")
                if evidence is None:
                    raise RuntimeError("Missing region_split edge probabilities")
                resolved.extend(self.region_resolver(entry, page, evidence))
            else:
                resolved.append(entry)
        return resolved
