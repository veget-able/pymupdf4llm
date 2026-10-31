"""Surface content-type clues for excerpts; never a grammar/quality verdict.

No AST, full-language parser, indentation validation or delimiter balancing.
The caller's text unit is preserved. Blank-separated units are reported
individually so one code excerpt cannot exempt a neighbouring body paragraph.
"""
import re
import unicodedata

# Horizontal whitespace only: unrelated PDF lines must not become x = ...
# or function(...) merely because a regular expression spans line breaks.
IDENT = r'(?:[$]|[^\W\d])[\w$]*'
MEMBER = IDENT + r'(?:\.' + IDENT + r'|\[[^\]\n]*\])*'
QUICK = re.compile(
    r'^[ \t]*(?:#|(?:async|def|class|interface|enum|function|if|elif|else|for|while|with|try|except|finally|switch|catch|const|let|var|export|default|public|private|protected|abstract|static|final|virtual|void|int|float|double|long|char|bool|boolean|String|auto|return|yield|raise|throw|import|from)\b|'
    + IDENT + r'[ \t]*(?:[=(.:\[]|[+*/%&|^-]=))',re.M)
HINT = re.compile(
    r'^[ \t]*(?:'
    r'(?P<directive>#[ \t]*(?:include|define|pragma)\b)'
    r'|(?P<definition>(?:(?:public|private|protected|abstract|export|default|async)[ \t]+)*(?:def|class|interface|enum|function)[ \t]+' + IDENT + r')'
    r'|(?P<flow>(?:if|elif|else|for|while|with|try|except|finally|switch|catch)\b[^\n]*(?::|==|!=|>=|<=|>|<|\bin\b|\band\b|\bor\b|\bnot\b|\())'
    r'|(?P<assignment>(?:export[ \t]+)?(?:(?:const|let|var)[ \t]+)?' + MEMBER + r'[ \t]*[+*/%&|^-]?=(?!=))'
    r'|(?P<call>(?:await[ \t]+)?' + IDENT + r'(?:\.' + IDENT + r')*[ \t]*\()'
    r'|(?P<import>(?:import[ \t]+[\w.*]+|from[ \t]+[\w.]+[ \t]+import\b))'
    r'|(?P<declaration>(?:(?:public|private|protected|static|final|virtual|const)[ \t]+)*(?:void|int|float|double|long|char|bool|boolean|String|auto)(?:[ \t]*[*&]+)?[ \t]+' + IDENT + r'[ \t]*[=(;])'
    r'|(?P<generic_declaration>(?:(?:public|private|protected|static|final|const)[ \t]+)*(?:' + IDENT + r'::)*' + IDENT + r'[ \t]*<[^>\n]*(?:>[ \t]+' + IDENT + r'|$))'
    r'|(?P<stream>(?:' + IDENT + r'::)+' + IDENT + r'[ \t]*(?:<<|>>))'
    r'|(?P<return>(?:return|yield|raise|throw)[ \t]+' + IDENT + r'))',
    re.M,
)
PROMPT = re.compile(r'^[ \t]*(?:In[ \t]*\[[\d ]*\]|Out[ \t]*\[\d+\]):[ \t]?', re.M)

# Mask literal contents/comments in C's regexp engine. Unterminated literals
# are allowed in an excerpt. Matching is evidence extraction, not validation.
QUOTES = (
    r'(?<!\w)R"(?P<rawtag>[^\s()\\]{0,16})\([\s\S]*?(?:\)(?P=rawtag)"|\Z)'
    r'|(?<!\w)(?:[rRuUbBfFL]{1,2})?"""(?:[\s\S]*?)(?:"""|\Z)'
    r"|(?<!\w)(?:[rRuUbBfFL]{1,2})?'''(?:[\s\S]*?)(?:'''|\Z)"
    r'|(?<!\w)(?:[rRuUbBfFL]{1,2})?"(?:\\[\s\S]|[^"\\])*(?:"|\Z)'
    r"|(?<!\w)(?:[rRuUbBfFL]{1,2})?'(?:\\[\s\S]|[^'\\])*(?:'|\Z)"
    r'|`(?:\\[\s\S]|[^`\\])*(?:`|\Z)'
)
PY_MASK = re.compile(QUOTES + r'|\#[^\n]*')
C_MASK = re.compile(QUOTES + r'|/\*[\s\S]*?(?:\*/|\Z)|//[^\n]*')
SUSPICIOUS = re.compile(r'[^\w\s.,;:()\[\]{}+*/%=!<>&|^~?#@\\$\-\'"`]', re.UNICODE)
BLOCK_GAP = re.compile(r'\r?\n[ \t]*\r?\n(?:[ \t]*\r?\n)*')
JSON_KEY = re.compile(r'[\'"][^\'"\n]+[\'"][ \t]*:')
TAG = re.compile(r'<[/!?]?[A-Za-z_][\w:.-]*(?:[ \t]|/?>|$)')
FIELD = re.compile(r'^(?:[\'"][^\'"\n]+[\'"]|[A-Za-z_]\w*)[ \t]*:[ \t]*(?:[\'"\[{\d-]|true\b|false\b|null\b)')
SQL = re.compile(r'^(?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|WITH|WHERE)\b[^\n]*(?:\bFROM\b|\bINTO\b|\bSET\b|\bAS\b|\bAND\b|=)',re.I)
URL = re.compile(r'(?:https?|ftp)://[^\s/]+(?:[/#?][^\s]*)?\Z')
EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+\Z')
TIMESTAMP = re.compile(r'\d{4}-\d\d-\d\d[T ]\d\d:\d\d(?:[^\s]*)?\Z')
PATH = re.compile(r'(?:/[\w.~@%+ -]+(?:/[\w.~@%+ -]*)+|[A-Za-z]:\\[^\n]+\\[^\n]*)\Z')


def format_hint(value):
    """Content format clue only; invalid/unfinished content can share a form."""
    if value[:1] in '{[':
        if JSON_KEY.search(value) or re.match(r'^\[[ \t]*(?:[\'"\d-])', value):
            return 'structured_data_like'
    if value.startswith('<') and TAG.match(value):
        return 'markup_like'
    if FIELD.match(value):
        return 'structured_field_excerpt'
    if SQL.match(value):
        return 'query_like_excerpt'
    if '://' in value[:12] and URL.fullmatch(value):
        return 'url_like'
    if '@' in value and EMAIL.fullmatch(value):
        return 'email_like'
    if value[:1].isdigit() and TIMESTAMP.fullmatch(value):
        return 'timestamp_like'
    if (value.startswith('/') or re.match(r'^[A-Za-z]:\\',value)) and PATH.fullmatch(value):
        return 'path_like'
    return None


def _block(text, include_data_formats):
    value=text.strip()
    if not value:
        return dict(kind='empty', language_check_applicable=False)
    if include_data_formats:
        kind=format_hint(value)
        if kind:
            return dict(kind=kind,language_check_applicable=False)
    if QUICK.search(text) is None:
        return dict(kind='not_identified_as_code',language_check_applicable=True)
    # Indentation already has a [space/tab]* prefix in HINT: no dedent pass.
    cleaned=PROMPT.sub('',text) if 'In' in text or 'Out' in text else text
    lines=[s.lstrip()for s in cleaned.splitlines()if s.strip()]
    if lines and all(s.startswith(('#','//'))for s in lines):
        has_prompt=cleaned!=text
        return dict(kind='code_comment_excerpt'if has_prompt else'comment_like',
                    language_check_applicable=not has_prompt)
    match=HINT.search(cleaned)
    if match is None:
        return dict(kind='not_identified_as_code',language_check_applicable=True)
    c_like=(match.lastgroup in ('directive','declaration','generic_declaration','stream')
            or re.match(r'(?:const|let|var|function)\b',match.group().lstrip()) is not None
            or (';' in cleaned and '{' in cleaned))
    mask=C_MASK if c_like else PY_MASK
    visible=mask.sub(' ',cleaned)
    # A directive's leading# is not a Python comment; C_MASK leaves it intact.
    hint=HINT.search(visible)
    if hint is None:
        return dict(kind='not_identified_as_code',language_check_applicable=True)
    if hint.lastgroup=='return'and re.match(r'^(?:return|yield|raise|throw)[ \t]+\w+[ \t]+\w+',visible.strip()):
        return dict(kind='not_identified_as_code',language_check_applicable=True)
    bad=SUSPICIOUS.search(visible)
    unexpected=(sorted({m.group()for m in SUSPICIOUS.finditer(visible)
                        if unicodedata.category(m.group())[0]!='M'})if bad else [])
    if unexpected:
        return dict(kind='code_cue_with_unexplained_characters',language_check_applicable=True,
                    unexplained=unexpected)
    return dict(kind='code_like_excerpt',language_check_applicable=False,
                evidence=[hint.lastgroup])


def inspect(text, include_data_formats=True):
    """Inspect a unit and return each blank-separated sub-unit with offsets.

    Mixed code/body text stays eligible for further inspection. Consumers
    may use units individually; protected spans must not certify a page.
    """
    units=[];start=0
    for gap in BLOCK_GAP.finditer(text):
        if text[start:gap.start()].strip():
            units.append(dict(start=start,end=gap.start(),**_block(text[start:gap.start()],include_data_formats)))
        start=gap.end()
    if text[start:].strip():
        units.append(dict(start=start,end=len(text),**_block(text[start:],include_data_formats)))
    if not units:
        return dict(kind='empty',language_check_applicable=False,units=[],
                    text_quality_assessed=False,page_OCR_skip=False)
    for i,unit in enumerate(units):
        if unit['kind']=='comment_like'and any(
            units[j]['kind']=='code_like_excerpt'for j in (i-1,i+1)if 0<=j<len(units)):
            unit.update(kind='comment_in_code_context',language_check_applicable=False)
    unprotected=[u for u in units if u['language_check_applicable']]
    kind=(units[0]['kind'] if len(units)==1 else
          'mixed_units' if unprotected and len(unprotected)!=len(units) else
          'code_or_data_units' if not unprotected else 'not_identified_as_code')
    return dict(kind=kind,language_check_applicable=bool(unprotected),units=units,
                text_quality_assessed=False,page_OCR_skip=False)
