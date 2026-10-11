"""CI guard: fail when a generated or published artefact names a local path.

Run it after any stage that writes artefacts. It reports and exits non-zero; it
never edits. `python -m scripts.sanitize_generated_paths` is the repair tool.
"""
import sys

from src.qa.paths import SCAN_ROOTS, scan


def main():
    hits = scan()
    if not hits:
        print(f'No local absolute path found under {", ".join(SCAN_ROOTS)}.')
        return 0
    print('Local absolute paths found in generated artefacts:')
    for path in hits:
        print(f'  {path}')
    print('Fix the writer so it uses src.config.portable, then run '
          'python -m scripts.sanitize_generated_paths for existing artefacts.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
