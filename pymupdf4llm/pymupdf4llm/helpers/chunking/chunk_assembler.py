"""Steps C+D: Assemble initial chunks and refine via split/merge."""

from .models import SentenceUnit, ProtoChunk, union_bbox, group_bboxes, horizontal_overlap_ratio, caption_matches_element
from .token_utils import TokenCounter

_ELEMENT_TYPES = frozenset({"table", "figure", "list"})


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

    # ── Step C: Initial assembly ─────────────────────────────────────

    def assemble(self, sents: list[SentenceUnit], scores: list[float]) -> list[ProtoChunk]:
        """Form initial chunks from sentences + boundary scores.

        A new chunk starts when:
        - break_score > threshold, OR
        - structural break (heading, type transition), OR
        - adding the next sentence would exceed max_tokens
        """
        if not sents:
            return []

        chunks = []
        current_sents = [sents[0]]
        current_text = sents[0].text

        for i, score in enumerate(scores):
            next_sent = sents[i + 1]

            # Break conditions (lazy: skip expensive checks if earlier one triggers)
            do_break = score > self.threshold
            if not do_break:
                do_break = self._is_structural_break(current_sents[-1], next_sent)
            if not do_break:
                combined_text = current_text + "\n" + next_sent.text
                do_break = self.counter.count(combined_text) > self.max_tokens

            if do_break:
                chunks.append(self._make_proto_chunk(len(chunks), current_sents))
                current_sents = [next_sent]
                current_text = next_sent.text
            else:
                current_sents.append(next_sent)
                current_text = combined_text

        # Flush remaining
        if current_sents:
            chunks.append(self._make_proto_chunk(len(chunks), current_sents))

        return chunks

    # ── Step D: Refine ───────────────────────────────────────────────

    def refine(self, chunks: list[ProtoChunk]) -> list[ProtoChunk]:
        """Refine chunks via split and multi-depth merge.

        1. Split  — break oversized chunks at sentence boundaries
        2. Semantic merge — heading+content, caption+element
        3. Budget merge  — greedily combine within max_tokens
        """
        # Step 1: Split oversized chunks
        split: list[ProtoChunk] = []
        for chunk in chunks:
            if chunk.token_count > self.max_tokens:
                split.extend(self._split_chunk(chunk))
            else:
                split.append(chunk)

        if not self.merge_small:
            return self._renumber(split)

        # Step 2: Semantic merge — preserve heading+content and caption+element pairs
        semantic = self._merge_semantic(split)

        # Step 3: Budget merge — greedily combine within max_tokens
        merged = self._merge_budget(semantic)
        return self._renumber(merged)

    # ── Structural break (used by assemble) ──────────────────────────

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
        return caption_matches_element(a, b) or caption_matches_element(b, a)

    # ── Split ────────────────────────────────────────────────────────

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

    # ── Semantic merge ───────────────────────────────────────────────

    def _merge_semantic(self, chunks: list[ProtoChunk]) -> list[ProtoChunk]:
        """Merge semantic pairs in a single forward pass.

        Pairs: heading + following content, caption + adjacent element.
        Semantic pairs always produce a single union bbox (not a list).
        """
        if len(chunks) <= 1:
            return chunks

        result: list[ProtoChunk] = []
        i = 0
        while i < len(chunks):
            chunk = chunks[i]

            if i + 1 < len(chunks) and self._is_semantic_pair(chunk, chunks[i + 1]):
                combined = chunk._sentences + chunks[i + 1]._sentences
                pc = self._make_proto_chunk(0, combined)
                # Semantic pairs are tightly related — always union into single bbox
                if len(pc.bboxes) > 1:
                    pc.bboxes = [union_bbox(iter(pc.bboxes))]
                result.append(pc)
                i += 2
            else:
                result.append(chunk)
                i += 1

        return result

    def _is_semantic_pair(self, a: ProtoChunk, b: ProtoChunk) -> bool:
        """Check if (a, b) form a semantic pair that should stay together."""
        if a.chunk_type_hint == "header_footer" or b.chunk_type_hint == "header_footer":
            return False
        if a.token_count + b.token_count > self.max_tokens:
            return False
        if abs(a.page_end - b.page_start) > 1:
            return False
        if not self._any_bbox_overlap(a.bboxes, b.bboxes):
            return False

        # heading + following content (any non-heading type)
        if a.chunk_type_hint == "heading" and b.chunk_type_hint != "heading":
            return True

        # caption + element (caption first)
        a_is_caption = bool(a._sentences) and all(s.is_caption for s in a._sentences)
        if a_is_caption and b.chunk_type_hint in _ELEMENT_TYPES:
            return self._caption_target_matches(a, b.chunk_type_hint)

        # element + caption (element first)
        b_is_caption = bool(b._sentences) and all(s.is_caption for s in b._sentences)
        if a.chunk_type_hint in _ELEMENT_TYPES and b_is_caption:
            return self._caption_target_matches(b, a.chunk_type_hint)

        return False

    @staticmethod
    def _caption_target_matches(caption_chunk: ProtoChunk, element_type: str) -> bool:
        """Check if caption's target type matches the element type."""
        target_types = {
            s.caption_target_type for s in caption_chunk._sentences
            if s.caption_target_type
        }
        if not target_types:
            return True  # no specific target → match any element
        return element_type in target_types

    # ── Budget merge ─────────────────────────────────────────────────

    def _merge_budget(self, chunks: list[ProtoChunk]) -> list[ProtoChunk]:
        """Greedily merge adjacent chunks that fit within max_tokens.

        Preserves bbox structure from earlier phases: instead of rebuilding
        bboxes from scratch, concatenates the bbox lists of both chunks.
        This keeps semantic-merge union bboxes intact.
        """
        if len(chunks) <= 1:
            return chunks

        merged = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = merged[-1]
            curr = chunks[i]

            if self._can_budget_merge(prev, curr):
                combined_sents = prev._sentences + curr._sentences
                pc = self._make_proto_chunk(0, combined_sents)
                # Re-group at chunk-level bboxes (not sentence-level) so that
                # semantic-merge unions are preserved as atomic inputs while
                # compatible bboxes (matching x0+x1 or y0+y1 pair) still merge.
                pc.bboxes = group_bboxes(iter(prev.bboxes + curr.bboxes))
                merged[-1] = pc
            else:
                merged.append(curr)

        return merged

    def _can_budget_merge(self, a: ProtoChunk, b: ProtoChunk) -> bool:
        """Check if two adjacent chunks can be merged within budget."""
        if a.chunk_type_hint == "header_footer" or b.chunk_type_hint == "header_footer":
            return False
        # Headings must start a chunk, never trail at the end of the previous one
        if b.chunk_type_hint == "heading":
            return False
        if a.token_count + b.token_count > self.max_tokens:
            return False
        if abs(a.page_end - b.page_start) > 1:
            return False
        if not self._any_bbox_overlap(a.bboxes, b.bboxes):
            return False
        return True

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _has_horizontal_overlap(bbox_a: tuple, bbox_b: tuple, min_ratio: float = 0.3) -> bool:
        """Check if two single bboxes have sufficient horizontal overlap."""
        return horizontal_overlap_ratio(bbox_a, bbox_b) >= min_ratio

    @staticmethod
    def _any_bbox_overlap(bboxes_a: list, bboxes_b: list, min_ratio: float = 0.3) -> bool:
        """Check if any bbox from list a overlaps horizontally with any from list b."""
        for ba in bboxes_a:
            for bb in bboxes_b:
                if horizontal_overlap_ratio(ba, bb) >= min_ratio:
                    return True
        return False

    def _make_proto_chunk(self, chunk_id: int, sents: list[SentenceUnit]) -> ProtoChunk:
        """Create a ProtoChunk from a list of SentenceUnits."""
        text = "\n".join(s.text for s in sents)
        token_count = self.counter.count(text)
        chunk_type = self._infer_chunk_type(sents)

        bboxes = group_bboxes(s.bbox for s in sents)

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
            bboxes=bboxes,
            chunk_type_hint=chunk_type,
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

    @staticmethod
    def _renumber(chunks: list[ProtoChunk]) -> list[ProtoChunk]:
        """Renumber chunk IDs sequentially."""
        for i, chunk in enumerate(chunks):
            chunk.chunk_id = i
        return chunks
