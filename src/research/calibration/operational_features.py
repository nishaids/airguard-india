"""Development-only, date-keyed history; never positional lags across gaps.

Daily lower-bound Severe values are not exact bias labels. They have a separate
lag indicator; the numerical history is missing and is imputed on training only.
Neighbour features must be rebuilt with permitted donors for spatial regimes.
"""
from datetime import timedelta
import numpy as np
import pandas as pd
from src.research.calibration.availability import Cutoffs, guard_daily_lag, guard_measurement


def history_features(rows, observations, forecasts):
    observed = observations.set_index(['station_id', 'target_date']).to_dict('index')
    modelled = forecasts.set_index(['station_id', 'target_date']).cams_aqi_static_three.to_dict()
    records = []
    for row in rows.itertuples():
        cut = Cutoffs.for_target(row.target_date)
        values, biases, record = [], [], {}
        for lag in range(2, 9):
            day = row.target_date - timedelta(days=lag)
            guard_daily_lag(day, cut)
            old = observed.get((row.station_id, day), {})
            exact = old.get('target_valid', False) and not old.get('censored', True)
            value = old.get('y_aqi', np.nan) if exact else np.nan
            values.append(value)
            baseline = modelled.get((row.station_id, day), np.nan)
            bias = value - baseline
            biases.append(bias)
            if lag in (2, 3, 7):
                record[f'history_lag{lag}'] = value
                record[f'history_lag{lag}_censored'] = float(old.get('censored', False)) if old.get('target_valid') else np.nan
            if lag == 2:
                record['bias_lag2'] = bias
        exact_values = np.array(values)[np.isfinite(values)]
        exact_bias = np.array(biases)[np.isfinite(biases)]
        record.update(history_roll7_n=len(exact_values),
                      history_roll7_mean=float(exact_values.mean()) if len(exact_values) >= 3 else np.nan,
                      history_roll7_std=float(exact_values.std(ddof=1)) if len(exact_values) >= 3 else np.nan,
                      bias_roll7=float(exact_bias.mean()) if len(exact_bias) >= 3 else np.nan,
                      latest_daily_lag_date=row.target_date-timedelta(days=2),
                      cams_previous_day=modelled.get((row.station_id,row.target_date-timedelta(days=1)),np.nan))
        record['cams_day_change'] = row.cams_aqi_static_three - record['cams_previous_day']
        records.append(record)
    return pd.DataFrame(records, index=rows.index)


def neighbour_features(rows, observations, donor_ids=None):
    """Only pre-issue rolling measurements, never same-day measured targets.

donor_ids allows the spatial runner to exclude held-out station/cluster feeds.
All candidate donor timestamps are checked before aggregation.
"""
    days = {day: part for day, part in observations.groupby('target_date')}
    records = []
    for day, part in rows.groupby('target_date', sort=False):
        donors = days.get(day, observations.iloc[:0])
        if donor_ids is not None:
            donors = donors[donors.station_id.isin(donor_ids)]
        donors = donors[donors.obs24_aqi.notna()]
        cut = Cutoffs.for_target(day)
        for end in donors.latest_measured_bin_end_utc:
            if pd.isna(end):
                raise ValueError('Neighbour measurement lacks bin-end provenance')
            guard_measurement(end, cut, 'neighbour donor')
        a = np.deg2rad(part[['latitude','longitude']].to_numpy(float))
        b = np.deg2rad(donors[['latitude','longitude']].to_numpy(float))
        h = np.sin((a[:,None,0]-b[None,:,0])/2)**2 + np.cos(a[:,None,0])*np.cos(b[None,:,0])*np.sin((a[:,None,1]-b[None,:,1])/2)**2
        distances = 2*6371.0088*np.arcsin(np.sqrt(np.clip(h,0,1)))
        for i, (index, row) in enumerate(part.iterrows()):
            other = donors.station_id.to_numpy() != row.station_id
            record = {'_index':index}
            for radius in (50,150):
                subset = donors[other & (distances[i] <= radius)]
                record[f'nbr{radius}_obs24_mean'] = subset.obs24_aqi.mean()
                record[f'nbr{radius}_count'] = len(subset)
            region = donors[other & (donors.region == row.region) & (donors.cluster != row.cluster)]
            record['region_obs24_mean'] = region.obs24_aqi.mean()
            # Conservative upper bound over every possible donor is sufficient.
            record['latest_neighbour_bin_end_utc'] = donors.latest_measured_bin_end_utc.max()
            records.append(record)
    return pd.DataFrame(records).set_index('_index').reindex(rows.index)
