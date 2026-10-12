# Repro fixtures for pymupdf4llm PRs #469, #470 and #471

This branch sits on the #471 head (which contains #470 and #469) and adds
only this directory. It is not meant to be merged. It gives the three PRs a
common set of failing tests and sample pages, so that a fix can be checked
locally before it is re-measured.

## Run

```
pip install pytest
pytest tests/repro_table_prs -q           # synthetic tests, no layout model needed
python tests/repro_table_prs/dump_pages.py  # converts pages/*.pdf to out/*.md
```

`dump_pages.py` uses the default (layout) path for every page, and the legacy
path (layout switched off) as well for the four #469 pages. Compare `out/`
with `expected_base/`, which holds the same conversions made with the PRs'
merge-base (6e51154). The base is not a ground truth, it is the "before" that
the review compared against.

## Synthetic tests

Each test builds a page with pymupdf and passes a hand-made grid to
`get_table_details()`, so it runs without the layout model.

| Test | Passes on | Fails on | What it checks |
|---|---|---|---|
| `test_pr470_row0.py::test_group_header_row_stays_in_table` | base | #470, #471 | a group-header row ("Three Months Ended" over two columns) is not hoisted out of the table |
| `test_pr470_row0.py::test_two_level_header_is_not_replaced_by_a_data_row` | base | #470, #471 | when row 0 holds two header levels, neither is hoisted and "Revenue" does not become the header |
| `test_pr470_row0.py::test_stub_label_keeps_the_date_line` | base, #471 | #470 | the colspan rule must not overwrite the date line under the group header |
| `test_pr470_join.py` | (skipped on base) | #470, #471 | two distinct tables with the same grid are not joined |
| `test_pr471_header_band.py` (pitch 16, 20) | base, #470 | #471 | a header band whose cells all wrap at the same offsets stays one row |
| `test_pr469_legacy_order.py` | base | #469, #470, #471 | legacy path: an unruled dense table keeps its row order (column-major output fails; one cell per line in row order passes) |

## Sample pages

Single pages from the ParseBench dataset
(https://huggingface.co/datasets/llamaindex/ParseBench, Apache-2.0; `table`
split, `docs/table/<name>.pdf`). The documents are public filings and
reports. Scores are the ParseBench table metric (GriTS and table record
match) on the default Markdown output, base -> head. They are given as
orientation; the metric does not see every defect listed.

### #470

| Page | Shows | base -> #470 |
|---|---|---|
| `Cost_Estimating_Guideline (1)_page3` | group header hoisted, columns lost | 0.544 -> 0.337 |
| `1 timetable (1)_page6` | rotated station headers dropped together with row 0 | 0.617 -> 0.493 |
| `bls-Feb-2026_page14` | group headers hoisted; "Not seasonally adjusted / Seasonally adjusted" no longer map to their columns although the score rises | 0.442 -> 0.469 |
| `SERFF_CA_random_pages 1_page310` | colspan overwrite loses header cells | 0.840 -> 0.497 |
| `203924_fb04e77929bf4bbc93dbd659653a4f01_page13` | colspan overwrite replaces a 170-word data row by the repeated band title; the metric barely sees it | 0.742 -> 0.727 |
| `AZ LIC Rate Tables 2.0.v2_page105` | "$3,000" and "$4,000" headers become "Basic Limit" | 0.373 -> 0.319 |
| `Apple 10-k_page50`, `SERFF_TX_random_pages 1_page201` | distinct tables joined as a continuation | 0.495 -> 0.078, 0.476 -> 0.128 |
| `SERFF_CA_random_pages 1_page2248`, `corp-q1-2025_page10` | the hoist working as intended | 0.165 -> 0.996, 0.466 -> 0.979 |

### #471 (against the #470 head)

| Page | Shows | #470 -> #471 |
|---|---|---|
| `FBLB-134215544_page10`, `FBLB-134215544_page6` | header band split into rows | 1.000 -> 0.316, 1.000 -> 0.658 |
| `SERFF_TX_random_pages 1_page300` | same defect | 1.000 -> 0.472 |
| `BRWS-134565917_page834`, `p29_page1` | the repair working as intended | 0.293 -> 0.883, 0.003 -> 0.251 |

### #469 (legacy path, compare the `.legacy.md` outputs)

| Page | Shows |
|---|---|
| `BRWS-134565917_page839` | 120 ordered lines become about 1,300 column-major lines |
| `SERFF_TX_random_pages 1_page568` | all years first, then all premiums |
| `SERFF_CA_random_pages 1_page756` | labels gathered into one code block, values listed afterwards |
| `SERFF_Interstate_random_pages 1_page80` | the good case: 31 data rows that the base drops are recovered |

## How the review measures

The whole ParseBench table set (503 pages) is converted with the default
Markdown path and scored with the ParseBench table metric. Base scores 57.19;
the #470 head 60.28 (row-0 exclusion +3.21, colspan handling +0.08,
continuation -0.24); the #471 head 59.92. A revised head can be re-scored on
request.
