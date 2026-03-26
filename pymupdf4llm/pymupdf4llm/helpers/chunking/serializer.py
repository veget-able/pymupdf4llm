"""Step E: Serialize ProtoChunks into FinalChunks with metadata and neighbor info."""

from bisect import bisect_right
from collections import defaultdict

from .models import ProtoChunk, FinalChunk, ChunkMetadata, ChunkNeighbors


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

        self._build_heading_paths()
        self._build_toc_page_index()

        finals = [self._make_final_chunk(pc) for pc in proto_chunks]

        self._link_neighbors(finals)
        self._link_related_elements(finals)

        return finals

    def _make_final_chunk(self, pc: ProtoChunk) -> FinalChunk:
        """Create a FinalChunk from a ProtoChunk."""
        chunk_id = f"c{pc.chunk_id}"
        heading_path = self._get_heading_path(pc)

        toc_items = []
        if self._toc_page_index:
            for p in range(pc.page_start, pc.page_end + 1):
                toc_items.extend(self._toc_page_index[p])

        metadata = ChunkMetadata(
            page_start=pc.page_start,
            page_end=pc.page_end,
            box_indices=pc.box_indices,
            sent_ids=pc.sent_ids,
            heading_path=heading_path,
            chunk_type_hint=pc.chunk_type_hint or "paragraph",
            is_table_related=(pc.chunk_type_hint == "table"),
            bbox_union=pc.bbox_union,
            file_path=self.doc.filename,
            page_count=self.doc.page_count,
            toc_items=toc_items,
        )

        contextual_text = ""
        if self.include_contextual:
            contextual_text = self._build_contextual_text(pc, heading_path)

        return FinalChunk(
            chunk_id=chunk_id,
            text=pc.text,
            contextual_text=contextual_text,
            metadata=metadata,
            neighbors=ChunkNeighbors(),
        )

    def _build_heading_paths(self):
        """Pre-build heading path data from TOC for efficient lookup.

        Computes heading paths for all pages in a single O(T) pass,
        stored as page → heading_path for O(1) lookup per chunk.
        """
        self._heading_by_page = {}
        self._heading_pages = []
        if not self.doc.toc:
            return

        toc_sorted = sorted(
            [(entry[0], str(entry[1]), entry[2]) for entry in self.doc.toc if len(entry) >= 3],
            key=lambda x: x[2],  # sort by page
        )
        if not toc_sorted:
            return

        # Single forward pass: build heading path at each TOC transition page
        path = {}
        prev_page = None
        for level, title, page in toc_sorted:
            if page != prev_page and prev_page is not None:
                self._heading_by_page[prev_page] = [path[k] for k in sorted(path.keys())]
            path[level] = title
            # Clear deeper levels when a shallower heading appears
            to_delete = [k for k in path if k > level]
            for k in to_delete:
                del path[k]
            prev_page = page
        # Store final page
        if prev_page is not None:
            self._heading_by_page[prev_page] = [path[k] for k in sorted(path.keys())]

        # Build sorted list of pages with headings for bisect lookup
        self._heading_pages = sorted(self._heading_by_page.keys())

    def _build_toc_page_index(self):
        """Pre-build page → TOC items index for O(1) lookup per chunk."""
        self._toc_page_index = defaultdict(list)
        if self.doc.toc:
            for t in self.doc.toc:
                if len(t) >= 3:
                    self._toc_page_index[t[2]].append(t)

    def _get_heading_path(self, pc: ProtoChunk) -> list[str]:
        """Get the heading hierarchy path for a chunk based on TOC."""
        if not self._heading_pages:
            return []

        # Find the latest heading page <= pc.page_start
        idx = bisect_right(self._heading_pages, pc.page_start) - 1
        if idx < 0:
            return []
        return list(self._heading_by_page[self._heading_pages[idx]])

    def _build_contextual_text(self, pc: ProtoChunk, heading_path: list[str]) -> str:
        """Build context-enriched text for embedding."""
        parts = []

        if heading_path:
            parts.append(f"[Section] {' > '.join(heading_path)}")

        if pc.page_start == pc.page_end:
            parts.append(f"[Page] {pc.page_start}")
        else:
            parts.append(f"[Pages] {pc.page_start}-{pc.page_end}")

        if pc.chunk_type_hint and pc.chunk_type_hint != "paragraph":
            parts.append(f"[Type] {pc.chunk_type_hint}")

        parts.append(f"[Content]\n{pc.text}")

        return "\n".join(parts)

    def _link_neighbors(self, finals: list[FinalChunk]):
        """Set prev/next neighbor references using window_size."""
        # Build page → chunk index for O(n) same-page lookup
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

            # Collect same-page chunks via index
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


def _adjacent_indices(center: int, total: int, radius: int = 2) -> list[int]:
    """Get indices adjacent to center, alternating before/after."""
    indices = []
    for d in range(1, radius + 1):
        if center - d >= 0:
            indices.append(center - d)
        if center + d < total:
            indices.append(center + d)
    return indices
