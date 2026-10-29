# F15: Split integrity and parent restoration

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f15-split-integrity

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- split_integrity_eligible/revert_broken_splits와 source scope 보호.
- 필수 기반: F07 또는 대상 분할 생산자, B1의 원부모 재료, F09. year_rows와는 의존 없음.
- 후단 방어가 없는 F07만의 회귀와 방어 추가 후 회복을 둘 다 기록함.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- B1: table-experiements/shared-runtime (revision pending).
- F07: table-experiements/f07-node-edge-region-split (revision pending).
- F09: table-experiements/f09-r6-header-classification (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
