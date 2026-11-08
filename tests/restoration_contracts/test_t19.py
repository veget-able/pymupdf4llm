from pymupdf4llm.helpers.table_html.reconstruct import _placement_grid_matrices
from .fixtures import *
from pymupdf4llm._table_pipeline.directional_table_split import install, split_parts

class FeatureBase(Base):
 def setUp(self):
  super().setUp()
  install(self.runtime)
 def parts(self,texts,edges=()):
  tab=self.tab(texts);self.material.edges=tuple(edges);self.material._joined_edges=None
  _,_,cells,extract=_placement_grid_matrices(tab.placements)
  return split_parts(cells,extract,self.material)

from dataclasses import FrozenInstanceError
from unittest.mock import patch
class SplitContracts(FeatureBase):
 def test_TX1299_one_empty_body_panel(self):
  self.assertEqual(self.parts([['Class','Relativity']*2]+[['A','1','','']]*42),[])
 def test_existing_positive_body_panels(self):
  self.assertEqual(len(self.parts([['Class','Rate']*2,['A','1','B','2']])),2)
 def test_heading_alone_is_not_enough(self):
  self.assertEqual(self.parts([['Class','Rate']*2]),[])
 def test_zero_body_and_nonlatin_positive(self):
  self.assertEqual(len(self.parts([['区分','数量']*2,['0','0','0','0']])),2)
 def test_shared_distinct_titles_remain_unsplit(self):
  self.assertEqual(self.parts([['Assets','','Liabilities',''],['Class','Rate']*2,['A','1','B','2']]),[])
 def test_connected_ruling_veto(self):
  edge=dict(orientation='h',x0=0,x1=40,top=10,bottom=10,ruling_origin='vector')
  self.assertEqual(self.parts([['Class','Rate']*2,['A','1','B','2']],[edge]),[])
 def test_outer_frame_alone_does_not_blanket_veto_positive(self):
  edges=[dict(orientation='h',x0=0,x1=40,top=y,bottom=y,ruling_origin='vector') for y in (0,20)]
  self.assertEqual(len(self.parts([['Class','Rate']*2,['A','1','B','2']],edges)),2)
 def test_separate_real_body_rules_and_gapped_panels_remain_positive(self):
  tab=self.tab([['Class','Rate']*2,['A','1','B','2']])
  for row in tab.placements:
   for cell in row[2:]:cell.bbox=(cell.bbox[0]+5,cell.bbox[1],cell.bbox[2]+5,cell.bbox[3])
  edges=[dict(orientation='h',x0=a,x1=b,top=10,bottom=10,ruling_origin='vector') for a,b in [(0,20),(25,45)]]
  material=Material(edges=edges);_,_,cells,texts=_placement_grid_matrices(tab.placements)
  self.assertEqual(len(split_parts(cells,texts,material)),2)
 def test_native_joined_contiguous_rule_fragments_veto(self):
  edges=[dict(orientation='h',x0=a,x1=b,top=10,bottom=10,ruling_origin='vector') for a,b in [(0,20),(20,40)]]
  self.assertEqual(self.parts([['Class','Rate']*2,['A','1','B','2']],edges),[])
 def test_source_word_crossing_cut_veto(self):
  self.material=Material([(15,12,25,18,'one phrase')])
  self.assertEqual(self.parts([['Class','Rate']*2,['A','1','B','2']]),[])
 def test_split_preserves_empty_cells_actual_refs_and_no_provenance_reads(self):
  tab=self.tab([['Class','Rate']*2,['A','','B','2']],refs=True)
  children=self.pipeline.split_table(self.page,tab)
  self.assertEqual(len(children),2)
  self.assertEqual(placement_counts(children),placement_counts([tab]))
  self.assertEqual(source_counts(children),source_counts([tab]))
  self.assertTrue(any(not c.text for t in children for row in t.placements for c in row))
 def test_merged_cell_crossing_cut_preserved(self):
  tab=self.tab([['Class','Rate']*2,['A','1','B','2']])
  tab.placements[1]=[SpanCell((0,10,40,20),'A',4,1)]
  self.assertEqual(self.pipeline.split_table(self.page,tab),[tab])
 def test_pending_roles_consumed_on_current_grid(self):
  tab=self.tab([['Only','Header'],['a','1']])
  self.pipeline._pending_parent_roles={id(tab.placements):(tab.placements,HeaderRegion(top_header_rows=1,section_header_rows=()))}
  out=self.pipeline.split_table(self.page,tab)
  self.assertEqual(self.pipeline._pending_parent_roles,{})
  self.assertEqual(out[0].header_rows,1)
  self.assertEqual(self.header.calls[0][1],(0,0,20,20))
 def test_actual_trial_failure_restores_snapshot_without_parent_resolve(self):
  tab=self.tab([['Class','Rate']*2,['A','1','B','2']],refs=True)
  before=placement_counts([tab]);refs=source_counts([tab]);self.header.corrupt_once=True
  out=self.pipeline.split_table(self.page,tab)
  self.assertEqual(len(out),1)
  self.assertEqual(placement_counts(out),before);self.assertEqual(source_counts(out),refs)
  self.assertIsNot(out[0],tab)
 def test_table_order_alone_is_not_a_rollback_reason(self):
  tab=self.tab([['Class','Rate']*2,['A','1','B','2']],refs=True)
  out=self.pipeline.split_table(self.page,tab)
  out=self.pipeline.finalize_tables(self.page,list(reversed(out)))
  self.assertEqual(len(out),2)
  self.assertFalse(any(e.get('status')=='rollback' for e in self.pipeline.events))
 def test_final_source_loss_rolls_back_actual_snapshot(self):
  tab=self.tab([['Class','Rate']*2,['A','1','B','2']],refs=True)
  before=source_counts([tab]);out=self.pipeline.split_table(self.page,tab)
  out[0].placements[0][0].source_content=None
  out=self.pipeline.finalize_tables(self.page,out)
  self.assertEqual(len(out),1);self.assertEqual(source_counts(out),before)
 def test_new_page_drops_old_trial_even_after_aborted_page(self):
  tab=self.tab([['Class','Rate']*2,['A','1','B','2']]);self.pipeline.split_table(self.page,tab)
  self.material=Material()
  normal=self.tab([['A','B'],['1','2']])
  self.assertEqual(self.pipeline.finalize_tables(self.page,[normal]),[normal])
 def test_provenance_and_parent_probabilities_do_not_select_policy(self):
  text=[['Class','Rate']*2,['A','1','B','2']]
  outcomes=[]
  for meta in [dict(grid_source='find_tables',source_gnn_indices=[],parent_bbox=[-1]*4,probability=0),
               dict(grid_source='tgif',source_gnn_indices=[99],parent_bbox=[999]*4,probability=1)]:
   tab=self.tab(text,meta=Poison(meta));out=self.pipeline.split_table(self.page,tab)
   outcomes.append([(envelope(t),[[c.text for c in row] for row in t.placements]) for t in out])
  self.assertEqual(outcomes[0],outcomes[1])
 def test_split_rowspan_kept_as_one_source_owner(self):
  tab=self.tab([['Class','Rate']*2,['A','1','B','2'],['A2','1','B2','2']],refs=True)
  left=tab.placements[1][1];left.rowspan=2;left.bbox=(10,10,20,30)
  del tab.placements[2][1]
  before=source_counts([tab]);out=self.pipeline.split_table(self.page,tab)
  self.assertEqual(len(out),2);self.assertEqual(source_counts(out),before)
  self.assertEqual(out[0].placements[1][1].rowspan,2)
 def test_cell_source_swap_cannot_pass_global_bag_conservation(self):
  tab=self.tab([['Class','Rate']*2,['A','1','B','2']],refs=True)
  original=source_counts([tab]);out=self.pipeline.split_table(self.page,tab)
  a,b=out[0].placements[1]
  a.source_content,b.source_content=b.source_content,a.source_content
  a.text,b.text=b.text,a.text
  out=self.pipeline.finalize_tables(self.page,out)
  self.assertEqual(len(out),1);self.assertEqual(source_counts(out),original)
  self.assertEqual(out[0].placements[1][0].text,'A')
