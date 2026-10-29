# F17: Retained-node cell ownership

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f17-cell-ownership-restoration

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- table_content_recovery/grid_ownership 및 실제 수용 검증·실패 원복.
- 필수 기반: F16의 전달 계약, F01/F09. F16 정책을 빼고도 가능하게 하려면 부모 취득/전달만 B1로 옮길 수 있는지 검증하되, 중복 parent 취득을 만들지 않음.
- 후속 F18/clip 없이도 유효 셀/잔여 출력이 완결돼야 함. 안전한 독립성이 없으면 F16과 병합 후 기능 표를 갱신함.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- F16: table-experiements/f16-union-fragment-restoration (revision pending).
- F01: table-experiements/f01-cell-source-output (revision pending).
- F09: table-experiements/f09-r6-header-classification (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
