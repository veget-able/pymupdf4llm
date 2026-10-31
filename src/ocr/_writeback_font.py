"""Script-aware OCR serialization, ported from c0e9751; not REC routing.

Page resource aliases are resolved before replacement and never shadow an
existing PDF font. Non-Devanagari strings retain the original CJK writeback.
"""
import math
import unicodedata
import pymupdf

FONT = pymupdf.Font("cjk")
FONTNAME = "myfont"
DEVANAGARI_FONTNAME = "devanagari_font"
DEVANAGARI_SCRIPT = pymupdf.mupdf.UCDN_SCRIPT_DEVANAGARI
REPLACEMENT_UNICODE = chr(0xFFFD)
_devanagari_font = None

class OCRFontCoverageError(RuntimeError):
    """Raised when no declared write-back font covers an OCR string."""

def adjust_width(text, fontsize, rect, font=FONT):
    """Compute matrix to adjust text width.

    We must ensure that inserted text has the width of the rectangle.
    The computed matrix will do this scaling.
    """
    tl = font.text_length(text, fontsize)
    if tl > 0:
        return pymupdf.Matrix(rect.width / tl, 1)
    return pymupdf.Matrix(1, 1)

def _contains_devanagari(text):
    return any(0x0900 <= ord(char) <= 0x097F for char in text)

def _font_covers(font, text):
    """Return whether *font* covers every non-control codepoint in *text*."""
    return all(
        unicodedata.category(char) == "Cc" or font.has_glyph(ord(char)) != 0
        for char in text
    )

def _get_devanagari_font():
    """Lazily load MuPDF's built-in Noto Serif Devanagari font."""
    global _devanagari_font
    if _devanagari_font is None:
        font = pymupdf.Font(script=DEVANAGARI_SCRIPT)
        if not _font_covers(font, "".join(map(chr, range(0x0900, 0x0980)))):
            raise OCRFontCoverageError("MuPDF Devanagari font is incomplete")
        _devanagari_font = font
    return _devanagari_font

def _select_writeback_font(text):
    """Return the declared write-back font and page resource for an OCR string.

    Existing RapidOCR write-back has always used the CJK font without a
    preflight coverage check.  Preserve that path exactly for strings that do
    not contain Devanagari: MuPDF's glyph probe is not authoritative for every
    legacy OCR result (for example U+2206).  The stricter, glyph-complete
    choice is only needed for strings which require the Devanagari fallback.
    """
    if not _contains_devanagari(text):
        return FONT, FONTNAME

    if "\x00" in text or REPLACEMENT_UNICODE in text:
        raise OCRFontCoverageError(
            "OCR output contains a forbidden control or replacement glyph"
        )
    if _font_covers(FONT, text):
        return FONT, FONTNAME
    if _contains_devanagari(text):
        font = _get_devanagari_font()
        if _font_covers(font, text):
            return font, DEVANAGARI_FONTNAME
    raise OCRFontCoverageError("no declared write-back font covers OCR output")

def _grapheme_clusters(text):
    """Return the write-back clusters that must not be split between fonts.

    OCR strings are already Unicode text, so this intentionally needs only the
    cluster extensions relevant to the two declared fonts. Combining marks,
    Devanagari virama, variation selectors, and join controls stay with the
    preceding base. A virama or ZWJ also keeps the following base in that
    cluster; ZWNJ remains with its preceding base but breaks the conjunct.
    """
    clusters = []
    attach_next = False
    for char in text:
        codepoint = ord(char)
        variation_selector = 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF
        extender = (
            unicodedata.category(char).startswith("M")
            or codepoint in (0x094D, 0x200C, 0x200D)
            or variation_selector
        )
        if not clusters:
            clusters.append(char)
        elif extender or attach_next:
            clusters[-1] += char
        else:
            clusters.append(char)
        attach_next = codepoint in (0x094D, 0x200D)
    return clusters

def _plan_mixed_devanagari_runs(text):
    """Choose maximal CJK/Devanagari font runs for a valid mixed string.

    The dynamic program minimizes font transitions. If multiple solutions have
    the same transition count, the lexicographically first CJK-preferred
    selection wins, which makes the legacy CJK choice deterministic whenever a
    cluster is covered by both declared fonts.
    """
    devanagari_font = _get_devanagari_font()
    candidates = []
    for cluster in _grapheme_clusters(text):
        choices = []
        if _font_covers(FONT, cluster):
            choices.append((FONT, FONTNAME))
        if _font_covers(devanagari_font, cluster):
            choices.append((devanagari_font, DEVANAGARI_FONTNAME))
        if not choices:
            raise OCRFontCoverageError("no declared write-back font covers OCR cluster")
        candidates.append((cluster, choices))

    # Each state stores (transition_count, CJK-preference tuple, selected runs).
    states = {}
    for cluster, choices in candidates:
        next_states = {}
        for font, fontname in choices:
            preference = 0 if fontname == FONTNAME else 1
            if not states:
                value = (0, (preference,), [(cluster, font, fontname)])
                next_states[fontname] = value
                continue
            for previous_name, (changes, preferences, selected) in states.items():
                value = (
                    changes + (previous_name != fontname),
                    preferences + (preference,),
                    selected + [(cluster, font, fontname)],
                )
                old = next_states.get(fontname)
                if old is None or value[:2] < old[:2]:
                    next_states[fontname] = value
        states = next_states

    _changes, _preferences, selected = min(states.values(), key=lambda value: value[:2])
    runs = []
    for cluster, font, fontname in selected:
        if runs and runs[-1][2] == fontname:
            runs[-1] = (runs[-1][0] + cluster, font, fontname)
        else:
            runs.append((cluster, font, fontname))
    return runs

def _prior_writeback_runs(text):
    """Return the existing single-font plan or a safe mixed-font plan."""
    if not _contains_devanagari(text):
        # Keep every legacy no-Devanagari decision and write-back path exact.
        font, fontname = _select_writeback_font(text)
        return [(text, font, fontname)]

    if "\x00" in text or REPLACEMENT_UNICODE in text:
        raise OCRFontCoverageError("OCR output contains a forbidden control or replacement glyph")
    if _font_covers(FONT, text):
        return [(text, FONT, FONTNAME)]
    devanagari_font = _get_devanagari_font()
    if _font_covers(devanagari_font, text):
        return [(text, devanagari_font, DEVANAGARI_FONTNAME)]
    return _plan_mixed_devanagari_runs(text)

def _prepare_writeback(text, rect):
    """Preflight all font runs and their finite natural widths before mutation."""
    fontsize = float(rect.height)
    if not math.isfinite(fontsize) or fontsize <= 0 or not math.isfinite(float(rect.width)) or rect.width <= 0:
        raise OCRFontCoverageError("OCR write-back rectangle has no finite positive size")
    runs = []
    natural_width = 0.0
    for run_text, font, fontname in _plan_writeback_runs(text):
        width = float(font.text_length(run_text, fontsize))
        if not math.isfinite(width) or width <= 0:
            raise OCRFontCoverageError("OCR write-back font run has no finite positive width")
        natural_width += width
        runs.append((run_text, font, fontname, width))
    if not math.isfinite(natural_width) or natural_width <= 0:
        raise OCRFontCoverageError("OCR write-back has no finite positive natural width")
    return runs, natural_width

def _insert_writeback(page, rect, text, prepared, inserted_fontnames, fontnames=None):
    """Insert a preflighted plan, preserving the existing one-font path exactly."""
    runs, natural_width = prepared
    if fontnames is None:
        fontnames = resolve_fontnames(page, [prepared])
    runs = [(text, font, fontnames[name], width)
            for text, font, name, width in runs]
    for _run_text, font, fontname, _width in runs:
        if fontname not in inserted_fontnames:
            page.insert_font(fontname=fontname, fontbuffer=font.buffer)
            inserted_fontnames.add(fontname)

    fontsize = rect.height
    baseline = rect.bl + (0, -0.2 * fontsize)
    if len(runs) == 1:
        # This is precisely the prior selected-font insertion operation.
        _run_text, font, fontname, _width = runs[0]
        mat = adjust_width(text, fontsize, rect, font=font)
        page.insert_text(
            baseline,
            text,
            fontsize=fontsize,
            fontname=fontname,
            morph=(rect.bl, mat),
        )
        return

    scale = rect.width / natural_width
    if not math.isfinite(scale) or scale <= 0:
        raise OCRFontCoverageError("OCR write-back scale is not finite and positive")
    before_spans = _capture_writeback_spans(page)
    cursor = baseline
    source_offset = 0
    source_parts = []
    for run_text, _font, fontname, width in runs:
        source_parts.append(dict(text=run_text, origin=(cursor.x, cursor.y),
                                 start=source_offset, end=source_offset+len(run_text)))
        source_offset += len(run_text)
        page.insert_text(
            cursor,
            run_text,
            fontsize=fontsize,
            fontname=fontname,
            morph=(cursor, pymupdf.Matrix(scale, 1)),
        )
        cursor += (width * scale, 0)
    # PDF number serialization rounds the emitted transforms. Capture actual
    # new text origins rather than widening a coordinate-matching threshold.
    _record_mixed_writeback(page, text, source_parts, before_spans)


def resolve_fontnames(page, plans):
    """Choose unused page resource names, without modifying PDF contents.

    Even an embedded font with the same display name need not be the same font.
    Reserve an unused alias rather than relying on insert_font replacing it.
    The no-collision legacy names stay exact.
    """
    used = {row[4] for row in page.get_fonts(full=True)} if hasattr(page, 'get_fonts') else set()
    aliases = {}
    for runs, _width in plans:
        for _text, _font, preferred, _advance in runs:
            if preferred in aliases:
                continue
            name = preferred
            ordinal = 1
            while name in used:
                name = f'{preferred}_{ordinal}'
                ordinal += 1
            aliases[preferred] = name
            used.add(name)
    return aliases






_extended_fonts = None

def _fallback_fonts():
    global _extended_fonts
    if _extended_fonts is None:
        _extended_fonts = [(pymupdf.Font('helv'), 'ocr_latin_font'),
                           (pymupdf.Font('zapfdingbats'), 'ocr_symbol_font')]
    return _extended_fonts


def _plan_writeback_runs(text):
    # Preserve every prior plan that already covers the actual output string.
    try:
        prior = _prior_writeback_runs(text)
    except OCRFontCoverageError:
        if _contains_devanagari(text):
            raise
        prior = [(text, FONT, FONTNAME)]
    if all(_font_covers(font, value) for value, font, _name in prior):
        return prior
    fonts = [(FONT, FONTNAME)] + _fallback_fonts()
    if _contains_devanagari(text):
        fonts.append((_get_devanagari_font(), DEVANAGARI_FONTNAME))
    states = {}
    for cluster in _grapheme_clusters(text):
        choices = [(index,font,name) for index,(font,name) in enumerate(fonts)
                   if _font_covers(font, cluster)]
        if not choices:
            # Keep the pre-existing unsupported-output policy outside the
            # declared font pool; this experiment does not add new rejections.
            return prior
        following = {}
        for index,font,name in choices:
            previous_states = states.items() if states else [(None,(0,(),[]))]
            for previous,(changes,preferences,selected) in previous_states:
                value=(changes + (previous is not None and previous != name),
                       preferences+(index,),selected+[(cluster,font,name)])
                if name not in following or value[:2] < following[name][:2]:
                    following[name]=value
        states=following
    if not states:
        return prior
    selected=min(states.values(),key=lambda value:value[:2])[2]
    runs=[]
    for cluster,font,name in selected:
        if runs and runs[-1][2]==name:
            runs[-1]=(runs[-1][0]+cluster,font,name)
        else:
            runs.append((cluster,font,name))
    return runs


def annotate_mixed_writeback_spans(page, blocks):
    """Attach exact source-contiguity evidence; never infer it from font or gap.

    Mark only one-to-one text/origin matches to this callback's mixed writes.
    Native spans, changed strings, duplicates, and uncertain matches stay as-is.
    No PDF, model input, text, or span geometry is modified here.
    """
    from collections import defaultdict
    tolerance = .001  # Existing PDF text-origin identity tolerance, in points.
    parts = []
    index = defaultdict(list)
    for group_id, group in enumerate(getattr(page, '_pymupdf4llm_mixed_writeback_groups', [])):
        for part in group['parts']:
            ordinal = len(parts)
            parts.append((group_id, part))
            x, y = part['origin']
            index[(part['text'], round(x/tolerance), round(y/tolerance))].append(ordinal)
    matches = []
    counts = defaultdict(int)
    for block in blocks:
        for line in block.get('lines', []):
            for span in line['spans']:
                if 'origin' not in span:
                    continue
                x, y = span['origin']
                qx, qy = round(x/tolerance), round(y/tolerance)
                candidates = []
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for ordinal in index.get((span['text'], qx+dx, qy+dy), []):
                            part = parts[ordinal][1]
                            if max(abs(x-part['origin'][0]), abs(y-part['origin'][1])) <= tolerance:
                                candidates.append(ordinal)
                if len(candidates) == 1:
                    ordinal = candidates[0]
                    matches.append((span, ordinal))
                    counts[ordinal] += 1
    for span, ordinal in matches:
        if counts[ordinal] != 1:
            continue
        group_id, part = parts[ordinal]
        span['_ocr_mixed_run'] = (group_id, part['start'], part['end'], span['text'])


def _capture_writeback_spans(page):
    if not hasattr(page, 'get_text'):
        return None
    return [span for block in page.get_text('dict')['blocks']
            for line in block.get('lines', []) for span in line['spans']]


def _record_mixed_writeback(page, text, parts, before):
    if before is None:
        return
    from collections import Counter
    identity = lambda span: (span['text'], span['font'], tuple(span['origin']))
    remaining = Counter(identity(span) for span in before)
    added = []
    for span in _capture_writeback_spans(page):
        key = identity(span)
        if remaining[key]:
            remaining[key] -= 1
        else:
            added.append(span)
    if any(remaining.values()):
        return  # Old spans changed or merged; ownership is uncertain.
    # Claim ownership only when the actual newly extracted spans are exactly
    # the runs just emitted, including repeated text in left-to-right order.
    added.sort(key=lambda span: span['origin'][0])
    if [span['text'] for span in added] != [part['text'] for part in parts]:
        return
    if any(left['origin'][0] >= right['origin'][0] for left, right in zip(added, added[1:])):
        return
    actual = [dict(part, origin=tuple(span['origin'])) for part, span in zip(parts, added)]
    page.__dict__.setdefault('_pymupdf4llm_mixed_writeback_groups', []).append(
        dict(text=text, parts=actual))
