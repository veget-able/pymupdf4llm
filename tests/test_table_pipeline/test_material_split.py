import ast
from pathlib import Path
from unittest.mock import patch

from pymupdf._table_spans import SpanCell

from pymupdf4llm._table_pipeline import material_split_rules as rules
from pymupdf4llm._table_pipeline.material_region_split import partition_placements


def structure(rows):
    return {"bbox": [0, 0, 40, len(rows)*10], "extract": rows,
            "cells": [[[0,r*10,20,(r+1)*10], [20,r*10,40,(r+1)*10]] for r in range(len(rows))]}




def test_node_boundary_not_child_center():
    s = structure([["A", "B"]]+[["1", "2"]]*5)
    with patch.object(rules, "_region_band_split", return_value=[[0,0,40,30],[0,30,40,60]]):
        parts = rules.grid_split(s, nodes=[], edges=[], horizontal=False)
    assert [p["rows"] for p in parts] == [(0,3),(3,6)]


def test_grid_heteromorphic_reaches_split_with_nodes():
    s = structure([["Product", "Price"], ["1", "2"], ["3", "4"], ["5", "6"]]*2)
    with patch.object(rules, "_region_band_split", return_value=[s["bbox"]]):
        result = rules.region_split_v2([], [], [], s["bbox"], structure=s)
        parts = rules.grid_split(s, nodes=[], edges=[])
    assert result["detection"]["merged"]
    assert [p["rows"] for p in parts] == [(0,4),(4,8)]
    assert result["regions"] == [p["bbox"] for p in parts]


def test_node_boundary_inside_contiguous_grid_row():
    # Apple51-shaped geometry: node gap midpoint 167.5 is inside r5,
    # while contiguous grid rows meet at 168. Preserve the row, cut before r6.
    s = structure([["A", "B"]] + [["1", "2"]] * 11)
    s["cells"] = [[[0, 54+r*19, 20, 73+r*19],
                   [20, 54+r*19, 40, 73+r*19]] for r in range(12)]
    s["bbox"] = [0, 54, 40, 282]
    with patch.object(rules, "_region_band_split", return_value=[
            [0,54,40,159.5], [0,175.5,40,282]]):
        parts = rules.grid_split(s, nodes=[], edges=[], horizontal=False)
    assert [p["rows"] for p in parts] == [(0,6),(6,12)]


def test_node_boundary_with_real_grid_gap():
    s = structure([["A", "B"]] + [["1", "2"]] * 5)
    for row in s["cells"][3:]:
        for cell in row:
            cell[1] += 4
            cell[3] += 4
    s["bbox"][3] = 64
    with patch.object(rules, "_region_band_split", return_value=[
            [0,0,40,30], [0,34,40,64]]):
        parts = rules.grid_split(s, nodes=[], edges=[], horizontal=False)
    assert [p["rows"] for p in parts] == [(0,3),(3,6)]


def test_spans_are_transferred_intact_not_flattened():
    grid = [[SpanCell((0,0,20,20), "shared", 2, 2, "th"),
             SpanCell((20,0,30,10), "x", 1, 1, "th")],
            [SpanCell((20,10,30,20), "y", 1, 1, "td")],
            [SpanCell((0,20,20,30), "z", 2, 1, "td"),
             SpanCell((20,20,30,30), "q", 1, 1, "td")]]
    children, reason = partition_placements(grid, [{"rows": (0,2), "cols": (0,3)},
                                                  {"rows": (2,3), "cols": (0,3)}])
    assert reason is None
    assert vars(children[0][0][0]) == vars(grid[0][0])
    assert children[0][0][0] is not grid[0][0]
    assert sum(len(r) for child in children for r in child) == 5


def test_crossing_merged_cell_preserves_original():
    cell = SpanCell((0,0,20,10), "Title", 2, 1, "th")
    children, reason = partition_placements([[cell]], [{"rows": (0,1), "cols": (0,1)},
                                                     {"rows": (0,1), "cols": (1,2)}])
    assert children is None and reason["reason"] == "crossing_merged_cell"
    assert vars(cell) == dict(bbox=(0,0,20,10), text="Title", colspan=2, rowspan=1, tag="th", source_content=None)
