from types import SimpleNamespace
from unittest.mock import patch

from pymupdf._table_spans import SpanCell
from pymupdf4llm.helpers.table_html import reconstruct as rec
from pymupdf4llm._table_pipeline import grid_ownership as go
from pymupdf4llm._table_pipeline.table_content_recovery import SourceNode, cell_ownership


def tab(x0=20,x1=120,y0=0,rows=3):
    placements=[[SpanCell((x0,y0+r*10,(x0+x1)/2,y0+(r+1)*10),'A'+str(r),1,1,'td'),
                 SpanCell(((x0+x1)/2,y0+r*10,x1,y0+(r+1)*10),'B'+str(r),1,1,'td')] for r in range(rows)]
    return SimpleNamespace(bbox=(x0,y0,x1,y0+rows*10),placements=placements,header_rows=0,section_rows=(),bbox_provenance={})


def test_lateral_empty_middle_cell_cannot_cover_other_table():
    target=tab();obstacle=tab(0,12,10,1)
    nodes=[SourceNode(0,(0,1,10,9),'left top'),SourceNode(1,(0,21,10,29),'left bottom')]
    output,decisions=go.absorb_grid_nodes([target,obstacle],nodes,{})
    assert not decisions and output[0] is target


def test_collision_also_covers_table_from_another_gnn_parent():
    target=tab();obstacle=tab(0,12,10,1)
    nodes=[SourceNode(0,(0,1,10,9),'left top'),SourceNode(1,(0,21,10,29),'left bottom')]
    output,decisions=go.absorb_grid_nodes([target],nodes,{},obstacles=[obstacle])
    assert not decisions and output[0] is target


def test_empty_residual_does_not_access_grid():
    t=tab();n=SourceNode(0,(21,1,50,9),'A0')
    with patch.object(go,'_table_grid_matrices',side_effect=AssertionError('unnecessary matrix access')):
        assert go.absorb_grid_nodes([t],[n],{0:dict(table=0)})==([t],[])


def test_unchanged_table_reuses_existing_matrix():
    t=tab();rec._table_grid_matrices(t,retain=True)
    n=SourceNode(0,(21,-12,50,-5),'isolated title')
    with patch.object(rec,'_placement_grid_matrices',side_effect=AssertionError('unnecessary matrix build')):
        out,ops=go.absorb_grid_nodes([t],[n],{})
    assert not ops and out[0] is t


def test_role_change_reuses_but_new_placements_invalidate_cache():
    t=tab();cached=rec._table_grid_matrices(t,retain=True)
    t.placements[0][0].tag='th'
    assert rec._table_grid_matrices(t,retain=True) is cached
    n=SourceNode(0,(71,31,100,36),'2.4813')
    out,ops=go.absorb_grid_nodes([t],[n],{})
    assert ops and rec._table_grid_matrices(out[0],retain=True)[0]==4
    assert rec._table_grid_matrices(t,retain=True) is cached


def test_planned_text_missing_in_actual_cells_rolls_back():
    t=tab();n=SourceNode(0,(71,31,100,36),'2.4813');original=go._updated
    def damaged(*a):
        result=original(*a);result.placements[-1][-1].text=''
        return result
    with patch.object(go,'_updated',damaged):
        out,ops=go.absorb_grid_nodes([t],[n],{})
    assert out[0] is t and not ops


def test_existing_accepted_node_loss_rolls_back():
    t=tab();old=SourceNode(0,(21,1,50,9),'A0');new=SourceNode(1,(71,31,100,36),'2.4813')
    nodes=[old,new];accepted=cell_ownership([t],nodes);original=go._updated
    def damaged(*a):
        result=original(*a)
        result.placements[0]=result.placements[0][1:]
        return result
    with patch.object(go,'_updated',damaged):
        out,ops=go.absorb_grid_nodes([t],nodes,accepted)
    assert out[0] is t and not ops and cell_ownership(out,nodes)==accepted


def test_valid_lateral_column_is_admitted_and_idempotent():
    t=tab();nodes=[SourceNode(0,(0,1,10,9),'left top'),SourceNode(1,(0,21,10,29),'left bottom')]
    out,ops=go.absorb_grid_nodes([t],nodes,{})
    accepted=cell_ownership(out,nodes)
    assert len(ops)==1 and set(accepted)=={0,1}
    assert out[0].placements[1][0].text==''
    assert go.absorb_grid_nodes(out,nodes,accepted)==(out,[])


def test_post_r6_node_loss_reverts_entire_restoration():
    from pymupdf4llm._table_pipeline import table_content_pipeline as pipeline
    from pymupdf4llm._table_pipeline.fragment_consolidation import FragmentConsolidationPipeline
    from pymupdf._table_headers import HeaderRegion
    original=tab();original.bbox_provenance={'source_gnn_indices':[0]}
    old=SourceNode(0,(21,1,50,9),'A0');new=SourceNode(1,(71,31,100,36),'2.4813')
    pipeline_object=object.__new__(pipeline.ContentRestorationPipeline)
    pipeline_object.events=[]
    pipeline_object.restoration_contexts={(0,(0,)):SimpleNamespace(source_nodes=[old,new],split_selected=False)}
    def damage(page,grid,region):
        # Return an independently corrupted post-role grid, keeping the original intact.
        rows=[[SpanCell(c.bbox,c.text,c.colspan,c.rowspan,c.tag) for c in row] for row in grid]
        rows[-1][-1].text=''
        return rows,HeaderRegion(top_header_rows=0,section_header_rows=())
    pipeline_object.header=SimpleNamespace(apply_roles=damage)
    def keep_pending(tables,nodes,accepted,**kwargs):
        return tables,tuple({'node_index':n.index} for n in nodes if n.index not in accepted)
    # This test isolates post-role rollback; output-source validation has its
    # own producer-backed tests in test_cell_source_delivery.
    with patch.object(FragmentConsolidationPipeline,'finalize_tables',lambda self,page,tables:tables),patch.object(pipeline,'retain_unassigned',keep_pending),patch('pymupdf4llm._table_pipeline.cell_output_boundary.external_content',return_value=[]):
        result=pipeline_object.finalize_tables(SimpleNamespace(number=0,_refine_words_cache=[(*n.bbox,n.text) for n in (old,new)]),[original])
    assert result[0] is original
    assert pipeline_object.events[0]['decisions']==[]
    assert pipeline_object.events[0]['cell_text']==1
