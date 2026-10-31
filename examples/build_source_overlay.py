"""Expose the paired Python changes over compatible existing 2.0 native files.

This utility copies Python/model sources and links existing native artifacts;
it does not compile, install, download or publish a wheel. The native package
must match the draft-2.0 binding API. The tested native MuPDF version is 1.28.5.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-repo', type=Path, required=True)
    parser.add_argument('--native-package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    native = args.native_package.resolve()
    core = args.core_repo.resolve()/'src'
    llm = Path(__file__).resolve().parents[1]/'src'
    output = args.output.resolve()
    if output.exists():
        parser.error('Output must be a new directory')
    if not core.is_dir() or not (native/'__init__.py').is_file():
        parser.error('Expected core source and an existing pymupdf package directory')
    output.mkdir(parents=True)
    target = output/'pymupdf'
    target.mkdir()
    for old in native.iterdir():
        if old.name == '__pycache__':
            continue
        source = core/old.name
        dest = target/old.name
        if source.is_file() and source.suffix in ('.py', '.pyi'):
            shutil.copyfile(source, dest)
        else:
            dest.symlink_to(old.resolve(), target_is_directory=old.is_dir())
    shutil.copytree(llm, output/'pymupdf4llm', ignore=shutil.ignore_patterns('__pycache__'))
    (output/'pymupdf4llm/versions_file.py').write_text("VERSION = '2.0'\nVERSION_TUPLE = (2, 0)\n")
    sources = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in output.rglob('*.py') if '__pycache__' not in p.parts}
    (output/'source-overlay.json').write_text(json.dumps(dict(
        core_source=str(core), llm_source=str(llm), native_package=str(native),
        native_rebuilt=False, source_sha256=sources), indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
