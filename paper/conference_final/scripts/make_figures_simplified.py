"""Redraw Figs. 3-5 in the simplified camera-ready layout.

Fig. 3: one single-column forest plot of the four paired contrasts.
Fig. 4: two panels, geographic exclusion and censored Severe forecasts.
Fig. 5: two panels, interval coverage by observed category and the warning trade-off.

Values come from evidence/verified_numbers.json and evidence/rows_temporal.parquet,
the same files the manuscript macros are generated from. Figs. 1 and 2 are untouched.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
N = json.loads((BASE / 'evidence' / 'verified_numbers.json').read_text())
FIGURES = BASE / 'figures'
TEXT, COLUMN = 7.14, 3.44
INK, BLUE, RED, GREEN, GREY = '#1a1a1a', '#1b5a8e', '#c4501b', '#2f7d5b', '#6e6e6e'

plt.rcParams.update({
    'font.family': 'serif', 'font.serif': ['Times New Roman', 'Nimbus Roman', 'DejaVu Serif'],
    'mathtext.fontset': 'stix', 'font.size': 8, 'axes.labelsize': 8, 'axes.titlesize': 8.5,
    'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 7.5, 'axes.linewidth': 0.6,
    'xtick.major.width': 0.6, 'ytick.major.width': 0.6, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
    'lines.linewidth': 1.1, 'lines.markersize': 4, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': INK, 'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': INK, 'text.color': INK,
    'legend.frameon': False, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'figure.dpi': 150})


def save(fig, name):
    fig.savefig(FIGURES / f'{name}.pdf')
    fig.savefig(FIGURES / f'{name}.png', dpi=300)
    plt.close(fig)
    print('wrote', name)


def grid(ax, axis='y'):
    ax.grid(axis=axis, color='#d9d9d9', linewidth=0.4, zorder=0)
    ax.set_axisbelow(True)


def figure_forest():
    fig, ax = plt.subplots(figsize=(COLUMN, 1.52),
                           gridspec_kw=dict(left=0.455, right=0.985, top=0.97, bottom=0.235))
    rows = [('ridge_strict_vs_climatology', 'Weather Ridge $-$ climatology', BLUE),
            ('weather_ablation', 'Weather Ridge $-$ calendar Ridge', BLUE),
            ('history_ablation_conditional', 'History Ridge $-$ weather Ridge', RED),
            ('ridge_history_vs_persistence', 'History Ridge $-$ persistence', RED)]
    for y, (key, label, color) in enumerate(rows[::-1]):
        e = N['paired'][key]
        crosses = e['ci95'][0] < 0 < e['ci95'][1]
        ax.errorbar(e['mae_difference'], y,
                    xerr=[[e['mae_difference'] - e['ci95'][0]], [e['ci95'][1] - e['mae_difference']]],
                    fmt='o', color=color, capsize=2.4, capthick=0.9, elinewidth=1.1, markersize=4.4,
                    markerfacecolor='white' if crosses else color, markeredgewidth=1.0)
        right = e['mae_difference'] < -5
        ax.text(e['ci95'][1] + 0.8 if right else e['ci95'][0] - 0.8, y + 0.04,
                f"{e['mae_difference']:+.2f}".replace('-', '−'), va='center',
                ha='left' if right else 'right', fontsize=7.5, color=color)
    ax.axvline(0, color=INK, lw=0.7, ls=(0, (3, 2)))
    ax.set_yticks(range(4)), ax.set_yticklabels([r[1] for r in rows[::-1]])
    ax.set_ylim(-0.65, 3.65), ax.set_xlim(-23, 5)
    ax.set_xlabel('Paired MAE difference (AQI units)', labelpad=2)
    grid(ax, 'x')
    save(fig, 'fig3_rq1')


def figure_transfer_severe():
    rows = pd.read_parquet(BASE / 'evidence' / 'rows_temporal.parquet')
    severe = rows[rows.censored]
    fig, axes = plt.subplots(1, 2, figsize=(TEXT, 2.02), gridspec_kw=dict(
        width_ratios=[1.0, 1.12], wspace=0.22, left=0.088, right=0.995, top=0.875, bottom=0.185))
    ax = axes[0]
    levels = [('station_id', 'Station'), ('city', 'City'), ('cluster', 'Urban cluster'), ('region', 'Region')]
    s = N['spatial_rows']
    for y, (key, _) in enumerate(levels[::-1]):
        e = s[key]
        ax.errorbar(e['difference'], y + 0.17,
                    xerr=[[e['difference'] - e['ci95'][0]], [e['ci95'][1] - e['difference']]],
                    fmt='o', color=BLUE, capsize=2.2, capthick=0.9, elinewidth=1.1, markersize=4.4)
        ax.errorbar(e['poor_or_worse_difference'], y - 0.17,
                    xerr=[[e['poor_or_worse_difference'] - e['poor_or_worse_ci95'][0]],
                          [e['poor_or_worse_ci95'][1] - e['poor_or_worse_difference']]],
                    fmt='D', color=RED, capsize=2.2, capthick=0.9, elinewidth=1.1, markersize=4)
    ax.axvline(0, color=INK, lw=0.7, ls=(0, (3, 2)))
    ax.set_yticks(range(4)), ax.set_yticklabels([l[1] for l in levels[::-1]])
    ax.set_ylim(-0.7, 3.8), ax.set_xlim(-0.9, 16)
    ax.set_xlabel('MAE increase when the location is withheld (AQI units)', labelpad=2)
    grid(ax, 'x')
    ax.plot([], [], 'o', color=BLUE, label=f"all exact pairs ({s['city']['n_exact']:,})")
    ax.plot([], [], 'D', color=RED, markersize=4, label=f"Poor or worse ({s['city']['poor_or_worse_n']:,})")
    ax.legend(loc='upper right', handletextpad=0.3, borderaxespad=0.2, labelspacing=0.3)
    ax.set_title('(a) Geographic exclusion', loc='left', fontweight='bold', pad=5)

    ax = axes[1]
    for name, color, label in (('ridge_strict', BLUE, 'Weather Ridge'), ('ridge_history', RED, 'History Ridge'),
                               ('persistence', GREEN, 'Persistence')):
        values = np.sort(severe[name].dropna().to_numpy())
        ax.step(np.concatenate([[0], values, [620]]),
                np.concatenate([[0], np.arange(1, len(values) + 1) / len(values) * 100, [100]]),
                where='post', color=color, lw=1.3, label=f'{label} ($n$ = {len(values)})')
    ax.axvline(401, color=INK, lw=0.9, ls=(0, (3, 2)))
    ax.text(14, 84, 'Severe lower\nbound: 401', fontsize=7.4, ha='left', va='center', linespacing=0.95)
    ax.set_xlim(0, 700), ax.set_ylim(0, 102)
    ax.set_xticks([0, 100, 200, 300, 401]), ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xlabel('Forecast on censored Severe days (AQI units)', labelpad=2)
    ax.set_ylabel('Cumulative share (%)', labelpad=2)
    ax.legend(loc='lower right', handlelength=1.6, borderaxespad=0.3, labelspacing=0.3)
    ax.set_title('(b) Forecasts on censored Severe days', loc='left', fontweight='bold', pad=5)
    save(fig, 'fig4_transfer_severe')


def figure_reliability():
    unc, w = N['uncertainty_rows'], N['warnings_rows']
    fig, axes = plt.subplots(1, 2, figsize=(TEXT, 2.02), gridspec_kw=dict(
        width_ratios=[1.12, 1.0], wspace=0.2, left=0.072, right=0.995, top=0.875, bottom=0.21))
    ax = axes[0]
    cats = ['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor']
    for offset, (key, color, marker, label, face) in zip((-0.16, 0.16), (('split_0.9', BLUE, 'o', 'Split conformal', BLUE),
                                                                        ('cqr_0.9', GREEN, '^', 'CQR', 'white'))):
        values = [unc[key]['by_category'][c] for c in cats]
        cov = np.array([v['coverage'] * 100 for v in values])
        lo = np.array([v['coverage_ci95'][0] * 100 for v in values])
        hi = np.array([v['coverage_ci95'][1] * 100 for v in values])
        ax.errorbar(np.arange(5) + offset, cov, yerr=[cov - lo, hi - cov], fmt=marker, color=color,
                    markerfacecolor=face, capsize=2, capthick=0.9, elinewidth=1.0, markersize=4.6,
                    markeredgewidth=1.0, label=label)
    ax.axhline(90, color=INK, lw=0.7, ls=(0, (3, 2)))
    ax.text(4.45, 92, 'nominal 90%', ha='right', va='bottom', fontsize=7.4)
    ax.set_xticks(range(5))
    ax.set_xticklabels([f"{s}\n{unc['split_0.9']['by_category'][c]['n']:,}" for s, c in
                        zip(['Good', 'Satis.', 'Moder.', 'Poor', 'V. poor'], cats)], linespacing=1.0)
    ax.set_ylim(0, 105), ax.set_yticks([0, 25, 50, 75, 100]), ax.set_xlim(-0.5, 4.5)
    ax.set_xlabel('Observed category and number of exact pairs', labelpad=2)
    ax.set_ylabel('Empirical coverage (%)', labelpad=2)
    grid(ax)
    ax.legend(loc='lower left', handletextpad=0.3, borderaxespad=0.25, labelspacing=0.3)
    ax.set_title('(a) Coverage of nominal 90% intervals', loc='left', fontweight='bold', pad=5)

    ax = axes[1]
    quantiles = ['0.5', '0.65', '0.75', '0.85', '0.9', '0.95', '0.975']
    over = [w['raw_quantiles'][q]['over'] * 100 for q in quantiles]
    under = [w['raw_quantiles'][q]['under'] * 100 for q in quantiles]
    ax.plot(over, under, color=GREY, marker='o', markersize=3.4, markerfacecolor='white', markeredgewidth=0.9,
            label=r'Raw quantile level $\tau$', zorder=2)
    for q, x, y in zip(quantiles, over, under):
        dx, dy, ha = (-2.0, 2.6, 'center') if q == '0.75' else (1.8, 1.3, 'left')
        ax.text(x + dx, y + dy, q, fontsize=7.0, color=GREY, ha=ha, va='center')
    for key, color, marker, label in (('P0', BLUE, 'o', 'P0: point forecast'), ('P1', GREEN, '^', 'P1: calibrated median'),
                                      ('P2', RED, 'D', 'P2: 0.75 quantile')):
        e = w[key]
        ax.errorbar(e['over'] * 100, e['under'] * 100,
                    xerr=[[(e['over'] - e['over_ci95'][0]) * 100], [(e['over_ci95'][1] - e['over']) * 100]],
                    yerr=[[(e['under'] - e['under_ci95'][0]) * 100], [(e['under_ci95'][1] - e['under']) * 100]],
                    fmt=marker, color=color, capsize=2, capthick=0.9, elinewidth=1.0, markersize=4.8, label=label, zorder=3)
    ax.set_xlim(15, 95), ax.set_ylim(0, 34), ax.set_yticks([0, 10, 20, 30])
    ax.set_xlabel('Over-warning (%)', labelpad=2), ax.set_ylabel('Under-warning (%)', labelpad=2)
    grid(ax, 'both')
    ax.legend(loc='upper right', handletextpad=0.3, borderaxespad=0.25, labelspacing=0.3)
    ax.set_title(f"(b) Warning losses ($n$ = {w['P0']['n']:,})", loc='left', fontweight='bold', pad=5)
    save(fig, 'fig5_uncertainty_warning')


if __name__ == '__main__':
    figure_forest()
    figure_transfer_severe()
    figure_reliability()
