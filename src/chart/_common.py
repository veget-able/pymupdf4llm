"""Shared helpers for chart_function callbacks (pure functions, no heavy deps)."""

from __future__ import annotations

import re

_DEVICE = None
_DTYPE = None


def resolve_device():
    """Device and dtype for chart models - cuda > mps, CPU excluded.

    - cuda: bfloat16.
    - mps: float32 - VLMs risk NaN in fp16 and the bfloat16 coverage of
      mps is incomplete, so float32 is the safe choice.
    - neither: RuntimeError. CPU inference is deliberately unsupported -
      per-crop generation times would be impractical.

    The result is cached per process.
    """
    global _DEVICE, _DTYPE
    if _DEVICE is None:
        import torch

        if torch.cuda.is_available():
            _DEVICE, _DTYPE = "cuda", torch.bfloat16
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            _DEVICE, _DTYPE = "mps", torch.float32
        else:
            raise RuntimeError(
                "chart models need CUDA or MPS (CPU is not supported)."
            )
    return _DEVICE, _DTYPE


def _row_cells(row: str) -> list[str]:
    return row.strip().strip("|").split("|")


def fix_header(md: str) -> str:
    """Restore the missing top-left corner cell of matrix-style tables.

    Some chart models drop the corner cell, leaving the header (and the
    separator row) one column short of the widest data row. If header or
    separator are exactly one cell short, prepend an empty leading cell.
    Data rows are never modified.
    """
    out: list[str] = []
    block: list[str] = []

    def flush() -> None:
        nonlocal block
        if len(block) >= 2:
            maxc = max(len(_row_cells(r)) for r in block)
            for i in range(min(2, len(block))):  # header and separator only
                if len(_row_cells(block[i])) == maxc - 1:
                    block[i] = "| " + block[i].lstrip()
        out.extend(block)
        block = []

    for line in md.split("\n"):
        if "|" in line:
            block.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


def _is_sep_row(line: str) -> bool:
    return set(line.replace("|", "").replace(" ", "")) <= {"-", ":"} and "-" in line


def pipe_normalize(text: str) -> str:
    """Normalize pipe-separated model output into a renderable table.

    Strips code fences, drops lines without a pipe, balances the outer
    pipes and inserts a separator row after the header if missing.
    """
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip()).strip()
    lines = [l for l in (line.strip() for line in t.splitlines()) if l and "|" in l]
    if not lines:
        return t

    def norm(l: str) -> str:
        return "| " + " | ".join(c.strip() for c in l.strip().strip("|").split("|")) + " |"

    rows = [norm(l) for l in lines]
    if len(rows) >= 2 and _is_sep_row(rows[1]):
        return "\n".join(rows)
    ncol = rows[0].count("|") - 1
    sep = "| " + " | ".join(["---"] * max(ncol, 1)) + " |"
    return "\n".join([rows[0], sep] + rows[1:])
