from copy import deepcopy
from types import SimpleNamespace as NS
from pymupdf import Rect
from pymupdf4llm.helpers.table_text_sources import attach_word_sources
from pymupdf4llm.helpers.table_external_text import _not_already_rendered, _rendered_word_indices
from pymupdf4llm.helpers.get_text_lines import get_raw_lines


def fixture(texts=('ABC','ABC'), starts=(0,30)):
    spans=[];rawspans=[];words=[]
    for text,x in zip(texts,starts):
        bbox=[x,5,x+len(text)*2,6]
        s=dict(text=text,bbox=bbox,origin=[x,8],font='Test',size=10,flags=0,char_flags=16,alpha=255)
        spans.append(s)
        chars=[dict(c=c,bbox=[x+i*2,5,x+(i+1)*2,6],origin=[x+i*2,8]) for i,c in enumerate(text)]
        rawspans.append(dict(s,chars=chars))
        words.append([x,0,x+len(text)*2,10,text])
    line=dict(bbox=[0,5,100,6],dir=[1.,0.],spans=spans)
    blocks=[dict(type=0,bbox=[0,0,100,10],lines=[line])]
    raw=[dict(type=0,lines=[dict(line,spans=rawspans)])]
    return blocks,raw,words


def box(spans):return NS(boxclass='text',textlines=[dict(spans=spans)])
def record(words,i):
    return dict(source_kind='word',node_index=0,bbox=words[i][:4],text=words[i][4],
                units=[dict(index=i,bbox=words[i][:4],text=words[i][4])])


def test_same_source_different_ink_and_font_height_is_not_reemitted():
    blocks,raw,words=fixture();attach_word_sources(blocks,raw,words)
    s=blocks[0]['lines'][0]['spans'][0]
    assert _not_already_rendered(record(words,0),[box([s])],words)==[]
    # Same text at a different physical source remains.
    assert _not_already_rendered(record(words,1),[box([s])],words)


def test_partial_word_requires_all_source_characters_to_have_been_rendered():
    blocks,raw,words=fixture(('AB','CD'),(0,4));words=[[0,0,8,10,'ABCD']]
    attach_word_sources(blocks,raw,words);spans=blocks[0]['lines'][0]['spans']
    assert _rendered_word_indices([box(spans[:1])],words)==set()
    assert _rendered_word_indices([box(spans)],words)=={0}


def test_real_span_join_carries_both_source_word_occurrences():
    blocks,raw,words=fixture(('AB','CD'),(0,4));attach_word_sources(blocks,raw,words)
    lines=get_raw_lines(blocks=blocks,clip=Rect(0,0,100,10),ignore_invisible=False)
    assert len(lines)==1 and len(lines[0][1])==1
    assert lines[0][1][0]['text']=='ABCD'
    assert _rendered_word_indices([box(lines[0][1])],words)=={0,1}


def test_modified_text_and_changed_word_cache_do_not_prove_delivery():
    blocks,raw,words=fixture();attach_word_sources(blocks,raw,words)
    s=blocks[0]['lines'][0]['spans'][0];changed=deepcopy(words);changed[0][0]=1
    assert _rendered_word_indices([box([s])],changed)==set()
    s['text']='AB'
    assert _rendered_word_indices([box([s])],words)==set()


def test_origin_maps_glyph_outside_font_height_without_bbox_tolerance():
    blocks,raw,words=fixture(('A',),(0,))
    raw[0]['lines'][0]['spans'][0]['chars'][0]['bbox']=[0,15,2,16]
    attach_word_sources(blocks,raw,words)
    assert _rendered_word_indices([box(blocks[0]['lines'][0]['spans'])],words)=={0}


def test_overlapping_identical_word_records_are_ambiguous():
    blocks,raw,words=fixture(('A',),(0,));words.append(list(words[0]))
    attach_word_sources(blocks,raw,words)
    assert _rendered_word_indices([box(blocks[0]['lines'][0]['spans'])],words)==set()


def test_neighbouring_source_lines_inside_tall_word_bbox_are_not_concatenated():
    blocks,raw,words=fixture(('ABC','noise'),(0,0))
    for data in (blocks,raw):
        line=data[0]['lines'][0]
        data[0]['lines']=[dict(line,spans=[s]) for s in line['spans']]
    words=words[:1]
    attach_word_sources(blocks,raw,words)
    assert _rendered_word_indices([box(blocks[0]['lines'][0]['spans'])],words)=={0}




def test_join_cannot_revalidate_a_source_claim_after_text_was_modified():
    blocks,raw,words=fixture(('AB','CD'),(0,4));attach_word_sources(blocks,raw,words)
    blocks[0]['lines'][0]['spans'][0]['text']='X'
    lines=get_raw_lines(blocks=blocks,clip=Rect(0,0,100,10),ignore_invisible=False)
    assert lines[0][1][0]['text']=='XCD'
    assert _rendered_word_indices([box(lines[0][1])],words)=={1}
