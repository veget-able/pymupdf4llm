"""Step E: Serialize ProtoChunks into FinalChunks with metadata and neighbor info."""

import re
from bisect import bisect_right
from collections import defaultdict

from .models import ProtoChunk, FinalChunk, ChunkMetadata, ChunkNeighbors

# Pattern: "Title ..... 123" or "Title ... 123" (dot-leader + page number)
_DOT_LEADER_RE = re.compile(r'\.{3,}\s*(\d+)\s*$')

# Minimum ratio of dot-leader lines to total lines to consider a page as TOC
_TOC_LINE_RATIO = 0.3


class ChunkSerializer:
    """Converts ProtoChunks into FinalChunks with full metadata and neighbor linkage."""

    def __init__(self, doc, window_size: int = 2, include_contextual: bool = True):
        self.doc = doc
        self.window_size = window_size
        self.include_contextual = include_contextual

    def serialize(self, proto_chunks: list[ProtoChunk]) -> list[FinalChunk]:
        """Convert ProtoChunks to FinalChunks."""
        if not proto_chunks:
            return []

        self._build_section_hierarchy()
        self._build_toc_page_index()

        finals = [self._make_final_chunk(pc) for pc in proto_chunks]

        self._link_neighbors(finals)
        self._link_related_elements(finals)

        return finals

    def _make_final_chunk(self, pc: ProtoChunk) -> FinalChunk:
        """Create a FinalChunk from a ProtoChunk."""
        chunk_id = f"c{pc.chunk_id}"
        hierarchy = self._get_section_hierarchy(pc)

        toc_items = []
        if self._toc_page_index:
            for p in range(pc.page_start, pc.page_end + 1):
                toc_items.extend(self._toc_page_index[p])

        metadata = ChunkMetadata(
            page_start=pc.page_start,
            page_end=pc.page_end,
            box_indices=pc.box_indices,
            sent_ids=pc.sent_ids,
            section_hierarchy=hierarchy,
            chunk_type_hint=pc.chunk_type_hint or "paragraph",
            chunk_types=pc.chunk_types or [pc.chunk_type_hint or "paragraph"],
            is_table_related=(pc.chunk_type_hint == "table"),
            bboxes=pc.bboxes,
            tables=pc.tables,
            figures=pc.figures,
            lists=pc.lists,
            file_path=self.doc.filename,
            page_count=self.doc.page_count,
            toc_items=toc_items,
        )

        contextual_text = ""
        if self.include_contextual:
            contextual_text = self._build_contextual_text(pc, hierarchy)

        return FinalChunk(
            chunk_id=chunk_id,
            text=pc.text,
            contextual_text=contextual_text,
            metadata=metadata,
            neighbors=ChunkNeighbors(),
        )

    # ── Section hierarchy from TOC ──────────────────────────────────

    def _build_section_hierarchy(self):
        """Build section hierarchy lookup from TOC.

        TOC source priority:
        1. PDF built-in bookmarks (doc.toc)
        2. Detected TOC pages (tables with dot-leader patterns + internal links)
        """
        self._hierarchy_by_page = {}
        self._hierarchy_pages = []

        toc = self.doc.toc or []
        if not toc:
            toc = self._detect_toc_from_layout()

        if not toc:
            return

        toc_sorted = sorted(
            [(entry[0], str(entry[1]), entry[2]) for entry in toc if len(entry) >= 3],
            key=lambda x: x[2],
        )
        if not toc_sorted:
            return

        # Single forward pass: build hierarchy at each TOC transition page
        path = {}
        prev_page = None
        for level, title, page in toc_sorted:
            if page != prev_page and prev_page is not None:
                self._hierarchy_by_page[prev_page] = [path[k] for k in sorted(path.keys())]
            path[level] = title
            # Clear deeper levels when a shallower heading appears
            to_delete = [k for k in path if k > level]
            for k in to_delete:
                del path[k]
            prev_page = page
        if prev_page is not None:
            self._hierarchy_by_page[prev_page] = [path[k] for k in sorted(path.keys())]

        self._hierarchy_pages = sorted(self._hierarchy_by_page.keys())

    def _detect_toc_from_layout(self) -> list:
        """Detect TOC entries from layout when PDF has no built-in bookmarks.

        Scans for pages where table boxes contain dot-leader patterns
        (e.g. "Section Title ........... 42") and validates against
        internal links and actual heading text on target pages.

        Handles page-number offsets (e.g. roman-numeral front matter
        where logical page 1 != physical page 1).

        Returns list of [level, title, physical_page_number] entries.
        """
        if not self.doc.pages:
            return []

        heading_texts = self._collect_heading_texts()

        # Phase 1: Extract raw TOC entries (page numbers as printed in TOC)
        raw_entries = []
        for page in self.doc.pages:
            page_entries = self._extract_toc_entries_from_page(page, heading_texts)
            if page_entries:
                raw_entries.extend(page_entries)

        if not raw_entries:
            return []

        # Phase 2: Detect page-number offset by cross-validating
        # TOC titles against actual heading texts on physical pages
        offset = self._detect_page_offset(raw_entries, heading_texts)

        # Phase 3: Apply offset and validate
        toc_entries = []
        for level, title, raw_page in raw_entries:
            phys_page = raw_page + offset
            if phys_page < 1 or phys_page > self.doc.page_count:
                continue
            toc_entries.append([level, title, phys_page])

        return toc_entries

    def _detect_page_offset(self, raw_entries: list, heading_texts: dict) -> int:
        """Detect the offset between TOC page numbers and physical page numbers.

        Tries offsets from 0 to page_count, scores each by how many TOC
        titles match actual headings on the offset-adjusted page (only
        counting pages within the document range).
        Returns the best offset.
        """
        if not raw_entries or not heading_texts:
            return 0

        best_offset = 0
        best_score = 0

        max_offset = min(self.doc.page_count, 50)
        for offset in range(0, max_offset):
            score = 0
            for _level, title, raw_page in raw_entries:
                phys_page = raw_page + offset
                if phys_page < 1 or phys_page > self.doc.page_count:
                    continue
                page_headings = heading_texts.get(phys_page, set())
                if not page_headings:
                    continue
                title_norm = _normalize_for_match(title)
                if any(title_norm in h or h in title_norm for h in page_headings):
                    score += 1
            if score > best_score:
                best_score = score
                best_offset = offset

        return best_offset

    def _collect_heading_texts(self) -> dict[int, set[str]]:
        """Collect normalized heading texts per page for TOC validation."""
        result = defaultdict(set)
        for page in self.doc.pages:
            for box in page.boxes:
                if box.boxclass in ("section-header", "title"):
                    if box.textlines:
                        text = _join_spans(box.textlines).strip()
                        if text:
                            result[page.page_number].add(_normalize_for_match(text))
        return dict(result)

    def _extract_toc_entries_from_page(self, page, heading_texts) -> list:
        """Extract TOC entries from a single page.

        Uses two strategies:
        1. Internal links (LINK_GOTO) — strongest signal
        2. Dot-leader + page number text patterns in table boxes — fallback
        """
        # Strategy 1: Internal links with dot-leader text from table markdown
        link_entries = self._extract_from_links(page, heading_texts)
        if link_entries:
            return link_entries

        # Strategy 2: Dot-leader patterns in table boxes
        entries = []
        for box in page.boxes:
            if box.boxclass not in ("table", "table-fallback"):
                continue

            text = _get_box_text(box)
            if not text:
                continue

            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if not lines:
                continue

            dot_lines = [l for l in lines if _DOT_LEADER_RE.search(l)]
            if len(dot_lines) < max(2, len(lines) * _TOC_LINE_RATIO):
                continue

            for line in dot_lines:
                entry = self._parse_toc_line(line, heading_texts)
                if entry:
                    entries.append(entry)

        return entries

    def _extract_from_links(self, page, heading_texts) -> list:
        """Extract TOC entries from internal links on the page.

        Uses PageLayout.links which stores pymupdf page.get_links() results.
        Internal links have kind=1 (LINK_GOTO).
        Link text is matched against dot-leader lines from table markdown.
        """
        if not page.links:
            return []

        internal = [l for l in page.links if l.get('kind') == 1]
        if len(internal) < 3:
            return []

        # Collect all dot-leader lines from table boxes on this page
        toc_lines = []
        for box in page.boxes:
            if box.boxclass not in ("table", "table-fallback"):
                continue
            text = _get_box_text(box)
            if text:
                for line in text.split('\n'):
                    line = line.strip()
                    if line and _DOT_LEADER_RE.search(line):
                        toc_lines.append(line)

        entries = []
        for link in internal:
            target_page = link.get('page')
            if target_page is None:
                continue
            target_page_1based = target_page + 1

            # Find the best matching dot-leader line for this link
            title = self._match_link_to_toc_line(link, toc_lines)
            if not title or len(title) < 2:
                continue

            level = _infer_heading_level(title)
            entries.append([level, title, target_page_1based])

        # If links produced entries, also add non-linked dot-leader lines
        # (some TOC entries may not have links)
        if entries and toc_lines:
            linked_titles = {e[1].lower() for e in entries}
            for line in toc_lines:
                entry = self._parse_toc_line(line, heading_texts)
                if entry and entry[1].lower() not in linked_titles:
                    entries.append(entry)
            entries.sort(key=lambda e: e[2])  # sort by page

        return entries

    @staticmethod
    def _match_link_to_toc_line(link, toc_lines) -> str:
        """Match a link to a dot-leader TOC line by y-coordinate overlap."""
        link_rect = link.get('from')
        if link_rect is None:
            return ""

        try:
            ly0, ly1 = float(link_rect[1]), float(link_rect[3])
        except (TypeError, IndexError):
            return ""

        # Find lines that overlap vertically with the link rect
        # (since we don't have per-line bboxes from markdown, use the first
        # dot-leader line as best effort — links are in reading order)
        if toc_lines:
            # Pop the first line (links and dot-leader lines are both in order)
            title = _clean_toc_title(toc_lines.pop(0))
            return title

        return ""

    def _parse_toc_line(self, line: str, heading_texts: dict) -> list | None:
        """Parse a single dot-leader TOC line into [level, title, raw_page].

        Returns None if the line is unparseable.  Page-number validation
        and offset correction are done later in _detect_toc_from_layout.
        """
        m = _DOT_LEADER_RE.search(line)
        if not m:
            return None

        page_num = int(m.group(1))
        title = line[:m.start()].rstrip('. \t')
        # Clean pipe separators from table markdown (e.g. "1|Scope" → "1 Scope")
        title = title.replace('|', ' ').strip()
        title = re.sub(r'\s+', ' ', title)
        if not title or len(title) < 2:
            return None

        level = _infer_heading_level(title)
        return [level, title, page_num]

    # ── TOC page index ──────────────────────────────────────────────

    def _build_toc_page_index(self):
        """Pre-build page → TOC items index for O(1) lookup per chunk."""
        self._toc_page_index = defaultdict(list)
        toc = self.doc.toc or []
        for t in toc:
            if len(t) >= 3:
                self._toc_page_index[t[2]].append(t)

    def _get_section_hierarchy(self, pc: ProtoChunk) -> list[str]:
        """Get the section hierarchy for a chunk."""
        if not self._hierarchy_pages:
            return []

        idx = bisect_right(self._hierarchy_pages, pc.page_start) - 1
        if idx < 0:
            return []
        return list(self._hierarchy_by_page[self._hierarchy_pages[idx]])

    # ── Contextual text ─────────────────────────────────────────────

    def _build_contextual_text(self, pc: ProtoChunk, hierarchy: list[str]) -> str:
        """Build context-enriched text for embedding."""
        parts = []

        if hierarchy:
            parts.append(f"[Section] {' > '.join(hierarchy)}")

        if pc.page_start == pc.page_end:
            parts.append(f"[Page] {pc.page_start}")
        else:
            parts.append(f"[Pages] {pc.page_start}-{pc.page_end}")

        non_para = [t for t in (pc.chunk_types or []) if t != "paragraph"]
        if non_para:
            parts.append(f"[Type] {', '.join(non_para)}")

        parts.append(f"[Content]\n{pc.text}")

        return "\n".join(parts)

    # ── Neighbor linking ────────────────────────────────────────────

    def _link_neighbors(self, finals: list[FinalChunk]):
        """Set prev/next neighbor references using window_size."""
        page_to_chunks = defaultdict(list)
        for i, fc in enumerate(finals):
            for p in range(fc.metadata.page_start, fc.metadata.page_end + 1):
                page_to_chunks[p].append(i)

        for i, fc in enumerate(finals):
            start = max(0, i - self.window_size)
            fc.neighbors.prev_chunk_ids = [
                finals[j].chunk_id for j in range(start, i)
            ]

            end = min(len(finals), i + 1 + self.window_size)
            fc.neighbors.next_chunk_ids = [
                finals[j].chunk_id for j in range(i + 1, end)
            ]

            same_page = set()
            for p in range(fc.metadata.page_start, fc.metadata.page_end + 1):
                for j in page_to_chunks[p]:
                    if j != i:
                        same_page.add(j)
            fc.neighbors.same_page_chunk_ids = [
                finals[j].chunk_id for j in sorted(same_page)
            ]

    _RELATED_FIELD_MAP = {
        "table": "related_table_chunk_id",
        "figure": "related_figure_chunk_id",
    }

    def _link_related_elements(self, finals: list[FinalChunk]):
        """Link table/figure chunks to their neighboring text chunks."""
        for i, fc in enumerate(finals):
            field = self._RELATED_FIELD_MAP.get(fc.metadata.chunk_type_hint)
            if field is None:
                continue
            for j in _adjacent_indices(i, len(finals), radius=2):
                if finals[j].metadata.chunk_type_hint in ("paragraph", "heading"):
                    setattr(finals[j].neighbors, field, fc.chunk_id)
                    break


# ── Module-level helpers ────────────────────────────────────────────

def _adjacent_indices(center: int, total: int, radius: int = 2) -> list[int]:
    """Get indices adjacent to center, alternating before/after."""
    indices = []
    for d in range(1, radius + 1):
        if center - d >= 0:
            indices.append(center - d)
        if center + d < total:
            indices.append(center + d)
    return indices


def _get_box_text(box) -> str:
    """Get text from a box, trying textlines first then table markdown."""
    if box.textlines:
        return _join_spans(box.textlines)
    if box.table and isinstance(box.table, dict):
        md = box.table.get("markdown", "")
        if md:
            # Strip markdown table formatting to get plain text lines
            lines = []
            for line in md.split('\n'):
                line = line.strip()
                if line.startswith('|---') or line == '|':
                    continue
                # Remove leading/trailing pipes and markdown bold
                line = line.strip('|').replace('**', '').replace('<br>', '\n')
                line = line.strip()
                if line:
                    lines.append(line)
            return '\n'.join(lines)
    return ""


def _join_spans(textlines: list[dict]) -> str:
    """Extract plain text from textlines by joining all spans."""
    parts = []
    for tl in textlines:
        line_text = ""
        for span in tl.get("spans", []):
            line_text += span.get("text", "")
        parts.append(line_text.strip())
    return "\n".join(parts)


def _normalize_for_match(text: str) -> str:
    """Normalize text for fuzzy matching: lowercase, collapse whitespace, strip numbering."""
    t = text.strip().lower()
    t = re.sub(r'\s+', ' ', t)
    # Strip leading section numbers like "8.1.2 " or "A.3 "
    t = re.sub(r'^[\d.]+\s+', '', t)
    t = re.sub(r'^[a-z]\.\d+\s+', '', t)
    return t


def _clean_toc_title(text: str) -> str:
    """Clean a TOC entry title: remove dot-leaders, trailing page numbers, pipes."""
    text = _DOT_LEADER_RE.sub('', text)
    text = text.rstrip('. \t')
    text = text.replace('|', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _infer_heading_level(title: str) -> int:
    """Infer heading level from section numbering.

    "1 Introduction" → 1
    "2.3 Methods" → 2
    "A.1.2 Details" → 3
    "Foreword" (no number) → 1
    """
    m = re.match(r'^(\d+(?:\.\d+)*)\s', title)
    if m:
        return m.group(1).count('.') + 1

    # Annex/Appendix pattern: "A.1.2" or "Annex A"
    m = re.match(r'^(?:Annex\s+)?([A-Z])(?:\.(\d+(?:\.\d+)*))?\s', title, re.IGNORECASE)
    if m:
        sub = m.group(2)
        return (sub.count('.') + 2) if sub else 1

    # No numbering — assume top-level
    return 1
