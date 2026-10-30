"""Line-level surface separation, independent replacement-character locations.

No complete syntax check; plain following body lines remain unprotected.
No output is authority for page OCR skipping or character replacement.
"""
import re
from ._damage_surface import _block, PROMPT, IDENT

MARKERS = re.compile(r'^[ \t]*[()\[\]{},;]+[ \t]*$')
ARGUMENT = re.compile(r'^[ \t]*(?:' + IDENT + r'(?:\.' + IDENT + r')*|[-+]?\d+(?:\.\d+)?)[ \t]*,[ \t]*$')
LITERAL = re.compile(r'^[ \t]*(?:[rRuUbBfF]{0,2})?[\'"`].*[,;][ \t]*$')
CASE = re.compile(r'^[ \t]*(?:case[ \t]+[^\n]+:|default[ \t]*:)[ \t]*$')
DECORATOR = re.compile(r'^[ \t]*@' + IDENT + r'(?:\.' + IDENT + r')*(?:[ \t]*\(|[ \t]*$)')
SHELL = re.compile(r'^[ \t]*(?:printf|echo|read|export|local)\b(?=[^\n]*(?:[\'"$]|=[^=]|[ \t]-\w))')
FFFD = re.compile('\ufffd')


def inspect(text, include_data_formats=True):
    # Observed marker positions only: intentionally printed U+FFFD and actual
    # mapping failures must still be distinguished by the upstream contract.
    replacements=[m.start()for m in FFFD.finditer(text)]
    lines=[];offset=0
    for raw in text.splitlines(keepends=True):
        end=offset+len(raw)
        if raw.strip():
            local=raw.rstrip('\r\n')
            cleaned=PROMPT.sub('',local)
            answer=_block(local,include_data_formats)
            if PROMPT.match(local):
                answer=dict(kind='notebook_prompt_or_output',language_check_applicable=False)
            elif DECORATOR.match(local)or SHELL.match(local):
                answer=dict(kind='code_fragment_surface',language_check_applicable=False)
            elif cleaned.lstrip().startswith(('#','//'))and answer['kind']!='code_like_excerpt':
                answer=dict(kind='comment_like',language_check_applicable=True)
            lines.append(dict(start=offset,end=end,text=local,
                              indent=len(local)-len(local.lstrip(' \t')),**answer))
        offset=end
    prior_code=False;opening_hint=False;base_indent=0
    for i,line in enumerate(lines):
        value=line['text'].strip()
        following=lines[i+1]if i+1<len(lines)else None
        next_is_code=bool(following and following['start']==line['end']and not following['language_check_applicable'])
        contiguous=bool(i and lines[i-1]['end']==line['start'])
        if not contiguous:
            prior_code=False;opening_hint=False
        if line['kind']=='comment_like'and(prior_code or next_is_code):
            line.update(kind='comment_in_code_context',language_check_applicable=False)
        elif line['language_check_applicable']and prior_code:
            shaped=bool(MARKERS.fullmatch(value)or CASE.fullmatch(value)
                        or(opening_hint and line['indent']>base_indent
                           and(ARGUMENT.fullmatch(value)or LITERAL.fullmatch(value))))
            if shaped:
                line.update(kind='code_continuation_shape',language_check_applicable=False)
        if not line['language_check_applicable']:
            if not prior_code:base_indent=line['indent']
            prior_code=True
            opening_hint=value.endswith(('(','[','{',',','\\'))
        else:
            prior_code=False;opening_hint=False
    # Merge adjacent equal-applicability runs, preserving raw offsets.
    units=[]
    for line in lines:
        key=line['language_check_applicable']
        if units and units[-1]['end']==line['start']and units[-1]['language_check_applicable']==key:
            units[-1]['end']=line['end'];units[-1]['line_kinds'].append(line['kind'])
        else:
            units.append(dict(start=line['start'],end=line['end'],
                              kind='body_or_unidentified'if key else'code_or_data_like',
                              language_check_applicable=key,line_kinds=[line['kind']]))
    eligible=[u for u in units if u['language_check_applicable']]
    body=''.join(text[u['start']:u['end']]for u in eligible)
    mixed=bool(eligible and len(eligible)!=len(units))
    return dict(kind='mixed_units'if mixed else'body_or_unidentified'if eligible else'code_or_data_units'if units else'empty',
                language_check_applicable=bool(eligible),units=units,lines=lines,residual_text=body,
                unicode_replacement_offsets=replacements,unicode_marker_is_not_confirmed_error=True,
                text_quality_assessed=False,page_OCR_skip=False,automatic_replacement=False)
