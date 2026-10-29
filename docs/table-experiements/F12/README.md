# F12: Year-row header completion

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f12-year-row-header

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- year_row_depth 및 R6 호출부. 구조 손상/부모 복원과 목적·실행 위치가 다르므로 분리함.
- 필수 기반: F09. F10/F11과 공유 occupancy 및 최종cap 계약을 유지함.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- F09: table-experiements/f09-r6-header-classification (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
