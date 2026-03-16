"""Layout-Aware Chunking for PyMuPDF4LLM.

Phase 1: Layout-only chunker using PDF-native signals
(box boundaries, font changes, vertical gaps, page breaks).
"""

from .models import SentenceUnit, ProtoChunk, FinalChunk, ChunkMetadata, ChunkNeighbors
from .sentence_builder import SentenceBuilder
from .boundary_scorer import BoundaryScorer
from .chunk_assembler import ChunkAssembler
from .serializer import ChunkSerializer
from .token_utils import TokenCounter

# Default weights for layout-only mode
WEIGHTS_LAYOUT = {
    "w_sem": 0.0,
    "w_box": 0.35,
    "w_class": 0.50,
    "w_page": 0.15,
    "w_gap": 0.30,
    "w_hgap": 0.30,
    "w_font": 0.25,
    "w_head": 0.45,
    "w_foot": 0.20,
    "w_list": 0.40,
    "w_table": 0.60,
}

# Default weights for layout+semantic mode
WEIGHTS_LAYOUT_SEMANTIC = {
    **WEIGHTS_LAYOUT,
    "w_sem": 0.45,
    "w_box": 0.25,
    "w_class": 0.40,
}

DEFAULTS = {
    "strategy": "layout",
    "max_tokens": 400,
    "min_tokens": 120,
    "window_size": 2,
    "breakpoint_threshold": 0.5,
    "merge_small_chunks": True,
    "include_contextual_text": True,
    "table_mode": "preserve",
    "header_footer_mode": "auto",
    "sentence_splitter": "default",
    "output_format": "dataclass",
}


def to_chunk(parsed_doc, **kwargs):
    """Chunk a ParsedDocument into retrieval-friendly pieces."""
    strategy = kwargs.get("strategy", DEFAULTS["strategy"])

    if strategy == "layout_semantic":
        default_weights = WEIGHTS_LAYOUT_SEMANTIC
    else:
        default_weights = WEIGHTS_LAYOUT

    weights = kwargs.get("weights") or default_weights
    embedder = kwargs.get("sentence_embedder") if strategy == "layout_semantic" else None

    if strategy == "layout_semantic" and embedder is None:
        import warnings
        warnings.warn(
            "strategy='layout_semantic' requested but no sentence_embedder provided. "
            "Falling back to strategy='layout'.",
            stacklevel=2,
        )
        weights = WEIGHTS_LAYOUT
        embedder = None

    # Step A: Box → SentenceUnit
    builder = SentenceBuilder(
        splitter=kwargs.get("sentence_splitter", DEFAULTS["sentence_splitter"]),
    )
    sents = builder.build_from_document(parsed_doc)

    if not sents:
        return []

    # Auto header/footer removal
    hf_mode = kwargs.get("header_footer_mode", DEFAULTS["header_footer_mode"])
    if hf_mode == "auto":
        repeated = builder.detect_repeated_headers_footers(parsed_doc)
        sents = [s for s in sents if (s.page_no, s.box_index) not in repeated]
    elif hf_mode == "exclude":
        sents = [s for s in sents if not s.is_header_footer]

    if not sents:
        return []

    # Step B: Boundary scoring
    scorer = BoundaryScorer(weights=weights, embedder=embedder)
    scores = scorer.score_all(sents)

    # Step C+D: Chunk assembly + refinement
    assembler = ChunkAssembler(
        max_tokens=kwargs.get("max_tokens", DEFAULTS["max_tokens"]),
        min_tokens=kwargs.get("min_tokens", DEFAULTS["min_tokens"]),
        threshold=kwargs.get("breakpoint_threshold", DEFAULTS["breakpoint_threshold"]),
        table_mode=kwargs.get("table_mode", DEFAULTS["table_mode"]),
        merge_small_chunks=kwargs.get("merge_small_chunks", DEFAULTS["merge_small_chunks"]),
    )
    proto_chunks = assembler.assemble(sents, scores)
    proto_chunks = assembler.refine(proto_chunks)

    # Step E: Serialization
    serializer = ChunkSerializer(
        doc=parsed_doc,
        window_size=kwargs.get("window_size", DEFAULTS["window_size"]),
        include_contextual=kwargs.get(
            "include_contextual_text", DEFAULTS["include_contextual_text"]
        ),
    )
    final_chunks = serializer.serialize(proto_chunks)

    if kwargs.get("output_format", DEFAULTS["output_format"]) == "dict":
        from dataclasses import asdict
        return [asdict(c) for c in final_chunks]

    return final_chunks
