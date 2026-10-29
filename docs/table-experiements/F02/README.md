# F02: Ruling and layout-grid union

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f02-ruling-gnn-union

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- PM _table_union/table, LL table_html/reconstruct 및 공개 API 연결의 main 대비 차이.
- grid_ref/union_split/union_append 권한과 bbox/grid provenance를 같이 보존함.
- 추가 승인 정책은 F05, 과분할 coherence는 F06으로 분리함. 기본 안전 계약은 포함함.
- 필수 기반: B1 및 실제 원문 소비 변경이 있으면 F01.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- B1: table-experiements/shared-runtime (revision pending).
- F01: table-experiements/f01-cell-source-output (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
