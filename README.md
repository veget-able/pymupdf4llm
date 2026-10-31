# OCR correction 7: writeback fonts and mixed-font spacing

Branch: ocr/writeback-correction/writeback-fonts-20261031

Independent direct-main correction. The selector branch and correction features1–6 remain unchanged.

Correct REC Unicode can be lost when the PDF writing font lacks a glyph. This change selects covering built-in fonts, avoids existing PDF font-resource aliases, and keeps adjacent font runs from the same REC string together during Markdown generation.

## Scope

- Writing fonts: existing Droid Sans Fallback, MuPDF built-in Noto Serif Devanagari, Helvetica and ZapfDingbats. No external font download or new recognition model.
- Preserve an existing covering font plan. Otherwise choose supported font runs while keeping combining-character clusters together. This is a finite font pool, not universal Unicode coverage or a general shaping engine.
- Reserve unused PDF font aliases before registration. Existing PDF font resources are retained.
- Mark a mixed write only when the before/after extracted spans identify the newly written runs exactly. The formatter joins only adjacent spans with the same REC owner, continuous character offsets and matching source text. Original spaces, separate REC results and unrelated native spans keep their existing behavior.
- Page selection, stored-text classification, render, Rapid DET/REC, public options and KEEP/DROP rules remain those of the target base. This feature does not require another correction branch or the historical REPAIR implementation.

## Further font additions

Add or expand fonts only when a concrete missing-font or missing-glyph case is confirmed. First compare raw REC Unicode with PDF write/save/reextract and final output; separate an already incorrect REC result from a writing loss. Record the document/character and selected font, add a minimal regression test, then validate the fallback and affected output quality. Do not expand the font pool speculatively.

## Current-main quality evidence

Frozen main: pymupdf4llm 363f177ef50deb05f07db8bf2061e7b9c8102b07 and PyMuPDF 1d34e04da00b7673a0b2c3f68b5a5246793a50b8. These are main-based results, not the older integrated IMF2 ROI/REPAIR score.

- CF: 79.6709087651% -> 79.6832432844%, +0.0123345193 percentage points; 3 improved, 0 regressed.
- SF: 56.6573495337% -> 56.7414138612%, +0.0840643275 percentage points; 1 improved, 0 regressed.
- Same 507 PDFs / 509 pages; CF506, SF476 supported / 456 defined. Official reference scorer 8c63e84eff6e51b943496492651ee27e9e71663f.
- Candidate public extraction ran for all 507 documents. All 509 page-selection tuples and 188 Rapid input RGB hashes match the existing main. Stored 7,023 REC strings were replayed after exact-input validation; new DET/REC inference calls: 0.
- Baseline reproduction freshly ran 9 affected/control documents and matched existing main Markdown. Official workers freshly scored 8 changed-output cases; 974 unchanged full-output/case/scorer/SHA-verified scores were reused.
- Final Markdown changed in 4 documents. The other 503 were identical. Page-level selector accuracy is unaffected; CF/SF are document quality metrics.

## Complete changed-output cases

### text/text_ocr__glitch — Changed output

PDF: docs/text/text_ocr__glitch.pdf; page1. Page selected: True; Rapid calls: 1. All cases here are single-page documents.

- CF: 75.91439074% -> 78.37687949%, +2.46248876 percentage points.
- SF: 13.06818182% -> 13.06818182%, +0.00000000 percentage points.
- Restores Romanian ț/ș lost by the original CJK writing font.

### text/text_ocr__routier — Changed output

PDF: docs/text/text_ocr__routier.pdf; page1. Page selected: True; Rapid calls: 1. All cases here are single-page documents.

- CF: 80.83080229% -> 84.60283190%, +3.77202960 percentage points.
- SF: 0.00000000% -> 38.33333333%, +38.33333333 percentage points.
- Restores Romanian letters. Font/text attributes also change downstream layout, so the SF gain is not attributed solely to character accuracy.

### text/text_ocr__ref — Changed output

PDF: docs/text/text_ocr__ref.pdf; page1. Page selected: True; Rapid calls: 1. All cases here are single-page documents.

- CF: 72.19144496% -> 72.19819338%, +0.00674842 percentage points.
- SF: 50.00000000% -> 50.00000000%, +0.00000000 percentage points.
- Preserves REC output containing ș. Font preservation does not establish that the REC spelling itself is correct.

### text/text_handwritting__math — Changed output

PDF: docs/text/text_handwritting__math.pdf; page1. Page selected: True; Rapid calls: 1. All cases here are single-page documents.

- CF: 36.74169191% -> 36.74169191%, +0.00000000 percentage points.
- SF: 0.00000000% -> 0.00000000%, +0.00000000 percentage points.
- Preserves ∆; CF/SF stay unchanged. This is not evidence of page-GT handwriting-policy improvement.

### text/text_simple__iehp — Unchanged comparison case

PDF: docs/text/text_simple__iehp.pdf; page1. Page selected: False; Rapid calls: 0. All cases here are single-page documents.

- CF: 94.04940089% -> 94.04940089%, +0.00000000 percentage points.
- SF: 75.00000000% -> 75.00000000%, +0.00000000 percentage points.
- Main does not select this page for OCR, so no font write is reached. The historical integrated handoff selected it; that older score must not be substituted here.

## Processing cost

Same9 documents,3 repetitions per arm, sequential AB/BA/AB order, CPU12, ORT intra/inter1 and OMP/OpenBLAS/MKL1. Imports and9-document process warmups were measured separately. All timing outputs match the quality-run Markdown. Stored REC replay replaces DET/REC inference, so these are replay-pipeline and writing costs, not actual full OCR inference latency or total507-document time.

- Baseline: 3.3940s per9 documents; mean 377.113ms/document, p95 1826.690ms.
- Candidate: 3.4459s per9 documents; mean 382.881ms/document, p95 1842.483ms.
- Writing-stage delta: +50.296ms per9-document batch, approximately +10.059ms per writing page in the5 writing pages /223 REC strings. This sample is not representative of every document.
- Main replay has zero mixed-font results. Separate synthetic mixed-run measurements showed owner capture adds approximately0.4ms with no native spans and1.8ms with200 native spans per mixed write. It extracts page text before and after the write; cost can grow with page text and mixed-result count.

## Persistence and other limits

- Fonts and Unicode survive PDF save/reopen. REC ownership metadata lives on the current Python Page object and is not serialized into the PDF.
- In the same OCR-to-Markdown session IE❤HP stays IE❤HP. After saving and reopening, raw get_text still returns IE❤HP, while Markdown may become IE ❤ HP. This feature does not promise persistent mixed-run spacing across PDF reopening.
- Some Devanagari-plus-symbol combinations, for example ț漢字प❤, are still rejected by the supplied prior planner before extended fallback. This was not present in the evaluated REC corpus and is not fixed here.
- Unsupported scripts, already wrong recognition, legacy font mappings, visual shaping and other native versions are not established by this evaluation.
- Existing1.28.0 was not rerun; this is a feature comparison on2.0-based main, not a version benchmark.

## Validation and reproduction

- Main-specific22 regression tests cover PDF Unicode roundtrip, resource collisions, source-contiguity boundaries and existing full/detection KEEP/DROP behavior. Historical174 tests belong to the older integrated source and are not claimed as current-main test results.
- From this checkout, run: python examples/check_ocr_writeback_fonts.py. Use matching PyMuPDF 2.0 main Python bindings (1d34e04 or compatible) and pytest; older draft-c bindings lack the layout API used by this main. The runner copies this checkout's source into a temporary package, generates only its required version metadata, and runs the tests without dependency installation, wheels or installed-package changes.
- Use an existing compatible PyMuPDF2.0 environment. Load this checkout’s src as pymupdf4llm through the same source overlay mechanism used by PyMuPDF2.0 builds; do not accidentally test the installed historical package.
- Run pytest with --noconftest and -p no:cacheprovider when using the repository tests, because its existing conftest performs dependency installation. The validated test is tests/test_ocr_writeback_fonts.py.
- Local full validation evidence: runs/OCR_WRITEBACK_MAIN_VALIDATION_20261031/ under the pb_ocr research workspace; source/REC RGB checks, official scores, timing and reopen reports are retained there.
- [Machine-readable results and complete per-document deltas](docs/ocr-writeback-fonts/results.json).
- This source change does not build or publish wheels, update installed packages, or deploy the viewer.

## IMF2 ROI combination and complete cases

The delivery branch contains only feature7 on main. The following auxiliary evaluation composes the existing selector0 and feature7 in a separate runtime, without inheriting corrections1–6. It is not the older integrated REPAIR score.

- CF: 80.2323814244% -> 80.2447159437%, +0.0123345193 percentage points; improved 3, regressed 0.
- SF: 57.5318031859% -> 57.6158675133%, +0.0840643275 percentage points; improved 1, regressed 0.
- All 507 candidate documents were freshly passed through public selection/render/writeback/GNN/Markdown. All 509 decision tuples and 265 Rapid RGB inputs match selector0; 7546 saved REC strings were replayed. New DET/REC inference calls: 0.
- Fresh official worker scores: 10; unchanged exact-output/case/scorer/SHA score reuses: 972.
- Baseline9 affected/control documents were freshly reproduced and matched the prior selector-only outputs. The P2 timing sample above is not reused as IMF2 timing.

### text/text_handwritting__math

PDF: docs/text/text_handwritting__math.pdf; page1. Selection pages: [1]; Rapid calls: 1; Markdown changed: True.

- CF: 36.74169191% -> 36.74169191%, +0.00000000 percentage points.
- SF: 0.00000000% -> 0.00000000%, +0.00000000 percentage points.

### text/text_ocr__glitch

PDF: docs/text/text_ocr__glitch.pdf; page1. Selection pages: [1]; Rapid calls: 1; Markdown changed: True.

- CF: 75.91439074% -> 78.37687949%, +2.46248876 percentage points.
- SF: 13.06818182% -> 13.06818182%, +0.00000000 percentage points.

### text/text_ocr__ref

PDF: docs/text/text_ocr__ref.pdf; page1. Selection pages: [1]; Rapid calls: 1; Markdown changed: True.

- CF: 72.19144496% -> 72.19819338%, +0.00674842 percentage points.
- SF: 50.00000000% -> 50.00000000%, +0.00000000 percentage points.

### text/text_ocr__routier

PDF: docs/text/text_ocr__routier.pdf; page1. Selection pages: [1]; Rapid calls: 1; Markdown changed: True.

- CF: 80.83080229% -> 84.60283190%, +3.77202960 percentage points.
- SF: 0.00000000% -> 38.33333333%, +38.33333333 percentage points.

### text/text_simple__iehp

PDF: docs/text/text_simple__iehp.pdf; page1. Selection pages: [1]; Rapid calls: 1; Markdown changed: True.

- CF: 93.54966189% -> 93.54966189%, +0.00000000 percentage points.
- SF: 75.00000000% -> 75.00000000%, +0.00000000 percentage points.

## Selector comparison on the same font correction

Comparison: 0+7 (IMF2 ROI plus fonts) versus7 (P2+ODM plus fonts). This measures the selector effect with the writing correction fixed. All changed document scores are listed below; score changes are not assertions of OCR correctness.

- CF: 79.6832432844% -> 80.2447159437%, +0.5614726593 percentage points.
- SF: 56.7414138612% -> 57.6158675133%, +0.8744536521 percentage points.

Unique documents with changed defined CF/SF: 54. Full machine-readable comparisons: [model-comparisons.json](docs/ocr-writeback-fonts/model-comparisons.json).

### text/text_dense__leaflet

PDF: docs/text/text_dense__leaflet.pdf; page1 (single-page document).
- CF: 92.85615807% -> 91.88619121%, -0.96996686 percentage points.
- SF: 60.68376068% -> 68.22344322%, +7.53968254 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_dense__underline

PDF: docs/text/text_dense__underline.pdf; page1 (single-page document).
- CF: 42.75298473% -> 47.82677084%, +5.07378611 percentage points.
- SF: no defined score.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_misc__gridofimages

PDF: docs/text/text_misc__gridofimages.pdf; page1 (single-page document).
- CF: 65.95501184% -> 65.33471109%, -0.62030075 percentage points.
- SF: no defined score.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_misc__ikea3

PDF: docs/text/text_misc__ikea3.pdf; page1 (single-page document).
- CF: 77.34984868% -> 76.76501298%, -0.58483570 percentage points.
- SF: 46.51864035% -> 35.00548246%, -11.51315789 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_misc__json

PDF: docs/text/text_misc__json.pdf; page1 (single-page document).
- CF: 89.12415594% -> 88.84273664%, -0.28141930 percentage points.
- SF: 83.33333333% -> 83.33333333%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__2col_fund_summary

PDF: docs/text/text_multicolumns__2col_fund_summary.pdf; page1 (single-page document).
- CF: 99.74446189% -> 99.28571429%, -0.45874760 percentage points.
- SF: 100.00000000% -> 90.00000000%, -10.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__2colrep

PDF: docs/text/text_multicolumns__2colrep.pdf; page1 (single-page document).
- CF: 97.29870685% -> 97.05198880%, -0.24671805 percentage points.
- SF: 36.60714286% -> 36.60714286%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__2x

PDF: docs/text/text_multicolumns__2x.pdf; page1 (single-page document).
- CF: 89.95946062% -> 92.41538477%, +2.45592415 percentage points.
- SF: 98.74213836% -> 61.24213836%, -37.50000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__3col_statment

PDF: docs/text/text_multicolumns__3col_statment.pdf; page1 (single-page document).
- CF: 80.95256302% -> 83.42169882%, +2.46913580 percentage points.
- SF: 100.00000000% -> 100.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__3colpres

PDF: docs/text/text_multicolumns__3colpres.pdf; page1 (single-page document).
- CF: 94.67148046% -> 88.47974066%, -6.19173979 percentage points.
- SF: 62.50000000% -> 62.50000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__article

PDF: docs/text/text_multicolumns__article.pdf; page1 (single-page document).
- CF: 90.91220086% -> 90.86973522%, -0.04246564 percentage points.
- SF: 100.00000000% -> 100.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__coorp

PDF: docs/text/text_multicolumns__coorp.pdf; page1 (single-page document).
- CF: 87.02560547% -> 96.09416871%, +9.06856324 percentage points.
- SF: 98.78048780% -> 98.78048780%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__dafta

PDF: docs/text/text_multicolumns__dafta.pdf; page1 (single-page document).
- CF: 91.26830401% -> 94.11662407%, +2.84832007 percentage points.
- SF: 50.00000000% -> 50.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__drill

PDF: docs/text/text_multicolumns__drill.pdf; page1 (single-page document).
- CF: 93.02193837% -> 96.51354957%, +3.49161119 percentage points.
- SF: 66.66666667% -> 58.33333333%, -8.33333333 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__energy2

PDF: docs/text/text_multicolumns__energy2.pdf; page1 (single-page document).
- CF: 85.48155079% -> 93.62038219%, +8.13883140 percentage points.
- SF: 99.10714286% -> 86.60714286%, -12.50000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__esd_end

PDF: docs/text/text_multicolumns__esd_end.pdf; page1 (single-page document).
- CF: 84.03747214% -> 83.63346135%, -0.40401079 percentage points.
- SF: 47.91666667% -> 0.00000000%, -47.91666667 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__esg_whitespace

PDF: docs/text/text_multicolumns__esg_whitespace.pdf; page1 (single-page document).
- CF: 97.60569582% -> 97.01778671%, -0.58790911 percentage points.
- SF: 100.00000000% -> 100.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__forword2cols

PDF: docs/text/text_multicolumns__forword2cols.pdf; page1 (single-page document).
- CF: 96.92247058% -> 88.49707366%, -8.42539692 percentage points.
- SF: 100.00000000% -> 50.00000000%, -50.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__heirloom

PDF: docs/text/text_multicolumns__heirloom.pdf; page1 (single-page document).
- CF: 38.09523810% -> 49.12577748%, +11.03053939 percentage points.
- SF: 0.00000000% -> 0.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__sbi

PDF: docs/text/text_multicolumns__sbi.pdf; page1 (single-page document).
- CF: 95.70287062% -> 95.68605688%, -0.01681374 percentage points.
- SF: 41.66666667% -> 41.66666667%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__tableOfContent8col

PDF: docs/text/text_multicolumns__tableOfContent8col.pdf; page1 (single-page document).
- CF: 62.09233489% -> 60.30254612%, -1.78978877 percentage points.
- SF: 0.00000000% -> 0.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__tableinmiddle2cols

PDF: docs/text/text_multicolumns__tableinmiddle2cols.pdf; page1 (single-page document).
- CF: 57.71836107% -> 82.52859940%, +24.81023833 percentage points.
- SF: 0.00000000% -> 11.25000000%, +11.25000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__visa

PDF: docs/text/text_multicolumns__visa.pdf; page1 (single-page document).
- CF: 87.30837866% -> 91.45566592%, +4.14728727 percentage points.
- SF: 0.00000000% -> 83.33333333%, +83.33333333 percentage points.
- Selection pages P2 -> IMF2: [1] -> []; Rapid calls: 1 -> 0; Markdown changed: True.

### text/text_multicolumns__waterfal

PDF: docs/text/text_multicolumns__waterfal.pdf; page1 (single-page document).
- CF: 94.39107115% -> 79.69297106%, -14.69810008 percentage points.
- SF: 68.33333333% -> 68.33333333%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multicolumns__weeds

PDF: docs/text/text_multicolumns__weeds.pdf; page1 (single-page document).
- CF: 99.23526078% -> 99.06447276%, -0.17078801 percentage points.
- SF: 100.00000000% -> 100.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multilang__cnnm

PDF: docs/text/text_multilang__cnnm.pdf; page1 (single-page document).
- CF: 57.14285714% -> 65.98639456%, +8.84353741 percentage points.
- SF: 0.00000000% -> 41.66666667%, +41.66666667 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multilang__greek

PDF: docs/text/text_multilang__greek.pdf; page1 (single-page document).
- CF: 87.71754667% -> 95.94548594%, +8.22793927 percentage points.
- SF: 25.00000000% -> 83.33333333%, +58.33333333 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multilang__japanese5

PDF: docs/text/text_multilang__japanese5.pdf; page1 (single-page document).
- CF: 25.20188786% -> 25.19587786%, -0.00601000 percentage points.
- SF: 44.95967742% -> 47.84135150%, +2.88167408 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multilang__kannada

PDF: docs/text/text_multilang__kannada.pdf; page1 (single-page document).
- CF: 30.37000015% -> 30.69631403%, +0.32631387 percentage points.
- SF: 0.00000000% -> 0.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multilang__romanian

PDF: docs/text/text_multilang__romanian.pdf; page1 (single-page document).
- CF: 84.55011505% -> 85.41796688%, +0.86785183 percentage points.
- SF: 91.86813187% -> 87.08791209%, -4.78021978 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multilang__spanish

PDF: docs/text/text_multilang__spanish.pdf; page1 (single-page document).
- CF: 82.04440813% -> 81.93447268%, -0.10993545 percentage points.
- SF: 83.47826087% -> 83.47826087%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multilang__spanish2

PDF: docs/text/text_multilang__spanish2.pdf; page1 (single-page document).
- CF: 93.68765114% -> 93.68765114%, +0.00000000 percentage points.
- SF: 25.00000000% -> 37.50000000%, +12.50000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multilang__turkish

PDF: docs/text/text_multilang__turkish.pdf; page1 (single-page document).
- CF: 89.37777087% -> 90.44824034%, +1.07046947 percentage points.
- SF: 0.00000000% -> 41.66666667%, +41.66666667 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_multilang__ukrainian

PDF: docs/text/text_multilang__ukrainian.pdf; page1 (single-page document).
- CF: 93.13781119% -> 92.77566182%, -0.36214938 percentage points.
- SF: 88.02083333% -> 88.02083333%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_ocr__klein

PDF: docs/text/text_ocr__klein.pdf; page1 (single-page document).
- CF: 45.07486665% -> 60.30019054%, +15.22532388 percentage points.
- SF: 0.00000000% -> 0.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_ocr__mag

PDF: docs/text/text_ocr__mag.pdf; page1 (single-page document).
- CF: 0.00000000% -> 73.38052933%, +73.38052933 percentage points.
- SF: 0.00000000% -> 26.31578947%, +26.31578947 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_ocr__scaninfile

PDF: docs/text/text_ocr__scaninfile.pdf; page1 (single-page document).
- CF: 0.00000000% -> 76.17625130%, +76.17625130 percentage points.
- SF: 0.00000000% -> 40.27777778%, +40.27777778 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__4g

PDF: docs/text/text_simple__4g.pdf; page1 (single-page document).
- CF: 96.50698626% -> 97.38746130%, +0.88047504 percentage points.
- SF: 82.37179487% -> 82.37179487%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__adminplan

PDF: docs/text/text_simple__adminplan.pdf; page1 (single-page document).
- CF: 87.07482993% -> 98.63945578%, +11.56462585 percentage points.
- SF: 0.00000000% -> 66.66666667%, +66.66666667 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__att10k

PDF: docs/text/text_simple__att10k.pdf; page1 (single-page document).
- CF: 62.49973258% -> 20.47879261%, -42.02093997 percentage points.
- SF: no defined score.
- Selection pages P2 -> IMF2: [1] -> []; Rapid calls: 1 -> 0; Markdown changed: True.

### text/text_simple__bottens

PDF: docs/text/text_simple__bottens.pdf; page1 (single-page document).
- CF: 99.02572523% -> 98.65749534%, -0.36822989 percentage points.
- SF: 93.30357143% -> 93.30357143%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__delinea

PDF: docs/text/text_simple__delinea.pdf; page1 (single-page document).
- CF: 93.84429803% -> 93.55888283%, -0.28541520 percentage points.
- SF: 50.00000000% -> 50.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__finra

PDF: docs/text/text_simple__finra.pdf; page1 (single-page document).
- CF: 41.91317941% -> 72.29822482%, +30.38504541 percentage points.
- SF: 0.00000000% -> 22.72727273%, +22.72727273 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__green

PDF: docs/text/text_simple__green.pdf; page1 (single-page document).
- CF: 66.53531347% -> 66.23190594%, -0.30340753 percentage points.
- SF: 50.00000000% -> 62.50000000%, +12.50000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__hex

PDF: docs/text/text_simple__hex.pdf; page1 (single-page document).
- CF: 88.26467217% -> 88.06327975%, -0.20139242 percentage points.
- SF: 83.33333333% -> 83.33333333%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__iehp

PDF: docs/text/text_simple__iehp.pdf; page1 (single-page document).
- CF: 94.04940089% -> 93.54966189%, -0.49973900 percentage points.
- SF: 75.00000000% -> 75.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__italicsummary

PDF: docs/text/text_simple__italicsummary.pdf; page1 (single-page document).
- CF: 97.61904762% -> 99.28722342%, +1.66817580 percentage points.
- SF: 100.00000000% -> 100.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__landfill

PDF: docs/text/text_simple__landfill.pdf; page1 (single-page document).
- CF: 38.09523810% -> 80.90008780%, +42.80484971 percentage points.
- SF: 0.00000000% -> 32.80204644%, +32.80204644 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__marknotTable

PDF: docs/text/text_simple__marknotTable.pdf; page1 (single-page document).
- CF: 97.70126659% -> 97.25682215%, -0.44444444 percentage points.
- SF: 84.48275862% -> 84.48275862%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__redirect

PDF: docs/text/text_simple__redirect.pdf; page1 (single-page document).
- CF: 96.03174603% -> 94.70359572%, -1.32815031 percentage points.
- SF: 95.45454545% -> 95.45454545%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__references

PDF: docs/text/text_simple__references.pdf; page1 (single-page document).
- CF: 96.43338143% -> 96.09601828%, -0.33736315 percentage points.
- SF: 100.00000000% -> 100.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__state

PDF: docs/text/text_simple__state.pdf; page1 (single-page document).
- CF: 87.74837363% -> 92.20779221%, +4.45941858 percentage points.
- SF: 100.00000000% -> 100.00000000%, +0.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_simple__tagblatt

PDF: docs/text/text_simple__tagblatt.pdf; page1 (single-page document).
- CF: 97.48890484% -> 97.54270819%, +0.05380335 percentage points.
- SF: 79.16666667% -> 100.00000000%, +20.83333333 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

### text/text_sparse__conductivity

PDF: docs/text/text_sparse__conductivity.pdf; page1 (single-page document).
- CF: 60.95238095% -> 77.34487734%, +16.39249639 percentage points.
- SF: 0.00000000% -> 100.00000000%, +100.00000000 percentage points.
- Selection pages P2 -> IMF2: [] -> [1]; Rapid calls: 0 -> 1; Markdown changed: True.

## Original package note

This is an empty package that is required by pymupdf-2.x, in order to avoid
a pip bug that can result in a broken installation when upgrading from
pymupdf-1.x to pymupdf-2.x.

[The pymupdf-2.x package now contains the 4llm code that used to be in
pymupdf4llm-1.x.]
