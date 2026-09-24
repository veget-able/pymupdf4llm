"""Portable V7 contract controls; no benchmark files, models, or PDF reads."""
from pymupdf4llm._table_pipeline.v7_region_rules import _region_band_split

def listing(*,reset=False,decimal=False,header=False,extra_column=False):
 labels=['Section Table Key' if header else 'Baseline','Detailed material condition','Alpha','Beta','Section Table Key' if header else 'Detailed material condition','Gamma','Delta','Epsilon']
 ys=[0,15,30,45,85,100,115,130];nodes=[]
 for i,(label,y) in enumerate(zip(labels,ys)):
  n=(i-3 if reset and i>=4 else i+1);value=str(n)+('.5' if decimal else '')
  nodes.extend([dict(bbox=[0,y,60,y+8],text=label),dict(bbox=[80,y,120,y+8],text=value)])
  if extra_column:nodes.append(dict(bbox=[140,y,180,y+8],text=str(i+20)))
 return nodes,[],[],[0,0,180 if extra_column else 120,138]

def test_continuing_integer_field_does_not_split_on_spatial_anchors():
 assert len(_region_band_split(*listing(),strict_gate=True))==1

def test_value_reset_preserves_headerless_stack_split():
 assert len(_region_band_split(*listing(reset=True),strict_gate=True))==2

def test_decimal_field_preserves_original_split():
 assert len(_region_band_split(*listing(decimal=True),strict_gate=True))==2

def test_independent_header_evidence_remains_eligible():
 assert len(_region_band_split(*listing(header=True),strict_gate=True))==2

def test_multicolumn_table_preserves_split():
 assert len(_region_band_split(*listing(extra_column=True),strict_gate=True))==2
