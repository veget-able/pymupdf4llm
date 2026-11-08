"""Native material contracts; four unchanged assertions from the source gate."""
from types import SimpleNamespace as NS
import pymupdf
from pymupdf._table_spans import resolve_spans
from pymupdf._table_word_geometry import page_word_geometry

def test_finder_retains_actual_raw_blocks_and_rules():
    with pymupdf.open() as doc:
        page = doc.new_page()
        for x in (20, 120, 220):
            page.draw_line((x, 20), (x, 100))
        for y in (20, 60, 100):
            page.draw_line((20, y), (220, y))
        page.insert_text((30, 45), 'Name')
        page.insert_text((130, 45), 'Value')
        page.insert_text((30, 85), 'One')
        page.insert_text((130, 85), '42')
        finder = page.find_tables(use_layout=False)
        assert len(finder.tables) == 1
        assert len(finder.ruling_evidence) == 6
        assert all(e['ruling_origin'] == 'vector' for e in finder.ruling_evidence)
        assert finder.tables[0]._ruling_edges is finder.ruling_evidence
        assert page._table_raw_blocks

def test_synthetic_envelope_and_unproved_user_lines_are_not_evidence():
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.draw_line((20, 20), (220, 100))
        page.draw_line((20, 100), (220, 20))
        page.insert_text((80, 65), 'diagram')
        finder = page.find_tables(use_layout=False, add_lines=[((20, 60), (220, 60))])
        assert finder.ruling_evidence == ()
        assert finder.edges

def test_existing_raster_cache_proves_only_the_matching_input_line():
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((30, 45), 'raster')
        raster = ((20, 20), (220, 20))
        other = ((20, 100), (220, 100))
        page._pymupdf4llm_raster_table_lines = {'lines': [raster]}
        finder = page.find_tables(use_layout=False, add_lines=[raster, other])
        assert len(finder.ruling_evidence) == 1
        evidence, = finder.ruling_evidence
        assert evidence['ruling_origin'] == 'raster'
        assert evidence['top'] == evidence['bottom'] == 20

def test_common_glyph_correspondence_does_not_change_cell_ownership():
    words = [(1, 0, 3, 10, '[')]
    raw = [dict(type=0, lines=[dict(dir=[1, 0], spans=[dict(chars=[
        dict(c='[', bbox=[1, 7, 3, 9], origin=[1, 8])])])])]
    page = NS(_refine_words_cache=words, _table_raw_blocks=raw,
              _span_text_spans_cache=[], _span_vertical_lines_cache=[])
    first = page_word_geometry(page, words)
    assert first == {0: ((1, 7, 3, 9),)}
    assert page_word_geometry(page, words) is first
    grid = resolve_spans(page, [[(0, 6, 5, 11)]])
    assert grid[0][0].text == ''
