"""Passive Unicode damage inventory; no selection, mode normalization or OCR."""

import math
import pymupdf as p
from .page_state import is_ocr_span

STROKED = p.mupdf.FZ_STEXT_STROKED
FILLED = p.mupdf.FZ_STEXT_FILLED
REPLACEMENT = "\ufffd"
STATE_FLAGS = (
    p.TEXT_ACCURATE_BBOXES | p.TEXT_PRESERVE_IMAGES | p.TEXT_COLLECT_VECTORS
) & ~p.TEXT_CID_FOR_UNKNOWN_UNICODE
DAMAGE_FLAGS = (p.TEXTFLAGS_RAWDICT | p.TEXT_ACCURATE_BBOXES) & ~(
    p.TEXT_CID_FOR_UNKNOWN_UNICODE | p.TEXT_PRESERVE_IMAGES | p.TEXT_MEDIABOX_CLIP
)


def describe_unicode_span(span):
    text = span.get("text")
    if text is None:
        text = "".join(c["c"] for c in span.get("chars", []))
    damaged = REPLACEMENT in text
    return dict(
        ocr_like=is_ocr_span(span),
        has_unicode_damage=damaged,
        replacement_count=text.count(REPLACEMENT),
        replacement_offsets=[i for i, c in enumerate(text) if c == REPLACEMENT],
        alpha_zero=span["alpha"] == 0,
        glyphless_font=span.get("font") == "GlyphLessFont",
        has_fill=bool(span["char_flags"] & FILLED),
        has_stroke=bool(span["char_flags"] & STROKED),
    )


def damage_inventory(page):
    """Locate all U+FFFD without excluding OCR-like or unusable-geometry spans.

    Geometry usability is metadata, not a condition for detecting an error.
    No span joining, guessed whitespace, render, OCR or language model is used.
    """
    raw = page.get_text("rawdict", flags=DAMAGE_FLAGS, clip=p.INFINITE_RECT())
    spans = []
    for bi, block in enumerate(raw["blocks"]):
        for li, line in enumerate(block.get("lines", [])):
            for si, span in enumerate(line["spans"]):
                info = describe_unicode_span(span)
                if not info["has_unicode_damage"]:
                    continue
                chars = []
                offset = 0
                for ci, char in enumerate(span["chars"]):
                    box = list(char["bbox"])
                    usable = (
                        all(math.isfinite(x) for x in box)
                        and not (p.Rect(box) & page.rect).is_empty
                    )
                    for j, c in enumerate(char["c"]):
                        if c == REPLACEMENT:
                            chars.append(
                                dict(
                                    offset=offset + j,
                                    char_index=ci,
                                    bbox_pdf=box,
                                    origin=list(char["origin"]),
                                    synthetic=bool(char.get("synthetic")),
                                    geometry_usable=usable,
                                )
                            )
                    offset += len(char["c"])
                assert len(chars) == info["replacement_count"]
                spans.append(
                    dict(
                        span_id=f"{bi}/{li}/{si}",
                        text="".join(c["c"] for c in span["chars"]),
                        bbox_pdf=list(span["bbox"]),
                        direction=list(line["dir"]),
                        **info,
                        characters=chars,
                    )
                )
    return dict(
        span_count=len(spans),
        character_count=sum(s["replacement_count"] for s in spans),
        OCR_like_span_count=sum(s["ocr_like"] for s in spans),
        unusable_geometry_characters=sum(
            not c["geometry_usable"] for s in spans for c in s["characters"]
        ),
        spans=spans,
    )


def selection_metadata(page):
    """Compatibility view of correction-owned page metadata."""
    from .page_state import collect_page_state

    return collect_page_state(page).metadata
