"""Explicit current-grid role providers; default R6 assembly remains fixed."""
from functools import lru_cache
from pathlib import Path
from contextlib import contextmanager
from .header_service import HeaderService

class HeaderRoles:
    transport = None
    def __init__(self):
        self.service=None;self.events=[];self.errors=[];self.decisions={};self._deferred_builds=None
    def apply_roles(self,page,grid,region,*,purpose='final',table_bbox=None):
        if self.service is None:raise RuntimeError('Header provider requires its runtime service')
        return self.service.apply_roles(self,page,grid,region,purpose=purpose,table_bbox=table_bbox)
    def input_identity(self,table_bbox):return None
    scoped_apply_roles=apply_roles
    @contextmanager
    def finder_scope(self):yield
    @contextmanager
    def defer_build_roles(self):
        """Retain native grids/heuristic regions until the split keeps a parent.

        Only placement construction is deferred. Explicit child apply_roles
        calls keep their own inputs, and construction resumes immediately when
        this scope ends. The caller owns and releases the returned references.
        """
        previous = self._deferred_builds
        pending = {}
        self._deferred_builds = pending
        try:
            yield pending
        finally:
            self._deferred_builds = previous


@lru_cache(maxsize=1)
def header_session():
    from .r6_header import load_session
    return load_session(Path(__file__).with_name('models')/'fang-header-rf-r6.onnx')

def build_header(session=None):
    from .r6_header import R6HeaderRoles
    header = R6HeaderRoles(header_session() if session is None else session,
        leaf_completion=True, role_demotion=True, year_rows=True)
    header.service = HeaderService()
    return header



def install(runtime):
    from types import MethodType
    from .header_boundary import structural_boundary
    runtime.header = build_header()
    runtime.header_service = runtime.header.service
    runtime.structural_policy.structural_boundary = MethodType(structural_boundary, runtime.structural_policy)
    runtime.refine_table = runtime.refine_tagged_table
