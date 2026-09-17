"""Recover table ruling lines that exist only inside PDF raster images.

The table engine operates in PDF point coordinates and normally sees vector
drawings only.  This module renders raster-image occurrences, extracts
horizontal / vertical grid rules, validates that they form a text-bearing grid,
and returns virtual ``add_lines`` suitable for ``Page.find_tables``.

OpenCV is deliberately imported lazily.  It is available in the RapidOCR
pipeline, while non-OCR installations keep the previous behavior and simply
return no supplemental lines.
"""

from __future__ import annotations

from bisect import bisect_right

import numpy as np
import pymupdf


DEFAULT_DPI = 150
MIN_IMAGE_AREA_RATIO = 0.005
MIN_IMAGE_SIDE_PT = 24.0
MIN_RULE_LENGTH_PT = 24.0
MAX_RULE_THICKNESS_PT = 5.0
MIN_GRID_WORDS = 2
MAX_TEXT_OVERLAP = 0.8


def _image_regions(page: pymupdf.Page) -> list[pymupdf.Rect]:
    """Return deduplicated, non-trivial raster-image occurrence rectangles."""
    page_rect = pymupdf.Rect(page.rect)
    page_area = max(1.0, float(page_rect.width * page_rect.height))
    regions = []
    seen = set()
    for info in page.get_image_info(hashes=False, xrefs=False):
        try:
            rect = pymupdf.Rect(info["bbox"]) & page_rect
        except (KeyError, TypeError, ValueError):
            continue
        if rect.is_empty:
            continue
        if rect.width < MIN_IMAGE_SIDE_PT or rect.height < MIN_IMAGE_SIDE_PT:
            continue
        if rect.width * rect.height < page_area * MIN_IMAGE_AREA_RATIO:
            continue
        key = tuple(round(float(value), 1) for value in rect)
        if key in seen:
            continue
        seen.add(key)
        regions.append(rect)
    return regions


def _segments_from_mask(mask, orientation, *, min_length, max_thickness):
    """Extract axis-aligned segments from an OpenCV binary morphology mask."""
    import cv2

    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
    segments = []
    for index in range(1, count):
        x, y, width, height, _area = (int(value) for value in stats[index])
        if orientation == "h":
            if width < min_length or height > max_thickness:
                continue
            segments.append((float(x), y + height / 2.0, float(x + width), y + height / 2.0))
        else:
            if height < min_length or width > max_thickness:
                continue
            segments.append((x + width / 2.0, float(y), x + width / 2.0, float(y + height)))
    return segments


def _merge_segments(segments, orientation, *, coordinate_tolerance, gap_tolerance):
    """Merge scan fragments that are collinear and separated by a small gap."""
    if orientation == "h":
        ordered = sorted(segments, key=lambda line: (line[1], line[0], line[2]))
    else:
        ordered = sorted(segments, key=lambda line: (line[0], line[1], line[3]))
    merged = []
    for line in ordered:
        did_merge = False
        for index in range(len(merged) - 1, -1, -1):
            old = merged[index]
            if orientation == "h":
                coordinate_delta = line[1] - old[1]
                if coordinate_delta > coordinate_tolerance:
                    break
                if (
                    abs(coordinate_delta) <= coordinate_tolerance
                    and line[0] <= old[2] + gap_tolerance
                    and line[2] >= old[0] - gap_tolerance
                ):
                    y = (old[1] + line[1]) / 2.0
                    merged[index] = (min(old[0], line[0]), y, max(old[2], line[2]), y)
                    did_merge = True
                    break
            else:
                coordinate_delta = line[0] - old[0]
                if coordinate_delta > coordinate_tolerance:
                    break
                if (
                    abs(coordinate_delta) <= coordinate_tolerance
                    and line[1] <= old[3] + gap_tolerance
                    and line[3] >= old[1] - gap_tolerance
                ):
                    x = (old[0] + line[0]) / 2.0
                    merged[index] = (x, min(old[1], line[1]), x, max(old[3], line[3]))
                    did_merge = True
                    break
        if not did_merge:
            merged.append(line)
    return merged


def _line_components(horizontal, vertical, *, tolerance):
    """Return intersecting bipartite line components that can enclose cells."""
    line_count = len(horizontal) + len(vertical)
    parents = list(range(line_count))
    intersects = [False] * line_count

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left, right):
        left = find(left)
        right = find(right)
        if left != right:
            parents[right] = left

    for h_index, h_line in enumerate(horizontal):
        hx0, hy, hx1, _ = h_line
        for v_index, v_line in enumerate(vertical):
            vx, vy0, _, vy1 = v_line
            if hx0 - tolerance <= vx <= hx1 + tolerance and vy0 - tolerance <= hy <= vy1 + tolerance:
                full_v_index = len(horizontal) + v_index
                intersects[h_index] = True
                intersects[full_v_index] = True
                union(h_index, full_v_index)

    groups = {}
    for index, has_intersection in enumerate(intersects):
        if has_intersection:
            groups.setdefault(find(index), []).append(index)

    components = []
    for indexes in groups.values():
        h_lines = [horizontal[index] for index in indexes if index < len(horizontal)]
        v_lines = [vertical[index - len(horizontal)] for index in indexes if index >= len(horizontal)]
        # Two rules in each direction enclose one box. A table needs at least
        # one additional rule in either direction, hence at least two cells.
        if len(h_lines) >= 2 and len(v_lines) >= 2 and (len(h_lines) >= 3 or len(v_lines) >= 3):
            components.append((h_lines, v_lines))
    return components


def _cluster_coordinates(values, tolerance):
    result = []
    for value in sorted(values):
        if result and value - result[-1] <= tolerance:
            result[-1] = (result[-1] + value) / 2.0
        else:
            result.append(value)
    return result


def _line_text_overlap(line, words):
    """Fraction of a segment covered by OCR/native word rectangles."""
    x0, y0, x1, y1 = line
    horizontal = abs(y1 - y0) <= abs(x1 - x0)
    intervals = []
    if horizontal:
        length = x1 - x0
        for word in words:
            if float(word[1]) <= y0 <= float(word[3]):
                start = max(x0, float(word[0]))
                end = min(x1, float(word[2]))
                if end > start:
                    intervals.append((start, end))
    else:
        length = y1 - y0
        for word in words:
            if float(word[0]) <= x0 <= float(word[2]):
                start = max(y0, float(word[1]))
                end = min(y1, float(word[3]))
                if end > start:
                    intervals.append((start, end))
    if length <= 0 or not intervals:
        return 0.0
    covered = 0.0
    current_start, current_end = sorted(intervals)[0]
    for start, end in sorted(intervals)[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            covered += current_end - current_start
            current_start, current_end = start, end
    covered += current_end - current_start
    return covered / length


def _word_cell_count(component, words, *, tolerance):
    """Count distinct grid slots containing extracted native/OCR words."""
    horizontal, vertical = component
    xs = _cluster_coordinates([line[0] for line in vertical], tolerance)
    ys = _cluster_coordinates([line[1] for line in horizontal], tolerance)
    if len(xs) < 2 or len(ys) < 2:
        return 0, 0
    occupied = set()
    word_count = 0
    for word in words:
        center_x = (float(word[0]) + float(word[2])) / 2.0
        center_y = (float(word[1]) + float(word[3])) / 2.0
        col = bisect_right(xs, center_x) - 1
        row = bisect_right(ys, center_y) - 1
        if 0 <= col < len(xs) - 1 and 0 <= row < len(ys) - 1:
            word_count += 1
            occupied.add((row, col))
    return word_count, len(occupied)


def _component_bbox(component):
    horizontal, vertical = component
    return pymupdf.Rect(
        min(line[0] for line in horizontal),
        min(line[1] for line in vertical),
        max(line[2] for line in horizontal),
        max(line[3] for line in vertical),
    )


def _overlaps_layout_table(component, table_rects):
    bbox = _component_bbox(component)
    area = max(1.0, bbox.width * bbox.height)
    for table_rect in table_rects:
        overlap = bbox & table_rect
        if not overlap.is_empty and overlap.width * overlap.height / area >= 0.5:
            return True
    return False


def _detect_grid_components(gray, *, scale, words=(), table_rects=()):
    """Detect validated ruling-line components in one grayscale image crop.

    ``words`` and ``table_rects`` use crop pixel coordinates. Components need
    text in at least two cells, unless the layout model already classified at
    least half of the component as a table.
    """
    import cv2

    if gray.ndim != 2 or min(gray.shape) < 8:
        return []
    gray = np.ascontiguousarray(gray, dtype=np.uint8)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    # Work from luminance edges rather than a dark-pixel mask. Filled / banded
    # cells otherwise become large foreground blobs and swallow their vertical
    # borders during connected-component extraction.
    binary = cv2.Canny(blurred, 30, 120)
    min_length = max(12, int(round(MIN_RULE_LENGTH_PT * scale)))
    max_thickness = max(3, int(round(MAX_RULE_THICKNESS_PT * scale)))
    gap = max(2, int(round(1.5 * scale)))
    horizontal_mask = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (gap, 1)),
    )
    horizontal_mask = cv2.morphologyEx(
        horizontal_mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (min_length, 1)),
    )
    vertical_mask = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, gap)),
    )
    vertical_mask = cv2.morphologyEx(
        vertical_mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_length)),
    )
    # Scaled scans commonly turn one rule into a pair of Canny edges. Collapse
    # that pair without merging genuinely adjacent row/column rules.
    coordinate_tolerance = max(2.0, 2.5 * scale)
    gap_tolerance = max(3.0, 3.0 * scale)
    horizontal = _merge_segments(
        _segments_from_mask(
            horizontal_mask,
            "h",
            min_length=min_length,
            max_thickness=max_thickness,
        ),
        "h",
        coordinate_tolerance=coordinate_tolerance,
        gap_tolerance=gap_tolerance,
    )
    vertical = _merge_segments(
        _segments_from_mask(
            vertical_mask,
            "v",
            min_length=min_length,
            max_thickness=max_thickness,
        ),
        "v",
        coordinate_tolerance=coordinate_tolerance,
        gap_tolerance=gap_tolerance,
    )
    # Directional morphology can preserve aligned glyph strokes as apparent
    # rules. OCR word geometry distinguishes those from cell borders without
    # erasing legitimate lines that merely touch a word box.
    horizontal = [
        line for line in horizontal
        if _line_text_overlap(line, words) < MAX_TEXT_OVERLAP
    ]
    vertical = [
        line for line in vertical
        if _line_text_overlap(line, words) < MAX_TEXT_OVERLAP
    ]
    intersection_tolerance = max(3.0, 3.0 * scale)
    components = _line_components(
        horizontal,
        vertical,
        tolerance=intersection_tolerance,
    )
    accepted = []
    for component in components:
        word_count, occupied_cells = _word_cell_count(
            component,
            words,
            tolerance=coordinate_tolerance,
        )
        if (
            word_count >= MIN_GRID_WORDS
            and occupied_cells >= MIN_GRID_WORDS
        ) or _overlaps_layout_table(component, table_rects):
            accepted.append(component)
    return accepted


def _to_crop_pixels(rect, clip, scale):
    """Convert a page-space rectangle to coordinates local to a render crop."""
    return pymupdf.Rect(
        (rect.x0 - clip.x0) * scale,
        (rect.y0 - clip.y0) * scale,
        (rect.x1 - clip.x0) * scale,
        (rect.y1 - clip.y0) * scale,
    )


def _page_words(page):
    try:
        return list(page.get_text("words"))
    except Exception:
        return []


def _layout_table_rects(page):
    result = []
    for item in page.layout_information or []:
        if isinstance(item, dict):
            if item.get("class_name") == "table" and item.get("group_bbox"):
                result.append(pymupdf.Rect(item["group_bbox"][:4]))
        elif len(item) >= 5 and item[-1] == "table":
            result.append(pymupdf.Rect(item[:4]))
    return result


def detect_raster_table_lines(page: pymupdf.Page, *, dpi: int = DEFAULT_DPI) -> list[tuple]:
    """Return validated raster ruling lines in PDF point coordinates.

    The page is expected to be derotated and, for useful cell text, OCR should
    already have run. Results are cached on the Page for repeated serializers.
    """
    cache = getattr(page, "_pymupdf4llm_raster_table_lines", None)
    if isinstance(cache, dict) and cache.get("dpi") == dpi:
        return list(cache.get("lines") or [])
    try:
        import cv2  # noqa: F401 -- optional, provided by the RapidOCR profile
    except ImportError:
        return []

    scale = float(dpi) / 72.0
    matrix = pymupdf.Matrix(scale, scale)
    inverse = ~matrix
    page_words = _page_words(page)
    layout_tables = _layout_table_rects(page)
    # Use pre-OCR pixels only for ruling detection. Text/layout support must
    # still come from the live page above; never alter its rendering or nodes.
    ruling_image = getattr(page, "_pymupdf4llm_ruling_displaylist", page)
    lines = []
    seen = set()
    for clip in _image_regions(page):
        pix = ruling_image.get_pixmap(
            matrix=matrix,
            clip=clip,
            colorspace=pymupdf.csGRAY,
            alpha=False,
        )
        if not pix.width or not pix.height:
            continue
        gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        words = [
            tuple(_to_crop_pixels(pymupdf.Rect(word[:4]), clip, scale)) + tuple(word[4:])
            for word in page_words
            if not (pymupdf.Rect(word[:4]) & clip).is_empty
        ]
        table_rects = [
            _to_crop_pixels(rect & clip, clip, scale)
            for rect in layout_tables
            if not (rect & clip).is_empty
        ]
        components = _detect_grid_components(
            gray,
            scale=scale,
            words=words,
            table_rects=table_rects,
        )
        for horizontal, vertical in components:
            for x0, y0, x1, y1 in horizontal + vertical:
                start = pymupdf.Point(pix.x + x0, pix.y + y0) * inverse
                end = pymupdf.Point(pix.x + x1, pix.y + y1) * inverse
                line = ((float(start.x), float(start.y)), (float(end.x), float(end.y)))
                key = tuple(round(value * 2.0) for point in line for value in point)
                if key not in seen:
                    seen.add(key)
                    lines.append(line)
    try:
        page._pymupdf4llm_raster_table_lines = {"dpi": dpi, "lines": lines}
    except Exception:
        pass
    return lines


__all__ = ["detect_raster_table_lines"]
