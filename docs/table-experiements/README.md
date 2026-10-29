# Table feature development branches
Each branch starts directly from the pinned main commit of its repository. The initial drafts specify scope, dependencies and evaluation contracts; they do not implement the feature. See the feature manifest on its own branch for the current implementation and validation status.
The `table-experiements/` namespace is intentional. No draft PR is created. Runtime changes belong to subsequent commits on the same feature branch.
Pinned main pair: PyMuPDF 1d34e04da00b7673a0b2c3f68b5a5246793a50b8; pymupdf4llm 363f177ef50deb05f07db8bf2061e7b9c8102b07.
Required dependency revisions are merged explicitly and recorded as compatible source pairs. A draft branch is not a production release or a measured quality improvement.
## Branch index
- B1: Shared table runtime and evidence contracts — [pymupdf](https://github.com/veget-able/PyMuPDF/tree/table-experiements/shared-runtime); [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/shared-runtime)
- I-A: OCR empty-list and None contract — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/ocr-empty-list-contract)
- I-B: Pre-OCR raster ruling image delivery — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/pre-ocr-ruling-image)
- F01: Cell source ownership and output preservation — [pymupdf](https://github.com/veget-able/PyMuPDF/tree/table-experiements/f01-cell-source-output); [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f01-cell-source-output)
- F02: Ruling and layout-grid union — [pymupdf](https://github.com/veget-able/PyMuPDF/tree/table-experiements/f02-ruling-gnn-union); [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f02-ruling-gnn-union)
- F03: Thin filled rectangles and painted vector strokes — [pymupdf](https://github.com/veget-able/PyMuPDF/tree/table-experiements/f03-vector-rule-recovery)
- F04: Raster ruling extraction — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f04-raster-ruling)
- F05: Independent table admission — [pymupdf](https://github.com/veget-able/PyMuPDF/tree/table-experiements/f05-table-admission)
- F06: Union split coherence — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f06-union-split-coherence)
- F07: Node and edge region splitting — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f07-node-edge-region-split)
- F08: Repeated-header table splitting — [pymupdf](https://github.com/veget-able/PyMuPDF/tree/table-experiements/f08-repeated-header-split)
- F09: R6 header classification — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f09-r6-header-classification)
- F10: Header leaf completion — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f10-header-leaf-completion)
- F11: Header role demotion — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f11-header-role-demotion)
- F12: Year-row header completion — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f12-year-row-header)
- F13: Parent and leaf header-band splitting — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f13-header-band-split)
- F14: Directional grid splitting and reconstruction — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f14-directional-grid-split)
- F15: Split integrity and parent restoration — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f15-split-integrity)
- F16: Union residual and fragment restoration — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f16-union-fragment-restoration)
- F17: Retained-node cell ownership — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f17-cell-ownership-restoration)
- F18: Ruled leading-row recovery — [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f18-ruled-leading-row)
- F19: PDF clip table restoration — [pymupdf](https://github.com/veget-able/PyMuPDF/tree/table-experiements/f19-clip-table-restoration); [pymupdf4llm](https://github.com/veget-able/pymupdf4llm/tree/table-experiements/f19-clip-table-restoration)

## Revision policy

Add implementation, focused tests and feature notes in the same scope. Append commits on this branch; do not create a new branch for each experiment. Keep development and validated revisions distinct. Do not attribute dependency updates to this feature. Preserve the existing production branches. Final product adoption and PR creation are separate.
