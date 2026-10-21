"""THF1 title alignment is a product contract, not a scoring dependency."""
import ast
from pathlib import Path

from pymupdf._table_spans import SpanCell
from pymupdf4llm._table_pipeline import r6_header_contract as contract


def cell(text, colspan=1, rowspan=1, tag='th'):
    return SpanCell(None, text, colspan, rowspan, tag)


def offset(grid, depth=2):
    return contract.input_offset(grid, [[0] * 19 for _ in grid], depth)


def test_spanning_title_alignment_keeps_original_grid():
    grid = [[cell('Annual report', 2)], [cell('Product'), cell('Amount')],
            [cell('A', tag='td'), cell('100', tag='td')]]
    assert offset(grid) == 1
    assert grid[0][0].text == 'Annual report'
    assert grid[0][0].colspan == 2


def test_bottom_unit_note_is_not_a_removed_input_prefix():
    grid = [[cell('Product'), cell('Amount')], [cell('(in millions)', 2)],
            [cell('A', tag='td'), cell('100', tag='td')]]
    assert offset(grid) == 0


def test_single_header_and_empty_prefix_are_not_rebased():
    grid = [[cell('Report', 2)], [cell('A', tag='td'), cell('100', tag='td')]]
    assert offset(grid, 1) == 0
    grid.insert(0, [cell('', 2, tag='td')])
    assert offset(grid, 2) == 0


def test_rowspanning_title_uses_one_logical_title_slot():
    grid = [[cell('Report', 2, 2)], [], [cell('Product'), cell('Amount')],
            [cell('A', tag='td'), cell('100', tag='td')]]
    # The empty physical row is not eligible for rebasing in the model contract.
    assert offset(grid, 3) == 0


def test_runtime_has_no_benchmark_imports():
    root = Path(contract.__file__).parent
    forbidden = {'parse_bench', 'pb_table', 'sklearn'}
    for path in root.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert (node.module or '').split('.')[0] not in forbidden, path
            elif isinstance(node, ast.Import):
                assert not {item.name.split('.')[0] for item in node.names} & forbidden, path
