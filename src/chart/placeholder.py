"""Placeholder chart_function - a dependency-free stub, no real inference.

Verifies the detection/extraction plumbing without a GPU: one placeholder
table per crop image.
"""

from __future__ import annotations

from pathlib import Path


def placeholder(crop_paths: list[Path]) -> list[str]:
    return [
        f"| chart | value |\n| --- | --- |\n| _placeholder #{i}_ | {p.name} |"
        for i, p in enumerate(crop_paths, 1)
    ]
