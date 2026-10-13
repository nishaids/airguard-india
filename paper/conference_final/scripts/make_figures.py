"""Vector figures for the conference manuscript, drawn at final print size.

Every plotted value is read from evidence/verified_numbers.json or from the
development-only row tables written by reproduce_development.py. Nothing is
typed in by hand except schematic labels in Figs. 1 and 2, whose counts are
asserted against the evidence files before drawing.

Run from the repository root:
    .venv-live/Scripts/python.exe paper/conference_final/scripts/make_figures.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

BASE = Path(__file__).resolve().parents[1]
EVIDENCE, FIGURES = BASE / 'evidence', BASE / 'figures'
N = json.loads((EVIDENCE / 'verified_numbers.json').read_text())
CAMS = json.loads((EVIDENCE / 'cams_status.json').read_text())

WIDTH = 7.14  # IEEEtran A4 conference text width in inches
INK, BLUE, RED, GREEN, GREY, LIGHT = '#1a1a1a', '#1b5a8e', '#c4501b', '#2f7d5b', '#6e6e6e', '#8fb4d6'
PALE_BLUE, PALE_GREY, PALE_RED = '#eaf1f8', '#f1f1f1', '#fbefe8'
MODEL = {'climatology': dict(color=GREY, marker='s', ls='--', label='Climatology'),
         'ridge_strict': dict(color=BLUE, marker='o', ls='-', label='Weather Ridge'),
         'persistence': dict(color=GREEN, marker='^', ls='-', label='Persistence'),
         'ridge_history': dict(color=RED, marker='D', ls='-', label='History Ridge')}
MONTHS = ['Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']

plt.rcParams.update({
    'font.family': 'serif', 'font.serif': ['Times New Roman', 'Nimbus Roman', 'DejaVu Serif'],
    'mathtext.fontset': 'stix', 'font.size': 8, 'axes.labelsize': 8, 'axes.titlesize': 8.5,
    'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 7.5, 'axes.linewidth': 0.6,
    'xtick.major.width': 0.6, 'ytick.major.width': 0.6, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
    'lines.linewidth': 1.1, 'lines.markersize': 3.6, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': INK, 'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': INK, 'text.color': INK,
    'legend.frameon': False, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'savefig.pad_inches': 0.01,
    'axes.grid': False, 'figure.dpi': 150})


def save(fig, name):
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f'{name}.pdf')
    fig.savefig(FIGURES / f'{name}.png', dpi=300)
    plt.close(fig)
    print('wrote', name)


def panel_title(ax, letter, text):
    ax.set_title(f'({letter}) {text}', loc='left', fontweight='bold', pad=4)


def light_grid(ax, axis='y'):
    ax.grid(axis=axis, color='#d9d9d9', linewidth=0.4, zorder=0)
    ax.set_axisbelow(True)


# ----------------------------------------------------------------------------- Fig. 1
def figure_architecture():
    assert CAMS['verified_chunks'] == 6 and CAMS['planned_chunks'] == 36 and CAMS['alignment']['dates'] == 42
    assert N['population']['folds'] == 12 and sum(v['holdouts'] for v in N['spatial_frozen'].values()) == 36
    height = 1.90
    fig = plt.figure(figsize=(WIDTH, height))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, WIDTH), ax.set_ylim(0, height), ax.axis('off')

    def box(x, y, w, h, title, lines, edge, face, dashed=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=0.045', linewidth=0.9,
                                    edgecolor=edge, facecolor=face, linestyle=(0, (3.2, 2.2)) if dashed else '-'))
        ax.text(x + w / 2, y + h - 0.095, title, ha='center', va='center', fontsize=8, fontweight='bold', color=edge)
        for index, line in enumerate(lines):
            ax.text(x + w / 2, y + h - 0.225 - 0.112 * index, line, ha='center', va='center', fontsize=7.3, color=INK)

    def arrow(x0, x1, y, color, dashed=False):
        ax.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle='-|>', mutation_scale=7, linewidth=0.9, color=color,
                                     linestyle=(0, (3.2, 2.2)) if dashed else '-', shrinkA=0, shrinkB=0))

    def lane(y, h, letter, title, status, color):
        ax.add_patch(Rectangle((0.02, y), WIDTH - 0.04, h, linewidth=0, facecolor='#fafafa'))
        ax.text(0.09, y + h - 0.085, letter, fontsize=8.5, fontweight='bold', color='white', ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.18', facecolor=color, edgecolor='none'))
        ax.text(0.24, y + h - 0.085, title, fontsize=8.3, fontweight='bold', color=color, va='center')
        ax.text(WIDTH - 0.08, y + h - 0.085, status, fontsize=7.6, style='italic', color=color, va='center', ha='right')

    left, gap, n = 0.10, 0.155, 5
    w = (WIDTH - 2 * left - gap * (n - 1)) / n
    xs = [left + i * (w + gap) for i in range(n)]
    bh = 0.415

    # Lane A: completed research evidence
    ya = 1.295
    lane(ya, 0.605, 'A', 'Completed research evidence', 'development data only; no CAMS predictor; final 90 days sealed', BLUE)
    content = [('Observations', ['CPCB monitors via OpenAQ', 'quality rules, rejection ledger']),
               ('Targets and inputs', ['three-pollutant daily AQI,', 'cutoff-checked predictors']),
               ('Temporal folds', ['12 expanding folds', 'calibration month, embargo']),
               ('Geographic holdouts', ['36 exclusions: station, city,', 'urban cluster, region']),
               ('Reliability audit', ['Severe bounds, intervals,', 'warning losses, paired tests'])]
    for x, (title, lines) in zip(xs, content):
        box(x, ya + 0.025, w, bh, title, lines, BLUE, PALE_BLUE)
    for i in range(n - 1):
        arrow(xs[i] + w + 0.012, xs[i + 1] - 0.012, ya + 0.025 + bh / 2, BLUE)

    # Lane B: incomplete CAMS extension
    yb = 0.65
    lane(yb, 0.605, 'B', 'Operational CAMS extension', 'incomplete: 6 of 36 archive chunks verified; no correction fitted', RED)
    content = [('CAMS forecast archive', ['run, lead and valid times,', '0.4° global fields']),
               ('GRIB verification', ['decoded units and levels,', 'checksums re-hashed']),
               ('Grid-to-station join', ['42 forecast dates aligned,', 'no eligible fold yet']),
               ('Residual correction', ['learner comparison and', 'selection lock pending'])]
    for x, (title, lines) in zip(xs, content):
        box(x, yb + 0.025, w, bh, title, lines, RED, 'white', dashed=True)
    for i in range(3):
        arrow(xs[i] + w + 0.012, xs[i + 1] - 0.012, yb + 0.025 + bh / 2, RED, dashed=True)
    ax.text(xs[4] + w / 2, yb + 0.025 + bh / 2 + 0.07, 'not evaluated;', ha='center', va='center', fontsize=7.6, color=RED, style='italic')
    ax.text(xs[4] + w / 2, yb + 0.025 + bh / 2 - 0.07, 'reported separately', ha='center', va='center', fontsize=7.6, color=RED, style='italic')

    # Lane C: live application
    yc = 0.005
    lane(yc, 0.605, 'C', 'Live application', 'presentation path; raw CAMS estimate shown; no research model deployed', GREY)
    content = [('Open-Meteo services', ['CAMS global composition,', 'GFS weather']),
               ('CPCB-style AQI engine', ['same breakpoints as', 'the research targets']),
               ('Python API', ['source and freshness', 'labels, immutable issues']),
               ('Next.js interface', ['forecast, atlas, research,', 'methods, status pages']),
               ('Forecast and guidance', ['correction shown as', '"not validated"'])]
    for x, (title, lines) in zip(xs, content):
        box(x, yc + 0.025, w, bh, title, lines, '#4a4a4a', PALE_GREY)
    for i in range(n - 1):
        arrow(xs[i] + w + 0.012, xs[i + 1] - 0.012, yc + 0.025 + bh / 2, '#4a4a4a')
    save(fig, 'fig1_architecture')


# ----------------------------------------------------------------------------- Fig. 2
def figure_timeline():
    meta = N['reproduction']['fold_meta']
    assert N['final_test_range'] == ['2026-07-10', '2026-10-07'] and N['final_test_scored'] is False
    fig = plt.figure(figsize=(WIDTH, 1.80))
    # (a) issue-time contract, hours relative to D 00:00 IST
    ax = fig.add_axes([0.012, 0.545, 0.976, 0.41])
    ax.set_xlim(-37.5, 33.5), ax.set_ylim(-0.95, 2.1), ax.axis('off')
    ax.text(-37.5, 2.02, '(a) Previous-evening issue contract (IST)', fontsize=8.5, fontweight='bold', va='center')
    ax.annotate('', xy=(33.3, 0), xytext=(-37.3, 0), arrowprops=dict(arrowstyle='-|>', lw=0.9, color=INK, mutation_scale=7))
    ticks = [(-31, r'$D{-}2$ 17:00', 'center'), (-24, r'$D{-}1$ 00:00', 'center'), (-7, r'$D{-}1$ 17:00' + '\nhistory cutoff', 'right'),
             (0, r'$D$ 00:00', 'left'), (24, r'$D$ 24:00', 'center')]
    for hour, label, align in ticks:
        ax.plot([hour, hour], [-0.10, 0.10], color=INK, lw=0.9)
        ax.text(hour + (0.5 if align == 'right' else -0.5 if align == 'left' else 0), -0.22, label, ha=align, va='top', fontsize=7.3,
                linespacing=1.0)
    ax.plot([-4, -4], [-0.56, -0.10], color=INK, lw=0.6)
    ax.text(-3.6, -0.60, r'$D{-}1$ 20:00 forecast issue', ha='left', va='top', fontsize=7.3)
    ax.add_patch(Rectangle((-31, 0.26), 24, 0.60, facecolor='#dcebe3', edgecolor=GREEN, lw=0.8))
    ax.text(-19, 0.555, 'measured history: 24 h of bins ending by the cutoff', ha='center', va='center', fontsize=7.4, color='#1f5a41')
    ax.add_patch(Rectangle((-7, 0.26), 3, 0.60, facecolor='white', edgecolor=GREY, lw=0.8, hatch='////'))
    ax.add_patch(Rectangle((0, 0.26), 24, 0.60, facecolor=PALE_BLUE, edgecolor=BLUE, lw=0.8))
    ax.text(12, 0.555, r'target day $D$: daily AQI label, known only afterwards', ha='center', va='center', fontsize=7.4, color=BLUE)
    ax.plot([-4, -4], [-0.10, 0.98], color=INK, lw=1.2)
    ax.text(-5.5, 1.10, '3 h', ha='center', va='center', fontsize=7.0, color=GREY)
    ax.text(-19, 1.12, 'three-hour receipt of station data is assumed, not logged', ha='center', va='center', fontsize=7.2,
            style='italic', color=GREY)
    ax.annotate('', xy=(0, 1.12), xytext=(24, 1.12), arrowprops=dict(arrowstyle='|-|', lw=0.7, color=BLUE, mutation_scale=3))
    ax.text(12, 1.50, 'GFS weather forecast for each target hour, from a run initialized at least 48 h earlier',
            ha='center', va='center', fontsize=7.4, color=BLUE)

    # (b) evaluation calendar on true dates
    bx = fig.add_axes([0.094, 0.13, 0.894, 0.30])
    start, end = date(2025, 2, 1), date(2026, 10, 20)
    bx.set_xlim(mdates.date2num(start), mdates.date2num(end))
    rows = [('Fold 1', 'fold_01'), ('Fold 6', 'fold_06'), ('Fold 12', 'fold_12')]
    colors = {'train': '#c9d9ea', 'cal': '#f3d9a4', 'eval': BLUE}

    def span(row, first, last, color, **kwargs):
        x0, x1 = mdates.date2num(date.fromisoformat(first)), mdates.date2num(date.fromisoformat(last)) + 1
        bx.add_patch(Rectangle((x0, row - 0.33), x1 - x0, 0.66, facecolor=color, edgecolor='white', lw=0.4, **kwargs))

    for index, (label, key) in enumerate(rows):
        row = 3 - index
        span(row, *meta[key]['train_range'], colors['train'])
        span(row, *meta[key]['calibration_range'], colors['cal'])
        span(row, *meta[key]['test_range'], colors['eval'])
    span(0, *N['reproduction']['spatial_train_range'], colors['train'])
    span(0, *N['reproduction']['spatial_test_range'], colors['eval'])
    sealed0, sealed1 = mdates.date2num(date(2026, 7, 10)), mdates.date2num(date(2026, 10, 7)) + 1
    bx.add_patch(Rectangle((sealed0, -0.45), sealed1 - sealed0, 3.9, facecolor='white', edgecolor=RED, lw=0.9, hatch='///', zorder=3))
    bx.text((sealed0 + sealed1) / 2, 1.5, 'sealed test\nnot accessed', ha='center', va='center', fontsize=7.3, color=RED,
            fontweight='bold', linespacing=1.0, zorder=4, bbox=dict(facecolor='white', edgecolor='none', pad=1.2))
    bx.set_ylim(-0.55, 3.55)
    bx.set_yticks([3, 2, 1, 0]), bx.set_yticklabels(['Fold 1', 'Fold 6', 'Fold 12', 'Spatial frame'])
    bx.tick_params(axis='y', length=0)
    bx.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[3, 6, 9, 12]))
    bx.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    bx.xaxis.set_minor_locator(mdates.MonthLocator())
    bx.tick_params(axis='x', which='minor', length=1.5, width=0.4)
    bx.spines['left'].set_visible(False)
    fig.text(0.012, 0.478, '(b) Development folds and protected final interval', fontsize=8.5, fontweight='bold', va='center')
    handles = [Rectangle((0, 0), 1, 1, facecolor=colors['train']), Rectangle((0, 0), 1, 1, facecolor=colors['cal']),
               Rectangle((0, 0), 1, 1, facecolor=colors['eval'])]
    fig.legend(handles, ['training (expanding, at least 90 d)', 'calibration (30 d)', 'evaluation'], loc='center right',
               bbox_to_anchor=(0.992, 0.478), ncol=3, handlelength=1.1, handleheight=0.7, columnspacing=1.2, fontsize=7.4)
    save(fig, 'fig2_timeline')


# ----------------------------------------------------------------------------- Fig. 3
def figure_rq1():
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 1.70), gridspec_kw=dict(width_ratios=[1.28, 1, 1], wspace=0.36,
                                                                               left=0.215, right=0.995, top=0.865, bottom=0.24))
    ax = axes[0]
    rows = [('ridge_strict_vs_climatology', 'Weather Ridge $-$ climatology', BLUE),
            ('weather_ablation', 'Weather Ridge $-$ calendar Ridge', BLUE),
            ('history_ablation_conditional', 'History Ridge $-$ weather Ridge', RED),
            ('ridge_history_vs_persistence', 'History Ridge $-$ persistence', RED)]
    for y, (key, label, color) in enumerate(rows[::-1]):
        entry = N['paired'][key]
        ax.errorbar(entry['mae_difference'], y, xerr=[[entry['mae_difference'] - entry['ci95'][0]], [entry['ci95'][1] - entry['mae_difference']]],
                    fmt='o', color=color, capsize=2.2, capthick=0.9, elinewidth=1.0, markersize=4,
                    markerfacecolor='white' if entry['ci95'][0] < 0 < entry['ci95'][1] else color)
        ax.text(entry['ci95'][1] + 0.7 if entry['mae_difference'] < -5 else entry['ci95'][0] - 0.7, y + 0.03,
                f"{entry['mae_difference']:+.2f}".replace('-', '−'), va='center', ha='left' if entry['mae_difference'] < -5 else 'right',
                fontsize=7.5, color=color)
    ax.axvline(0, color=INK, lw=0.6, ls=(0, (3, 2)))
    ax.set_yticks(range(4)), ax.set_yticklabels([r[1] for r in rows[::-1]])
    ax.set_ylim(-0.6, 3.6), ax.set_xlim(-22, 4.5)
    ax.set_xlabel('Paired MAE difference (AQI units)')
    light_grid(ax, 'x')
    panel_title(ax, 'a', 'Paired contrasts, 95% intervals')
    ax.title.set_position((-0.92, 1.0))

    folds = N['folds']
    x = np.arange(1, 13)
    for ax, letter, title, pair, keys in ((axes[1], 'b', 'All exact pairs',
                                           ('climatology', 'ridge_strict'), ('mae_climatology', 'mae_ridge_strict')),
                                          (axes[2], 'c', 'History-available pairs',
                                           ('persistence', 'ridge_history'), ('mae_persistence', 'mae_ridge_history'))):
        for name, key in zip(pair, keys):
            style = MODEL[name]
            ax.plot(x, [f[key] for f in folds], color=style['color'], marker=style['marker'], ls=style['ls'], label=style['label'],
                    markerfacecolor='white' if name in ('climatology', 'persistence') else style['color'], markeredgewidth=0.9)
        ax.set_xticks(x), ax.set_xticklabels(MONTHS, rotation=90)
        ax.set_ylim(0, 128), ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_xlabel('Evaluation month, 2025–26')
        light_grid(ax)
        ax.legend(loc='upper left', handlelength=1.9, borderaxespad=0.1, labelspacing=0.25)
        panel_title(ax, letter, title)
    axes[1].set_ylabel('MAE (AQI units)')
    save(fig, 'fig3_rq1')


# ----------------------------------------------------------------------------- Fig. 4
def figure_rq2_severe():
    rows = pd.read_parquet(EVIDENCE / 'rows_temporal.parquet')
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 1.70), gridspec_kw=dict(width_ratios=[0.92, 1.04, 1.2], wspace=0.33,
                                                                               left=0.118, right=0.995, top=0.865, bottom=0.24))
    ax = axes[0]
    levels = [('station_id', 'Station'), ('city', 'City'), ('cluster', 'Urban\ncluster'), ('region', 'Region')]
    spatial = N['spatial_rows']
    for y, (key, _) in enumerate(levels[::-1]):
        entry = spatial[key]
        ax.errorbar(entry['difference'], y + 0.16, xerr=[[entry['difference'] - entry['ci95'][0]], [entry['ci95'][1] - entry['difference']]],
                    fmt='o', color=BLUE, capsize=2, capthick=0.9, elinewidth=1.0, markersize=4)
        ax.errorbar(entry['poor_or_worse_difference'], y - 0.16,
                    xerr=[[entry['poor_or_worse_difference'] - entry['poor_or_worse_ci95'][0]],
                          [entry['poor_or_worse_ci95'][1] - entry['poor_or_worse_difference']]],
                    fmt='D', color=RED, capsize=2, capthick=0.9, elinewidth=1.0, markersize=3.6)
    ax.axvline(0, color=INK, lw=0.6, ls=(0, (3, 2)))
    ax.set_yticks(range(4)), ax.set_yticklabels([l[1] for l in levels[::-1]], linespacing=0.9)
    ax.set_ylim(-0.6, 3.75), ax.set_xlim(-0.8, 15.5)
    ax.set_xlabel('MAE increase when excluded (AQI)')
    light_grid(ax, 'x')
    ax.plot([], [], 'o', color=BLUE, label=f"all pairs ({spatial['city']['n_exact']:,})")
    ax.plot([], [], 'D', color=RED, markersize=3.6, label=f"Poor or worse ({spatial['city']['poor_or_worse_n']:,})")
    ax.legend(loc='upper right', handletextpad=0.2, borderaxespad=0.15, labelspacing=0.25)
    panel_title(ax, 'a', 'Geographic exclusion')
    ax.title.set_position((-0.33, 1.0))

    ax = axes[1]
    cats = ['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor']
    short = ['Good', 'Satis.', 'Moder.', 'Poor', 'V. poor']
    for name in ('climatology', 'ridge_strict', 'persistence', 'ridge_history'):
        style = MODEL[name]
        ax.plot(range(5), [N['by_observed_category'][c][name]['bias'] for c in cats], color=style['color'], marker=style['marker'],
                ls=style['ls'], label=style['label'], markerfacecolor='white' if name in ('climatology', 'persistence') else style['color'],
                markeredgewidth=0.9)
    ax.axhline(0, color=INK, lw=0.6, ls=(0, (3, 2)))
    ax.set_xticks(range(5)), ax.set_xticklabels(short, linespacing=0.9)
    ax.set_ylim(-230, 75), ax.set_yticks([-200, -150, -100, -50, 0, 50])
    ax.set_ylabel('Mean bias (AQI units)', labelpad=1)
    ax.set_xlabel('Observed category')
    light_grid(ax)
    ax.legend(loc='lower left', handlelength=1.9, borderaxespad=0.15, labelspacing=0.22)
    panel_title(ax, 'b', 'Bias by observed category')

    ax = axes[2]
    severe = rows[rows.censored]
    assert len(severe) == N['severe']['ridge_strict']['n'] == 363
    for name in ('ridge_strict', 'ridge_history', 'persistence'):
        values = np.sort(severe[name].dropna().to_numpy())
        style = MODEL[name]
        ax.step(np.concatenate([[0], values, [560]]), np.concatenate([[0], np.arange(1, len(values) + 1) / len(values) * 100, [100]]),
                where='post', color=style['color'], lw=1.2)
    ax.axvline(401, color=INK, lw=0.8, ls=(0, (3, 2)))
    for edge in (200, 300):
        ax.axvline(edge, color='#c8c8c8', lw=0.5, zorder=0)
    ax.text(426, 89, f"Weather Ridge\n($n$ = {N['severe']['ridge_strict']['n']})", color=BLUE, fontsize=7.3, ha='left', va='center', linespacing=0.95)
    ax.text(426, 65, f"History Ridge\n($n$ = {N['severe']['ridge_history']['n']})", color=RED, fontsize=7.3, ha='left', va='center', linespacing=0.95)
    ax.text(426, 41, f"Persistence\n($n$ = {N['severe']['persistence']['n']})", color=GREEN, fontsize=7.3, ha='left', va='center', linespacing=0.95)
    ax.text(426, 13, 'Severe lower\nbound: 401', color=INK, fontsize=7.3, ha='left', va='center', linespacing=0.95)
    ax.set_xlim(0, 608), ax.set_ylim(0, 102), ax.set_yticks([0, 25, 50, 75, 100]), ax.set_xticks([0, 100, 200, 300, 401])
    ax.set_xlabel('Forecast on censored Severe days (AQI)')
    ax.set_ylabel('Cumulative share (%)', labelpad=1)
    panel_title(ax, 'c', 'Forecasts on censored Severe days')
    save(fig, 'fig4_transfer_severe')


# ----------------------------------------------------------------------------- Fig. 5
def figure_uncertainty_warning():
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 1.76), gridspec_kw=dict(width_ratios=[1.0, 1.08, 1.02], wspace=0.33,
                                                                              left=0.058, right=0.995, top=0.865, bottom=0.245))
    unc = N['uncertainty_rows']
    ax = axes[0]
    x = np.arange(1, 13)
    for key, color, marker, label, face in (('split_0.8', LIGHT, 's', 'Split 80%', 'white'), ('split_0.9', BLUE, 'o', 'Split 90%', BLUE),
                                            ('cqr_0.9', GREEN, '^', 'CQR 90%', 'white')):
        ax.plot(x, [unc[key]['by_fold'][f'fold_{i:02d}']['coverage'] * 100 for i in x], color=color, marker=marker, label=label,
                markerfacecolor=face, markeredgewidth=0.9)
    ax.axhline(90, color=BLUE, lw=0.6, ls=(0, (3, 2))), ax.axhline(80, color=LIGHT, lw=0.6, ls=(0, (3, 2)))
    ax.set_xticks(x), ax.set_xticklabels(MONTHS, rotation=90)
    ax.set_ylim(50, 100), ax.set_yticks([50, 60, 70, 80, 90, 100])
    ax.set_ylabel('Empirical coverage (%)', labelpad=1), ax.set_xlabel('Evaluation month, 2025–26')
    light_grid(ax)
    ax.legend(loc='lower right', handlelength=1.8, borderaxespad=0.1, labelspacing=0.22)
    panel_title(ax, 'a', 'Marginal coverage by fold')

    ax = axes[1]
    cats = ['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor']
    for offset, (key, color, marker, label, face) in zip((-0.22, 0, 0.22), (('split_0.9', BLUE, 'o', 'Split', BLUE),
                                                                           ('mondrian_0.9', GREY, 's', 'Mondrian', 'white'),
                                                                           ('cqr_0.9', GREEN, '^', 'CQR', 'white'))):
        values = [unc[key]['by_category'][c] for c in cats]
        cov = np.array([v['coverage'] * 100 for v in values])
        lo = np.array([v['coverage_ci95'][0] * 100 for v in values])
        hi = np.array([v['coverage_ci95'][1] * 100 for v in values])
        ax.errorbar(np.arange(5) + offset, cov, yerr=[cov - lo, hi - cov], fmt=marker, color=color, markerfacecolor=face, capsize=1.6,
                    capthick=0.8, elinewidth=0.9, markersize=3.8, markeredgewidth=0.9, label=label)
    ax.axhline(90, color=INK, lw=0.6, ls=(0, (3, 2)))
    ax.text(4.42, 91.5, 'nominal 90%', ha='right', va='bottom', fontsize=7.2)
    ax.set_xticks(range(5))
    ax.set_xticklabels([f"{s}\n{unc['split_0.9']['by_category'][c]['n']:,}" for s, c in zip(['Good', 'Satis.', 'Moder.', 'Poor', 'V. poor'], cats)],
                       linespacing=0.95)
    ax.set_ylim(0, 104), ax.set_yticks([0, 25, 50, 75, 100]), ax.set_xlim(-0.5, 4.5)
    ax.set_xlabel('Observed category and exact pairs', labelpad=2)
    light_grid(ax)
    ax.legend(loc='lower left', handletextpad=0.2, borderaxespad=0.15, labelspacing=0.22)
    panel_title(ax, 'b', '90% coverage by observed category')

    ax = axes[2]
    w = N['warnings_rows']
    quantiles = ['0.5', '0.65', '0.75', '0.85', '0.9', '0.95', '0.975']
    over = [w['raw_quantiles'][q]['over'] * 100 for q in quantiles]
    under = [w['raw_quantiles'][q]['under'] * 100 for q in quantiles]
    ax.plot(over, under, color=GREY, marker='o', markerfacecolor='white', markeredgewidth=0.9, label=r'Raw quantile $\tau$', zorder=2)
    offsets = {'0.5': (2.0, 1.3, 'left'), '0.65': (2.0, 1.2, 'left'), '0.75': (-2.0, -1.5, 'right'), '0.85': (2.2, 1.4, 'left'),
               '0.9': (2.0, 1.3, 'left'), '0.95': (-1.0, 2.4, 'center'), '0.975': (-1.5, 2.5, 'center')}
    for q, xo, yu in zip(quantiles, over, under):
        ax.text(xo + offsets[q][0], yu + offsets[q][1], q, fontsize=7.0, color=GREY, ha=offsets[q][2], va='center')
    for key, color, marker, label in (('P0', BLUE, 'o', 'P0 point'), ('P1', GREEN, '^', 'P1 median'), ('P2', RED, 'D', 'P2 0.75 quantile')):
        entry = w[key]
        ax.errorbar(entry['over'] * 100, entry['under'] * 100,
                    xerr=[[(entry['over'] - entry['over_ci95'][0]) * 100], [(entry['over_ci95'][1] - entry['over']) * 100]],
                    yerr=[[(entry['under'] - entry['under_ci95'][0]) * 100], [(entry['under_ci95'][1] - entry['under']) * 100]],
                    fmt=marker, color=color, capsize=1.6, capthick=0.8, elinewidth=0.9, markersize=4.2, label=label, zorder=3)
    ax.set_xlim(15, 92), ax.set_ylim(0, 35), ax.set_yticks([0, 10, 20, 30])
    ax.set_xlabel('Over-warning (%)'), ax.set_ylabel('Under-warning (%)', labelpad=1)
    light_grid(ax, 'both')
    ax.legend(loc='upper right', handletextpad=0.3, borderaxespad=0.1, labelspacing=0.22)
    panel_title(ax, 'c', f"Warning losses ($n$ = {w['P0']['n']:,})")
    save(fig, 'fig5_uncertainty_warning')


if __name__ == '__main__':
    figure_architecture()
    figure_timeline()
    figure_rq1()
    figure_rq2_severe()
    figure_uncertainty_warning()
