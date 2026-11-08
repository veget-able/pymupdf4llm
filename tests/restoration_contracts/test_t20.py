from .fixtures import *
from pymupdf4llm._table_pipeline.original_grid_restoration import install, StructuralProposalTrial

class FeatureBase(Base):
 def setUp(self):
  super().setUp()
  install(self.runtime)

from dataclasses import FrozenInstanceError
from unittest.mock import patch
class TrialContracts(FeatureBase):
 def setup_trial(self,kind='union',n=3):
  names=[['Title','Value'],['Alpha','One'],['Beta','Two']]
  tabs=[self.tab([names[i]],y=i*20,depth=1 if i==0 else 0,refs=True) for i in range(n)]
  words=self.material.words
  self.material.sources=tuple(NativeSource(i,tuple(w[:4]),w[4],('native',),
   (CellSource('word',i,tuple(w[:4]),w[4],words),)) for i,w in enumerate(words))
  raw=[[[*c.bbox] for c in t.placements[0]] for t in tabs]
  self.calls=0
  self.candidate=self.tab([['x','y']]*n,depth=1)
  self.candidate.placements=[[c.clone() for c in t.placements[0]] for t in tabs]
  self.runtime.header_service=NS(valid_table=lambda header,tab:True)
  def reconstruct():self.calls+=1;return [self.candidate]
  selected_grids=[[[list(c.bbox) for c in t.placements[0]]] for t in tabs]
  trial=StructuralProposalTrial((0,0,20,(n-1)*20+10),raw,
    [envelope(t) for t in tabs],kind,self.material.sources,reconstruct,selected_grids)
  self.runtime.structural_trials=[trial]
  return tabs,trial
 def test_uniform_stack_actual_trial_adopts_retained_structure(self):
  tabs,trial=self.setup_trial();out=self.pipeline.finalize_tables(self.page,tabs)
  self.assertEqual(out,[self.candidate]);self.assertEqual(self.calls,1)
  self.assertTrue(any(e['status']=='adopted' for e in self.pipeline.events))
 def test_physical_headerless_child_reuses_original_eligible(self):
  tabs,trial=self.setup_trial('physical',2);out=self.pipeline.finalize_tables(self.page,tabs)
  self.assertEqual(out,[self.candidate]);self.assertEqual(self.calls,1)
  self.assertEqual(self.pipeline.events[0]['reason'],'headerless_child')
 def test_directional_headerless_child_uses_same_contract(self):
  tabs,trial=self.setup_trial('directional',2)
  self.assertEqual(self.pipeline.finalize_tables(self.page,tabs),[self.candidate])
 def test_union_two_children_do_not_use_uniform_stack_revert(self):
  tabs,trial=self.setup_trial(n=2);self.assertEqual(self.pipeline.finalize_tables(self.page,tabs),tabs)
  self.assertEqual(self.calls,0)
 def test_callback_source_loss_preserves_actual_children(self):
  tabs,trial=self.setup_trial();c=self.candidate.placements[0][0];c.text='';c.source_content=CellContent('',())
  self.assertEqual(self.pipeline.finalize_tables(self.page,tabs),tabs);self.assertEqual(self.calls,1)
 def test_callback_source_duplication_preserves_actual_children(self):
  tabs,trial=self.setup_trial();c=self.candidate.placements[0][0]
  c.source_content=CellContent(c.text,c.source_content.sources*2)
  self.assertEqual(self.pipeline.finalize_tables(self.page,tabs),tabs)
 def test_invalid_final_R6_result_cannot_be_adopted(self):
  tabs,trial=self.setup_trial();self.runtime.header_service.valid_table=lambda header,tab:False
  self.assertEqual(self.pipeline.finalize_tables(self.page,tabs),tabs)
 def test_callback_error_propagates_without_empty_success(self):
  tabs,trial=self.setup_trial()
  def fail():raise RuntimeError('actual refinement failed')
  from dataclasses import replace
  self.runtime.structural_trials=[replace(trial,reconstruct_original=fail)]
  with self.assertRaisesRegex(RuntimeError,'actual refinement failed'):self.pipeline.finalize_tables(self.page,tabs)
  self.assertEqual(len(tabs),3)
 def test_overlapping_trial_families_do_not_get_quality_priority(self):
  tabs,trial=self.setup_trial();self.runtime.structural_trials=[trial,trial]
  self.assertEqual(self.pipeline.finalize_tables(self.page,tabs),tabs);self.assertEqual(self.calls,0)
 def test_trial_snapshot_is_detached_and_immutable(self):
  tabs,trial=self.setup_trial();old=trial.original_grid
  tabs[0].placements[0][0].bbox=(90,90,100,100)
  self.assertEqual(trial.original_grid,old)
  with self.assertRaises(FrozenInstanceError):trial.original_box=(1,2,3,4)
 def test_missing_selected_grids_is_explicit_contract_error(self):
  tabs,trial=self.setup_trial()
  with self.assertRaisesRegex(ValueError,'Incomplete'):
   StructuralProposalTrial(trial.original_box,trial.original_grid,trial.selected_boxes,trial.split_kind,
    trial.native_sources,trial.reconstruct_original,())
 def test_changed_page_producer_cannot_match_old_trial(self):
  tabs,trial=self.setup_trial();self.material=Material(self.material.words)
  self.assertIsNone(self.pipeline._proposal_family(trial,tabs,self.material));self.assertEqual(self.calls,0)
 def test_source_grid_scope_mismatch_preserves_current(self):
  from dataclasses import replace
  tabs,trial=self.setup_trial();self.runtime.structural_trials=[replace(trial,original_box=(0,0,21,50))]
  self.assertEqual(self.pipeline.finalize_tables(self.page,tabs),tabs);self.assertEqual(self.calls,0)
 def test_other_table_ID_collision_prevents_adoption(self):
  tabs,trial=self.setup_trial();other=self.tab([['external','table']],y=80)
  other.table_id=self.candidate.table_id='already-used'
  out=self.pipeline.finalize_tables(self.page,tabs+[other])
  self.assertEqual(out,tabs+[other])

class PendingContracts(FeatureBase):
 def test_pending_roles_consumed_on_current_grid(self):
  tab=self.tab([['Only','Header'],['a','1']])
  self.pipeline._pending_parent_roles={id(tab.placements):(tab.placements,HeaderRegion(top_header_rows=1,section_header_rows=()))}
  out=self.pipeline.split_table(self.page,tab)
  self.assertEqual(self.pipeline._pending_parent_roles,{})
  self.assertEqual(out[0].header_rows,1)
  self.assertEqual(self.header.calls[0][1],(0,0,20,20))

from contextlib import nullcontext
import pymupdf
from pymupdf import _table_union as U
from pymupdf4llm._table_pipeline.original_grid_restoration import original_refiner
class Contract(unittest.TestCase):
    def test_callback_copies_immutable_snapshot_to_mutable_rows(self):
        grid=[[(0.,0.,10.,10.),(10.,0.,20.,10.)]]
        entry=U._TableGridEntry(pymupdf.Rect(0,0,20,10),grid,{'diagnostic_only':True})
        runtime=NS(stats=Counter(),structure_predict=lambda *a: self.fail('TGIF called'))
        page=object();material=NS(characters=({'text':'A'},));observed=[]
        callback=original_refiner(runtime,page,entry,material)
        grid[0][0]=(0,0,1,1)
        def refine(actual_page,cells,box,trace,holder):
            self.assertIs(actual_page,page);self.assertIsInstance(cells,list)
            self.assertIsInstance(cells[0],list)
            self.assertEqual(cells[0][0],(0.,0.,10.,10.))
            self.assertEqual(holder._chars,material.characters)
            observed.append(cells);cells[0].append((20,0,30,10));return ['refined']
        with patch('pymupdf4llm._table_pipeline.original_grid_restoration.refinement_geometry',side_effect=nullcontext),patch('pymupdf4llm._table_pipeline.original_grid_restoration.table.Table',side_effect=lambda *a,**k:NS()),patch('pymupdf4llm._table_pipeline.original_grid_restoration.refine_child',side_effect=refine):
            self.assertEqual(callback(),['refined']);self.assertEqual(callback(),['refined'])
        self.assertIsNot(observed[0],observed[1]);self.assertIsNot(observed[0][0],observed[1][0])
        self.assertEqual(runtime.stats['structural_alternative_refinements'],2)

from pymupdf import Rect,_table_union as U
from pymupdf4llm._table_pipeline.runtime import TableRuntime
class Page:
 number=0
 _union_text_span_records_cache=[]
 @property
 def layout_information(self):raise AssertionError('Table policy accessed detector layout metadata')
 def get_text(self,*a,**kw):raise AssertionError('Unexpected extraction in prepared material contract')

class NativeSelectionContracts(unittest.TestCase):
 def runtime(self):
  material=NS(sources_in=lambda box:(),characters=())
  runtime=NS(page_material=lambda page:material,stats=Counter(),errors=[],structural_trials=[],
    header=Header(),union_consumer=None,parent_coherence=None,union_selection_consumer=None)
  runtime.pipeline=TableFinalization(runtime)
  install(runtime)
  return runtime
 def opts(self,ref=True):return dict(grid_ref=ref,grid_ref_iou=.9,span_mult_gate=False,span_mult_threshold=3)
 def test_split_retains_real_structural_trial_without_parent_group_lookup(self):
  whole=[[(0,0,20,20)]];a=[[(0,0,20,10)]];b=[[(0,10,20,20)]]
  p=U._TableGridEntry(Rect(0,0,20,20),whole,dict(source_gnn_indices=[999]))
  children=[U._TableGridEntry(Rect(0,0,20,10),a,{}),U._TableGridEntry(Rect(0,10,20,20),b,{})]
  rt=self.runtime();result=TableRuntime.fuse(rt,[p],children,page=Page(),**self.opts(False))
  self.assertEqual(len(result),2);self.assertEqual(len(rt.structural_trials),1)
  self.assertEqual(rt.structural_trials[0].original_grid,(((0,0,20,20),),))
