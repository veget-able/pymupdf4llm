# F16: Union residual and fragment restoration

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f16-union-fragment-restoration

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- union_content_recovery + fragment_consolidation의 join/revert, RestorationContext 전달.
- 현재 R 단계가 보관한 parent/residual을 C가 소비함. 이를 단순 파일 분리만으로 독립 기능이라고 설명하지 않음.
- 실제 순서 R→refine/R6→C, 원조각 R6 판정 고정, 시도/수용/미확정 구분을 함께 유지함.
- 필수 기반: F02/B1/F01/F09. S0/S1/S1'/S2/join/revert 하위액션은 이벤트로 구분하고 하나의 검수 단위로 평가함.
- 향후 독립 소비 계약을 변경해 R/C를 떼는 별도 설계는 이번 커밋 분할의 필수 목표가 아님.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- B1: table-experiements/shared-runtime (revision pending).
- F01: table-experiements/f01-cell-source-output (revision pending).
- F02: table-experiements/f02-ruling-gnn-union (revision pending).
- F09: table-experiements/f09-r6-header-classification (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
