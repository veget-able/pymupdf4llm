"""Crossing repair must keep long-rule evidence and preserve merged cells."""
import numpy as np
import pytest

from pymupdf4llm.helpers.table_html import raster_lines


@pytest.mark.parametrize("body,seed,expect_extension", [
    (True, True, True), (False, True, False), (True, False, False),
])
def test_vertical_fragments_join_only_at_existing_crossings(
        monkeypatch, body, seed, expect_extension):
    cv2 = pytest.importorskip("cv2")
    binary = np.zeros((240, 320), dtype=np.uint8)
    for y in (20, 100, 140, 180, 220):
        binary[y, 20:301] = 255
        # Rounded Canny intersections: horizontal close can fill these two
        # pixels, but vertical close alone cannot bridge the intersection.
        binary[y, 159:161] = 0
    binary[20:221, 20] = binary[20:221, 300] = 255
    if seed:
        binary[20:98, 160] = 255
    if body:
        for start, stop in ((103, 138), (143, 178), (183, 218)):
            binary[start:stop, 160] = 255
    monkeypatch.setattr(cv2, "Canny", lambda *args: binary.copy())
    gray = np.full_like(binary, 255)
    before = gray.copy()
    groups = raster_lines._detect_grid_components(
        gray, scale=150 / 72, table_rects=[(0, 0, 320, 240)])
    vertical = [line for _, lines in groups for line in lines
                if 155 < line[0] < 165]
    assert any(line[3] >= 218 for line in vertical) == expect_extension
    assert np.array_equal(gray, before)
    if not seed:
        assert not vertical
