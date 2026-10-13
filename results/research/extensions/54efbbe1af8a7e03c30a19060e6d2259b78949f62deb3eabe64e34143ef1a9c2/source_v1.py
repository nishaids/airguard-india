"""Post-paper development extensions. Exploratory; nothing here is selected or deployed.

Four questions the frozen non-CAMS run left open are examined on development
dates only, with the folds, station eligibility and feature lists of that run:

1. Severe tail      - can a persistence-anchored or boosted model keep the extremes?
2. Uncertainty      - do recalibration schemes repair coverage on polluted days?
3. Warning policy   - what operating points exist between missed categories and alerts?
4. Survivorship     - do conclusions change when the cohort is frozen before evaluation?

Rows are filtered by date before they are materialised, so no sealed-period
label is read. The protocol's primary comparison (operational CAMS correction),
the model-selection lock and the final test are untouched: every number written
here is a development estimate from an analysis examined after the paper's
results, and is labelled as such in the output.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
from datetime import date, datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src import config
from src.research.calibration import catalogue, data, metrics, splits
from src.research.calibration.checkpoint import OUT, canonical_hash, write_json
from src.research.calibration.measured import CONDITIONAL_FEATURES, STRICT_FEATURES
from src.research.calibration.preliminary import climatology, eligible, estimator, fit_predict
from src.research.calibration.protocol import load
from src.research.calibration.statistics import finite_quantile, paired

HISTORY_FEATURES = STRICT_FEATURES + CONDITIONAL_FEATURES
LEVEL = 0.9
SEVERE_FLOOR = metrics.SEVERE_FLOOR
QUANTILES = (0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 0.95)
# Fixed before fitting. Leaves and child size are the protocol's fixed ablation
# configuration; the round count is a constant, so nothing is tuned on any fold.
LGBM = dict(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=60, subsample=0.8,
            subsample_freq=1, colsample_bytree=0.8, random_state=42, n_jobs=4, deterministic=True,
            force_col_wise=True, verbose=-1)
PLAN = {
    'experiment': 'NON_CAMS_DEVELOPMENT_EXTENSIONS', 'version': 'development-extensions-v1', 'status': 'EXPLORATORY_POST_PAPER',
    'selection': 'none; no model, interval method or warning rule is selected, locked or deployed here',
    'point_candidates': {
        'persistence': 'AQI of the 24 h ending at the 17:00 cutoff (reference)',
        'ridge_weather_same_rows': 'paper Weather Ridge refitted on history-available rows (reference)',
        'ridge_history': 'paper History Ridge (reference)',
        'ridge_persistence_residual': 'Ridge on target minus persistence; shrinks toward persistence, not the mean',
        'lgbm_history': 'LightGBM, squared error, history features',
        'lgbm_persistence_residual': 'LightGBM on target minus persistence',
        'lgbm_tail_weighted': 'LightGBM, sample weight 1 + observed category index',
        'lgbm_censored_floor': 'LightGBM trained with censored Severe days at their 401 lower bound (biased low by construction)',
        'max_persistence_ridge': 'maximum of persistence and History Ridge (threshold-aware heuristic)',
    },
    'lightgbm': LGBM, 'quantile_levels': QUANTILES, 'quantile_rounds': 200,
    'interval_level': LEVEL, 'rolling_window_days': 30, 'outcome_delay_days': 2, 'adaptive_gamma': 0.02, 'scale_floor': 50.0,
    'interval_note': 'outcomes of day D-1 are incomplete at the 20:00 issue on D-1, so recalibration uses dates up to D-2',
    'survivorship_cohort': 'stations with at least 30 valid targets in the first fold training window, fixed for all folds',
    'final_test': 'SEALED; rows filtered by date before materialisation',
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def load_development(protocol):
    """Valid development targets only. Sealed rows are never materialised."""
    quality = json.loads((OUT / 'measured_dataset.json').read_text())
    path = config.PROJECT_ROOT / quality['table']
    folds = splits.rolling_folds(data.study_dates(protocol), protocol)
    splits.check(folds)
    sealed_start = min(next(f for f in folds if f['role'] == 'final_test')['test'])
    table = pq.read_table(path, filters=[('target_date', '<', sealed_start)]).to_pandas()
    table['target_date'] = pd.to_datetime(table.target_date).dt.date
    guard_development(table, sealed_start)
    table = table[table.target_valid].copy()
    inputs = path.parent.parent / 'inputs.json'
    metadata, _ = data.station_table(json.loads(inputs.read_text())['selection'])
    return table, folds, metadata, quality, sealed_start


def guard_development(frame, sealed_start):
    if len(frame) and max(frame.target_date) >= sealed_start:
        raise ValueError('Sealed final-test rows reached a development analysis')
    return True


# --------------------------------------------------------------------------- point candidates
def history_candidates(train, parts):
    """Fit every point candidate on history-available training rows; predict each part."""
    import lightgbm as lgb
    exact = train[~train.censored]
    if len(exact) < 30:
        raise ValueError('Too few exact history-available training targets')
    base = exact.obs24_aqi.to_numpy()
    ridge = estimator(HISTORY_FEATURES).fit(exact[HISTORY_FEATURES], exact.y_aqi)
    ridge_weather = estimator(STRICT_FEATURES).fit(exact[STRICT_FEATURES], exact.y_aqi)
    ridge_residual = estimator(HISTORY_FEATURES).fit(exact[HISTORY_FEATURES], exact.y_aqi - base)
    boosted = lgb.LGBMRegressor(**LGBM).fit(exact[HISTORY_FEATURES], exact.y_aqi)
    boosted_residual = lgb.LGBMRegressor(**LGBM).fit(exact[HISTORY_FEATURES], exact.y_aqi - base)
    boosted_tail = lgb.LGBMRegressor(**LGBM).fit(exact[HISTORY_FEATURES], exact.y_aqi,
                                                sample_weight=1.0 + exact.y_category.to_numpy(dtype=float))
    boosted_floor = lgb.LGBMRegressor(**LGBM).fit(train[HISTORY_FEATURES], train.y_aqi)  # censored rows carry 401
    quantile_models = {q: lgb.LGBMRegressor(**{**LGBM, 'objective': 'quantile', 'alpha': q, 'n_estimators': 200})
                       .fit(exact[HISTORY_FEATURES], exact.y_aqi) for q in QUANTILES}
    outputs = []
    for part in parts:
        persistence = part.obs24_aqi.to_numpy(dtype=float)
        history = np.maximum(0, ridge.predict(part[HISTORY_FEATURES]))
        out = {
            'persistence': persistence,
            'ridge_weather_same_rows': np.maximum(0, ridge_weather.predict(part[STRICT_FEATURES])),
            'ridge_history': history,
            'ridge_persistence_residual': np.maximum(0, persistence + ridge_residual.predict(part[HISTORY_FEATURES])),
            'lgbm_history': np.maximum(0, boosted.predict(part[HISTORY_FEATURES])),
            'lgbm_persistence_residual': np.maximum(0, persistence + boosted_residual.predict(part[HISTORY_FEATURES])),
            'lgbm_tail_weighted': np.maximum(0, boosted_tail.predict(part[HISTORY_FEATURES])),
            'lgbm_censored_floor': np.maximum(0, boosted_floor.predict(part[HISTORY_FEATURES])),
            'max_persistence_ridge': np.maximum(persistence, history),
        }
        stacked = np.sort(np.stack([np.maximum(0, quantile_models[q].predict(part[HISTORY_FEATURES])) for q in QUANTILES]), axis=0)
        out.update({quantile_name(q): stacked[i] for i, q in enumerate(QUANTILES)})  # sorted: crossing repaired without labels
        outputs.append(out)
    return outputs


def quantile_name(q):
    return f'lgbm_q{int(round(q * 1000)):03d}'


# --------------------------------------------------------------------------- scores and summaries
def point_summary(frame, column):
    """Exact-error metrics on exact days; bound-based diagnostics on censored Severe days."""
    forecast = frame[column].to_numpy(dtype=float)
    observed, category, censored = frame.y_aqi.to_numpy(dtype=float), frame.y_category.to_numpy(dtype=int), frame.censored.to_numpy(dtype=bool)
    exact, error = ~censored, forecast - observed
    issued = metrics.bands(forecast)

    def block(mask):
        if not mask.any():
            return {'n': 0, 'mae': None, 'bias': None}
        return {'n': int(mask.sum()), 'mae': float(np.abs(error[mask]).mean()), 'bias': float(error[mask].mean())}

    high = category >= 3
    severe = forecast[censored]
    return {
        'n_exact': int(exact.sum()), 'mae': float(np.abs(error[exact]).mean()), 'rmse': float(math.sqrt((error[exact] ** 2).mean())),
        'bias': float(error[exact].mean()),
        'good_to_moderate': block(exact & (category <= 2)), 'poor_or_worse': block(exact & high),
        'poor': block(exact & (category == 3)), 'very_poor': block(exact & (category == 4)),
        'category_accuracy': float((issued == category).mean()), 'within_one_category': float((np.abs(issued - category) <= 1).mean()),
        'under_warning': float((issued < category).mean()), 'over_warning': float((issued > category).mean()),
        'serious_under_warning': float((issued < category - 1).mean()),
        'poor_or_worse_under_warning': float((issued[high] < category[high]).mean()) if high.any() else None,
        'severe': {'n': int(censored.sum()), 'reaches_401': int((severe >= SEVERE_FLOOR).sum()),
                   'reaches_very_poor': int((severe > 300).sum()),
                   'mean_shortfall_lower_bound': float(np.clip(SEVERE_FLOOR - severe, 0, None).mean()) if len(severe) else None},
    }


def warning_summary(category, decision):
    category, issued = np.asarray(category, dtype=int), metrics.bands(np.asarray(decision, dtype=float))
    high = category >= 3
    return {'n': int(len(category)), 'under_warning': float((issued < category).mean()), 'over_warning': float((issued > category).mean()),
            'serious_under_warning': float((issued < category - 1).mean()),
            'poor_or_worse_under_warning': float((issued[high] < category[high]).mean()) if high.any() else None,
            'severe_issued_when_severe': int(((issued == 5) & (category == 5)).sum()), 'severe_observed': int((category == 5).sum())}


def nonconformity(frame, prediction, scale_floor=None):
    """Absolute residual; for a censored day the bound 401 gives a lower bound of the error."""
    prediction = np.asarray(prediction, dtype=float)
    score = np.abs(frame.y_aqi.to_numpy(dtype=float) - prediction)
    score = np.where(frame.censored.to_numpy(dtype=bool), np.maximum(SEVERE_FLOOR - prediction, 0), score)
    return score / np.maximum(prediction, scale_floor) if scale_floor else score


def static_intervals(cal, pred_cal, pred_test, level=LEVEL, scale_floor=None, groups_cal=None, groups_test=None, minimum=30):
    """Split conformal from the calibration month; optional scaling and group-wise (Mondrian) radii."""
    pred_test = np.asarray(pred_test, dtype=float)
    exact = ~cal.censored.to_numpy(dtype=bool)
    score = nonconformity(cal, pred_cal, scale_floor)[exact]
    pooled = finite_quantile(score, level)
    if pooled is None:
        pooled = float(np.max(score)) if len(score) else float('nan')
    radius = np.full(len(pred_test), pooled, dtype=float)
    if groups_cal is not None:
        groups_cal, groups_test = np.asarray(groups_cal)[exact], np.asarray(groups_test)
        for group in np.unique(groups_test):
            values = score[groups_cal == group]
            specific = finite_quantile(values, level) if len(values) >= minimum else None
            if specific is not None:
                radius[groups_test == group] = specific  # otherwise the pooled radius is kept
    scale = np.maximum(pred_test, scale_floor) if scale_floor else 1.0
    return np.maximum(0, pred_test - radius * scale), pred_test + radius * scale


def rolling_intervals(cal, test, pred_cal, pred_test, level=LEVEL, window=30, delay=2, scale_floor=None, gamma=None):
    """Recalibrate each target date from the most recent outcomes known at issue.

    The radius for date D uses scores of dates in (D - delay - window, D - delay].
    With `gamma` the miscoverage level follows adaptive conformal inference, again
    updated only with dates whose outcomes are known (delayed feedback).
    """
    pred_test = np.asarray(pred_test, dtype=float)
    dates = np.concatenate([np.asarray(cal.target_date), np.asarray(test.target_date)])
    scores = np.concatenate([nonconformity(cal, pred_cal, scale_floor), nonconformity(test, pred_test, scale_floor)])
    by_date = {d: scores[dates == d] for d in sorted(set(dates))}
    test_dates = np.asarray(test.target_date)
    observed, censored = test.y_aqi.to_numpy(dtype=float), test.censored.to_numpy(dtype=bool)
    lower, upper = np.empty(len(test)), np.empty(len(test))
    nominal = alpha = 1 - level
    missed, pending = {}, sorted(set(test_dates))
    applied = set()
    for day in pending:
        known_until = day - timedelta(days=delay)
        if gamma:
            for earlier in pending:
                if earlier <= known_until and earlier not in applied:
                    alpha = float(np.clip(alpha + gamma * (nominal - missed[earlier]), 0.005, 0.5))
                    applied.add(earlier)
        start = known_until - timedelta(days=window)
        pool = [by_date[d] for d in by_date if start < d <= known_until]
        pool = np.concatenate(pool) if pool else np.array([])
        radius = finite_quantile(pool, 1 - alpha)
        if radius is None:
            radius = float(np.max(pool)) if len(pool) else float('nan')
        mask = test_dates == day
        scale = np.maximum(pred_test[mask], scale_floor) if scale_floor else 1.0
        lower[mask], upper[mask] = np.maximum(0, pred_test[mask] - radius * scale), pred_test[mask] + radius * scale
        outside = np.where(censored[mask], upper[mask] < SEVERE_FLOOR, (observed[mask] < lower[mask]) | (observed[mask] > upper[mask]))
        missed[day] = float(outside.mean())
    return lower, upper


def interval_summary(frame, lower, upper):
    lower, upper = np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
    observed, category, censored = frame.y_aqi.to_numpy(dtype=float), frame.y_category.to_numpy(dtype=int), frame.censored.to_numpy(dtype=bool)
    issued = np.isfinite(lower) & np.isfinite(upper)
    exact = issued & ~censored
    covered = (lower <= observed) & (observed <= upper)

    def rate(mask):
        return {'n': int(mask.sum()), 'coverage': float(covered[mask].mean()) if mask.any() else None,
                'mean_width': float((upper[mask] - lower[mask]).mean()) if mask.any() else None}

    out = {'n_exact': int(exact.sum()), 'coverage': float(covered[exact].mean()), 'mean_width': float((upper[issued] - lower[issued]).mean()),
           'median_width': float(np.median(upper[issued] - lower[issued])),
           'by_category': {label: rate(exact & (category == index)) for index, label in enumerate(metrics.LABELS[:5])},
           'poor_or_worse': rate(exact & (category >= 3)),
           'by_season': {str(name): rate(exact & (frame.season.to_numpy() == name)) for name in sorted(frame.season.unique())},
           'by_region': {str(name): rate(exact & (frame.region.to_numpy() == name)) for name in sorted(frame.region.unique())},
           'censored_severe': {'n': int((issued & censored).sum()), 'upper_reaches_401': int((upper[issued & censored] >= SEVERE_FLOOR).sum())}}
    categories = [v['coverage'] for v in out['by_category'].values() if v['n'] >= 30]
    out['worst_category_coverage'] = float(min(categories)) if categories else None
    return out


# --------------------------------------------------------------------------- experiment
def run_folds(table, folds, with_candidates=True):
    """Pooled out-of-fold rows for the all-pairs and history-available populations."""
    everything, history = [], []
    for fold in [f for f in folds if f['role'] == 'rolling']:
        train = table[table.target_date.isin(fold['train'])]
        test = table[table.target_date.isin(fold['test'])]
        cal = table[table.target_date.isin(fold['calibration'])]
        train, test = eligible(train, test)
        cal = cal[cal.station_id.isin(train.station_id.unique())]
        test, cal = test.copy(), cal.copy()
        test['fold'] = cal['fold'] = fold['name']
        test['climatology'] = climatology(train, test)
        cal_weather, test['ridge_weather'] = fit_predict(train, [cal, test], STRICT_FEATURES)
        if with_candidates:
            test['w_split_lo'], test['w_split_hi'] = static_intervals(cal, cal_weather, test.ridge_weather)
            test['w_rolling_lo'], test['w_rolling_hi'] = rolling_intervals(cal, test, cal_weather, test.ridge_weather)
            test['w_adaptive_lo'], test['w_adaptive_hi'] = rolling_intervals(cal, test, cal_weather, test.ridge_weather,
                                                                           gamma=PLAN['adaptive_gamma'])
        everything.append(test)
        train_h, cal_h, test_h = (frame[frame.obs24_aqi.notna()].copy() for frame in (train, cal, test))
        if len(train_h[~train_h.censored]) < 30 or not len(test_h):
            continue
        if not with_candidates:
            test_h['persistence'] = test_h.obs24_aqi
            test_h['ridge_history'] = fit_predict(train_h, [test_h], HISTORY_FEATURES)[0]
            history.append(test_h)
            continue
        predicted_cal, predicted_test = history_candidates(train_h, [cal_h, test_h])
        for name, values in predicted_test.items():
            test_h[name] = values
        groups_cal, groups_test = metrics.bands(cal_h.obs24_aqi), metrics.bands(test_h.obs24_aqi)
        floor = PLAN['scale_floor']
        for label, model in (('pers', 'persistence'), ('hist', 'ridge_history'), ('wx', 'ridge_weather_same_rows'),
                             ('hyb', 'ridge_persistence_residual')):
            test_h[f'{label}_split_lo'], test_h[f'{label}_split_hi'] = static_intervals(cal_h, predicted_cal[model], predicted_test[model])
        hybrid_cal, hybrid_test = predicted_cal['ridge_persistence_residual'], predicted_test['ridge_persistence_residual']
        test_h['hyb_scaled_lo'], test_h['hyb_scaled_hi'] = static_intervals(cal_h, hybrid_cal, hybrid_test, scale_floor=floor)
        test_h['hyb_mondrian_lo'], test_h['hyb_mondrian_hi'] = static_intervals(cal_h, hybrid_cal, hybrid_test,
                                                                               groups_cal=groups_cal, groups_test=groups_test)
        test_h['hyb_rolling_scaled_lo'], test_h['hyb_rolling_scaled_hi'] = rolling_intervals(cal_h, test_h, hybrid_cal, hybrid_test,
                                                                                             scale_floor=floor)
        test_h['hyb_adaptive_scaled_lo'], test_h['hyb_adaptive_scaled_hi'] = rolling_intervals(
            cal_h, test_h, hybrid_cal, hybrid_test, scale_floor=floor, gamma=PLAN['adaptive_gamma'])
        history.append(test_h)
        print(f"{fold['name']}: {len(test)} outcomes, {len(test_h)} with history", flush=True)
    return pd.concat(everything, ignore_index=True), pd.concat(history, ignore_index=True)


def spatial_penalties(table, metadata, geometry, groups=('cluster', 'region')):
    """Paired MAE increase of an excluded Weather Ridge over an all-station reference, same rows."""
    base_train = table[table.target_date.isin(geometry['train'])]
    base_test = table[table.target_date.isin(geometry['test'])]
    out = {}
    for group in groups:
        assignment = splits.grouped_folds(metadata[group], k=10) if group != 'region' else {g: g for g in metadata[group].unique()}
        rows = []
        for heldout in sorted(set(assignment.values())):
            members = [g for g, f in assignment.items() if f == heldout]
            train = base_train[~base_train[group].isin(members)]
            test = base_test[base_test[group].isin(members)].copy()
            if len(train[~train.censored]) < 30 or len(test) < 30:
                continue
            test['excluded'] = fit_predict(train, [test], STRICT_FEATURES)[0]
            test['reference'] = fit_predict(base_train, [test], STRICT_FEATURES)[0]
            rows.append(test[['station_id', 'target_date', 'y_aqi', 'y_category', 'censored', 'excluded', 'reference']])
        pooled = pd.concat(rows, ignore_index=True)
        comparison = paired(pooled, 'excluded', 'reference')
        polluted = pooled[pooled.y_category >= 3]
        high = paired(polluted, 'excluded', 'reference') if len(polluted[~polluted.censored]) >= 30 else {'n': int(len(polluted))}
        out[group] = {'n_exact': comparison['n'], 'mae_increase': comparison['mae_difference'], 'ci95': comparison['ci95'],
                      'poor_or_worse_n': high.get('n'), 'poor_or_worse_mae_increase': high.get('mae_difference'),
                      'poor_or_worse_ci95': high.get('ci95'), 'stations': int(pooled.station_id.nunique())}
    return out


def cohort_summary(everything, history):
    exact = everything[~everything.censored]
    counts = everything.y_category.astype(int).value_counts().sort_index()
    comparisons = {'weather_minus_climatology': paired(everything, 'ridge_weather', 'climatology'),
                   'history_minus_persistence': paired(history, 'ridge_history', 'persistence')}
    return {'stations': int(everything.station_id.nunique()), 'cities': int(everything.city.nunique()), 'dates': int(everything.target_date.nunique()),
            'outcomes': int(len(everything)), 'exact_pairs': int(len(exact)), 'censored_severe': int(everything.censored.sum()),
            'history_exact_pairs': int((~history.censored).sum()),
            'category_share': {metrics.LABELS[i]: float(counts.get(i, 0) / len(everything)) for i in range(6)},
            'mae': {'climatology': float((exact.climatology - exact.y_aqi).abs().mean()),
                    'ridge_weather': float((exact.ridge_weather - exact.y_aqi).abs().mean()),
                    'persistence': float((history[~history.censored].persistence - history[~history.censored].y_aqi).abs().mean()),
                    'ridge_history': float((history[~history.censored].ridge_history - history[~history.censored].y_aqi).abs().mean())},
            'paired': {key: {k: value[k] for k in ('n', 'mae_difference', 'ci95')} for key, value in comparisons.items()}}


def catalogue_exposure(study_start, active_since=catalogue.ACTIVE_SINCE):
    """How many otherwise-eligible monitors the recent-activity rule removed. Catalogue metadata only."""
    payload = json.loads(catalogue.CATALOGUE.read_text(encoding='utf-8'))
    locations = payload['results'] if isinstance(payload, dict) and 'results' in payload else payload
    structural = [loc for loc in locations if (loc.get('provider') or {}).get('name') == 'CPCB'
                  and all(catalogue.mass_sensor(loc, parameter) for parameter in catalogue.REQUIRED)
                  and (loc.get('coordinates') or {}).get('latitude') is not None]
    start = str(study_start)

    def last(loc):
        return ((loc.get('datetimeLast') or {}).get('utc') or '')

    def first(loc):
        return ((loc.get('datetimeFirst') or {}).get('utc') or '')

    alive_at_start = [loc for loc in structural if first(loc) and first(loc)[:10] <= start <= last(loc)[:10]]
    survivors = [loc for loc in alive_at_start if last(loc) >= active_since]
    return {'structurally_eligible': len(structural), 'eligible_under_study_rule': sum(last(loc) >= active_since for loc in structural),
            'reporting_at_study_start': len(alive_at_start), 'of_those_active_after_cutoff': len(survivors),
            'of_those_dropped_by_recent_activity_rule': len(alive_at_start) - len(survivors),
            'started_after_study_start': sum(bool(first(loc)) and first(loc)[:10] > start and last(loc) >= active_since for loc in structural),
            'basis': 'OpenAQ catalogue first/last timestamps; no pollutant value read; dropped monitors were never downloaded'}


def run():
    protocol = load()
    table, folds, metadata, quality, sealed_start = load_development(protocol)
    code_hash = sha256(__file__)
    run_id = canonical_hash([quality['dataset_hash'], canonical_hash(PLAN), code_hash])
    destination = OUT / 'extensions' / run_id
    destination.mkdir(parents=True, exist_ok=True)
    everything, history = run_folds(table, folds)
    guard_development(everything, sealed_start), guard_development(history, sealed_start)

    point_names = list(PLAN['point_candidates'])
    points = {name: point_summary(history, name) for name in point_names}
    for name in point_names:
        if name != 'persistence':
            comparison = paired(history, name, 'persistence')
            points[name]['minus_persistence'] = {k: comparison[k] for k in ('mae_difference', 'ci95')}
            polluted = history[history.y_category >= 3]
            high = paired(polluted, name, 'persistence')
            points[name]['minus_persistence_poor_or_worse'] = {k: high[k] for k in ('n', 'mae_difference', 'ci95')}
    points['ridge_weather_all_pairs'] = point_summary(everything, 'ridge_weather')

    intervals = {
        'all_pairs': {'population': 'all outcomes; weather-only point forecast', 'methods': {
            'split@weather_ridge (paper)': interval_summary(everything, everything.w_split_lo, everything.w_split_hi),
            'rolling30@weather_ridge': interval_summary(everything, everything.w_rolling_lo, everything.w_rolling_hi),
            'adaptive@weather_ridge': interval_summary(everything, everything.w_adaptive_lo, everything.w_adaptive_hi)}},
        'history_pairs': {'population': 'history-available outcomes', 'methods': {
            'split@weather_ridge': interval_summary(history, history.wx_split_lo, history.wx_split_hi),
            'split@persistence': interval_summary(history, history.pers_split_lo, history.pers_split_hi),
            'split@ridge_history': interval_summary(history, history.hist_split_lo, history.hist_split_hi),
            'split@ridge_persistence_residual': interval_summary(history, history.hyb_split_lo, history.hyb_split_hi),
            'scaled@ridge_persistence_residual': interval_summary(history, history.hyb_scaled_lo, history.hyb_scaled_hi),
            'mondrian_persistence_category@ridge_persistence_residual': interval_summary(history, history.hyb_mondrian_lo, history.hyb_mondrian_hi),
            'rolling30_scaled@ridge_persistence_residual': interval_summary(history, history.hyb_rolling_scaled_lo, history.hyb_rolling_scaled_hi),
            'adaptive_scaled@ridge_persistence_residual': interval_summary(history, history.hyb_adaptive_scaled_lo, history.hyb_adaptive_scaled_hi)}}}

    warnings = {'history_pairs': {'n': int(len(history)), 'operating_points': {
        **{name: warning_summary(history.y_category, history[name]) for name in
           ('persistence', 'ridge_history', 'ridge_persistence_residual', 'lgbm_history', 'max_persistence_ridge')},
        **{f'quantile_{q}': warning_summary(history.y_category, history[quantile_name(q)]) for q in QUANTILES}}},
        'all_pairs': {'n': int(len(everything)), 'operating_points': {
            'ridge_weather_point': warning_summary(everything.y_category, everything.ridge_weather)}},
        'default_policy': 'NONE SELECTED: no cost ratio between a missed category and an excess alert has been declared'}

    # Survivorship sensitivity: eligibility frozen in the first fold's training window.
    first = next(f for f in folds if f['role'] == 'rolling')
    window = table[table.target_date.isin(first['train'])]
    counts = window.groupby('station_id').size()
    frozen = set(counts[counts >= 30].index)
    geometry = splits.spatial_frame(data.study_dates(protocol), protocol)
    reference_all, reference_history = everything, history
    cohort_table = table[table.station_id.isin(frozen)]
    cohort_all, cohort_history = run_folds(cohort_table, folds, with_candidates=False)
    survivorship = {
        'frozen_rule': PLAN['survivorship_cohort'], 'eligibility_window': first['train_range'],
        'paper_cohort': {**cohort_summary(reference_all, reference_history.assign(ridge_history=reference_history.ridge_history)),
                         'spatial': spatial_penalties(table, metadata, geometry)},
        'frozen_cohort': {**cohort_summary(cohort_all, cohort_history), 'spatial': spatial_penalties(cohort_table, metadata, geometry)},
        'late_entry_stations_removed': int(reference_all.station_id.nunique() - cohort_all.station_id.nunique()),
        'catalogue_exposure': catalogue_exposure(protocol['study_window']['first_date']),
        'limit': 'Monitors that stopped reporting before the recent-activity cutoff were never downloaded, so this analysis removes '
                 'late entrants but cannot add back lost monitors; catalogue_exposure counts them.'}

    keep = ['station_id', 'city', 'region', 'season', 'target_date', 'fold', 'y_aqi', 'y_category', 'censored'] + point_names + \
           [quantile_name(q) for q in QUANTILES] + [c for c in history.columns if c.endswith(('_lo', '_hi'))]
    history[keep].to_parquet(destination / 'rows_history.parquet', index=False)
    everything[['station_id', 'city', 'region', 'season', 'target_date', 'fold', 'y_aqi', 'y_category', 'censored', 'climatology',
                'ridge_weather'] + [c for c in everything.columns if c.endswith(('_lo', '_hi'))]].to_parquet(destination / 'rows_all.parquet', index=False)
    result = {'generated_at': datetime.now(timezone.utc).isoformat(), 'experiment': PLAN['experiment'], 'status': PLAN['status'],
              'run_id': run_id, 'plan': PLAN, 'dataset_hash': quality['dataset_hash'], 'protocol_sha256': protocol['_sha256'],
              'code_sha256': code_hash, 'git_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'runtime': {'python': platform.python_version(), 'packages': {p: version(p) for p in
                          ('numpy', 'pandas', 'scikit-learn', 'lightgbm', 'pyarrow', 'scipy')}},
              'reader_filter': f'target_date < {sealed_start}', 'final_test_accessed': False, 'final_test_scored': False,
              'paper_run_modified': False, 'selection_made': False,
              'populations': {'all_pairs': {'outcomes': int(len(everything)), 'exact': int((~everything.censored).sum()),
                                            'censored_severe': int(everything.censored.sum())},
                              'history_pairs': {'outcomes': int(len(history)), 'exact': int((~history.censored).sum()),
                                                'censored_severe': int(history.censored.sum())}},
              'point': points, 'intervals': intervals, 'warnings': warnings, 'survivorship': survivorship,
              'rows': {'history': {'path': config.portable(destination / 'rows_history.parquet'), 'sha256': sha256(destination / 'rows_history.parquet')},
                       'all': {'path': config.portable(destination / 'rows_all.parquet'), 'sha256': sha256(destination / 'rows_all.parquet')}},
              'artifact': config.portable(destination / 'results.json')}
    write_json(destination / 'results.json', result)
    write_json(OUT / 'development_extensions.json', result)
    return result


if __name__ == '__main__':
    outcome = run()
    print(json.dumps({k: outcome[k] for k in ('status', 'run_id', 'final_test_accessed', 'artifact')}, indent=1))
