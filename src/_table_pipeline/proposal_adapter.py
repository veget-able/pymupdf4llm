"""The only adapter reading layout groups: proposals, never table approval."""
from types import SimpleNamespace
from pymupdf import _table_union as union


def model_table_proposals(page):
    reader=union._layout_table_grids_base
    for index,group in enumerate(page.layout_information or ()):
        if not isinstance(group,dict) or group.get('class_name')!='table':continue
        prediction=group.get('table_grid')
        if prediction is None or not group.get('group_bbox'):continue
        if hasattr(prediction,'resolve'):prediction.resolve()
        entries=reader(SimpleNamespace(layout_information=[group]))
        for entry in entries:
            # Values are now concrete cells; policy receives no group, nodes,
            # retained predictor args, edge probabilities or model object.
            yield union._TableGridEntry(entry[0],entry[1],dict(entry.bbox_provenance,
                source_gnn_indices=[index]))
