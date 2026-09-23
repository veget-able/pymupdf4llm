# Native HTML table pipeline (review integration, 2026-09-23)

## What this changes

This branch makes the September 17 reviewed table composition run inside the
products. Installing only the earlier Table branches did **not** activate the
algorithms hosted by the research runner. The public HTML path now activates
them automatically; no `pb_table` install, PYTHONPATH entry, runner, saved HTML,
benchmark data, or monkeypatch is required at inference time.

The reference is the reviewed **80.98682258124252% GTRM** composition. Later M1
and other research candidates are deliberately not included. This is an
integration/parity change, not a new table algorithm or a new generalization
claim. The older `table-features.md` is the frozen feature specification; this
document updates its implementation-location and activation statements.

## Usage and dependencies

Install the paired `review/table-native-20260923` branches of PyMuPDF and
PyMuPDF4LLM, with the matching reviewed Layout runtime. The PyMuPDF private hook
module is required; an unmodified upstream PyMuPDF wheel is not interchangeable.
The paired PyMuPDF integration commit is `e4179c71` on review base `37deea5b`;
this PyMuPDF4LLM branch extends review base `83df76a1`.

```python
import pymupdf4llm

chunks = pymupdf4llm.to_markdown(
    "input.pdf", page_chunks=True, table_output="html", show_progress=False,
)
```

The shared layout parser also activates this pipeline for its HTML-table JSON
path. Plain Markdown table rendering does not activate it. Standalone PyMuPDF
`Page.find_tables()` keeps its existing behavior without an active consumer;
installing this branch does not make PyMuPDF depend on PyMuPDF4LLM or ONNX.

NumPy and ONNX Runtime are explicit PyMuPDF4LLM dependencies. The R6 model is
bundled in the wheel at `_table_pipeline/models/fang-header-rf-r6.onnx`, loaded
once per process with CPU inference and float64 `[N, 19]` input. Its documented
feature order, prefix decoder and missing-value guard are unchanged.

**OCR remains separate.** The 80.9868% reference uses the independent
`review/ocr-input-fixes-20260917` change (`229e96d0c32da5de1a968dbf5b5f56ed07996ae0`)
and RapidOCR at 150 DPI, with `PYMUPDF_MAX_OCRSIZE=10`. Apply that branch separately
to reproduce OCR-page results; these Table commits do not modify `src/ocr`.
Changing OCR, the Layout model or evaluation settings invalidates exact parity.

## Feature ownership and execution boundaries

- **GNN node/edge region splitting**: `header_region_split.py`,
  `v7_region_rules.py`, `gnn_edge_evidence.py`. Existing GNN probabilities and
  node IDs are captured from the original inference. Deferred TGIF runs on the
  retained parent or on genuinely changed child crops, not both indiscriminately.
- **Directional grid splitting**: `grid_reconstruct_split.py`,
  `direction_reconstruct_split.py`, `material_region_split.py`,
  `material_split_rules.py`. Horizontal parts slice existing placements;
  heterogeneous parts reconstruct child inputs. A cut through a merged cell
  is rejected by the existing partition contract.
- **Union coherence and early residual recovery**:
  `union_split_coherence.py`, `union_content_recovery.py`. Decisions stay at
  union selection, with the reviewed gates and constants. Parent predictions
  and source nodes survive for the later consumers.
- **Final header roles and structural header repair**: `r6_header.py`,
  `r6_header_contract.py`, `header_leaf_completion.py`, `header_role_demotion.py`,
  `header_band_split.py`. Includes reviewed leaf completion, common-note/section
  demotion, year rows and header-band repair. Roles are delayed for discarded
  parents and recomputed only when the surviving placements change.
- **Fragment and source-backed content restoration**:
  `fragment_consolidation.py`, `table_content_pipeline.py`,
  `table_content_recovery.py`, `grid_ownership.py`, `ruled_leading_row.py`,
  `cell_output_boundary.py`, `table_restoration.py`. Keeps join/revert,
  split-integrity, supported cell recovery and external text delivery in their
  existing order. Attempted handling is not relabelled as proven cell acceptance.
- **Shared data/helpers**: `child_inputs`, `vg_rule_primitives`,
  `partition_placements`, native placement matrices, existing word/ruling caches,
  retained deferred predictions and live post-OCR R6 character cache are reused.
  The R-stage parent entry is passed to C, not independently acquired again.

No new PDF reopening, OCR pass, GNN pass or generic reconstruction algorithm
was introduced by the integration. Existing reviewed extraction/reconstruction
work remains. No claim is made that every extraction in that composition is
already globally deduplicated. Removing an individual behavior still requires
respecting the dependencies described in `table-features.md`; these commits do
not introduce arbitrary independent feature switches.

## Lifecycle and error behavior

`runtime.py` owns a document-local pipeline. PyMuPDF provides private boundaries
for layout prediction, union and refinement via a ContextVar. The cached Layout
model's methods are never patched: a local model/extractor view captures edges
and defers TGIF while sharing immutable weights/session resources.

There are no external `unittest.mock` runtime patches or mutable global recovery
ledgers. Context and character-cache scopes reset on exception. Restoration
errors cannot silently become successful empty pages. The inherited PyMuPDF
geometry machinery still uses process-global settings, so enhanced HTML calls
are serialized within a process; use independent processes for parallel work.
This does not certify unrelated simultaneous raw PyMuPDF calls as thread-safe.

## Verification and limitations

- Full Table503, ordinary product API: 503 successes, zero failures.
- Raw and normalized outputs: **503/503 equal** to the reviewed composition.
- GTRM: `0.8098682258124252`; GriTS_CON: `0.8856166354231998`;
  TRM: `0.7091856091907063`. These equal the reference, not isolated feature gains.
- Product contracts: 159 tests across the two repositories; algorithm tests plus
  native activation, exception cleanup, model immutability, repeated multipage
  calls, model input contract and package inclusion.
- PyMuPDF4LLM wheel built using its actual build backend, including all modules
  and the model; the wheel is exercised with the separate OCR composition.
  The second full503 run (`full-wheel-02`) also has 503/503 raw/normalized
  equality, zero failures and exactly the same three official aggregate scores.
- The reviewed compiled MuPDF (`5fe54cef1e233e4823ae743eacd00c35e96f1062`) and Layout
  (`b6e83e8b55bf861c45e259762483f6863688ed16`) binaries were reused. This does not
  validate a new C engine, an arbitrary current upstream Layout wheel, or other
  platforms. PyMuPDF source packaging includes the new hook and the two previously
  omitted word-geometry/font-symbol modules; a new native C build was not performed.
- No new CF/VG/DocLayNet quality claim or speedup claim. Full503 is the development
  parity corpus, not a new held-out generalization test.

Local reproduction artifacts live in the research workspace under
`runs/table-native-20260923/`: `validate.py`, `full-01/parity.json`, the official
evaluation report under `full-01/pymupdf4llm_html_tables_rapidocr_v3/`,
`full-wheel-02/`, and `tests.log`. Those datasets and run outputs are not shipped
inside the product. Tests in this repository run with installed paired products:

```sh
python -m pytest --noconftest -c /dev/null -p no:cacheprovider tests/test_table_pipeline -q
```

Both review branches are local additions to their September 17 review bases.
Publishing branches and creating PRs are separate actions, not performed here.
