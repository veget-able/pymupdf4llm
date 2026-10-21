# Fang-inspired header RF R6 ONNX

This directory contains the ONNX export of the R6 table-header row classifier.
It is bundled in this review branch and used by the native HTML table pipeline.
This is a review candidate, not a claim about an upstream release.

## Artifact

- File: `fang-header-rf-r6.onnx`
- SHA256: `a810f2f20519f22db3fa1d1dde9e75ec266d8980e4def4fb2f383ec4788aa8b3`
- Size: 5,473,845 bytes
- Input: `features`, `tensor(double)`, shape `[N, 19]`
- Outputs: `label` (`tensor(int64)`) and `probabilities`
- ONNX opsets: default domain 18, `ai.onnx.ml` 1

The source estimator is
`runs/fang-header-rf/20260910-06/R6.joblib`, SHA256
`e72502b80b7075bb8c422f0ab25340e61b04b8b929ee69b4b4a996c02cf56ec9`.
It is a scikit-learn 1.9.0 `RandomForestClassifier` converted with
skl2onnx 1.20.0 and ONNX 1.22.0. Inference was checked with ONNX Runtime
1.28.0 on CPU.

## Feature contract

The columns must be supplied in this exact order:

1. `cell_count`
2. `mean_cell_length`
3. `character_count`
4. `digit_fraction`
5. `alpha_fraction`
6. `symbol_fraction`
7. `numeric_cell_fraction`
8. `mean_font_size`
9. `bold_cell_fraction`
10. `italic_cell_fraction`
11. `row_number`
12. `spanning_cell_fraction`
13. `cell_count_difference`
14. `mean_alignment`
15. `mean_horizontal_overlap`
16. `same_data_type_fraction`
17. `same_font_style_fraction`
18. `overall_content_repetition`
19. `mean_content_repetition`

The input must remain float64. A float32 export changed one classifier label
at an exact 0.5 decision tie in 68,309 checked rows, while this float64 export
had no label differences.

## Equivalence checks

- 68,309 prepared external-data rows: zero label differences from R6.joblib.
- 730 matched Table503 pairs / 13,112 input rows: zero label differences.
- The same 730 pairs: zero decoded top-header-prefix differences.

Only the `label` output is covered by this equivalence contract. The exported
floating-point probabilities are not declared numerically identical to
scikit-learn probabilities.

## Integration boundary

The graph contains only the random-forest classifier. Deployment must retain
the frozen 19-feature extractor, pred-only leading-title alignment, contiguous
leading-header prefix decoder, exact `None`/`N/A` guard, and the fallback for
tables whose native character/font features cannot be constructed.

The evaluated behavior changes only the final header/body row roles while
preserving table cells, text, bounding boxes, rowspan, colspan, and section
rows. Replacing earlier structural header decisions has not been evaluated.

The source estimator and training reports remain in the `pb_table` research
repository, not runtime dependencies: `docs/experiments/fang-rf-r6-header-retention-retraining-20260910.md`
and `docs/fang-rf-complete-training-reproduction-20260911.md`.
