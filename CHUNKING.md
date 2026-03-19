# Layout-Aware Chunking API

`pymupdf4llm.to_chunk()` splits a PDF into retrieval-friendly chunks using PDF-native layout signals (box boundaries, font changes, vertical gaps, page breaks).

## Quick Start

```python
import pymupdf4llm

chunks = pymupdf4llm.to_chunk("input.pdf")

for c in chunks:
    print(c.chunk_id, c.metadata.chunk_type_hint, c.text[:80])
```

## Two Ways to Call

```python
# 1. One-step: file path or pymupdf.Document
chunks = pymupdf4llm.to_chunk("input.pdf", max_tokens=400)

# 2. Two-step: parse first, then chunk
from pymupdf4llm.helpers.document_layout import parse_document

doc = parse_document("input.pdf")
chunks = doc.to_chunks(max_tokens=400)
```

The one-step form accepts both parse and chunk parameters. They are split internally.

## Parameters

### Parse Parameters

Passed to `parse_document()` internally.

| Parameter | Default | Description |
|---|---|---|
| `pages` | `None` | Pages to process (`None`=all, or list of 0-based page numbers) |
| `dpi` / `image_dpi` | `150` | Image extraction DPI |
| `ocr_dpi` | `300` | OCR DPI |
| `use_ocr` | `True` | Enable OCR when beneficial |
| `force_ocr` | `False` | Force OCR on all pages |
| `ocr_language` | `"eng"` | OCR language |
| `show_progress` | `False` | Show progress bar |

### Chunk Parameters

| Parameter | Default | Description |
|---|---|---|
| `max_tokens` | `400` | Maximum tokens per chunk |
| `min_tokens` | `120` | Minimum tokens (merge threshold) |
| `breakpoint_threshold` | `0.5` | Boundary score threshold for splitting |
| `window_size` | `2` | Number of neighbor chunks linked in each direction |
| `merge_small_chunks` | `True` | Merge undersized chunks with neighbors |
| `include_contextual_text` | `True` | Generate `contextual_text` field |
| `table_mode` | `"preserve"` | `"preserve"`: keep tables as single chunks |
| `header_footer_mode` | `"auto"` | `"auto"`: detect and remove repeated headers/footers, `"include"`: keep all, `"exclude"`: remove all |
| `sentence_splitter` | `"default"` | `"default"` (English) or `"multilingual"` (CJK support) |
| `output_format` | `"dataclass"` | `"dataclass"` or `"dict"` |

## Output Structure

### FinalChunk (dataclass)

```python
FinalChunk:
    chunk_id: str              # "c0", "c1", ...
    text: str                  # original text
    contextual_text: str       # text with [Section], [Page], [Type] tags
    metadata: ChunkMetadata
    neighbors: ChunkNeighbors
```

### ChunkMetadata

```python
ChunkMetadata:
    page_start: int            # 1-based page number
    page_end: int
    heading_path: list[str]    # e.g. ["Chapter 1", "Section 1.2"]
    chunk_type_hint: str       # "paragraph", "table", "list", "figure", "heading", "footnote"
    bbox_union: tuple          # (x0, y0, x1, y1) in PDF points
    file_path: str
    page_count: int
```

### ChunkNeighbors

```python
ChunkNeighbors:
    prev_chunk_ids: list[str]
    next_chunk_ids: list[str]
    same_page_chunk_ids: list[str]
    related_table_chunk_id: str | None
    related_figure_chunk_id: str | None
```

### contextual_text Format

```
[Section] Chapter 1 > Section 1.2
[Page] 5
[Type] table
[Content]
{chunk.text}
```

- `[Section]` appears only when `heading_path` is non-empty.
- `[Type]` appears only when the type is not `"paragraph"`.

## Examples

### Dict Output

```python
chunks = pymupdf4llm.to_chunk("input.pdf", output_format="dict")
# Returns list[dict] with keys: chunk_id, text, contextual_text, metadata, neighbors
```

### Custom Token Budget

```python
chunks = pymupdf4llm.to_chunk("paper.pdf", max_tokens=800, min_tokens=200)
```

### Multilingual Documents

```python
chunks = pymupdf4llm.to_chunk("korean.pdf", sentence_splitter="multilingual")
```

### Exclude All Headers/Footers

```python
chunks = pymupdf4llm.to_chunk("report.pdf", header_footer_mode="exclude")
```

### RAG with Neighbor Context

```python
chunks = pymupdf4llm.to_chunk("doc.pdf", window_size=3)

for c in chunks:
    # Use contextual_text for embedding (includes heading path + page info)
    embed(c.contextual_text)

    # At retrieval time, expand context using neighbors
    neighbor_ids = c.neighbors.prev_chunk_ids + c.neighbors.next_chunk_ids
```

## Testing & Visualization

테스트 스위트와 시각화 도구에 대한 자세한 설명은 아래 문서를 참고하세요.

- **테스트 가이드**: [`test/TESTING.md`](test/TESTING.md) — 테스트 구조 (T1–T9), 실행 방법, 시각화 도구 사용법
- **시각화 도구**: `chunk_visualizer.py` — DocLayNet 라벨 + 청킹 결과 오버레이 GUI
