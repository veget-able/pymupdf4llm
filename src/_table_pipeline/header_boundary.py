"""Current-grid role boundary supplied by the actual role provider."""
from pymupdf import table

def structural_boundary(self,service,header,page,cells,*,purpose="structure",table_bbox=None):
    shape=tuple(tuple(None if c is None else tuple(c) for c in row) for row in cells)
    state,_=service.state(header,page);key=(state,shape,purpose,header.input_identity(table_bbox))
    if state is not None and key in self.boundaries:return self.boundaries[key]
    grid,initial_depth,initial_boundary=table._refine_model_grid(page,cells)
    if grid is None:raise RuntimeError('Early R6 requires valid preliminary placements')
    region=table.find_header_region(table._refine_placements_text_grid(grid));table._refine_tag_grid(grid,region.top_header_rows)
    previous=service.stage;service.stage='early' if purpose=='structure' else 'final'
    try:grid,predicted=header.apply_roles(page,grid,region,purpose=purpose,table_bbox=table_bbox)
    finally:service.stage=previous
    event=header.decisions[id(grid)][1]
    if not service.valid(header,grid,event,purpose=purpose):raise RuntimeError('Early R6 input invalid: '+str(event))
    boundary=max(1,min(predicted.top_header_rows,len(cells))) if cells else 0
    service.events[-1].update(initial_depth=initial_depth,initial_boundary=initial_boundary,resulting_boundary=boundary,boundary_consumer="row" if purpose=="structure" else "span")
    state,_=service.state(header,page)
    if state is not None:self.boundaries[state,shape,purpose,header.input_identity(table_bbox)]=boundary
    return boundary

