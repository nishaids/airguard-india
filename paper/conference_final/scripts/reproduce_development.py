"""Development-only reproduction of the frozen non-CAMS run with row-level outputs.

Purpose
-------
The frozen run (results/research/preliminary/<run_id>/results.json) stores fold
summaries but not interval endpoints, quantile forecasts or spatial-holdout
predictions. This script refits the *same* frozen configuration with the
project's own functions, verifies that every refit fold summary equals the
frozen artifact, and only then writes row-level tables for paired spatial
intervals, severity-conditioned coverage and the warning operating curve.

Final-test isolation
--------------------
Rows are filtered by Arrow predicate ``target_date < first sealed date`` before
any column is materialised. No sealed-period label is read, scored or plotted.
No model, feature, hyperparameter or threshold is chosen here; the plan is the
committed ``non-cams-plan-v1``.

Run from the repository root:
    .venv-live/Scripts/python.exe paper/conference_final/scripts/reproduce_development.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.calibration import data, metrics, splits  # noqa: E402
from src.research.calibration.measured import CONDITIONAL_FEATURES, STRICT_FEATURES  # noqa: E402
from src.research.calibration.preliminary import PLAN, climatology, eligible, fit_predict  # noqa: E402
from src.research.calibration.protocol import load  # noqa: E402
from src.research.calibration.statistics import finite_quantile, select_risk_quantile  # noqa: E402

OUT = ROOT / 'paper' / 'conference_final' / 'evidence'
RUN = '287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f'
FROZEN = ROOT / 'results' / 'research' / 'preliminary' / RUN / 'results.json'
QUANTILES = [.05, .1, .5, .65, .75, .85, .9, .95, .975]
TOLERANCE = 1e-9


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def load_development(protocol):
    quality = json.loads((ROOT / 'results/research/measured_dataset.json').read_text())
    path = ROOT / quality['table']
    folds = splits.rolling_folds(data.study_dates(protocol), protocol)
    splits.check(folds)
    final = next(f for f in folds if f['role'] == 'final_test')
    sealed_start = min(final['test'])
    assert sealed_start == date(2026, 7, 10), sealed_start
    # Predicate pushdown: sealed rows are never materialised.
    table = pq.read_table(path, filters=[('target_date', '<', sealed_start)]).to_pandas()
    table['target_date'] = pd.to_datetime(table.target_date).dt.date
    assert table.target_date.max() < sealed_start
    ledger = {'development_station_days': int(len(table)),
              'development_valid_targets': int(table.target_valid.sum()),
              'development_rejected_targets': int((~table.target_valid).sum()),
              'development_last_date': str(table.target_date.max()),
              'development_first_date': str(table.target_date.min())}
    table = table[table.target_valid].copy()
    ledger.update({'development_valid_stations': int(table.station_id.nunique()),
                   'development_valid_cities': int(table.city.nunique()),
                   'development_valid_dates': int(table.target_date.nunique()),
                   'development_censored_severe': int(table.censored.sum()),
                   'development_exact_targets': int((~table.censored).sum())})
    inputs = path.parent.parent / 'inputs.json'
    metadata, _ = data.station_table(json.loads(inputs.read_text())['selection'])
    return table, folds, metadata, quality, path, ledger


def interval_rows(train, cal, test, columns):
    """Row-level replica of preliminary.uncertainty(); same order of operations."""
    pred_cal, pred = fit_predict(train, [cal, test], columns)
    exact = ~cal.censored.to_numpy()
    y_cal = cal.y_aqi.to_numpy()
    residual = np.abs(y_cal[exact] - pred_cal[exact])
    out = pd.DataFrame(index=test.index)
    out['point'] = pred
    radii = {}
    for nominal in (.8, .9):
        radius = finite_quantile(residual, nominal)
        radii[nominal] = radius
        out[f'split{int(nominal * 100)}_lo'] = np.maximum(0, pred - radius) if radius is not None else np.nan
        out[f'split{int(nominal * 100)}_hi'] = pred + radius if radius is not None else np.nan
    mond = np.full(len(test), np.nan)
    for band in range(6):
        values = residual[metrics.bands(pred_cal[exact]) == band]
        radius = finite_quantile(values, .9) if len(values) >= 30 else None
        if radius is not None:
            mond[metrics.bands(pred) == band] = radius
    out['mondrian90_lo'] = np.where(np.isfinite(mond), np.maximum(0, pred - mond), np.nan)
    out['mondrian90_hi'] = np.where(np.isfinite(mond), pred + mond, np.nan)
    exact_train = train[~train.censored & train.target_valid]
    imputer = SimpleImputer(strategy='median', keep_empty_features=True)
    xtrain = imputer.fit_transform(exact_train[columns])
    xcal, xtest = imputer.transform(cal[columns]), imputer.transform(test[columns])
    q_cal, q_test = {}, {}
    cfg = PLAN['quantile_model']
    for q in QUANTILES:
        model = GradientBoostingRegressor(loss='quantile', alpha=q, n_estimators=cfg['estimators'],
                                          max_depth=cfg['depth'], min_samples_leaf=cfg['min_samples_leaf'],
                                          learning_rate=cfg['learning_rate'], random_state=42)
        model.fit(xtrain, exact_train.y_aqi)
        q_cal[q], q_test[q] = model.predict(xcal), model.predict(xtest)
    ordered_cal = np.sort(np.stack([q_cal[q] for q in QUANTILES]), axis=0)
    ordered_test = np.sort(np.stack([q_test[q] for q in QUANTILES]), axis=0)
    q_cal, q_test = dict(zip(QUANTILES, ordered_cal)), dict(zip(QUANTILES, ordered_test))
    scores = np.maximum(q_cal[.05][exact] - y_cal[exact], y_cal[exact] - q_cal[.95][exact])
    correction = finite_quantile(scores, .9)
    if correction is not None:
        correction = max(0, correction)
        out['cqr90_lo'] = np.maximum(0, q_test[.05] - correction)
        out['cqr90_hi'] = q_test[.95] + correction
    else:
        out['cqr90_lo'] = out['cqr90_hi'] = np.nan
    for q in QUANTILES:
        out[f'q{int(round(q * 1000)):03d}'] = q_test[q]
    for q, name in ((.5, 'p1'), (.75, 'p2')):
        shift = finite_quantile(y_cal[exact] - q_cal[q][exact], q)
        out[name] = np.maximum(0, q_test[q] + shift) if shift is not None else np.nan
    candidates = {q: q_cal[q] for q in QUANTILES if q >= .5}
    chosen = {target: select_risk_quantile(cal.y_category, candidates, target) for target in (.1, .05)}
    for target, q in chosen.items():
        out[f'p3_{int(target * 100):02d}'] = q_test[q] if q is not None else np.nan
        out[f'p3_{int(target * 100):02d}_quantile'] = q if q is not None else np.nan
    meta = {'calibration_exact': int(exact.sum()), 'calibration_censored': int((~exact).sum()),
            'split_radius_80': radii[.8], 'split_radius_90': radii[.9], 'cqr_correction': correction,
            'p3_quantile_10': chosen[.1], 'p3_quantile_05': chosen[.05]}
    return out, meta


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    protocol = load()
    table, folds, metadata, quality, table_path, ledger = load_development(protocol)
    frozen = json.loads(FROZEN.read_text())
    assert quality['dataset_hash'] == frozen['dataset_hash']
    frozen_folds = {f['fold']: f for f in frozen['folds'] if f['design'] == 'expanding'}
    checks, temporal, fold_meta = [], [], {}
    for fold in [f for f in folds if f['role'] == 'rolling']:
        train = table[table.target_date.isin(fold['train'])]
        test = table[table.target_date.isin(fold['test'])]
        cal = table[table.target_date.isin(fold['calibration'])]
        train, test = eligible(train, test)
        cal = cal[cal.station_id.isin(train.station_id.unique())]
        test = test.copy()
        test['climatology'] = climatology(train, test)
        test['ridge_strict'] = fit_predict(train, [test], STRICT_FEATURES)[0]
        base = [c for c in STRICT_FEATURES if not c.startswith('wx_')]
        test['ridge_calendar_spatial'] = fit_predict(train, [test], base)[0]
        common = test[test.obs24_aqi.notna()].copy()
        conditional_train = train[train.obs24_aqi.notna()]
        test['persistence'] = test['ridge_history'] = test['ridge_strict_same_training'] = np.nan
        if len(conditional_train[~conditional_train.censored]) >= 30 and len(common):
            test.loc[common.index, 'persistence'] = common.obs24_aqi
            test.loc[common.index, 'ridge_history'] = fit_predict(
                conditional_train, [common], STRICT_FEATURES + CONDITIONAL_FEATURES)[0]
            test.loc[common.index, 'ridge_strict_same_training'] = fit_predict(
                conditional_train, [common], STRICT_FEATURES)[0]
        intervals, meta = interval_rows(train, cal, test, STRICT_FEATURES)
        assert np.allclose(intervals['point'].to_numpy(), test['ridge_strict'].to_numpy())
        test = test.join(intervals.drop(columns=['point']))
        test['fold'] = fold['name']
        meta.update({'train_range': fold['train_range'], 'calibration_range': fold['calibration_range'],
                     'test_range': fold['test_range'], 'stations_training_eligible': int(train.station_id.nunique()),
                     'train_exact_rows': int((~train.censored).sum()), 'test_rows': int(len(test))})
        fold_meta[fold['name']] = meta
        ref = frozen_folds[fold['name']]
        exact = ~test.censored
        for name in ('climatology', 'ridge_strict', 'ridge_calendar_spatial'):
            mae = float((test.loc[exact, name] - test.loc[exact, 'y_aqi']).abs().mean())
            checks.append(('temporal', fold['name'], name, mae, ref['strict'][name]['mae']))
        cov = float(((test.split90_lo <= test.y_aqi) & (test.y_aqi <= test.split90_hi))[exact].mean())
        checks.append(('interval', fold['name'], 'split_0.9', cov, frozen['uncertainty'][fold['name']]['split_0.9']['coverage_exact']))
        cov = float(((test.cqr90_lo <= test.y_aqi) & (test.y_aqi <= test.cqr90_hi))[exact].mean())
        checks.append(('interval', fold['name'], 'cqr_0.9', cov, frozen['uncertainty'][fold['name']]['cqr_0.9']['coverage_exact']))
        under = float((metrics.bands(test.p2) < test.y_category).mean())
        checks.append(('advisory', fold['name'], 'P2', under, frozen['advisory'][fold['name']]['P2']['under_warning']))
        temporal.append(test)
        print(fold['name'], len(test), flush=True)
    keep = ['station_id', 'city', 'state', 'region', 'season', 'latitude', 'longitude', 'cluster', 'target_date',
            'y_aqi', 'y_category', 'y_dominant', 'censored', 'fold', 'climatology', 'ridge_strict',
            'ridge_calendar_spatial', 'ridge_strict_same_training', 'persistence', 'ridge_history',
            'split80_lo', 'split80_hi', 'split90_lo', 'split90_hi', 'mondrian90_lo', 'mondrian90_hi',
            'cqr90_lo', 'cqr90_hi', 'p1', 'p2', 'p3_10', 'p3_10_quantile', 'p3_05', 'p3_05_quantile'] + \
           [f'q{int(round(q * 1000)):03d}' for q in QUANTILES]
    rows = pd.concat(temporal, ignore_index=True)[keep]
    rows.to_parquet(OUT / 'rows_temporal.parquet', index=False)

    geometry = splits.spatial_frame(data.study_dates(protocol), protocol)
    base_train = table[table.target_date.isin(geometry['train'])]
    base_test = table[table.target_date.isin(geometry['test'])]
    frozen_spatial = {(s['group'], s['holdout']): s for s in frozen['spatial']}
    spatial = []
    for group in ('city', 'cluster', 'station_id', 'region'):
        assignment = splits.grouped_folds(metadata[group], k=10) if group != 'region' else {g: g for g in metadata[group].unique()}
        for heldout in sorted(set(assignment.values())):
            members = [g for g, f in assignment.items() if f == heldout]
            train = base_train[~base_train[group].isin(members)]
            test = base_test[base_test[group].isin(members)].copy()
            if len(train[~train.censored]) < 30 or len(test) < 30:
                continue
            assert not (set(train[group]) & set(test[group]))
            test['holdout_prediction'] = fit_predict(train, [test], STRICT_FEATURES)[0]
            test['reference_prediction'] = fit_predict(base_train, [test], STRICT_FEATURES)[0]
            test['group'], test['holdout'] = group, str(heldout)
            exact = ~test.censored
            ref = frozen_spatial[(group, str(heldout))]
            for column, key in (('holdout_prediction', 'ridge_strict'), ('reference_prediction', 'reference_same_rows')):
                mae = float((test.loc[exact, column] - test.loc[exact, 'y_aqi']).abs().mean())
                checks.append(('spatial', f'{group}:{heldout}', key, mae, ref[key]['mae']))
            spatial.append(test[['group', 'holdout', 'station_id', 'city', 'region', 'cluster', 'target_date', 'y_aqi',
                                 'y_category', 'censored', 'holdout_prediction', 'reference_prediction']])
        print('spatial', group, flush=True)
    spatial_rows = pd.concat(spatial, ignore_index=True)
    spatial_rows.to_parquet(OUT / 'rows_spatial.parquet', index=False)

    worst = max(abs(a - b) for *_, a, b in checks)
    report = {'purpose': 'Development-only row-level reproduction of the frozen non-CAMS run',
              'frozen_run_id': RUN, 'frozen_results_sha256': sha256(FROZEN),
              'frozen_git_sha': frozen['git_sha'], 'dataset_hash': quality['dataset_hash'],
              'measured_table_sha256': sha256(table_path), 'protocol_sha256': protocol['_sha256'],
              'plan': PLAN['version'], 'reader_filter': 'target_date < 2026-07-10 (Arrow predicate pushdown)',
              'final_test_accessed': False, 'final_test_scored': False,
              'spatial_train_range': geometry['train_range'], 'spatial_test_range': geometry['test_range'],
              'ledger': ledger, 'folds': fold_meta,
              'checks_compared': len(checks), 'max_abs_difference_from_frozen': worst,
              'tolerance': TOLERANCE, 'reproduces_frozen_artifact': bool(worst <= TOLERANCE),
              'rows_temporal': {'path': 'evidence/rows_temporal.parquet', 'rows': int(len(rows)),
                                'sha256': sha256(OUT / 'rows_temporal.parquet')},
              'rows_spatial': {'path': 'evidence/rows_spatial.parquet', 'rows': int(len(spatial_rows)),
                               'sha256': sha256(OUT / 'rows_spatial.parquet')}}
    (OUT / 'reproduction_report.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('checks_compared', 'max_abs_difference_from_frozen',
                                             'reproduces_frozen_artifact', 'ledger')}, indent=1))
    if worst > TOLERANCE:
        raise SystemExit('Refit does not reproduce the frozen artifact; row-level outputs must not be used.')


if __name__ == '__main__':
    main()
