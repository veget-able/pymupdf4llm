"""Data models for the chunking pipeline."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SentenceUnit:
    """A sentence-level unit extracted from a LayoutBox.

    For table/figure boxes, this represents the entire box content as one unit.
    """
    sent_id: int
    text: str
    norm_text: str

    # Location
    page_no: int
    box_index: int
    boxclass: str
    bbox: tuple  # (x0, y0, x1, y1)

    # Font metrics (from dominant span)
    font_size_dominant: float = 0.0
    font_flags_dominant: int = 0

    # Vertical spacing
    line_gap_before: Optional[float] = None
    line_gap_after: Optional[float] = None

    # Structure hints (derived from LayoutBox.boxclass)
    is_heading_hint: bool = False
    heading_level_hint: Optional[int] = None
    is_list_item: bool = False
    is_table_content: bool = False
    is_figure_related: bool = False
    is_footnote: bool = False
    is_header_footer: bool = False
    is_caption: bool = False
    caption_target_type: Optional[str] = None  # "table", "figure", None

    # Original table markdown (when is_table_content=True)
    table_markdown: Optional[str] = None

    # Tracks original box indices when multiple HF units are merged
    _source_box_indices: list = field(default_factory=list, repr=False)


@dataclass
class ProtoChunk:
    """An intermediate chunk before split/merge refinement."""
    chunk_id: int
    sent_ids: list = field(default_factory=list)
    text: str = ""
    token_count: int = 0

    # Location
    page_start: int = 0
    page_end: int = 0
    box_indices: list = field(default_factory=list)  # [(page_no, box_index), ...]
    bbox_union: tuple = (0, 0, 0, 0)

    # Structure
    chunk_type_hint: Optional[str] = None  # paragraph, table, list, figure, footnote, heading
    heading_path: list = field(default_factory=list)
    table_markdown: Optional[str] = None

    # References to SentenceUnits (kept for split/merge)
    _sentences: list = field(default_factory=list, repr=False)


@dataclass
class ChunkMetadata:
    """Metadata attached to a final chunk."""
    page_start: int = 0
    page_end: int = 0
    box_indices: list = field(default_factory=list)
    sent_ids: list = field(default_factory=list)
    heading_path: list = field(default_factory=list)
    chunk_type_hint: str = "paragraph"
    is_table_related: bool = False
    bbox_union: tuple = (0, 0, 0, 0)

    # Compatibility with existing page_chunks format
    file_path: Optional[str] = None
    page_count: Optional[int] = None
    toc_items: list = field(default_factory=list)


@dataclass
class ChunkNeighbors:
    """Neighbor linkage for retrieval expansion."""
    prev_chunk_ids: list = field(default_factory=list)
    next_chunk_ids: list = field(default_factory=list)
    same_page_chunk_ids: list = field(default_factory=list)
    related_table_chunk_id: Optional[str] = None
    related_figure_chunk_id: Optional[str] = None


@dataclass
class FinalChunk:
    """A finalized, retrieval-ready chunk."""
    chunk_id: str
    text: str
    contextual_text: str = ""
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)
    neighbors: ChunkNeighbors = field(default_factory=ChunkNeighbors)
