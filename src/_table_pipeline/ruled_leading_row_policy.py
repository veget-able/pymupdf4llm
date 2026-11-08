"""Actual ruled leading-row production and its source/role adoption gate."""
from dataclasses import dataclass
from types import MethodType
import pymupdf
from pymupdf import table
from pymupdf._table_headers import HeaderRegion
from pymupdf4llm.helpers.table_html.reconstruct import _table_grid_matrices, _placement_grid_matrices
from .placement_material import source_key, source_counts, placement_counts, grid_state, envelope, _cells_bbox
from .table_content_recovery import node_sources
from .ruled_leading_row import recover as recover_ruled_leading_row

def restore_leading_rows(self, page, tables, material):
    reserved = set(source_counts(tables))
    output = []
    for tab in tables:
        obstacles = [other for other in tables if other is not tab] + output
        restored = tab
        ruled = recover_ruled_leading_row(restored, material.sources, material.words,
                                          material.edges, obstacles)
        if ruled is not None:
            before = source_counts([restored])
            after = source_counts([ruled])
            if before <= after and not any(k in reserved and k not in before for k in after):
                restored = self._roles(page, ruled, HeaderRegion(
                    top_header_rows=ruled.header_rows, section_header_rows=ruled.section_rows))
                reserved.update(after)
                self.events.append(dict(stage='independent_restore', status='ruled_leading_row'))
        output.append(restored)
    return output


def install(runtime):
    runtime.pipeline.finalizers.append(MethodType(restore_leading_rows, runtime.pipeline))
