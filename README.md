# OCR feature 0: imf2-roi-selector

Branch: ocr/page-selector/imf2-roi-selector-20261027

- P2+ODM: CF 79.6709%; SF 56.6573%.
- IMF2 ROI: CF 80.2324%; SF 57.5318%.

[Complete improvement/regression cases in this README](#independent-ocr-feature-review) | [Machine-readable cases](docs/ocr-independent-cases.json)

This is an independent feature branch on frozen main. Executable code is unchanged by this documentation update.

---

This is an empty package that is required by pymupdf-2.x, in order to avoid
a pip bug that can result in a broken installation when upgrading from
pymupdf-1.x to pymupdf-2.x.

[The pymupdf-2.x package now contains the 4llm code that used to be in
pymupdf4llm-1.x.]

## Independent OCR feature review

Feature 0: imf2-roi-selector

Branch: ocr/page-selector/imf2-roi-selector-20261027

Replaces P2 heuristics+ODM selection with IMF2 ROI. Retains main existing-layer preservation and original OFF/KEEP/DROP/force, Rapid input and writeback. Shared state/policy/render helpers preserve main behavior; no correction is enabled. ROI never crops or filters downstream Rapid.

This repository contains the implementation/dependency change for this feature.

Use the paired branch in both repositories: [PyMuPDF](https://github.com/veget-able/PyMuPDF/tree/ocr/page-selector/imf2-roi-selector-20261027) and [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/ocr/page-selector/imf2-roi-selector-20261027). A documentation-only companion does not implement this feature by itself.

### Model scores and comparison contract

- P2+ODM: CF 79.6709%; SF 56.6573%.
- IMF2 ROI: CF 80.2324%; SF 57.5318%.
- P2+ODM is unmodified main; IMF2 ROI is feature0 only. The selector comparison is0-main, never0-0.
- Same507PDF/509pages;CF506/SF456defined;reference scorer8c63e84;RapidOCR3.10 PPv6small DET/REC,nominal150DPI. Direct REC/shared-span/white masking/OSD/fastText are excluded.
- This update reaggregates stored official scores. No new inference/scoring or implementation change.
- Every changed CF/SF document is listed below; no top5 truncation. Raw scores are0..1 in JSON, percentages here, and changes are percentage points(pp).
- CF/SF are document scores. Page1 is exact for single-page PDFs. For multi-page PDFs, the aggregate change is not assigned to a particular page. OCR page activity is separate processing evidence.
- Improvement/regression labels describe measured score direction, not new visual validation of OCR correctness or proof of the cause.

Full machine-readable cases: [ocr-independent-cases.json](docs/ocr-independent-cases.json).

### Comparison 1: Selector replacement: 0 versus main

Before: main(P2+ODM). After: 0:imf2-roi-selector(IMF2 ROI).

- CF: improved 26, regressed 27, unchanged 453 scored documents.
- SF: improved 16, regressed 8, unchanged 432 scored documents.
- Unique changed documents: 54. A document with opposite CF/SF directions is listed once under mixed changes.

#### Improvements without a regression (23 documents)

- text/text_sparse__conductivity; PDF page1 (single-page document).
  Input PDF: docs/text/text_sparse__conductivity.pdf.
  CF: 60.9524% -> 77.3449% (+16.3925pp; improved). SF: 0.0000% -> 100.0000% (+100.0000pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__visa; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__visa.pdf.
  CF: 87.3084% -> 91.4557% (+4.1473pp; improved). SF: 0.0000% -> 83.3333% (+83.3333pp; improved).
  OCR selection pages: 1 -> none; Rapid invocation pages: 1 -> none.
  Final Markdown changed.
- text/text_ocr__scaninfile; PDF page1 (single-page document).
  Input PDF: docs/text/text_ocr__scaninfile.pdf.
  CF: 0.0000% -> 76.1763% (+76.1763pp; improved). SF: 0.0000% -> 40.2778% (+40.2778pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_ocr__mag; PDF page1 (single-page document).
  Input PDF: docs/text/text_ocr__mag.pdf.
  CF: 0.0000% -> 73.3805% (+73.3805pp; improved). SF: 0.0000% -> 26.3158% (+26.3158pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__adminplan; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__adminplan.pdf.
  CF: 87.0748% -> 98.6395% (+11.5646pp; improved). SF: 0.0000% -> 66.6667% (+66.6667pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multilang__greek; PDF page1 (single-page document).
  Input PDF: docs/text/text_multilang__greek.pdf.
  CF: 87.7175% -> 95.9455% (+8.2279pp; improved). SF: 25.0000% -> 83.3333% (+58.3333pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__landfill; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__landfill.pdf.
  CF: 38.0952% -> 80.9001% (+42.8048pp; improved). SF: 0.0000% -> 32.8020% (+32.8020pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multilang__turkish; PDF page1 (single-page document).
  Input PDF: docs/text/text_multilang__turkish.pdf.
  CF: 89.3778% -> 90.4482% (+1.0705pp; improved). SF: 0.0000% -> 41.6667% (+41.6667pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multilang__cnnm; PDF page1 (single-page document).
  Input PDF: docs/text/text_multilang__cnnm.pdf.
  CF: 57.1429% -> 65.9864% (+8.8435pp; improved). SF: 0.0000% -> 41.6667% (+41.6667pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__finra; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__finra.pdf.
  CF: 41.9132% -> 72.2982% (+30.3850pp; improved). SF: 0.0000% -> 22.7273% (+22.7273pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__tableinmiddle2cols; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__tableinmiddle2cols.pdf.
  CF: 57.7184% -> 82.5286% (+24.8102pp; improved). SF: 0.0000% -> 11.2500% (+11.2500pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__tagblatt; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__tagblatt.pdf.
  CF: 97.4889% -> 97.5427% (+0.0538pp; improved). SF: 79.1667% -> 100.0000% (+20.8333pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_ocr__klein; PDF page1 (single-page document).
  Input PDF: docs/text/text_ocr__klein.pdf.
  CF: 45.0749% -> 60.3002% (+15.2253pp; improved). SF: 0.0000% -> 0.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multilang__spanish2; PDF page1 (single-page document).
  Input PDF: docs/text/text_multilang__spanish2.pdf.
  CF: 93.6877% -> 93.6877% (+0.00000000pp; unchanged). SF: 25.0000% -> 37.5000% (+12.5000pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__heirloom; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__heirloom.pdf.
  CF: 38.0952% -> 49.1258% (+11.0305pp; improved). SF: 0.0000% -> 0.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__coorp; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__coorp.pdf.
  CF: 87.0256% -> 96.0942% (+9.0686pp; improved). SF: 98.7805% -> 98.7805% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_dense__underline; PDF page1 (single-page document).
  Input PDF: docs/text/text_dense__underline.pdf.
  CF: 42.7530% -> 47.8268% (+5.0738pp; improved). SF: not scored.
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__state; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__state.pdf.
  CF: 87.7484% -> 92.2078% (+4.4594pp; improved). SF: 100.0000% -> 100.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__dafta; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__dafta.pdf.
  CF: 91.2683% -> 94.1166% (+2.8483pp; improved). SF: 50.0000% -> 50.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__3col_statment; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__3col_statment.pdf.
  CF: 80.9526% -> 83.4217% (+2.4691pp; improved). SF: 100.0000% -> 100.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__italicsummary; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__italicsummary.pdf.
  CF: 97.6190% -> 99.2872% (+1.6682pp; improved). SF: 100.0000% -> 100.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__4g; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__4g.pdf.
  CF: 96.5070% -> 97.3875% (+0.8805pp; improved). SF: 82.3718% -> 82.3718% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multilang__kannada; PDF page1 (single-page document).
  Input PDF: docs/text/text_multilang__kannada.pdf.
  CF: 30.3700% -> 30.6963% (+0.3263pp; improved). SF: 0.0000% -> 0.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.

#### Regressions without an improvement (24 documents)

- text/text_multicolumns__forword2cols; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__forword2cols.pdf.
  CF: 96.9225% -> 88.4971% (-8.4254pp; regressed). SF: 100.0000% -> 50.0000% (-50.0000pp; regressed).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__esd_end; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__esd_end.pdf.
  CF: 84.0375% -> 83.6335% (-0.4040pp; regressed). SF: 47.9167% -> 0.0000% (-47.9167pp; regressed).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__att10k; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__att10k.pdf.
  CF: 62.4997% -> 20.4788% (-42.0209pp; regressed). SF: not scored.
  OCR selection pages: 1 -> none; Rapid invocation pages: 1 -> none.
  Final Markdown changed.
- text/text_multicolumns__waterfal; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__waterfal.pdf.
  CF: 94.3911% -> 79.6930% (-14.6981pp; regressed). SF: 68.3333% -> 68.3333% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_misc__ikea3; PDF page1 (single-page document).
  Input PDF: docs/text/text_misc__ikea3.pdf.
  CF: 77.3498% -> 76.7650% (-0.5848pp; regressed). SF: 46.5186% -> 35.0055% (-11.5132pp; regressed).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__2col_fund_summary; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__2col_fund_summary.pdf.
  CF: 99.7445% -> 99.2857% (-0.4587pp; regressed). SF: 100.0000% -> 90.0000% (-10.0000pp; regressed).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__3colpres; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__3colpres.pdf.
  CF: 94.6715% -> 88.4797% (-6.1917pp; regressed). SF: 62.5000% -> 62.5000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__tableOfContent8col; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__tableOfContent8col.pdf.
  CF: 62.0923% -> 60.3025% (-1.7898pp; regressed). SF: 0.0000% -> 0.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__redirect; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__redirect.pdf.
  CF: 96.0317% -> 94.7036% (-1.3282pp; regressed). SF: 95.4545% -> 95.4545% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_misc__gridofimages; PDF page1 (single-page document).
  Input PDF: docs/text/text_misc__gridofimages.pdf.
  CF: 65.9550% -> 65.3347% (-0.6203pp; regressed). SF: not scored.
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__esg_whitespace; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__esg_whitespace.pdf.
  CF: 97.6057% -> 97.0178% (-0.5879pp; regressed). SF: 100.0000% -> 100.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__iehp; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__iehp.pdf.
  CF: 94.0494% -> 93.5497% (-0.4997pp; regressed). SF: 75.0000% -> 75.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__marknotTable; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__marknotTable.pdf.
  CF: 97.7013% -> 97.2568% (-0.4444pp; regressed). SF: 84.4828% -> 84.4828% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__bottens; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__bottens.pdf.
  CF: 99.0257% -> 98.6575% (-0.3682pp; regressed). SF: 93.3036% -> 93.3036% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multilang__ukrainian; PDF page1 (single-page document).
  Input PDF: docs/text/text_multilang__ukrainian.pdf.
  CF: 93.1378% -> 92.7757% (-0.3621pp; regressed). SF: 88.0208% -> 88.0208% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__references; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__references.pdf.
  CF: 96.4334% -> 96.0960% (-0.3374pp; regressed). SF: 100.0000% -> 100.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__delinea; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__delinea.pdf.
  CF: 93.8443% -> 93.5589% (-0.2854pp; regressed). SF: 50.0000% -> 50.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_misc__json; PDF page1 (single-page document).
  Input PDF: docs/text/text_misc__json.pdf.
  CF: 89.1242% -> 88.8427% (-0.2814pp; regressed). SF: 83.3333% -> 83.3333% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__2colrep; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__2colrep.pdf.
  CF: 97.2987% -> 97.0520% (-0.2467pp; regressed). SF: 36.6071% -> 36.6071% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__hex; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__hex.pdf.
  CF: 88.2647% -> 88.0633% (-0.2014pp; regressed). SF: 83.3333% -> 83.3333% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__weeds; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__weeds.pdf.
  CF: 99.2353% -> 99.0645% (-0.1708pp; regressed). SF: 100.0000% -> 100.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multilang__spanish; PDF page1 (single-page document).
  Input PDF: docs/text/text_multilang__spanish.pdf.
  CF: 82.0444% -> 81.9345% (-0.1099pp; regressed). SF: 83.4783% -> 83.4783% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__article; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__article.pdf.
  CF: 90.9122% -> 90.8697% (-0.0425pp; regressed). SF: 100.0000% -> 100.0000% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__sbi; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__sbi.pdf.
  CF: 95.7029% -> 95.6861% (-0.0168pp; regressed). SF: 41.6667% -> 41.6667% (+0.00000000pp; unchanged).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.

#### Mixed CF/SF changes (7 documents)

- text/text_multicolumns__2x; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__2x.pdf.
  CF: 89.9595% -> 92.4154% (+2.4559pp; improved). SF: 98.7421% -> 61.2421% (-37.5000pp; regressed).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__energy2; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__energy2.pdf.
  CF: 85.4816% -> 93.6204% (+8.1388pp; improved). SF: 99.1071% -> 86.6071% (-12.5000pp; regressed).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_simple__green; PDF page1 (single-page document).
  Input PDF: docs/text/text_simple__green.pdf.
  CF: 66.5353% -> 66.2319% (-0.3034pp; regressed). SF: 50.0000% -> 62.5000% (+12.5000pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multicolumns__drill; PDF page1 (single-page document).
  Input PDF: docs/text/text_multicolumns__drill.pdf.
  CF: 93.0219% -> 96.5135% (+3.4916pp; improved). SF: 66.6667% -> 58.3333% (-8.3333pp; regressed).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_dense__leaflet; PDF page1 (single-page document).
  Input PDF: docs/text/text_dense__leaflet.pdf.
  CF: 92.8562% -> 91.8862% (-0.9700pp; regressed). SF: 60.6838% -> 68.2234% (+7.5397pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multilang__romanian; PDF page1 (single-page document).
  Input PDF: docs/text/text_multilang__romanian.pdf.
  CF: 84.5501% -> 85.4180% (+0.8679pp; improved). SF: 91.8681% -> 87.0879% (-4.7802pp; regressed).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.
- text/text_multilang__japanese5; PDF page1 (single-page document).
  Input PDF: docs/text/text_multilang__japanese5.pdf.
  CF: 25.2019% -> 25.1959% (-0.0060pp; regressed). SF: 44.9597% -> 47.8414% (+2.8817pp; improved).
  OCR selection pages: none -> 1; Rapid invocation pages: none -> 1.
  Final Markdown changed.

### TODO: REPAIR policy/API naming

- REPAIR names, enum values and API binding are deferred. No new REPAIR API is included.
- Features5 and6 operate independently on main; a future API binding must preserve their distinct scope and existing explicit modes.

### Options, source and validation

- Additional gate/damage behavior runs for literal use_ocr=True. Explicit KEEP/DROP/FORCE modes retain main behavior; no new damage priority is enabled. Public force_ocr=True retains the original main forwarding to FORCE_KEEP_OLD.
- Fixed PyMuPDF main: 1d34e04da00b7673a0b2c3f68b5a5246793a50b8.
- Fixed pymupdf4llm main: 363f177ef50deb05f07db8bf2061e7b9c8102b07.
- One final review commit directly on fixed main. The documentation amendment preserves the executable tree of implementation commit 3b9b30a15095822a3db55e50bc30cfef4dbf980a.
- Prior validation:61feature tests;120direct mode cases;48public forwarding cases;helper-only parity on509analysis/render pages,507fresh Markdown outputs and188actual Rapid inputs. No helper-only quality arm added.
- Earlier evaluation timings include partial extraction/cache checks and concurrent resource contention. They are not full fresh-pipeline latency or evidence of speed advantage.
- Exact comparison arms, input hashes, official score values, before/after Markdown hashes, source-score-file hashes and all cases are preserved in docs/ocr-independent-cases.json.
