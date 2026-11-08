from .fixtures import *
from pymupdf4llm._table_pipeline.ruled_leading_row_policy import install

class FeatureBase(Base):
 def setUp(self):
  super().setUp()
  install(self.runtime)

from dataclasses import FrozenInstanceError
from unittest.mock import patch
class RuledRetainedContracts(FeatureBase):
 def fixture(self):
  self.material=Material([(2,2,18,8,'real caption')]);self.page._refine_words_cache=self.material.words
  self.material.edges=tuple(dict(orientation='h',x0=0,x1=20,top=y,bottom=y,ruling_origin='vector') for y in (0,10))
  tab=self.tab([['a','b']],y=10,refs=True)
  return tab
 def test_real_ruled_source_added_once_body_preserved(self):
  tab=self.fixture();before=source_counts([tab]);placements=placement_counts([tab])
  out=self.pipeline.finalize_tables(self.page,[tab])[0]
  self.assertEqual(len(out.placements),2);self.assertEqual(out.placements[0][0].text,'real caption')
  self.assertEqual(out.placements[0][0].colspan,2);self.assertTrue(before<=source_counts([out]))
  self.assertTrue(placements<=placement_counts([out]));self.assertTrue(all(n==1 for n in source_counts([out]).values()))
 def test_no_ruling_no_outside_row_recovery(self):
  tab=self.fixture();self.material.edges=();self.assertEqual(self.pipeline.finalize_tables(self.page,[tab]),[tab])
 def test_one_rule_does_not_prove_band(self):
  tab=self.fixture();self.material.edges=self.material.edges[:1]
  self.assertEqual(self.pipeline.finalize_tables(self.page,[tab]),[tab])
 def test_layout_provenance_does_not_change_ruled_geometry(self):
  tab=self.fixture();tab.bbox_provenance=Poison(dict(grid_source='x',source_gnn_indices=[999]))
  self.assertEqual(self.pipeline.finalize_tables(self.page,[tab])[0].placements[0][0].text,'real caption')
 def test_actual_vertical_rule_prevents_spanning_cell(self):
  tab=self.fixture();self.material.edges+=(dict(orientation='v',x0=10,x1=10,top=0,bottom=10,ruling_origin='vector'),)
  self.assertEqual(self.pipeline.finalize_tables(self.page,[tab]),[tab])
 def test_other_actual_table_obstacle_prevents_ruled_recovery(self):
  tab=self.fixture();other=self.tab([['','']],y=0,refs=True);other.bbox=(0,0,20,10)
  self.assertEqual(self.pipeline.finalize_tables(self.page,[tab,other]),[tab,other])
 def test_caption_word_crossing_band_boundary_is_not_accepted(self):
  tab=self.fixture();w=self.material.words[0];self.material.words[0]=(w[0],-1,w[2],8,w[4])
  self.assertEqual(self.pipeline.finalize_tables(self.page,[tab]),[tab])
 def test_multi_line_content_is_not_one_spanning_band(self):
  tab=self.fixture();words=self.material.words;words[:1]=[(2,1,18,3,'line1'),(2,7,18,9,'line2')]
  # A different source scenario is explicitly supplied by its real fixture producer.
  self.material=Material(words,self.material.edges);self.page._refine_words_cache=self.material.words
  tab=self.tab([['a','b']],y=10,refs=True)
  self.assertEqual(self.pipeline.finalize_tables(self.page,[tab]),[tab])
 def test_rule_word_producer_exception_propagates(self):
  tab=self.fixture()
  with patch('pymupdf4llm._table_pipeline.ruled_leading_row._span_claim_text_in_rect',side_effect=ValueError('actual source failure')):
   with self.assertRaisesRegex(ValueError,'actual source failure'):self.pipeline.finalize_tables(self.page,[tab])
 def test_final_role_failure_is_not_empty_success(self):
  tab=self.fixture()
  with patch.object(self.header,'apply_roles',side_effect=RuntimeError('actual role failure')):
   with self.assertRaisesRegex(RuntimeError,'actual role failure'):self.pipeline.finalize_tables(self.page,[tab])

class SourceContracts(FeatureBase):
 def set_words(self,words):
  self.material=Material(words);self.page._refine_words_cache=self.material.words
 def test_no_new_gnn_source_factory(self):
  self.set_words([(1,1,9,9,'same'),(11,1,19,9,'same')]);refs=node_sources(self.material.sources)
  self.assertIs(refs[0],self.material.sources[0].sources[0]);self.assertEqual([r.index for r in refs],[0,1])
  self.assertEqual({r.kind for r in refs},{'word'})
 def test_missing_producer_fails_explicitly(self):
  with self.assertRaises(ValueError):node_sources((NS(index=0,bbox=(0,0,1,1),text='x'),))
 def test_stale_source_index_and_snapshot_rejected(self):
  self.set_words([(1,1,9,9,'actual')]);s=self.material.sources[0]
  self.material.words[0]=(1,1,9,9,'changed')
  with self.assertRaises(ValueError):node_sources((s,))
  ref=CellSource('word',-1,(1,1,9,9),'actual',self.material.words)
  with self.assertRaises(ValueError):node_sources((NS(text='actual',sources=(ref,)),))
 def test_glyph_and_vertical_source_refs_borrowed_without_retyping(self):
  refs=(CellSource('glyph',0,(0,0,1,1),'g',[{'text':'g','bbox':(0,0,1,1),'font_xrefs':(7,),'char_index':2}],(7,2)),
        CellSource('vertical_line',0,(0,0,1,1),'v',[((0,0,1,1),'v')]))
  out=node_sources((NS(text='g v',sources=refs),))
  self.assertTrue(all(a is b for a,b in zip(refs,out)))

class PendingContracts(FeatureBase):
 def test_pending_roles_consumed_on_current_grid(self):
  tab=self.tab([['Only','Header'],['a','1']])
  self.pipeline._pending_parent_roles={id(tab.placements):(tab.placements,HeaderRegion(top_header_rows=1,section_header_rows=()))}
  out=self.pipeline.split_table(self.page,tab)
  self.assertEqual(self.pipeline._pending_parent_roles,{})
  self.assertEqual(out[0].header_rows,1)
  self.assertEqual(self.header.calls[0][1],(0,0,20,20))
