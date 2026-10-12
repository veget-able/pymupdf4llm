"""Dump pymupdf4llm.to_markdown() for the sample pages, to compare a fix
against the base outputs in expected_base/.

    python tests/repro_table_prs/dump_pages.py            # writes out/<name>.md
    python tests/repro_table_prs/dump_pages.py --out DIR  # another directory

Every page is converted with the default (layout) path. The pages listed in
LEGACY_PAGES are also converted with layout switched off (legacy path), as
<name>.legacy.md, because that is the path PR 469 changes.
Single process, no OCR options, so the output is reproducible.
"""
import argparse
import sys
from pathlib import Path

import pymupdf4llm

HERE = Path(__file__).parent
LEGACY_PAGES = {
    "BRWS-134565917_page839",
    "SERFF_TX_random_pages 1_page568",
    "SERFF_CA_random_pages 1_page756",
    "SERFF_Interstate_random_pages 1_page80",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--pages", default=str(HERE / "pages"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(Path(args.pages).glob("*.pdf"))
    for pdf in pdfs:
        md = pymupdf4llm.to_markdown(str(pdf), show_progress=False)
        (out / f"{pdf.stem}.md").write_text(md, encoding="utf-8")
        if pdf.stem in LEGACY_PAGES:
            previous = getattr(pymupdf4llm, "_use_layout", True)
            pymupdf4llm.use_layout(False)
            try:
                md = pymupdf4llm.to_markdown(str(pdf), show_progress=False)
            finally:
                pymupdf4llm.use_layout(previous)
            (out / f"{pdf.stem}.legacy.md").write_text(md, encoding="utf-8")
        print("ok", pdf.name, flush=True)
    print(f"{len(pdfs)} pages -> {out}")


if __name__ == "__main__":
    sys.exit(main())
