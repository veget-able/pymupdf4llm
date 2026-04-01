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
    bboxes: list = field(default_factory=list)  # list of (x0, y0, x1, y1)

    # Structure
    chunk_type_hint: Optional[str] = None  # primary type: paragraph, table, list, figure, ...
    chunk_types: list = field(default_factory=list)  # all types present, e.g. ["heading", "table"]
    table_markdown: Optional[str] = None

    # Extracted element content (preserved when different types merge)
    tables: list = field(default_factory=list)   # list of {"markdown": str, "bbox": tuple}
    figures: list = field(default_factory=list)   # list of {"text": str, "bbox": tuple}
    list_items: list = field(default_factory=list) # list of {"text": str, "bbox": tuple}

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
    chunk_types: list = field(default_factory=list)  # all types present
    is_table_related: bool = False
    bboxes: list = field(default_factory=list)  # list of (x0, y0, x1, y1)

    # Extracted element content within this chunk
    tables: list = field(default_factory=list)
    figures: list = field(default_factory=list)
    list_items: list = field(default_factory=list)

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


def caption_matches_element(caption, element) -> bool:
    """Check if a caption SentenceUnit matches an element SentenceUnit (one direction).

    Returns True if caption targets the element type, or if target_type is None
    and element is table/figure/list.
    """
    if not caption.is_caption:
        return False
    if not (element.is_table_content or element.is_figure_related or element.is_list_item):
        return False
    if caption.caption_target_type is None:
        return True
    if caption.caption_target_type == "table" and element.is_table_content:
        return True
    if caption.caption_target_type == "figure" and element.is_figure_related:
        return True
    return False


def horizontal_overlap_ratio(bbox_a: tuple, bbox_b: tuple) -> float:
    """Compute horizontal overlap ratio between two bboxes.

    Returns overlap / min_width, or 1.0 if either bbox has zero width.
    """
    ax0, _, ax1, _ = bbox_a
    bx0, _, bx1, _ = bbox_b
    min_width = min(ax1 - ax0, bx1 - bx0)
    if min_width <= 0:
        return 1.0
    overlap = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    return overlap / min_width


def union_bbox(bboxes) -> tuple:
    """Compute the union bounding box from an iterable of (x0, y0, x1, y1) tuples."""
    x0 = y0 = float('inf')
    x1 = y1 = float('-inf')
    for bx0, by0, bx1, by1 in bboxes:
        x0 = min(x0, bx0)
        y0 = min(y0, by0)
        x1 = max(x1, bx1)
        y1 = max(y1, by1)
    if x0 == float('inf'):
        return (0, 0, 0, 0)
    return (x0, y0, x1, y1)


def _has_shared_edge(bbox_a: tuple, bbox_b: tuple, tol: float) -> bool:
    """Check if two bboxes share a matching edge *pair*.

    Returns True when (x0 AND x1) or (y0 AND y1) both match within *tol*.
    A single edge match (e.g. only x1) is not enough — it would cause
    chain-reaction grouping across spatially unrelated boxes.
    """
    ax0, ay0, ax1, ay1 = bbox_a
    bx0, by0, bx1, by1 = bbox_b
    x_pair = abs(ax0 - bx0) <= tol and abs(ax1 - bx1) <= tol
    y_pair = abs(ay0 - by0) <= tol and abs(ay1 - by1) <= tol
    return x_pair or y_pair


def group_bboxes(bboxes, tolerance: float = 10.0) -> list[tuple]:
    """Group sequential bboxes that share a matching edge pair.

    Only the *last* (most recent) group is checked for each incoming box.
    If it doesn't match, a new group is created.  This respects reading
    order: once a spatially different region appears (e.g. an indented
    code block), subsequent boxes continue from that break rather than
    jumping back to an earlier group.

    *tolerance* defaults to 10 PDF points (~3.5 mm at 72 dpi).
    """
    boxes = list(bboxes)
    if not boxes:
        return []
    if len(boxes) == 1:
        return list(boxes)

    groups: list[list[tuple]] = [[boxes[0]]]
    for box in boxes[1:]:
        last_union = union_bbox(iter(groups[-1]))
        if _has_shared_edge(last_union, box, tolerance):
            groups[-1].append(box)
        else:
            groups.append([box])

    return [union_bbox(iter(g)) for g in groups]
