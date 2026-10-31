"""Run the integration test profile without repository install hooks.

The current Python must already import the paired integration sources. This
command does not build/install packages. Pass --core-repo for paired CropBox
checks. Independent feature test files also contain mutually exclusive
standalone assertions; integration_profile.json documents their replacements.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-repo', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    profile = json.loads((repo/'tests/integration_profile.json').read_text())
    tests = [str(repo/item) for item in profile['tests']]
    if args.core_repo:
        tests.extend(str(args.core_repo.resolve()/item) for item in profile['paired_core_tests'])
    subprocess.run([sys.executable, '-m', 'pytest', '--noconftest', '-q',
                    '-p', 'no:cacheprovider', *tests], cwd=repo, check=True)


if __name__ == '__main__':
    main()
