"""Step B: Compute boundary scores between adjacent SentenceUnits."""

import statistics
from typing import Callable, Optional

from .models import SentenceUnit


class BoundaryScorer:
    """Scores the likelihood of a chunk boundary between adjacent sentence pairs.

    Higher score = more likely to break here.
    """

    def __init__(self, weights: dict, embedder: Optional[Callable] = None):
        self.weights = weights
        self.embedder = embedder
        self._embedding_cache: dict[int, list[float]] = {}

    def score_all(self, sents: list[SentenceUnit]) -> list[float]:
        """Compute break scores for all adjacent pairs.

        Returns list of len(sents)-1 scores.
        """
        if len(sents) < 2:
            return []

        gaps = [s.line_gap_before for s in sents if s.line_gap_before is not None and s.line_gap_before > 0]
        self._median_gap = statistics.median(gaps) if gaps else 12.0

        sizes = [s.font_size_dominant for s in sents if s.font_size_dominant > 0]
        self._median_font = statistics.median(sizes) if sizes else 10.0

        if self.embedder and self.weights.get("w_sem", 0) > 0:
            self._precompute_embeddings(sents)

        scores = []
        for i in range(len(sents) - 1):
            scores.append(self.score_pair(sents[i], sents[i + 1]))

        return scores

    def score_pair(self, left: SentenceUnit, right: SentenceUnit) -> float:
        """Compute break score for a single adjacent pair."""
        w = self.weights
        score = 0.0

        # Layout signals
        box_changed = (left.box_index != right.box_index) or (left.page_no != right.page_no)
        score += w.get("w_box", 0) * float(box_changed)

        score += w.get("w_class", 0) * float(left.boxclass != right.boxclass)
        score += w.get("w_page", 0) * float(left.page_no != right.page_no)
        score += w.get("w_gap", 0) * self._compute_gap_jump(right)
        score += w.get("w_font", 0) * self._compute_font_jump(left, right)

        # Structure hint signals
        score += w.get("w_head", 0) * float(right.is_heading_hint and not left.is_heading_hint)
        score += w.get("w_foot", 0) * float(not left.is_footnote and right.is_footnote)
        score += w.get("w_hgap", 0) * self._compute_hgap_jump(left, right)

        # Suppression signals (negative = keep together)
        score -= w.get("w_list", 0) * float(left.is_list_item and right.is_list_item and not box_changed)
        score -= w.get("w_table", 0) * float(left.is_table_content and right.is_table_content)

        # Semantic signal (optional)
        if self.embedder and w.get("w_sem", 0) > 0:
            sem_dist = self._compute_semantic_distance(left, right)
            score += w.get("w_sem", 0) * sem_dist

        return score

    def _compute_gap_jump(self, right: SentenceUnit) -> float:
        """Normalized vertical gap signal (0.0-1.0)."""
        gap = right.line_gap_before
        if gap is None or self._median_gap <= 0:
            return 0.0
        ratio = gap / self._median_gap
        if ratio <= 1.5:
            return 0.0
        return min(1.0, (ratio - 1.5) / 2.0)

    def _compute_hgap_jump(self, left: SentenceUnit, right: SentenceUnit) -> float:
        """Horizontal non-overlap signal for multi-column detection (0.0-1.0)."""
        if left.page_no != right.page_no:
            return 0.0

        lx0, _, lx1, _ = left.bbox
        rx0, _, rx1, _ = right.bbox

        lw = lx1 - lx0
        rw = rx1 - rx0
        min_width = min(lw, rw)
        if min_width <= 0:
            return 0.0

        overlap = max(0.0, min(lx1, rx1) - max(lx0, rx0))
        ratio = overlap / min_width

        if ratio >= 0.5:
            return 0.0
        # 0.5 → 0.0, 0.0 → 1.0
        return 1.0 - ratio * 2.0

    def _compute_font_jump(self, left: SentenceUnit, right: SentenceUnit) -> float:
        """Font size change signal (0.0-1.0)."""
        if left.font_size_dominant <= 0 or right.font_size_dominant <= 0:
            return 0.0

        diff = abs(left.font_size_dominant - right.font_size_dominant)
        if diff < 0.5:
            return 0.0

        if self._median_font > 0:
            ratio = diff / self._median_font
            return min(1.0, ratio)
        return min(1.0, diff / 10.0)

    def _precompute_embeddings(self, sents: list[SentenceUnit]):
        """Pre-compute and cache sentence embeddings."""
        self._embedding_cache = {}
        for s in sents:
            if s.sent_id not in self._embedding_cache and s.norm_text:
                self._embedding_cache[s.sent_id] = self.embedder(s.norm_text)

    def _compute_semantic_distance(self, left: SentenceUnit, right: SentenceUnit) -> float:
        """Cosine distance between sentence embeddings (0.0-1.0)."""
        emb_l = self._embedding_cache.get(left.sent_id)
        emb_r = self._embedding_cache.get(right.sent_id)

        if emb_l is None or emb_r is None:
            return 0.0

        return 1.0 - _cosine_similarity(emb_l, emb_r)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
