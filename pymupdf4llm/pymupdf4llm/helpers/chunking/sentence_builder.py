"""Step A: Convert LayoutBox textlines into SentenceUnits."""

import re
from collections import Counter, defaultdict
from typing import Optional

from .models import SentenceUnit

# Sentence-ending patterns
_SENT_END_EN = re.compile(
    r'(?<=[.!?])'        # after sentence-ending punctuation
    r'(?:\s*["\'\)\]]*)'  # optional closing quotes/brackets
    r'\s+'                # followed by whitespace
    r'(?=[A-Z"\'\(\[])'   # before uppercase or opening quote/bracket
)

_SENT_END_MULTI = re.compile(
    r'(?<=[.!?。！？])'
    r'(?:\s*["\'\)\]」』]*)'
    r'\s*'
    r'(?=[A-Z가-힣ㄱ-ㅎㅏ-ㅣ一-鿿"\'\(\[「『]|$)'
)

# Hyphenated line break pattern
_HYPHEN_BREAK = re.compile(r'(\w)-\s*\n\s*(\w)')

# Whitespace normalization
_MULTI_SPACE = re.compile(r'[ \t]+')
_LINE_BREAK = re.compile(r'\s*\n\s*')

# Page-number pattern for HF merge
_PAGE_NUMBER_RE = re.compile(
    r'^(?:\d+|-\s*\d+\s*-|page\s+\d+(?:\s+of\s+\d+)?|[ivxlcdm]+)$',
    re.IGNORECASE,
)

# Caption detection patterns
_CAPTION_PATTERNS = [
    re.compile(r'^(?:figure|fig\.?\s*)\s*\d+(?:[.\-]\d+)*', re.IGNORECASE),
    re.compile(r'^(?:table|tbl\.?\s*)\s*\d+(?:[.\-]\d+)*', re.IGNORECASE),
    re.compile(r'^\(\s*[a-z0-9]\s*\)', re.IGNORECASE),
    re.compile(r'^(?:source|notes?)\s*:', re.IGNORECASE),
]


def _detect_caption(text: str) -> tuple[bool, Optional[str]]:
    """Detect if text is a caption and determine target type.

    Returns (is_caption, target_type) where target_type is "figure", "table", or None.
    """
    stripped = text.strip()
    if not stripped:
        return False, None

    for pat in _CAPTION_PATTERNS:
        if pat.search(stripped):
            low = stripped.lower()
            if low.startswith(("figure", "fig")):
                return True, "figure"
            if low.startswith(("table", "tbl")):
                return True, "table"
            return True, None

    return False, None


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace."""
    t = text.strip().lower()
    t = _MULTI_SPACE.sub(' ', t)
    return t


def _join_textline_spans(textlines: list[dict]) -> str:
    """Extract plain text from textlines by joining all spans."""
    parts = []
    for tl in textlines:
        line_text = ""
        for span in tl.get("spans", []):
            line_text += span.get("text", "")
        parts.append(line_text.strip())
    return "\n".join(parts)


def _get_dominant_font(textlines: list[dict]) -> tuple[float, int]:
    """Get the most common (font_size, font_flags) from spans by character count."""
    font_counter = Counter()
    for tl in textlines:
        for span in tl.get("spans", []):
            text = span.get("text", "")
            char_count = len(text.strip())
            if char_count > 0:
                size = round(span.get("size", 0), 1)
                flags = span.get("flags", 0)
                font_counter[(size, flags)] += char_count

    if not font_counter:
        return 0.0, 0

    (size, flags), _ = font_counter.most_common(1)[0]
    return size, flags


def _compute_bbox_union(textlines: list[dict]) -> tuple:
    """Compute the union bounding box of all textlines."""
    x0 = y0 = float('inf')
    x1 = y1 = float('-inf')

    for tl in textlines:
        bbox = tl.get("bbox")
        if bbox is None:
            continue
        try:
            bx0, by0, bx1, by1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        except (TypeError, IndexError):
            continue
        x0 = min(x0, bx0)
        y0 = min(y0, by0)
        x1 = max(x1, bx1)
        y1 = max(y1, by1)

    if x0 == float('inf'):
        return (0, 0, 0, 0)
    return (x0, y0, x1, y1)


def _compute_line_gaps(textlines: list[dict]) -> list[Optional[float]]:
    """Compute vertical gaps between consecutive textlines.

    Returns a list of gaps, one per textline.
    gaps[0] is None (no previous line), gaps[i] is the gap before textline[i].
    """
    gaps = [None]
    for i in range(1, len(textlines)):
        prev_bbox = textlines[i - 1].get("bbox")
        curr_bbox = textlines[i].get("bbox")
        if prev_bbox is not None and curr_bbox is not None:
            try:
                gap = float(curr_bbox[1]) - float(prev_bbox[3])  # curr.y0 - prev.y1
                gaps.append(gap)
            except (TypeError, IndexError):
                gaps.append(None)
        else:
            gaps.append(None)
    return gaps


def _boxclass_to_hints(boxclass: str, toc=None, page_no=None, text=None):
    """Map LayoutBox.boxclass to structure hint flags."""
    hints = {
        "is_heading_hint": False,
        "heading_level_hint": None,
        "is_list_item": False,
        "is_table_content": False,
        "is_figure_related": False,
        "is_footnote": False,
        "is_header_footer": False,
        "is_caption": False,
        "caption_target_type": None,
    }

    if boxclass == "title":
        hints["is_heading_hint"] = True
        hints["heading_level_hint"] = 1
    elif boxclass == "section-header":
        hints["is_heading_hint"] = True
        level = _match_toc_level(toc, page_no, text) if toc and text else None
        hints["heading_level_hint"] = level or 2
    elif boxclass == "list-item":
        hints["is_list_item"] = True
    elif boxclass in ("table", "table-fallback"):
        hints["is_table_content"] = True
    elif boxclass in ("picture", "formula"):
        hints["is_figure_related"] = True
    elif boxclass == "footnote":
        hints["is_footnote"] = True
    elif boxclass in ("page-header", "page-footer"):
        hints["is_header_footer"] = True
    elif boxclass == "caption":
        hints["is_caption"] = True
        if text:
            _, target = _detect_caption(text)
            hints["caption_target_type"] = target

    return hints


def _match_toc_level(toc: list, page_no: int, text: str) -> Optional[int]:
    """Try to match text against TOC entries for the given page to determine heading level."""
    if not toc or not text:
        return None

    norm = _normalize_text(text)
    if not norm:
        return None

    for entry in toc:
        if len(entry) < 3:
            continue
        level, title, toc_page = entry[0], entry[1], entry[2]
        if toc_page != page_no:
            continue
        toc_norm = _normalize_text(str(title))
        if not toc_norm:
            continue
        if norm.startswith(toc_norm) or toc_norm.startswith(norm):
            return level

    return None


class SentenceBuilder:
    """Converts ParsedDocument's LayoutBoxes into SentenceUnits."""

    def __init__(self, splitter: str = "default"):
        self.splitter = splitter
        if splitter == "multilingual":
            self._split_re = _SENT_END_MULTI
        else:
            self._split_re = _SENT_END_EN

    def build_from_document(self, doc) -> list[SentenceUnit]:
        """Build SentenceUnits from all pages/boxes in a ParsedDocument."""
        units = []
        sent_id = 0
        prev_unit = None

        for page in doc.pages:
            for box_idx, box in enumerate(page.boxes):
                new_units = self._process_box(
                    page=page,
                    box_idx=box_idx,
                    box=box,
                    sent_id_start=sent_id,
                    toc=doc.toc,
                    prev_unit=prev_unit,
                )
                for u in new_units:
                    units.append(u)
                    sent_id += 1
                    prev_unit = u

        # Merge same-page header/footer units that share a y-band
        units = self._merge_same_page_hf_units(units)
        units = self._renumber_sent_ids(units)

        for i in range(len(units) - 1):
            if units[i + 1].line_gap_before is not None and units[i].page_no == units[i + 1].page_no:
                units[i].line_gap_after = units[i + 1].line_gap_before

        return units

    def _process_box(self, page, box_idx, box, sent_id_start, toc, prev_unit) -> list[SentenceUnit]:
        """Process a single LayoutBox into SentenceUnits."""
        boxclass = box.boxclass

        if boxclass in ("table", "table-fallback"):
            return self._table_as_unit(page, box_idx, box, sent_id_start, toc)

        if boxclass in ("picture", "formula") and not box.textlines:
            return self._figure_as_unit(page, box_idx, box, sent_id_start, toc)

        if box.textlines:
            return self._split_sentences(page, box_idx, box, sent_id_start, toc, prev_unit)

        return []

    def _table_as_unit(self, page, box_idx, box, sent_id_start, toc) -> list[SentenceUnit]:
        """Create a single SentenceUnit for a table box."""
        table_md = ""
        if box.table and isinstance(box.table, dict):
            table_md = box.table.get("markdown", "")
        text = table_md or _join_textline_spans(box.textlines or [])
        if not text.strip():
            return []

        hints = _boxclass_to_hints(box.boxclass, toc, page.page_number, text)
        return [SentenceUnit(
            sent_id=sent_id_start,
            text=text,
            norm_text=_normalize_text(text),
            page_no=page.page_number,
            box_index=box_idx,
            boxclass=box.boxclass,
            bbox=(box.x0, box.y0, box.x1, box.y1),
            table_markdown=table_md or None,
            **hints,
        )]

    def _figure_as_unit(self, page, box_idx, box, sent_id_start, toc) -> list[SentenceUnit]:
        """Create a single SentenceUnit for a figure/formula without text."""
        text = f"[Figure: {int(box.x1 - box.x0)}x{int(box.y1 - box.y0)}]"
        hints = _boxclass_to_hints(box.boxclass, toc, page.page_number, text)
        return [SentenceUnit(
            sent_id=sent_id_start,
            text=text,
            norm_text=_normalize_text(text),
            page_no=page.page_number,
            box_index=box_idx,
            boxclass=box.boxclass,
            bbox=(box.x0, box.y0, box.x1, box.y1),
            **hints,
        )]

    def _split_sentences(self, page, box_idx, box, sent_id_start, toc, prev_unit) -> list[SentenceUnit]:
        """Split textlines into sentence-level SentenceUnits."""
        textlines = box.textlines
        if not textlines:
            return []

        raw_text = _join_textline_spans(textlines)
        if not raw_text.strip():
            return []

        # Restore hyphenated line breaks, collapse line breaks into spaces
        joined = _HYPHEN_BREAK.sub(r'\1\2', raw_text)
        joined = _LINE_BREAK.sub(' ', joined)
        joined = _MULTI_SPACE.sub(' ', joined).strip()

        if not joined:
            return []

        font_size, font_flags = _get_dominant_font(textlines)
        line_gaps = _compute_line_gaps(textlines)
        first_gap = None
        if prev_unit and prev_unit.page_no == page.page_number:
            if textlines[0].get("bbox") is not None:
                first_gap = float(textlines[0]["bbox"][1]) - (prev_unit.bbox[3] if prev_unit else 0)

        hints = _boxclass_to_hints(box.boxclass, toc, page.page_number, joined)

        # Detect captions in non-caption boxclass text boxes
        if not hints["is_caption"] and box.boxclass not in (
            "title", "section-header", "table", "table-fallback",
            "picture", "formula", "footnote", "page-header", "page-footer",
        ):
            is_cap, cap_target = _detect_caption(joined)
            if is_cap:
                hints["is_caption"] = True
                hints["caption_target_type"] = cap_target

        if hints["is_heading_hint"] or hints["is_footnote"] or hints["is_header_footer"] or hints["is_caption"]:
            bbox = _compute_bbox_union(textlines)
            return [SentenceUnit(
                sent_id=sent_id_start,
                text=joined,
                norm_text=_normalize_text(joined),
                page_no=page.page_number,
                box_index=box_idx,
                boxclass=box.boxclass,
                bbox=bbox,
                font_size_dominant=font_size,
                font_flags_dominant=font_flags,
                line_gap_before=first_gap,
                **hints,
            )]

        sentences = self._split_re.split(joined)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return []

        if len(sentences) == 1 or hints["is_list_item"]:
            bbox = _compute_bbox_union(textlines)
            return [SentenceUnit(
                sent_id=sent_id_start,
                text=joined,
                norm_text=_normalize_text(joined),
                page_no=page.page_number,
                box_index=box_idx,
                boxclass=box.boxclass,
                bbox=bbox,
                font_size_dominant=font_size,
                font_flags_dominant=font_flags,
                line_gap_before=first_gap,
                **hints,
            )]

        box_bbox = _compute_bbox_union(textlines)
        units = []
        for i, sent_text in enumerate(sentences):
            units.append(SentenceUnit(
                sent_id=sent_id_start + i,
                text=sent_text,
                norm_text=_normalize_text(sent_text),
                page_no=page.page_number,
                box_index=box_idx,
                boxclass=box.boxclass,
                bbox=box_bbox,  # approximate: use whole box bbox
                font_size_dominant=font_size,
                font_flags_dominant=font_flags,
                line_gap_before=first_gap if i == 0 else None,
                **hints,
            ))

        return units

    def detect_repeated_headers_footers(self, doc) -> set[tuple[int, int]]:
        """Detect header/footer boxes that repeat across pages.

        Returns set of (page_no, box_index) tuples to exclude.
        """
        if not doc.pages or len(doc.pages) < 3:
            return set()

        header_texts = defaultdict(list)  # (y_bucket, text_norm) -> [(page_no, box_idx)]
        footer_texts = defaultdict(list)

        for page in doc.pages:
            for box_idx, box in enumerate(page.boxes):
                if box.boxclass == "page-header" and box.textlines:
                    text = _normalize_text(_join_textline_spans(box.textlines))
                    if text:
                        y_bucket = round(box.y0 / 10) * 10  # bucket by ~10pt
                        header_texts[(y_bucket, text)].append((page.page_number, box_idx))
                elif box.boxclass == "page-footer" and box.textlines:
                    text = _normalize_text(_join_textline_spans(box.textlines))
                    if text:
                        y_bucket = round(box.y0 / 10) * 10
                        footer_texts[(y_bucket, text)].append((page.page_number, box_idx))

        threshold = max(2, len(doc.pages) * 0.5)
        repeated = set()

        for entries in [header_texts, footer_texts]:
            for _key, locations in entries.items():
                if len(locations) >= threshold:
                    repeated.update(locations)

        return repeated

    # ── Header/Footer same-line merge ─────────────────────────────────

    def _merge_same_page_hf_units(self, units: list[SentenceUnit],
                                   y_tolerance: float = 20.0) -> list[SentenceUnit]:
        """Merge consecutive same-page, same-boxclass HF units sharing a y-band."""
        if not units:
            return units

        result = []
        i = 0
        while i < len(units):
            u = units[i]
            if not u.is_header_footer:
                result.append(u)
                i += 1
                continue

            # Collect consecutive HF units on the same page with the same boxclass
            group = [u]
            j = i + 1
            while j < len(units):
                nxt = units[j]
                if (nxt.is_header_footer
                        and nxt.page_no == u.page_no
                        and nxt.boxclass == u.boxclass):
                    group.append(nxt)
                    j += 1
                else:
                    break

            if len(group) == 1:
                result.append(u)
            else:
                # Group by y-band and merge each band
                bands = self._group_by_y_band(group, y_tolerance)
                for band in bands:
                    result.append(self._merge_hf_group(band))
            i = j

        return result

    @staticmethod
    def _group_by_y_band(units: list[SentenceUnit],
                         y_tolerance: float) -> list[list[SentenceUnit]]:
        """Group units by y-center proximity (greedy clustering)."""
        sorted_units = sorted(units, key=lambda u: (u.bbox[1] + u.bbox[3]) / 2)
        bands: list[list[SentenceUnit]] = []
        for u in sorted_units:
            yc = (u.bbox[1] + u.bbox[3]) / 2
            if bands:
                last_yc = (bands[-1][-1].bbox[1] + bands[-1][-1].bbox[3]) / 2
                if abs(yc - last_yc) <= y_tolerance:
                    bands[-1].append(u)
                    continue
            bands.append([u])
        return bands

    @staticmethod
    def _merge_hf_group(group: list[SentenceUnit]) -> SentenceUnit:
        """Merge a group of HF units into a single unit (left-to-right order)."""
        if len(group) == 1:
            return group[0]

        sorted_group = sorted(group, key=lambda u: u.bbox[0])  # sort by x0
        text = " | ".join(u.text for u in sorted_group)

        # Union bbox
        x0 = min(u.bbox[0] for u in sorted_group)
        y0 = min(u.bbox[1] for u in sorted_group)
        x1 = max(u.bbox[2] for u in sorted_group)
        y1 = max(u.bbox[3] for u in sorted_group)

        # Use font info from the longest-text unit
        longest = max(sorted_group, key=lambda u: len(u.text))

        # Collect all source box indices
        source_indices = []
        for u in sorted_group:
            source_indices.append(u.box_index)
            source_indices.extend(getattr(u, '_source_box_indices', []))

        merged = SentenceUnit(
            sent_id=sorted_group[0].sent_id,
            text=text,
            norm_text=_normalize_text(text),
            page_no=sorted_group[0].page_no,
            box_index=sorted_group[0].box_index,
            boxclass=sorted_group[0].boxclass,
            bbox=(x0, y0, x1, y1),
            font_size_dominant=longest.font_size_dominant,
            font_flags_dominant=longest.font_flags_dominant,
            line_gap_before=sorted_group[0].line_gap_before,
            is_header_footer=True,
        )
        merged._source_box_indices = source_indices
        return merged

    @staticmethod
    def _renumber_sent_ids(units: list[SentenceUnit]) -> list[SentenceUnit]:
        """Renumber sent_ids sequentially from 0."""
        for i, u in enumerate(units):
            u.sent_id = i
        return units
