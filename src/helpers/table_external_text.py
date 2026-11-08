"""Common final table payload validation. No residual generation."""
def validate_table_delivery(page):
    """Validate final table payload IDs and HTML without residual Text emission."""
    delivered=[]
    for box in page.boxes:
        items=(box.table or {}).get('html_tables',[]) if box.boxclass=='table' else []
        if items:
            if box.table.get('html') != '\n\n'.join(item['html'] for item in items):
                raise ValueError('Rendered table HTML differs from delivered cell payload')
            delivered.extend(item['table_id'] for item in items)
    expected={item['table_id'] for item in (getattr(page,'find_tables',None) or ())}
    if set(delivered)!=expected or len(delivered)!=len(set(delivered)):
        raise ValueError('Final layout lost or duplicated a produced table payload')

