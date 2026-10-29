# F04: Raster ruling extraction

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f04-raster-ruling

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- LL raster_lines 및 add_lines 전달. 현재 채택 Sobel 구현 한 개만 포함함.
- Canny→Sobel 과거 개발 순서를 여러 제품 기능으로 재연하지 않음.
- 필수 기반: I-B, F02의 선 입력 전달. I-A는 제품 공통 입력 기준으로 유지함.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- B1: table-experiements/shared-runtime (revision pending).
- F02: table-experiements/f02-ruling-gnn-union (revision pending).
- I-B: table-experiements/pre-ocr-ruling-image (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
