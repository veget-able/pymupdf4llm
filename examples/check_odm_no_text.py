"""Test this checkout over existing compatible draft-2.0 native artifacts.

No package installation/build/download. --core-repo selects paired Python
wrappers when the installed source version differs from the reviewed main.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-repo',type=Path)
    args=parser.parse_args()
    import pymupdf
    if not pymupdf.VersionBind.startswith('2.0'):
        parser.error('Use compatible PyMuPDF draft-2.0 native bindings')
    repo=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='ocr-odm-no-text-tests-')as td:
        root=Path(td)
        shutil.copytree(repo/'src',root/'pymupdf4llm',ignore=shutil.ignore_patterns('__pycache__'))
        (root/'pymupdf4llm/versions_file.py').write_text("VERSION='2.0'\nVERSION_TUPLE=(2,0)\n")
        if args.core_repo:
            original=Path(pymupdf.__file__).parent
            core=args.core_repo.resolve()/'src'
            if not(core/'__init__.py').is_file():parser.error('Expected --core-repo/src/__init__.py')
            target=root/'pymupdf';target.mkdir()
            for old in original.iterdir():
                if old.name=='__pycache__':continue
                source=core/old.name;dest=target/old.name
                if source.is_file()and source.suffix in ['.py','.pyi']:shutil.copyfile(source,dest)
                else:dest.symlink_to(old.resolve(),target_is_directory=old.is_dir())
        env={**os.environ,'PYTHONPATH':str(root)+os.pathsep+os.environ.get('PYTHONPATH',''),'PYTHONDONTWRITEBYTECODE':'1'}
        subprocess.run([sys.executable,'-m','pytest','--noconftest','-q','-p','no:cacheprovider',str(repo/'tests/test_odm_no_text.py')],env=env,check=True)


if __name__=='__main__':main()
