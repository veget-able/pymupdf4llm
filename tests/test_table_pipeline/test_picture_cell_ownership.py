"""Occurrence-preservation and shared-input tests for picture table ownership."""
import copy
import unittest
from unittest.mock import patch

from pymupdf4llm.helpers.table_picture_content import prepare_picture_text as prepare


def fixture(texts):
    raw_spans, spans, words = [], [], []
    for text, x in texts:
        chars = [dict(c=c, origin=(x+i, 1), bbox=(x+i, 0, x+i+1, 2))
                 for i, c in enumerate(text)]
        raw_spans.append(dict(chars=chars, font="Test", origin=(x, 1)))
        spans.append(dict(text=text, font="Test", origin=(x, 1),
                          bbox=(x, 0, x+len(text), 2)))
    raw = [dict(type=0, lines=[dict(dir=(1, 0), spans=raw_spans)])]
    blocks = [dict(type=0, lines=[dict(dir=(1, 0), spans=spans)])]
    return blocks, raw, words


def table(word, index=0):
    return [dict(cell_sources=[dict(sources=[
        dict(kind="word", index=index, source_set=0, bbox=word[:4], text=word[4])
    ])])]


def contents(blocks):
    return [s["text"] for b in blocks if b["type"] == 0
            for line in b["lines"] for s in line["spans"]]


class OwnershipTests(unittest.TestCase):
    def test_same_state_word_geometry_is_reused(self):
        from pymupdf4llm.helpers.table_text_sources import attach_word_sources
        b, r, _ = fixture([("Table Legend", 0)])
        w = (0, 0, 5, 2, "Table")
        geometry = attach_word_sources(b, r, [w])
        with patch("pymupdf._table_word_geometry.match_word_characters",
                   side_effect=AssertionError("duplicate glyph indexing")):
            result, stats = prepare(b, r, [w], table(w), word_geometry=geometry)
        self.assertEqual(contents(result), ["Legend"])
        self.assertEqual(stats["owned_glyphs"], 5)

    def test_partial_span_keeps_outside_word(self):
        b, r, _ = fixture([("Table Legend", 0)])
        w = (0, 0, 5, 2, "Table")
        old = copy.deepcopy((b, r))
        result, stats = prepare(b, r, [w], table(w))
        self.assertEqual(contents(result), ["Legend"])
        self.assertEqual(stats["owned_glyphs"], 5)
        self.assertEqual((b, r), old)

    def test_same_text_elsewhere_is_not_removed(self):
        b, r, _ = fixture([("Value", 0), ("Value", 20)])
        w = (0, 0, 5, 2, "Value")
        result, _ = prepare(b, r, [w], table(w))
        self.assertEqual(contents(result), ["Value"])
        self.assertEqual(result[0]["lines"][0]["spans"][0]["origin"], (20, 1))

    def test_word_crossing_two_font_spans(self):
        b, r, _ = fixture([("Med", 0), ("ical", 3), (" Outside", 7)])
        w = (0, 0, 7, 2, "Medical")
        result, _ = prepare(b, r, [w], table(w))
        self.assertEqual(contents(result), [" Outside"])

    def test_extra_blank_span_does_not_shift_identity(self):
        b, r, _ = fixture([(" ", 0), ("Value", 20)])
        r[0]["lines"][0]["spans"].pop(0)
        w = (20, 0, 25, 2, "Value")
        result, _ = prepare(b, r, [w], table(w))
        self.assertEqual(contents(result), [" "])

    def test_changed_input_is_retained(self):
        b, r, _ = fixture([("Value", 0)])
        b[0]["lines"][0]["spans"][0]["font"] = "Other"
        w = (0, 0, 5, 2, "Value")
        result, stats = prepare(b, r, [w], table(w))
        self.assertIsNone(result)
        self.assertEqual(stats["skipped_state_mismatch"], 1)

    def test_stale_word_index_is_not_accepted(self):
        b, r, _ = fixture([("Value", 0)])
        w = (0, 0, 5, 2, "Value")
        result, stats = prepare(b, r, [w], table((20, 0, 25, 2, "Value")))
        self.assertEqual(contents(result), ["Value"])
        self.assertEqual(stats["accepted_words"], 0)

    def test_ambiguous_glyphs_are_not_removed(self):
        b, r, _ = fixture([("Value", 0)])
        w = (0, 0, 5, 2, "Value")
        result, _ = prepare(b, r, [w, w], table(w))
        self.assertEqual(contents(result), ["Value"])

    def test_graphics_and_unrelated_spans_unchanged(self):
        b, r, _ = fixture([("Value", 0), ("Chart", 20)])
        image = dict(type=1, bbox=(0, 0, 50, 50), image=b"original pixels")
        vector = dict(type=3, bbox=(10, 10, 50, 50))
        b.extend([image, vector])
        w = (0, 0, 5, 2, "Value")
        result, _ = prepare(b, r, [w], table(w))
        self.assertEqual(b[1:], [image, vector])
        self.assertTrue(all(block["type"] == 0 for block in result))
        self.assertEqual(contents(result), ["Chart"])

    def test_missing_material_does_not_drop_text(self):
        b, _, _ = fixture([("Value", 0)])
        result, stats = prepare(b, None, [], [])
        self.assertIsNone(result)
        self.assertEqual(stats["skipped_missing_raw"], 1)

    def test_unsupported_source_kind_keeps_text(self):
        b, r, _ = fixture([("Value", 0)])
        w = (0, 0, 5, 2, "Value")
        t = table(w)
        t[0]["cell_sources"][0]["sources"][0]["kind"] = "glyph"
        result, stats = prepare(b, r, [w], t)
        self.assertEqual(contents(result), ["Value"])
        self.assertEqual(stats["unsupported_source_kind"], 1)


if __name__ == "__main__":
    unittest.main()
