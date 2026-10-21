"""union 후 표 복원(table content restoration) — 통합 계약·전달 계층 v3.

작업 1(행동 불변 통합). 실행 순서·조건·상수·추론 입력은 승인 구현(V9/V10)
그대로. 본 모듈은 R→C 실행 전달을 세 원칙으로 제공한다:

  1) 인스턴스 귀속 전달(전역 저장소 아님): 호출별 ContextVar가 가리키는
     파이프라인에 R의 RestorationContext를 전달한다. 호출 종료 시 context가
     해제되어 문서 간 데이터가 섞이지 않는다. 활성 호출이 없으면 no-op.

  2) 실제 입력 공유: R이 이미 취득한 union parent entry를 context로
     전달한다. C(fragment)는 자신의 `_layout_table_grids` 재-patch(retain)를
     제거하고 이 parent를 재사용한다 — 동일 객체 취득의 중복 제거.

  3) 수용 판정 금지(미확정 유지): 이 단계에서는 셀 수용을 '확인'하지
     않는다. stitch/append로 처리를 시도한 노드도 전부 indeterminate로
     두고, 미소비 잔여와 함께 전달 목록에 유지한다. 기하적 포함은 판정에
     쓰지 않는다.
"""

RESTORATION_INPUT_CONTRACT = {
    "parent": ["union parent entry(원본 노드·보존 재료·resolve 가능)"],
    "children": ["cells(원좌표,span)", "grid_source", "bbox_source",
                 "admission_provenance"],
    "r6": ["원조각 판정 고정(연결 후 재판정은 마지막 1회)"],
    "handoff": ["미처리+미확정 잔여 목록(폐기 금지)"],
}

PHASES = ("R:union_content_recovery(S0,S1,S1',S2)",
          "refine+R6",
          "C:fragment_consolidation(join,revert)")


class ResidualReport:
    """R 단계 잔여의 처리-시도(attempted)와 미확정(indeterminate)만 구분한다.
    수용(accepted)은 이 단계에서 확정하지 않는다 — 전달 목록은 residual 전체
    중 아직 수용 확인되지 않은 것(= 현 단계 전부)."""

    def __init__(self):
        self.attempted = set()      # 기존 알고리즘이 처리 묶음에 넣은 노드(표시 불변)
        self.indeterminate = set()  # 수용 미확정(stitch/append 소비 포함)
        self.residual = []          # R 단계 잔여 노드 전체(index 순서 보존)

    def handoff(self):
        """다음 단계로 전달할 (node_index, disposition). 수용 확정이 없으므로
        residual 전체가 남으며, 처리 시도분은 indeterminate로 표시한다."""
        out = []
        for i in self.residual:
            tag = "indeterminate" if i in self.indeterminate else "unprocessed"
            out.append((int(i), tag))
        return out

    def summary(self):
        return {"residual": len(self.residual),
                "attempted": len(self.attempted),
                "indeterminate": len(self.indeterminate),
                "handoff": len(self.handoff())}


class RestorationContext:
    def __init__(self, page_number, parent_key, parent_entry):
        self.page_number = int(page_number)
        self.parent_key = tuple(parent_key)
        self.parent_entry = parent_entry   # R이 취득한 union parent(공유 입력)
        self.residual_report = ResidualReport()
        self.node_bboxes = {}              # handoff 노드 bbox
        # Optional ownership experiment: immutable node text/geometry retained
        # before a deferred prediction can release its inputs. The old residual
        # report remains attempted/indeterminate and is never relabelled accepted.
        self.source_nodes = ()
        self.split_selected = False


def publish(context):
    from pymupdf._table_pipeline import current
    runtime = current()
    if runtime is not None:
        runtime.pipeline.restoration_contexts[(context.page_number, context.parent_key)] = context
