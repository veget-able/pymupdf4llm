"""Consume approved cells and retained source material without changing a grid.

Word selection is the existing producer's inclusive center rule. A source-node
bbox only selects candidate words; table envelopes never classify those words.
"""
from pymupdf import Rect
from pymupdf._table_spans import _span_select_words_in_rect, _span_words_to_line_text, _span_word_line_tuple


def _inside(box, item):
    x, y = (item[0] + item[2]) / 2, (item[1] + item[3]) / 2
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def external_content(tables, nodes, words, key, *, characters=(), word_geometry=None):
    """Return only unconsumed source units outside every approved cell.

    Missing producer evidence inside a cell is a delivery error, never permission
    to emit a duplicate Text box. No strings decide table/Text ownership.
    """
    cells = [c for t in tables for row in t.placements for c in row if c.bbox is not None]
    claims = []
    for c in cells:
        c.validate_source_content()
        if c.source_content is not None:
            claims.extend(c.source_content.sources)
    consumed_words = {r.index for r in claims if r.kind == 'word' and r.collection is words}
    other_claims = [r for r in claims if r.kind != 'word' or r.collection is not words]
    # Other refinements can own a different word-cache state; its actual source
    # boxes remain evidence, but unrelated indices never match by number alone.
    covered = lambda w: any(_inside(r.bbox, w) for r in other_claims)
    emitted = set()
    output = []
    for node in nodes:
        selected = _span_select_words_in_rect(words, Rect(node.bbox))
        if characters:
            # GNN uses glyph-ink boxes; the producer uses font-height words.
            # A thin dash or a partial word need not contain a word center.
            # Map retained nonblank glyph positions back to existing word units,
            # then use the SAME word-to-cell contract as the actual producer.
            node_chars = [ch for ch in characters if ch["text"].strip()
                          and _inside(node.bbox, (ch["x0"], ch["top"], ch["x1"], ch["bottom"]))]
            glyphs = [(ch["x0"], ch["top"], ch["x1"], ch["bottom"]) for ch in node_chars]
            # Math glyph ink can extend below its font-height word bbox. Finder
            # already preserves the original text matrix/baseline: convert its
            # bottom-up y to the same top-down page coordinates, without reads.
            for ch in node_chars:
                if "matrix" in ch and "y1" in ch:
                    x = (ch["x0"] + ch["x1"]) / 2
                    y = ch["top"] + ch["y1"] - ch["matrix"][5]
                    glyphs.append((x, y, x, y))
            # A node may contain a whole word AND a fragment of the next word.
            # Keep the direct selection and map only glyphs it does not cover.
            glyphs = [g for g in glyphs if not any(_inside(w[:4], g) for _, w in selected)]
            # The shared index indexes CENTERS, not rectangle overlap. It
            # cannot serve this glyph-in-word query without excluding the very
            # words being recovered. Scan the existing list only on this branch.
            if glyphs:
                indices = {i for i, _ in selected}
                selected += [(i,w) for i,w in enumerate(words)
                             if i not in indices and str(w[4]).strip()
                             and any(_inside(w[:4], glyph) for glyph in glyphs)]
                selected.sort(key=lambda item: item[0])
        remaining = []
        for index, word in selected:
            if index in emitted or index in consumed_words or covered(word):
                continue
            from pymupdf._table_word_geometry import glyph_cell_owners
            glyph_owners = glyph_cell_owners((word_geometry or {}).get(index, ()), [c.bbox for c in cells])
            if glyph_owners or any(_inside(c.bbox, word) for c in cells):
                raise ValueError(f'Unproved cell content at source word {index}; not external Text')
            remaining.append((index, word))
        if remaining:
            emitted.update(i for i, _ in remaining)
            boxes = [w[:4] for _, w in remaining]
            bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                    max(b[2] for b in boxes), max(b[3] for b in boxes))
            output.append(dict(source_gnn_indices=list(key), node_index=node.index,
                               source_kind='word', source_indices=[i for i, _ in remaining],
                               units=[dict(index=i, bbox=list(w[:4]), text=str(w[4])) for i,w in remaining],
                               bbox=list(bbox), text=_span_words_to_line_text([
                                   _span_word_line_tuple(w) for _, w in remaining])))
        elif not selected and node.text.strip():
            # GNN-only source has no smaller native unit. Preserve the whole
            # source only when disjoint; a crossing node cannot be guessed apart.
            consumed = any(r.kind == 'gnn_node' and r.scope == node.scope and r.index == node.index
                           for r in claims)
            if consumed or any(Rect(r.bbox).contains(Rect(node.bbox)) for r in claims):
                # A GNN fragment (e.g. 'Pr' in a produced 'Protection' word)
                # or a thin punctuation box can have no word center of its
                # own. Full containment in an ACTUAL consumed source unit
                # proves delivery; this is not containment in table/cell bbox.
                continue
            if any(Rect(node.bbox).intersects(Rect(c.bbox)) for c in cells):
                raise ValueError(f'GNN-only source {node.index} crosses a cell without producer proof')
            output.append(dict(source_gnn_indices=list(key), node_index=node.index,
                               source_kind='gnn_node', source_indices=[node.index],
                               bbox=list(node.bbox), text=node.text))
    return output
