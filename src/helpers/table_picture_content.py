"""A source-owned text view for pictures containing accepted HTML tables.

This consumer never changes a picture's graphics, crop or layout class.
Unknown source references remain visible; bbox containment is not ownership.
"""
from collections import Counter
from copy import deepcopy


def prepare_picture_text(blocks, raw_blocks, words, tables, *, word_geometry=None):
    """Return an independent text view and correspondence counts.

    DICT and RAWDICT must be from the same output TextPage, before formatting.
    ``word_geometry`` may be borrowed from attach_word_sources on that state.
    No extraction, model inference, or caller-owned data mutation occurs here.
    """
    from pymupdf._table_word_geometry import match_word_characters

    if raw_blocks is None:
        return None, {"skipped_missing_raw": 1}
    spans = [s for b in blocks if b["type"] == 0
             for line in b["lines"] for s in line["spans"]]
    raw = [s for b in raw_blocks if b["type"] == 0
           for line in b["lines"] for s in line["spans"]]
    visible = [(i, s) for i, s in enumerate(spans) if s["text"].strip()]
    raw_visible = [(i, s) for i, s in enumerate(raw)
                   if "".join(c["c"] for c in s["chars"]).strip()]
    if len(visible) != len(raw_visible) or any(
        s["text"] != "".join(c["c"] for c in r["chars"])
        or tuple(s["origin"]) != tuple(r["origin"]) or s["font"] != r["font"]
        for (_, s), (_, r) in zip(visible, raw_visible)
    ):
        return None, {"skipped_state_mismatch": 1}
    raw_by_rendered = {i: j for (i, _), (j, _) in zip(visible, raw_visible)}
    chars, matches = (match_word_characters(raw_blocks, words)
                      if word_geometry is None else word_geometry)
    stats, accepted = Counter(), set()
    for table in tables:
        for cell in table.get("cell_sources", ()):
            for source in cell["sources"]:
                if source["kind"] != "word":
                    stats["unsupported_source_kind"] += 1
                    continue
                wi = source["index"]
                # source_set is collection-local, not a global page identity.
                if not (0 <= wi < len(words)
                        and tuple(words[wi][:4]) == tuple(source["bbox"])
                        and words[wi][4] == source["text"]):
                    stats["unmatched_word_record"] += 1
                    continue
                if wi not in matches:
                    stats["unmatched_word_glyphs"] += 1
                    continue
                accepted.add(wi)
    owned = {ci for wi in accepted for ci in matches[wi]}
    positions = [(si, ri) for si, span in enumerate(raw)
                 for ri, ch in enumerate(span["chars"]) if ch["c"].strip()]
    assert len(positions) == len(chars)
    by_span = {}
    for ci in owned:
        si, ri = positions[ci]
        by_span.setdefault(si, set()).add(ri)
    # Copy only text, not potentially large raster image payloads.
    output = deepcopy([b for b in blocks if b["type"] == 0])
    si = 0
    for block in output:
        for line in block["lines"]:
            replacement = []
            for span in line["spans"]:
                raw_index = raw_by_rendered.get(si)
                remove = by_span.get(raw_index, set())
                si += 1
                if not remove:
                    replacement.append(span)
                    continue
                original_chars = raw[raw_index]["chars"]
                runs, run = [], []
                for ri, ch in enumerate(original_chars):
                    if ri in remove:
                        if run:
                            runs.append(run)
                            run = []
                    else:
                        run.append(ch)
                if run:
                    runs.append(run)
                retained_parts = []
                for run in runs:
                    lo, hi = 0, len(run)
                    while lo < hi and not run[lo]["c"].strip():
                        lo += 1
                    while hi > lo and not run[hi-1]["c"].strip():
                        hi -= 1
                    run = run[lo:hi]
                    if not run:
                        continue
                    part = dict(span)
                    part.pop("_word_sources", None)
                    part.pop("_source_text", None)
                    part["text"] = "".join(c["c"] for c in run)
                    part["origin"] = run[0]["origin"]
                    part["bbox"] = [
                        min(c["bbox"][0] for c in run), min(c["bbox"][1] for c in run),
                        max(c["bbox"][2] for c in run), max(c["bbox"][3] for c in run),
                    ]
                    replacement.append(part)
                    retained_parts.append(part["text"])
                expected = "".join(c["c"] for ri, c in enumerate(original_chars)
                                   if ri not in remove)
                assert "".join("".join(retained_parts).split()) == "".join(expected.split())
            line["spans"] = replacement
    stats.update(accepted_words=len(accepted), owned_glyphs=len(owned),
                 source_glyphs=len(chars), retained_glyphs=len(chars)-len(owned))
    return output, dict(stats)
