# F01: Cell source ownership and output preservation

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/f01-cell-source-output

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- PM _table_spans/_table_word_geometry/_table_font_symbols, LL cell_output_boundary/table_external_text/table_picture_content 및 소비 배선.
- 셀 생산자가 원문 참조를 만들고, 표/외부 Text/picture가 동일 참조를 소비하는 계약을 한 단위로 묶음.
- 원문 생산만 바꾸고 출력 소비를 뒤에 남기는 중간 상태의 누락/중복을 허용하지 않음.
- glyph 기호 복원과 외부 방출의 하위 효과는 별도 이벤트/fixture로 식별하되, +0.1072pp를 전체 묶음의 현재 기여로 대용하지 않음.
- 필수 기반: B1. 범위는 표와 관련된 원문/그림 소비만이며 일반 CF/SF 출력 개선은 제외함.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- B1: table-experiements/shared-runtime (revision pending).

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
