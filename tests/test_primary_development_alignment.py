from datetime import date, datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest
from src.research.calibration.availability import Cutoffs, LeakageError
from src.research.calibration.primary_dataset import align, read_development
from src.research.calibration.protocol import load
from src.research.calibration.primary import guard_primary_row


def inputs():
    target = date(2025, 2, 19)
    cut = Cutoffs.for_target(target)
    reference = datetime(2025, 2, 18, tzinfo=timezone.utc)
    measured = pd.DataFrame([{'station_id': 1, 'target_date': target, 'latitude': 10., 'longitude': 77.,
                             'y_support': 'PM2.5+PM10+O3', 'target_valid': True, 'y_aqi': 401., 'censored': True,
                             'latest_measured_bin_end_utc': cut.measurement,
                             'weather_latest_run_bound_utc': reference, 'obs24_aqi': 100.}])
    forecasts = pd.DataFrame([{'station_id': 1, 'target_date': target, 'latitude': 10., 'longitude': 77.,
                              'reference_time_utc': reference.isoformat(), 'issue_time_utc': cut.issue.isoformat(),
                              'cams_aqi_static_three': 120., 'cams_six': 140.,
                              'cams_sub_PM2.5': 120., 'cams_sub_PM10': 100., 'cams_sub_O3': 80.}])
    return measured, forecasts


def test_censored_target_retained_and_never_enters_predictors():
    measured, forecasts = inputs()
    frame, features = align(measured, forecasts, load())
    assert len(frame) == 1 and frame.iloc[0].censored
    assert frame.iloc[0].cams_matched_evaluation_only == 120.
    assert not any(n.startswith(('y_', 'target_')) or 'evaluation_only' in n for n in features)
    assert frame.iloc[0].cams_aqi_frozen == 120.


def test_rejected_target_retained_without_manufactured_matched_index():
    measured, forecasts = inputs()
    measured.loc[0, 'target_valid'] = False
    measured.loc[0, 'y_support'] = ''
    frame, _ = align(measured, forecasts, load())
    assert len(frame) == 1 and np.isnan(frame.iloc[0].cams_matched_evaluation_only)


def test_late_initialization_rejected():
    measured, forecasts = inputs()
    forecasts.loc[0, 'reference_time_utc'] = '2025-02-19T00:00:00+00:00'
    with pytest.raises(LeakageError):
        align(measured, forecasts, load())


def test_future_measurements_rejected():
    measured, forecasts = inputs()
    measured.loc[0, 'latest_measured_bin_end_utc'] += timedelta(hours=1)
    with pytest.raises(LeakageError):
        align(measured, forecasts, load())


def test_sealed_rows_filtered_before_materialisation(tmp_path):
    measured, _ = inputs()
    sealed = measured.copy()
    sealed.loc[0, 'target_date'] = date(2026, 7, 10)
    path = tmp_path/'fixture.parquet'
    pd.concat([measured, sealed], ignore_index=True).to_parquet(path, index=False)
    result = read_development(path, load())
    assert result.target_date.tolist() == [date(2025, 2, 19)]


def test_final_dates_and_station_identity_mismatch_refused():
    measured, forecasts = inputs()
    forecasts.loc[0, 'longitude'] = 78.
    with pytest.raises(ValueError, match='coordinates'):
        align(measured, forecasts, load())
    measured.loc[0, 'target_date'] = date(2026, 7, 10)
    with pytest.raises(ValueError, match='development'):
        align(measured, forecasts, load())


def test_daily_history_needs_pre_cutoff_date_even_when_no_rolling_measurement():
    measured, forecasts = inputs()
    frame, _ = align(measured, forecasts, load())
    row = frame.iloc[0].to_dict()
    row['latest_measured_bin_end_utc'] = None
    row['history_lag2'] = 100.
    with pytest.raises(LeakageError):
        guard_primary_row(row, ['history_lag2'])
    row['latest_daily_lag_date'] = row['target_date'] - timedelta(days=2)
    guard_primary_row(row, ['history_lag2'])
    row['latest_daily_lag_date'] = row['target_date'] - timedelta(days=1)
    with pytest.raises(LeakageError):
        guard_primary_row(row, ['history_lag2'])


def test_zero_neighbour_count_needs_no_fabricated_measurement_timestamp():
    measured, forecasts = inputs()
    frame, _ = align(measured, forecasts, load())
    row = frame.iloc[0].to_dict()
    row.update(nbr50_count=0, latest_neighbour_bin_end_utc=None)
    guard_primary_row(row, ['nbr50_count'])
    row['nbr50_count'] = 1
    with pytest.raises(LeakageError):
        guard_primary_row(row, ['nbr50_count'])
