"""Validate existing native CellSource references; no restoration policy."""
from pymupdf._table_spans import CellSource


def node_sources(nodes):
    """Borrow already produced references; an occurrence is not a new source.

    NativeSource supplies the producer's real CellSource objects. Legacy
    SourceNode does not: inventing a gnn_node reference would hide that missing
    contract. Keep failures explicit rather than matching strings or boxes.
    """
    result = []
    for node in nodes:
        refs = getattr(node, 'sources', None)
        if refs is None or (node.text.strip() and not refs):
            raise ValueError('Native occurrence has no produced CellSource references')
        if len(refs) == 1 and hasattr(node, 'bbox') and (
                tuple(node.bbox) != tuple(refs[0].bbox) or node.text != refs[0].text):
            raise ValueError('Native occurrence and producer snapshots disagree')
        for ref in refs:
            if not isinstance(ref, CellSource) or ref.collection is None:
                raise ValueError('Invalid native occurrence producer reference')
            if ref.kind not in ('word', 'vertical_line', 'glyph'):
                raise ValueError('Native occurrence cannot create a detector source')
            if not isinstance(ref.index, int) or not 0 <= ref.index < len(ref.collection):
                raise ValueError('Invalid native occurrence producer index')
            if ref.kind == 'word':
                word = ref.collection[ref.index]
                if tuple(word[:4]) != tuple(ref.bbox) or str(word[4]) != ref.text:
                    raise ValueError('Native occurrence producer snapshot changed')
            elif ref.kind == 'glyph':
                record = ref.collection[ref.index]
                if (tuple(record['bbox']) != tuple(ref.bbox) or record['text'] != ref.text
                        or (*record['font_xrefs'], record['char_index']) != tuple(ref.scope)):
                    raise ValueError('Native glyph producer snapshot changed')
            result.append(ref)
    return tuple(result)
