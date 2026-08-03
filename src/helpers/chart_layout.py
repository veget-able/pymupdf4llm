"""Chart extraction hook for the layout pipeline.

Fills the .chart payload of picture boxes with tabular chart data
produced by a chart extraction callback. to_markdown() / to_json()
invoke this right after parse_document() when chart_function is given -
without it the layout output is unchanged.

Chart boxes stay picture-class layout boxes at their detected
coordinates and no other box is removed or moved: visual-grounding
consumers see the same layout with or without chart extraction, and a
failed extraction simply leaves the original content in place. The
serializers render the payload alongside the picture content - as a
fenced "chart table" block in Markdown, as a chart object (with CSV)
in JSON.

Candidate boxes are the pictures flagged by chart detection when
parse_document(detect_charts=...) ran, and all picture boxes otherwise
(or with chart_region="picture"). Custom detectors plug in at the
parse stage via detect_charts=<callable>.

The extraction callback contract mirrors ocr_function:

    chart_function(crop_paths: list[Path]) -> list[str]

one Markdown table per crop image, in order. Failures degrade
losslessly by default and are recorded in chart_diagnostics (and
logged); pass chart_strict=True to re-raise instead.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import pymupdf

# Diagnostics go through logging rather than print on purpose: extraction
# failures must be visible by default yet silenceable per consumer, which
# the parser's print-based messaging cannot offer.
_log = logging.getLogger("pymupdf4llm.chart")

ZOOM = 2.0  # default crop render scale


def _is_sep_row(line: str) -> bool:
    return set(line.replace("|", "").replace(" ", "")) <= {"-", ":"} and "-" in line


def pipe_to_csv(md: str) -> str:
    """Convert a pipe Markdown table to CSV text (separator row dropped)."""
    import csv
    import io

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for line in md.splitlines():
        line = line.strip()
        if not line or "|" not in line or _is_sep_row(line):
            continue
        writer.writerow([c.strip() for c in line.strip("|").split("|")])
    return out.getvalue().rstrip("\n")


def _diagnostic(
    diagnostics: list[dict[str, Any]],
    *,
    level: str,
    stage: str,
    error: Exception,
    page_number: int | None = None,
    crop: Path | None = None,
) -> None:
    record: dict[str, Any] = {
        "level": level,
        "stage": stage,
        "error_type": type(error).__name__,
        "message": str(error),
    }
    if page_number is not None:
        record["page_number"] = page_number
    if crop is not None:
        record["crop"] = str(crop)
    diagnostics.append(record)
    _log.warning(
        "chart extraction %s [%s]%s - %s: %s",
        level,
        stage,
        f" (page {page_number})" if page_number is not None else "",
        record["error_type"],
        record["message"],
    )


def _chart_tables_safe(
    chart_function,
    crops,
    *,
    strict: bool,
    diagnostics: list[dict[str, Any]],
    page_number: int,
) -> list:
    """Run the extraction callback with per-crop failure isolation.

    The batch call is the normal path. If it raises, each crop is
    retried individually so one bad crop cannot take down the page:
    failed crops yield None (their boxes keep the original content). The
    returned list always has len(crops) entries.
    """
    try:
        out = chart_function(crops)
        return [out[i] if i < len(out) else None for i in range(len(crops))]
    except Exception as exc:  # degrade losslessly, then isolate per crop
        if strict:
            raise
        _diagnostic(
            diagnostics,
            level="warning",
            stage="chart_batch",
            error=exc,
            page_number=page_number,
        )
        tables = []
        for cp in crops:
            try:
                one = chart_function([cp])
                tables.append(one[0] if one else None)
            except Exception as exc:  # skip this crop only
                _diagnostic(
                    diagnostics,
                    level="error",
                    stage="chart_crop",
                    error=exc,
                    page_number=page_number,
                    crop=cp,
                )
                tables.append(None)
        return tables


def _flagged_boxes(page) -> list:
    return [
        b
        for b in page.boxes
        if b.boxclass == "picture" and b.chart is not None
    ]


def _picture_candidates(page) -> list:
    """All non-degenerate picture boxes.

    Degenerate boxes (width or height < 1 pt) are dropped: the parser
    occasionally emits ghost boxes like [0, 0, 0, 0] which would yield
    empty crops or zero-dimension pixmaps whose PNG export raises.
    """
    return [
        b
        for b in page.boxes
        if b.boxclass == "picture" and (b.x1 - b.x0) >= 1.0 and (b.y1 - b.y0) >= 1.0
    ]


def splice_charts_into_parsed(
    parsed,
    source_pdf: Path | str | pymupdf.Document,
    chart_function: Callable[..., list[str]],
    workdir: Path,
    *,
    zoom: float | None = None,
    region_source: str | None = None,
    strict: bool = False,
    diagnostics: list[dict[str, Any]] | None = None,
) -> None:
    """Fill the .chart payload of chart picture boxes of 'parsed' (in place).

    Call between parse_document() and serialization. 'workdir' receives
    the temporary crop images handed to chart_function.

    region_source: None for automatic - the detection-flagged boxes when
    parse_document(detect_charts=...) ran, all picture boxes otherwise;
    "picture" forces all picture boxes.
    """
    if chart_function is None:
        raise ValueError("chart_function is required")
    if region_source not in (None, "picture"):
        raise ValueError(
            f"unknown chart_region={region_source!r} - only 'picture' is valid"
        )
    if zoom is None:
        zoom = ZOOM

    if isinstance(source_pdf, pymupdf.Document):
        if source_pdf.is_closed:
            raise ValueError("source PDF document is closed")
        src = source_pdf
        owns_source = False
    else:
        src = pymupdf.open(source_pdf)
        owns_source = True
    if diagnostics is None:
        diagnostics = []
    # Trust the parse stage: when detection ran there, its flags are the
    # candidate set - even when it found nothing. Falling back to "all
    # pictures" here would hand every image on chartless documents to the
    # extraction model.
    use_flagged = region_source != "picture" and parsed.detect_charts
    try:
        for page in parsed.pages:
            candidates = (
                _flagged_boxes(page) if use_flagged else _picture_candidates(page)
            )
            if not candidates:
                continue

            # Crop from the source page; parse coordinates are derotated,
            # so rotated pages are copied into memory and derotated first
            # (the common non-rotated case renders with no copy at all).
            src_page = src[page.page_number - 1]  # page_number is 1-based
            copy_doc = None
            try:
                if src_page.rotation:
                    copy_doc = pymupdf.open()
                    copy_doc.insert_pdf(
                        src,
                        from_page=src_page.number,
                        to_page=src_page.number,
                    )
                    work_page = copy_doc[0]
                    work_page.remove_rotation()
                else:
                    work_page = src_page

                det_rects = [
                    pymupdf.Rect(c.chart["bbox"])
                    for c in candidates
                    if c.chart is not None and c.chart.get("bbox")
                ]
                crops, order = [], []
                for k, b in enumerate(candidates):
                    clip = pymupdf.Rect(b.x0, b.y0, b.x1, b.y1)
                    # A parser picture box and the chart detection often
                    # disagree slightly; crop their union so the extraction
                    # model sees both the detected chart area and whatever
                    # context (title, caption) the picture box adds. The
                    # layout box itself stays untouched.
                    det = (b.chart or {}).get("bbox")
                    if det:
                        det = pymupdf.Rect(det)
                        clip |= det
                        # A wide parser box can drag the crop across a
                        # neighboring chart; a crop containing two charts
                        # degrades the extraction model, so fall back to the
                        # detection box alone when the crop swallows a
                        # meaningful part of another detection.
                        if any(
                            other != det
                            and (clip & other).get_area() > 0.1 * other.get_area()
                            for other in det_rects
                        ):
                            clip = det
                    clip &= work_page.rect
                    # Parsers occasionally emit boxes outside the page
                    # (observed: y 521..703 on a 482 pt page). Such clips
                    # produce zero-height pixmaps whose PNG export raises
                    # and would fail the whole document.
                    if clip.is_empty:
                        _diagnostic(
                            diagnostics,
                            level="warning",
                            stage="chart_crop",
                            error=ValueError(f"box outside page: {b}"),
                            page_number=page.page_number,
                        )
                        continue
                    cp = workdir / f"p{page.page_number}_c{k}.png"
                    work_page.get_pixmap(
                        matrix=pymupdf.Matrix(zoom, zoom),
                        clip=clip,
                    ).save(str(cp))
                    crops.append(cp)
                    order.append(b)
            finally:
                if copy_doc is not None:
                    copy_doc.close()

            tables = _chart_tables_safe(
                chart_function,
                crops,
                strict=strict,
                diagnostics=diagnostics,
                page_number=page.page_number,
            )
            for b, md in zip(order, tables):
                if not md:
                    continue  # failed crop - box keeps its original content
                payload = dict(b.chart or {})
                payload["markdown"] = md
                # CSV is part of the JSON output contract for charts, so
                # it is materialized here rather than derived by readers.
                payload["csv"] = pipe_to_csv(md)
                b.chart = payload
    finally:
        if owns_source:
            src.close()
