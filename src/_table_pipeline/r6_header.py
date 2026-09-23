"""Final-role R6 ONNX classification on live post-OCR placements."""
from dataclasses import replace
from contextlib import contextmanager

import numpy as np
import onnxruntime as ort
import pymupdf
from pymupdf import table

from pymupdf4llm._table_pipeline.header_leaf_completion import grid_rows, leaf_completion_depth, occupancy, year_row_depth
from pymupdf4llm._table_pipeline.header_role_demotion import demotion_depth
from pymupdf4llm._table_pipeline.r6_header_contract import (
    attach_pdf_features, chars_on_page, input_offset, missing_body_cap, norm, prefix_depth,
    row_features, title_rebased_features,
)


def load_session(path):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])


class R6HeaderRoles:
    """Use the LIVE post-OCR page supplying the final table placements.

    Hooks only final placements. Earlier header-based structural refinement,
    V5/V7, cells and section rows remain untouched. Process-local, not threaded.
    """
    def __init__(self, session, page_chars=None, *, enabled=True, leaf_completion=False, role_demotion=False,
                 year_rows=False):
        self.session = session
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
        self.events = []
        self.errors = []
        # Retain grids so callers can distinguish final children from discarded
        # parent decisions without id reuse. Does not alter the RF contract.
        self.decisions = {}
        self._char_cache = None
        self._deferred_builds = None

    @contextmanager
    def defer_build_roles(self):
        """Retain native grids/heuristic regions until the split keeps a parent.

        Only placement construction is deferred. Explicit child apply_roles
        calls keep their own inputs, and construction resumes immediately when
        this scope ends. The caller owns and releases the returned references.
        """
        previous = self._deferred_builds
        pending = {}
        self._deferred_builds = pending
        try:
            yield pending
        finally:
            self._deferred_builds = previous

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

    def apply_roles(self, page, grid, region):
        if not self.enabled:
            return grid, region
        event = {"before": region.top_header_rows, "after": region.top_header_rows,
                 "rows": len(grid), "section_rows": list(region.section_header_rows),
                 "input_source": "live_post_ocr" if self.page_chars is None else "injected"}
        self.decisions[id(grid)] = (grid, event)
        try:
            if not grid:
                raise ValueError("empty_grid")
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
            features = row_features(rows)
            offset = input_offset(grid, features, region.top_header_rows, limit=1,
                                  section_header_rows=region.section_header_rows)
            inputs = np.asarray(title_rebased_features(features, offset), dtype=np.float64)
            labels = self.session.run(["label"], {"features": inputs})[0].tolist()
            raw_depth = offset + prefix_depth(labels)
            capped = missing_body_cap(rows, raw_depth, offset)
            depth = demoted = capped
            span_rows = grid_rows(grid)
            # One occupancy resolution of the grid shared by H3 and H2.
            cells = occupancy(span_rows) if (self.role_demotion or self.leaf_completion or self.year_rows) else None
            if self.role_demotion:
                # Over-tag demotion first: drop trailing common-note and
                # section rows the model tagged as header.
                depth = demoted = demotion_depth(span_rows, capped, cells)
            if self.leaf_completion:
                # Merged-header leaf-label completion: extend over the row
                # that supplies single-column labels under unresolved
                # colspan parents, using the grid's own spans. The existing
                # None/N/A body cap is the final word: a completed row of
                # missing-value tokens is capped again, never re-promoted.
                depth = missing_body_cap(rows, leaf_completion_depth(span_rows, demoted, cells), offset)
            completed = depth
            if self.year_rows:
                # Year/date second header line under labeled columns; the
                # None/N/A cap stays final here as well.
                depth = missing_body_cap(rows, year_row_depth(span_rows, completed, cells), offset)
            event.update(status="onnx", after=depth, offset=offset,
                         guard_changed=capped != raw_depth,
                         role_demoted=demoted != capped,
                         leaf_completed=completed != demoted,
                         year_rows=depth != completed)
            self.events.append(event)
            region = replace(region, top_header_rows=depth)
            return table._refine_tag_grid(grid, depth), region
        except Exception as error:
            # Finder catches exceptions internally: explicitly fail the run
            # after inference rather than silently publishing partial output.
            self.errors.append(repr(error))
            raise
