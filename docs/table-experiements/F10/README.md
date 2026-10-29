# F10: Header leaf completion

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f10-header-leaf-completion

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- header_leaf_completion의 leaf_completion_depth와 R6 호출부·테스트.
- 필수 기반: F09. 공통 occupancy를 복제하지 않음.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- F09: table-experiements/f09-r6-header-classification (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
