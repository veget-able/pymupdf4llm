"""Frozen title alignment for THF1 input, using only predicted cells.

These text equality and spanning-title operations preserve the model's original
input contract. They do not remove cells from output or read benchmark data.
"""
from dataclasses import dataclass
import re
import unicodedata
import numpy as np

@dataclass
class TitleGrid:
    data: np.ndarray
    header_rows: set
    header_cols: set
    col_headers: dict
    row_headers: dict
    header_cells: set


_SINGLE_QUOTE_CHARS = '‘’‚‛`´ʼʹ＇′‵ʻˊˋ'

_DOUBLE_QUOTE_CHARS = '“”„‟〝〞＂″‶ˮ'

_FULLWIDTH_PUNCT_CHARS = {'，': ',', '．': '.', '：': ':', '；': ';', '！': '!', '？': '?', '（': '(', '）': ')', '、': ',', '。': '.'}

_QUOTE_TRANSLATION_TABLE = str.maketrans({**dict.fromkeys(_SINGLE_QUOTE_CHARS, "'"), **dict.fromkeys(_DOUBLE_QUOTE_CHARS, '"'), **_FULLWIDTH_PUNCT_CHARS})

_CJK_BASE_RANGES = (('\u3040', 'ゟ'), ('゠', 'ヿ'), ('一', '鿿'), ('㐀', '䶿'), ('豈', '\ufaff'), ('가', '\ud7af'), ('ᄀ', 'ᇿ'), ('\u0b80', '\u0bff'), ('ಀ', '\u0cff'))

def _is_cjk_base_char(ch: str) -> bool:
    return any((lo <= ch <= hi for lo, hi in _CJK_BASE_RANGES))

_UNICODE_SYMBOL_CLASSES: list[tuple[str, str]] = [('●○◦∙⦁·', '•'), ('⮾ⓧ⨂', '⊗')]

_UNICODE_SYMBOL_TABLE = str.maketrans({char: canonical for chars, canonical in _UNICODE_SYMBOL_CLASSES for char in chars})

def _normalize_unicode_symbols(text: str) -> str:
    return text.translate(_UNICODE_SYMBOL_TABLE)

def _normalize_quotes(text: str) -> str:
    return text.translate(_QUOTE_TRANSLATION_TABLE)

_HTML_SPAN_RE = re.compile('</?span\\b[^>]*>', re.IGNORECASE)

_SUPERSCRIPT_TO_ASCII = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ', '0123456789+-=()ni')

_SUBSCRIPT_TO_ASCII = str.maketrans('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ', '0123456789+-=()aehijklmnoprstuvx')

def _normalize_sub_sup_for_table(text: str) -> str:
    text = re.sub('<sup[^>]*>(.*?)</sup>', '\\1', text, flags=re.IGNORECASE)
    text = re.sub('<sub[^>]*>(.*?)</sub>', '\\1', text, flags=re.IGNORECASE)
    text = text.translate(_SUPERSCRIPT_TO_ASCII)
    text = text.translate(_SUBSCRIPT_TO_ASCII)
    return text

def normalize_text(md_content: str | None) -> str:
    if md_content is None:
        return ''
    md_content = re.sub('<((?:https?://|mailto:)[^>\\s]+|[^>@\\s]+@[^>@\\s]+\\.[^>@\\s]+)>', '\\1', md_content, flags=re.IGNORECASE)
    md_content = re.sub('<br\\s*/?>', ' ', md_content)
    md_content = _normalize_quotes(md_content)
    md_content = re.sub('\\s+', ' ', md_content)
    md_content = re.sub('\\*\\*(.*?)\\*\\*', '\\1', md_content)
    md_content = re.sub('__(.*?)__', '\\1', md_content)
    md_content = re.sub('</?b>', '', md_content)
    md_content = re.sub('</?i>', '', md_content)
    md_content = re.sub('\\*(.*?)\\*', '\\1', md_content)
    md_content = re.sub('_(.*?)_', '\\1', md_content)
    md_content = md_content.replace('_', ' ')
    md_content = unicodedata.normalize('NFD', md_content)
    result_chars: list[str] = []
    for char in md_content:
        if unicodedata.category(char) != 'Mn':
            result_chars.append(char)
        elif result_chars and _is_cjk_base_char(result_chars[-1]):
            result_chars.append(char)
    md_content = ''.join(result_chars)
    md_content = unicodedata.normalize('NFC', md_content)
    replacements = {'＿': '_', '–': '-', '—': '-', '‑': '-', '‒': '-', '−': '-', '…': '...', '<ins>': '', '</ins>': '', '<u>': '', '</u>': '', '~~': '', '<mark>': '', '</mark>': '', '<br/>': ' ', '<br />': ' ', '\n': ' ', '$$': '', 'µ': 'μ'}
    for fancy_char, ascii_char in replacements.items():
        md_content = md_content.replace(fancy_char, ascii_char)
    md_content = _normalize_unicode_symbols(md_content)
    md_content = re.sub('</?(?:s|del|strike)>', '', md_content, flags=re.IGNORECASE)
    md_content = _HTML_SPAN_RE.sub('', md_content)
    md_content = re.sub('<sup[^>]*>.*?</sup>', '', md_content, flags=re.IGNORECASE)
    md_content = re.sub('<sub[^>]*>.*?</sub>', '', md_content, flags=re.IGNORECASE)
    md_content = re.sub('[\\u00b9\\u00b2\\u00b3\\u2070\\u2074-\\u2079]+', '', md_content)
    md_content = re.sub('[\\u2080-\\u2089]+', '', md_content)
    md_content = re.sub('-{2,}', '-', md_content)
    md_content = re.sub('\\.{2,}\\s*$', '', md_content)
    md_content = md_content.lower()
    return md_content

def _normalize_trm_cell_text(text: str) -> str:
    text = re.sub('(?:\\.\\s){2,}\\.?', '', text)
    text = re.sub('\\.{2,}', '', text)
    text = re.sub('  +', ' ', text).strip()
    text = re.sub('\\$\\s+', '$', text)
    text = re.sub('\\s+%', '%', text)
    text = re.sub('\\s+\\(', '(', text)
    text = re.sub('\\s+\\)', ')', text)
    text = re.sub('\\s+®', '®', text)
    text = re.sub('(\\d),(\\d)', '\\1\\2', text)
    return text

def normalize_table(table: TitleGrid) -> TitleGrid:
    if table.data.size == 0:
        return table
    n_rows, n_cols = table.data.shape
    normalized = np.empty_like(table.data)
    for r in range(n_rows):
        for c in range(n_cols):
            val = str(table.data[r, c])
            val = _normalize_sub_sup_for_table(val)
            val = normalize_text(val)
            val = _normalize_trm_cell_text(val)
            normalized[r, c] = val
    normalized_col_headers: dict[int, list[tuple[int, str]]] = {}
    for col_idx, entries in table.col_headers.items():
        normalized_col_headers[col_idx] = [(row_idx, _normalize_trm_cell_text(normalize_text(_normalize_sub_sup_for_table(text)))) for row_idx, text in entries]
    normalized_row_headers: dict[int, list[tuple[int, str]]] = {}
    for row_idx, entries in table.row_headers.items():
        normalized_row_headers[row_idx] = [(col_idx, _normalize_trm_cell_text(normalize_text(_normalize_sub_sup_for_table(text)))) for col_idx, text in entries]

    def _col_is_empty(c: int) -> bool:
        for r in range(n_rows):
            if str(normalized[r, c]) != '':
                return False
        for _row_idx, text in normalized_col_headers.get(c, []):
            if text != '':
                return False
        return True
    keep_cols = [c for c in range(n_cols) if not _col_is_empty(c)]
    if len(keep_cols) != n_cols:
        old_to_new = {old: new for new, old in enumerate(keep_cols)}
        normalized = normalized[:, keep_cols]
        normalized_col_headers = {old_to_new[c]: normalized_col_headers[c] for c in keep_cols if c in normalized_col_headers}
        header_cols = {old_to_new[c] for c in table.header_cols if c in old_to_new}
        header_cells = {(r, old_to_new[c]) for r, c in table.header_cells if c in old_to_new}
        normalized_row_headers = {row_idx: [(old_to_new[c], text) for c, text in entries if c in old_to_new] for row_idx, entries in normalized_row_headers.items()}
    else:
        header_cols = table.header_cols
        header_cells = table.header_cells
    return TitleGrid(data=normalized, header_rows=table.header_rows, header_cols=header_cols, col_headers=normalized_col_headers, row_headers=normalized_row_headers, header_cells=header_cells)

def detect_td_title_rows(table: TitleGrid, nominal_header_rows: set[int]) -> set[int]:
    n_rows, n_cols = table.data.shape
    if n_cols <= 1:
        return set()
    candidates: set[int] = set()
    for r in range(n_rows):
        if r in nominal_header_rows:
            break
        row_values = [str(table.data[r, c]).strip() for c in range(n_cols)]
        unique_nonempty = {v for v in row_values if v}
        if len(unique_nonempty) == 1 and all((v for v in row_values)):
            candidates.add(r)
        else:
            break
    if candidates and len(candidates) < n_rows:
        return candidates
    return set()

def find_col_header_rows(table: TitleGrid, nominal_header_rows: set[int], td_title_rows: set[int]) -> set[int]:
    n_rows, n_cols = table.data.shape
    first_possible_header = max(td_title_rows) + 1 if td_title_rows else 0
    leading_header_end = first_possible_header
    for r in range(first_possible_header, n_rows):
        if r not in nominal_header_rows:
            break
        has_non_th_content = any((str(table.data[r, c]).strip() and (r, c) not in table.header_cells for c in range(n_cols)))
        if has_non_th_content:
            break
        leading_header_end = r + 1
    col_header_rows = set(range(leading_header_end)) & nominal_header_rows
    if col_header_rows:
        bottom_row = max(col_header_rows)
        for c in range(n_cols):
            cell_val = str(table.data[bottom_row, c]).strip()
            if cell_val and (bottom_row, c) not in table.header_cells:
                col_header_rows.discard(bottom_row)
                break
    return col_header_rows

def detect_th_title_rows(table: TitleGrid, col_header_rows: set[int], *, max_top: int=1) -> set[int]:
    n_cols = table.data.shape[1]
    cols_with_headers: set[int] = set()
    for c in range(n_cols):
        for row_idx, text in table.col_headers.get(c, []):
            if row_idx in col_header_rows and text.strip():
                cols_with_headers.add(c)
                break
    title_rows: set[int] = set()
    for r in col_header_rows:
        col_texts: list[str] = []
        for c in range(n_cols):
            text = ''
            for row_idx, t in table.col_headers.get(c, []):
                if row_idx == r:
                    text = t.strip()
            col_texts.append(text)
        unique_nonempty = {t for t in col_texts if t}
        if len(unique_nonempty) != 1:
            continue
        covered = {c for c, t in enumerate(col_texts) if t}
        other_header_cols: set[int] = set()
        for other_r in col_header_rows:
            if other_r == r:
                continue
            for c in range(n_cols):
                for row_idx, t in table.col_headers.get(c, []):
                    if row_idx == other_r and t.strip():
                        other_header_cols.add(c)
        target_cols = other_header_cols if other_header_cols else cols_with_headers
        if not target_cols:
            continue
        uncovered = target_cols - covered
        if uncovered:
            edge_cols = {min(target_cols), max(target_cols)}
            if not uncovered <= edge_cols:
                continue
        rh = table.row_headers.get(r, [])
        n_nonempty_th = sum((1 for _, text in rh if text.strip()))
        if n_nonempty_th < len(covered):
            title_rows.add(r)
    if not title_rows:
        return set()
    to_strip: set[int] = set()

    def _is_rowspan_continuation(r: int) -> bool:
        for c in range(n_cols):
            for row_idx, _t in table.col_headers.get(c, []):
                if row_idx == r:
                    return False
        return True
    sorted_header = sorted(col_header_rows)
    bottom_of_block = sorted_header[-1]
    if max_top > 0:
        top_cap = min(len(col_header_rows) - 1, max_top)
        n_taken = 0
        i = 0
        while i < len(sorted_header) and n_taken < top_cap:
            r = sorted_header[i]
            if r not in title_rows:
                break
            tentative = {r}
            j = i + 1
            while j < len(sorted_header) and _is_rowspan_continuation(sorted_header[j]):
                tentative.add(sorted_header[j])
                j += 1
            to_strip |= tentative
            n_taken += 1
            i = j
    if bottom_of_block in title_rows and bottom_of_block not in to_strip:
        if len(col_header_rows - to_strip - {bottom_of_block}) >= 1:
            to_strip.add(bottom_of_block)
    return to_strip

def aligned_data(raw, limit=1):
    """Select the title-free input rows; never mutate the source placements.

    The caller rejects empty leading rows and non-prefix removals. A bottom
    header title is retained, matching the frozen model alignment contract.
    """
    if not raw.data.size:
        return raw.data
    normal = normalize_table(raw)
    td_titles = detect_td_title_rows(normal, normal.header_rows) if limit > 0 else set()
    headers = find_col_header_rows(normal, normal.header_rows, td_titles)
    titles = detect_th_title_rows(normal, headers, max_top=limit)
    bottom = {max(headers)} if headers and max(headers) in titles else set()
    removed = td_titles | (titles - bottom)
    return raw.data[[r for r in range(len(raw.data)) if r not in removed]]

