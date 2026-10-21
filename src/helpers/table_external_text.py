"""Deliver approved external table material as ordinary text using real spans.

This consumer cannot create cells, alter HTML, enlarge a table, or classify a
failed string match as external. It receives the structural producer's output.
"""
from copy import deepcopy
from pymupdf import Rect
from pymupdf._table_spans import _span_words_to_line_text


def _same_text(a, b):
    return ' '.join(a.split()) == ' '.join(b.split())


def _same_place(a, b):
    return all(abs(x-y) <= 1.0 for x,y in zip(a,b))


def _bbox(units):
    boxes = [u['bbox'] for u in units]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _text(units):
    return _span_words_to_line_text([(u['bbox'][1], u['bbox'][0], u['bbox'][3], u['text']) for u in units])


def _rendered_word_indices(boxes, page_words):
    """Only complete source words whose characters survive in emitted spans."""
    from .document_layout import get_plain_text
    positions = {}
    for box in boxes:
        if box.boxclass == 'table':
            continue
        for line in box.textlines or []:
            for span in line['spans']:
                if not _same_text(get_plain_text([span]), span.get('_source_text', '')):
                    continue
                for ref in span.get('_word_sources', []):
                    i = ref['index']
                    if not 0 <= i < len(page_words):
                        continue
                    word = page_words[i]
                    if list(word[:4]) != list(ref['bbox']) or word[4] != ref['text']:
                        continue
                    positions.setdefault(i, set()).update(ref['positions'])
    return {i for i, offsets in positions.items() if offsets == set(range(len(page_words[i][4])))}


def _not_already_rendered(record, boxes, page_words=(), *, rendered_words=None):
    from .document_layout import get_plain_text
    units = record.get('units') or [dict(index=record['node_index'],bbox=record['bbox'],text=record['text'])]
    keep = set(range(len(units)))
    if record.get('source_kind') == 'word' and page_words:
        covered = _rendered_word_indices(boxes, page_words) if rendered_words is None else rendered_words
        keep.difference_update(i for i,u in enumerate(units)
            if u['index'] in covered and list(page_words[u['index']][:4]) == list(u['bbox'])
            and page_words[u['index']][4] == u['text'])
    if not keep:
        return []
    for box in boxes:
        if box.boxclass == 'table':
            continue
        for line in box.textlines or []:
            spans = line['spans']
            # Both individual spans and the complete rendered line can prove an
            # occurrence. No comparison to the enclosing paragraph bbox/text.
            for group in [[s] for s in spans] + ([spans] if len(spans)>1 else []):
                area = _bbox([dict(bbox=s['bbox']) for s in group])
                # A residual can be one word inside a longer emitted span.
                # Verify the COMPLETE span against the existing producer words
                # at this physical position before reusing any subset. A mere
                # substring elsewhere in the paragraph proves nothing.
                if page_words and record.get('source_kind') == 'word':
                    from pymupdf._table_spans import _span_select_words_in_rect
                    candidates = _span_select_words_in_rect(page_words, Rect(area))
                    all_units = [dict(index=i,bbox=w[:4],text=w[4]) for i,w in candidates]
                    if all_units and _same_place(area, _bbox(all_units)) and _same_text(get_plain_text(group), _text(all_units)):
                        covered = {u['index'] for u in all_units}
                        keep.difference_update(i for i,u in enumerate(units) if u['index'] in covered)
                indices = [i for i in keep if Rect(area).contains(Rect(units[i]['bbox']))
                           or _same_place(area, units[i]['bbox'])]
                if not indices:
                    continue
                selected = [units[i] for i in sorted(indices)]
                if _same_place(area, _bbox(selected)) and _same_text(get_plain_text(group), _text(selected)):
                    keep.difference_update(indices)
    return [u for i,u in enumerate(units) if i in keep]


def emit_external_text(page):
    from .document_layout import LayoutBox, _bbox_provenance
    delivered=[]
    for box in page.boxes:
        items=(box.table or {}).get("html_tables", []) if box.boxclass=="table" else []
        if items:
            if box.table.get("html") != "\n\n".join(item["html"] for item in items):
                raise ValueError("Rendered table HTML differs from delivered cell payload")
            delivered.extend(item["table_id"] for item in items if "table_id" in item)
    expected=getattr(page,"find_tables",None)
    if expected is not None:
        ids={item["table_id"] for item in expected if "table_id" in item}
        if set(delivered)!=ids or len(delivered)!=len(set(delivered)):
            raise ValueError("Final layout lost or duplicated a produced table payload")
    pending=[]
    for box in page.boxes:
        if box.boxclass == 'table' and box.table:
            for item in box.table.get('html_tables', []):
                pending.extend(item.get('external_content', []))
    if not pending:
        return
    # Split a multi-table delivery box only when an external source must appear
    # between its children. Every child's HTML/geometry remains unchanged.
    boxes=[]
    for box in page.boxes:
        items=(box.table or {}).get('html_tables', [])
        midpoints=[(i['bbox'][1]+i['bbox'][3])/2 for i in items]
        split=len(items)>1 and any(min(midpoints)<(r['bbox'][1]+r['bbox'][3])/2<max(midpoints)
                                  and Rect([box.x0,box.y0,box.x1,box.y1]).intersects(Rect(r['bbox']))
                                  for r in pending)
        if not split:
            boxes.append(box)
            continue
        for item in items:
            child=deepcopy(box)
            child.x0,child.y0,child.x1,child.y1=item['bbox']
            child.bbox_provenance = dict(_bbox_provenance(item),
                layout_operation="external_text_table_split",
                bbox_owner_table_id=item.get("table_id"))
            child.table=dict(bbox=item['bbox'], row_count=item['rows'], col_count=item['cols'],
                             cells=item['cells'],extract=item['extract'],html_tables=[item],
                             html=item['html'],markdown=None)
            boxes.append(child)
    insertions = {}
    emitted_boxes = []
    rendered_words = _rendered_word_indices(boxes, getattr(page,"words",None) or ())
    for record in pending:
        units=_not_already_rendered(record, boxes + emitted_boxes, getattr(page,"words",None) or (), rendered_words=rendered_words)
        if not units:
            continue
        b=_bbox(units)
        span=dict(bbox=b,text=_text(units),size=max(1.,b[3]-b[1]),flags=0,font='',
                  color=0,char_flags=0,block=0,line=0,origin=[b[0],b[3]],dir=[1.,0.])
        extra=LayoutBox(*b,'text',textlines=[dict(bbox=b,spans=[span])])
        # Anchor delivery to its actual parent/children, preserving the page's
        # established column order. A global y sort would move a right-column
        # residual into an unrelated earlier left-column paragraph.
        key=tuple(record.get("source_gnn_indices", ()))
        related=[(i,box) for i,box in enumerate(boxes) if box.boxclass=="table"
                 and any(tuple(item.get("source_gnn_indices", ()))==key
                         for item in (box.table or {}).get("html_tables", []))]
        if not related:
            raise ValueError("External text lost its source table delivery owner")
        position=next((i for i,box in related
                       if (b[1]+b[3])/2 < (box.y0+box.y1)/2),related[-1][0]+1)
        insertions.setdefault(position, []).append(extra)
        emitted_boxes.append(extra)
    # Insert as a batch: repeated insertion after one table reverses the notes.
    page.boxes = []
    for i in range(len(boxes) + 1):
        page.boxes.extend(sorted(insertions.get(i, []), key=lambda box: (box.y0, box.x0)))
        if i < len(boxes):
            page.boxes.append(boxes[i])
