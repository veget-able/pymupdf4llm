"""Span-level provenance contracts for text inserted by OCR producers."""

from types import SimpleNamespace
from unittest import TestCase, mock

import pymupdf


def _fake_pixmap():
    width = height = 100
    return SimpleNamespace(
        width=width,
        height=height,
        samples=bytes(width * height * 3),
        irect=pymupdf.IRect(0, 0, width, height),
    )


def _text_spans(page):
    blocks = page.get_text(
        "dict",
        flags=pymupdf.TEXTFLAGS_DICT | pymupdf.TEXT_COLLECT_STYLES,
    )["blocks"]
    return [
        span
        for block in blocks
        if block["type"] == 0
        for line in block["lines"]
        for span in line["spans"]
    ]


def _text_blocks(page):
    return page.get_text(
        "dict",
        flags=pymupdf.TEXTFLAGS_DICT
        | pymupdf.TEXT_COLLECT_STYLES
        | pymupdf.TEXT_ACCURATE_BBOXES,
    )["blocks"]


def _annotated_spans(page, *, runtime_ocr_applied=False):
    from pymupdf4llm.ocr.span_provenance import annotate_page_ocr_spans

    blocks = _text_blocks(page)
    annotate_page_ocr_spans(
        page,
        blocks,
        runtime_ocr_applied=runtime_ocr_applied,
    )
    return [
        span
        for block in blocks
        if block["type"] == 0
        for line in block["lines"]
        for span in line["spans"]
    ]


def _scan_backed_page(hidden_text="hidden scan text"):
    """Paint ordinary text, then cover it with a raster of the same page."""
    source = pymupdf.open()
    source_page = source.new_page(width=240, height=100)
    source_page.insert_text((20, 45), hidden_text, fontsize=10)
    scan = source_page.get_pixmap(dpi=150, alpha=False)

    target = pymupdf.open()
    target_page = target.new_page(width=240, height=100)
    target_page.insert_text((20, 45), hidden_text, fontsize=10)
    target_page.insert_image(target_page.rect, pixmap=scan, overlay=True)
    reopened = pymupdf.open(stream=target.tobytes(), filetype="pdf")
    source.close()
    target.close()
    return reopened, reopened[0]


def _persisted_hidden_ocr_page(text="existing OCR text"):
    """Return a reopened PDF page containing a pre-existing OCR text layer."""
    source = pymupdf.open()
    page = source.new_page(width=100, height=100)
    font = pymupdf.Font("cjk")
    page.insert_font(fontname="ocrfont", fontbuffer=font.buffer)
    page.insert_text((10, 30), text, fontname="ocrfont", render_mode=3)
    reopened = pymupdf.open(stream=source.tobytes(), filetype="pdf")
    return reopened, reopened[0]


def _assert_ocr_provenance(span, expected_text, expected_origin, *, hidden):
    from pymupdf4llm.helpers.utils import is_ocr_text
    from pymupdf4llm.ocr.analyze_page import is_ocr_span

    assert span["text"] == expected_text
    assert span["font"] == "Droid Sans Fallback Regular"
    assert (span["alpha"] == 0) is hidden
    assert (
        not span["char_flags"] & pymupdf.mupdf.FZ_STEXT_FILLED
        and not span["char_flags"] & pymupdf.mupdf.FZ_STEXT_STROKED
    ) is hidden
    assert span["is_ocr"] is True
    assert span["ocr_origin"] == expected_origin
    assert is_ocr_span(span) is True
    assert is_ocr_text(span) is True


class OCRSpanProvenanceTests(TestCase):
    def test_preexisting_hidden_ocr_layer_survives_keep_old(self):
        from pymupdf4llm.ocr import exec_ocr_interface

        for path in ("full", "detection"):
            with self.subTest(path=path):
                doc, page = _persisted_hidden_ocr_page()
                calls = []
                if path == "full":
                    exec_ocr_interface.exec_ocr_full(
                        page,
                        lambda _image: calls.append(True),
                        keep_ocr_text=True,
                    )
                else:
                    with mock.patch.object(
                        exec_ocr_interface, "TESSDATA", object()
                    ):
                        exec_ocr_interface.exec_ocr_detection(
                            page,
                            lambda _image: calls.append(True),
                            keep_ocr_text=True,
                        )

                self.assertEqual(calls, [])
                spans = _annotated_spans(page)
                self.assertEqual(len(spans), 1)
                _assert_ocr_provenance(
                    spans[0],
                    "existing OCR text",
                    "source_standard",
                    hidden=True,
                )
                doc.close()

    def test_zero_output_runtime_call_does_not_claim_existing_source_ocr(self):
        from pymupdf4llm.ocr import exec_ocr_interface

        pixmap = _fake_pixmap()
        doc, page = _persisted_hidden_ocr_page()
        with mock.patch.object(
            exec_ocr_interface,
            "get_pixmap",
            side_effect=lambda *_args, **_kwargs: (pixmap, False),
        ):
            exec_ocr_interface.exec_ocr_full(
                page,
                lambda _image: [],
                keep_ocr_text=False,
            )

        spans = _annotated_spans(page, runtime_ocr_applied=True)
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0]["is_ocr"])
        self.assertEqual(spans[0]["ocr_origin"], "source_standard")
        doc.close()

    def test_preexisting_hidden_ocr_layer_is_replaced_with_same_provenance(self):
        from pymupdf4llm.ocr import exec_ocr_interface

        pixmap = _fake_pixmap()
        box = [(10, 10), (90, 10), (90, 30), (10, 30)]
        doc, page = _persisted_hidden_ocr_page()
        with mock.patch.object(
            exec_ocr_interface,
            "get_pixmap",
            side_effect=lambda *_args, **_kwargs: (pixmap, False),
        ):
            exec_ocr_interface.exec_ocr_full(
                page,
                lambda _image: [(box, "replacement OCR text", 0.99)],
                keep_ocr_text=False,
            )

        spans = _annotated_spans(page)
        self.assertEqual(len(spans), 1)
        _assert_ocr_provenance(
            spans[0], "replacement OCR text", "runtime", hidden=False
        )
        doc.close()

    def test_full_ocr_writeback_preserves_span_provenance(self):
        from pymupdf4llm.ocr import exec_ocr_interface

        pixmap = _fake_pixmap()
        box = [(10, 10), (90, 10), (90, 30), (10, 30)]
        with mock.patch.object(
            exec_ocr_interface,
            "get_pixmap",
            side_effect=lambda *_args, **_kwargs: (pixmap, False),
        ):
            doc = pymupdf.open()
            page = doc.new_page(width=100, height=100)
            exec_ocr_interface.exec_ocr_full(
                page,
                lambda _image: [(box, "recognized text", 0.99)],
            )

        spans = _annotated_spans(page)
        self.assertEqual(len(spans), 1)
        _assert_ocr_provenance(
            spans[0], "recognized text", "runtime", hidden=False
        )

    def test_runtime_regions_do_not_relabel_native_spans_on_a_mixed_page(self):
        from pymupdf4llm.ocr import exec_ocr_interface

        pixmap = _fake_pixmap()
        box = [(10, 10), (90, 10), (90, 30), (10, 30)]
        doc = pymupdf.open()
        page = doc.new_page(width=100, height=100)
        page.insert_text((10, 80), "native text", fontsize=10)
        with mock.patch.object(
            exec_ocr_interface,
            "get_pixmap",
            side_effect=lambda *_args, **_kwargs: (pixmap, False),
        ):
            exec_ocr_interface.exec_ocr_full(
                page,
                lambda _image: [(box, "runtime text", 0.99)],
            )

        spans = {span["text"]: span for span in _annotated_spans(page)}
        self.assertFalse(spans["native text"]["is_ocr"])
        self.assertIsNone(spans["native text"]["ocr_origin"])
        self.assertTrue(spans["runtime text"]["is_ocr"])
        self.assertEqual(spans["runtime text"]["ocr_origin"], "runtime")
        doc.close()

    def test_detection_ocr_writeback_preserves_span_provenance(self):
        from pymupdf4llm.ocr import exec_ocr_interface

        pixmap = _fake_pixmap()
        box = [(10, 10), (90, 10), (90, 30), (10, 30)]
        with (
            mock.patch.object(exec_ocr_interface, "TESSDATA", object()),
            mock.patch.object(
                exec_ocr_interface,
                "get_pixmap",
                side_effect=lambda *_args, **_kwargs: (pixmap, False),
            ),
            mock.patch.object(
                exec_ocr_interface,
                "_recognize_detection_boxes",
                side_effect=lambda *_args, **_kwargs: [
                    (pymupdf.IRect(10, 10, 90, 30), "detected text")
                ],
            ),
        ):
            doc = pymupdf.open()
            page = doc.new_page(width=100, height=100)
            exec_ocr_interface.exec_ocr_detection(
                page,
                lambda _image: [(box, 0.99)],
            )

        spans = _annotated_spans(page)
        self.assertEqual(len(spans), 1)
        _assert_ocr_provenance(
            spans[0], "detected text", "runtime", hidden=False
        )

    def test_visible_native_fallback_font_is_not_mistaken_for_ocr(self):
        from pymupdf4llm.helpers.utils import is_ocr_text
        from pymupdf4llm.ocr.analyze_page import is_ocr_span

        for text in ("native text", "native CJK \uac00"):
            with self.subTest(text=text):
                doc = pymupdf.open()
                page = doc.new_page()
                font = pymupdf.Font("cjk")
                page.insert_font(fontname="nativefont", fontbuffer=font.buffer)
                page.insert_text((72, 72), text, fontname="nativefont")

                spans = _text_spans(page)
                self.assertEqual(len(spans), 1)
                self.assertEqual(spans[0]["font"], "Droid Sans Fallback Regular")
                self.assertEqual(spans[0]["alpha"], 255)
                self.assertTrue(
                    spans[0]["char_flags"] & pymupdf.mupdf.FZ_STEXT_FILLED
                )
                self.assertFalse(is_ocr_span(spans[0]))
                self.assertFalse(is_ocr_text(spans[0]))

    def test_annotation_distinguishes_existing_and_runtime_hidden_text(self):
        from pymupdf4llm.ocr.span_provenance import annotate_page_ocr_spans

        for runtime, expected_origin in (
            (False, "source_standard"),
            (True, "runtime"),
        ):
            with self.subTest(runtime=runtime):
                doc, page = _persisted_hidden_ocr_page()
                blocks = _text_blocks(page)
                result = annotate_page_ocr_spans(
                    page,
                    blocks,
                    runtime_ocr_applied=runtime,
                )
                span = next(
                    span
                    for block in blocks
                    if block["type"] == 0
                    for line in block["lines"]
                    for span in line["spans"]
                )
                self.assertTrue(span["is_ocr"])
                self.assertEqual(span["ocr_origin"], expected_origin)
                self.assertEqual(result[f"{expected_origin}_spans"], 1)
                doc.close()

    def test_annotation_preserves_native_and_ocr_spans_on_a_mixed_page(self):
        from pymupdf4llm.ocr.span_provenance import annotate_page_ocr_spans

        doc = pymupdf.open()
        page = doc.new_page(width=240, height=100)
        page.insert_text((20, 30), "visible native", fontsize=10)
        page.insert_text((20, 60), "hidden OCR", fontsize=10, render_mode=3)
        blocks = _text_blocks(page)
        annotate_page_ocr_spans(page, blocks)
        spans = {
            span["text"]: span
            for block in blocks
            if block["type"] == 0
            for line in block["lines"]
            for span in line["spans"]
        }

        self.assertFalse(spans["visible native"]["is_ocr"])
        self.assertIsNone(spans["visible native"]["ocr_origin"])
        self.assertTrue(spans["hidden OCR"]["is_ocr"])
        self.assertEqual(
            spans["hidden OCR"]["ocr_origin"], "source_standard"
        )
        doc.close()

    def test_line_coalescing_does_not_erase_ocr_provenance_boundary(self):
        from pymupdf4llm.helpers.get_text_lines import get_raw_lines

        blocks = [
            {
                "type": 0,
                "bbox": (10, 10, 50, 22),
                "lines": [
                    {
                        "bbox": (10, 10, 50, 22),
                        "dir": (1, 0),
                        "spans": [
                            {
                                "bbox": (10, 10, 30, 22),
                                "text": "OCR",
                                "font": "Helvetica",
                                "size": 10,
                                "flags": 0,
                                "char_flags": pymupdf.mupdf.FZ_STEXT_FILLED,
                                "alpha": 255,
                                "is_ocr": True,
                                "ocr_origin": "source_nonstandard",
                            },
                            {
                                "bbox": (30, 10, 50, 22),
                                "text": "native",
                                "font": "Helvetica",
                                "size": 10,
                                "flags": 0,
                                "char_flags": pymupdf.mupdf.FZ_STEXT_FILLED,
                                "alpha": 255,
                                "is_ocr": False,
                                "ocr_origin": None,
                            },
                        ],
                    }
                ],
            }
        ]
        lines = get_raw_lines(
            blocks=blocks,
            clip=pymupdf.Rect(0, 0, 100, 100),
            ignore_invisible=False,
        )

        self.assertEqual(len(lines), 1)
        self.assertEqual(len(lines[0][1]), 2)
        self.assertEqual(
            [span["is_ocr"] for span in lines[0][1]], [True, False]
        )

    def test_nonstandard_source_ocr_requires_all_three_page_signals(self):
        from pymupdf4llm.helpers.utils import is_ocr_text
        from pymupdf4llm.ocr.span_provenance import annotate_page_ocr_spans

        doc, page = _scan_backed_page("hidden scan text provenance")
        blocks = _text_blocks(page)
        result = annotate_page_ocr_spans(
            page,
            blocks,
            line_recognizer=lambda crops, _language: [
                "hidden scan text provenance" for _crop in crops
            ],
        )
        spans = [
            span
            for block in blocks
            if block["type"] == 0
            for line in block["lines"]
            for span in line["spans"]
            if span["text"].strip()
        ]
        self.assertEqual(result["nonstandard_status"], "confirmed")
        self.assertEqual(result["source_nonstandard_spans"], len(spans))
        self.assertTrue(all(span["is_ocr"] for span in spans))
        self.assertTrue(all(is_ocr_text(span) for span in spans))
        self.assertEqual(
            {span["ocr_origin"] for span in spans},
            {"source_nonstandard"},
        )
        doc.close()

    def test_nonstandard_source_decision_is_reused_on_the_same_page(self):
        from pymupdf4llm.ocr.span_provenance import annotate_page_ocr_spans

        doc, page = _scan_backed_page("cached hidden scan text")
        calls = []

        def recognize(crops, _language):
            calls.append(len(crops))
            return ["cached hidden scan text" for _crop in crops]

        first = annotate_page_ocr_spans(
            page,
            _text_blocks(page),
            line_recognizer=recognize,
        )
        second_blocks = _text_blocks(page)
        second = annotate_page_ocr_spans(
            page,
            second_blocks,
            line_recognizer=lambda *_args: self.fail(
                "cached page decision must avoid a second recognition call"
            ),
        )

        self.assertEqual(calls, [1])
        self.assertEqual(first["nonstandard_status"], "confirmed")
        self.assertEqual(second["nonstandard_status"], "confirmed")
        self.assertTrue(
            all(
                span["is_ocr"]
                for block in second_blocks
                if block["type"] == 0
                for line in block["lines"]
                for span in line["spans"]
                if span["text"].strip()
            )
        )
        doc.close()

    def test_occluded_nonmatching_text_is_not_called_ocr(self):
        from pymupdf4llm.ocr.span_provenance import annotate_page_ocr_spans

        doc, page = _scan_backed_page(
            "stale hidden text without raster agreement"
        )
        blocks = _text_blocks(page)
        result = annotate_page_ocr_spans(
            page,
            blocks,
            line_recognizer=lambda crops, _language: [
                "different raster text" for _crop in crops
            ],
        )
        spans = [
            span
            for block in blocks
            if block["type"] == 0
            for line in block["lines"]
            for span in line["spans"]
            if span["text"].strip()
        ]
        self.assertEqual(result["nonstandard_status"], "text_image_mismatch")
        self.assertTrue(all(span["is_ocr"] is False for span in spans))
        self.assertTrue(all(span["ocr_origin"] is None for span in spans))
        doc.close()

    def test_visible_text_above_page_image_is_not_called_ocr(self):
        from pymupdf4llm.ocr.span_provenance import annotate_page_ocr_spans

        image_doc = pymupdf.open()
        image_page = image_doc.new_page(width=240, height=100)
        image_page.insert_text((20, 45), "background scan", fontsize=16)
        scan = image_page.get_pixmap(dpi=150, alpha=False)
        doc = pymupdf.open()
        page = doc.new_page(width=240, height=100)
        page.insert_image(page.rect, pixmap=scan)
        page.insert_text((20, 75), "visible overlay", fontsize=16)
        blocks = _text_blocks(page)
        result = annotate_page_ocr_spans(
            page,
            blocks,
            line_recognizer=lambda *_args: self.fail(
                "recognizer must not run for visible overlay text"
            ),
        )
        spans = [
            span
            for block in blocks
            if block["type"] == 0
            for line in block["lines"]
            for span in line["spans"]
            if span["text"].strip()
        ]
        self.assertEqual(result["nonstandard_status"], "no_candidate")
        self.assertTrue(all(span["is_ocr"] is False for span in spans))
        image_doc.close()
        doc.close()
