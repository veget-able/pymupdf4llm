# B1: Shared table runtime and evidence contracts

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/shared-runtime

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- 기존 runtime scope, deferred TGIF 수명·결과 재사용, 원 parent/node/edge 참조, provenance, shared word/drawing/grid 자료를 실제 소비 위치에 연결함.
- 새 정책 없이 main 동작이 유지되는 부분만 공통 기반 커밋으로 분리함. 독립 소비자가 없는 빈 wrapper/미래 전용 framework는 넣지 않음.
- 행동 불변으로 분리할 수 없는 기반 변경은 최초 실제 소비 기능 커밋에 포함하고 함께 평가함.
- 현재 불필요한 클래스 상속 의존은 최소 배선 변경으로 제거하되 R→refine/R6→C의 실제 실행 순서를 바꾸지 않음.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- No additional feature dependency is currently proposed; compatibility with main still requires validation.

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
