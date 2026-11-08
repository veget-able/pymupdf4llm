"""Shared existing line/word/rowspan geometry; no H6 or header policy."""

GAP_RATIO = 1.5
CENTRE_TOLERANCE = 0.15

def _cluster_lines(words):
    lines = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        cy = (w[1] + w[3]) / 2
        for line in lines:
            if line["y0"] <= cy <= line["y1"] or w[1] <= (line["y0"] + line["y1"]) / 2 <= w[3]:
                line["y0"], line["y1"] = min(line["y0"], w[1]), max(line["y1"], w[3])
                line["words"].append(w)
                break
        else:
            lines.append({"y0": w[1], "y1": w[3], "words": [w]})
    for line in lines:
        height = max(1e-6, line["y1"] - line["y0"])
        segs, cur = [], []
        for w in sorted(line["words"], key=lambda w: w[0]):
            if cur and w[0] - cur[-1][2] > GAP_RATIO * height:
                segs.append(cur)
                cur = []
            cur.append(w)
        if cur:
            segs.append(cur)
        line["segments"] = [(min(w[0] for w in s), max(w[2] for w in s)) for s in segs]
        line["segment_words"] = segs
    return sorted(lines, key=lambda l: l["y0"])


def _word_crossings(words, bounds):
    """Interior boundaries that a single word straddles: only these justify
    merging two columns. Per-column labels that merely sit close together
    ("COLL/UMPD COLL/UMPD ...") cross no boundary word-wise."""
    return {b for b in bounds[1:-1] for w in words if w[0] + 1.0 < b < w[2] - 1.0}


def _rowspan_slots(band, slots, words, spans):
    """Slots whose band text is one line inside the slot, centred on the band
    and not under a spanning label: cells spanning both header rows. Returns
    {slot index: words}."""
    per = {}
    for w in words:
        cx = (w[0] + w[2]) / 2
        for i, s in enumerate(slots):
            if s is not None and s[0] <= cx <= s[1]:
                per.setdefault(i, []).append(w)
                break
    out = {}
    for i, ws in per.items():
        s0, s1 = slots[i]
        if any(w[0] < s0 - 1.0 or w[2] > s1 + 1.0 for w in ws):
            continue
        if any(x0 < s1 - 1.0 and x1 > s0 + 1.0 for x0, x1, _ in spans):
            continue
        if len(_cluster_lines(ws)) != 1:
            continue
        y0, y1 = min(w[1] for w in ws), max(w[3] for w in ws)
        if abs((y0 + y1) / 2 - (band.y0 + band.y1) / 2) <= CENTRE_TOLERANCE * band.height:
            out[i] = ws
    return out

