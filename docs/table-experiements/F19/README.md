# F19: PDF clip table restoration

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f19-clip-table-restoration

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- clip_evidence/geometry/restoration 및 PM _table_clip.
- 필수 기반: F01/F09/B1, 실제 괘선 생산자는 사용되는 문서 유형에 따라 연결함.
- 현재 content finalize callback이더라도 셀 귀속 정책 F17에 불필요하게 의존시키지 않음. 공통 최종 격자 후처리 연결로 분리할 수 있는지 행동 불변 검증함.
- clip 분석과 복원은 현재 하나의 완결 기능으로 유지함. 분석만 추가해 비용을 만들고 소비는 뒤 커밋에 미루지 않음.

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
