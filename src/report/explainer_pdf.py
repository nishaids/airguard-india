"""Render ``PROJECT_EXPLAINED.md`` as a typeset PDF.

The Markdown file stays the single source of truth for the words; this module
only decides how they look on paper. It converts the document to HTML, wraps it
in a print stylesheet (A4, a cover page, a contents page, and typography sized
for reading rather than for a screen), and prints it through headless Chrome so
the result matches what a browser would render.

Chrome is driven through Playwright when it is installed, and through
``chrome --headless --print-to-pdf`` otherwise, so the only hard requirement is
a Chrome or Edge installation.

Run with::

    python -m src.report.explainer_pdf
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from src import config

SOURCE = config.PROJECT_ROOT / "PROJECT_EXPLAINED.md"
OUTPUT = config.REPORTS_DIR / "AirGuard_India_Project_Explained.pdf"

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


# --------------------------------------------------------------------------- #
# Markdown -> HTML
# --------------------------------------------------------------------------- #
def _inline(text: str) -> str:
    """Render the inline span syntax, escaping everything else."""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"(?<!href=\")(?<!>)(https?://[^\s<)]+)", r'<a href="\1">\1</a>', out)
    return out


def _table(rows: List[str]) -> str:
    def cells(row: str) -> List[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    header = cells(rows[0])
    body = [cells(r) for r in rows[2:]]
    head_html = "".join(f"<th>{_inline(c)}</th>" for c in header)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>" for row in body
    )
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"


def markdown_to_html(text: str) -> str:
    lines = text.split("\n")
    out: List[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        if re.fullmatch(r"\s*(---|\*\*\*|___)\s*", line):
            out.append('<hr class="rule">')
            i += 1
            continue

        if line.lstrip().startswith("```"):
            i += 1
            code: List[str] = []
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre>" + html.escape("\n".join(code)) + "</pre>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        if line.startswith("|"):
            table: List[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                table.append(lines[i])
                i += 1
            out.append(_table(table))
            continue

        if line.lstrip().startswith(">"):
            quote: List[str] = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(quote))}</blockquote>")
            continue

        bullet = re.match(r"^(\s*)([-*]|\d+\.)\s+", line)
        if bullet:
            ordered = bool(re.match(r"^\s*\d+\.", line))
            items: List[str] = []
            while i < len(lines) and re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
                # fold continuation lines into the item
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                    items[-1] += " " + lines[i].strip()
                    i += 1
            tag = "ol" if ordered else "ul"
            body = "".join(f"<li>{_inline(item)}</li>" for item in items)
            out.append(f"<{tag}>{body}</{tag}>")
            continue

        para: List[str] = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|\||>|\s*([-*]|\d+\.)\s|\s*(---|\*\*\*|___)\s*$|```)", lines[i]
        ):
            para.append(lines[i])
            i += 1
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
        else:
            i += 1

    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Document assembly
# --------------------------------------------------------------------------- #
STYLE = """
@page {
  size: A4;
  margin: 19mm 17mm 21mm;
}
@page :first { margin: 0; }

:root {
  --ink: #16191f;
  --ink-soft: #3d434e;
  --ink-dim: #6b7280;
  --rule: #dfe3ea;
  --blue: #0072b2;
  --deep: #05306b;
  --green: #007a59;
  --orange: #b45309;
  --plum: #9d4d7c;
  --tint: #f4f7fb;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: "Inter", "Segoe UI", system-ui, sans-serif;
  font-size: 10.2pt;
  line-height: 1.58;
  color: var(--ink);
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

/* ---- Cover ------------------------------------------------------------- */
.cover {
  height: 297mm;
  padding: 0;
  page-break-after: always;
  display: flex;
  flex-direction: column;
  color: #fff;
  background: linear-gradient(150deg, #04234f 0%, #0a4f8f 46%, #1d7fb8 100%);
  position: relative;
  overflow: hidden;
}
.cover::after {
  content: "";
  position: absolute;
  right: -90mm; top: -70mm;
  width: 240mm; height: 240mm;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255,255,255,0.13), transparent 62%);
}
.cover-inner { padding: 30mm 22mm 0; position: relative; flex: 1; }
.cover .eyebrow {
  font-size: 8.4pt; letter-spacing: 0.22em; text-transform: uppercase;
  color: #a7d3f0; font-weight: 600; margin-bottom: 9mm;
}
.cover h1 {
  font-family: "Outfit", sans-serif;
  font-size: 40pt; line-height: 1.04; font-weight: 600;
  letter-spacing: -0.03em; margin: 0 0 6mm; color: #fff;
}
.cover .sub {
  font-size: 13pt; line-height: 1.45; color: #d6e8f7;
  font-weight: 400; max-width: 135mm; margin: 0 0 14mm;
}
.cover .pills { display: flex; gap: 4mm; flex-wrap: wrap; margin-bottom: 16mm; }
.cover .pill {
  border: 1px solid rgba(255,255,255,0.4); border-radius: 40px;
  padding: 1.6mm 5mm; font-size: 8.6pt; font-weight: 500; color: #eaf4fc;
}
.cover-meta {
  position: relative; margin-top: auto;
  background: rgba(0,0,0,0.22); padding: 12mm 22mm;
  border-top: 1px solid rgba(255,255,255,0.18);
}
.cover-meta table { width: 100%; border: none; font-size: 9.4pt; margin: 0; }
/* The cover's metadata grid is a table, so it must opt out of the body table
   styling below -- otherwise the zebra striping paints bars across the cover. */
.cover-meta tbody tr, .cover-meta tbody tr:nth-child(even) { background: transparent; }
.cover-meta td, .cover-meta tbody td {
  border: none; border-bottom: none; padding: 1.6mm 0;
  color: #d6e8f7; vertical-align: top; font-weight: 400;
}
.cover-meta td:first-child {
  width: 34mm; color: #8fc3e8; font-size: 8.2pt; text-transform: uppercase;
  letter-spacing: 0.1em; font-weight: 600; padding-top: 2.1mm;
}
.cover-meta strong { color: #fff; font-weight: 600; }
.cover-meta a { color: #bfe0f7; text-decoration: none; }

/* ---- Contents ---------------------------------------------------------- */
.toc { page-break-after: always; padding-top: 4mm; }
.toc h2 {
  font-size: 15pt; margin: 0 0 7mm; padding: 0 0 3mm;
  border-bottom: 2px solid var(--blue); color: var(--deep);
}
.toc ol { list-style: none; counter-reset: toc; padding: 0; margin: 0; }
.toc li {
  counter-increment: toc; padding: 2.6mm 0;
  border-bottom: 1px solid var(--rule); font-size: 10.6pt;
}
.toc li::before {
  content: counter(toc) ".";
  display: inline-block; width: 9mm; color: var(--blue); font-weight: 700;
}
.toc li span { color: var(--ink-dim); font-size: 9.2pt; display: block; margin-left: 9mm; }

/* ---- Body -------------------------------------------------------------- */
h1, h2, h3, h4 {
  font-family: "Outfit", "Segoe UI", sans-serif;
  color: var(--deep); font-weight: 600; letter-spacing: -0.015em;
  page-break-after: avoid; break-after: avoid;
}
h2 {
  font-size: 16pt; margin: 0 0 5mm; padding-bottom: 2.6mm;
  border-bottom: 2px solid var(--blue); page-break-before: always;
}
h2:first-of-type { page-break-before: avoid; }
h3 {
  font-size: 11.6pt; margin: 7mm 0 2.5mm; color: var(--blue);
}
h4 { font-size: 10.4pt; margin: 5mm 0 2mm; }

p { margin: 0 0 3.2mm; color: var(--ink-soft); orphans: 3; widows: 3; }
strong { color: var(--ink); font-weight: 600; }

a { color: var(--blue); text-decoration: none; }

ul, ol { margin: 0 0 3.6mm; padding-left: 6.5mm; color: var(--ink-soft); }
li { margin-bottom: 1.5mm; }
li::marker { color: var(--blue); }

code {
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 8.8pt; background: var(--tint); border: 1px solid var(--rule);
  border-radius: 3px; padding: 0.3mm 1.2mm; color: var(--deep);
}

pre {
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 8.4pt; line-height: 1.5; background: var(--tint);
  border: 1px solid var(--rule); border-left: 3px solid var(--blue);
  border-radius: 4px; padding: 3mm 4mm; overflow-wrap: anywhere;
  white-space: pre-wrap; page-break-inside: avoid; margin: 0 0 4mm;
}

blockquote {
  margin: 4mm 0; padding: 3.4mm 5mm;
  background: #fff8e8; border-left: 3px solid var(--orange);
  border-radius: 0 4px 4px 0; color: #4a3a1c;
  font-size: 9.8pt; page-break-inside: avoid;
}

hr.rule { border: none; border-top: 1px solid var(--rule); margin: 7mm 0; }

/* ---- Tables ------------------------------------------------------------ */
table {
  width: 100%; border-collapse: collapse; margin: 3mm 0 5mm;
  font-size: 9pt; page-break-inside: avoid;
}
thead th {
  background: var(--deep); color: #fff; text-align: left;
  padding: 2.2mm 3mm; font-weight: 600; font-size: 8.4pt;
  letter-spacing: 0.04em; text-transform: uppercase;
}
tbody td {
  padding: 2.1mm 3mm; border-bottom: 1px solid var(--rule);
  color: var(--ink-soft); vertical-align: top;
}
tbody tr:nth-child(even) { background: #f8fafc; }
tbody td:first-child { color: var(--ink); font-weight: 500; }
"""

GOOGLE_FONTS_CSS = (
    "https://fonts.googleapis.com/css2?"
    "family=Outfit:wght@500;600;700&"
    "family=Inter:wght@400;500;600&"
    "family=JetBrains+Mono:wght@400&display=swap"
)

FONT_CACHE = config.REPORTS_DIR / ".fontcache"

#: Stacks used when the fonts cannot be fetched and cached. The document still
#: typesets correctly, just in the reader's system faces.
FONT_FALLBACK = "<style>/* embedded fonts unavailable; using system faces */</style>"


def _embedded_font_css() -> str:
    """Return an @font-face block with the fonts inlined as data URIs.

    Headless Chrome fetching webfonts mid-print is the one step in this whole
    pipeline that depends on the network, and it is flaky: a slow response makes
    ``Page.printToPDF`` fail outright. Inlining the files removes that
    dependency, so the PDF renders identically offline and every run produces
    the same document. The files are cached after the first fetch.
    """
    import base64

    FONT_CACHE.mkdir(parents=True, exist_ok=True)
    css_cache = FONT_CACHE / "fonts.css"

    if css_cache.exists():
        return f"<style>{css_cache.read_text(encoding='utf-8')}</style>"

    try:
        import requests

        headers = {
            # A modern UA makes Google return woff2 rather than legacy formats.
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        }
        css = requests.get(GOOGLE_FONTS_CSS, headers=headers, timeout=30).text

        for url in sorted(set(re.findall(r"url\((https://[^)]+\.woff2)\)", css))):
            data = requests.get(url, headers=headers, timeout=30).content
            encoded = base64.b64encode(data).decode("ascii")
            css = css.replace(url, f"data:font/woff2;base64,{encoded}")

        css_cache.write_text(css, encoding="utf-8")
        return f"<style>{css}</style>"
    except Exception as exc:  # noqa: BLE001 - the document must still render
        print(f"  Could not embed webfonts ({exc}); falling back to system faces.")
        return FONT_FALLBACK


FONTS = ""  # populated per build by build_html()


def _cover(deployment_url: str) -> str:
    academic = config.ACADEMIC
    team = " · ".join(
        f"{member['name']} ({member['register_no']})"
        for member in config.TEAM
        if "<" not in member["name"]
    )
    return f"""
<section class="cover">
  <div class="cover-inner">
    <div class="eyebrow">Principles of Data Science &middot; Project Report</div>
    <h1>AirGuard India</h1>
    <p class="sub">{html.escape(academic['project_subtitle'])}</p>
    <div class="pills">
      <span class="pill">7 population cohorts</span>
      <span class="pill">12 cities</span>
      <span class="pill">18,395 city-days</span>
      <span class="pill">3 ML paradigms</span>
    </div>
  </div>
  <div class="cover-meta">
    <table>
      <tr><td>Course</td><td><strong>{academic['course_code']} &mdash; {academic['course_name']}</strong></td></tr>
      <tr><td>Programme</td><td>{academic['degree_branch']} &middot; Semester {academic['semester']}</td></tr>
      <tr><td>Institution</td><td>{academic['institution']}</td></tr>
      {f'<tr><td>Team</td><td>{html.escape(team)}</td></tr>' if team else ''}
      <tr><td>Live app</td><td><a href="{deployment_url}">{deployment_url}</a></td></tr>
      <tr><td>Repository</td><td><a href="{config.REPO_URL}">{config.REPO_URL}</a></td></tr>
    </table>
  </div>
</section>
"""


def _contents(sections: List[str]) -> str:
    items = "".join(f"<li>{html.escape(title)}</li>" for title in sections)
    return f'<section class="toc"><h2>Contents</h2><ol>{items}</ol></section>'


def build_html(deployment_url: str) -> str:
    text = SOURCE.read_text(encoding="utf-8")

    # Drop the source file's own title block: the cover page replaces it.
    body_start = text.index("## 1.")
    body_md = text[body_start:]

    sections = [
        re.sub(r"^\d+\.\s*", "", m.group(1)).strip()
        for m in re.finditer(r"^##\s+(.*)$", body_md, flags=re.MULTILINE)
    ]

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>AirGuard India — Project Explained</title>
{_embedded_font_css()}
<style>{STYLE}</style>
</head><body>
{_cover(deployment_url)}
{_contents(sections)}
{markdown_to_html(body_md)}
</body></html>"""


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _find_chrome() -> Optional[str]:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _stamp_footers(pdf_path: Path) -> None:
    """Draw a running footer on every page except the cover.

    Chrome's ``--print-to-pdf`` either omits the footer entirely or prints its
    own (which includes the temporary ``file://`` path), and driving Chrome
    through Playwright to get a custom one proved unreliable here. Stamping the
    footer afterwards is deterministic and keeps the renderer to a single,
    fast code path.
    """
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    writer = PdfWriter()

    for index, page in enumerate(reader.pages):
        if index > 0:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            buffer = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            buffer.close()
            overlay = canvas.Canvas(buffer.name, pagesize=(width, height))
            overlay.setFont("Helvetica", 7.5)
            overlay.setFillColor(HexColor("#8b93a1"))
            margin = 48.0
            baseline = 30.0
            overlay.drawString(margin, baseline, "AirGuard India — Project Explained")
            overlay.drawRightString(width - margin, baseline, f"{index} / {total - 1}")
            overlay.setStrokeColor(HexColor("#e3e7ee"))
            overlay.setLineWidth(0.5)
            overlay.line(margin, baseline + 11, width - margin, baseline + 11)
            overlay.save()

            stamp = PdfReader(buffer.name).pages[0]
            page.merge_page(stamp)
            Path(buffer.name).unlink(missing_ok=True)

        writer.add_page(page)

    with pdf_path.open("wb") as handle:
        writer.write(handle)


def _render_chrome_cli(html_path: Path) -> bool:
    chrome = _find_chrome()
    if not chrome:
        return False
    # A throwaway profile: reusing the user's can block on an existing lock and
    # hang until the timeout.
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--no-pdf-header-footer",
                f"--print-to-pdf={OUTPUT}",
                "--virtual-time-budget=8000",
                html_path.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    return OUTPUT.exists()


def main() -> Path:
    config.ensure_dirs()

    deployment = config.RESULTS_DIR / "deployment.json"
    url = "https://webapp-phi-taupe.vercel.app"
    if deployment.exists():
        import json

        url = json.loads(deployment.read_text(encoding="utf-8")).get("url", url)

    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "explainer.html"
        html_path.write_text(build_html(url), encoding="utf-8")

        if not _render_chrome_cli(html_path):
            raise RuntimeError(
                "No Chrome or Edge installation found. Install one, or open the "
                "generated HTML and print it to PDF manually."
            )

    _stamp_footers(OUTPUT)

    size_mb = OUTPUT.stat().st_size / 1e6
    print(f"Wrote {OUTPUT.relative_to(config.PROJECT_ROOT)} ({size_mb:.2f} MB)")
    return OUTPUT


if __name__ == "__main__":
    main()
