# Approved OCR integration: feature5 excluded

Branch: ocr/integration/all-features-20261031

Current active features:0,1,2,3,4,6,7. Feature5 Unicode damage recovery is excluded by explicit user decision. The independent feature5 branch is preserved for standalone review; it is not merged into this integration. The branch name remains stable.

Use the same branch in both repositories: https://github.com/veget-able/PyMuPDF/tree/ocr/integration/all-features-20261031 and https://github.com/veget-able/pymupdf4llm/tree/ocr/integration/all-features-20261031. Each is one final review commit directly on frozen main.

## Included branches

- 0: IMF2 ROI page selector.
  PyMuPDF: ocr/page-selector/imf2-roi-selector-20261027; source 5841ec7b94300e6b2442a19e901912b0bc6b9cba.
  pymupdf4llm: ocr/page-selector/imf2-roi-selector-20261027; source 508fe23fb37a081a868f819a0aa0418065b6d5ae.
- 1: Rotated text output.
  PyMuPDF: ocr/output-correction/rotated-text-20261030; source 1983f03d1fd422382523b542a2d741bf86ff6d96.
  pymupdf4llm: ocr/output-correction/rotated-text-20261030; source 9a96c303d6299bf1cb8a69db663e6a6f54ab69b2.
- 2: CropBox rotation correction.
  PyMuPDF: ocr/input-correction/cropbox-rotation-20261030; source d5dd452588f7004bae4324d1b9bedfb895ad23bd.
  pymupdf4llm: ocr/input-correction/cropbox-rotation-20261030; source 8e101462e424b19b9724195bb13428a949eb305c.
- 3: Verified Form BBox input preparation.
  PyMuPDF: ocr/input-correction/form-bbox-input-20261030; source 0f64bf02a7e3bdeef87413079edda927f5278e7e.
  pymupdf4llm: ocr/input-correction/form-bbox-input-20261030; source 96c7856975ec84f458e32c8ba6c42d6edc32fe3e.
- 4: Default True existing-OCR gate bypass.
  PyMuPDF: ocr/selection-policy/existing-ocr-gate-bypass-20261030; source 445ce9d25ae4a388c5dee50b58229b38080b5e57.
  pymupdf4llm: ocr/selection-policy/existing-ocr-gate-bypass-20261030; source 6094a091c009cc87aa2c2e53f18e132c548dea89.
- 6: Symbol damage selection/render/mapped replacement.
  PyMuPDF: ocr/stored-text-recovery/symbol-damage-recovery-20261030; source df8367743cc6d578fed0bd51c3f8cf2ad4c14fde.
  pymupdf4llm: ocr/stored-text-recovery/symbol-damage-recovery-20261030; source db33fccf0c1fc32b6d2735dff52cde2de9cbd299.
- 7: Writeback fonts and same-result mixed-font spacing.
  pymupdf4llm: ocr/writeback-correction/writeback-fonts-20261031; source e91486977eca9c35436f4c44575ae0186fc3c4af.
  PyMuPDF: ocr/writeback-correction/writeback-fonts-20261031; source fd5f686c8032b8c6d9f598134f169238d439d8d8.

## Excluded branch5 and investigation

Do not merge ocr/stored-text-recovery/unicode-damage-recovery-20261030 into the current profile. This exclusion removes its unconditional U+FFFD priority and activated special render fallback. The sources were recomposed from the remaining independent branches, including their original callbacks; the unicode_priority module and standalone feature5 tests are absent.

Main generic U+FFFD handling and feature6 passive Unicode inventory/marker-aware targets remain. Feature6 can still select dense U+FFFD under its distinct symbol criterion; that is not the excluded one-marker priority. Source-shared helper code never enables the missing priority module.

The independent feature5 README documented CF+0.2972pp on selector0 alone, with improvements in eller/att10k/grayson and a Hindi regression. In the historical full0-7 profile the first three remain recovered without5 through feature6; feature4 also recovers eller/grayson. Their Rapid input and Markdown are identical with/without5. Of23 Unicode-selected pages,9 fallback to symbol priority and12 to IMF2 ROI. paper2 has no REC output. Hindi is the only changed-quality case: CF34.0984% without5 versus33.1693% with5; its28 REC strings contain no Devanagari characters. The regression predates integration. The independent Unicode/renderer source files matched byte-for-byte; no omitted feature5 merge was found.

The old full0-7 CF82.6694292%/SF58.7090060% and its conditional feature contributions are historical evidence, not current profile scores. Their artifacts remain in OCR_ALL_FEATURES_INTEGRATION_20261031 and OCR_INTEGRATED_FEATURE_CONTRIBUTIONS_20261031. Current exclusion decision/audit: OCR_UNICODE_README_MERGE_AUDIT_20261031 and OCR_INTEGRATION_EXCLUDE_UNICODE_20261031.

## Policy and input contract

- Default use_ocr=True enables feature4 and symbol feature6. Explicit KEEP/DROP/FORCE and OFF/None retain inherited contracts. TODO: REPAIR naming/API remains deferred; no new REPAIR enum or to_markdown policy parameter is introduced.
- IMF2 ROI only returns page selection. It never crops or filters common Rapid DET/REC. Common normal-glyph culling and full-page OCR remain. No direct REC, white painting, OSD, fastText or model training is included.
- Feature3 requires explicit verified input preparation with examples/prepare_verified_ocr_input.py and examples/ocr_verified_input_repairs.json. It does not automatically repair arbitrary Form bounds in to_markdown. Source PDFs remain untouched.
- Current writeback fonts are finite. Additional fonts require confirmed actual glyph/writeback loss, reproduction and regression checks. Same-result ownership is in memory; reopening spacing and unsupported script combinations retain the documented limits.

## Current evaluation

Same507PDF/509pages per arm; CF506/SF476 supported456defined; official scorer8c63e84. RapidOCR3.10.0 PPv6small DET/REC; OCR150DPI inherited pixel cap; use_ocr=True,force_ocr=False,force_text=True,ocr_language=eng,render_html_tables=None. Two current source arms were freshly extracted; exact RGB/model/config recognition and exact full-output/case/scorer scores were verified before reuse.
- Fixed-main P2+ODM reference: CF79.6709088%/SF56.6573495%; preceding fresh remote validation.
- P2+ODM with approved corrections1,2,3,4,6,7: CF81.9120785%/SF57.9868410%; main delta+2.2411698/+1.3294915pp; selected/Rapid pages237/237.
- IMF2 ROI with approved corrections1,2,3,4,6,7: CF82.6712653%/SF58.7090060%; main delta+3.0003565/+2.0516565pp; selected/Rapid pages307/307.
- Same-correction selector effect IMF2 minus P2: CF+0.7591868pp/SF+0.7221650pp.
- Fresh public outputs1014; actual new DET/REC inputs0; verified recognition reuses544. Official workers0 new;1107 previous unique scores validated. No old Markdown output was substituted for the new public runs.
- Observed extraction validation wall sum291.29s; scoring/reaggregation5.37s. Four workers/startup/tracing and recognition/score reuse are included. These are validation costs, not independent product latency or speed rankings.
- Strict remaining-branch composition reproduces all507 Markdown outputs,509 decision tuples and Rapid RGB inputs of the previously scored without5 arm. New71-test integration profile passed; explicit absence of unconditional Unicode priority is covered. Prior76 tests belonged to the historical full0-7 profile.

## Reproduction

Use a compatible existing draft-2.0 native runtime (tested MuPDF1.28.5), paired source branches and Rapid3.10 models. Python-only source overlay; no native rebuild, wheel publication or package installation was performed.

python examples/build_source_overlay.py --core-repo /path/to/PyMuPDF --native-package /path/to/existing/pymupdf --output /new/path/ocr-runtime

PYTHONPATH=/new/path/ocr-runtime python examples/check_integrated_ocr.py --core-repo /path/to/PyMuPDF

PYTHONPATH=/new/path/ocr-runtime python examples/run_integrated_ocr.py input.pdf /new/path/output.md --input-rules examples/ocr_verified_input_repairs.json

Append --selector p2-odm only for the same-correction comparison adapter; this is not a new public API. The pinned local benchmark/protocol/environment/source hashes are under runs/OCR_INTEGRATION_EXCLUDE_UNICODE_20261031 in the pb_ocr research workspace.

## Complete current improvement/regression cases

Every changed document is listed below. CF/SF are document-level percentages; changes are percentage points. Single-page cases identify page1; multi-page aggregate scores are not attributed to one page. OCR activity is execution evidence, not proof that recognition is correct.

### Approved corrections1,2,3,4,6,7 versus main

Before:main; after:without5-p2.
- CF: improved57, regressed18, unchanged431.
- SF: improved19, regressed5, unchanged432.

- text/text_handwritting__contract; PDF page1.
  Input:docs/text/text_handwritting__contract.pdf.
  CF: 30.5309% -> 48.5736% (+18.0427pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_handwritting__signatures; PDF page1.
  Input:docs/text/text_handwritting__signatures.pdf.
  CF: 36.4002% -> 55.4796% (+19.0793pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__colorprofile; PDF page1.
  Input:docs/text/text_misc__colorprofile.pdf.
  CF: 38.0952% -> 73.9850% (+35.8898pp; improved).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__missing; PDF page1.
  Input:docs/text/text_misc__missing.pdf.
  CF: 78.4066% -> 86.0067% (+7.6001pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__redacted; PDF page1.
  Input:docs/text/text_misc__redacted.pdf.
  CF: 81.7151% -> 80.9245% (-0.7907pp; regressed).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__redacted3; PDF page1.
  Input:docs/text/text_misc__redacted3.pdf.
  CF: 87.2416% -> 79.1084% (-8.1332pp; regressed).
  SF: 48.3871% -> 0.0000% (-48.3871pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__10k2col; PDF page1.
  Input:docs/text/text_multicolumns__10k2col.pdf.
  CF: 91.3701% -> 91.9813% (+0.6112pp; improved).
  SF: 25.0000% -> 25.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multicolumns__2col; PDF page1.
  Input:docs/text/text_multicolumns__2col.pdf.
  CF: 0.0000% -> 79.3136% (+79.3136pp; improved).
  SF: 0.0000% -> 60.2617% (+60.2617pp; improved).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__2pages; PDF page1.
  Input:docs/text/text_multicolumns__2pages.pdf.
  CF: 0.0000% -> 90.5557% (+90.5557pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__3colP; PDF page1.
  Input:docs/text/text_multicolumns__3colP.pdf.
  CF: 46.8622% -> 46.6890% (-0.1733pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__3col_statment; PDF page1.
  Input:docs/text/text_multicolumns__3col_statment.pdf.
  CF: 80.9526% -> 81.1062% (+0.1536pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__3colsbeluga; PDF page1.
  Input:docs/text/text_multicolumns__3colsbeluga.pdf.
  CF: 96.2322% -> 96.5985% (+0.3663pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__4colimg; PDF page1.
  Input:docs/text/text_multicolumns__4colimg.pdf.
  CF: 0.0000% -> 97.8192% (+97.8192pp; improved).
  SF: 0.0000% -> 50.0000% (+50.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__analysis; PDF page1.
  Input:docs/text/text_multicolumns__analysis.pdf.
  CF: 87.3326% -> 89.9853% (+2.6527pp; improved).
  SF: 97.7528% -> 97.7528% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__battery; PDF page1.
  Input:docs/text/text_multicolumns__battery.pdf.
  CF: 99.2610% -> 98.9697% (-0.2913pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__coorp; PDF page1.
  Input:docs/text/text_multicolumns__coorp.pdf.
  CF: 87.0256% -> 87.2711% (+0.2455pp; improved).
  SF: 98.7805% -> 98.7805% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__dafta; PDF page1.
  Input:docs/text/text_multicolumns__dafta.pdf.
  CF: 91.2683% -> 91.1638% (-0.1045pp; regressed).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__elpais; PDF page1.
  Input:docs/text/text_multicolumns__elpais.pdf.
  CF: 70.0184% -> 70.2900% (+0.2716pp; improved).
  SF: 14.1807% -> 14.1807% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multicolumns__ethbottens; PDF page1.
  Input:docs/text/text_multicolumns__ethbottens.pdf.
  CF: 77.0392% -> 49.8925% (-27.1467pp; regressed).
  SF: 81.2500% -> 64.2045% (-17.0455pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__japanesefrench; PDF page1.
  Input:docs/text/text_multicolumns__japanesefrench.pdf.
  CF: 72.3819% -> 72.4608% (+0.0789pp; improved).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multicolumns__pap_2col; PDF page1.
  Input:docs/text/text_multicolumns__pap_2col.pdf.
  CF: 86.2349% -> 88.0655% (+1.8306pp; improved).
  SF: 79.1246% -> 79.1246% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__paper2; PDF page1.
  Input:docs/text/text_multicolumns__paper2.pdf.
  CF: 91.7413% -> 94.7084% (+2.9671pp; improved).
  SF: 29.1667% -> 29.1667% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__paperchem; PDF page1.
  Input:docs/text/text_multicolumns__paperchem.pdf.
  CF: 64.4459% -> 70.3823% (+5.9364pp; improved).
  SF: 36.1570% -> 44.3723% (+8.2153pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__pwc; PDF page1.
  Input:docs/text/text_multicolumns__pwc.pdf.
  CF: 35.5949% -> 55.5444% (+19.9495pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multilang__enfr; PDF page1.
  Input:docs/text/text_multilang__enfr.pdf.
  CF: 87.0844% -> 85.5368% (-1.5477pp; regressed).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__khazak; PDF page1.
  Input:docs/text/text_multilang__khazak.pdf.
  CF: 46.6742% -> 46.5003% (-0.1739pp; regressed).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multilang__mandarin4; PDF page1.
  Input:docs/text/text_multilang__mandarin4.pdf.
  CF: 26.7394% -> 63.0826% (+36.3432pp; improved).
  SF: 50.0000% -> 87.5000% (+37.5000pp; improved).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multilang__spanish; PDF page1.
  Input:docs/text/text_multilang__spanish.pdf.
  CF: 82.0444% -> 92.8244% (+10.7800pp; improved).
  SF: 83.4783% -> 83.4783% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multilang__spanish2; PDF page1.
  Input:docs/text/text_multilang__spanish2.pdf.
  CF: 93.6877% -> 95.3700% (+1.6824pp; improved).
  SF: 25.0000% -> 25.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multilang__tegulu; PDF page1.
  Input:docs/text/text_multilang__tegulu.pdf.
  CF: 32.5427% -> 32.6554% (+0.1126pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multilang__turkish; PDF page1.
  Input:docs/text/text_multilang__turkish.pdf.
  CF: 89.3778% -> 90.5091% (+1.1313pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multilang__ukrainian; PDF page1.
  Input:docs/text/text_multilang__ukrainian.pdf.
  CF: 93.1378% -> 95.1430% (+2.0052pp; improved).
  SF: 88.0208% -> 88.0208% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_ocr__069; PDF page1.
  Input:docs/text/text_ocr__069.pdf.
  CF: 36.1432% -> 79.2167% (+43.0735pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__2pages; PDF page1.
  Input:docs/text/text_ocr__2pages.pdf.
  CF: 59.0716% -> 85.0408% (+25.9692pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__9; PDF page1.
  Input:docs/text/text_ocr__9.pdf.
  CF: 62.1733% -> 64.2655% (+2.0922pp; improved).
  SF: 0.0000% -> 8.3333% (+8.3333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__File0021; PDF page1.
  Input:docs/text/text_ocr__File0021.pdf.
  CF: 56.4770% -> 74.0143% (+17.5373pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__abstract; PDF page1.
  Input:docs/text/text_ocr__abstract.pdf.
  CF: 97.5188% -> 85.2618% (-12.2570pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__admnh; PDF page1.
  Input:docs/text/text_ocr__admnh.pdf.
  CF: 83.9142% -> 86.3518% (+2.4376pp; improved).
  SF: 81.2500% -> 81.2500% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__archive; PDF page1.
  Input:docs/text/text_ocr__archive.pdf.
  CF: 39.3527% -> 50.2913% (+10.9386pp; improved).
  SF: 66.6667% -> 75.0000% (+8.3333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__attendence; PDF page1.
  Input:docs/text/text_ocr__attendence.pdf.
  CF: 32.6896% -> 78.7769% (+46.0873pp; improved).
  SF: 0.0000% -> 8.3333% (+8.3333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__blurry; PDF page1.
  Input:docs/text/text_ocr__blurry.pdf.
  CF: 39.0605% -> 70.9002% (+31.8397pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__blurry2; PDF page1.
  Input:docs/text/text_ocr__blurry2.pdf.
  CF: 33.7785% -> 50.8697% (+17.0912pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__bold; PDF page1.
  Input:docs/text/text_ocr__bold.pdf.
  CF: 76.4630% -> 70.9869% (-5.4761pp; regressed).
  SF: 87.5000% -> 0.0000% (-87.5000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__cert_of_assistanvce; PDF page1.
  Input:docs/text/text_ocr__cert_of_assistanvce.pdf.
  CF: 37.3329% -> 56.8890% (+19.5561pp; improved).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__christmass; PDF page1.
  Input:docs/text/text_ocr__christmass.pdf.
  CF: 96.0868% -> 95.1979% (-0.8888pp; regressed).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__code; PDF page1.
  Input:docs/text/text_ocr__code.pdf.
  CF: 36.1675% -> 73.8302% (+37.6627pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__cyber; PDF page1.
  Input:docs/text/text_ocr__cyber.pdf.
  CF: 87.3672% -> 92.3587% (+4.9915pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__das; PDF page1.
  Input:docs/text/text_ocr__das.pdf.
  CF: 38.7711% -> 46.0062% (+7.2350pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__data; PDF page1.
  Input:docs/text/text_ocr__data.pdf.
  CF: 96.5644% -> 95.9161% (-0.6483pp; regressed).
  SF: 20.8333% -> 91.6667% (+70.8333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__diseeas; PDF page1.
  Input:docs/text/text_ocr__diseeas.pdf.
  CF: 95.9877% -> 80.6396% (-15.3481pp; regressed).
  SF: 9.8214% -> 88.0952% (+78.2738pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__eller; PDF page1.
  Input:docs/text/text_ocr__eller.pdf.
  CF: 21.3800% -> 91.8295% (+70.4496pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__fpl; PDF page1.
  Input:docs/text/text_ocr__fpl.pdf.
  CF: 72.2005% -> 92.5914% (+20.3909pp; improved).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__glitch; PDF page1.
  Input:docs/text/text_ocr__glitch.pdf.
  CF: 75.9144% -> 78.3769% (+2.4625pp; improved).
  SF: 13.0682% -> 13.0682% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_ocr__inr; PDF page1.
  Input:docs/text/text_ocr__inr.pdf.
  CF: 66.3401% -> 94.7199% (+28.3798pp; improved).
  SF: 16.6667% -> 52.3810% (+35.7143pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__letter; PDF page1.
  Input:docs/text/text_ocr__letter.pdf.
  CF: 46.6693% -> 76.5078% (+29.8385pp; improved).
  SF: 0.0000% -> 78.4903% (+78.4903pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__orientedtex; PDF page1.
  Input:docs/text/text_ocr__orientedtex.pdf.
  CF: 34.8214% -> 47.3520% (+12.5305pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__p4013; PDF page1.
  Input:docs/text/text_ocr__p4013.pdf.
  CF: 92.1540% -> 90.8797% (-1.2742pp; regressed).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__parent; PDF page1.
  Input:docs/text/text_ocr__parent.pdf.
  CF: 98.1859% -> 99.0930% (+0.9070pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__pol; PDF page1.
  Input:docs/text/text_ocr__pol.pdf.
  CF: 52.9425% -> 81.6009% (+28.6584pp; improved).
  SF: 0.0000% -> 2.7778% (+2.7778pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__polishlike; PDF page1.
  Input:docs/text/text_ocr__polishlike.pdf.
  CF: 35.6470% -> 88.9227% (+53.2757pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__pretest; PDF page1.
  Input:docs/text/text_ocr__pretest.pdf.
  CF: 93.0461% -> 79.6841% (-13.3620pp; regressed).
  SF: 100.0000% -> 0.0000% (-100.0000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__ref; PDF page1.
  Input:docs/text/text_ocr__ref.pdf.
  CF: 72.1914% -> 72.1982% (+0.0067pp; improved).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_ocr__routier; PDF page1.
  Input:docs/text/text_ocr__routier.pdf.
  CF: 80.8308% -> 84.6028% (+3.7720pp; improved).
  SF: 0.0000% -> 38.3333% (+38.3333pp; improved).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_ocr__scanbook; PDF page1.
  Input:docs/text/text_ocr__scanbook.pdf.
  CF: 0.0000% -> 71.4371% (+71.4371pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__secretaria; PDF page1.
  Input:docs/text/text_ocr__secretaria.pdf.
  CF: 68.1164% -> 92.7423% (+24.6259pp; improved).
  SF: 15.6250% -> 21.8750% (+6.2500pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__skew; PDF page1.
  Input:docs/text/text_ocr__skew.pdf.
  CF: 37.7354% -> 87.7469% (+50.0116pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__sup; PDF page1.
  Input:docs/text/text_ocr__sup.pdf.
  CF: 58.3444% -> 79.7251% (+21.3807pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__tata; PDF page1.
  Input:docs/text/text_ocr__tata.pdf.
  CF: 40.7096% -> 78.4876% (+37.7780pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__tridimensional; PDF page1.
  Input:docs/text/text_ocr__tridimensional.pdf.
  CF: 76.1507% -> 76.8015% (+0.6508pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__yellowtype; PDF page1.
  Input:docs/text/text_ocr__yellowtype.pdf.
  CF: 91.0155% -> 87.9665% (-3.0490pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__zaposlitve; PDF page1.
  Input:docs/text/text_ocr__zaposlitve.pdf.
  CF: 53.9199% -> 55.7589% (+1.8390pp; improved).
  SF: 41.4969% -> 0.0000% (-41.4969pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__Preview; PDF page1.
  Input:docs/text/text_simple__Preview.pdf.
  CF: 97.5813% -> 96.9836% (-0.5976pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_simple__att10k; PDF page1.
  Input:docs/text/text_simple__att10k.pdf.
  CF: 62.4997% -> 88.8516% (+26.3519pp; improved).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_simple__grayson; PDF page1.
  Input:docs/text/text_simple__grayson.pdf.
  CF: 38.0952% -> 76.9421% (+38.8468pp; improved).
  SF: 0.0000% -> 9.0278% (+9.0278pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__listwarnings; PDF page1.
  Input:docs/text/text_simple__listwarnings.pdf.
  CF: 98.6875% -> 98.4581% (-0.2295pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

### Approved integration0,1,2,3,4,6,7 versus main

Before:main; after:without5-imf2.
- CF: improved76, regressed37, unchanged393.
- SF: improved33, regressed12, unchanged411.

- text/text_dense__leaflet; PDF page1.
  Input:docs/text/text_dense__leaflet.pdf.
  CF: 92.8562% -> 91.8862% (-0.9700pp; regressed).
  SF: 60.6838% -> 68.2234% (+7.5397pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_dense__underline; PDF page1.
  Input:docs/text/text_dense__underline.pdf.
  CF: 42.7530% -> 47.8268% (+5.0738pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_handwritting__contract; PDF page1.
  Input:docs/text/text_handwritting__contract.pdf.
  CF: 30.5309% -> 48.5736% (+18.0427pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_handwritting__jp; PDF page1.
  Input:docs/text/text_handwritting__jp.pdf.
  CF: 0.0000% -> 27.0721% (+27.0721pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_handwritting__signatures; PDF page1.
  Input:docs/text/text_handwritting__signatures.pdf.
  CF: 36.4002% -> 55.4796% (+19.0793pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__colorprofile; PDF page1.
  Input:docs/text/text_misc__colorprofile.pdf.
  CF: 38.0952% -> 73.9850% (+35.8898pp; improved).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__gridofimages; PDF page1.
  Input:docs/text/text_misc__gridofimages.pdf.
  CF: 65.9550% -> 65.3347% (-0.6203pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__ikea3; PDF page1.
  Input:docs/text/text_misc__ikea3.pdf.
  CF: 77.3498% -> 76.7650% (-0.5848pp; regressed).
  SF: 46.5186% -> 35.0055% (-11.5132pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__json; PDF page1.
  Input:docs/text/text_misc__json.pdf.
  CF: 89.1242% -> 88.8427% (-0.2814pp; regressed).
  SF: 83.3333% -> 83.3333% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__redacted; PDF page1.
  Input:docs/text/text_misc__redacted.pdf.
  CF: 81.7151% -> 80.9245% (-0.7907pp; regressed).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__redacted3; PDF page1.
  Input:docs/text/text_misc__redacted3.pdf.
  CF: 87.2416% -> 79.1084% (-8.1332pp; regressed).
  SF: 48.3871% -> 0.0000% (-48.3871pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__10k2col; PDF page1.
  Input:docs/text/text_multicolumns__10k2col.pdf.
  CF: 91.3701% -> 91.9813% (+0.6112pp; improved).
  SF: 25.0000% -> 25.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multicolumns__2col; PDF page1.
  Input:docs/text/text_multicolumns__2col.pdf.
  CF: 0.0000% -> 79.3136% (+79.3136pp; improved).
  SF: 0.0000% -> 60.2617% (+60.2617pp; improved).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__2col_fund_summary; PDF page1.
  Input:docs/text/text_multicolumns__2col_fund_summary.pdf.
  CF: 99.7445% -> 99.2857% (-0.4587pp; regressed).
  SF: 100.0000% -> 90.0000% (-10.0000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__2colrep; PDF page1.
  Input:docs/text/text_multicolumns__2colrep.pdf.
  CF: 97.2987% -> 97.0520% (-0.2467pp; regressed).
  SF: 36.6071% -> 36.6071% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__2pages; PDF page1.
  Input:docs/text/text_multicolumns__2pages.pdf.
  CF: 0.0000% -> 90.5557% (+90.5557pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__2x; PDF page1.
  Input:docs/text/text_multicolumns__2x.pdf.
  CF: 89.9595% -> 92.4154% (+2.4559pp; improved).
  SF: 98.7421% -> 61.2421% (-37.5000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__3colP; PDF page1.
  Input:docs/text/text_multicolumns__3colP.pdf.
  CF: 46.8622% -> 46.6890% (-0.1733pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__3col_statment; PDF page1.
  Input:docs/text/text_multicolumns__3col_statment.pdf.
  CF: 80.9526% -> 83.5753% (+2.6227pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__3colpres; PDF page1.
  Input:docs/text/text_multicolumns__3colpres.pdf.
  CF: 94.6715% -> 88.4797% (-6.1917pp; regressed).
  SF: 62.5000% -> 62.5000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__4colimg; PDF page1.
  Input:docs/text/text_multicolumns__4colimg.pdf.
  CF: 0.0000% -> 97.8192% (+97.8192pp; improved).
  SF: 0.0000% -> 50.0000% (+50.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__analysis; PDF page1.
  Input:docs/text/text_multicolumns__analysis.pdf.
  CF: 87.3326% -> 89.9853% (+2.6527pp; improved).
  SF: 97.7528% -> 97.7528% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__article; PDF page1.
  Input:docs/text/text_multicolumns__article.pdf.
  CF: 90.9122% -> 90.8697% (-0.0425pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__battery; PDF page1.
  Input:docs/text/text_multicolumns__battery.pdf.
  CF: 99.2610% -> 98.9697% (-0.2913pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__coorp; PDF page1.
  Input:docs/text/text_multicolumns__coorp.pdf.
  CF: 87.0256% -> 96.3423% (+9.3167pp; improved).
  SF: 98.7805% -> 98.7805% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__dafta; PDF page1.
  Input:docs/text/text_multicolumns__dafta.pdf.
  CF: 91.2683% -> 92.3889% (+1.1206pp; improved).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__drill; PDF page1.
  Input:docs/text/text_multicolumns__drill.pdf.
  CF: 93.0219% -> 96.5135% (+3.4916pp; improved).
  SF: 66.6667% -> 58.3333% (-8.3333pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__elpais; PDF page1.
  Input:docs/text/text_multicolumns__elpais.pdf.
  CF: 70.0184% -> 70.2900% (+0.2716pp; improved).
  SF: 14.1807% -> 14.1807% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multicolumns__energy2; PDF page1.
  Input:docs/text/text_multicolumns__energy2.pdf.
  CF: 85.4816% -> 93.6204% (+8.1388pp; improved).
  SF: 99.1071% -> 86.6071% (-12.5000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__esd_end; PDF page1.
  Input:docs/text/text_multicolumns__esd_end.pdf.
  CF: 84.0375% -> 83.6335% (-0.4040pp; regressed).
  SF: 47.9167% -> 0.0000% (-47.9167pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__esg_whitespace; PDF page1.
  Input:docs/text/text_multicolumns__esg_whitespace.pdf.
  CF: 97.6057% -> 97.0178% (-0.5879pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__forword2cols; PDF page1.
  Input:docs/text/text_multicolumns__forword2cols.pdf.
  CF: 96.9225% -> 88.4971% (-8.4254pp; regressed).
  SF: 100.0000% -> 50.0000% (-50.0000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__heirloom; PDF page1.
  Input:docs/text/text_multicolumns__heirloom.pdf.
  CF: 38.0952% -> 49.1258% (+11.0305pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__japanesefrench; PDF page1.
  Input:docs/text/text_multicolumns__japanesefrench.pdf.
  CF: 72.3819% -> 72.4608% (+0.0789pp; improved).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multicolumns__pap_2col; PDF page1.
  Input:docs/text/text_multicolumns__pap_2col.pdf.
  CF: 86.2349% -> 88.0655% (+1.8306pp; improved).
  SF: 79.1246% -> 79.1246% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__paper2; PDF page1.
  Input:docs/text/text_multicolumns__paper2.pdf.
  CF: 91.7413% -> 94.7084% (+2.9671pp; improved).
  SF: 29.1667% -> 29.1667% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_multicolumns__pwc; PDF page1.
  Input:docs/text/text_multicolumns__pwc.pdf.
  CF: 35.5949% -> 55.5444% (+19.9495pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multicolumns__sbi; PDF page1.
  Input:docs/text/text_multicolumns__sbi.pdf.
  CF: 95.7029% -> 95.6861% (-0.0168pp; regressed).
  SF: 41.6667% -> 41.6667% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__tableOfContent8col; PDF page1.
  Input:docs/text/text_multicolumns__tableOfContent8col.pdf.
  CF: 62.0923% -> 60.3025% (-1.7898pp; regressed).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__tableinmiddle2cols; PDF page1.
  Input:docs/text/text_multicolumns__tableinmiddle2cols.pdf.
  CF: 57.7184% -> 82.5286% (+24.8102pp; improved).
  SF: 0.0000% -> 11.2500% (+11.2500pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__visa; PDF page1.
  Input:docs/text/text_multicolumns__visa.pdf.
  CF: 87.3084% -> 91.4557% (+4.1473pp; improved).
  SF: 0.0000% -> 83.3333% (+83.3333pp; improved).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_multicolumns__waterfal; PDF page1.
  Input:docs/text/text_multicolumns__waterfal.pdf.
  CF: 94.3911% -> 79.6930% (-14.6981pp; regressed).
  SF: 68.3333% -> 68.3333% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__weeds; PDF page1.
  Input:docs/text/text_multicolumns__weeds.pdf.
  CF: 99.2353% -> 99.0645% (-0.1708pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__cnnm; PDF page1.
  Input:docs/text/text_multilang__cnnm.pdf.
  CF: 57.1429% -> 65.9864% (+8.8435pp; improved).
  SF: 0.0000% -> 41.6667% (+41.6667pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__greek; PDF page1.
  Input:docs/text/text_multilang__greek.pdf.
  CF: 87.7175% -> 95.9455% (+8.2279pp; improved).
  SF: 25.0000% -> 83.3333% (+58.3333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__japanese5; PDF page1.
  Input:docs/text/text_multilang__japanese5.pdf.
  CF: 25.2019% -> 25.1959% (-0.0060pp; regressed).
  SF: 44.9597% -> 47.8414% (+2.8817pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__kannada; PDF page1.
  Input:docs/text/text_multilang__kannada.pdf.
  CF: 30.3700% -> 30.6963% (+0.3263pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__khazak; PDF page1.
  Input:docs/text/text_multilang__khazak.pdf.
  CF: 46.6742% -> 46.5003% (-0.1739pp; regressed).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multilang__mandarin4; PDF page1.
  Input:docs/text/text_multilang__mandarin4.pdf.
  CF: 26.7394% -> 63.0826% (+36.3432pp; improved).
  SF: 50.0000% -> 87.5000% (+37.5000pp; improved).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multilang__romanian; PDF page1.
  Input:docs/text/text_multilang__romanian.pdf.
  CF: 84.5501% -> 85.4180% (+0.8679pp; improved).
  SF: 91.8681% -> 87.0879% (-4.7802pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__spanish; PDF page1.
  Input:docs/text/text_multilang__spanish.pdf.
  CF: 82.0444% -> 92.5283% (+10.4839pp; improved).
  SF: 83.4783% -> 83.4783% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__spanish2; PDF page1.
  Input:docs/text/text_multilang__spanish2.pdf.
  CF: 93.6877% -> 95.3700% (+1.6824pp; improved).
  SF: 25.0000% -> 37.5000% (+12.5000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__tegulu; PDF page1.
  Input:docs/text/text_multilang__tegulu.pdf.
  CF: 32.5427% -> 32.6554% (+0.1126pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_multilang__turkish; PDF page1.
  Input:docs/text/text_multilang__turkish.pdf.
  CF: 89.3778% -> 91.6040% (+2.2262pp; improved).
  SF: 0.0000% -> 41.6667% (+41.6667pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__ukrainian; PDF page1.
  Input:docs/text/text_multilang__ukrainian.pdf.
  CF: 93.1378% -> 94.7894% (+1.6516pp; improved).
  SF: 88.0208% -> 88.0208% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__069; PDF page1.
  Input:docs/text/text_ocr__069.pdf.
  CF: 36.1432% -> 79.2167% (+43.0735pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__2pages; PDF page1.
  Input:docs/text/text_ocr__2pages.pdf.
  CF: 59.0716% -> 85.0408% (+25.9692pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__9; PDF page1.
  Input:docs/text/text_ocr__9.pdf.
  CF: 62.1733% -> 64.2655% (+2.0922pp; improved).
  SF: 0.0000% -> 8.3333% (+8.3333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__File0021; PDF page1.
  Input:docs/text/text_ocr__File0021.pdf.
  CF: 56.4770% -> 74.0143% (+17.5373pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__archive; PDF page1.
  Input:docs/text/text_ocr__archive.pdf.
  CF: 39.3527% -> 50.2913% (+10.9386pp; improved).
  SF: 66.6667% -> 75.0000% (+8.3333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__attendence; PDF page1.
  Input:docs/text/text_ocr__attendence.pdf.
  CF: 32.6896% -> 78.7769% (+46.0873pp; improved).
  SF: 0.0000% -> 8.3333% (+8.3333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__blurry; PDF page1.
  Input:docs/text/text_ocr__blurry.pdf.
  CF: 39.0605% -> 70.9002% (+31.8397pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__blurry2; PDF page1.
  Input:docs/text/text_ocr__blurry2.pdf.
  CF: 33.7785% -> 50.8697% (+17.0912pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__bold; PDF page1.
  Input:docs/text/text_ocr__bold.pdf.
  CF: 76.4630% -> 70.9869% (-5.4761pp; regressed).
  SF: 87.5000% -> 0.0000% (-87.5000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__cert_of_assistanvce; PDF page1.
  Input:docs/text/text_ocr__cert_of_assistanvce.pdf.
  CF: 37.3329% -> 56.8890% (+19.5561pp; improved).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__christmass; PDF page1.
  Input:docs/text/text_ocr__christmass.pdf.
  CF: 96.0868% -> 95.1979% (-0.8888pp; regressed).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__code; PDF page1.
  Input:docs/text/text_ocr__code.pdf.
  CF: 36.1675% -> 73.8302% (+37.6627pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__cyber; PDF page1.
  Input:docs/text/text_ocr__cyber.pdf.
  CF: 87.3672% -> 92.3587% (+4.9915pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__data; PDF page1.
  Input:docs/text/text_ocr__data.pdf.
  CF: 96.5644% -> 95.9161% (-0.6483pp; regressed).
  SF: 20.8333% -> 91.6667% (+70.8333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__eller; PDF page1.
  Input:docs/text/text_ocr__eller.pdf.
  CF: 21.3800% -> 91.8295% (+70.4496pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__fpl; PDF page1.
  Input:docs/text/text_ocr__fpl.pdf.
  CF: 72.2005% -> 92.5914% (+20.3909pp; improved).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__glitch; PDF page1.
  Input:docs/text/text_ocr__glitch.pdf.
  CF: 75.9144% -> 78.3769% (+2.4625pp; improved).
  SF: 13.0682% -> 13.0682% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_ocr__inr; PDF page1.
  Input:docs/text/text_ocr__inr.pdf.
  CF: 66.3401% -> 94.7199% (+28.3798pp; improved).
  SF: 16.6667% -> 52.3810% (+35.7143pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__klein; PDF page1.
  Input:docs/text/text_ocr__klein.pdf.
  CF: 45.0749% -> 60.3002% (+15.2253pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__letter; PDF page1.
  Input:docs/text/text_ocr__letter.pdf.
  CF: 46.6693% -> 76.5078% (+29.8385pp; improved).
  SF: 0.0000% -> 78.4903% (+78.4903pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__mag; PDF page1.
  Input:docs/text/text_ocr__mag.pdf.
  CF: 0.0000% -> 73.3805% (+73.3805pp; improved).
  SF: 0.0000% -> 26.3158% (+26.3158pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__orientedtex; PDF page1.
  Input:docs/text/text_ocr__orientedtex.pdf.
  CF: 34.8214% -> 47.3520% (+12.5305pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__p4013; PDF page1.
  Input:docs/text/text_ocr__p4013.pdf.
  CF: 92.1540% -> 90.8797% (-1.2742pp; regressed).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__parent; PDF page1.
  Input:docs/text/text_ocr__parent.pdf.
  CF: 98.1859% -> 99.0930% (+0.9070pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__pol; PDF page1.
  Input:docs/text/text_ocr__pol.pdf.
  CF: 52.9425% -> 81.6009% (+28.6584pp; improved).
  SF: 0.0000% -> 2.7778% (+2.7778pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__polishlike; PDF page1.
  Input:docs/text/text_ocr__polishlike.pdf.
  CF: 35.6470% -> 88.9227% (+53.2757pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__pretest; PDF page1.
  Input:docs/text/text_ocr__pretest.pdf.
  CF: 93.0461% -> 79.6841% (-13.3620pp; regressed).
  SF: 100.0000% -> 0.0000% (-100.0000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__ref; PDF page1.
  Input:docs/text/text_ocr__ref.pdf.
  CF: 72.1914% -> 72.1982% (+0.0067pp; improved).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_ocr__routier; PDF page1.
  Input:docs/text/text_ocr__routier.pdf.
  CF: 80.8308% -> 84.6028% (+3.7720pp; improved).
  SF: 0.0000% -> 38.3333% (+38.3333pp; improved).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_ocr__scanbook; PDF page1.
  Input:docs/text/text_ocr__scanbook.pdf.
  CF: 0.0000% -> 71.4371% (+71.4371pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__scaninfile; PDF page1.
  Input:docs/text/text_ocr__scaninfile.pdf.
  CF: 0.0000% -> 76.1763% (+76.1763pp; improved).
  SF: 0.0000% -> 40.2778% (+40.2778pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__secretaria; PDF page1.
  Input:docs/text/text_ocr__secretaria.pdf.
  CF: 68.1164% -> 92.7423% (+24.6259pp; improved).
  SF: 15.6250% -> 21.8750% (+6.2500pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__skew; PDF page1.
  Input:docs/text/text_ocr__skew.pdf.
  CF: 37.7354% -> 87.7469% (+50.0116pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__sup; PDF page1.
  Input:docs/text/text_ocr__sup.pdf.
  CF: 58.3444% -> 79.7251% (+21.3807pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__tata; PDF page1.
  Input:docs/text/text_ocr__tata.pdf.
  CF: 40.7096% -> 78.4876% (+37.7780pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__tridimensional; PDF page1.
  Input:docs/text/text_ocr__tridimensional.pdf.
  CF: 76.1507% -> 76.8015% (+0.6508pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__yellowtype; PDF page1.
  Input:docs/text/text_ocr__yellowtype.pdf.
  CF: 91.0155% -> 87.9665% (-3.0490pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__zaposlitve; PDF page1.
  Input:docs/text/text_ocr__zaposlitve.pdf.
  CF: 53.9199% -> 55.7589% (+1.8390pp; improved).
  SF: 41.4969% -> 0.0000% (-41.4969pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__4g; PDF page1.
  Input:docs/text/text_simple__4g.pdf.
  CF: 96.5070% -> 97.3875% (+0.8805pp; improved).
  SF: 82.3718% -> 82.3718% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__Preview; PDF page1.
  Input:docs/text/text_simple__Preview.pdf.
  CF: 97.5813% -> 96.9836% (-0.5976pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_simple__adminplan; PDF page1.
  Input:docs/text/text_simple__adminplan.pdf.
  CF: 87.0748% -> 98.6395% (+11.5646pp; improved).
  SF: 0.0000% -> 66.6667% (+66.6667pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__att10k; PDF page1.
  Input:docs/text/text_simple__att10k.pdf.
  CF: 62.4997% -> 88.8516% (+26.3519pp; improved).
  Selected pages:[1]->[1]; Rapid pages:[1]->[1]; Markdown changed:True.

- text/text_simple__bottens; PDF page1.
  Input:docs/text/text_simple__bottens.pdf.
  CF: 99.0257% -> 98.6575% (-0.3682pp; regressed).
  SF: 93.3036% -> 93.3036% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__delinea; PDF page1.
  Input:docs/text/text_simple__delinea.pdf.
  CF: 93.8443% -> 93.5589% (-0.2854pp; regressed).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__finra; PDF page1.
  Input:docs/text/text_simple__finra.pdf.
  CF: 41.9132% -> 72.2982% (+30.3850pp; improved).
  SF: 0.0000% -> 22.7273% (+22.7273pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__grayson; PDF page1.
  Input:docs/text/text_simple__grayson.pdf.
  CF: 38.0952% -> 76.9421% (+38.8468pp; improved).
  SF: 0.0000% -> 9.0278% (+9.0278pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__green; PDF page1.
  Input:docs/text/text_simple__green.pdf.
  CF: 66.5353% -> 66.2319% (-0.3034pp; regressed).
  SF: 50.0000% -> 62.5000% (+12.5000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__hex; PDF page1.
  Input:docs/text/text_simple__hex.pdf.
  CF: 88.2647% -> 88.0633% (-0.2014pp; regressed).
  SF: 83.3333% -> 83.3333% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__iehp; PDF page1.
  Input:docs/text/text_simple__iehp.pdf.
  CF: 94.0494% -> 93.5497% (-0.4997pp; regressed).
  SF: 75.0000% -> 75.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__italicsummary; PDF page1.
  Input:docs/text/text_simple__italicsummary.pdf.
  CF: 97.6190% -> 99.2872% (+1.6682pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__landfill; PDF page1.
  Input:docs/text/text_simple__landfill.pdf.
  CF: 38.0952% -> 80.9001% (+42.8048pp; improved).
  SF: 0.0000% -> 32.8020% (+32.8020pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__listwarnings; PDF page1.
  Input:docs/text/text_simple__listwarnings.pdf.
  CF: 98.6875% -> 98.4581% (-0.2295pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[]; Rapid pages:[]->[]; Markdown changed:True.

- text/text_simple__marknotTable; PDF page1.
  Input:docs/text/text_simple__marknotTable.pdf.
  CF: 97.7013% -> 97.2568% (-0.4444pp; regressed).
  SF: 84.4828% -> 84.4828% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__redirect; PDF page1.
  Input:docs/text/text_simple__redirect.pdf.
  CF: 96.0317% -> 94.7036% (-1.3282pp; regressed).
  SF: 95.4545% -> 95.4545% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__references; PDF page1.
  Input:docs/text/text_simple__references.pdf.
  CF: 96.4334% -> 96.0960% (-0.3374pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__state; PDF page1.
  Input:docs/text/text_simple__state.pdf.
  CF: 87.7484% -> 92.2078% (+4.4594pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__tagblatt; PDF page1.
  Input:docs/text/text_simple__tagblatt.pdf.
  CF: 97.4889% -> 97.5427% (+0.0538pp; improved).
  SF: 79.1667% -> 100.0000% (+20.8333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_sparse__conductivity; PDF page1.
  Input:docs/text/text_sparse__conductivity.pdf.
  CF: 60.9524% -> 77.3449% (+16.3925pp; improved).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

### Selector comparison on identical approved corrections

Before:without5-p2; after:without5-imf2.
- CF: improved31, regressed31, unchanged444.
- SF: improved17, regressed10, unchanged429.

- text/text_dense__leaflet; PDF page1.
  Input:docs/text/text_dense__leaflet.pdf.
  CF: 92.8562% -> 91.8862% (-0.9700pp; regressed).
  SF: 60.6838% -> 68.2234% (+7.5397pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_dense__underline; PDF page1.
  Input:docs/text/text_dense__underline.pdf.
  CF: 42.7530% -> 47.8268% (+5.0738pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_handwritting__jp; PDF page1.
  Input:docs/text/text_handwritting__jp.pdf.
  CF: 0.0000% -> 27.0721% (+27.0721pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__gridofimages; PDF page1.
  Input:docs/text/text_misc__gridofimages.pdf.
  CF: 65.9550% -> 65.3347% (-0.6203pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__ikea3; PDF page1.
  Input:docs/text/text_misc__ikea3.pdf.
  CF: 77.3498% -> 76.7650% (-0.5848pp; regressed).
  SF: 46.5186% -> 35.0055% (-11.5132pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__json; PDF page1.
  Input:docs/text/text_misc__json.pdf.
  CF: 89.1242% -> 88.8427% (-0.2814pp; regressed).
  SF: 83.3333% -> 83.3333% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_misc__missing; PDF page1.
  Input:docs/text/text_misc__missing.pdf.
  CF: 86.0067% -> 78.4066% (-7.6001pp; regressed).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_multicolumns__2col_fund_summary; PDF page1.
  Input:docs/text/text_multicolumns__2col_fund_summary.pdf.
  CF: 99.7445% -> 99.2857% (-0.4587pp; regressed).
  SF: 100.0000% -> 90.0000% (-10.0000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__2colrep; PDF page1.
  Input:docs/text/text_multicolumns__2colrep.pdf.
  CF: 97.2987% -> 97.0520% (-0.2467pp; regressed).
  SF: 36.6071% -> 36.6071% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__2x; PDF page1.
  Input:docs/text/text_multicolumns__2x.pdf.
  CF: 89.9595% -> 92.4154% (+2.4559pp; improved).
  SF: 98.7421% -> 61.2421% (-37.5000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__3col_statment; PDF page1.
  Input:docs/text/text_multicolumns__3col_statment.pdf.
  CF: 81.1062% -> 83.5753% (+2.4691pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__3colpres; PDF page1.
  Input:docs/text/text_multicolumns__3colpres.pdf.
  CF: 94.6715% -> 88.4797% (-6.1917pp; regressed).
  SF: 62.5000% -> 62.5000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__3colsbeluga; PDF page1.
  Input:docs/text/text_multicolumns__3colsbeluga.pdf.
  CF: 96.5985% -> 96.2322% (-0.3663pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_multicolumns__article; PDF page1.
  Input:docs/text/text_multicolumns__article.pdf.
  CF: 90.9122% -> 90.8697% (-0.0425pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__coorp; PDF page1.
  Input:docs/text/text_multicolumns__coorp.pdf.
  CF: 87.2711% -> 96.3423% (+9.0712pp; improved).
  SF: 98.7805% -> 98.7805% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__dafta; PDF page1.
  Input:docs/text/text_multicolumns__dafta.pdf.
  CF: 91.1638% -> 92.3889% (+1.2251pp; improved).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__drill; PDF page1.
  Input:docs/text/text_multicolumns__drill.pdf.
  CF: 93.0219% -> 96.5135% (+3.4916pp; improved).
  SF: 66.6667% -> 58.3333% (-8.3333pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__energy2; PDF page1.
  Input:docs/text/text_multicolumns__energy2.pdf.
  CF: 85.4816% -> 93.6204% (+8.1388pp; improved).
  SF: 99.1071% -> 86.6071% (-12.5000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__esd_end; PDF page1.
  Input:docs/text/text_multicolumns__esd_end.pdf.
  CF: 84.0375% -> 83.6335% (-0.4040pp; regressed).
  SF: 47.9167% -> 0.0000% (-47.9167pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__esg_whitespace; PDF page1.
  Input:docs/text/text_multicolumns__esg_whitespace.pdf.
  CF: 97.6057% -> 97.0178% (-0.5879pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__ethbottens; PDF page1.
  Input:docs/text/text_multicolumns__ethbottens.pdf.
  CF: 49.8925% -> 77.0392% (+27.1467pp; improved).
  SF: 64.2045% -> 81.2500% (+17.0455pp; improved).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_multicolumns__forword2cols; PDF page1.
  Input:docs/text/text_multicolumns__forword2cols.pdf.
  CF: 96.9225% -> 88.4971% (-8.4254pp; regressed).
  SF: 100.0000% -> 50.0000% (-50.0000pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__heirloom; PDF page1.
  Input:docs/text/text_multicolumns__heirloom.pdf.
  CF: 38.0952% -> 49.1258% (+11.0305pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__paperchem; PDF page1.
  Input:docs/text/text_multicolumns__paperchem.pdf.
  CF: 70.3823% -> 64.4459% (-5.9364pp; regressed).
  SF: 44.3723% -> 36.1570% (-8.2153pp; regressed).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_multicolumns__sbi; PDF page1.
  Input:docs/text/text_multicolumns__sbi.pdf.
  CF: 95.7029% -> 95.6861% (-0.0168pp; regressed).
  SF: 41.6667% -> 41.6667% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__tableOfContent8col; PDF page1.
  Input:docs/text/text_multicolumns__tableOfContent8col.pdf.
  CF: 62.0923% -> 60.3025% (-1.7898pp; regressed).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__tableinmiddle2cols; PDF page1.
  Input:docs/text/text_multicolumns__tableinmiddle2cols.pdf.
  CF: 57.7184% -> 82.5286% (+24.8102pp; improved).
  SF: 0.0000% -> 11.2500% (+11.2500pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__visa; PDF page1.
  Input:docs/text/text_multicolumns__visa.pdf.
  CF: 87.3084% -> 91.4557% (+4.1473pp; improved).
  SF: 0.0000% -> 83.3333% (+83.3333pp; improved).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_multicolumns__waterfal; PDF page1.
  Input:docs/text/text_multicolumns__waterfal.pdf.
  CF: 94.3911% -> 79.6930% (-14.6981pp; regressed).
  SF: 68.3333% -> 68.3333% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multicolumns__weeds; PDF page1.
  Input:docs/text/text_multicolumns__weeds.pdf.
  CF: 99.2353% -> 99.0645% (-0.1708pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__cnnm; PDF page1.
  Input:docs/text/text_multilang__cnnm.pdf.
  CF: 57.1429% -> 65.9864% (+8.8435pp; improved).
  SF: 0.0000% -> 41.6667% (+41.6667pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__enfr; PDF page1.
  Input:docs/text/text_multilang__enfr.pdf.
  CF: 85.5368% -> 87.0844% (+1.5477pp; improved).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_multilang__greek; PDF page1.
  Input:docs/text/text_multilang__greek.pdf.
  CF: 87.7175% -> 95.9455% (+8.2279pp; improved).
  SF: 25.0000% -> 83.3333% (+58.3333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__japanese5; PDF page1.
  Input:docs/text/text_multilang__japanese5.pdf.
  CF: 25.2019% -> 25.1959% (-0.0060pp; regressed).
  SF: 44.9597% -> 47.8414% (+2.8817pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__kannada; PDF page1.
  Input:docs/text/text_multilang__kannada.pdf.
  CF: 30.3700% -> 30.6963% (+0.3263pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__romanian; PDF page1.
  Input:docs/text/text_multilang__romanian.pdf.
  CF: 84.5501% -> 85.4180% (+0.8679pp; improved).
  SF: 91.8681% -> 87.0879% (-4.7802pp; regressed).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__spanish; PDF page1.
  Input:docs/text/text_multilang__spanish.pdf.
  CF: 92.8244% -> 92.5283% (-0.2961pp; regressed).
  SF: 83.4783% -> 83.4783% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__spanish2; PDF page1.
  Input:docs/text/text_multilang__spanish2.pdf.
  CF: 95.3700% -> 95.3700% (+0.0000pp; unchanged).
  SF: 25.0000% -> 37.5000% (+12.5000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__turkish; PDF page1.
  Input:docs/text/text_multilang__turkish.pdf.
  CF: 90.5091% -> 91.6040% (+1.0949pp; improved).
  SF: 0.0000% -> 41.6667% (+41.6667pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_multilang__ukrainian; PDF page1.
  Input:docs/text/text_multilang__ukrainian.pdf.
  CF: 95.1430% -> 94.7894% (-0.3536pp; regressed).
  SF: 88.0208% -> 88.0208% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__abstract; PDF page1.
  Input:docs/text/text_ocr__abstract.pdf.
  CF: 85.2618% -> 97.5188% (+12.2570pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_ocr__admnh; PDF page1.
  Input:docs/text/text_ocr__admnh.pdf.
  CF: 86.3518% -> 83.9142% (-2.4376pp; regressed).
  SF: 81.2500% -> 81.2500% (+0.0000pp; unchanged).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_ocr__das; PDF page1.
  Input:docs/text/text_ocr__das.pdf.
  CF: 46.0062% -> 38.7711% (-7.2350pp; regressed).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_ocr__diseeas; PDF page1.
  Input:docs/text/text_ocr__diseeas.pdf.
  CF: 80.6396% -> 95.9877% (+15.3481pp; improved).
  SF: 88.0952% -> 9.8214% (-78.2738pp; regressed).
  Selected pages:[1]->[]; Rapid pages:[1]->[]; Markdown changed:True.

- text/text_ocr__klein; PDF page1.
  Input:docs/text/text_ocr__klein.pdf.
  CF: 45.0749% -> 60.3002% (+15.2253pp; improved).
  SF: 0.0000% -> 0.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__mag; PDF page1.
  Input:docs/text/text_ocr__mag.pdf.
  CF: 0.0000% -> 73.3805% (+73.3805pp; improved).
  SF: 0.0000% -> 26.3158% (+26.3158pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_ocr__scaninfile; PDF page1.
  Input:docs/text/text_ocr__scaninfile.pdf.
  CF: 0.0000% -> 76.1763% (+76.1763pp; improved).
  SF: 0.0000% -> 40.2778% (+40.2778pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__4g; PDF page1.
  Input:docs/text/text_simple__4g.pdf.
  CF: 96.5070% -> 97.3875% (+0.8805pp; improved).
  SF: 82.3718% -> 82.3718% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__adminplan; PDF page1.
  Input:docs/text/text_simple__adminplan.pdf.
  CF: 87.0748% -> 98.6395% (+11.5646pp; improved).
  SF: 0.0000% -> 66.6667% (+66.6667pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__bottens; PDF page1.
  Input:docs/text/text_simple__bottens.pdf.
  CF: 99.0257% -> 98.6575% (-0.3682pp; regressed).
  SF: 93.3036% -> 93.3036% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__delinea; PDF page1.
  Input:docs/text/text_simple__delinea.pdf.
  CF: 93.8443% -> 93.5589% (-0.2854pp; regressed).
  SF: 50.0000% -> 50.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__finra; PDF page1.
  Input:docs/text/text_simple__finra.pdf.
  CF: 41.9132% -> 72.2982% (+30.3850pp; improved).
  SF: 0.0000% -> 22.7273% (+22.7273pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__green; PDF page1.
  Input:docs/text/text_simple__green.pdf.
  CF: 66.5353% -> 66.2319% (-0.3034pp; regressed).
  SF: 50.0000% -> 62.5000% (+12.5000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__hex; PDF page1.
  Input:docs/text/text_simple__hex.pdf.
  CF: 88.2647% -> 88.0633% (-0.2014pp; regressed).
  SF: 83.3333% -> 83.3333% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__iehp; PDF page1.
  Input:docs/text/text_simple__iehp.pdf.
  CF: 94.0494% -> 93.5497% (-0.4997pp; regressed).
  SF: 75.0000% -> 75.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__italicsummary; PDF page1.
  Input:docs/text/text_simple__italicsummary.pdf.
  CF: 97.6190% -> 99.2872% (+1.6682pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__landfill; PDF page1.
  Input:docs/text/text_simple__landfill.pdf.
  CF: 38.0952% -> 80.9001% (+42.8048pp; improved).
  SF: 0.0000% -> 32.8020% (+32.8020pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__marknotTable; PDF page1.
  Input:docs/text/text_simple__marknotTable.pdf.
  CF: 97.7013% -> 97.2568% (-0.4444pp; regressed).
  SF: 84.4828% -> 84.4828% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__redirect; PDF page1.
  Input:docs/text/text_simple__redirect.pdf.
  CF: 96.0317% -> 94.7036% (-1.3282pp; regressed).
  SF: 95.4545% -> 95.4545% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__references; PDF page1.
  Input:docs/text/text_simple__references.pdf.
  CF: 96.4334% -> 96.0960% (-0.3374pp; regressed).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__state; PDF page1.
  Input:docs/text/text_simple__state.pdf.
  CF: 87.7484% -> 92.2078% (+4.4594pp; improved).
  SF: 100.0000% -> 100.0000% (+0.0000pp; unchanged).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_simple__tagblatt; PDF page1.
  Input:docs/text/text_simple__tagblatt.pdf.
  CF: 97.4889% -> 97.5427% (+0.0538pp; improved).
  SF: 79.1667% -> 100.0000% (+20.8333pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

- text/text_sparse__conductivity; PDF page1.
  Input:docs/text/text_sparse__conductivity.pdf.
  CF: 60.9524% -> 77.3449% (+16.3925pp; improved).
  SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  Selected pages:[]->[1]; Rapid pages:[]->[1]; Markdown changed:True.

## Original repository README

This is an empty package that is required by pymupdf-2.x, in order to avoid
a pip bug that can result in a broken installation when upgrading from
pymupdf-1.x to pymupdf-2.x.

[The pymupdf-2.x package now contains the 4llm code that used to be in
pymupdf4llm-1.x.]
