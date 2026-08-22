import unittest
from unittest import mock

import pymupdf

from pymupdf4llm.ocr import exec_ocr_interface as ocr


DEVANAGARI_STRINGS = (
    "कार्यालय: सीमा शल्क प्रधान आयक्त (वाय माल वाहक आयात)",
    "नवीन सीमा शल्क भवन, निकट इंदिरा गाधी अंतराष्टीय हवाई अडडा, नई दिल्ली-110037",
    "7०9/19",
)


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

    def test_uncovered_devanagari_ascii_fails_closed_before_page_mutation(self):
        document, page = _nonempty_page()
        before = _page_snapshot(page)

        with self.assertRaises(ocr.OCRFontCoverageError):
            ocr.exec_ocr_full(page, _full_ocr_result(("भारत OFFICE",)))

        self.assertEqual(before, _page_snapshot(page))
        document.close()

    def test_devanagari_resource_is_inserted_once_for_multiple_strings(self):
        document, page = _nonempty_page()

        ocr.exec_ocr_full(page, _full_ocr_result(DEVANAGARI_STRINGS))

        resources = [font[4] for font in page.get_fonts(full=True)]
        self.assertEqual(1, resources.count(ocr.DEVANAGARI_FONTNAME))
        self.assertEqual(list(DEVANAGARI_STRINGS), page.get_text("text").splitlines())
        document.close()

    def test_current_font_covered_writeback_uses_the_existing_cjk_path(self):
        for text in (
            "OFFICE OF THE PRINCIPAL COMMISSIONER",
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

    def test_uncovered_non_devanagari_or_invalid_text_is_rejected(self):
        for text in ("😀", "العربية", "NUL\x00text", "bad\ufffdtext"):
            with self.subTest(text=repr(text)):
                with self.assertRaises(ocr.OCRFontCoverageError):
                    ocr._select_writeback_font(text)

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
        for text in ("भारत OFFICE", "bad\x00text", "bad\ufffdtext", "😀"):
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
