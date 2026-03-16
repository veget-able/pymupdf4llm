"""Step E: Serialize ProtoChunks into FinalChunks with metadata and neighbor info."""

from .models import ProtoChunk, FinalChunk, ChunkMetadata, ChunkNeighbors


class ChunkSerializer:
    """Converts ProtoChunks into FinalChunks with full metadata and neighbor linkage."""

    def __init__(self, doc, window_size: int = 2, include_contextual: bool = True):
        self.doc = doc
        self.window_size = window_size
        self.include_contextual = include_contextual
        self._heading_path_cache = None

    def serialize(self, proto_chunks: list[ProtoChunk]) -> list[FinalChunk]:
        """Convert ProtoChunks to FinalChunks."""
        if not proto_chunks:
            return []

        self._build_heading_paths(proto_chunks)

        finals = [self._make_final_chunk(pc) for pc in proto_chunks]

        self._link_neighbors(finals)
        self._link_related_elements(finals)

        return finals

    def _make_final_chunk(self, pc: ProtoChunk) -> FinalChunk:
        """Create a FinalChunk from a ProtoChunk."""
        chunk_id = f"c{pc.chunk_id}"
        heading_path = self._get_heading_path(pc)
        pc.heading_path = heading_path

        toc_items = []
        if self.doc.toc:
            pages_in_chunk = set(range(pc.page_start, pc.page_end + 1))
            toc_items = [t for t in self.doc.toc if t[-1] in pages_in_chunk]

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

    def _build_heading_paths(self, proto_chunks: list[ProtoChunk]):
        """Pre-build heading path data from TOC for efficient lookup."""
        if not self.doc.toc:
            self._heading_path_cache = {}
            return

        # TOC format: [level, title, page_number, ...]
        self._toc_sorted = sorted(
            [(entry[0], str(entry[1]), entry[2]) for entry in self.doc.toc if len(entry) >= 3],
            key=lambda x: x[2],  # sort by page
        )

    def _get_heading_path(self, pc: ProtoChunk) -> list[str]:
        """Get the heading hierarchy path for a chunk based on TOC."""
        if not self.doc.toc or not hasattr(self, '_toc_sorted'):
            return []

        relevant = [
            (level, title, page)
            for level, title, page in self._toc_sorted
            if page <= pc.page_start
        ]

        if not relevant:
            return []

        path = {}
        for level, title, page in relevant:
            path[level] = title
            # Clear deeper levels when a shallower heading appears
            for k in list(path.keys()):
                if k > level:
                    del path[k]

        return [path[k] for k in sorted(path.keys())]

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
        for i, fc in enumerate(finals):
            start = max(0, i - self.window_size)
            fc.neighbors.prev_chunk_ids = [
                finals[j].chunk_id for j in range(start, i)
            ]

            end = min(len(finals), i + 1 + self.window_size)
            fc.neighbors.next_chunk_ids = [
                finals[j].chunk_id for j in range(i + 1, end)
            ]

            fc.neighbors.same_page_chunk_ids = [
                finals[j].chunk_id
                for j in range(len(finals))
                if j != i and _pages_overlap(
                    finals[j].metadata.page_start, finals[j].metadata.page_end,
                    fc.metadata.page_start, fc.metadata.page_end,
                )
            ]

    def _link_related_elements(self, finals: list[FinalChunk]):
        """Link table/figure chunks to their neighboring text chunks."""
        for i, fc in enumerate(finals):
            ctype = fc.metadata.chunk_type_hint

            if ctype == "table":
                for j in _adjacent_indices(i, len(finals), radius=2):
                    if finals[j].metadata.chunk_type_hint in ("paragraph", "heading"):
                        finals[j].neighbors.related_table_chunk_id = fc.chunk_id
                        break

            elif ctype == "figure":
                for j in _adjacent_indices(i, len(finals), radius=2):
                    if finals[j].metadata.chunk_type_hint in ("paragraph", "heading"):
                        finals[j].neighbors.related_figure_chunk_id = fc.chunk_id
                        break


def _pages_overlap(start1, end1, start2, end2) -> bool:
    """Check if two page ranges overlap."""
    return start1 <= end2 and start2 <= end1


def _adjacent_indices(center: int, total: int, radius: int = 2) -> list[int]:
    """Get indices adjacent to center, alternating before/after."""
    indices = []
    for d in range(1, radius + 1):
        if center - d >= 0:
            indices.append(center - d)
        if center + d < total:
            indices.append(center + d)
    return indices
