# ODM page pixels without normal stored text

Branch: ocr/page-selector/odm-no-text

Independent candidate directly on fixed main. P2 is retained: this is a controlled ODM input change, not ODM-only selection and not an IMF2 branch or a correction bundle. The approved integration remains unchanged.

Paired sources: https://github.com/veget-able/PyMuPDF/tree/ocr/page-selector/odm-no-text and https://github.com/veget-able/pymupdf4llm/tree/ocr/page-selector/odm-no-text. Each repository has one final review commit on main. This repository contains implementation and tests.

## Contract

- Preserve main P2 heuristics, existing OCR-layer gate, use_ocr/force_ocr and explicit KEEP/DROP/FORCE behavior. No unrelated correction or unconditional Unicode priority is enabled.
- The ODM receives22 features, not an image tensor. Only page_sobel_energy/page_sobel_entropy/page_sobel_var/page_white_ratio change. The other18 original text/layout/embedded-image features remain, including num_spans/text_area. Original weights, feature order and0.93 threshold remain.
- Render at the original72DPI in grayscale, then downsample128x128. Exclude main Rapid-normal stored spans: not ocr_text(span) and no U+FFFD. Native glyph culling uses span bboxes; images/vectors remain. This is not white-box painting or a rewrite of the PDF.
- An empty normal exclusion list returns the original page render, preserving damaged glyphs. OCR-like hidden text and U+FFFD spans are not normal exclusion targets. This is an input-render condition, not a new page damage-selection rule or feature5 priority.
- no-text describes the page pixel input, not zeroing the structural text features or deleting all stored PDF text. The shared/native culling implementation can retain glyphs outside approximate span boxes; no new character mapping/filter is introduced.
- Post-selection Rapid DET/REC, normal-glyph OCR rendering, insertion and output remain those of the target base. No ROI restriction or direct REC is added. No new model file, dependency, retraining or language selection.

## Evaluated scopes and scores

Same507PDF509pages/CF506/SF476 supported456defined; official scorer8c63e84; RapidOCR3.10 PPv6small DET/REC150DPI. Nominal72DPI applies only to ODM page features, not the later OCR render. Main parents: PyMuPDF1d34e04da00b7673a0b2c3f68b5a5246793a50b8 and pymupdf4llm363f177ef50deb05f07db8bf2061e7b9c8102b07. Existing1.28.0 was not rerun; this is a draft-2.0 feature comparison.

- main-odm-no-text: baseline CF79.6709088%/SF56.6573495% -> candidate CF79.7167681%/SF56.8591933%; delta+0.0458594/+0.2018438pp.
  PageGT200: TP85,FP3,FN15,TN97; precision96.5909%,recall85.0000%,F190.4255%.
  P2/ODM cohort and page metadata unchanged;18 feature values matched on every one of299 ODM calls. Page pixel values changed on209 pages. Same selected pages use identical downstream Rapid input.

- corrected-odm-no-text: baseline CF81.9120785%/SF57.9868410% -> candidate CF81.9573219%/SF58.1886848%; delta+0.0452433/+0.2018438pp.
  PageGT200: TP85,FP3,FN15,TN97; precision96.5909%,recall85.0000%,F190.4255%.
  P2/ODM cohort and page metadata unchanged;18 feature values matched on every one of342 ODM calls. Page pixel values changed on209 pages. Same selected pages use identical downstream Rapid input.

The first scope is this branch alone on main. The second is an auxiliary composition on approved corrections1,2,3,4,6,7, retaining P2+ODM and replacing only the two input-feature files. It is not an extra feature inherited by this independent branch, and is not installed/pushed as a replacement of the default IMF2 integration.

Validation:6 renderer/feature tests;641 real feature-parity checks;1014 fresh public output runs. Verified recognition replay427, same-run replay1, new actual DET/REC inputs1. Official workers14 new;1118 exact output/case/scorer matches reused.

Observed public-API campaign span sum330.61s; score validation/scoring9.88s. Spans run from first API start to last successful completion, include4workers/tracing/feature audit, recognition reuse and the initial observer retry pause. They are validation cost, not standalone product latency or a speed ranking. The initial observer incorrectly treated identical original/candidate NaNs in3 documents as a difference; equal_nan comparison fixed the observer only and those3 were retried. Other successful outputs were preserved.

Original ODM weights SHA256:f72d8975dfc650d6761f793dad424939e70bb94a27d13de8d3507033c74fa101. Page-input distribution changes without retraining; the measured gain is not a general accuracy guarantee.

## Reproduction

Use an existing compatible draft-2.0 runtime and the paired branch sources. A source overlay must expose this checkout as pymupdf4llm; do not accidentally benchmark the installed historical package. No wheel build/publication or installation was performed.

python examples/check_odm_no_text.py --core-repo /path/to/PyMuPDF
python -m pytest --noconftest -q -p no:cacheprovider tests/test_odm_no_text.py

The repository conftest can install dependencies, so --noconftest is intentional. The frozen local public API protocol, source overlays, recognition/model hashes, exact features and official scores are in runs/OCR_ODM_NO_TEXT_BRANCH_20261031 in the pb_ocr research workspace. Source/PDF content stays unchanged during rendering.

## Complete improvements, regressions and changed outputs

Per-document scores are percentages; deltas are percentage points. Page1 labels are exact for a single-page PDF. Multi-page quality is aggregated and not attributed to one page. OCR activity is separate evidence; CF/SF gains do not by themselves prove every OCR addition is correct. Full machine-readable cases are in docs/ocr-odm-no-text-cases.json.

### main+input change only

- CF: improved9,regressed4,unchanged493.
- SF: improved3,regressed3,unchanged450.

- text/text_dense__underline; PDF page1.
  Input:docs/text/text_dense__underline.pdf.
  CF: 42.7530% -> 47.8268% (+5.0738pp;improved).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_misc__2pages; PDF page1.
  Input:docs/text/text_misc__2pages.pdf.
  CF: 90.1375% -> 90.1309% (-0.0065pp;regressed).
  SF: 72.7941% -> 72.7941% (+0.0000pp;unchanged).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_misc__ikea3; PDF page1.
  Input:docs/text/text_misc__ikea3.pdf.
  CF: 77.3498% -> 76.7650% (-0.5848pp;regressed).
  SF: 46.5186% -> 35.0055% (-11.5132pp;regressed).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_multicolumns__drill; PDF page1.
  Input:docs/text/text_multicolumns__drill.pdf.
  CF: 93.0219% -> 96.5135% (+3.4916pp;improved).
  SF: 66.6667% -> 58.3333% (-8.3333pp;regressed).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_multicolumns__elpais; PDF page1.
  Input:docs/text/text_multicolumns__elpais.pdf.
  CF: 70.0184% -> 71.8234% (+1.8051pp;improved).
  SF: 14.1807% -> 34.4013% (+20.2206pp;improved).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_multicolumns__energy2; PDF page1.
  Input:docs/text/text_multicolumns__energy2.pdf.
  CF: 85.4816% -> 93.6204% (+8.1388pp;improved).
  SF: 99.1071% -> 86.6071% (-12.5000pp;regressed).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_multicolumns__visa; PDF page1.
  Input:docs/text/text_multicolumns__visa.pdf.
  CF: 87.3084% -> 91.4557% (+4.1473pp;improved).
  SF: 0.0000% -> 83.3333% (+83.3333pp;improved).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_multicolumns__zh; PDF page1.
  Input:docs/text/text_multicolumns__zh.pdf.
  CF: 56.9613% -> 56.9824% (+0.0211pp;improved).
  SF: 12.6263% -> 12.6263% (+0.0000pp;unchanged).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_simple__4g; PDF page1.
  Input:docs/text/text_simple__4g.pdf.
  CF: 96.5070% -> 97.3875% (+0.8805pp;improved).
  SF: 82.3718% -> 82.3718% (+0.0000pp;unchanged).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_simple__delinea; PDF page1.
  Input:docs/text/text_simple__delinea.pdf.
  CF: 93.8443% -> 93.5589% (-0.2854pp;regressed).
  SF: 50.0000% -> 50.0000% (+0.0000pp;unchanged).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_simple__norman; PDF page1.
  Input:docs/text/text_simple__norman.pdf.
  CF: 60.1226% -> 59.5854% (-0.5372pp;regressed).
  SF: 64.5833% -> 85.4167% (+20.8333pp;improved).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_simple__otago; PDF page1.
  Input:docs/text/text_simple__otago.pdf.
  CF: 96.3256% -> 96.9312% (+0.6056pp;improved).
  SF: 80.3030% -> 80.3030% (+0.0000pp;unchanged).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_simple__wordForwords; PDF page1.
  Input:docs/text/text_simple__wordForwords.pdf.
  CF: 93.7837% -> 94.2387% (+0.4550pp;improved).
  SF: 96.8750% -> 96.8750% (+0.0000pp;unchanged).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

### approved corrections1,2,3,4,6,7+input change only

- CF: improved9,regressed4,unchanged493.
- SF: improved3,regressed3,unchanged450.

- text/text_dense__underline; PDF page1.
  Input:docs/text/text_dense__underline.pdf.
  CF: 42.7530% -> 47.8268% (+5.0738pp;improved).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_misc__2pages; PDF page1.
  Input:docs/text/text_misc__2pages.pdf.
  CF: 90.1375% -> 90.1309% (-0.0065pp;regressed).
  SF: 72.7941% -> 72.7941% (+0.0000pp;unchanged).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_misc__ikea3; PDF page1.
  Input:docs/text/text_misc__ikea3.pdf.
  CF: 77.3498% -> 76.7650% (-0.5848pp;regressed).
  SF: 46.5186% -> 35.0055% (-11.5132pp;regressed).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_multicolumns__drill; PDF page1.
  Input:docs/text/text_multicolumns__drill.pdf.
  CF: 93.0219% -> 96.5135% (+3.4916pp;improved).
  SF: 66.6667% -> 58.3333% (-8.3333pp;regressed).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_multicolumns__elpais; PDF page1.
  Input:docs/text/text_multicolumns__elpais.pdf.
  CF: 70.2900% -> 71.7834% (+1.4934pp;improved).
  SF: 14.1807% -> 34.4013% (+20.2206pp;improved).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_multicolumns__energy2; PDF page1.
  Input:docs/text/text_multicolumns__energy2.pdf.
  CF: 85.4816% -> 93.6204% (+8.1388pp;improved).
  SF: 99.1071% -> 86.6071% (-12.5000pp;regressed).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_multicolumns__visa; PDF page1.
  Input:docs/text/text_multicolumns__visa.pdf.
  CF: 87.3084% -> 91.4557% (+4.1473pp;improved).
  SF: 0.0000% -> 83.3333% (+83.3333pp;improved).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_multicolumns__zh; PDF page1.
  Input:docs/text/text_multicolumns__zh.pdf.
  CF: 56.9613% -> 56.9824% (+0.0211pp;improved).
  SF: 12.6263% -> 12.6263% (+0.0000pp;unchanged).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_simple__4g; PDF page1.
  Input:docs/text/text_simple__4g.pdf.
  CF: 96.5070% -> 97.3875% (+0.8805pp;improved).
  SF: 82.3718% -> 82.3718% (+0.0000pp;unchanged).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_simple__delinea; PDF page1.
  Input:docs/text/text_simple__delinea.pdf.
  CF: 93.8443% -> 93.5589% (-0.2854pp;regressed).
  SF: 50.0000% -> 50.0000% (+0.0000pp;unchanged).
  Selected:[]->[1];Rapid:[]->[1];Markdown changed:True.

- text/text_simple__norman; PDF page1.
  Input:docs/text/text_simple__norman.pdf.
  CF: 60.1226% -> 59.5854% (-0.5372pp;regressed).
  SF: 64.5833% -> 85.4167% (+20.8333pp;improved).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_simple__otago; PDF page1.
  Input:docs/text/text_simple__otago.pdf.
  CF: 96.3256% -> 96.9312% (+0.6056pp;improved).
  SF: 80.3030% -> 80.3030% (+0.0000pp;unchanged).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

- text/text_simple__wordForwords; PDF page1.
  Input:docs/text/text_simple__wordForwords.pdf.
  CF: 93.7837% -> 94.2387% (+0.4550pp;improved).
  SF: 96.8750% -> 96.8750% (+0.0000pp;unchanged).
  Selected:[1]->[];Rapid:[1]->[];Markdown changed:True.

## Original repository README

This is an empty package that is required by pymupdf-2.x, in order to avoid
a pip bug that can result in a broken installation when upgrading from
pymupdf-1.x to pymupdf-2.x.

[The pymupdf-2.x package now contains the 4llm code that used to be in
pymupdf4llm-1.x.]
