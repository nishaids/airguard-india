"""Render main.pdf to page images for visual inspection and report layout facts.

Usage: python scripts/render_pages.py [dpi]   (run inside paper/conference_final)
Outputs review/page_NN.png, review/overview.png and review/layout.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz
from PIL import Image

BASE = Path(__file__).resolve().parents[1]
dpi = int(sys.argv[1]) if len(sys.argv) > 1 else 110
out = BASE / 'review'
out.mkdir(exist_ok=True)
for stale in out.glob('page_*.png'):
    stale.unlink()
doc = fitz.open(BASE / 'main.pdf')
pages, layout = [], {'pages': len(doc), 'page_size_pt': [doc[0].rect.width, doc[0].rect.height], 'fonts': sorted({f[3] for p in doc for f in p.get_fonts()})}
for number, page in enumerate(doc, 1):
    path = out / f'page_{number:02d}.png'
    page.get_pixmap(dpi=dpi).save(path)
    pages.append(Image.open(path))
    blocks = [b for b in page.get_text('blocks') if b[4].strip()]
    mid = page.rect.width / 2
    left = [b for b in blocks if b[2] <= mid + 5]
    right = [b for b in blocks if b[0] >= mid - 5]
    layout[f'page_{number}'] = {'text_bottom_left_pt': round(max((b[3] for b in left), default=0), 1),
                                'text_bottom_right_pt': round(max((b[3] for b in right), default=0), 1),
                                'words': len(page.get_text('words'))}
last = doc[-1]
body_bottom = 841.89 - 72 * 1.0  # informative only
layout['last_page_right_column_fill'] = round((layout[f'page_{len(doc)}']['text_bottom_right_pt'] - 54) / (last.rect.height - 54 - 72 * 1.0), 3)
text = ''.join(page.get_text() for page in doc)
start = text.find('Abstract')
end = text.find('Index Terms')
abstract = text[start:end].replace('Abstract—', '').replace('-\n', '').replace('\n', ' ')
layout['abstract_words'] = len(abstract.split())
(out / 'layout.json').write_text(json.dumps(layout, indent=1), encoding='utf-8')
(out / 'text.txt').write_text(text, encoding='utf-8')
cols = 3
w, h = pages[0].size
scale = 0.5
tw, th = int(w * scale), int(h * scale)
rows = (len(pages) + cols - 1) // cols
sheet = Image.new('RGB', (cols * tw, rows * th), 'white')
for index, image in enumerate(pages):
    sheet.paste(image.resize((tw, th)), ((index % cols) * tw, (index // cols) * th))
sheet.save(out / 'overview.png')
print(json.dumps(layout, indent=1))
