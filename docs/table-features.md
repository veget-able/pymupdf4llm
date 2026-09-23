# PyMuPDF4LLM Table 기능 명세

2026-09-23 제품 내부 이식: 아래는 동결된 기능 명세이며, PB 어댑터의 외부 설치·활성화
설명은 [제품 내부 배선 문서](native-table-pipeline.md)로 대체한다. 알고리즘·상수는 유지하고
일반 HTML 제품 API에서 실행하도록 옮겼다. OCR은 별도 브랜치다.

이 파일은 pb_table의 기능 명세에서 이 저장소의 변경과 필요한 공통 계약을 발췌한 동결본이다.
원문: PB:docs/benchmarks/table-feature-specification.md (2026-09-17). 절 번호는 원문과 같다.
PM=PyMuPDF, LL=PyMuPDF4LLM Table, OCR=별도 OCR 브랜치, PB=pb_table 실행 어댑터다.
다른 저장소 파일/기능을 여기에 이미 내장했다는 뜻은 아니다. 테스트 이름은 저장소 표기를
따르며, 별도 표기가 없는 어댑터 테스트는 PB:tests/에 있다.

커밋 메시지의 Spec 참조는 이 검수 브랜치 최종 상태에 포함된 파일을 가리킨다.
개별 중간 커밋에 모든 의존 소스와 명세가 갖춰져 있다는 뜻은 아니다.
커밋을 따로 적용할 때 Requires와 원문 보존 계약을 함께 확인한다.

## 2. 실행 위치와 기능 간 경계

```text
page text / native rules / image pixels
  -> GNN regions + retained TGIF inputs
  -> ruling candidates + admission
  -> union selection + parent-preservation decision
  -> early residual grid recovery
  -> remaining GNN regions: node-based split -> TGIF
  -> grid refinement / repeated-header split / header-band repair
  -> grid-based split: horizontal slice OR child TGIF + refinement
  -> final header roles per surviving grid
  -> fragment repair / retained-node cell recovery
  -> header roles again ONLY for changed grids
  -> source-backed external Text / HTML / layout normalization
```

모든 검출을 처음 한 번에 끝내고 모든 복원을 한 번만 하는 구조가 아니다.
원본 node 분할은 TGIF 전에, 격자 기반 분할은 셀이 생긴 뒤에야 판단 가능하다.
실제 구현은 scoped hook과 기존 refine 호출을 재사용한다. 위 순서는 의존 관계이며
각 함수가 페이지당 정확히 한 번 실행된다는 보장이 아니다.

특히 현재 **초기 잔여 복원 -> refine/R6 -> 조각 정리 -> 최종 셀 귀속** 순서를 유지한다.
조각 연결을 앞당겨 bbox 내부가 된 틈새 텍스트를 잔여에서 지우는 재배열은 승인되지 않았다.

### 3.1 추가 괘선·박스 입력 전달 — `rule-input-forwarding`

- **문제/역할**: 호출자가 전달한 선·박스가 중첩 union finder에서 빠지면 raster 등의
  추가 근거가 실제 검출에 사용되지 않는다. 기존 `add_lines`/`add_boxes`를 끝까지 전달한다.
- **입출력·위치**: PDF 페이지 좌표의 가상 선/박스 -> union 내부 괘선 후보. 좌표를 새로
  추정하거나, 입력되었다는 이유만으로 후보를 승인하지 않는다.
- **의존/재사용**: 기존 `Page.find_tables` 입력 계약과 후보 생성기 사용. 추가 추론 없음.
- **적용/제거**: 전달 계약 수정으로 항상 적용. 독립 정책 스위치 없음. 제거하면 3.3 등의
  생산자는 존재해도 소비가 끊긴다. 생산 기능과 함께 정리하지 않는 단독 제거는 권하지 않는다.
- **구현/확인**: `PM:src/_table_union.py::_union_line_candidates`,
  `PM:src/table.py::find_tables`; 제품 `tests/test_table_html.py`의 가상 입력 경로.

### 3.3 이미지 내부 괘선 검출 — `raster-rule-detection`

- **문제/역할**: PDF drawing 목록에 없는 이미지 속 가로·세로선을 찾아 기존 finder에 공급한다.
  OCR이나 셀 구조 모델을 대체하지 않는다.
- **입력**: 이미지 발생 영역, 렌더링 픽셀, 현재 페이지 단어, GNN 표 영역.
  OCR 원본 snapshot이 있으면 **선 검출 픽셀만** snapshot을 사용하며 단어는 live OCR 결과다.
- **처리/출력**: 이진 morphology·선 연결·교차 성분과 텍스트 지지를 검사한 뒤 PDF 좌표의
  `add_lines`를 반환한다. 최소 선 길이 24pt, 최대 두께 5pt 등은 경험 상수다.
- **적용/제거**: 승인 HTML 경로에서 호출한다. OpenCV가 없거나 적합한 격자가 없으면
  보충 선 없음. 독립적인 공개 on/off 옵션은 없으며 소비 호출을 분리해야 한다.
  제거 시 native 괘선/TGIF는 남지만 raster 괘선표의 복원 기회를 잃는다.
- **의존/비용**: 3.1 필수. 원본 픽셀 사용에는 OCR-2 생산자가 필요하다.
  추가 이미지 렌더링·영상 처리는 있지만 이 기능 자체가 OCR/GNN/TGIF를 호출하지 않는다.
- **구현/확인**: `LL:src/helpers/table_html/raster_lines.py::detect_raster_table_lines`;
  `tests/test_raster_ruling_ocr_pixels.py`. 원본 픽셀 계약 (원문 PB:docs/benchmarks 기준 상대 경로: ../experiments/raster-ruling-pre-ocr-pixels-20260916.md).

### 7.1 셀의 원문 참조 보존 — `table-provenance.cell-sources`

- **문제/역할**: 셀에 문자열만 남으면 어떤 원문을 썼는지 잃어 후단에서 재추정/중복한다.
  셀 생산 순간 선택한 word/character/GNN node의 실제 참조를 함께 보존한다.
- **입출력**: 기존 캐시 collection·index·좌표·scope -> `CellSource`/`source_content`.
  clone·슬라이스·연결에도 전달한다. 서로 다른 문서/페이지/부모의 같은 index는 같은 원문이 아니다.
- **경계**: 문자열 변경 후 옛 참조를 그대로 유효하게 취급하지 않는다. bbox 안에 있거나
  TGIF에 입력했다는 사실은 실제 셀 생산의 증명이 아니다.
- **적용/제거**: 정책 옵션이 아닌 생산자-소비자 데이터 계약. 외부 Text 중복 방지와
  복원 검증이 의존하므로 **단독 제거 불가**. 제거하려면 대체 원문 귀속 계약을 먼저 제공해야 한다.
- **비용/구현**: 기존 자료 참조를 전달하며 PDF 재오픈/추론 없음.
  `PM:src/_table_spans.py::SpanCell`, `PM:src/table.py`의 셀 생산;
  `LL:src/helpers/table_html/reconstruct.py`; `tests/test_cell_source_delivery.py`.

### 7.4 실제 셀 외부 원문의 일반 Text 출력 — `table-reading-order.external-text`

- **목적**: 표 처리 중 보존한 원문 중 실제 셀에서 생산되지 않은 **외부** 내용을 본문으로 남긴다.
  pending 기록만 보존하는 것은 이 기능을 구현한 것이 아니다.
- **판정**: 최종 셀과 실제 생산 참조를 사용한다. 내부 미생산/경계 교차를 문자열 불일치라는
  이유로 외부로 바꾸지 않는다. 내부인데 생산 증명이 없으면 오류를 드러낸다.
  현재 구현은 최종 셀 및 소비 원문 기하를 판정하므로 큰 table bbox 하나와 동일한 소속 규칙이 아니다.
- **출력**: 외부 word/node 단위의 text와 bbox -> 실제 `text` layout box 및 본문.
  기존 본문 span에 원문 문자 참조를 붙여 이미 출력한 occurrence는 재방출하지 않는다.
  같은 문자열이 다른 좌표에 있는 경우까지 지우는 문자열 dedup이 아니다.
- **적용/제거**: 승인 `--complete` 경로와 PyMuPDF4LLM 소비자가 함께 필요하다.
  방출만 끄면 표 점수가 같아도 원문/CF/VG 손실 가능. caption이나 pending-only로 대체하지 않는다.
  비활성화 정책을 추가한다면 외부 원문을 누가 출력할지 먼저 지정해야 한다.
- **구현/확인**: `PB:src/pb_table/cell_output_boundary.py::external_content`,
  `table_content_pipeline.py`; `LL:src/helpers/table_external_text.py`,
  `table_text_sources.py`, `get_text_lines.py`; `tests/test_span_word_sources.py`,
  `tests/test_residual_output_boundary.py`.

### 7.5 표 보존 읽기 순서·layout 연결 — `table-reading-order`

- **문제/역할**: 이미 복원한 HTML 표가 picture/큰 layout box에 흡수되거나 순서/정규화에서 탈락한다.
  개별 HTML 표의 기하와 layout 전달을 보존하고 외부 Text가 사이에 있으면 분리 배치한다.
- **범위**: 표 후보 검출·TGIF 재구성이 아니다. HTML 표 개수와 최종 layout box 개수는
  서로 다를 수 있다. 전달 box 분리를 bbox 검출 성능 향상으로 세지 않는다.
- **적용/제거**: 항상 적용되는 출력 수정, 독립 스위치 없음. 제거하면 셀 복원은 성공해도
  사용자 출력에서 표/내용이 사라질 수 있다. 원문 방출과 함께 layout/CF/VG 검사가 필요하다.
- **구현/확인**: `LL:src/helpers/document_layout.py`, `utils.py`,
  `table_html/reconstruct.py`, `table_external_text.py`; 제품 HTML 테스트와 full-503 출력 대조.

### 7.6 영역·격자·복원 출처 기록 — `table-provenance`

- **역할**: `bbox_source`, `grid_source`, `bbox_operation`, 원 GNN index, 부모/자식/복원 이력을
  구분한다. bbox가 GNN이고 grid가 find_tables인 `grid_ref`는 정상 조합이다.
- **외부/내부 구분**: public compact page JSON, 내부 TablePayload/ParsedDocument,
  분석 details는 같은 스키마가 아니다. CellSource가 있다고 `find_tables[].cell_sources`가
  공개 JSON에 전부 직렬화된다고 설명하면 안 된다.
- **적용/제거**: 진단용 상세 로그와 실제 제어 필드를 구분해야 한다. 현재 복원 그룹핑/조건은
  `source_gnn_indices`, `bbox_operation` 등에 의존하므로 provenance 전체 삭제는 행동 변경이다.
  로그만 줄이려면 제어/원문 전달 필드는 내부에 유지한다.
- **구현/확인**: `PM:src/_table_union.py`, `LL:src/helpers/document_layout.py`,
  `table_html/reconstruct.py`, ParseBench provider 전달 patch;
  `tests/test_bbox_source_recording.py`, `tests/test_restoration_handoff.py`.

## 8. 실행 기반과 최적화: 기능 정책과 별도로 판단

아래는 위 기능의 의미를 바꾸지 않고 실행 비용·중복·참조 수명을 관리하는 층이다.
“점수가 오르지 않는다”는 제거 근거가 아니다. 제거 시 의미가 같도록 대체 실행을 제공해야 한다.

- **지연 TGIF와 부모 입력 보존** (`deferred-tgif-execution`)
  - union 선택 후 필요한 영역만 resolve하며 결과 cache를 재사용한다.
    coherence 검증·실패 원복 때문에 버려질 부모도 필요시 추론한다. “최종 미채택 표는 절대 추론 안 함”은 틀리다.
  - `DeferredTGIFPipeline(deferred=False)`는 eager 비교 경로지만 승인 복원 어댑터들은
    deferred 객체/보존 입력 계약에 의존한다. 전체 stack을 그대로 두고 이 값만 바꾸는 제거는 안전하지 않다.
  - `PB:src/pb_table/deferred_tgif.py`; `tests/test_deferred_tgif.py`.
- **원본 edge 확률 전달** (`gnn-edge-evidence`)
  - 기존 GNN 결과를 전달할 뿐 새 추론이 아니다. 원 node ID 대응을 유지한다.
    node 분할을 유지하면서 이 정보를 삭제하면 입력 계약이 깨진다.
  - `PB:src/pb_table/gnn_edge_evidence.py`; `tests/test_gnn_edge_evidence.py`.
- **공용 helper/실행 경계**
  - `child_inputs`, `vg_rule_primitives`, `refine_child`, `_cells_to_rows`,
    `_collect_graphic_evidence` 등을 공유한다. 이름이 비슷하지만 계약이 다른 clustering은 억지 통합하지 않는다.
  - 이들은 옵션이 아니다. 제거가 목적이면 동일 계약 구현을 실제 소비자에 제공해야 한다.
- **같은 상태의 자료 재사용**
  - union text span, drawings, word 선택 index, placements matrix, output rows,
    grid split signals, union selection plan을 공유한다.
  - OCR/회전/flags 또는 split/stitch/내용 변경 후에도 무조건 cache를 재사용하지 않는다.
  - 관련 소스: `PM:src/table.py`, `_table_refine.py`, `_table_union.py`;
    `LL:src/helpers/table_html/reconstruct.py`; `PB:src/pb_table/material_split_rules.py`.
  - 관련 테스트: `test_drawing_sharing.py`, `test_word_search.py`, `test_grid_result_sharing.py`,
    `test_union_selection_sharing.py`, `test_refine_execution_sharing.py`.
- **헤더 실행 비용 감소**
  - HTML 경로에서 불필요한 공개 `_get_header` 호출 생략. 공개 header/Markdown/pandas 계약은 유지한다.
  - R6 입력을 기존 격자에서 직접 만들고 page 문자를 같은 상태에서 공유한다.
    교체될 부모의 R6는 지연하며 살아남는 부모·새 자식은 필요한 판정을 받는다.
  - 관련 소스: `PM:src/table.py`, `PB:src/pb_table/r6_header.py`, `r6_header_contract.py`,
    `direction_reconstruct_split.py`; `test_html_header_omission.py`, `test_r6_character_sharing.py`,
    `test_r6_direct_input.py`, `test_r6_parent_delay.py`.

현재 어댑터는 scoped process-local patch를 사용하며 같은 process에서 동시 실행하는
thread-safe 제품 API로 검증된 것이 아니다. 독립 process worker 사용 계약을 유지한다.

## 10. 선택·제거 검수 계약

1. 선택 단위는 위 기능/하위 액션으로 적는다. “V9 제거”처럼 구현 시점만 지정하지 않는다.
2. 독립 switch가 없는 항목은 먼저 **자료 전달을 유지한 행동 bypass**가 가능한지 본다.
   이 명세는 그러한 switch를 새로 구현한 문서가 아니다.
3. 삭제하는 기능의 소비자 목록을 확인한다. R6 제거 시 join/split-integrity,
   source 참조 제거 시 내부 복원 검증·외부 dedup까지 영향을 받는다.
4. 기본 계약: 좌표/원 node 대응, 실제 producer 참조, 생존 표의 R6,
   기존 내용 보존, None/empty·결측/0 구분. 기능 비활성화를 이유로 실패를 숨기지 않는다.
5. 동일 503 full 비교에서 GTRM/CON/TRM, 페이지 회귀, 실제 HTML·원문·bbox 변경을 본다.
   원문 방출/영역 선택/읽기 순서 변경이면 CF/VG/DocLayNet 관련 범위도 확인한다.
6. 비기능 refactoring/최적화만 바꾸는 경우 점수뿐 아니라 raw/normalized 출력 동등성을 요구한다.
   성능은 별도 반복 측정하며 기존 결과를 새 하드웨어 속도 보장으로 쓰지 않는다.
7. 개발 데이터에서 조정한 상수와 양식 특이 신호는 위에 공개했다. GT를 runtime에서 안 읽는다고
   overfit 가능성이 없어진 것은 아니다. 실제 제거/독립 ablation을 하지 않은 효과는 미측정이다.

## 검증 범위

제품/어댑터/OCR을 합친 승인 stack은 full-503에서 GTRM 0.8098682258124252이며,
정본과 503개 raw 출력·정규화 출력·페이지별 지표가 같았다. 이는 최종 조합 검증이며
이 저장소 단독 또는 각 중간 커밋의 독립 기여도/비회귀 검증은 아니다.
기존 실행: PB:runs/review-branches-20260917/full. 메시지·문서만 변경한 뒤
제품 소스/테스트 tree 동일성을 별도로 확인한다. 원격 push/PR은 수행하지 않는다.
전체 어댑터 시험 476 통과/6 skip, 제품 경계 16 통과, HTML 13 통과는 이전 조합의
검증 범위다. 새로운 성능·일반화 측정으로 취급하지 않는다.
