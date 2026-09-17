"""Carry actual word/character occurrences through rendered span assembly.

DICT and RAWDICT come from the SAME existing TextPage. Word boxes use font
metrics, while these spans/chars can use ink boxes; their heights need not agree.
No text extraction or model call is performed here.
"""
from collections import defaultdict


def attach_word_sources(blocks, raw_blocks, words):
    """Bind original spans before get_raw_lines modifies boxes/joins text."""
    spans = [s for b in blocks if b['type'] == 0 for l in b['lines'] for s in l['spans']]
    raw = [(s, l['dir'], (bi,li)) for bi,b in enumerate(raw_blocks) for li,l in enumerate(b['lines']) for s in l['spans']]
    # Exact same TextPage traversal is the identity contract, not fuzzy matching.
    if len(spans) != len(raw) or any(s['text'] != ''.join(c['c'] for c in rs['chars'])
                                   or tuple(s['origin']) != tuple(rs['origin'])
                                   or s['font'] != rs['font']
                                   for s, (rs, _, _) in zip(spans, raw)):
        raise ValueError('Rendered spans and raw characters are not the same TextPage state')
    from pymupdf._table_word_geometry import match_word_characters
    chars, matches = match_word_characters(raw_blocks, words)
    by_span = defaultdict(list)
    for wi, hits in matches.items():
        positions = defaultdict(list); offset = 0
        for ci in hits:
            si, text, _, _ = chars[ci]
            positions[si].extend(range(offset, offset+len(text))); offset += len(text)
        for si, offsets in positions.items():
            by_span[si].append(dict(index=wi,bbox=list(words[wi][:4]),text=words[wi][4],positions=offsets))
    for si, sources in by_span.items():
        spans[si]['_word_sources'] = sources
        spans[si]['_source_text'] = spans[si]['text']
