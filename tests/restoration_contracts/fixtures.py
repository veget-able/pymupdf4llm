"""자체 포함 합성 fixture. 실제 모델·문서 실행 인증과 별개."""
import unittest
from types import SimpleNamespace as NS
from collections import Counter
from pymupdf._table_spans import SpanCell, CellSource, CellContent
from pymupdf._table_headers import HeaderRegion
from pymupdf4llm._table_pipeline.native_page_material import PageMaterial, NativeSource
from pymupdf4llm._table_pipeline.table_finalization import TableFinalization
from pymupdf4llm._table_pipeline.placement_material import envelope, placement_counts, source_counts
from pymupdf4llm._table_pipeline.table_content_recovery import node_sources

class Material:
 cut_is_clear=PageMaterial.cut_is_clear
 joined_edges=PageMaterial.joined_edges
 def __init__(self,words=(),edges=()):
  self.words=list(words);self.edges=tuple(edges);self._joined_edges=None
  self.sources=tuple(NativeSource(i,tuple(w[:4]),w[4],('native',),
    (CellSource('word',i,tuple(w[:4]),w[4],self.words),)) for i,w in enumerate(self.words))
 def sources_in(self,b):
  return tuple(s for s in self.sources if b[0] <= (s.bbox[0]+s.bbox[2])/2 < b[2] and b[1] <= (s.bbox[1]+s.bbox[3])/2 < b[3])

class Header:
 def __init__(self):self.calls=[];self.corrupt_once=False
 def apply_roles(self,page,grid,region,*,table_bbox):
  self.calls.append((grid,table_bbox))
  if self.corrupt_once:
   self.corrupt_once=False;grid[0][0].bbox=(0,0,99,99)
  return grid,region

class Poison(dict):
 def get(self,key,default=None):
  if key in ('source_gnn_indices','grid_source','parent_bbox','parent_key','probability'):raise AssertionError('provenance predicate')
  return super().get(key,default)
 def __getitem__(self,k):raise AssertionError('provenance predicate')

class Base(unittest.TestCase):
 def setUp(self):
  self.page=NS(rotation=0,_span_vertical_lines_cache=[],_table_control_glyphs=[])
  self.material=Material();self.header=Header()
  self.runtime=NS(header=self.header,errors=[],stats=Counter(),structural_trials=[],
    page_material=lambda page:self.material,union_consumer=None,parent_coherence=None,
    union_selection_consumer=None)
  self.pipeline=TableFinalization(self.runtime)
  self.runtime.pipeline=self.pipeline
 def tab(self,texts,*,y=0,depth=0,refs=False,meta=None):
  grid=[]
  for ri,row in enumerate(texts):
   out=[]
   for ci,text in enumerate(row):
    bbox=(ci*10,y+ri*10,(ci+1)*10,y+(ri+1)*10)
    sources=[]
    if refs and text:
     i=len(self.material.words);w=(*bbox,text);self.material.words.append(w)
     sources=[CellSource('word',i,bbox,text,self.material.words)]
    out.append(SpanCell(bbox,text,1,1,sources=sources if refs else None))
   grid.append(out)
  return NS(placements=grid,header_rows=depth,section_rows=(),textpage=None,_chars=(),
    bbox=(999,999,1000,1000),bbox_provenance=Poison() if meta is None else meta)
