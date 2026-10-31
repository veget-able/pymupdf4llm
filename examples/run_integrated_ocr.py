"""Run the all-features evaluation branch using its paired PyMuPDF runtime.

Optional --selector p2-odm changes only the selection delegate for a comparison;
this is an example adapter, not a new public to_markdown parameter or OCRMode.
Verified Form input corrections require the explicit --input-rules manifest.
"""
import argparse
from pathlib import Path
import hashlib
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--selector', choices=['imf2-roi', 'p2-odm'], default='imf2-roi')
    parser.add_argument('--input-rules', type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve() == args.source.resolve():
        parser.error('Output must be a new file distinct from the input')

    import pymupdf
    import pymupdf4llm
    if args.selector == 'p2-odm':
        from pymupdf4llm.ocr import model_selector
        from pymupdf4llm.ocr.analyze_page import analyze_page
        model_selector.analyze_page = analyze_page

    data = args.source.read_bytes()
    repairs = []
    with pymupdf.open(stream=data, filetype='pdf') as document:
        if args.input_rules:
            from prepare_verified_ocr_input import prepare_document
            rules = json.loads(args.input_rules.read_text())['repairs']
            repairs = prepare_document(document, hashlib.sha256(data).hexdigest(), rules)
        markdown = pymupdf4llm.to_markdown(
            document, use_ocr=True, force_ocr=False, force_text=True,
            ocr_dpi=150, ocr_language='eng', page_chunks=False,
            show_progress=False, render_html_tables=None,
        )
    args.output.write_text(markdown, encoding='utf-8')
    print(json.dumps(dict(selector=args.selector, input_repairs=len(repairs),
                         output=str(args.output), pymupdf=pymupdf.__file__,
                         pymupdf4llm=pymupdf4llm.__file__), ensure_ascii=False))


if __name__ == '__main__':
    main()
