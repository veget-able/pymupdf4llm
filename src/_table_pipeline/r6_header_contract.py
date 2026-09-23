"""Frozen R6 feature/decoder contract copied from scripts/analysis.

No training dependencies, GT, or per-page scoring rules.
"""
import collections
import re
import unicodedata
import numpy as np
from rapidfuzz.distance import Levenshtein
from parse_bench.evaluation.metrics.parse.table_extraction import ExtractedTable
from parse_bench.evaluation.metrics.parse.table_parsing import TableData
from pymupdf._table_headers import _table_output_rows
from parse_bench.evaluation.metrics.parse.table_title_stripping import strip_title_rows


FEATURES = [
    "cell_count",
    "mean_cell_length",
    "character_count",
    "digit_fraction",
    "alpha_fraction",
    "symbol_fraction",
    "numeric_cell_fraction",
    "mean_font_size",
    "bold_cell_fraction",
    "italic_cell_fraction",
    "row_number",
    "spanning_cell_fraction",
    "cell_count_difference",
    "mean_alignment",
    "mean_horizontal_overlap",
    "same_data_type_fraction",
    "same_font_style_fraction",
    "overall_content_repetition",
    "mean_content_repetition",
]

def norm(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())

def chars_on_page(page):
    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span["chars"]:
                    if char["c"].strip():
                        chars.append(
                            (char["bbox"], char["c"], span["size"], bool(span["flags"] & 16), bool(span["flags"] & 2))
                        )
    centers = np.array([[(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] for b, *_ in chars]).reshape(-1, 2)
    return chars, centers

def attach_pdf_features(cell, page_chars):
    chars, centers = page_chars
    x0, y0, x1, y1 = cell["bbox"]
    mask = (centers[:, 0] >= x0) & (centers[:, 0] <= x1) & (centers[:, 1] >= y0) & (centers[:, 1] <= y1)
    selected = [chars[i] for i in np.flatnonzero(mask)]
    if not selected:
        raise ValueError("nonempty_cell_without_pdf_characters")
    expected = collections.Counter(re.sub(r"\s", "", norm(cell["text"])))
    observed = collections.Counter(re.sub(r"\s", "", norm("".join(c[1] for c in selected))))
    overlap = sum((expected & observed).values())
    agreement = 2 * overlap / max(1, sum(expected.values()) + sum(observed.values()))
    # This is a source/annotation alignment check, not a classifier input or gate.
    cell = dict(cell)
    cell.update(
        font_size=float(np.mean([c[2] for c in selected])),
        bold=float(np.mean([c[3] for c in selected])) >= 0.5,
        italic=float(np.mean([c[4] for c in selected])) >= 0.5,
        tight=[
            min(c[0][0] for c in selected),
            min(c[0][1] for c in selected),
            max(c[0][2] for c in selected),
            max(c[0][3] for c in selected),
        ],
        source_text_agreement=agreement,
    )
    return cell

def data_type(text):
    compact = re.sub(r"\s", "", text)
    if compact and all(c in "0123456789.%" for c in compact):
        return "numeric"
    return "alphabetic" if re.search("[A-Za-z]", compact) else "symbol"

def repetition(a, b):
    return Levenshtein.normalized_similarity(re.sub("[0-9]", "#", a), re.sub("[0-9]", "#", b))

def row_features(rows):
    """Only observed cells; deliberately ignores all labels/identifiers/tags."""
    output = []
    for i, upper in enumerate(rows):
        lower = rows[i + 1] if i + 1 < len(rows) else []
        texts = [c["text"] for c in upper]
        joined = "".join(texts)
        n, length = len(upper), len(joined)
        digits = sum("0" <= c <= "9" for c in joined)
        alpha = sum("a" <= c <= "z" or "A" <= c <= "Z" for c in joined)
        single = [
            n,
            length / max(n, 1),
            length,
            digits / max(length, 1),
            alpha / max(length, 1),
            (length - digits - alpha) / max(length, 1),
            sum(data_type(t) == "numeric" for t in texts) / max(n, 1),
            sum(c["font_size"] for c in upper) / max(n, 1),
            sum(c["bold"] for c in upper) / max(n, 1),
            sum(c["italic"] for c in upper) / max(n, 1),
            i + 1,
        ]
        pairs, degree = [], collections.Counter()
        for j, a in enumerate(upper):
            for b in lower:
                ax0, _, ax1, _ = a["tight"]
                bx0, _, bx1, _ = b["tight"]
                overlap = min(ax1, bx1) - max(ax0, bx0)
                if overlap <= 0:
                    continue
                alignment = (
                    1
                    if abs(ax0 - bx0) <= 1
                    else 2
                    if abs(ax1 - bx1) <= 1
                    else 3
                    if abs((ax0 + ax1 - bx0 - bx1) / 2) <= 1
                    else 4
                )
                pairs.append(
                    [
                        alignment,
                        overlap / max(1e-9, min(ax1 - ax0, bx1 - bx0)),
                        data_type(a["text"]) == data_type(b["text"]),
                        (a["bold"], a["italic"]) == (b["bold"], b["italic"]),
                        repetition(a["text"], b["text"]),
                    ]
                )
                degree[j] += 1
        avg = np.mean(pairs, axis=0).tolist() if pairs else [0] * 5
        neighbor = (
            [
                sum(d >= 2 for d in degree.values()) / max(n, 1),
                abs(n - len(lower)) / max(n + len(lower), 1),
                *avg[:4],
                repetition(" ".join(texts), " ".join(c["text"] for c in lower)),
                avg[4],
            ]
            if lower
            else [0] * 8
        )
        values = single + neighbor
        assert len(values) == len(FEATURES) == 19 and np.isfinite(values).all()
        output.append(values)
    return output

def prefix_depth(predictions):
    """Contiguous top header region; no forced first row, no later islands."""
    return next((i for i, value in enumerate(predictions) if not value), len(predictions))

def leading_removed(raw, trimmed):
    """A unique exact leading slice, not inferred from caption words or GT."""
    if raw.ndim != 2 or trimmed.ndim != 2 or raw.shape[1] != trimmed.shape[1]:
        return None
    k = len(raw) - len(trimmed)
    if k <= 0 or not np.array_equal(raw[k:], trimmed):
        return None
    matches = [i for i in range(k + 1) if np.array_equal(raw[i : i + len(trimmed)], trimmed)]
    return k if matches == [k] else None

def title_rebased_features(features, k):
    result = np.array(features, dtype=float)[k:].copy()
    result[:, FEATURES.index("row_number")] -= k
    return result

def _placement_title_input(grid, section_header_rows=()):
    """Build title-analysis data from the writer's effective cells, without HTML.

    Unlike _placement_grid_matrices, title analysis needs text in every covered
    slot and the originating header-cell metadata, including span continuations.
    This is a narrow adapter for the generated table view, not an HTML parser.
    """
    filled, header_rows, header_cols, header_cells = {}, set(), set(), set()
    col_headers, row_headers, nonempty_rows = {}, {}, []
    for ri, cells in enumerate(_table_output_rows(grid, section_header_rows)):
        ci = 0
        nonempty_rows.append(any(any(line.strip() for line in lines) for _, lines, _, _ in cells))
        for tag, lines, colspan, rowspan in cells:
            # The writer omits attributes <= 1 and formats larger ones with %d.
            cs, rs = int(colspan) if colspan > 1 else 1, int(rowspan) if rowspan > 1 else 1
            while (ri, ci) in filled:
                ci += 1
            # Generated text is escaped, so it cannot introduce HTML elements.
            # Preserve the lxml HTML reader's null replacement, without parsing.
            text = " ".join(lines).replace("\x00", "\ufffd")
            is_header = tag == "th"
            if is_header:
                header_rows.add(ri)
                header_cols.add(ci)
            for r in range(ri, ri + rs):
                for c in range(ci, ci + cs):
                    filled[r, c] = text
                    if is_header:
                        header_cells.add((r, c))
            if is_header:
                for c in range(ci, ci + cs):
                    col_headers.setdefault(c, []).append((ri, text))
                for r in range(ri, ri + rs):
                    row_headers.setdefault(r, []).append((ci, text))
            ci += cs
    if filled:
        nr = max(r for r, _ in filled) + 1
        nc = max(c for _, c in filled) + 1
        data = np.full((nr, nc), "", dtype=object)
        for (r, c), text in filled.items():
            data[r, c] = text
    else:
        data = np.array([[]], dtype=object)
    return TableData(data=data, header_rows=header_rows, header_cols=header_cols,
                     col_headers=col_headers, row_headers=row_headers,
                     header_cells=header_cells), nonempty_rows


def input_offset(grid, features, heuristic_depth, limit=1, *, section_header_rows=()):
    """Prediction-only title offset from existing cells; no HTML round trip."""
    raw, nonempty_rows = _placement_title_input(grid, section_header_rows)
    # strip_title_rows consumes TableData and preserves raw_html opaquely. There
    # is no HTML consumer on this path, so no serialization is needed for it.
    trimmed = strip_title_rows(ExtractedTable("", raw), max_top_title_rows=limit).table_data
    k = leading_removed(raw.data, trimmed.data)
    assert len(nonempty_rows) == len(features)
    if k is None or not 0 < k < len(features) or k > heuristic_depth:
        return 0
    return k if all(nonempty_rows[:k]) else 0

def missing_body_cap(rows, depth, offset=0):
    """Exact entire-cell tokens only; no substring, numeric or broad NA rule.

    Cap only predicted prefix rows, after the frozen leading-title alignment.
    Empty rows and mixed field-label/missing-token rows do not trigger.
    """
    assert type(depth) is int and 0 <= depth <= len(rows)
    for i in range(offset, depth):
        ts = [norm(c["text"] if isinstance(c, dict) else c).casefold() for c in rows[i]]
        ts = [t for t in ts if t]
        if ts and all(t in {"none", "n/a"} for t in ts):
            return i
    return depth
