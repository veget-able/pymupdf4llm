from copy import copy
from types import SimpleNamespace as NS
import pytest
from pymupdf import Rect
from pymupdf._table_spans import SpanCell, CellSource, _span_claim_text_in_rect
from pymupdf4llm._table_pipeline.table_content_recovery import SourceNode,node_sources
from pymupdf4llm._table_pipeline.cell_output_boundary import external_content
from pymupdf4llm._table_pipeline.fragment_consolidation import concat_placements
from pymupdf4llm.helpers.document_layout import LayoutBox
from pymupdf4llm.helpers.table_external_text import emit_external_text


def native_cell(words,bbox):
 refs=[]
 p=NS(_span_vertical_lines_cache=[])
 text=_span_claim_text_in_rect(p,Rect(bbox),words,set(),sources=refs)
 return SpanCell(bbox,text,1,1,sources=refs)


def test_producer_keeps_text_and_actual_cache_reference():
 words=[(1,1,4,3,'one'),(6,1,9,3,'two')]
 c=native_cell(words,(0,0,5,5))
 assert c.text=='one'
 assert c.source_content.sources[0].collection is words
 assert c.clone().source_content is c.source_content
 assert concat_placements([NS(placements=[[c]])])[0][0].source_content is c.source_content


def test_vertical_keeps_actual_line_source_and_old_formatting():
 words=[(0,0,2,2,'native'),(0,3,2,5,'words')]
 lines=[(Rect(0,0,2,6),'Vertical original')]
 p=NS(_span_vertical_lines_cache=lines)
 refs=[]
 text=_span_claim_text_in_rect(p,Rect(0,0,3,7),words,set(),sources=refs)
 assert text=='Vertical original'
 assert len(refs)==1 and refs[0].kind=='vertical_line' and refs[0].collection is lines


def test_mutated_cell_with_retained_ids_is_not_valid():
 words=[(1,1,4,3,'one')];c=native_cell(words,(0,0,5,5));c.text=''
 with pytest.raises(ValueError,match='changed after production'): c.clone()
 with pytest.raises(ValueError,match='changed after production'):
  external_content([NS(placements=[[c]])],[SourceNode(0,(0,0,5,5),'one')],words,(0,))


def test_envelope_does_not_absorb_outside_text():
 words=[(0,0,10,2,'outside'),(0,4,10,6,'inside')]
 c=native_cell(words,(0,3,11,7)); t=NS(bbox=(-10,-10,50,50),placements=[[c]])
 rows=t.placements
 out=external_content([t],[SourceNode(0,(0,0,11,7),'outside inside')],words,(0,))
 assert [r['text'] for r in out]==['outside']
 assert t.placements is rows and len(rows)==1


def test_existing_cell_beyond_stale_table_box_is_kept():
 words=[(0,11,9,13,'footnote')];c=native_cell(words,(0,10,10,15))
 t=NS(bbox=(0,0,10,5),placements=[[c]])
 assert external_content([t],[SourceNode(0,(0,10,10,15),'footnote')],words,(0,))==[]


def test_inside_without_proof_does_not_become_text():
 words=[(1,1,4,3,'lost')];c=SpanCell((0,0,5,5),'',1,1,sources=[])
 with pytest.raises(ValueError,match='Unproved cell content'):
  external_content([NS(placements=[[c]])],[SourceNode(0,(0,0,5,5),'lost')],words,(0,))


def test_gnn_scopes_are_not_interchangeable():
 n=SourceNode(0,(0,0,5,5),'node',(0,3))
 c=SpanCell(n.bbox,n.text,1,1,sources=node_sources([n]))
 assert c.source_content.sources[0].scope==(0,3)
 assert external_content([NS(placements=[[c]])],[SourceNode(0,(10,10,15,15),'other',(0,4))],[],(4,))[0]['text']=='other'


def span(text,bbox):
 return dict(bbox=bbox,text=text,flags=0,size=10,font='',origin=[bbox[0],bbox[3]])


def text_box(text,bbox,outer=None):
 return LayoutBox(*(outer or bbox),'text',textlines=[dict(bbox=bbox,spans=[span(text,bbox)])])


def page_with(record,body):
 item=dict(bbox=[0,0,100,100],html='<table></table>',rows=0,cols=0,cells=[],extract=[],external_content=[record])
 return NS(boxes=[*body,LayoutBox(0,0,100,100,'table',table=dict(html_tables=[item],html=item['html']))])


def record():
 return dict(node_index=0,bbox=[1,1,20,4],text='Retained note',units=[dict(index=0,bbox=[1,1,10,4],text='Retained'),dict(index=1,bbox=[11,1,20,4],text='note')])


def test_existing_span_inside_larger_paragraph_is_reused():
 p=page_with(record(),[text_box('Retained note',[1,1,20,4],[0,0,100,80])]);emit_external_text(p)
 assert len(p.boxes)==2


def test_same_string_at_other_position_is_not_removed():
 p=page_with(record(),[text_box('Retained note',[1,30,20,33])]);emit_external_text(p)
 assert len(p.boxes)==3
 assert p.boxes[0].boxclass=='text'


def test_partial_span_coverage_emits_only_remaining_unit():
 p=page_with(record(),[text_box('Retained',[1,1,10,4])]);emit_external_text(p)
 texts=[s['text'] for b in p.boxes for l in b.textlines or [] for s in l['spans']]
 assert texts==['Retained','note']


def test_rendered_string_matters_superscript_is_not_plain_occurrence():
 b=text_box('Retained note',[1,1,20,4]);b.textlines[0]['spans'][0]['flags']=1
 p=page_with(record(),[b]);emit_external_text(p)
 assert len(p.boxes)==3


def test_thin_punctuation_and_gnn_word_fragment_use_consumed_source_unit():
 words=[(0,0,40,10,'Protection'),(0,12,40,22,'..................')]
 cell=native_cell(words,(0,0,40,25))
 nodes=[SourceNode(0,(0,2,8,8),'Pr'),SourceNode(1,(0,19,40,20),'..................')]
 assert external_content([NS(placements=[[cell]])],nodes,words,(0,))==[]


def test_restoration_rollback_remains_before_external_delivery(monkeypatch):
 from pymupdf4llm._table_pipeline import table_content_pipeline as pipeline
 from pymupdf4llm._table_pipeline.fragment_consolidation import FragmentConsolidationPipeline
 from pymupdf._table_headers import HeaderRegion
 words=[(1,1,8,5,'old'),(1,12,8,16,'new')]
 original=NS(placements=[[native_cell(words,(0,0,10,10))]],bbox=(0,0,10,10),
             bbox_provenance={'source_gnn_indices':[0]},header_rows=0,section_rows=())
 old=SourceNode(0,(0,0,10,10),'old');new=SourceNode(1,(0,11,10,17),'new')
 candidate=copy(original);candidate.placements=original.placements+[[SpanCell(new.bbox,'new',1,1,sources=node_sources([new]))]]
 runner=object.__new__(pipeline.ContentRestorationPipeline);runner.events=[]
 runner.restoration_contexts={(0,(0,)):NS(source_nodes=[old,new],split_selected=False)}
 def damage(page,rows,region):
  damaged=[[c.clone() for c in row] for row in rows];damaged[-1][0].text=''
  return damaged,HeaderRegion(top_header_rows=0,section_header_rows=())
 runner.header=NS(apply_roles=damage)
 monkeypatch.setattr(FragmentConsolidationPipeline,'finalize_tables',lambda self,p,t:t)
 monkeypatch.setattr(pipeline,'restore_tables',lambda *a,**k:([candidate],{0:{'table':0},1:{'table':0}},[{}]))
 result=runner.finalize_tables(NS(number=0,_refine_words_cache=words),[original])
 assert result[0].placements==original.placements
 assert result[0].external_content[0]['text']=='new'


def test_punctuation_node_includes_trailing_space_beyond_produced_word():
 words=[(0,0,8,9,'—')];c=native_cell(words,(0,0,20,10))
 n=SourceNode(0,(0,5,10,7),'—')
 chars=[dict(x0=0,top=5,x1=8,bottom=5.3,text='—'),dict(x0=8,top=7,x1=10,bottom=7,text=' ')]
 assert external_content([NS(placements=[[c]])],[n],words,(0,),characters=chars)==[]


def test_residual_word_inside_a_longer_emitted_span_uses_real_word_input():
 r=record();r.update(source_kind='word',units=[dict(index=1,bbox=[11,1,20,4],text='note')],text='note',bbox=[11,1,20,4])
 p=page_with(r,[text_box('Retained note',[1,1,20,4],[0,0,100,80])])
 p.words=[(1,1,10,4,'Retained'),(11,1,20,4,'note')]
 emit_external_text(p)
 assert len(p.boxes)==2


def test_thin_glyph_query_works_with_live_center_index_enabled():
 from pymupdf.table import _html_table_scope
 words=[(0,0,8,9,'—')];c=native_cell(words,(0,0,20,10))
 n=SourceNode(0,(0,5,10,7),'—')
 chars=[dict(x0=0,top=5,x1=8,bottom=5.3,text='—')]
 with _html_table_scope():
  assert external_content([NS(placements=[[c]])],[n],words,(0,),characters=chars)==[]


def test_glyph_overlap_does_not_override_actual_word_to_cell_contract():
 from pymupdf.table import _html_table_scope
 words=[(0,0,8,9,'—')];c=SpanCell((0,6,20,10),'',1,1,sources=[])
 n=SourceNode(0,(0,6,10,7),'—')
 chars=[dict(x0=0,top=6,x1=8,bottom=6.3,text='—')]
 with _html_table_scope():
  out=external_content([NS(placements=[[c]])],[n],words,(0,),characters=chars)
 assert out[0]['text']=='—' and out[0]['source_kind']=='word'


def test_math_glyph_uses_preserved_baseline_when_ink_extends_below_word_box():
 words=[(0,0,8,8,'√')];c=native_cell(words,(0,0,10,10))
 n=SourceNode(0,(0,6,8,15),'√')
 chars=[dict(x0=0,top=6,x1=8,bottom=15,text='√',y1=94,matrix=[1,0,0,1,0,93])]
 assert external_content([NS(placements=[[c]])],[n],words,(0,),characters=chars)==[]


def test_supported_new_row_cannot_cover_an_unselected_source_with_a_blank_cell():
 from pymupdf4llm._table_pipeline.grid_ownership import absorb_grid_nodes
 class Table:
  bbox=(0,0,60,20);header_rows=0;section_rows=();bbox_provenance={}
  placements=[[SpanCell((i*20,0,(i+1)*20,10),str(i),1,1) for i in range(3)],
              [SpanCell((i*20,10,(i+1)*20,20),str(i+3),1,1) for i in range(3)]]
 t=Table()
 supported=[SourceNode(0,(2,-10,18,-5),'A'),SourceNode(1,(22,-10,38,-5),'B')]
 failures=[]
 unchanged,decisions=absorb_grid_nodes([t],supported+[SourceNode(2,(39,-10,62,-5),'unselected')],{},failures=failures)
 assert failures==[dict(table=0,reason='new-cell-omits-source',nodes=[2])]
 assert unchanged[0] is t and decisions==[]
 changed,decisions=absorb_grid_nodes([t],supported,{})
 assert decisions and len(changed[0].placements)==3


def test_undecoded_control_glyph_cannot_be_hidden_or_reclassified_as_text():
 c=SpanCell((0,0,10,10),'',1,1,sources=[])
 with pytest.raises(ValueError,match='without producer proof'):
  external_content([NS(placements=[[c]])],[SourceNode(0,(1,1,5,5),'\x13')],[],(0,))


def test_split_delivery_box_preserves_child_provenance_and_html():
 items=[dict(bbox=[0,y,20,y+10],html=f'<table><tr><td>{y}</td></tr></table>',rows=1,cols=1,
             cells=[[[0,y,20,y+10]]],extract=[[str(y)]],table_id=f't{y}',bbox_source='region_split',
             source_gnn_indices=[0],external_content=[]) for y in [0,30]]
 items[0]['external_content']=[dict(node_index=0,source_gnn_indices=[0],bbox=[1,15,10,20],text='between')]
 p=NS(boxes=[LayoutBox(0,0,20,40,'table',table=dict(html_tables=items,html='\n\n'.join(t['html'] for t in items)))])
 emit_external_text(p)
 tables=[b for b in p.boxes if b.boxclass=='table']
 assert [b.table['html'] for b in tables]==[t['html'] for t in items]
 assert [b.bbox_provenance['bbox_owner_table_id'] for b in tables]==['t0','t30']
 assert all(b.bbox_provenance['bbox_source']=='region_split' for b in tables)


def test_external_text_stays_with_its_parent_in_a_later_column():
 p=page_with(record(),[text_box('left column',[0,30,10,40])])
 p.boxes[-1].x0=100;p.boxes[-1].x1=200
 p.boxes[-1].table['html_tables'][0]['external_content'][0]['bbox']=[101,1,120,4]
 p.boxes[-1].table['html_tables'][0]['external_content'][0].pop('units')
 emit_external_text(p)
 assert p.boxes[0].textlines[0]['spans'][0]['text']=='left column'
 assert p.boxes[1].textlines[0]['spans'][0]['text']=='Retained note'


def test_actual_html_loss_fails_even_when_individual_metadata_retains_content():
 p=page_with(record(),[]);p.boxes[0].table['html']='corrupted'
 with pytest.raises(ValueError,match='Rendered table HTML'):emit_external_text(p)


def test_layout_cannot_drop_a_produced_table_while_keeping_its_source_ids():
 p=NS(boxes=[],find_tables=[dict(table_id='missing')])
 with pytest.raises(ValueError,match='lost or duplicated'):emit_external_text(p)


def test_node_with_whole_word_and_partial_next_word_preserves_both_units():
 words=[(0,0,4,4,'one'),(6,0,16,4,'Protection')]
 chars=[dict(text='P',x0=6,top=1,x1=7,bottom=3)]
 node=SourceNode(0,(0,0,8,4),'one Pr')
 out=external_content([], [node], words, (0,), characters=chars)
 assert out[0]['source_indices']==[0,1]
 assert out[0]['text']=='one Protection'


def test_multiple_notes_after_same_table_keep_top_to_bottom_order():
 p=page_with(record(),[])
 items=p.boxes[0].table['html_tables']
 items[0]['source_gnn_indices']=[0]
 items[0]['external_content']=[dict(node_index=i,source_gnn_indices=[0],bbox=[0,y,10,y+3],text=t)
                              for i,(y,t) in enumerate([(110,'first'),(120,'second')])]
 emit_external_text(p)
 assert [b.textlines[0]['spans'][0]['text'] for b in p.boxes if b.boxclass=='text']==['first','second']
