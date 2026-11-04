# OCR input correction: empty text exclusions

Branch: ocr/input-correction/empty-text-exclusions-20261104.
Independent, single review commit from fixed pymupdf4llm main
363f177ef50deb05f07db8bf2061e7b9c8102b07. No prior correction is required.
Only pymupdf4llm changes; existing PyMuPDF/MuPDF APIs already handle an empty list correctly.

## Problem and change

When no normal stored spans can be excluded, the OCR caller passes rects=[].
The previous helper replaced that empty list with a page-sized rectangle,
removing all text glyphs, including the damaged glyphs OCR needed to recover.
On stock P2+ODM this occurs after the page has been selected for OCR.
An IMF2 selector that uses the same renderer can also lose its selection signal.

Pass explicit empty lists through to MuPDF so they exclude no glyphs.
An omitted/None list retains the legacy exclude-all behavior. Nonempty bbox
lists, DPI/pixel caps, blank-image checks, OCR modes, span classification,
models, language routing and downstream DET/REC settings are unchanged.
The implementation changes one condition: if not rects -> if rects is None.

## PB CF/SF result: no change in the evaluated integration

CF: 82.6712653% -> 82.6712653%, delta0.0000000 percentage points.
SF: 58.7090060% -> 58.7090060%, delta0.0000000 percentage points.

This comparison fixes the approved IMF2 ROI integration with features
0,1,2,3,4,6,7 and adds only this rendering correction. It is not a newly
measured standalone-main CF/SF result and must not be presented as one.
CF covers506 documents. SF covers476 documents, with456 defined scores.
The union contains507 original PDFs/509 pages. All507 final Markdown outputs,
all509 selection tuples and all307 Rapid RGB inputs were unchanged.
There were no changed CF/SF documents, improvements or regressions in this comparison.

Two scope details explain the unchanged scores:

- The seven original PB failures below belong to the table and layout groups;
  none belongs to the507-document CF/SF cohort.
- Symbol-damage recovery already protects their glyphs in the approved integration.
  This independent correction fixes the stock renderer without depending on that recovery.

Candidate public-API extraction was fresh for all507 PDFs. Baseline outputs
were reused after source/PDF/hash validation. Recognition was replayed only
for exact RGB/model/config matches(307 calls); the full-corpus comparison
needed no new Rapid inference. Official scores were reused only for exact
output payload/case/scorer/score-file matches(982 unique scores), then
aggregated with the fixed official scorer8c63e84. This is not a claim that
all OCR inference or all official scoring workers were rerun.

The same200-page GTv3 result is unchanged: TP99, FP10, FN1, TN90,
precision90.8257%, recall99.0000%, F1 94.7368%.
See docs/empty-text-exclusions-evaluation.txt and .json for the conditional comparison.

## Original PB failures on uncorrected2.0 main

A census of all2078 locally registered PB files(2036 PDFs+42 images,
2080 pages) found exactly seven pages with no normal exclusion spans
and visible U+FFFD-containing spans under the actual OCR callback rules:

- docs/layout/list.pdf
- docs/table/Tables - Apple Def 14a_page8.pdf
- docs/table/Tables - Apple Def 14a_page18.pdf
- docs/table/Tables - Apple Def 14a_page40.pdf
- docs/table/Tables - Apple Def 14a_page67.pdf
- docs/table/Tables - Apple Def 14a_page75.pdf
- docs/table/Tables - Apple Def 14a_page102.pdf

Each file contains one page. Baseline source is fixed PyMuPDF main
1d34e04da00b7673a0b2c3f68b5a5246793a50b8 plus the pymupdf4llm main above,
running PyMuPDF2.0/MuPDF1.28.5. No correction, IMF2 selector, symbol recovery,
input repair or writeback-font correction is included in this baseline.

All seven pages are selected by P2 with reason chars_bad. Their normal
exclusion lists are empty. Backgrounds and vectors remain after the old
page-wide culling, so Rapid runs on defective input; these are not
blank-input early returns or missing OCR calls.

Paired public-API extraction was fresh:14 extractions and14 actual Rapid
pipeline calls with fixed RapidOCR3.10.0/150DPI, no recognition replay.
These count configured DET/REC pipeline calls; recognition can be skipped
when detection returns no boxes. After the correction, all seven OCR input
RGB buffers equal their original renders and all seven Markdown outputs change.
For example, page8 produces1->38 recognized regions and15->1227 recognized
characters. These are diagnostic counts, not recall or formal quality scores.
No new CF/SF, table GTRM or layout quality score is claimed for these seven files.
The older workspace report used RapidOCR3.9.2, so its output counts may differ.

See docs/empty-text-exclusions-main-pb-cases.txt and .json for all seven
cases, source hashes, input comparisons and extraction evidence.

## Regression checks and review scope

Nine focused rendering checks cover normal text, actual U+FFFD PDF mappings,
normal/damaged mixtures, image-only pages, stored invisible text, nested Forms,
blank pages, None/full-page behavior and the existing DPI cap.
Before correction:5 failures/4 passes. After correction:all9 pass on both
fixed-main and approved-integration runtimes. A separate actual Rapid smoke
restores a four-character synthetic PDF from U+FFFD to ABCD.

Run tests/test_empty_text_exclusions.py using this branch on the import path
with a compatible PyMuPDF2.0 runtime. Use pytest --noconftest -p no:cacheprovider
to avoid the repository conftest installing unrelated packages.

This is an independent review branch. Publication does not merge it into the
approved integration or update the viewer. No wheel or package publication is needed.
No documentation-only companion branch is created in PyMuPDF.

---

This is an empty package that is required by pymupdf-2.x, in order to avoid
a pip bug that can result in a broken installation when upgrading from
pymupdf-1.x to pymupdf-2.x.

[The pymupdf-2.x package now contains the 4llm code that used to be in
pymupdf4llm-1.x.]
