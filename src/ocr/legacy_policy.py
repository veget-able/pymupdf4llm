def legacy_existing_ocr_result(
    page, state, replace_ocr=False, ignore_existing_ocr=False, stats=None
):
    analysis = dict(state.analysis)
    if not analysis["ocr_spans"] or ignore_existing_ocr:
        return None
    if isinstance(stats, dict):
        stats["old_ocr"] = stats.get("old_ocr", 0) + 1
    if not replace_ocr:
        return {**analysis, "needs_ocr": False, "reason": None, "probability": None}
    import pymupdf

    for rect in state.ocr_span_boxes:
        page.add_redact_annot(rect)
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )
    return {**analysis, "needs_ocr": True, "reason": "ocr_spans", "probability": None}
