"""Stored rotated text remains available without running OCR."""
from copy import deepcopy
import pytest
import pymupdf as p
from pymupdf4llm.helpers.get_text_lines import get_raw_lines, _horizontal_raw_lines

@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize("hidden", [False, True])
def test_stored_rotated_text(angle, hidden):
    with p.open() as doc:
        page = doc.new_page(width=400, height=400)
        page.insert_text((200, 200), "STORED OCR", fontsize=15, rotate=angle,
                         render_mode=3 if hidden else 0)
        blocks=page.get_text("dict")["blocks"]
        rows=get_raw_lines(blocks=deepcopy(blocks), clip=page.rect,
                           ignore_invisible=False)
        assert "STORED OCR" in "".join(s["text"] for _, spans in rows for s in spans)
        horizontal=get_raw_lines(blocks=deepcopy(blocks), clip=page.rect,
                                 ignore_invisible=False, only_horizontal=True)
        if angle:
            assert not horizontal
        else:
            assert horizontal == _horizontal_raw_lines(blocks=deepcopy(blocks),
                clip=page.rect, ignore_invisible=False)

def test_clip_excludes_rotated_text():
    with p.open() as doc:
        page=doc.new_page(width=400,height=400)
        page.insert_text((200,200),"OUTSIDE",rotate=90)
        assert not get_raw_lines(blocks=page.get_text("dict")["blocks"],
                                 clip=p.Rect(0,0,50,50))
