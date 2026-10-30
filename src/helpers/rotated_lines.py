"""Direction-aware grouping while preserving the horizontal extraction algorithm."""
from copy import deepcopy
from math import hypot
import pymupdf as p
from .utils import are_disjoint, almost_in_bbox

def _horizontal(direction):
    return abs(1-direction[0]) <= 1e-3

def _union(rectangles):
    result=p.Rect()
    for rectangle in rectangles: result |= p.Rect(rectangle)
    return result

def directional_raw_lines(original, textpage=None, blocks=None, clip=None, tolerance=3, ignore_invisible=True, only_horizontal=False, audit=None):
    if blocks is None:
        if textpage is None:
            return original(textpage=textpage, blocks=blocks, clip=clip, tolerance=tolerance, ignore_invisible=ignore_invisible, only_horizontal=only_horizontal)
        blocks = [b for b in textpage.extractDICT()['blocks'] if b['type'] == 0]
    if clip is None:
        clip = textpage.rect if textpage is not None else None
    if only_horizontal or not any((not _horizontal(line['dir']) for b in blocks for line in b.get('lines', []))):
        return original(textpage=textpage, blocks=blocks, clip=clip, tolerance=tolerance, ignore_invisible=ignore_invisible, only_horizontal=only_horizontal)
    horizontal = original(blocks=blocks, clip=clip, tolerance=tolerance, ignore_invisible=ignore_invisible, only_horizontal=True)
    groups = {}
    for bno, block in enumerate(blocks):
        if clip is not None and are_disjoint(block['bbox'], clip):
            continue
        for line in block.get('lines', []):
            direction = line['dir']
            if _horizontal(direction):
                continue
            if clip is not None and are_disjoint(line['bbox'], clip):
                continue
            length = hypot(*direction)
            if not length:
                raise ValueError('Invalid zero-length text direction')
            direction = tuple((v / length for v in direction))
            key = tuple((round(v, 6) for v in direction))
            group = groups.setdefault(key, dict(direction=direction, blocks={}, original_boxes=[]))
            spans = [deepcopy(s) for s in line['spans'] if clip is None or almost_in_bbox(p.Rect(s['bbox']), clip, portion=0.51)]
            if not spans:
                continue
            transformed = deepcopy(line)
            transformed['spans'] = spans
            group['blocks'].setdefault(bno, dict(type=0, lines=[]))['lines'].append(transformed)
            group['original_boxes'].extend((s['bbox'] for s in spans))
    bundles = []
    if horizontal:
        bundles.append((_union((r[0] for r in horizontal)), horizontal))
    for group in groups.values():
        c, s = group['direction']
        matrix = p.Matrix(c, -s, s, c, 0, 0)
        inverse = ~matrix
        normalized = list(group['blocks'].values())
        for block in normalized:
            for line in block['lines']:
                for span in line['spans']:
                    span['bbox'] = (p.recover_quad(group['direction'], span) * matrix).rect
                    if 'origin' in span:
                        span['origin'] = tuple(p.Point(span['origin']) * matrix)
                line['bbox'] = _union((span['bbox'] for span in line['spans']))
                line['dir'] = (1.0, 0.0)
            block['bbox'] = _union((line['bbox'] for line in block['lines']))
        if not normalized:
            continue
        normal_clip = _union((b['bbox'] for b in normalized)) + (-1, -1, 1, 1)
        lines = original(blocks=normalized, clip=normal_clip, tolerance=tolerance, ignore_invisible=ignore_invisible, only_horizontal=True)
        for row in lines:
            row[0] = p.Rect(row[0]) * inverse
            for span in row[1]:
                span['bbox'] = p.Rect(span['bbox']) * inverse
                if 'origin' in span:
                    span['origin'] = tuple(p.Point(span['origin']) * inverse)
                span['dir'] = group['direction']
        if lines:
            bundles.append((_union(group['original_boxes']), lines))
            if audit is not None:
                audit['direction_groups'] = audit.get('direction_groups', 0) + 1
                audit['rotated_lines'] = audit.get('rotated_lines', 0) + len(lines)
                audit['rotated_spans'] = audit.get('rotated_spans', 0) + sum((len(r[1]) for r in lines))
    bundles.sort(key=lambda item: (item[0].y0, item[0].x0))
    return [row for _, rows in bundles for row in rows]
