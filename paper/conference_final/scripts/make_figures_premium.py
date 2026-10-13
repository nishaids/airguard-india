"""Camera-ready figure set (Figs. 1-6) in one design language.

Figs. 3-5 read evidence/verified_numbers.json and evidence/rows_temporal.parquet, the
same files the manuscript macros come from. Figs. 1-2 are schematics whose counts are
asserted against the evidence files. Fig. 6 crops the production captures written by
capture_application.cjs using the measured element boxes; pixels are never retouched.
Three tones only (blue, orange-red, grey); all text is at least 8 pt at print size.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
from PIL import Image

BASE = Path(__file__).resolve().parents[1]
EVIDENCE, FIGURES = BASE / 'evidence', BASE / 'figures'
N = json.loads((EVIDENCE / 'verified_numbers.json').read_text())
CAMS = json.loads((EVIDENCE / 'cams_status.json').read_text())
TEXT, COLUMN = 7.14, 3.44
INK, BLUE, RED, GREY, LIGHT = '#1a1a1a', '#1b5a8e', '#c4501b', '#5c5c5c', '#b5b5b5'
PALE_BLUE, PALE_RED, PALE_GREY = '#e9f0f7', '#fbeee6', '#f0f0f0'

plt.rcParams.update({
    'font.family': 'serif', 'font.serif': ['Times New Roman', 'Nimbus Roman', 'DejaVu Serif'],
    'mathtext.fontset': 'stix', 'font.size': 8.5, 'axes.labelsize': 8.5, 'axes.titlesize': 8.8,
    'xtick.labelsize': 8, 'ytick.labelsize': 8, 'legend.fontsize': 8, 'axes.linewidth': 0.7,
    'xtick.major.width': 0.7, 'ytick.major.width': 0.7, 'xtick.major.size': 2.8, 'ytick.major.size': 2.8,
    'lines.linewidth': 1.3, 'lines.markersize': 4.8, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': INK, 'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': INK, 'text.color': INK,
    'legend.frameon': False, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'figure.dpi': 150})
DASH = (0, (3, 2))


def save(fig, name):
    fig.savefig(FIGURES / f'{name}.pdf')
    fig.savefig(FIGURES / f'{name}.png', dpi=300)
    plt.close(fig)
    print('wrote', name)


def grid(ax, axis='y'):
    ax.grid(axis=axis, color='#dcdcdc', linewidth=0.45, zorder=0)
    ax.set_axisbelow(True)


def panel(ax, letter, text):
    ax.set_title(f'({letter}) {text}', loc='left', fontweight='bold', pad=5)


# --------------------------------------------------------------------------- Fig. 1
def figure_architecture():
    assert CAMS['verified_chunks'] == 6 and CAMS['planned_chunks'] == 36 and CAMS['eligible_rolling_folds'] == 0
    width, height = TEXT, 1.86
    fig = plt.figure(figsize=(width, height))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width), ax.set_ylim(0, height), ax.axis('off')
    left, gap, columns, box_h, lane_h, lane_gap = 0.06, 0.125, 8, 0.36, 0.58, 0.05
    col_w = (width - 2 * left - gap * (columns - 1)) / columns

    def span(column, count=1):
        return left + column * (col_w + gap), count * col_w + (count - 1) * gap

    def lane(index, letter, title, note, color):
        top = height - 0.01 - index * (lane_h + lane_gap)
        y = top - 0.095
        ax.add_patch(FancyBboxPatch((left, y - 0.072), 0.15, 0.144, boxstyle='round,pad=0,rounding_size=0.03', fc=color, ec='none'))
        ax.text(left + 0.075, y - 0.004, letter, color='white', fontsize=8.5, fontweight='bold', ha='center', va='center')
        ax.text(left + 0.22, y, title, color=color, fontsize=8.8, fontweight='bold', va='center')
        ax.text(width - left, y, note, color=color, fontsize=8, style='italic', va='center', ha='right')
        return top - 0.2 - box_h

    def box(column, count, y, label, edge, face, dashed=False, text=INK):
        x, w = span(column, count)
        ax.add_patch(FancyBboxPatch((x, y), w, box_h, boxstyle='round,pad=0,rounding_size=0.045', linewidth=0.95,
                                    edgecolor=edge, facecolor=face, linestyle=DASH if dashed else '-'))
        ax.text(x + w / 2, y + box_h / 2 - 0.004, label, ha='center', va='center', fontsize=8, color=text, linespacing=1.02)
        return x, w

    def arrow(x0, x1, y, color, dashed=False):
        ax.add_patch(FancyArrowPatch((x0 + 0.012, y), (x1 - 0.012, y), arrowstyle='-|>', mutation_scale=6.5, linewidth=0.95,
                                     color=color, linestyle=DASH if dashed else '-', shrinkA=0, shrinkB=0))

    def chain(y, items, edge, face, dashed=False, text=INK):
        previous = None
        for column, count, label, *style in items:
            x, w = box(column, count, y, label, style[0] if style else edge, style[1] if len(style) > 1 else face,
                       dashed, style[2] if len(style) > 2 else text)
            if previous is not None:
                arrow(previous, x, y + box_h / 2, edge, dashed)
            previous = x + w

    y = lane(0, 'A', 'Completed development evidence', 'evaluated in this paper; final 90 days sealed', BLUE)
    chain(y, [(0, 1, 'Observations'), (1, 1, 'Quality\ncontrol'), (2, 1, 'AQI\ntargets'), (3, 1, 'Issue-safe\npredictors'),
              (4, 1, 'Temporal\nevaluation'), (5, 1, 'Geographic\ntransfer'), (6, 1, 'Reliability\naudit'),
              (7, 1, 'Evidence\nartifacts')], BLUE, PALE_BLUE)

    y = lane(1, 'B', 'Operational CAMS extension',
             f"{CAMS['verified_chunks']} of {CAMS['planned_chunks']} archive chunks verified; no correction fitted", RED)
    pending = (LIGHT, 'white', GREY)
    chain(y, [(0, 1, 'Archived\nCAMS'), (1, 1, 'Run / lead\nverification'), (2, 1, 'GRIB + unit\nchecks'),
              (3, 1, 'Grid–station\nalignment'), (4, 1, 'Residual\ncalibration', *pending), (5, 1, 'Model\nlock', *pending),
              (6, 1, 'Final\nevaluation', *pending)], RED, PALE_RED, dashed=True)
    x, w = span(7)
    ax.text(x + w / 2, y + box_h / 2, 'operational\ncalibration\npending', ha='center', va='center', fontsize=8, style='italic',
            color=RED, linespacing=0.98)

    y = lane(2, 'C', 'Deployed AirGuard application', 'presentation path; raw CAMS-based estimate shown', GREY)
    chain(y, [(0, 2, 'Open-Meteo, CAMS,\nstation feeds'), (2, 1, 'AQI\nservice'), (3, 1, 'API'), (4, 2, 'Web interface'),
              (6, 2, 'Forecast, atlas,\nresearch, methods')], GREY, PALE_GREY)
    save(fig, 'fig1_architecture')


# --------------------------------------------------------------------------- Fig. 2
def figure_timeline():
    assert N['final_test_range'] == ['2026-07-10', '2026-10-07'] and N['final_test_scored'] is False
    fig = plt.figure(figsize=(TEXT, 1.62))
    ax = fig.add_axes([0.008, 0.43, 0.984, 0.475])
    ax.set_xlim(-38, 30), ax.set_ylim(-1.12, 2.0), ax.axis('off')
    fig.text(0.008, 0.955, '(a) Issue-time contract (IST)', fontsize=8.8, fontweight='bold', va='center')
    ax.add_patch(Rectangle((-37.5, 0.14), 33.5, 1.84, facecolor=PALE_BLUE, edgecolor='none'))
    ax.add_patch(Rectangle((-4, 0.14), 33, 1.84, facecolor=PALE_RED, edgecolor='none'))
    ax.text(-36.8, 1.70, 'ONLY PRE-ISSUE INFORMATION', fontsize=8, fontweight='bold', color=BLUE, va='center')
    ax.text(28.3, 1.70, 'TARGET INFORMATION — PROHIBITED', fontsize=8, fontweight='bold', color=RED, va='center', ha='right')
    ax.add_patch(Rectangle((-31, 0.30), 24, 0.50, facecolor='white', edgecolor=BLUE, lw=0.9))
    ax.text(-19, 0.55, 'measured history: 24 h of bins ending 17:00', ha='center', va='center', fontsize=8, color=BLUE)
    ax.text(-36.8, 1.20, 'forecast weather for day $D$ from runs at least 48 h old', ha='left',
            va='center', fontsize=8, color=BLUE)
    ax.add_patch(Rectangle((0, 0.30), 24, 0.50, facecolor='white', edgecolor=RED, lw=0.9, linestyle=DASH))
    ax.text(12, 0.55, 'target day $D$: observations are labels only', ha='center', va='center', fontsize=8, color=RED)
    ax.annotate('', xy=(29.6, 0), xytext=(-37.5, 0), arrowprops=dict(arrowstyle='-|>', lw=0.9, color=INK, mutation_scale=7))
    ax.plot([-4, -4], [-0.6, 1.98], color=INK, lw=1.5)
    for hour, label, align in ((-31, r'$D{-}2$ 17:00', 'center'), (-7, r'$D{-}1$ 17:00 history cutoff', 'right'),
                               (0, r'$D$ 00:00', 'left'), (24, r'$D$ 24:00', 'center')):
        ax.plot([hour, hour], [-0.1, 0.1], color=INK, lw=0.9)
        offset = -0.5 if align == 'right' else 0.6 if align == 'left' else 0
        ax.text(hour + offset, -0.16, label, ha=align, va='top', fontsize=8)
    ax.text(-4, -0.66, r'$D{-}1$ 20:00 forecast issue', ha='center', va='top', fontsize=8, fontweight='bold')

    bx = fig.add_axes([0.008, 0.02, 0.984, 0.36])
    bx.set_xlim(0, 100), bx.set_ylim(0, 1), bx.axis('off')
    fig.text(0.008, 0.415, '(b) One expanding fold and the sealed interval', fontsize=8.8, fontweight='bold', va='center')
    y0, h = 0.36, 0.44

    def block(x0, x1, label, face, edge, color=INK, **kwargs):
        bx.add_patch(Rectangle((x0, y0), x1 - x0, h, facecolor=face, edgecolor=edge, lw=0.9, **kwargs))
        bx.text((x0 + x1) / 2, y0 + h / 2, label, ha='center', va='center', fontsize=8, color=color, linespacing=1.0)

    block(0.6, 36, 'Training: all earlier dates (at least 90 d)', PALE_BLUE, BLUE)
    block(38.6, 53, 'Calibration (30 d)', '#f6e7c4', '#a8842c')
    block(55.6, 70, 'Evaluation (30 d)', BLUE, BLUE, color='white')
    for x in (37.3, 54.3):
        bx.text(x, y0 + h + 0.05, '1 d', ha='center', va='bottom', fontsize=8, color=GREY)
    bx.annotate('', xy=(80.4, y0 + h / 2), xytext=(70.6, y0 + h / 2), arrowprops=dict(arrowstyle='-|>', lw=0.9, color=GREY, mutation_scale=7))
    bx.text(75.5, y0 + h / 2 + 0.16, 'advance 30 d', ha='center', va='bottom', fontsize=8, color=GREY)
    bx.text(75.5, y0 + h / 2 - 0.16, '12 folds', ha='center', va='top', fontsize=8, color=GREY)
    bx.add_patch(Rectangle((81, y0), 18.4, h, facecolor='white', edgecolor=RED, lw=1.0, hatch='////'))
    bx.text(90.2, y0 + h / 2, 'FINAL 90 DAYS\nSEALED', ha='center', va='center', fontsize=8, fontweight='bold', color=RED,
            linespacing=1.0, bbox=dict(facecolor='white', edgecolor='none', pad=1.5))
    bx.text(18.3, 0.13, 'from 19 Feb 2025', ha='center', va='center', fontsize=8, color=GREY)
    bx.text(62.8, 0.13, '22 Jun 2025 to 15 Jun 2026', ha='center', va='center', fontsize=8, color=GREY)
    bx.text(90.2, 0.13, '10 Jul to 7 Oct 2026', ha='center', va='center', fontsize=8, color=RED)
    save(fig, 'fig2_timeline')


# --------------------------------------------------------------------------- Fig. 3
def figure_forest():
    fig, ax = plt.subplots(figsize=(COLUMN, 1.5), gridspec_kw=dict(left=0.475, right=0.985, top=0.975, bottom=0.25))
    rows = [('ridge_strict_vs_climatology', 'Weather Ridge $-$ climatology'),
            ('weather_ablation', 'Weather Ridge $-$ calendar Ridge'),
            ('history_ablation_conditional', 'History Ridge $-$ weather Ridge'),
            ('ridge_history_vs_persistence', 'History Ridge $-$ persistence')]
    for y, (key, _) in enumerate(rows[::-1]):
        e = N['paired'][key]
        crosses = e['ci95'][0] < 0 < e['ci95'][1]
        color = GREY if crosses else BLUE
        ax.errorbar(e['mae_difference'], y, xerr=[[e['mae_difference'] - e['ci95'][0]], [e['ci95'][1] - e['mae_difference']]],
                    fmt='o', color=color, capsize=2.6, capthick=1.0, elinewidth=1.3, markersize=5,
                    markerfacecolor='white' if crosses else color, markeredgewidth=1.1)
        right = e['mae_difference'] < -5
        ax.text(e['ci95'][1] + 0.8 if right else e['ci95'][0] - 0.8, y + 0.03, f"{e['mae_difference']:+.2f}".replace('-', '−'),
                va='center', ha='left' if right else 'right', fontsize=8, color=color)
    ax.axvline(0, color=INK, lw=0.8, ls=DASH)
    ax.set_yticks(range(4)), ax.set_yticklabels([r[1] for r in rows[::-1]])
    ax.tick_params(axis='y', length=0)
    ax.set_ylim(-0.65, 3.65), ax.set_xlim(-23, 5)
    ax.set_xlabel('Paired MAE difference (AQI units)', labelpad=2)
    grid(ax, 'x')
    save(fig, 'fig3_rq1')


# --------------------------------------------------------------------------- Fig. 4
def figure_transfer_severe():
    severe = pd.read_parquet(EVIDENCE / 'rows_temporal.parquet')
    severe = severe[severe.censored]
    assert len(severe) == N['severe']['ridge_strict']['n']
    fig, axes = plt.subplots(1, 2, figsize=(TEXT, 1.8), gridspec_kw=dict(width_ratios=[1.0, 1.1], wspace=0.24, left=0.098,
                                                                          right=0.995, top=0.855, bottom=0.215))
    ax, s = axes[0], N['spatial_rows']
    levels = [('station_id', 'Station'), ('city', 'City'), ('cluster', 'Urban cluster'), ('region', 'Region')]
    for y, (key, _) in enumerate(levels[::-1]):
        e = s[key]
        ax.errorbar(e['difference'], y + 0.17, xerr=[[e['difference'] - e['ci95'][0]], [e['ci95'][1] - e['difference']]],
                    fmt='o', color=BLUE, capsize=2.4, capthick=1.0, elinewidth=1.3, markersize=5)
        ax.errorbar(e['poor_or_worse_difference'], y - 0.17,
                    xerr=[[e['poor_or_worse_difference'] - e['poor_or_worse_ci95'][0]],
                          [e['poor_or_worse_ci95'][1] - e['poor_or_worse_difference']]],
                    fmt='o', color=RED, capsize=2.4, capthick=1.0, elinewidth=1.3, markersize=5, markerfacecolor='white',
                    markeredgewidth=1.1)
    ax.axvline(0, color=INK, lw=0.8, ls=DASH)
    ax.set_yticks(range(4)), ax.set_yticklabels([l[1] for l in levels[::-1]])
    ax.tick_params(axis='y', length=0)
    ax.set_ylim(-0.7, 3.85), ax.set_xlim(-0.9, 16)
    ax.set_xlabel('MAE increase when the location is withheld (AQI units)', labelpad=2)
    grid(ax, 'x')
    ax.plot([], [], 'o', color=BLUE, label=f"all exact pairs ({s['city']['n_exact']:,})")
    ax.plot([], [], 'o', color=RED, markerfacecolor='white', markeredgewidth=1.1,
            label=f"Poor-or-worse pairs ({s['city']['poor_or_worse_n']:,})")
    ax.legend(loc='upper right', handletextpad=0.3, borderaxespad=0.2, labelspacing=0.3)
    panel(ax, 'a', 'Geographic exclusion')

    ax = axes[1]
    for name, color, style, label, y_text in (('ridge_strict', BLUE, '-', 'Weather Ridge', 46), ('ridge_history', RED, '-', 'History Ridge', 31),
                                              ('persistence', GREY, (0, (5, 2)), 'Persistence (dashed)', 16)):
        values = np.sort(severe[name].dropna().to_numpy())
        ax.step(np.concatenate([[0], values, [800]]), np.concatenate([[0], np.arange(1, len(values) + 1) / len(values) * 100, [100]]),
                where='post', color=color, lw=1.4, ls=style)
        ax.text(424, y_text, f'{label}, $n$ = {len(values)}', color=color, fontsize=8, ha='left', va='center')
    ax.axvline(401, color=INK, lw=1.0, ls=DASH)
    ax.text(424, 72, 'Severe lower bound = AQI 401', fontsize=8, ha='left', va='center')
    ax.set_xlim(0, 790), ax.set_ylim(0, 102)
    ax.set_xticks([0, 100, 200, 300, 401]), ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xlabel('Forecast on censored Severe days (AQI units)', labelpad=2)
    ax.set_ylabel('Cumulative share (%)', labelpad=2)
    panel(ax, 'b', 'Forecasts on censored Severe days')
    save(fig, 'fig4_transfer_severe')


# --------------------------------------------------------------------------- Fig. 5
def figure_reliability():
    unc, w = N['uncertainty_rows'], N['warnings_rows']
    fig, axes = plt.subplots(1, 2, figsize=(TEXT, 1.8), gridspec_kw=dict(width_ratios=[1.1, 1.0], wspace=0.21, left=0.075,
                                                                          right=0.995, top=0.855, bottom=0.24))
    ax = axes[0]
    cats = ['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor']
    for offset, (key, color, marker, label, face) in zip((-0.15, 0.15), (('split_0.9', BLUE, 'o', 'Split conformal', BLUE),
                                                                        ('cqr_0.9', GREY, '^', 'CQR', 'white'))):
        values = [unc[key]['by_category'][c] for c in cats]
        cov = np.array([v['coverage'] * 100 for v in values])
        lo = np.array([v['coverage_ci95'][0] * 100 for v in values])
        hi = np.array([v['coverage_ci95'][1] * 100 for v in values])
        ax.errorbar(np.arange(5) + offset, cov, yerr=[cov - lo, hi - cov], fmt=marker, color=color, markerfacecolor=face,
                    capsize=2.2, capthick=1.0, elinewidth=1.2, markersize=5, markeredgewidth=1.1, label=label)
    ax.axhline(90, color=INK, lw=0.8, ls=DASH)
    ax.text(4.46, 92, 'nominal 90%', ha='right', va='bottom', fontsize=8)
    ax.set_xticks(range(5))
    ax.set_xticklabels([f"{name}\n{unc['split_0.9']['by_category'][c]['n']:,}" for name, c in
                        zip(['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor'], cats)], linespacing=1.02)
    ax.tick_params(axis='x', length=0)
    ax.set_ylim(0, 106), ax.set_yticks([0, 25, 50, 75, 100]), ax.set_xlim(-0.5, 4.5)
    ax.set_ylabel('Empirical coverage (%)', labelpad=2)
    grid(ax)
    ax.legend(loc='lower left', handletextpad=0.3, borderaxespad=0.3, labelspacing=0.3)
    panel(ax, 'a', 'Coverage of nominal 90% intervals by observed category')

    ax = axes[1]
    quantiles = ['0.5', '0.65', '0.75', '0.85', '0.9', '0.95', '0.975']
    over = [w['raw_quantiles'][q]['over'] * 100 for q in quantiles]
    under = [w['raw_quantiles'][q]['under'] * 100 for q in quantiles]
    ax.plot(over, under, color=LIGHT, marker='o', markersize=3, markerfacecolor='white', markeredgewidth=0.9, lw=1.2,
            label=r'raw quantile level $\tau$', zorder=2)
    ax.text(over[0] + 1.6, under[0] + 1.6, r'$\tau$ = 0.5', fontsize=8, color=GREY, ha='left', va='center')
    ax.text(over[-1] + 1.4, under[-1] + 2.0, r'$\tau$ = 0.975', fontsize=8, color=GREY, ha='center', va='center')
    for key, color, marker, label, face in (('P0', BLUE, 'o', 'P0: point forecast', BLUE), ('P1', GREY, '^', 'P1: calibrated median', 'white'),
                                            ('P2', RED, 'D', 'P2: 0.75 quantile', RED)):
        e = w[key]
        ax.errorbar(e['over'] * 100, e['under'] * 100,
                    xerr=[[(e['over'] - e['over_ci95'][0]) * 100], [(e['over_ci95'][1] - e['over']) * 100]],
                    yerr=[[(e['under'] - e['under_ci95'][0]) * 100], [(e['under_ci95'][1] - e['under']) * 100]],
                    fmt=marker, color=color, markerfacecolor=face, markeredgewidth=1.1, capsize=2.2, capthick=1.0, elinewidth=1.2,
                    markersize=5.4, label=label, zorder=3)
    ax.text(17, 3.6, 'more conservative rules \u2192', fontsize=8, color=GREY, ha='left', va='center')
    ax.set_xlim(15, 96), ax.set_ylim(0, 35), ax.set_yticks([0, 10, 20, 30])
    ax.set_xlabel('Over-warning (%)', labelpad=2), ax.set_ylabel('Under-warning (%)', labelpad=2)
    grid(ax, 'both')
    ax.legend(loc='upper right', handletextpad=0.4, borderaxespad=0.25, labelspacing=0.3)
    panel(ax, 'b', f"Warning losses on {w['P0']['n']:,} outcomes")
    save(fig, 'fig5_uncertainty_warning')


# --------------------------------------------------------------------------- Fig. 6
def figure_application():
    folder = FIGURES / 'app_capture'
    meta = json.loads((folder / 'capture.json').read_text())
    scale = meta['device_scale_factor']
    live, research = meta['panels']['live']['element'], meta['panels']['research']['element']
    image_live = Image.open(folder / 'live_full.png').convert('RGB')
    image_research = Image.open(folder / 'research_full.png').convert('RGB')
    margin_x, margin_top = 14, 8
    pixels = np.asarray(image_live)

    def clean(y_css):  # the cut must fall on a blank row of the forecast card
        row = int(round(y_css * scale))
        x0, x1 = int((live['x'] + live['width'] / 2 + 12) * scale), int((live['x'] + live['width'] - 6) * scale)
        band = pixels[row - 4:row + 2, x0:x1].reshape(-1, 3).astype(int)
        return int(np.ptp(band, axis=0).max()) <= 6

    body = None
    for extra in np.arange(0, 14.01, 1 / scale):  # research list height, grown until the card cut is clean
        if clean(live['y'] + research['height'] + extra):
            body = research['height'] + extra
            break
    assert body is not None, 'no blank row found for the forecast-card cut'

    def crop(image, element):
        box = tuple(int(round(v * scale)) for v in (element['x'] - margin_x, element['y'] - margin_top,
                                                    element['x'] + element['width'] + margin_x, element['y'] + body))
        return image.crop(box), box

    outputs = {}
    for name, image, element, target in (('live', image_live, live, 'fig6a_forecast.png'),
                                         ('research', image_research, research, 'fig6b_research.png')):
        panel_image, box = crop(image, element)
        panel_image.save(FIGURES / target, dpi=(450, 450))
        outputs[name] = {'file': f'figures/{target}', 'size_px': panel_image.size, 'crop_box_device_px': box,
                         'sha256': hashlib.sha256((FIGURES / target).read_bytes()).hexdigest(), 'url': meta['panels'][name]['url']}
    assert outputs['live']['size_px'] == outputs['research']['size_px']
    manifest = {'site': meta['site'], 'captured_at_utc': meta['captured_at_utc'], 'viewport_css_px': meta['viewport'],
                'device_scale_factor': scale, 'processing': 'crop only, by measured element boxes; no retouching, no rescaling',
                'panels': outputs}
    (EVIDENCE / 'application_figure_manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    print('wrote fig6 panels', outputs['live']['size_px'], 'body css px', round(body, 2))


if __name__ == '__main__':
    figure_architecture()
    figure_timeline()
    figure_forest()
    figure_transfer_severe()
    figure_reliability()
    figure_application()
