# I-B: Pre-OCR raster ruling image delivery

Status: specification draft. No runtime implementation or benchmark result is included in this commit.

Branch: table-experiements/pre-ocr-ruling-image

Base: pymupdf4llm main at 363f177ef50deb05f07db8bf2061e7b9c8102b07.

## Scope and execution boundary

- 원본 displaylist 전달과 raster cache 무효화의 기존 B 수정. OCR 글자를 괘선용 이미지에 다시 그리지 않음.
- A/B는 표 정책의 성과에 숨겨 넣지 않음. 각각 기능 변경 페이지와 누적 baseline 변화도 기록함.
- A/B는 이번 제품의 기존 입력 계약 범위만 포함함. OCR 모델/언어/일반 출력 개선은 가져오지 않음. 다른 OCR 담당자 브랜치를 변경하지 않음.

## Dependencies

The following are proposed dependencies, not merged or independently validated revisions. Only necessary contracts are reused; unrelated policies must not be imported.

- No additional feature dependency is currently proposed; compatibility with main still requires validation.

## Validation and page-level attribution

Follow [the evaluation contract](../evaluation-contract.json). For the initial implementation, compare against the same main and pinned prerequisite combination. For later changes, compare against this feature’s previous validated revision with identical dependencies.

List every improved and regressed page, score-neutral output change, and per-metric regression. Keep TP loss/recovery identities, bbox/cell/header changes, original-source ownership and text output evidence. A positive aggregate or preserved table count does not prove preservation. No page improvement or regression has been measured for this draft.

## Continued development

Add implementation, wiring, tests and updated evidence in subsequent commits on this branch. Record compatibility pairs for cross-repository changes. Merge prerequisite updates explicitly and measure their effect separately. The working revision may be newer than the validated revision; do not report unmeasured work as validated. Do not create product feature flags merely to stage the port.

The [branch index](../README.md) links the related feature drafts. Existing production branches remain unchanged.
