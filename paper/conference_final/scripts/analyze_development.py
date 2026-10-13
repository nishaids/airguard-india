"""Recompute every manuscript number from development artifacts only.

Inputs
------
1. Frozen run  results/research/preliminary/<run>/results.json  and  predictions.csv
   (committed; last represented date 2026-06-15).
2. Row-level reproduction  paper/conference_final/evidence/rows_{temporal,spatial}.parquet
   written by reproduce_development.py, usable only if that script certified an
   exact match with the frozen fold summaries.

No sealed-period row is read. Output: evidence/verified_numbers.json plus the
LaTeX number macros in tables/numbers.tex.

Run from the repository root:
    .venv-live/Scripts/python.exe paper/conference_final/scripts/analyze_development.py
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.calibration.metrics import LABELS, bands  # noqa: E402
from src.research.calibration.statistics import holm, paired  # noqa: E402

BASE = ROOT / 'paper' / 'conference_final'
EVIDENCE = BASE / 'evidence'
RUN = '287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f'
RUN_DIR = ROOT / 'results' / 'research' / 'preliminary' / RUN
SEALED_START = date(2026, 7, 10)
QUANTILE_COLUMNS = {.5: 'q500', .65: 'q650', .75: 'q750', .85: 'q850', .9: 'q900', .95: 'q950', .975: 'q975'}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def errors(frame, column):
    exact = frame[~frame.censored]
    error = exact[column] - exact.y_aqi
    return {'n': int(len(exact)), 'mae': float(error.abs().mean()), 'rmse': float(math.sqrt((error ** 2).mean())),
            'bias': float(error.mean())}


def block_ci(frame, value, block=7, repetitions=5000, seed=42):
    """Moving calendar-block bootstrap of a ratio-of-sums mean, pairs kept within dates."""
    dates = pd.to_datetime(frame.target_date)
    calendar = pd.date_range(dates.min(), dates.max(), freq='D')
    daily = frame.assign(_d=dates.values, _v=value.values).groupby('_d')._v.agg(['sum', 'count']).reindex(calendar, fill_value=0)
    sums, counts = daily['sum'].to_numpy(), daily['count'].to_numpy()
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, len(sums) - block + 1, size=(repetitions, math.ceil(len(sums) / block)))
    index = (starts[:, :, None] + np.arange(block)).reshape(repetitions, -1)[:, :len(sums)]
    denominator = counts[index].sum(axis=1)
    estimates = sums[index].sum(axis=1)[denominator > 0] / denominator[denominator > 0]
    return [float(v) for v in np.quantile(estimates, [.025, .975])]


def weighted(values, weights):
    values, weights = np.asarray(values, float), np.asarray(weights, float)
    return float((values * weights).sum() / weights.sum())


def main():
    frozen = json.loads((RUN_DIR / 'results.json').read_text())
    out = {'run_id': RUN, 'results_sha256': sha256(RUN_DIR / 'results.json'),
           'predictions_sha256': sha256(RUN_DIR / 'predictions.csv'),
           'dataset_hash': frozen['dataset_hash'], 'protocol_sha256': frozen['protocol_sha256'],
           'git_sha': frozen['git_sha'], 'final_test_range': frozen['final_test_range'],
           'final_test_scored': frozen['final_test_scored']}

    # ------------------------------------------------------------------ saved predictions
    pred = pd.read_csv(RUN_DIR / 'predictions.csv')
    pred['target_date'] = pd.to_datetime(pred.target_date).dt.date
    assert pred.target_date.max() < SEALED_START
    exact = pred[~pred.censored]
    severe = pred[pred.censored]
    out['population'] = {'rows': int(len(pred)), 'exact': int(len(exact)), 'censored_severe': int(len(severe)),
                         'stations': int(pred.station_id.nunique()), 'cities': int(pred.city.nunique()),
                         'dates': int(pred.target_date.nunique()), 'first_date': str(pred.target_date.min()),
                         'last_date': str(pred.target_date.max()), 'folds': int(pred.fold.nunique())}
    history = pred.dropna(subset=['persistence', 'ridge_history'])
    out['history_population'] = {'rows': int(len(history)), 'exact': int((~history.censored).sum()),
                                 'censored_severe': int(history.censored.sum()),
                                 'stations': int(history.station_id.nunique()), 'dates': int(history.target_date.nunique())}
    out['point'] = {name: errors(pred, name) for name in ('climatology', 'ridge_calendar_spatial', 'ridge_strict')}
    out['point_history'] = {name: errors(history, name) for name in
                            ('climatology', 'ridge_strict_same_training', 'persistence', 'ridge_history')}
    # Date-weighted sensitivity: each represented date counts once.
    daily = exact.assign(a=(exact.ridge_strict - exact.y_aqi).abs(), c=(exact.climatology - exact.y_aqi).abs()) \
        .groupby('target_date')[['a', 'c']].mean()
    out['date_weighted_mae'] = {'ridge_strict': float(daily.a.mean()), 'climatology': float(daily.c.mean())}

    comparisons = {'ridge_strict_vs_climatology': paired(pred, 'ridge_strict', 'climatology'),
                   'weather_ablation': paired(pred, 'ridge_strict', 'ridge_calendar_spatial'),
                   'ridge_history_vs_persistence': paired(history, 'ridge_history', 'persistence'),
                   'history_ablation_conditional': paired(history, 'ridge_history', 'ridge_strict_same_training')}
    holm(comparisons)
    out['paired'] = comparisons
    out['paired_matches_frozen'] = {
        key: bool(abs(value['mae_difference'] - frozen['paired_comparisons'][key]['mae_difference']) < 1e-9
                  and np.allclose(value['ci95'], frozen['paired_comparisons'][key]['ci95'], atol=1e-9))
        for key, value in comparisons.items()}
    out['block_length_sensitivity'] = {}
    for key, (frame, first, second) in {'ridge_strict_vs_climatology': (pred, 'ridge_strict', 'climatology'),
                                        'weather_ablation': (pred, 'ridge_strict', 'ridge_calendar_spatial'),
                                        'ridge_history_vs_persistence': (history, 'ridge_history', 'persistence'),
                                        'history_ablation_conditional': (history, 'ridge_history', 'ridge_strict_same_training')}.items():
        out['block_length_sensitivity'][key] = {str(block): paired(frame, first, second, block=block)['ci95']
                                               for block in (3, 7, 14, 28)}

    folds = []
    for name, group in pred.groupby('fold'):
        e = group[~group.censored]
        h = group.dropna(subset=['persistence', 'ridge_history'])
        he = h[~h.censored]
        folds.append({'fold': name, 'first': str(group.target_date.min()), 'last': str(group.target_date.max()),
                      'n_exact': int(len(e)), 'n_censored': int(group.censored.sum()),
                      'stations': int(group.station_id.nunique()), 'mean_observed_exact': float(e.y_aqi.mean()),
                      'mae_climatology': float((e.climatology - e.y_aqi).abs().mean()),
                      'mae_ridge_strict': float((e.ridge_strict - e.y_aqi).abs().mean()),
                      'bias_ridge_strict': float((e.ridge_strict - e.y_aqi).mean()),
                      'n_history_exact': int(len(he)),
                      'mae_persistence': float((he.persistence - he.y_aqi).abs().mean()),
                      'mae_ridge_history': float((he.ridge_history - he.y_aqi).abs().mean())})
    out['folds'] = folds
    out['folds_ridge_worse_than_climatology'] = [f['fold'] for f in folds if f['mae_ridge_strict'] > f['mae_climatology']]
    out['folds_history_worse_than_persistence'] = [f['fold'] for f in folds if f['mae_ridge_history'] > f['mae_persistence']]

    # Severity-conditioned point behaviour (observed category).
    by_category = {}
    for index, label in enumerate(LABELS):
        rows = exact[exact.y_category == index]
        hist_rows = history[(history.y_category == index) & ~history.censored]
        entry = {'n': int(len(rows)), 'n_history': int(len(hist_rows))}
        for name in ('climatology', 'ridge_strict'):
            if len(rows):
                entry[name] = {'mae': float((rows[name] - rows.y_aqi).abs().mean()), 'bias': float((rows[name] - rows.y_aqi).mean()),
                               'under_category': float((bands(rows[name]) < index).mean())}
        for name in ('persistence', 'ridge_history'):
            if len(hist_rows):
                entry[name] = {'mae': float((hist_rows[name] - hist_rows.y_aqi).abs().mean()),
                               'bias': float((hist_rows[name] - hist_rows.y_aqi).mean()),
                               'under_category': float((bands(hist_rows[name]) < index).mean())}
        by_category[label] = entry
    out['by_observed_category'] = by_category

    # Category confusion (rows observed, columns forecast) for the weather Ridge, all 38,745 outcomes.
    issued = bands(pred.ridge_strict)
    observed = pred.y_category.astype(int).to_numpy()
    confusion = np.zeros((6, 6), int)
    np.add.at(confusion, (observed, issued), 1)
    out['confusion_ridge_strict'] = {'labels': list(LABELS), 'rows_observed_columns_forecast': confusion.tolist()}
    high = observed >= 3
    out['poor_or_worse'] = {'events': int(high.sum()), 'lower_category_issued': int((issued[high] < observed[high]).sum()),
                            'forecast_reaches_poor': int((issued[high] >= 3).sum()),
                            'false_alarms_poor': int(((issued >= 3) & ~high).sum())}
    very = observed >= 4
    out['very_poor_or_worse'] = {'events': int(very.sum()), 'forecast_reaches_very_poor': int((issued[very] >= 4).sum())}

    # Censored Severe outcomes: lower bound 401, never an exact value.
    def severe_summary(frame, column):
        values = frame[column].dropna().to_numpy()
        return {'n': int(len(values)), 'below_401': int((values < 401).sum()), 'max_forecast': float(values.max()),
                'median_forecast': float(np.median(values)), 'mean_shortfall': float(np.clip(401 - values, 0, None).mean()),
                'reaches_very_poor': int((values > 300).sum()), 'reaches_poor': int((values > 200).sum())}
    out['severe'] = {name: severe_summary(severe, name) for name in
                     ('climatology', 'ridge_calendar_spatial', 'ridge_strict', 'persistence', 'ridge_history')}
    out['severe']['folds_represented'] = int(severe.fold.nunique())
    out['severe']['stations'] = int(severe.station_id.nunique())
    out['severe']['cities'] = int(severe.city.nunique())
    out['severe']['dates'] = int(severe.target_date.nunique())
    out['severe']['history_available'] = int(severe.persistence.notna().sum())

    # ------------------------------------------------------------------ frozen fold summaries
    unc = frozen['uncertainty']
    pooled = {}
    for method in ('split_0.8', 'split_0.9', 'mondrian_0.9', 'cqr_0.9'):
        rows = [unc[f][method] for f in sorted(unc) if method in unc[f]]
        n_exact = [r['n_exact'] for r in rows]
        n_all = [r['n_exact'] + r['n_censored'] for r in rows]
        pooled[method] = {'folds': len(rows), 'n_exact': int(sum(n_exact)),
                          'coverage': weighted([r['coverage_exact'] for r in rows], n_exact),
                          'mean_width': weighted([r['mean_width'] for r in rows], n_all),
                          'fold_min': float(min(r['coverage_exact'] for r in rows)),
                          'fold_max': float(max(r['coverage_exact'] for r in rows)),
                          'abstained': int(sum(r.get('abstained_rows', 0) for r in rows)),
                          'by_fold': {f: unc[f][method]['coverage_exact'] for f in sorted(unc) if method in unc[f]}}
    out['uncertainty_frozen'] = pooled
    out['fold_01_very_poor'] = {m: unc['fold_01'][m]['y_category']['4.0'] for m in ('split_0.8', 'split_0.9', 'mondrian_0.9', 'cqr_0.9')}
    adv = frozen['advisory']
    advisory = {}
    for policy in ('P0', 'P1', 'P2', 'P3_target_0.1', 'P3_target_0.05'):
        rows = [adv[f][policy] for f in sorted(adv) if adv[f][policy].get('n')]
        n = [r['n'] for r in rows]
        advisory[policy] = {'folds': len(rows), 'n': int(sum(n)),
                            'under': weighted([r['under_warning'] for r in rows], n),
                            'over': weighted([r['over_warning'] for r in rows], n),
                            'serious_under': weighted([r['serious_under_warning'] for r in rows], n)}
    out['advisory_frozen'] = advisory
    spatial = {}
    for group in ('station_id', 'city', 'cluster', 'region'):
        rows = [s for s in frozen['spatial'] if s['group'] == group and 'ridge_strict' in s]
        n = [s['ridge_strict']['n_exact'] for s in rows]
        spatial[group] = {'holdouts': len(rows), 'n_exact': int(sum(n)), 'n_censored': int(sum(s['ridge_strict']['n_censored_severe'] for s in rows)),
                          'mae_holdout': weighted([s['ridge_strict']['mae'] for s in rows], n),
                          'mae_reference': weighted([s['reference_same_rows']['mae'] for s in rows], n)}
    out['spatial_frozen'] = spatial
    sliding = [f for f in frozen['folds'] if f['design'] == 'sliding_90d' and 'strict' in f]
    expanding = [f for f in frozen['folds'] if f['design'] == 'expanding' and 'strict' in f]
    out['training_window_sensitivity'] = {
        design: {name: weighted([f['strict'][name]['mae'] for f in rows], [f['strict'][name]['n_exact'] for f in rows])
                 for name in ('climatology', 'ridge_strict')}
        for design, rows in (('expanding', expanding), ('sliding_90d', sliding))}
    out['season_frozen'] = {k: {'n': v['n'], 'mae': v['metrics']['mae'], 'bias': v['metrics']['bias']}
                            for k, v in frozen['subgroups']['season'].items() if v['metrics']}
    out['region_frozen'] = {k: {'n': v['n'], 'mae': v['metrics']['mae'], 'bias': v['metrics']['bias']}
                            for k, v in frozen['subgroups']['region'].items() if v['metrics']}

    # ------------------------------------------------------------------ row-level reproduction
    report_path = EVIDENCE / 'reproduction_report.json'
    if report_path.exists() and json.loads(report_path.read_text())['reproduces_frozen_artifact']:
        report = json.loads(report_path.read_text())
        out['reproduction'] = {k: report[k] for k in ('checks_compared', 'max_abs_difference_from_frozen', 'tolerance',
                                                      'reproduces_frozen_artifact', 'ledger', 'spatial_train_range',
                                                      'spatial_test_range', 'final_test_accessed')}
        out['reproduction']['fold_meta'] = report['folds']
        rows = pd.read_parquet(EVIDENCE / 'rows_temporal.parquet')
        rows['target_date'] = pd.to_datetime(rows.target_date).dt.date
        assert rows.target_date.max() < SEALED_START and len(rows) == len(pred)
        ex = rows[~rows.censored]
        coverage = {}
        for method, (lo, hi, nominal) in {'split_0.8': ('split80_lo', 'split80_hi', .8), 'split_0.9': ('split90_lo', 'split90_hi', .9),
                                          'mondrian_0.9': ('mondrian90_lo', 'mondrian90_hi', .9), 'cqr_0.9': ('cqr90_lo', 'cqr90_hi', .9)}.items():
            issued_rows = ex[ex[lo].notna()]
            covered = ((issued_rows[lo] <= issued_rows.y_aqi) & (issued_rows.y_aqi <= issued_rows[hi])).astype(float)
            every = rows[rows[lo].notna()]
            entry = {'nominal': nominal, 'n_exact': int(len(issued_rows)), 'coverage': float(covered.mean()),
                     'coverage_ci95': block_ci(issued_rows, covered),
                     'mean_width': float((every[hi] - every[lo]).mean()), 'median_width': float((every[hi] - every[lo]).median()),
                     'withheld': int(rows[lo].isna().sum()), 'by_category': {}, 'by_fold': {}, 'by_season': {}, 'by_region': {}}
            for index, label in enumerate(LABELS[:5]):
                mask = issued_rows.y_category == index
                entry['by_category'][label] = {'n': int(mask.sum()), 'covered': int(covered[mask].sum()),
                                               'coverage': float(covered[mask].mean()) if mask.sum() else None,
                                               'coverage_ci95': block_ci(issued_rows[mask], covered[mask]) if mask.sum() >= 30 else None,
                                               'mean_width': float((issued_rows.loc[mask, hi] - issued_rows.loc[mask, lo]).mean()) if mask.sum() else None,
                                               'above_upper': int((issued_rows.loc[mask, 'y_aqi'] > issued_rows.loc[mask, hi]).sum()),
                                               'below_lower': int((issued_rows.loc[mask, 'y_aqi'] < issued_rows.loc[mask, lo]).sum())}
            high_mask = issued_rows.y_category >= 3
            entry['poor_or_worse'] = {'n': int(high_mask.sum()), 'covered': int(covered[high_mask].sum()),
                                      'coverage': float(covered[high_mask].mean()),
                                      'coverage_ci95': block_ci(issued_rows[high_mask], covered[high_mask])}
            low_mask = issued_rows.y_category <= 1
            entry['good_or_satisfactory'] = {'n': int(low_mask.sum()), 'coverage': float(covered[low_mask].mean())}
            for name, group in issued_rows.groupby('fold'):
                entry['by_fold'][name] = {'n': int(len(group)), 'coverage': float(covered[group.index].mean())}
            for field in ('season', 'region'):
                for name, group in issued_rows.groupby(field):
                    entry['by_' + field][name] = {'n': int(len(group)), 'coverage': float(covered[group.index].mean())}
            censored_rows = rows[rows.censored & rows[hi].notna()]
            entry['censored_upper_reaches_401'] = {'n': int(len(censored_rows)), 'count': int((censored_rows[hi] >= 401).sum())}
            coverage[method] = entry
        out['uncertainty_rows'] = coverage
        out['uncertainty_rows_match_frozen'] = {m: bool(abs(coverage[m]['coverage'] - pooled[m]['coverage']) < 1e-9) for m in coverage}

        # Warning operating points on identical outcomes (38,745 rows, censored categories included).
        observed = rows.y_category.astype(int).to_numpy()

        def losses(decision):
            cat = bands(decision)
            under, over = (cat < observed).astype(float), (cat > observed).astype(float)
            serious = (cat < observed - 1).astype(float)
            hi_mask = observed >= 3
            return {'n': int(len(cat)), 'under': float(under.mean()), 'over': float(over.mean()),
                    'under_ci95': block_ci(rows, pd.Series(under, index=rows.index)),
                    'over_ci95': block_ci(rows, pd.Series(over, index=rows.index)),
                    'serious_under': float(serious.mean()),
                    'high_pollution_under': float(under[hi_mask].mean()), 'high_pollution_n': int(hi_mask.sum()),
                    'severe_issued_severe': int(((cat == 5) & (observed == 5)).sum())}
        warnings = {'P0': losses(rows.ridge_strict), 'P1': losses(rows.p1), 'P2': losses(rows.p2)}
        warnings['raw_quantiles'] = {str(q): losses(rows[column]) for q, column in QUANTILE_COLUMNS.items()}
        for target, column in ((.1, 'p3_10'), (.05, 'p3_05')):
            feasible = rows[rows[column].notna()]
            cat = bands(feasible[column])
            obs = feasible.y_category.astype(int).to_numpy()
            p0 = bands(feasible.ridge_strict)
            hi_rows = obs >= 3
            warnings[f'P3_{target}'] = {'n': int(len(feasible)), 'folds': int(feasible.fold.nunique()),
                                        'serious_under': float((cat < obs - 1).mean()),
                                        'high_pollution_under': float((cat[hi_rows] < obs[hi_rows]).mean()),
                                        'high_pollution_n': int(hi_rows.sum()),
                                        'infeasible_folds': sorted(set(rows.fold) - set(feasible.fold)),
                                        'under': float((cat < obs).mean()), 'over': float((cat > obs).mean()),
                                        'p0_same_rows_under': float((p0 < obs).mean()), 'p0_same_rows_over': float((p0 > obs).mean()),
                                        'folds_meeting_target': int(sum(((bands(g[column]) < g.y_category).mean() <= target)
                                                                        for _, g in feasible.groupby('fold'))),
                                        'selected_quantiles': {f: float(g[column + '_quantile'].iloc[0]) for f, g in feasible.groupby('fold')}}
        delta_under = (bands(rows.p2) < observed).astype(float) - (bands(rows.ridge_strict) < observed).astype(float)
        delta_over = (bands(rows.p2) > observed).astype(float) - (bands(rows.ridge_strict) > observed).astype(float)
        warnings['P2_minus_P0'] = {'under': float(delta_under.mean()), 'under_ci95': block_ci(rows, pd.Series(delta_under, index=rows.index)),
                                   'over': float(delta_over.mean()), 'over_ci95': block_ci(rows, pd.Series(delta_over, index=rows.index))}
        out['warnings_rows'] = warnings
        out['warnings_rows_match_frozen'] = {p: bool(abs(warnings[p]['under'] - advisory[p]['under']) < 1e-9
                                                     and abs(warnings[p]['over'] - advisory[p]['over']) < 1e-9) for p in ('P0', 'P1', 'P2')}

        # Calibration-to-evaluation shift: the previous fold's evaluation window is this fold's calibration month (offset one day).
        shift = []
        meta = report['folds']
        for name, group in rows.groupby('fold'):
            e = group[~group.censored]
            shift.append({'fold': name, 'split_radius_90': meta[name]['split_radius_90'],
                          'evaluation_q90_abs_error': float((e.ridge_strict - e.y_aqi).abs().quantile(.9)),
                          'coverage_90': float(((e.split90_lo <= e.y_aqi) & (e.y_aqi <= e.split90_hi)).mean()),
                          'mean_observed': float(e.y_aqi.mean())})
        out['calibration_shift'] = shift
        ratio = [s['evaluation_q90_abs_error'] / s['split_radius_90'] for s in shift]
        out['calibration_shift_correlation'] = float(np.corrcoef(ratio, [s['coverage_90'] for s in shift])[0, 1])

        spatial_rows = pd.read_parquet(EVIDENCE / 'rows_spatial.parquet')
        spatial_rows['target_date'] = pd.to_datetime(spatial_rows.target_date).dt.date
        assert spatial_rows.target_date.max() < SEALED_START
        paired_spatial = {}
        for group, frame in spatial_rows.groupby('group'):
            e = frame[~frame.censored]
            delta = (e.holdout_prediction - e.y_aqi).abs() - (e.reference_prediction - e.y_aqi).abs()
            high = e[e.y_category >= 3]
            delta_high = (high.holdout_prediction - high.y_aqi).abs() - (high.reference_prediction - high.y_aqi).abs()
            per_holdout = e.assign(d=delta).groupby('holdout').d.mean()
            paired_spatial[group] = {'n_exact': int(len(e)), 'stations': int(e.station_id.nunique()), 'dates': int(e.target_date.nunique()),
                                     'mae_holdout': float((e.holdout_prediction - e.y_aqi).abs().mean()),
                                     'mae_reference': float((e.reference_prediction - e.y_aqi).abs().mean()),
                                     'difference': float(delta.mean()), 'ci95': block_ci(e, delta),
                                     'relative': float(delta.mean() / (e.reference_prediction - e.y_aqi).abs().mean()),
                                     'holdouts': int(per_holdout.size), 'holdouts_worse': int((per_holdout > 0).sum()),
                                     'holdout_difference_min': float(per_holdout.min()), 'holdout_difference_max': float(per_holdout.max()),
                                     'bias_holdout': float((e.holdout_prediction - e.y_aqi).mean()),
                                     'bias_reference': float((e.reference_prediction - e.y_aqi).mean()),
                                     'poor_or_worse_n': int(len(high)), 'poor_or_worse_difference': float(delta_high.mean()),
                                     'poor_or_worse_ci95': block_ci(high, delta_high)}
            if group == 'region':
                paired_spatial[group]['by_region'] = {
                    name: {'n': int(len(g)), 'mae_holdout': float((g.holdout_prediction - g.y_aqi).abs().mean()),
                           'mae_reference': float((g.reference_prediction - g.y_aqi).abs().mean()),
                           'difference': float(((g.holdout_prediction - g.y_aqi).abs() - (g.reference_prediction - g.y_aqi).abs()).mean())}
                    for name, g in e.groupby('holdout')}
        out['spatial_rows'] = paired_spatial
        out['spatial_rows_match_frozen'] = {g: bool(abs(paired_spatial[g]['mae_holdout'] - spatial[g]['mae_holdout']) < 1e-9
                                                    and abs(paired_spatial[g]['mae_reference'] - spatial[g]['mae_reference']) < 1e-9)
                                            for g in paired_spatial}
        out['row_level_sha256'] = {'rows_temporal': sha256(EVIDENCE / 'rows_temporal.parquet'),
                                   'rows_spatial': sha256(EVIDENCE / 'rows_spatial.parquet')}

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'verified_numbers.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print('written', EVIDENCE / 'verified_numbers.json')


if __name__ == '__main__':
    main()
