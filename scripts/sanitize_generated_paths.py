"""Rewrite local absolute paths already recorded in generated artefacts.

Only the path strings change. Hashes inside these files are hashes of file
contents, not of the JSON, so replacing a path string does not invalidate any
recorded measurement; nothing is recomputed and no value is reinterpreted.
Regenerating the legacy reports instead would need the 66 MB raw archive, so
this exists to repair artefacts whose inputs are no longer on hand.

Run with --check to report without writing.
"""
import argparse
import re
import sys

from src import config
from src.qa.paths import LEAK, TEXT_SUFFIXES, scan

# A quoted or bare path, Windows (escaped or single backslash) or POSIX home.
CANDIDATE = re.compile(
    r'(?:[A-Z]:(?:\\\\|\\|/)[^"\'\n,;|`)\]]*)'
    r'|(?:/Users/[^"\'\n,;|`)\]]*)'
    r'|(?:/home/[a-z][^"\'\n,;|`)\]]*)'
)


def portable_of(found: str) -> str:
    """Portable form of one matched path, preserving JSON escaping."""
    escaped = '\\\\' in found
    literal = found.replace('\\\\', '\\') if escaped else found
    value = config.portable(literal.rstrip('\\/ '))
    return value.replace('\\', '\\\\') if escaped else value


def rewrite(text: str):
    replacements = []

    def swap(match):
        found = match.group(0)
        value = portable_of(found)
        replacements.append((found, value))
        return value

    return CANDIDATE.sub(swap, text), replacements


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='report without writing')
    args = parser.parse_args()
    changed = {}
    for relative in scan():
        path = config.PROJECT_ROOT / relative
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding='utf-8')
        new, replacements = rewrite(text)
        if new == text:
            print(f'{relative}: matched the leak pattern but no path could be rewritten; fix by hand')
            continue
        if LEAK.search(new):
            print(f'{relative}: rewrite left a local path behind; fix by hand')
            continue
        changed[relative] = sorted({value for _found, value in replacements})
        if not args.check:
            path.write_text(new, encoding='utf-8')
    for relative, values in changed.items():
        print(f'{"would rewrite" if args.check else "rewrote"} {relative}: {", ".join(values)}')
    if not changed:
        print('Nothing to rewrite.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
