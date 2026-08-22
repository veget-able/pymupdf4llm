import hashlib
import math
import unittest
from unittest import mock

import pymupdf

from pymupdf4llm.ocr import exec_ocr_interface as ocr


DEVANAGARI_STRINGS = (
    "कार्यालय: सीमा शल्क प्रधान आयक्त (वाय माल वाहक आयात)",
    "नवीन सीमा शल्क भवन, निकट इंदिरा गाधी अंतराष्टीय हवाई अडडा, नई दिल्ली-110037",
    "7०9/19",
)

D2_MIXED_STRINGS = (
    "uo updde oqe प q pगy sem zi's/n uoensI8ay Suypes VOIoN पoI u! uoneoddeपL 'I",
    "Jo unpuerouaN/snL Jo pa e q ponsuos eM uonnsuI/snL ueodde पL ZI0Z/I0/8I",
)
D2_MIXED_SHA256 = (
    "58b2ebbd4283f54515600378c2d43ddcadc1d370471bb49a84154f6e8676ac0e",
    "13a88bf9cae678c1bc770f523b90b0eb6b834b380f16619374d8c08d62dcaca2",
)


class _RecordingPage:
    def __init__(self):
        self.fonts = []
        self.text = []

    def insert_font(self, **kwargs):
        self.fonts.append(kwargs)

    def insert_text(self, point, text, **kwargs):
        self.text.append((pymupdf.Point(point), text, kwargs))


def _write_text(text, font, fontname):
    document = pymupdf.open()
    page = document.new_page(width=600, height=180)
    rect = pymupdf.Rect(20, 20, 580, 80)
    page.insert_font(fontname=fontname, fontbuffer=font.buffer)
    page.insert_text(
        rect.bl + (0, -0.2 * rect.height),
        text,
        fontsize=rect.height,
        fontname=fontname,
        morph=(rect.bl, ocr.adjust_width(text, rect.height, rect, font=font)),
    )
    reopened = pymupdf.open("pdf", document.tobytes())
    reopened_page = reopened[0]
    return reopened_page.get_text("text"), reopened_page.read_contents(), reopened_page


def _full_ocr_result(texts):
    def full_ocr(image):
        width = image.shape[1]
        result = []
        for ordinal, text in enumerate(texts):
            top = 20 + ordinal * 80
            result.append(
                (
                    [
                        [20, top],
                        [width - 20, top],
                        [width - 20, top + 50],
                        [20, top + 50],
                    ],
                    text,
                    0.99,
                )
            )
        return result

    return full_ocr


def _det_only_result(text_count):
    def det_only(image):
        width = image.shape[1]
        result = []
        for ordinal in range(text_count):
            top = 20 + ordinal * 80
            result.append(
                (
                    [
                        [20, top],
                        [width - 20, top],
                        [width - 20, top + 50],
                        [20, top + 50],
                    ],
                    0.99,
                )
            )
        return result

    return det_only


def _nonempty_page():
    document = pymupdf.open()
    page = document.new_page(width=600, height=300)
    page.draw_rect(page.rect, color=None, fill=(0, 0, 0))
    return document, page


def _page_snapshot(page):
    return (
        page.get_text("text"),
        page.read_contents(),
        page.get_fonts(full=True),
        list(page.annots() or ()),
    )


def _run_detection(page, texts):
    with (
        mock.patch.object(ocr, "TESSDATA", "test"),
        mock.patch.object(ocr, "get_text", side_effect=texts),
    ):
        ocr.exec_ocr_detection(page, _det_only_result(len(texts)))


class ScriptAwareWritebackTests(unittest.TestCase):
    def test_devanagari_font_is_builtin_and_covers_the_full_block(self):
        font = ocr._get_devanagari_font()

        self.assertEqual("Noto Serif Devanagari Regular", font.name)
        self.assertTrue(
            all(font.has_glyph(codepoint) != 0 for codepoint in range(0x0900, 0x0980))
        )

    def test_devanagari_roundtrips_without_replacement_or_nul(self):
        for text in DEVANAGARI_STRINGS:
            with self.subTest(text=text):
                font, fontname = ocr._select_writeback_font(text)
                extracted, _, _ = _write_text(text, font, fontname)

                self.assertEqual(ocr.DEVANAGARI_FONTNAME, fontname)
                self.assertEqual(text, extracted.strip())
                self.assertNotIn("\ufffd", extracted)
                self.assertNotIn("\x00", extracted)

    def test_devanagari_ascii_punctuation_can_use_the_script_font(self):
        font, fontname = ocr._select_writeback_font("भारत 7/19")

        self.assertIs(font, ocr._get_devanagari_font())
        self.assertEqual(ocr.DEVANAGARI_FONTNAME, fontname)

    def test_uncovered_devanagari_input_fails_closed_before_page_mutation(self):
        document, page = _nonempty_page()
        before = _page_snapshot(page)

        with self.assertRaises(ocr.OCRFontCoverageError):
            ocr.exec_ocr_full(page, _full_ocr_result(("भारत😀",)))

        self.assertEqual(before, _page_snapshot(page))
        document.close()

    def test_devanagari_resource_is_inserted_once_for_multiple_strings(self):
        document, page = _nonempty_page()

        ocr.exec_ocr_full(page, _full_ocr_result(DEVANAGARI_STRINGS))

        resources = [font[4] for font in page.get_fonts(full=True)]
        self.assertEqual(1, resources.count(ocr.DEVANAGARI_FONTNAME))
        self.assertEqual(list(DEVANAGARI_STRINGS), page.get_text("text").splitlines())
        document.close()

    def test_non_devanagari_writeback_uses_the_exact_legacy_cjk_path(self):
        for text in (
            "OFFICE OF THE PRINCIPAL COMMISSIONER",
            "∆E = mc²",
            "العربية",
            "Русский",
            "漢字",
        ):
            with self.subTest(text=text):
                current = _write_text(text, ocr.FONT, ocr.FONTNAME)
                selected_font, selected_name = ocr._select_writeback_font(text)
                selected = _write_text(text, selected_font, selected_name)

                self.assertIs(ocr.FONT, selected_font)
                self.assertEqual(ocr.FONTNAME, selected_name)
                self.assertEqual(current[0], selected[0])
                self.assertEqual(current[1], selected[1])
                self.assertNotIn(
                    ocr.DEVANAGARI_FONTNAME,
                    [font[4] for font in selected[2].get_fonts(full=True)],
                )

    def test_devanagari_strings_not_fully_covered_are_rejected(self):
        for text in ("भारत\x00", "भारत\ufffd", "भारत😀"):
            with self.subTest(text=repr(text)):
                with self.assertRaises(ocr.OCRFontCoverageError):
                    ocr._select_writeback_font(text)

    def test_non_devanagari_full_and_detection_paths_keep_legacy_selection(self):
        texts = ("∆E = mc²", "العربية", "Русский")

        document, page = _nonempty_page()
        ocr.exec_ocr_full(page, _full_ocr_result(texts))
        full_resources = [font[4] for font in page.get_fonts(full=True)]
        self.assertEqual(1, full_resources.count(ocr.FONTNAME))
        self.assertNotIn(ocr.DEVANAGARI_FONTNAME, full_resources)
        document.close()

        document, page = _nonempty_page()
        _run_detection(page, texts)
        detection_resources = [font[4] for font in page.get_fonts(full=True)]
        self.assertEqual(1, detection_resources.count(ocr.FONTNAME))
        self.assertNotIn(ocr.DEVANAGARI_FONTNAME, detection_resources)
        document.close()

    def test_detection_writeback_roundtrips_devanagari_without_replacement_or_nul(self):
        document, page = _nonempty_page()

        _run_detection(page, DEVANAGARI_STRINGS)

        reopened = pymupdf.open("pdf", document.tobytes())
        extracted = reopened[0].get_text("text")
        self.assertEqual(list(DEVANAGARI_STRINGS), extracted.splitlines())
        self.assertNotIn("\ufffd", extracted)
        self.assertNotIn("\x00", extracted)
        resources = [font[4] for font in reopened[0].get_fonts(full=True)]
        self.assertEqual(1, resources.count(ocr.DEVANAGARI_FONTNAME))
        document.close()

    def test_detection_preflight_rejects_before_target_page_mutation(self):
        for text in ("भारत\x00", "भारत\ufffd", "भारत😀"):
            with self.subTest(text=repr(text)):
                document, page = _nonempty_page()
                before = _page_snapshot(page)

                with self.assertRaises(ocr.OCRFontCoverageError):
                    _run_detection(page, (text,))

                self.assertEqual(before, _page_snapshot(page))
                document.close()

    def test_blank_results_do_not_mutate_either_writeback_path(self):
        for callback in (
            lambda page: ocr.exec_ocr_full(page, _full_ocr_result((" \t",))),
            lambda page: _run_detection(page, (" \t",)),
        ):
            with self.subTest(callback=callback):
                document, page = _nonempty_page()
                before = _page_snapshot(page)

                callback(page)

                self.assertEqual(before, _page_snapshot(page))
                document.close()

    def test_detection_covered_path_uses_existing_cjk_resource(self):
        document, page = _nonempty_page()

        _run_detection(page, ("OFFICE OF THE PRINCIPAL COMMISSIONER",))

        resources = [font[4] for font in page.get_fonts(full=True)]
        self.assertEqual(1, resources.count(ocr.FONTNAME))
        self.assertNotIn(ocr.DEVANAGARI_FONTNAME, resources)
        self.assertEqual(
            "OFFICE OF THE PRINCIPAL COMMISSIONER", page.get_text("text").strip()
        )
        document.close()

    def test_selected_font_controls_the_width_scaling(self):
        text = DEVANAGARI_STRINGS[0]
        font, _ = ocr._select_writeback_font(text)
        rect = pymupdf.Rect(10, 10, 400, 40)

        matrix = ocr.adjust_width(text, rect.height, rect, font=font)

        self.assertIsNot(font, ocr.FONT)
        self.assertEqual(rect.width / font.text_length(text, rect.height), matrix.a)

    def test_actual_d2_mixed_strings_and_codepoints_are_pinned(self):
        self.assertEqual(
            list(D2_MIXED_SHA256),
            [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in D2_MIXED_STRINGS],
        )
        self.assertEqual([0x092A, 0x0917, 0x092A, 0x092A], [ord(c) for c in D2_MIXED_STRINGS[0] if 0x0900 <= ord(c) <= 0x097F])
        self.assertEqual([0x092A], [ord(c) for c in D2_MIXED_STRINGS[1] if 0x0900 <= ord(c) <= 0x097F])

    def test_actual_d2_mixed_strings_plan_maximal_cjk_and_devanagari_runs(self):
        for text in D2_MIXED_STRINGS:
            with self.subTest(text_sha256=hashlib.sha256(text.encode()).hexdigest()):
                runs = ocr._plan_writeback_runs(text)
                self.assertEqual(text, "".join(run[0] for run in runs))
                self.assertGreater(len(runs), 1)
                self.assertEqual(ocr.FONTNAME, runs[0][2])
                self.assertTrue(any(run[2] == ocr.DEVANAGARI_FONTNAME for run in runs))
                self.assertTrue(all(run[2] != next_run[2] for run, next_run in zip(runs, runs[1:])))
                self.assertTrue(all(ocr._font_covers(run[1], run[0]) for run in runs))

    def test_mixed_planner_uses_cjk_for_an_equal_transition_tie(self):
        runs = ocr._plan_writeback_runs("A/प")

        self.assertEqual([("A/", ocr.FONTNAME), ("प", ocr.DEVANAGARI_FONTNAME)], [(text, name) for text, _font, name in runs])

    def test_cluster_planner_keeps_marks_virama_variation_and_join_controls_with_base(self):
        self.assertEqual(["क्‍षि"], ocr._grapheme_clusters("क्‍षि"))
        self.assertEqual(["क्‌", "ष"], ocr._grapheme_clusters("क्‌ष"))
        self.assertEqual(["क️"], ocr._grapheme_clusters("क️"))

    def test_mixed_roundtrip_preserves_actual_d2_strings_in_full_and_detection_paths(self):
        for path in ("full", "detection"):
            with self.subTest(path=path):
                document, page = _nonempty_page()
                if path == "full":
                    ocr.exec_ocr_full(page, _full_ocr_result(D2_MIXED_STRINGS))
                else:
                    _run_detection(page, D2_MIXED_STRINGS)
                reopened = pymupdf.open("pdf", document.tobytes())
                extracted = reopened[0].get_text("text")
                self.assertEqual(list(D2_MIXED_STRINGS), extracted.splitlines())
                self.assertNotIn("\ufffd", extracted)
                self.assertNotIn("\x00", extracted)
                resources = [font[4] for font in reopened[0].get_fonts(full=True)]
                self.assertEqual(1, resources.count(ocr.FONTNAME))
                self.assertEqual(1, resources.count(ocr.DEVANAGARI_FONTNAME))
                document.close()

    def test_mixed_inserter_uses_one_scale_and_preserves_run_order_and_geometry(self):
        text = D2_MIXED_STRINGS[1]
        rect = pymupdf.Rect(20, 20, 580, 80)
        prepared = ocr._prepare_writeback(text, rect)
        page = _RecordingPage()
        ocr._insert_writeback(page, rect, text, prepared, {ocr.FONTNAME})
        runs, natural_width = prepared
        scale = rect.width / natural_width
        self.assertTrue(math.isfinite(scale) and scale > 0)
        self.assertEqual([run[0] for run in runs], [record[1] for record in page.text])
        self.assertEqual(text, "".join(record[1] for record in page.text))
        self.assertTrue(all(record[2]["morph"][1].a == scale for record in page.text))
        expected = rect.bl + (0, -0.2 * rect.height)
        self.assertEqual(expected, page.text[0][0])
        self.assertAlmostEqual(rect.x1, page.text[-1][0].x + runs[-1][3] * scale)
        self.assertEqual(1, sum(font["fontname"] == ocr.DEVANAGARI_FONTNAME for font in page.fonts))

    def test_mixed_preflight_rejects_a_later_uncovered_item_before_any_mutation(self):
        callbacks = (
            lambda page: ocr.exec_ocr_full(page, _full_ocr_result((D2_MIXED_STRINGS[0], "भारत😀"))),
            lambda page: _run_detection(page, (D2_MIXED_STRINGS[0], "भारत😀")),
        )
        for callback in callbacks:
            with self.subTest(callback=callback):
                document, page = _nonempty_page()
                before = _page_snapshot(page)
                with self.assertRaises(ocr.OCRFontCoverageError):
                    callback(page)
                self.assertEqual(before, _page_snapshot(page))
                document.close()

    def test_mixed_resource_is_reused_across_multiple_items(self):
        document, page = _nonempty_page()
        ocr.exec_ocr_full(page, _full_ocr_result(D2_MIXED_STRINGS))
        resources = [font[4] for font in page.get_fonts(full=True)]
        self.assertEqual(1, resources.count(ocr.FONTNAME))
        self.assertEqual(1, resources.count(ocr.DEVANAGARI_FONTNAME))
        document.close()
