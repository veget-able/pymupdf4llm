from types import SimpleNamespace
from unittest.mock import patch
import json
import pytest
from pymupdf._table_spans import SpanCell
from pymupdf4llm._table_pipeline.table_content_recovery import SourceNode,cell_ownership,retain_unassigned
from pymupdf4llm.helpers.table_html import reconstruct as rec
from pymupdf4llm.helpers import document_layout as dl


import inspect
import textwrap
from pymupdf4llm.helpers import document_layout as dl

source = inspect.getsource(dl.parse_document)
start = source.index("        find_tables_metadata = []\n")
stop = source.index("\n        # Dictionary with details for all tables.", start)
producer = compile(textwrap.dedent(source[start:stop]), dl.__file__, "exec")


def find_table_metadata(payloads):
    scope = {"page_html_tables_list": payloads, "_html_table_meta": dl._html_table_meta,
             "_bbox_provenance": dl._bbox_provenance}
    exec(producer, scope)
    return scope["find_tables_metadata"]


def table(html='<table><tr><td>A</td></tr></table>'):
    class Tab(SimpleNamespace):
        def to_html(self):return self.html
    return Tab(html=html,bbox=(0,0,20,10),placements=[[SpanCell((0,0,20,10),'A',1,1,'td')]],header_rows=0,section_rows=(),bbox_provenance={'source_gnn_indices':[4]})


def material():return [SourceNode(0,(1,1,10,9),'A'),SourceNode(1,(0,12,18,18),'pending text')]


def test_residual_is_not_a_cell_owner_or_caption():
    t=table();nodes=material();accepted=cell_ownership([t],nodes)
    out,pending=retain_unassigned([t],nodes,accepted,source_gnn_indices=[4])
    assert set(accepted)=={0} and [r['node_index'] for r in pending]==[1]
    assert pending[0]==dict(node_index=1,source_gnn_indices=[4],bbox=[0,12,18,18],text='pending text',original_text='pending text',cell_accepted=False,semantic_role=None,emission='pending')
    assert out[0].to_html()==t.to_html() and out[0].placements is t.placements
    assert out[0].bbox==t.bbox and out[0].bbox_provenance==t.bbox_provenance
    assert not hasattr(t,'unresolved_content')
    assert 'table' not in pending[0] and 'table_bbox' not in pending[0]


def test_preserves_original_source_spacing_and_real_caption():
    t=table('<table><caption>Real caption</caption><tr><td>A</td></tr></table>')
    nodes=material();originals=[nodes[0],SourceNode(1,nodes[1].bbox,'pendingtext')]
    out,pending=retain_unassigned([t],nodes,{0:dict(table=0)},source_gnn_indices=[4],original_nodes=originals)
    assert pending[0]['original_text']=='pendingtext' and pending[0]['text']=='pending text'
    assert out[0].to_html()==t.to_html()


def test_no_residual_does_not_copy_or_add_metadata():
    t=table();out,pending=retain_unassigned([t],material()[:1],{0:dict(table=0)},source_gnn_indices=[4])
    assert out[0] is t and not pending


def test_repartition_clears_stale_residual_without_mutating_old_output():
    t=table();nodes=material();first,pending=retain_unassigned([t],nodes,{0:dict(table=0)},source_gnn_indices=[4])
    second,pending2=retain_unassigned(first,nodes,{0:dict(table=0),1:dict(table=0)},source_gnn_indices=[4])
    assert not pending2 and not hasattr(second[0],'unresolved_content')
    assert first[0].unresolved_content==pending


def test_missing_carrier_and_unknown_ownership_fail_explicitly():
    with pytest.raises(ValueError,match='carrier'):retain_unassigned([],material(),{},source_gnn_indices=[4])
    with pytest.raises(ValueError,match='unknown'):retain_unassigned([table()],material(),{99:{}},source_gnn_indices=[4])


def test_serialization_roundtrip_preserves_pending_without_rendering():
    t=table();nodes=material();out,pending=retain_unassigned([t],nodes,{0:dict(table=0)},source_gnn_indices=[4])
    page=SimpleNamespace(number=0,find_tables=lambda **kw:SimpleNamespace(tables=out))
    with patch.object(rec,'_raster_lines',return_value=[]):payloads=rec.page_html_tables(page)
    assert len(payloads[0])==6 and payloads[0].unresolved_content is out[0].unresolved_content
    full=dl._html_table_meta(payloads[0]);compact=find_table_metadata(payloads)[0]
    assert all(k not in compact for k in ('html','cells','extract'))
    assert compact['unresolved_content']==list(pending)
    box=dl.LayoutBox(0,0,20,10,'table',table={'html':full['html'],'html_tables':[full]},bbox_provenance={})
    pl=dl.PageLayout(1,100,100,[box],raw_gnn_tables=[],find_tables=[compact])
    doc=dl.ParsedDocument(filename='fixture',page_count=1,toc=[],pages=[pl],metadata={})
    result=json.loads(json.dumps(doc.to_markdown(page_chunks=True)))
    assert result[0]['text']==t.to_html()+'\n\n'
    assert result[0]['find_tables'][0]['unresolved_content']==list(pending)
    assert 'unresolved_content' not in result[0]['page_boxes'][0]['html_tables'][0]
    assert 'pending text' not in result[0]['text']


def test_same_local_node_id_in_different_parents_stays_distinct():
    t=table();n=SourceNode(1,(0,12,18,18),'same')
    a,ra=retain_unassigned([t],[n],{},source_gnn_indices=[4])
    b,rb=retain_unassigned([t],[n],{},source_gnn_indices=[9])
    assert ra[0]['node_index']==rb[0]['node_index']
    assert ra[0]['source_gnn_indices']!=rb[0]['source_gnn_indices']
    assert a[0].unresolved_content is not b[0].unresolved_content


def test_pipeline_transports_pending_with_event_logging_disabled():
    from pymupdf4llm._table_pipeline.table_content_pipeline import ContentRestorationPipeline
    from pymupdf4llm._table_pipeline.fragment_consolidation import FragmentConsolidationPipeline
    class NoLog:
        def append(self,event):pass
    t=table();nodes=material();p=object.__new__(ContentRestorationPipeline)
    p.events=NoLog();p.restoration_contexts={(0,(4,)):SimpleNamespace(source_nodes=nodes,split_selected=False)}
    # Pending metadata remains separate from producer-backed external delivery.
    with patch.object(FragmentConsolidationPipeline,'finalize_tables',lambda self,page,tables:tables),patch('pymupdf4llm._table_pipeline.cell_output_boundary.external_content',return_value=[]):
        out=p.finalize_tables(SimpleNamespace(number=0,_refine_words_cache=[]),[t])
    assert out[0].to_html()==t.to_html()
    assert out[0].unresolved_content[0]['node_index']==1


def test_existing_one_argument_metadata_capture_hook_is_compatible():
    t=table();out,_=retain_unassigned([t],material(),{0:dict(table=0)},source_gnn_indices=[4])
    page=SimpleNamespace(number=0,find_tables=lambda **kw:SimpleNamespace(tables=out))
    with patch.object(rec,'_raster_lines',return_value=[]):payloads=rec.page_html_tables(page)
    original=dl._html_table_meta;observed=[]
    def capture(item):
        meta=original(item);observed.append(meta);return meta
    with patch.object(dl,'_html_table_meta',capture):result=find_table_metadata(payloads)
    assert 'html' in observed[0] and 'cells' in observed[0]
    assert 'html' not in result[0] and result[0]['unresolved_content']
