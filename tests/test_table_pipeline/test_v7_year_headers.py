"""Retained node/edge controls; no PDF, model or benchmark installation needed."""
import copy
import json
from pathlib import Path

import pytest

from pymupdf4llm._table_pipeline.v7_region_rules import _region_band_split
from test_v7_listing import listing


CASES = {
    name: json.loads((Path(__file__).parent / 'fixtures' / (name + '.json')).read_text())
    for name in ('shared_year_balance_a', 'shared_year_balance_b',
                 'number_description_listing', 'shared_then_restated_years')
}


@pytest.mark.parametrize('name', sorted(CASES))
def test_shared_year_headers_preserve_the_right_boundaries(name):
    case = copy.deepcopy(CASES[name])
    actual = _region_band_split(
        case['nodes'], case['edges'], case['rects'], case['bbox'], strict_gate=True
    )
    assert sorted(actual, key=lambda bbox: bbox[1]) == case['expected']
    assert case == CASES[name], 'Retained inputs must not be modified'


def test_single_year_value_is_not_a_multicolumn_header():
    # Keep independent header evidence so this isolates the year-field guard,
    # not the separate protection against unlabeled spatial gaps.
    inputs = listing(reset=True, header=True)
    for row in range(4):
        inputs[0][row * 2 + 1]['text'] = str(2001 + row)
    assert len(_region_band_split(*inputs, strict_gate=True)) == 2


def test_later_year_header_is_required_to_keep_the_later_boundary():
    case = copy.deepcopy(CASES['shared_then_restated_years'])
    lower_top = case['expected'][1][1]
    changed = 0
    for node in case['nodes']:
        if node['bbox'][1] >= lower_top and node['text'].strip() in ('2018', '2017'):
            node['text'] = ''
            changed += 1
    assert changed == 2
    assert _region_band_split(
        case['nodes'], case['edges'], case['rects'], case['bbox'], strict_gate=True
    ) == [case['bbox']]
