"""Independent Unicode markers and fixed symbol-density damage candidates.

The 50-character and one-third conditions apply only to the symbol heuristic.
Technical protection never hides Unicode markers or certifies text quality.
No render, model, language classifier, OCR, filename or benchmark ID is used.
"""
from collections import defaultdict
import unicodedata

import pymupdf as p
from ._damage_guard import inspect
from .unicode_damage import damage_inventory

MIN_BODY_NONSPACE = 50
EXCLUDED_SYMBOLS = frozenset('()[]{}' + chr(92))


def is_symbol(char):
    return unicodedata.category(char)[0] in 'PS' and char not in EXCLUDED_SYMBOLS


def periodic_symbol_positions(text):
    """Mask exact gap-sequence periods 1..3 repeated >=3 times; never U+FFFD."""
    bychar = defaultdict(list)
    prefix = [0]
    for index, char in enumerate(text):
        prefix.append(prefix[-1] + (unicodedata.category(char)[0] in 'LNM'))
        if is_symbol(char) and char != '\ufffd':
            bychar[char].append(index)
    masked = set()
    for sequence in bychar.values():
        gaps = [prefix[b] - prefix[a+1] for a, b in zip(sequence, sequence[1:])]
        for period in (1, 2, 3):
            index = 0
            while index + 3*period <= len(gaps):
                seed = gaps[index:index+period]
                end = index+period
                while end < len(gaps) and gaps[end] == seed[(end-index) % period]:
                    end += 1
                if end-index >= 3*period:
                    masked.update(sequence[index:end+1])
                    index = end-period+1
                else:
                    index += 1
    return masked


def assess_text(text):
    """Return page candidate plus source offsets, without changing the input."""
    split = inspect(text)
    offsets = [i for line in split['lines'] if line['language_check_applicable']
               for i in range(line['start'], line['end'])]
    body = ''.join(text[i] for i in offsets)
    assert body == split['residual_text']
    nonspace = sum(not char.isspace() for char in body)
    masked = periodic_symbol_positions(body)
    counted = {i for i, char in enumerate(body) if is_symbol(char)} - masked
    candidate = nonspace >= MIN_BODY_NONSPACE and 3*len(counted) >= nonspace
    return dict(candidate=candidate, nonspace=nonspace, symbol_count=len(counted),
                symbol_ratio=len(counted)/max(1, nonspace),
                masked_symbol_count=len(masked), eligible=nonspace >= MIN_BODY_NONSPACE,
                unicode_marker_offsets=split['unicode_replacement_offsets'],
                body_offsets=offsets, counted_symbol_offsets={offsets[i] for i in counted},
                short_input=nonspace < MIN_BODY_NONSPACE)


def character_key(char):
    return char['c'], round(char['origin'][0], 3), round(char['origin'][1], 3)


def span_has_symbol_damage(span, keys):
    if not keys:
        return False
    if 'chars' in span:
        return any(character_key(char) in keys for char in span['chars'])
    text = span.get('text', '')
    return bool(text and 'origin' in span and character_key(dict(c=text[0], origin=span['origin'])) in keys)


def inspect_page(page):
    """Choose mapped repair targets after the fixed symbol-page check.

    With no independently observed U+FFFD, a positive symbol page expands to
    its stored text. Wrong Unicode mappings can be letters or numbers, so no
    second per-span density test is applied in that scope. With any U+FFFD,
    retain the established span targets and technical-boundary protection.
    Neither scope certifies text quality; uncertain alignment stays preserved.
    """
    flags = p.TEXTFLAGS_TEXT & ~p.TEXT_CID_FOR_UNKNOWN_UNICODE
    tp = page.get_textpage(flags=flags, clip=p.INFINITE_RECT())
    text = tp.extractText().replace('\r\n', '\n').replace('\r', '\n')
    result = assess_text(text)
    result['symbol_character_keys'] = set()
    result['symbol_target_spans'] = 0
    result['source_alignment_exact'] = True
    if not result['candidate']:
        return result
    raw = tp.extractRAWDICT()
    pieces, spans, offset = [], [], 0
    for block in raw['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                start = offset
                for char in span['chars']:
                    pieces.append(char['c'])
                    offset += len(char['c'])
                spans.append((start, offset, span))
            pieces.append('\n')
            offset += 1
    if ''.join(pieces) != text:
        # Keep the page signal but do not guess individual replacement targets.
        result['source_alignment_exact'] = False
        return result
    eligible = set(result['body_offsets'])
    counted = result['counted_symbol_offsets']
    # A marker-free encoding error may affect spans whose decoded symbols are
    # sparse or absent. Use one target set for their render and replacement.
    # The independent inventory also sees markers outside extraction geometry.
    if not damage_inventory(page)['character_count']:
        for start, end, span in spans:
            if not any(not text[i].isspace() for i in range(start, end)):
                continue
            result['symbol_target_spans'] += 1
            result['symbol_character_keys'].update(character_key(char) for char in span['chars']
                                                  if not char.get('synthetic'))
        return result
    for start, end, span in spans:
        indices = [i for i in range(start, end) if i in eligible and not text[i].isspace()]
        if not indices or 3*sum(i in counted for i in indices) < len(indices):
            continue
        # Never replace a span that crosses an unprotected/protected boundary.
        if any(i not in eligible and not text[i].isspace() for i in range(start, end)):
            continue
        result['symbol_target_spans'] += 1
        result['symbol_character_keys'].update(character_key(char) for char in span['chars']
                                              if not char.get('synthetic'))
    return result
