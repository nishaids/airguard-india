"""Compose the stacked two-panel application figure from unmodified screenshots.

Captures of 12 October 2026 (https://webapp-phi-taupe.vercel.app/) are cropped only;
pixels are never retouched or upscaled, and panel letters sit outside the screenshot
area. Crop boxes and source hashes go to evidence/application_figure_manifest.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
ASSETS = ROOT.parent / 'Research References' / 'airguard_assets' / 'AirGuard_Claude_Research_Screenshots'
PANELS = [
    ('a', ASSETS / '01_Main_Dashboard.png', (112, 356, 1235, 604),
     'Current and next-day modelled AQI with category, dominant pollutant, observation and issue times, and source'),
    ('b', ASSETS / '05a_Research_Operational_Validation_Status.png', (108, 608, 1235, 918),
     'Research status: forecast mode, raw CAMS baseline, correction marked not validated, issue time and target, '
     'data source and freshness, unavailable prediction interval, and prospective verification state'),
]
GAP, BORDER, INDENT = 14, 2, 46


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def font(size):
    for name in ('timesbd.ttf', 'Times New Roman Bold.ttf', 'DejaVuSerif-Bold.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def framed(image):
    canvas = Image.new('RGB', (image.width + 2 * BORDER, image.height + 2 * BORDER), '#8a8a8a')
    canvas.paste(image, (BORDER, BORDER))
    return canvas


def main():
    crops = [(letter, framed(Image.open(path).convert('RGB').crop(box))) for letter, path, box, _ in PANELS]
    width = INDENT + max(image.width for _, image in crops)
    height = sum(image.height for _, image in crops) + GAP * (len(crops) - 1)
    sheet = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(sheet)
    label = font(30)
    y = 0
    for letter, image in crops:
        draw.text((2, y + 4), f'({letter})', fill='black', font=label)
        sheet.paste(image, (INDENT, y))
        y += image.height + GAP
    out = BASE / 'figures' / 'fig6_application.png'
    sheet.save(out, dpi=(300, 300))
    manifest = {'figure': 'figures/fig6_application.png', 'sha256': sha256(out), 'size': sheet.size,
                'capture_date': '2026-10-12', 'site': 'https://webapp-phi-taupe.vercel.app/',
                'processing': 'crop only at original pixel scale; no retouching; letters outside the screenshot area',
                'panels': [{'panel': letter, 'source': str(path.relative_to(ROOT.parent)).replace('\\', '/'),
                            'source_sha256': sha256(path), 'crop_box_px': box, 'shows': shows}
                           for letter, path, box, shows in PANELS]}
    (BASE / 'evidence' / 'application_figure_manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    print(out, sheet.size, [(letter, image.size) for letter, image in crops])


if __name__ == '__main__':
    main()
