# PyMuPDF4LLM OCR 기능 명세

이 파일은 pb_table의 기능 명세에서 이 저장소의 변경과 필요한 공통 계약을 발췌한 동결본이다.
원문: PB:docs/benchmarks/table-feature-specification.md (2026-09-17). 절 번호는 원문과 같다.
PM=PyMuPDF, LL=PyMuPDF4LLM Table, OCR=별도 OCR 브랜치, PB=pb_table 실행 어댑터다.
다른 저장소 파일/기능을 여기에 이미 내장했다는 뜻은 아니다. 테스트 이름은 저장소 표기를
따르며, 별도 표기가 없는 어댑터 테스트는 PB:tests/에 있다.

커밋 메시지의 Spec 참조는 이 검수 브랜치 최종 상태에 포함된 파일을 가리킨다.
개별 중간 커밋에 모든 의존 소스와 명세가 갖춰져 있다는 뜻은 아니다.
커밋을 따로 적용할 때 Requires와 원문 보존 계약을 함께 확인한다.

## 9. OCR 전용 기능: Table 브랜치와 별도

### OCR-1. 깨진 native 텍스트를 지우지 않고 OCR — `broken-native-text-ocr`

- **문제**: culling할 native span이 0개인 `[]`를 `None`과 같게 처리해 모든 native 문자를
  OCR 이미지에서 지운다. 깨진 문자도 이미지에서는 읽히는데 인식 입력이 사라진다.
- **수정**: `[]`는 아무 span도 지우지 않음, `None`은 기존 전체 text culling 의미 유지.
  `/ToUnicode` 유무만으로 발화하는 새 detector를 추가한 것이 아니다.
- **적용/제거**: OCR 모듈의 입력 의미 수정. 모델/표 구조와 독립적으로 검토·커밋한다.
  제거 시 깨진 native 페이지에서 내용 소실이 돌아올 수 있고 Table 외에도 영향이 있다.
- **구현/확인**: `OCR:src/ocr/get_culled_pixmap.py::get_pixmap`;
  OCR 브랜치 `tests/test_ocr.py::test_get_pixmap_empty_rects_keep_text`.

### OCR-2. OCR writeback 전 원본 픽셀 보존

- **역할**: 최초 OCR 덧그리기 직전 display list를 같은 page에 보존한다.
  live OCR 텍스트와 기존 GNN 입력은 그대로 둔다. OCR을 없애거나 보이지 않게 만드는 기능이 아니다.
- **경계**: 생산자는 OCR 브랜치, 이를 읽는 raster 괘선 소비자는 Table 3.3이다.
  optional 속성 `_pymupdf4llm_ruling_displaylist`가 없으면 소비자는 live page를 렌더링한다.
- **적용/제거**: 별도 정책 옵션 없음. 반복 OCR에서도 최초 snapshot을 덮어쓰지 않는다.
  생산자를 제거하면 OCR 자체는 실행되지만 Table 선 검출에 덧그린 글자가 다시 섞일 수 있다.
  Table과 무관한 독립 OCR 사용에서는 소비하지 않는 데이터라는 점도 함께 검토한다.
- **구현/확인**: `OCR:src/ocr/exec_ocr_interface.py::exec_ocr_full`, `exec_ocr_detection`;
  OCR 브랜치 `tests/test_pre_ocr_displaylist.py`, 통합 `test_raster_ruling_ocr_pixels.py`.

## 검증 범위

제품/어댑터/OCR을 합친 승인 stack은 full-503에서 GTRM 0.8098682258124252이며,
정본과 503개 raw 출력·정규화 출력·페이지별 지표가 같았다. 이는 최종 조합 검증이며
이 저장소 단독 또는 각 중간 커밋의 독립 기여도/비회귀 검증은 아니다.
기존 실행: PB:runs/review-branches-20260917/full. 메시지·문서만 변경한 뒤
제품 소스/테스트 tree 동일성을 별도로 확인한다. 원격 push/PR은 수행하지 않는다.
전체 어댑터 시험 476 통과/6 skip, 제품 경계 16 통과, HTML 13 통과는 이전 조합의
검증 범위다. 새로운 성능·일반화 측정으로 취급하지 않는다.
