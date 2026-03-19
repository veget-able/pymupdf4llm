# Testing & Visualization Guide

이 문서는 layout-aware chunking 파이프라인의 테스트 체계와 시각화 도구 사용법을 설명합니다.

## 디렉토리 구조

```
<project-root>/
├── test/
│   ├── test_chunking.py                    # 메인 테스트 스위트 (T1–T9)
│   ├── test_reading_order_issue.py         # 읽기 순서 이슈 재현 테스트
│   ├── *.pdf / *.json                      # DocLayNet 테스트 PDF 10종 + 라벨
│   └── TESTING.md                          # ← 이 파일
├── chunk_visualizer.py                     # GUI 시각화 도구
└── pymupdf4llm/
    └── tests/
        └── test_370.pdf / test_370_expected.md   # 기존 회귀 테스트 데이터
```

---

## 테스트 실행 방법

### 전체 테스트 실행

```bash
cd <project-root>
python -m pytest test/test_chunking.py -v
```

### 특정 테스트 그룹만 실행

```bash
# T1 (Smoke tests)만 실행
python -m pytest test/test_chunking.py -v -k "t1_"

# T7 (Integration tests)만 실행
python -m pytest test/test_chunking.py -v -k "t7_"

# T9 (Metrics report)만 실행 — 콘솔 출력 확인
python -m pytest test/test_chunking.py -v -k "t9_" -s
```

### 읽기 순서 이슈 테스트

```bash
python -m pytest test/test_reading_order_issue.py -v
```

---

## test_chunking.py — 테스트 구조 (T1–T9)

### T1. Smoke Tests

기본 동작 확인. `to_chunk()`이 `list[FinalChunk]`을 반환하는지, dict 출력 포맷이 올바른지, 빈 PDF와 단일 페이지 PDF를 처리하는지 검증합니다.

| 테스트 ID | 설명 |
|---|---|
| T1.1 | `to_chunk(pdf)` → `list[FinalChunk]` 반환 |
| T1.2 | `output_format='dict'` → 필수 키 포함 확인 |
| T1.3 | `parsed.to_chunks()` == `to_chunk()` 결과 일치 |
| T1.4 | 빈 PDF → 빈 리스트, 예외 없음 |
| T1.5 | 단일 페이지 PDF → 최소 1개 청크 |

### T2. SentenceBuilder Unit Tests

문장 생성기의 개별 기능을 Mock 객체로 테스트합니다.

| 테스트 ID | 설명 |
|---|---|
| T2.1a–h | `boxclass` → hint 매핑 (title, section-header, list-item, table, picture, footnote, page-header/footer, text) |
| T2.2 | 하이픈 줄바꿈 복원 (`hyphen-\nated` → `hyphenated`) |
| T2.3 | PDF 줄바꿈 → 공백 정규화 |
| T2.4 | 문장 분리 정확도 (2문장 → 2 SentenceUnit) |
| T2.5 | 제목(title)은 마침표가 있어도 분리하지 않음 |
| T2.6 | 테이블 → 단일 유닛, `table_markdown` 보존 |
| T2.7 | 그림(picture) → `[Figure: WxH]` 플레이스홀더 |
| T2.8 | 반복 머리글/바닥글 감지 (3페이지 이상 동일 텍스트) |
| T2.9 | 폰트 메트릭 (`font_size_dominant > 0`) |
| T2.10 | TOC 매칭 heading level |

### T3. BoundaryScorer Unit Tests

경계 점수 계산기의 각 시그널을 독립적으로 검증합니다.

| 테스트 ID | 설명 |
|---|---|
| T3.1 | 같은 박스 → 낮은 점수 |
| T3.2 | 박스 변경 → `w_box` 반영 |
| T3.3 | boxclass 변경 → `w_class` 반영 (최고 단일 시그널) |
| T3.4 | 페이지 변경 → `w_page` 반영 |
| T3.5 | 수직 갭 점프 (중앙값 3배) |
| T3.6 | 폰트 크기 점프 |
| T3.7 | 제목 진입 → 점수 증가 |
| T3.8 | 리스트 연속 → 점수 억제 |
| T3.9 | 테이블 내부 → 점수 억제 (≤0) |
| T3.10 | 모든 점수 유한 (NaN/Inf 없음) |

### T4. ChunkAssembler Unit Tests

청크 조립기의 분할, 병합, 타입 판정 로직을 테스트합니다.

| 테스트 ID | 설명 |
|---|---|
| T4.1 | 임계값 초과 시 분할 |
| T4.2 | `max_tokens` 예산 준수 (refine 후) |
| T4.3 | `table_mode='preserve'` → 대형 테이블도 단일 청크 유지 |
| T4.4 | 제목 → 항상 새 청크 시작 |
| T4.5 | 그림 → 독립 청크 |
| T4.6 | 과대 청크 → refine에서 문장 경계 분할 |
| T4.7 | 과소 청크 → 호환 이웃과 병합 |
| T4.8 | paragraph ↔ table 병합 금지 |
| T4.9 | 2페이지 이상 떨어진 청크 병합 금지 |
| T4.10 | `chunk_type_hint` 정확성 (table, list, figure, heading, paragraph) |
| T4.11 | refine 후 `chunk_id` 연속성 (0..N-1) |

### T5. ChunkSerializer Unit Tests

직렬화기의 출력 형식, heading_path, contextual_text, 이웃 연결을 검증합니다.

| 테스트 ID | 설명 |
|---|---|
| T5.1 | `chunk_id` 포맷 (`c0`, `c1`, ...) |
| T5.2 | TOC 기반 `heading_path` 생성 |
| T5.3 | TOC 없음 → `heading_path` 빈 리스트 |
| T5.4 | `contextual_text`에 `[Page]`, `[Content]` 포함 |
| T5.5 | heading_path → `[Section]` 태그 |
| T5.6 | 테이블 → `[Type] table` 태그 / paragraph → `[Type]` 없음 |
| T5.7 | `window_size` 기반 prev/next 이웃 |
| T5.8 | 첫 청크 prev 없음, 마지막 청크 next 없음 |
| T5.9 | `related_figure_chunk_id` 연결 |
| T5.10 | `related_table_chunk_id` 연결 |
| T5.11 | `metadata.file_path`, `page_count` 정확성 |

### T6. TokenCounter Unit Tests

| 테스트 ID | 설명 |
|---|---|
| T6.1 | 빈 문자열 → 0 |
| T6.2 | fallback 추정값 > 0 |
| T6.3 | 커스텀 함수 (`lambda t: len(t)`) |
| T6.4 | tiktoken `cl100k_base` (설치 시) |

### T7. Integration Tests (DocLayNet 10 PDFs)

10종의 DocLayNet PDF 전체를 대상으로 실제 파이프라인을 검증합니다.

| 테스트 ID | 설명 |
|---|---|
| T7.1 | 모든 PDF → 에러 없이 `list[FinalChunk]` 반환 |
| T7.2 | 모든 청크 텍스트 비어있지 않음 |
| T7.3 | `page_start ≤ page_end` |
| T7.4 | 테이블 포함 PDF → `chunk_type_hint='table'` 존재 |
| T7.5 | 그림 포함 PDF → `figure` 청크 + `related_figure_chunk_id` |
| T7.6 | 리스트 포함 PDF → `chunk_type_hint='list'` 존재 |
| T7.7 | `max_tokens` 작을수록 청크 수 증가 |
| T7.8 | `header_footer_mode='exclude'` → 청크 수 감소 또는 동일 |
| T7.9 | `merge_small_chunks=False` → 청크 수 증가 또는 동일 |
| T7.10 | `window_size=0` → prev/next 이웃 모두 빈 리스트 |
| T7.11 | `window_size=3` → 중간 청크에 prev/next 각 3개 |

### T8. Regression Tests

기존 pymupdf4llm 기능(to_markdown, to_json, to_text)이 변경되지 않았는지 확인합니다.

| 테스트 ID | 설명 |
|---|---|
| T8.1 | `to_markdown` 출력 `test_370_expected.md`와 일치 |
| T8.2 | `to_markdown(page_chunks=True)` → `list[dict]` with `metadata`/`text` |
| T8.3 | `to_json()` → 유효한 JSON 문자열 |
| T8.4 | `to_text()` → 비어있지 않은 문자열 |

### T9. Quantitative Metrics Report

하드 assertion 없이 품질 메트릭을 콘솔에 출력합니다. `-s` 플래그로 실행해야 출력이 보입니다.

보고 항목:
- 총 청크 수, 평균 토큰 수
- `min_tokens` 미만 / `max_tokens` 초과 비율
- 테이블/그림 청크 통계
- heading_path 부착률
- 페이지 교차 청크 수
- DocLayNet label ↔ boxclass 일치율
- PDF별 상세 통계

---

## test_reading_order_issue.py

PyMuPDF의 읽기 순서 이슈를 재현하고 문서화하는 테스트입니다.

**대상 PDF**: `0096e871...pdf` — 가로 2단 레이아웃

**문제**: PyMuPDF가 왼쪽 칼럼의 `(a)` 항목 다음에 오른쪽 칼럼 전체를 배치하고, `(b)` 항목을 맨 마지막에 놓아 읽기 순서가 깨집니다.

| 테스트 클래스 | 설명 |
|---|---|
| `TestDocumentLayout` | 가로 레이아웃, 2단 분리 확인 |
| `TestReadingOrderAnomaly` | (a)→(b) 순서 깨짐 문서화 |
| `TestBoundaryScorerColumnBreak` | 칼럼 전환 시 경계 점수 > 임계값 확인 |
| `TestMergeColumnIsolation` | (b) 항목이 오른쪽 칼럼과 병합되지 않음 확인 |

---

## Chunk Visualizer

`chunk_visualizer.py`는 PDF 페이지 위에 DocLayNet 라벨과 청킹 결과를 오버레이하여 시각적으로 비교하는 GUI 도구입니다.

### 실행

```bash
cd <project-root>
python chunk_visualizer.py
```

> **필수 의존성**: `Pillow` (`pip install Pillow`)

### 기능

- **PDF 선택**: 오른쪽 사이드바에서 `test/` 디렉토리의 PDF 파일 목록을 클릭
- **Label 오버레이**: DocLayNet JSON 라벨을 반투명 색상 박스로 표시
- **Chunk 오버레이**: `pymupdf4llm.to_chunk()` 결과를 점선 박스로 표시 (백그라운드 스레드에서 처리)
- **레이어 토글**: 상단 체크박스로 Label/Chunk 레이어를 개별 on/off
- **DPI 변경**: 72 / 150 / 200 DPI 선택 가능
- **청크 상세 보기**: 청크 박스에 마우스를 올리면 사이드바에 chunk_id, type, page, 전체 텍스트 표시
- **범례**: Label 색상(text, section-header, table 등)과 Chunk 색상(paragraph, heading, table 등) 범례 제공

### 색상 범례

**Label Colors** (DocLayNet 라벨 — 채움):

| 카테고리 | 색상 |
|---|---|
| text | 파랑 (#4285F4) |
| section-header | 빨강 (#EA4335) |
| list-item | 초록 (#34A853) |
| table | 주황 (#FF6D00) |
| picture | 보라 (#AB47BC) |
| caption | 청록 (#00ACC1) |
| title | 노랑 (#FFD600) |
| footnote | 갈색 (#8D6E63) |
| page-header / page-footer | 회색 |

**Chunk Colors** (청킹 결과 — 점선):

| 타입 | 색상 |
|---|---|
| paragraph | 진한 파랑 (#1565C0) |
| heading | 진한 빨강 (#C62828) |
| table | 진한 주황 (#E65100) |
| list | 진한 초록 (#2E7D32) |
| figure | 진한 보라 (#6A1B9A) |
| footnote | 진한 갈색 (#4E342E) |

### 사용 팁

1. **Label과 Chunk 비교**: 두 레이어를 번갈아 켜면서 DocLayNet 라벨이 chunking 결과와 얼마나 일치하는지 확인
2. **DPI 조정**: 세밀한 박스 확인이 필요하면 200 DPI, 전체 조감은 72 DPI
3. **이슈 추적**: 청크가 예상과 다르게 분할/병합되었을 때 Label 오버레이로 원인 파악

---

## 테스트 데이터

### DocLayNet 10 PDFs

`test/` 디렉토리에 위치한 10종의 DocLayNet PDF와 대응하는 JSON 라벨 파일:

- 각 PDF는 SHA-256 해시 기반 파일명
- JSON 파일에는 `annotations` 배열이 포함되며, 각 항목에 `category_name`과 `bbox_pdf` (PDF 좌표) 제공
- 테이블, 그림, 리스트, 머리글/바닥글 등 다양한 레이아웃 요소 포함

### 기존 회귀 데이터

- `pymupdf4llm/tests/test_370.pdf` — `to_markdown` 회귀 비교용 원본 PDF
- `pymupdf4llm/tests/test_370_expected.md` — 기대 출력
