# F07: Node and edge region splitting

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f07-node-edge-region-split

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- header_region_split/v7_region_rules/region_partition 및 기존 node/edge evidence 전달.
- 필수 기반: B1, F02. R6를 포함하지 않는 기능 브랜치에서도 main의 기존 유효 헤더 경로로 실행 가능해야 함.
- R6가 구조 선택의 실제 필수 조건인 부분이 발견되면 F09를 선행하도록 순서를 조정하고 의존 원장에 기재함.
- V7 기존 회귀를 숨기지 않으며 분할 전체 해제를 목표로 하지 않음.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- B1: table-experiements/shared-runtime (revision pending).
- F02: table-experiements/f02-ruling-gnn-union (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
