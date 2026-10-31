"""Research-only line surface protection. No AST or complete grammar checks.

Protecting a content type never certifies its transcription or skips page OCR.
"""
import re
import unicodedata as U

from ._damage_lines import inspect as code_inspect

LATEX = re.compile(r'\\(?:frac|dfrac|tfrac|sqrt|sum|prod|int|iint|lim|begin|end|left|right|'
                   r'sin|cos|tan|log|ln|exp|alpha|beta|gamma|theta|lambda|mu|pi|sigma|omega|'
                   r'text|mathrm|mathbf|mathcal|vec|overline|underline)\b')
REGEX = re.compile(r'\(\?(?:P?<|[:=!])|\\[dDsSwWbB](?:[+*?]|\{)|\[\^?[^\]\n]+\][+*?]')
MATH_WORD = re.compile(r'[^\W\d_]+',re.UNICODE)
OPERATORS = frozenset('+-*/=^<>×÷±∓≤≥≠≈∝∈∉∪∩')
MATH_EXTRA = frozenset('()[]{}|.,:;_′″∑∏∫√∞°²³⁰¹⁻⁺')|OPERATORS
PAIR = re.compile(r'[\w)\]}][ \t]*(?:\^|[+*/=<>×÷±≤≥≠≈-])[ \t]*(?:[\w(\[{]|[+-][ \t]*\w)',re.UNICODE)
POWER = re.compile(r'(?<![\w^])[^\W\d_]\w{0,2}\^[+-]?\d+',re.UNICODE)


def technical_hint(line):
    value=line.strip()
    if LATEX.search(value):return 'latex_command_surface'
    if REGEX.search(value):return 'regex_surface'
    if not value:return None
    # A weak equation/exponent clue is only used when no ordinary long words
    # or unexplained symbols are present. Variables may be Unicode letters.
    if any(len(word)>3 for word in MATH_WORD.findall(value)):return None
    if any(not(c.isalnum()or c.isspace()or U.category(c)[0]=='M'or c in MATH_EXTRA)for c in value):return None
    if ('='in value or POWER.search(value))and PAIR.search(value):
        return 'formula_surface'
    return None


def inspect(text):
    # This experiment protects technical text, not arbitrary JSON/markup/data
    # fragments. In particular, a damaged "[-." must remain inspectable.
    original=code_inspect(text,include_data_formats=False)
    rows=[]
    for line in original['lines']:
        row=dict(line)
        if row['language_check_applicable']:
            hint=technical_hint(row['text'])
            if hint:row.update(kind=hint,language_check_applicable=False)
        rows.append(row)
    body=''.join(text[r['start']:r['end']]for r in rows if r['language_check_applicable'])
    return dict(lines=rows,residual_text=body,
                unicode_replacement_offsets=original['unicode_replacement_offsets'],
                text_quality_assessed=False,page_OCR_skip=False,automatic_replacement=False,
                same_physical_line_code_prose_boundary_not_solved=True)
