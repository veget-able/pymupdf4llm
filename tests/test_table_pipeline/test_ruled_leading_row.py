from contextlib import nullcontext
from types import SimpleNamespace as NS
from unittest.mock import patch
import pytest
from pymupdf._table_spans import SpanCell,CellSource
from pymupdf4llm._table_pipeline.table_content_recovery import SourceNode
from pymupdf4llm._table_pipeline.ruled_leading_row import recover
from pymupdf4llm._table_pipeline.table_content_pipeline import ContentRestorationPipeline

class Table(NS):
 @property
 def bbox(self):return self._bbox

def fixture():
 words=[(2,3,8,7,'Spanning'),(9,3,15,7,'label')]
 t=Table(_bbox=(0,2,20,30),placements=[[SpanCell((0,10,10,30),'left',1,1),SpanCell((10,10,20,30),'right',1,1)]],
         header_rows=0,section_rows=(),bbox_provenance={},_chars=[])
 ns=[SourceNode(0,(2,3,15,7),'Spanning label')]
 es=[dict(orientation='h',x0=0,x1=20,top=y,bottom=y,ruling_origin='vector') for y in (0,10)]
 return t,ns,words,es

def test_ruled_band_restores_spanning_cell_without_assigning_header_role():
 t,ns,words,es=fixture();child=recover(t,ns,words,es,[])
 assert child.placements[0][0].text=='Spanning label'
 assert child.placements[0][0].colspan==2
 assert child.placements[0][0].tag=='td'
 assert child.placements[1][0] is t.placements[0][0]
 assert all(s.collection is words for s in child.placements[0][0].source_content.sources)

@pytest.mark.parametrize('case',['no_top_rule','no_bottom_rule','vertical_divider','different_width','outside_words','two_lines','no_parent_nodes','other_table'])
def test_ruled_band_rejects_unsupported_cases(case):
 t,ns,words,es=fixture();obstacles=[]
 if case=='no_top_rule':es=es[1:]
 if case=='no_bottom_rule':es=es[:1]
 if case=='vertical_divider':es.append(dict(orientation='v',x0=10,x1=10,top=0,bottom=10,ruling_origin='vector'))
 if case=='different_width':es[0]['x1']=30
 if case=='outside_words':words[0]=(-2,3,8,7,'Spanning')
 if case=='two_lines':words[1]=(9,8,15,9,'label')
 if case=='no_parent_nodes':ns=[]
 if case=='other_table':obstacles=[NS(bbox=(0,0,20,10))]
 assert recover(t,ns,words,es,obstacles) is None

def make_cell(words,index):
 w=words[index];return SpanCell(w[:4],w[4],1,1,sources=[CellSource('word',index,w[:4],w[4],words)])

def rollback_case(mode):
 words=[(0,0,4,4,'kept'),(6,0,10,4,'missing'),(12,0,16,4,'extra-kept')]
 children=[NS(placements=[[make_cell(words,0)]],_chars=[]),NS(placements=[[make_cell(words,2)]],_chars=[])]
 source=[SourceNode(0,words[0][:4],'kept'),SourceNode(1,words[1][:4],'missing')]
 indices={'complete':[0,1,2],'missed':[0,2],'lost_old':[0,1],'already_complete':[0,1,2]}[mode]
 result=[NS(placements=[[make_cell(words,i) for i in indices]])]
 if mode=='already_complete':children[0].placements[0].append(make_cell(words,1))
 calls=[]
 class Rows:
  def resolve(self):calls.append('resolve');return []
 class Entry(tuple):bbox_provenance={}
 ctx=NS(parent_key=(0,),parent_entry=Entry(((0,0,16,4),Rows())),source_nodes=source)
 pipe=object.__new__(ContentRestorationPipeline);pipe.events=[]
 return pipe,NS(_refine_words_cache=words),ctx,children,result,calls

@pytest.mark.parametrize('mode',['complete','missed','lost_old','already_complete'])
def test_split_rollback_requires_recovery_and_preserves_old_child_sources(mode):
 pipe,page,ctx,children,result,calls=rollback_case(mode)
 with patch('pymupdf4llm._table_pipeline.grid_reconstruct_split.refinement_geometry',lambda p:nullcontext(p)),patch('pymupdf4llm._table_pipeline.grid_reconstruct_split.refine_child',return_value=result):
  got=pipe.reject_incomplete_split(page,ctx,children,[])
 assert (got is result)==(mode=='complete')
 assert bool(calls)==(mode!='already_complete')

def test_split_rollback_rejects_other_table_collision():
 pipe,page,ctx,children,result,calls=rollback_case('complete')
 with patch('pymupdf4llm._table_pipeline.grid_reconstruct_split.refinement_geometry',lambda p:nullcontext(p)),patch('pymupdf4llm._table_pipeline.grid_reconstruct_split.refine_child',return_value=result):
  other=NS(bbox=(2,2,3,3),placements=[])
  assert pipe.reject_incomplete_split(page,ctx,children,[other]) is None
 assert pipe.events[-1]['reason']=='other-table-collision'
