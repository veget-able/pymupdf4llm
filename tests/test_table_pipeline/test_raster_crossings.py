"""Crossing repair must keep long-rule evidence and preserve merged cells."""
import numpy as np
import pytest

from pymupdf4llm.helpers.table_html import raster_lines


@pytest.mark.parametrize("body,seed,expect_extension", [
    (True, True, True), (False, True, False), (True, False, False),
])
def test_vertical_fragments_join_only_at_existing_crossings(
        body, seed, expect_extension):
    pytest.importorskip("cv2")
    binary = np.zeros((240, 320), dtype=np.uint8)
    for y in (20, 100, 140, 180, 220):
        binary[y, 20:301] = 255
        # Scan-like discontinuities at intersections, tested through real
        # image gradients rather than mocking the replaced Canny stage.
        binary[y, 159:161] = 0
    binary[20:221, 20] = binary[20:221, 300] = 255
    if seed:
        binary[20:98, 160] = 255
    if body:
        for start, stop in ((103, 138), (143, 178), (183, 218)):
            binary[start:stop, 160] = 255
    gray = 255 - binary
    before = gray.copy()
    groups = raster_lines._detect_grid_components(
        gray, scale=150 / 72, table_rects=[(0, 0, 320, 240)])
    vertical = [line for _, lines in groups for line in lines
                if 155 < line[0] < 165]
    assert any(line[3] >= 218 for line in vertical) == expect_extension
    assert np.array_equal(gray, before)
    if not seed:
        assert not vertical


@pytest.mark.parametrize("background,ink", [(255, 0), (0, 255), (255, 230)])
def test_paired_edges_support_dark_bright_and_weak_rules(background, ink):
    pytest.importorskip("cv2")
    gray = np.full((240, 320), background, dtype=np.uint8)
    for y in (20, 100, 220):
        gray[y:y + 2, 20:302] = ink
    for x in (20, 160, 300):
        gray[20:222, x:x + 2] = ink
    before = gray.copy()
    groups = raster_lines._detect_grid_components(
        gray, scale=150 / 72, table_rects=[(0, 0, 320, 240)])
    assert len(groups) == 1
    horizontal, vertical = groups[0]
    assert len(horizontal) == len(vertical) == 3
    assert np.array_equal(gray, before)


@pytest.mark.parametrize("kind", ["blank", "wide_bands"])
def test_no_grid_in_blank_or_wide_filled_bands(kind):
    pytest.importorskip("cv2")
    gray = np.full((240, 320), 255, dtype=np.uint8)
    if kind == "wide_bands":
        for y in (20, 100, 180):
            gray[y:y + 30, 20:300] = 0
    assert raster_lines._detect_grid_components(
        gray, scale=150 / 72, table_rects=[(0, 0, 320, 240)]) == []
