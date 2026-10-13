"""Leakage, censoring and bookkeeping guards for the post-paper development extensions."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.research.calibration import extensions as ext


def frame(dates, y, censored=None, category=None):
    y = np.asarray(y, dtype=float)
    censored = np.zeros(len(y), bool) if censored is None else np.asarray(censored, bool)
    category = ext.metrics.bands(y) if category is None else np.asarray(category)
    return pd.DataFrame({'target_date': dates, 'y_aqi': y, 'censored': censored, 'y_category': category,
                         'season': 'winter', 'region': 'North'})


def days(start, count):
    return [start + timedelta(days=i) for i in range(count)]


def test_sealed_rows_are_refused():
    sealed = date(2026, 7, 10)
    assert ext.guard_development(frame([date(2026, 7, 9)], [100]), sealed)
    with pytest.raises(ValueError):
        ext.guard_development(frame([date(2026, 7, 10)], [100]), sealed)


def test_censored_score_is_a_lower_bound_never_an_exact_error():
    rows = frame([date(2025, 12, 1)] * 3, [401, 401, 120], censored=[True, True, False])
    score = ext.nonconformity(rows, [150.0, 450.0, 100.0])
    assert score.tolist() == [251.0, 0.0, 20.0]          # 401 - forecast, floored at zero above the bound
    scaled = ext.nonconformity(rows, [150.0, 450.0, 10.0], scale_floor=50.0)
    assert scaled.tolist() == [251.0 / 150.0, 0.0, 110.0 / 50.0]


def test_static_interval_uses_exact_calibration_rows_and_group_fallback():
    cal = frame(days(date(2025, 6, 1), 40), [100.0] * 40, censored=[False] * 39 + [True])
    pred_cal = np.concatenate([np.full(39, 90.0), [0.0]])   # the censored row would add a huge score if it were used
    lower, upper = ext.static_intervals(cal, pred_cal, np.array([200.0, 20.0]))
    assert (upper - np.array([200.0, 20.0])).tolist() == [10.0, 10.0] and lower.tolist() == [190.0, 10.0]
    # A group with fewer than 30 calibration pairs keeps the pooled radius.
    groups_cal = np.array([0] * 35 + [1] * 5)
    low2, high2 = ext.static_intervals(cal, pred_cal, np.array([200.0, 200.0]), groups_cal=groups_cal, groups_test=np.array([0, 1]))
    assert high2.tolist() == [210.0, 210.0]
    # Scaled radii grow with the forecast level and never fall below the floor.
    low3, high3 = ext.static_intervals(cal, pred_cal, np.array([400.0, 20.0]), scale_floor=50.0)
    assert (high3[0] - 400.0) > (high3[1] - 20.0) > 0


def test_rolling_radius_never_uses_outcomes_later_than_two_days_before_target():
    cal = frame(days(date(2025, 6, 1), 30), np.full(30, 100.0))
    test = frame(days(date(2025, 7, 2), 10), np.full(10, 100.0))
    pred_cal, pred_test = np.full(30, 95.0), np.full(10, 100.0)
    base_low, base_high = ext.rolling_intervals(cal, test, pred_cal, pred_test)
    shocked = test.copy()
    shocked.loc[shocked.index[5:], 'y_aqi'] = 900.0          # change outcomes from the sixth test day onward
    low, high = ext.rolling_intervals(cal, shocked, pred_cal, pred_test)
    # Target day index 5 (and 6) can only see outcomes up to index 3 (and 4): unchanged.
    assert np.allclose(high[:7], base_high[:7]) and np.allclose(low[:7], base_low[:7])
    assert high[9] > base_high[9]                            # enough shocked days are known by the last target day
    # With a one-day delay the same shock would arrive one target day earlier: the delay is what is enforced.
    _, eager = ext.rolling_intervals(cal, shocked, pred_cal, pred_test, delay=1)
    assert eager[8] > base_high[8] and high[8] == base_high[8]


def test_adaptive_level_widens_after_delayed_misses_only():
    cal = frame(days(date(2025, 6, 1), 30), np.full(30, 100.0))
    test = frame(days(date(2025, 7, 2), 12), np.full(12, 100.0))
    pred_cal = 100.0 + np.tile(np.arange(-5.0, 5.0), 3)      # calibration residuals between 0 and 5
    pred_test = np.full(12, 100.0)
    missing = test.copy()
    missing['y_aqi'] = 106.0                                  # outside the calibrated 90% radius of 5: every day is a miss
    fixed_low, fixed_high = ext.rolling_intervals(cal, missing, pred_cal, pred_test, window=400)
    adaptive_low, adaptive_high = ext.rolling_intervals(cal, missing, pred_cal, pred_test, window=400, gamma=0.5)
    assert fixed_high[0] == 105.0
    assert np.allclose(adaptive_high[:2], fixed_high[:2])     # no feedback has arrived for the first two days
    assert adaptive_high[3] > fixed_high[3]                   # two known misses lower the miscoverage level first


def test_interval_summary_excludes_censored_from_coverage_and_reports_bound_reach():
    rows = frame([date(2025, 12, 1)] * 4, [60, 250, 401, 401], censored=[False, False, True, True], category=[1, 3, 5, 5])
    summary = ext.interval_summary(rows, np.array([50.0, 100.0, 300.0, 300.0]), np.array([70.0, 200.0, 500.0, 390.0]))
    assert summary['n_exact'] == 2 and summary['coverage'] == 0.5
    assert summary['censored_severe'] == {'n': 2, 'upper_reaches_401': 1}
    assert summary['by_category']['Poor'] == {'n': 1, 'coverage': 0.0, 'mean_width': 100.0}


def test_point_summary_scores_severe_days_by_bound_only():
    rows = frame([date(2025, 12, 1)] * 4, [60, 250, 401, 401], censored=[False, False, True, True], category=[1, 3, 5, 5])
    rows['forecast'] = [80.0, 150.0, 420.0, 301.0]
    summary = ext.point_summary(rows, 'forecast')
    assert summary['n_exact'] == 2 and summary['mae'] == 60.0 and summary['bias'] == -40.0
    assert summary['severe'] == {'n': 2, 'reaches_401': 1, 'reaches_very_poor': 2, 'mean_shortfall_lower_bound': 50.0}
    assert summary['under_warning'] == 0.5 and summary['over_warning'] == 0.0
    assert summary['poor_or_worse_under_warning'] == pytest.approx(2 / 3)


def test_warning_summary_counts_both_errors():
    summary = ext.warning_summary([0, 2, 4, 5], [120.0, 150.0, 150.0, 450.0])
    assert summary['under_warning'] == 0.25 and summary['over_warning'] == 0.25 and summary['serious_under_warning'] == 0.25
    assert summary['poor_or_worse_under_warning'] == 0.5 and summary['severe_issued_when_severe'] == 1


def test_plan_declares_no_selection_and_fixed_configuration():
    assert ext.PLAN['status'] == 'EXPLORATORY_POST_PAPER' and ext.PLAN['selection'].startswith('none')
    assert ext.LGBM['random_state'] == 42 and ext.LGBM['deterministic'] is True
    assert ext.PLAN['outcome_delay_days'] >= 2
    assert all(feature in ext.HISTORY_FEATURES for feature in ext.CONDITIONAL_FEATURES)
    assert not any(feature.startswith('y_') for feature in ext.HISTORY_FEATURES)
    assert 'lgbm_censored_floor' not in ext.PLAN['point_candidates']


def test_every_regression_and_quantile_fit_excludes_censored_targets(monkeypatch):
    import lightgbm
    fitted=[]
    class Model:
        def __init__(self,*args,**kwargs): pass
        def fit(self,x,y,**kwargs):
            fitted.append(np.asarray(y).copy())
            return self
        def predict(self,x): return np.full(len(x),100.0)
    monkeypatch.setattr(lightgbm,'LGBMRegressor',Model)
    monkeypatch.setattr(ext,'estimator',lambda columns:Model())
    data=frame(days(date(2025,1,1),35),[100.0]*34+[401.0],censored=[False]*34+[True])
    for name in ext.HISTORY_FEATURES:data[name]=0.0
    data['obs24_aqi']=0.0
    output=ext.history_candidates(data,[data])[0]
    assert 'lgbm_censored_floor' not in output
    assert fitted and all(len(y)==34 and np.all(y==100.0) for y in fitted)


def test_catalogue_exposure_counts_monitors_removed_by_recent_activity(tmp_path, monkeypatch):
    def location(identifier, first, last):
        return {'id': identifier, 'provider': {'name': 'CPCB'}, 'coordinates': {'latitude': 1.0, 'longitude': 1.0},
                'datetimeFirst': {'utc': first}, 'datetimeLast': {'utc': last},
                'sensors': [{'parameter': {'name': p, 'units': 'µg/m³'}} for p in ('pm25', 'pm10', 'o3')]}
    catalogue = [location(1, '2020-01-01T00:00:00Z', '2026-10-01T00:00:00Z'),    # survivor
                 location(2, '2020-01-01T00:00:00Z', '2025-12-01T00:00:00Z'),    # reported at start, lost later
                 location(3, '2025-08-01T00:00:00Z', '2026-10-01T00:00:00Z'),    # late entrant
                 location(4, '2020-01-01T00:00:00Z', '2024-01-01T00:00:00Z')]    # gone before the study
    catalogue[3]['sensors'] = catalogue[3]['sensors'][:2]                         # structurally ineligible
    path = tmp_path / 'catalogue.json'
    path.write_text(__import__('json').dumps({'results': catalogue}), encoding='utf-8')
    monkeypatch.setattr(ext.catalogue, 'CATALOGUE', path)
    exposure = ext.catalogue_exposure('2025-02-19')
    assert exposure['structurally_eligible'] == 3 and exposure['eligible_under_study_rule'] == 2
    assert exposure['reporting_at_study_start'] == 2 and exposure['of_those_dropped_by_recent_activity_rule'] == 1
    assert exposure['started_after_study_start'] == 1
