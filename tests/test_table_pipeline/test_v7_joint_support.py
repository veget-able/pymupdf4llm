"""Portable controls for child admission, independent of benchmark GT."""
import copy

import pytest

from pymupdf4llm._table_pipeline.v7_region_rules import _region_band_split


def node(x, y, text, width=40, height=8):
    return dict(bbox=[x, y, x + width, y + height], text=text)


def body():
    return [node(x, y, text)
            for y, texts in [(60, ['Coverage Class', 'Pricing Factor']),
                             (72, ['Bronze', '1.2']), (84, ['Silver', '1.4'])]
            for x, text in zip([0, 100], texts)]


def split(top):
    nodes = top + body()
    original = copy.deepcopy(nodes)
    boxes = _region_band_split(nodes, [], [], [0, 0, 140, 92], strict_gate=True)
    assert nodes == original
    return boxes


@pytest.mark.parametrize('labels', [
    ['Proposed Changes', 'Rating Proposal'], ['予定変更', '料金案'],
])
def test_staggered_titles_are_not_a_two_dimensional_table(labels):
    assert len(split([node(0, 0, labels[0]), node(100, 10, labels[1])])) == 1


def test_one_multicolumn_line_plus_continuation_is_not_enough():
    top = [node(0, 0, 'Rating'), node(100, 0, 'Proposal'), node(100, 12, 'Continued')]
    assert len(split(top)) == 1


def test_two_by_two_table_remains_independent():
    top = [node(x, y, text)
           for y, texts in [(0, ['Other Class', 'Other Factor']), (12, ['A', '3'])]
           for x, text in zip([0, 100], texts)]
    assert len(split(top)) == 2


def test_multiline_cell_does_not_remove_support_of_its_logical_band():
    top = [node(0, 0, 'Other Class', height=20), node(100, 0, 'Other'),
           node(100, 12, 'Factor'), node(0, 32, 'A'), node(100, 32, '3')]
    assert len(split(top)) == 2


def test_wide_descriptions_remain_column_evidence_next_to_keys():
    # The short continuation discovers column two, but support comes from
    # the two actual records whose descriptions exceed 60% of table width.
    top = [node(0, 0, '10.1', width=15),
           node(30, 0, 'A long description', width=110),
           node(30, 10, 'continued', width=40),
           node(0, 22, '10.2', width=15),
           node(30, 22, 'Another long description', width=110)]
    assert len(split(top)) == 2


@pytest.mark.parametrize('separator', ['...', '   ', '\t'])
def test_single_node_typographic_columns_are_retained(separator):
    top = [node(0, 0, 'Alpha' + separator + '10', width=140),
           node(0, 12, 'Beta' + separator + '20', width=140)]
    assert len(split(top)) == 2
