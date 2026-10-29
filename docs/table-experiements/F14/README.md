# F14: Directional grid splitting and reconstruction

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f14-directional-grid-split

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- direction/grid_reconstruct_split, material_split_rules, placement partition.
- 가로 slice와 이형 child-TGIF는 같은 분할/복원 선택 계약이므로 현재 단위 유지함.
- 필수 기반: F01/B1/F09. V7 상속을 제거해도 node 분할 정책 자체가 필요한지 별도 검사함. 실제 필수이면 F07 명시함.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- B1: table-experiements/shared-runtime (revision pending).
- F01: table-experiements/f01-cell-source-output (revision pending).
- F09: table-experiements/f09-r6-header-classification (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
