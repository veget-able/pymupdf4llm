"""Steps C+D: Assemble initial chunks and refine via split/merge."""

from .models import SentenceUnit, ProtoChunk
from .token_utils import TokenCounter


class ChunkAssembler:
    """Assembles SentenceUnits into ProtoChunks based on boundary scores,
    then refines by splitting oversized and merging undersized chunks.
    """

    def __init__(
        self,
        max_tokens: int = 400,
        min_tokens: int = 120,
        threshold: float = 0.5,
        table_mode: str = "preserve",
        merge_small_chunks: bool = True,
        tokenizer=None,
    ):
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.threshold = threshold
        self.table_mode = table_mode
        self.merge_small = merge_small_chunks
        self.counter = TokenCounter(tokenizer)

    def assemble(self, sents: list[SentenceUnit], scores: list[float]) -> list[ProtoChunk]:
        """Form initial chunks from sentences + boundary scores.

        A new chunk starts when:
        - break_score > threshold, OR
        - adding the next sentence would exceed max_tokens, OR
        - the next sentence is a table/figure (structural isolation)
        """
        if not sents:
            return []

        chunks = []
        current_sents = [sents[0]]
        current_text = sents[0].text
        current_tokens = self.counter.count(current_text)

        for i, score in enumerate(scores):
            next_sent = sents[i + 1]

            # Force break conditions
            should_break = score > self.threshold
            combined_text = current_text + "\n" + next_sent.text
            would_exceed = self.counter.count(combined_text) > self.max_tokens
            structural_break = self._is_structural_break(current_sents[-1], next_sent)

            if should_break or would_exceed or structural_break:
                chunks.append(self._make_proto_chunk(len(chunks), current_sents))
                current_sents = [next_sent]
                current_text = next_sent.text
                current_tokens = self.counter.count(current_text)
            else:
                current_sents.append(next_sent)
                current_text = combined_text
                current_tokens = self.counter.count(current_text)

        # Flush remaining
        if current_sents:
            chunks.append(self._make_proto_chunk(len(chunks), current_sents))

        return chunks

    def refine(self, chunks: list[ProtoChunk]) -> list[ProtoChunk]:
        """Refine chunks by splitting oversized and merging undersized ones."""
        # Phase 0: Merge orphan caption chunks into their target element
        chunks = self._merge_captions(chunks)

        # Phase 1: Split oversized chunks
        split_chunks = []
        for chunk in chunks:
            if chunk.token_count > self.max_tokens:
                split_chunks.extend(self._split_chunk(chunk))
            else:
                split_chunks.append(chunk)

        if not self.merge_small:
            return self._renumber(split_chunks)

        # Phase 2: Merge undersized chunks
        merged = self._merge_chunks(split_chunks)
        return self._renumber(merged)

    def _is_structural_break(self, prev: SentenceUnit, next_sent: SentenceUnit) -> bool:
        """Check if there's a forced structural break between units."""
        # Caption-element pairs should NOT be structurally separated
        if self._is_caption_element_pair(prev, next_sent):
            return False
        # Heading followed by table/figure on same page → keep together
        if self._is_heading_element_pair(prev, next_sent):
            return False
        if next_sent.is_header_footer != prev.is_header_footer:
            return True
        if next_sent.is_table_content != prev.is_table_content:
            return True
        if next_sent.is_figure_related != prev.is_figure_related:
            return True
        if next_sent.is_heading_hint:
            return True
        return False

    @staticmethod
    def _is_heading_element_pair(prev: SentenceUnit, next_sent: SentenceUnit) -> bool:
        """Check if prev is a heading and next is its associated element."""
        if not prev.is_heading_hint:
            return False
        if prev.page_no != next_sent.page_no:
            return False
        if not (next_sent.is_table_content or next_sent.is_figure_related):
            return False
        return ChunkAssembler._has_horizontal_overlap(prev.bbox, next_sent.bbox)

    @staticmethod
    def _is_caption_element_pair(a: SentenceUnit, b: SentenceUnit) -> bool:
        """Check if a and b form a caption-element pair on the same page."""
        if a.page_no != b.page_no:
            return False
        if not ChunkAssembler._has_horizontal_overlap(a.bbox, b.bbox):
            return False

        if a.is_caption and (b.is_table_content or b.is_figure_related or b.is_list_item):
            if a.caption_target_type:
                if a.caption_target_type == "table" and b.is_table_content:
                    return True
                if a.caption_target_type == "figure" and b.is_figure_related:
                    return True
                return False
            return True

        if b.is_caption and (a.is_table_content or a.is_figure_related or a.is_list_item):
            if b.caption_target_type:
                if b.caption_target_type == "table" and a.is_table_content:
                    return True
                if b.caption_target_type == "figure" and a.is_figure_related:
                    return True
                return False
            return True

        return False

    @staticmethod
    def _has_horizontal_overlap(bbox_a: tuple, bbox_b: tuple, min_ratio: float = 0.3) -> bool:
        """Check if two bboxes have sufficient horizontal overlap."""
        ax0, _, ax1, _ = bbox_a
        bx0, _, bx1, _ = bbox_b
        aw = ax1 - ax0
        bw = bx1 - bx0
        min_width = min(aw, bw)
        if min_width <= 0:
            return True  # degenerate bbox, allow merge
        overlap = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        return (overlap / min_width) >= min_ratio

    def _make_proto_chunk(self, chunk_id: int, sents: list[SentenceUnit]) -> ProtoChunk:
        """Create a ProtoChunk from a list of SentenceUnits."""
        text = "\n".join(s.text for s in sents)
        token_count = self.counter.count(text)
        chunk_type = self._infer_chunk_type(sents)

        x0 = min(s.bbox[0] for s in sents)
        y0 = min(s.bbox[1] for s in sents)
        x1 = max(s.bbox[2] for s in sents)
        y1 = max(s.bbox[3] for s in sents)

        box_indices = list(dict.fromkeys(
            (s.page_no, s.box_index) for s in sents
        ))

        table_md = None
        if chunk_type == "table":
            for s in sents:
                if s.table_markdown:
                    table_md = s.table_markdown
                    break

        return ProtoChunk(
            chunk_id=chunk_id,
            sent_ids=[s.sent_id for s in sents],
            text=text,
            token_count=token_count,
            page_start=sents[0].page_no,
            page_end=sents[-1].page_no,
            box_indices=box_indices,
            bbox_union=(x0, y0, x1, y1),
            chunk_type_hint=chunk_type,
            heading_path=[],  # filled by serializer
            table_markdown=table_md,
            _sentences=list(sents),
        )

    def _infer_chunk_type(self, sents: list[SentenceUnit]) -> str:
        """Determine the dominant chunk type from sentence hints."""
        if any(s.is_header_footer for s in sents):
            return "header_footer"
        if any(s.is_table_content for s in sents):
            return "table"
        if any(s.is_figure_related for s in sents):
            return "figure"
        if all(s.is_list_item for s in sents):
            return "list"
        if any(s.is_caption for s in sents) and any(s.is_list_item for s in sents):
            return "list"
        if any(s.is_heading_hint for s in sents) and len(sents) == 1:
            return "heading"
        if any(s.is_footnote for s in sents):
            return "footnote"
        return "paragraph"

    def _split_chunk(self, chunk: ProtoChunk) -> list[ProtoChunk]:
        """Split an oversized chunk at sentence boundaries."""
        sents = chunk._sentences
        if not sents:
            return [chunk]

        if chunk.chunk_type_hint == "table" and self.table_mode == "preserve":
            return [chunk]

        result = []
        current = []
        current_text = ""

        for sent in sents:
            sent_tokens = self.counter.count(sent.text)

            if sent_tokens > self.max_tokens:
                if current:
                    result.append(self._make_proto_chunk(0, current))
                    current = []
                    current_text = ""
                result.append(self._make_proto_chunk(0, [sent]))
                continue

            combined = (current_text + "\n" + sent.text) if current_text else sent.text
            if self.counter.count(combined) > self.max_tokens and current:
                result.append(self._make_proto_chunk(0, current))
                current = [sent]
                current_text = sent.text
            else:
                current.append(sent)
                current_text = combined

        if current:
            result.append(self._make_proto_chunk(0, current))

        return result

    def _merge_chunks(self, chunks: list[ProtoChunk]) -> list[ProtoChunk]:
        """Merge adjacent undersized chunks if compatible."""
        if len(chunks) <= 1:
            return chunks

        merged = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = merged[-1]
            curr = chunks[i]

            can_merge = (
                prev.token_count < self.min_tokens
                and self._can_merge_pair(prev, curr)
            )

            if can_merge:
                combined_sents = prev._sentences + curr._sentences
                merged[-1] = self._make_proto_chunk(0, combined_sents)
            else:
                merged.append(curr)

        if len(merged) >= 2 and merged[-1].token_count < self.min_tokens:
            last = merged[-1]
            prev = merged[-2]
            if self._can_merge_pair(prev, last):
                combined = prev._sentences + last._sentences
                merged[-2] = self._make_proto_chunk(0, combined)
                merged.pop()

        return merged

    def _can_merge_pair(self, a: ProtoChunk, b: ProtoChunk) -> bool:
        """Check if two chunks can be merged."""
        if a.chunk_type_hint == "header_footer" or b.chunk_type_hint == "header_footer":
            return False

        # Only allow merging same types, or heading+following content, or caption+element
        if a.chunk_type_hint != b.chunk_type_hint:
            heading_merge = (
                a.chunk_type_hint == "heading"
                and b.chunk_type_hint in ("paragraph", "table", "figure", "list")
            )
            if not heading_merge:
                if not self._is_caption_element_merge(a, b):
                    return False

        if a.token_count + b.token_count > self.max_tokens:
            return False

        if abs(a.page_end - b.page_start) > 1:
            return False

        # Don't merge chunks in different columns
        ax0, _, ax1, _ = a.bbox_union
        bx0, _, bx1, _ = b.bbox_union
        min_width = min(ax1 - ax0, bx1 - bx0)
        if min_width > 0:
            overlap = max(0.0, min(ax1, bx1) - max(ax0, bx0))
            if overlap / min_width < 0.3:
                return False

        return True

    def _merge_captions(self, chunks: list[ProtoChunk]) -> list[ProtoChunk]:
        """Phase 0: Merge orphan caption/heading chunks into adjacent target elements."""
        if len(chunks) <= 1:
            return chunks

        _ELEMENT_TYPES = {"table", "figure", "list"}
        merged_indices: set[int] = set()
        result_map: dict[int, ProtoChunk] = {}  # index -> merged chunk

        for i, chunk in enumerate(chunks):
            if i in merged_indices:
                continue
            if not chunk._sentences:
                continue

            is_caption_chunk = all(s.is_caption for s in chunk._sentences)
            is_heading_chunk = chunk.chunk_type_hint == "heading"

            if not is_caption_chunk and not is_heading_chunk:
                continue

            # Determine target type from caption sentences
            target_types = set()
            if is_caption_chunk:
                for s in chunk._sentences:
                    if s.caption_target_type:
                        target_types.add(s.caption_target_type)

            # For headings, only look forward (heading → element)
            # For captions, look both directions
            search_dirs = (i + 1,) if is_heading_chunk else (i - 1, i + 1)

            best = None
            best_idx = None
            for adj_idx in search_dirs:
                if adj_idx < 0 or adj_idx >= len(chunks) or adj_idx in merged_indices:
                    continue
                adj = chunks[adj_idx]
                if adj.chunk_type_hint not in _ELEMENT_TYPES:
                    continue
                # Same page check
                if not (chunk.page_start == adj.page_start or chunk.page_end == adj.page_start
                        or chunk.page_start == adj.page_end):
                    continue
                # Horizontal overlap check
                if not self._has_horizontal_overlap(chunk.bbox_union, adj.bbox_union):
                    continue
                # Target type matching (captions only)
                if target_types:
                    if adj.chunk_type_hint not in target_types:
                        continue
                # Token limit check
                if chunk.token_count + adj.token_count > self.max_tokens * 1.2:
                    continue
                best = adj
                best_idx = adj_idx
                break  # prefer first valid match

            if best is not None and best_idx is not None:
                # Merge: caption/heading text goes before or after element
                if best_idx > i:
                    combined_sents = chunk._sentences + best._sentences
                else:
                    combined_sents = best._sentences + chunk._sentences
                merged_chunk = self._make_proto_chunk(0, combined_sents)
                merged_indices.add(i)
                merged_indices.add(best_idx)
                result_map[min(i, best_idx)] = merged_chunk

        # Build result preserving order
        result = []
        for i, chunk in enumerate(chunks):
            if i in merged_indices:
                if i in result_map:
                    result.append(result_map[i])
            else:
                result.append(chunk)

        return result

    @staticmethod
    def _is_caption_element_merge(a: ProtoChunk, b: ProtoChunk) -> bool:
        """Check if one chunk is all-captions and the other is a target element."""
        _ELEMENT_TYPES = {"table", "figure", "list"}
        a_all_caption = bool(a._sentences) and all(s.is_caption for s in a._sentences)
        b_all_caption = bool(b._sentences) and all(s.is_caption for s in b._sentences)

        if a_all_caption and b.chunk_type_hint in _ELEMENT_TYPES:
            return True
        if b_all_caption and a.chunk_type_hint in _ELEMENT_TYPES:
            return True
        return False

    @staticmethod
    def _renumber(chunks: list[ProtoChunk]) -> list[ProtoChunk]:
        """Renumber chunk IDs sequentially."""
        for i, chunk in enumerate(chunks):
            chunk.chunk_id = i
        return chunks
