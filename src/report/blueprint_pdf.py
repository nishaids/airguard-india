"""Typeset the AirGuard 2.0 evidence and blueprint as one PDF.

The Markdown files in ``docs/airguard2/`` are the source of truth. This module
stitches them in order, resolves ``{{include:...}}`` directives (used for the
tables generated from the prior-art corpus), sets ``:::landscape`` blocks on
landscape pages so the wide comparison matrices stay legible, and prints the
result with the same renderer as the project explainer.

Run with::

    python -m src.research.prior_art_tables   # refresh generated tables first
    python -m src.report.blueprint_pdf
"""

from __future__ import annotations

import html
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import List

from src import config
from src.report.explainer_pdf import (
    STYLE,
    _embedded_font_css,
    _render_chrome_cli,
    _stamp_footers,
    markdown_to_html,
)

DOCS = config.PROJECT_ROOT / "docs" / "airguard2"
OUTPUT = config.REPORTS_DIR / "AirGuard2_Evidence_and_Blueprint.pdf"
PARTS = [
    "00_summary.md",
    "01_evidence.md",
    "02_research_design.md",
    "03_platform.md",
    "04_product.md",
    "05_program.md",
]

EXTRA_STYLE = """
@page wide { size: A4 landscape; margin: 14mm 12mm 17mm; }
section.landscape { page: wide; page-break-before: always; page-break-after: always; }

h1 {
  font-size: 21pt; margin: 0 0 6mm; padding-bottom: 3mm;
  border-bottom: 3px solid var(--blue); page-break-before: always;
}
h2 { font-size: 14.5pt; margin: 9mm 0 4mm; page-break-before: auto; }
h3 { font-size: 11pt; }

/* Long tables must be allowed to break across pages, with the header repeated. */
table { page-break-inside: auto; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }

table.wide { font-size: 7.7pt; }
table.wide thead th { font-size: 6.9pt; padding: 1.6mm 1.6mm; }
table.wide tbody td { padding: 1.4mm 1.6mm; }

table.xwide { font-size: 7pt; }
table.xwide thead th { font-size: 6.2pt; padding: 1.4mm 1mm; letter-spacing: 0; text-align: center; }
table.xwide thead th:nth-child(-n+4) { text-align: left; }
table.xwide tbody td { padding: 1.1mm 1mm; text-align: center; }
table.xwide tbody td:nth-child(-n+4) { text-align: left; }
table.xwide tbody td:nth-child(n+5) { font-size: 9pt; color: var(--deep); }

pre { font-size: 7.1pt; line-height: 1.45; }
blockquote { background: #f1f6fb; border-left-color: var(--blue); color: var(--ink); }
"""


def _resolve_includes(text: str) -> str:
    def repl(match: re.Match) -> str:
        return (DOCS / match.group(1)).read_text(encoding="utf-8")

    return re.sub(r"^\{\{include:([^}]+)\}\}\s*$", repl, text, flags=re.MULTILINE)


def _classify_tables(markup: str) -> str:
    def repl(match: re.Match) -> str:
        columns = match.group(0).split("</thead>")[0].count("<th>")
        cls = "xwide" if columns >= 14 else "wide" if columns >= 8 else ""
        return match.group(0).replace("<table>", f'<table class="{cls}">', 1) if cls else match.group(0)

    return re.sub(r"<table>.*?</table>", repl, markup, flags=re.DOTALL)


def _render_part(text: str) -> str:
    """Convert one Markdown part, honouring ``:::landscape`` blocks."""
    chunks: List[str] = []
    for index, piece in enumerate(re.split(r"^:::landscape\s*$|^:::\s*$", text, flags=re.MULTILINE)):
        if not piece.strip():
            continue
        body = _classify_tables(markdown_to_html(piece))
        chunks.append(f'<section class="landscape">{body}</section>' if index % 2 else body)
    return "\n".join(chunks)


def _cover() -> str:
    academic = config.ACADEMIC
    return f"""
<section class="cover">
  <div class="cover-inner">
    <div class="eyebrow">Audit &middot; Prior art &middot; Research design &middot; Blueprint</div>
    <h1 style="border:none;page-break-before:auto;font-size:40pt;color:#fff;margin:0 0 6mm;padding:0">AirGuard India 2.0</h1>
    <p class="sub">What the existing system does, what the rest of the field has already built,
    what is genuinely missing, and the experiments designed to test it.</p>
    <div class="pills">
      <span class="pill">47 external systems reviewed</span>
      <span class="pill">5 pilot experiments</span>
      <span class="pill">24 deliverables</span>
      <span class="pill">Nothing claimed without a source</span>
    </div>
  </div>
  <div class="cover-meta">
    <table>
      <tr><td>Status</td><td><strong>Evidence and design. No part of version 2.0 has been built.</strong></td></tr>
      <tr><td>Reviewed</td><td>{date.today().strftime('%d %B %Y')}</td></tr>
      <tr><td>Course</td><td>{academic['course_code']} &mdash; {academic['course_name']}</td></tr>
      <tr><td>Institution</td><td>{html.escape(academic['institution'])}</td></tr>
      <tr><td>Current system</td><td><a href="https://webapp-phi-taupe.vercel.app">https://webapp-phi-taupe.vercel.app</a></td></tr>
      <tr><td>Repository</td><td><a href="{config.REPO_URL}">{config.REPO_URL}</a></td></tr>
    </table>
  </div>
</section>
"""


CONTENTS = [
    ("Summary", "What was done, six findings, the gap that survives, and where each deliverable is"),
    ("Part 1 — Evidence", "Audit of the existing system · pilot experiments · 47-system prior-art corpus · gap matrix · hypothesis"),
    ("Part 2 — Research design", "Data sources as verified · benchmark · evaluation · the risk-controlled advisory · advisory index"),
    ("Part 3 — Platform architecture", "Batch-first architecture · API · database schema · MLOps · security"),
    ("Part 4 — Product and interface", "Interface specification · wireframes · design system · roadmap to a service · demonstration"),
    ("Part 5 — Programme", "Roadmap · paper outline · risks · limitations · acceptance criteria · decisions needed"),
]


def build_html() -> str:
    body = "\n".join(_render_part(_resolve_includes((DOCS / name).read_text(encoding="utf-8"))) for name in PARTS)
    items = "".join(f"<li>{html.escape(t)}<span>{html.escape(d)}</span></li>" for t, d in CONTENTS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>AirGuard India 2.0 — Evidence and Blueprint</title>
{_embedded_font_css()}
<style>{STYLE}{EXTRA_STYLE}</style>
</head><body>
{_cover()}
<section class="toc"><h2 style="margin-top:0">Contents</h2><ol>{items}</ol></section>
{body}
</body></html>"""


def main() -> Path:
    config.ensure_dirs()
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "blueprint.html"
        page.write_text(build_html(), encoding="utf-8")
        if not _render_chrome_cli(page, OUTPUT):
            raise RuntimeError("No Chrome or Edge installation found to print the PDF.")
    _stamp_footers(OUTPUT, "AirGuard India 2.0 — Evidence and Blueprint")
    print(f"Wrote {OUTPUT.relative_to(config.PROJECT_ROOT)} ({OUTPUT.stat().st_size / 1e6:.2f} MB)")
    return OUTPUT


if __name__ == "__main__":
    main()
