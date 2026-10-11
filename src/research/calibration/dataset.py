"""Assemble the modelling table: one issue-time feature snapshot per station-day.

Each row is a forecast case - what was knowable at 20:00 IST on D-1 about
station s, and what was later measured on D. Beside the features it carries the
timestamps a reviewer needs to check that claim: the last measured bin read, the
latest daily lag, the latest fire detection, the bound on the weather run, and
the fact that the CAMS input is a short-lead proxy. `availability.guard_snapshot`
re-checks any row from those columns alone.

    python -m src.research.calibration.dataset
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src import config
from src.research.calibration import data
from src.research.calibration.availability import (
    FEATURE_AVAILABILITY, FEATURE_VERSION, Cutoffs, guard_fire, guard_snapshot)
from src.research.calibration.catalogue import SELECTION
from src.research.calibration.model_archives import CAMS_SOURCE
from src.research.calibration.protocol import load as load_protocol

TABLE = data.DERIVED / 'modelling_table.parquet'
SUMMARY = config.PROJECT_ROOT / 'results/research/target_dataset.json'
SNAPSHOTS = config.PROJECT_ROOT / 'results/research/feature_snapshots.json'
ELEVATION = data.ROOT / 'catalogue/elevation.json'

# Feature groups, as named in the protocol. A feature belongs to exactly one.
GROUPS = {
    'A': ['cams_matched', 'cams_six', 'cams_matched_prev', 'cams_matched_delta',
          *[f'cams_conc_{p}' for p in data.POLLUTANTS], *[f'cams_sub_{p}' for p in data.POLLUTANTS],
          'cams_hourmax_PM2.5', 'cams_hourmax_PM10', 'cams_hourmax_O3',
          'cams_pm25_night_day_ratio', 'cams_pm25_hourly_std',
          'cams_dom_PM2.5', 'cams_dom_PM10', 'cams_dom_O3', 'cams_dom_other'],
    'B': ['obs24_aqi', 'obs24_conc_PM2.5', 'obs24_conc_PM10', 'obs24_conc_O3',
          'obs_pm25_last6_mean', 'obs_pm25_last6_slope', 'y_lag2', 'y_lag3', 'y_lag7',
          'y_roll7_mean', 'y_roll7_std', 'y_roll7_n', 'obs_delta', 'obs_dev7',
          'bias_now', 'bias_lag2', 'bias_roll7', 'obs24_minus_cams'],
    'C': ['wx_temp_mean', 'wx_temp_range', 'wx_rh_mean', 'wx_wind_mean', 'wx_wind_min', 'wx_u_mean',
          'wx_v_mean', 'wx_precip_sum', 'wx_pressure_mean', 'wx_shortwave_mean', 'wx_cloud_mean'],
    'D': ['doy_sin', 'doy_cos', 'month', 'dow', 'weekend', 'season_index'],
    'E': ['latitude', 'longitude', 'elevation', 'cell_row', 'cell_column', 'cell_station_count',
          'nearest_station_km', 'nbr50_obs24_mean', 'nbr50_count', 'nbr150_obs24_mean', 'nbr150_count',
          'region_obs24_mean'],
    'F': ['fire_n50_24h', 'fire_n150_24h', 'fire_n300_24h', 'fire_n150_72h', 'fire_frp150_24h',
          'fire_min_km_72h'],
}
GROUP_KEYS = {'A': 'A_cams', 'B': 'B_measured_history', 'C': 'C_weather_forecast', 'D': 'D_temporal',
              'E': 'E_spatial', 'F': 'F_fire'}
SEASONS = {12: 'winter', 1: 'winter', 2: 'winter', 3: 'pre_monsoon', 4: 'pre_monsoon', 5: 'pre_monsoon',
           6: 'monsoon', 7: 'monsoon', 8: 'monsoon', 9: 'monsoon', 10: 'post_monsoon', 11: 'post_monsoon'}
SEASON_INDEX = {'winter': 0, 'pre_monsoon': 1, 'monsoon': 2, 'post_monsoon': 3}


def features(groups='ABCDE'):
    return [name for group in groups for name in GROUPS[group]]


def elevations(stations):
    """Station elevation from the Open-Meteo elevation endpoint, cached."""
    cache = json.loads(ELEVATION.read_text(encoding='utf-8')) if ELEVATION.exists() else {}
    missing = stations[~stations['station_id'].astype(str).isin(cache)]
    for offset in range(0, len(missing), 100):
        chunk = missing.iloc[offset:offset + 100]
        query = urllib.parse.urlencode({
            'latitude': ','.join(f'{v:.5f}' for v in chunk['latitude']),
            'longitude': ','.join(f'{v:.5f}' for v in chunk['longitude'])})
        with urllib.request.urlopen('https://api.open-meteo.com/v1/elevation?' + query, timeout=60) as response:  # noqa: S310
            values = json.loads(response.read().decode('utf-8')).get('elevation') or []
        for station_id, value in zip(chunk['station_id'], values):
            cache[str(station_id)] = value
    ELEVATION.parent.mkdir(parents=True, exist_ok=True)
    ELEVATION.write_text(json.dumps(cache), encoding='utf-8')
    return stations['station_id'].astype(str).map(cache).astype(float)


def lag_features(targets, cams_matched):
    """Daily-index lags and recent measured-minus-CAMS bias, from D-2 and earlier only."""
    frames = []
    for station_id, group in targets.groupby('station_id'):
        index = pd.date_range(group['target_date'].min(), group['target_date'].max(), freq='D')
        y = group.set_index(pd.to_datetime(group['target_date']))['y_aqi'].reindex(index).astype(float)
        modelled = (cams_matched[cams_matched['station_id'] == station_id]
                    .set_index(pd.to_datetime(cams_matched.loc[cams_matched['station_id'] == station_id, 'target_date']))
                    ['cams_matched'].reindex(index).astype(float))
        bias = y - modelled
        past = y.shift(2)          # the most recent complete day at the cutoff is D-2
        past_bias = bias.shift(2)
        frames.append(pd.DataFrame({
            'station_id': station_id, 'target_date': index.date,
            'y_lag2': past, 'y_lag3': y.shift(3), 'y_lag7': y.shift(7),
            'y_roll7_mean': past.rolling(7, min_periods=3).mean(),
            'y_roll7_std': past.rolling(7, min_periods=3).std(),
            'y_roll7_n': past.rolling(7, min_periods=1).count(),
            'bias_lag2': past_bias, 'bias_roll7': past_bias.rolling(7, min_periods=3).mean(),
            'cams_matched_prev': modelled.shift(1),
        }))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def neighbour_features(table, stations, distances):
    """Other stations' issue-time index, within 50 and 150 km and across the region."""
    order = list(stations['station_id'])
    matrix = (table.pivot_table(index='target_date', columns='station_id', values='obs24_aqi', aggfunc='first')
              .reindex(columns=order))
    values = matrix.to_numpy(dtype=float)
    present = ~np.isnan(values)
    filled = np.where(present, values, 0.0)
    out = {}
    for radius in (50, 150):
        mask = (distances <= radius).astype(float)           # station x station, diagonal excluded
        counts = present.astype(float) @ mask.T
        sums = filled @ mask.T
        with np.errstate(invalid='ignore', divide='ignore'):
            out[f'nbr{radius}_obs24_mean'] = np.where(counts > 0, sums / counts, np.nan)
        out[f'nbr{radius}_count'] = counts
    # Regional mean excluding the station's own urban cluster.
    region = stations['region'].to_numpy()
    cluster = stations['cluster'].to_numpy()
    other = ((region[:, None] == region[None, :]) & (cluster[:, None] != cluster[None, :])).astype(float)
    counts = present.astype(float) @ other.T
    sums = filled @ other.T
    with np.errstate(invalid='ignore', divide='ignore'):
        out['region_obs24_mean'] = np.where(counts > 0, sums / counts, np.nan)
    frames = []
    for name, array in out.items():
        frame = pd.DataFrame(array, index=matrix.index, columns=order).stack(future_stack=True).rename(name)
        frames.append(frame)
    return pd.concat(frames, axis=1).reset_index().rename(columns={'level_1': 'station_id'})


def fire_features(stations, dates, detections):
    """Detections near each station in the 24 and 72 hours before the fire cutoff."""
    from sklearn.neighbors import BallTree
    columns = GROUPS['F']
    if detections.empty:
        return pd.DataFrame(columns=['station_id', 'target_date', 'latest_fire_acquired_utc', *columns])
    # Naive UTC nanoseconds: numpy has no timezone, and both sides of every
    # comparison below are UTC.
    times = detections['acquired_utc'].dt.tz_convert('UTC').dt.tz_localize(None).to_numpy(dtype='datetime64[ns]')
    radians = np.deg2rad(detections[['latitude', 'longitude']].to_numpy(dtype=float))
    frp = detections['frp'].to_numpy(dtype=float)
    points = np.deg2rad(stations[['latitude', 'longitude']].to_numpy(dtype=float))
    earth = 6371.0088
    rows = []
    for day in dates:
        cutoffs = Cutoffs.for_target(day)
        cut = np.datetime64(cutoffs.fire.replace(tzinfo=None), 'ns')
        low = np.searchsorted(times, cut - np.timedelta64(72, 'h'), side='right')
        high = np.searchsorted(times, cut, side='right')
        latest = None
        if high > low:
            latest = pd.Timestamp(times[high - 1]).tz_localize('UTC')
            guard_fire(latest.to_pydatetime(), cutoffs)
            tree = BallTree(radians[low:high], metric='haversine')
            found, dist = tree.query_radius(points, r=300.0 / earth, return_distance=True)
            nearest = tree.query(points, k=1)[0][:, 0] * earth
            recent = times[low:high] > cut - np.timedelta64(24, 'h')
            power = frp[low:high]
        for index, station_id in enumerate(stations['station_id']):
            if high > low:
                km = dist[index] * earth
                last24 = recent[found[index]]
                rows.append((station_id, day, latest,
                             int((last24 & (km <= 50)).sum()), int((last24 & (km <= 150)).sum()),
                             int(last24.sum()), int((km <= 150).sum()),
                             float(np.nansum(power[found[index]][last24 & (km <= 150)])),
                             float(min(nearest[index], 500.0))))
            else:
                rows.append((station_id, day, None, 0, 0, 0, 0, 0.0, 500.0))
    return pd.DataFrame(rows, columns=['station_id', 'target_date', 'latest_fire_acquired_utc', *columns])


def build(extra_lag_hours=0, write=True, jobs=-2):
    protocol = load_protocol()
    selection = json.loads(SELECTION.read_text(encoding='utf-8'))
    hours = data.manifest('openaq_hours_manifest.json')
    cams_manifest = data.manifest('cams_archive_manifest.json')
    weather_manifest = data.manifest('weather_archive_manifest.json')
    firms_manifest = data.manifest('firms_archive_manifest.json') or {'files': {}}
    dates = data.study_dates(protocol)
    stations, distances = data.station_table(selection)
    complete = {int(k) for k, v in hours['stations'].items() if v.get('complete')}
    keep = stations['station_id'].isin(complete).to_numpy()
    stations, distances = stations[keep].reset_index(drop=True), distances[np.ix_(keep, keep)]
    stations['elevation'] = elevations(stations)

    targets, rolling, audits = data.measured_frames(dates, hours['stations'], jobs=jobs,
                                                    extra_lag_hours=extra_lag_hours)
    targets = targets[targets['station_id'].isin(complete)]
    pollutant_columns = [f'y_conc_{p}' for p in data.POLLUTANTS]
    targets['y_support'] = targets[pollutant_columns].notna().apply(
        lambda row: data.support_tag([p for p, ok in zip(data.POLLUTANTS, row) if ok]), axis=1)

    # CAMS, matched to what each station actually measured on each day.
    cell_of = stations.set_index('station_id')['cell_id']
    supports = {}
    for station_id, tag in zip(targets['station_id'], targets['y_support']):
        supports.setdefault(cell_of[station_id], set()).add(tuple(data.POLLUTANTS) if tag == 'six' else tuple(tag.split('+')))
    cams = data.cams_frames(dates, cams_manifest, supports, jobs=jobs)

    table = targets.merge(stations, on='station_id', how='left')
    table = table.merge(cams, on=['cell_id', 'target_date'], how='left')
    tags = table['y_support'].to_numpy()
    for name, prefix in (('cams_matched', 'cams_aqi__'), ('cams_matched_status', 'cams_status__'),
                         ('cams24_matched', 'cams24_aqi__')):
        values = np.full(len(table), np.nan, dtype=object)
        for tag in set(tags):
            column = f'{prefix}{tag}'
            if column in table:
                values[tags == tag] = table.loc[tags == tag, column].to_numpy()
        table[name] = values
    table['cams_matched'] = pd.to_numeric(table['cams_matched'], errors='coerce')
    table['cams24_matched'] = pd.to_numeric(table['cams24_matched'], errors='coerce')
    table['cams_six'] = pd.to_numeric(table['cams_aqi__six'], errors='coerce')
    table = table.drop(columns=[c for c in table.columns if c.startswith(('cams_aqi__', 'cams_status__', 'cams24_aqi__'))])

    table = table.merge(rolling, on=['station_id', 'target_date'], how='left')
    lags = lag_features(table[['station_id', 'target_date', 'y_aqi']], table[['station_id', 'target_date', 'cams_matched']])
    table = table.merge(lags, on=['station_id', 'target_date'], how='left')
    table = table.merge(neighbour_features(table, stations, distances), on=['station_id', 'target_date'], how='left')
    weather = data.weather_frame(weather_manifest) if weather_manifest else pd.DataFrame()
    if not weather.empty:
        table = table.merge(weather.drop(columns=['wx_hours']), on=['weather_point', 'target_date'], how='left')
    fires = fire_features(stations, dates, data.fire_detections(firms_manifest))
    table = table.merge(fires, on=['station_id', 'target_date'], how='left')

    # Derived columns. The merges above leave a fragmented frame; consolidate once.
    table = table.copy()
    for column in GROUPS['C'] + GROUPS['F']:
        if column not in table:
            table[column] = np.nan
    numeric = lambda name: pd.to_numeric(table[name], errors='coerce')  # noqa: E731
    table['y'] = numeric('y_aqi')
    table['persistence'] = numeric('obs24_aqi')
    table['obs24_aqi'] = table['persistence']
    table['cams_matched_delta'] = table['cams_matched'] - table['cams_matched_prev']
    table['obs_delta'] = table['obs24_aqi'] - table['y_lag2']
    table['obs_dev7'] = table['obs24_aqi'] - table['y_roll7_mean']
    table['bias_now'] = table['obs24_aqi'] - table['cams24_matched']
    table['obs24_minus_cams'] = table['obs24_aqi'] - table['cams_matched']
    dominant = table['cams_dominant'].fillna('none')
    for pollutant in ('PM2.5', 'PM10', 'O3'):
        table[f'cams_dom_{pollutant}'] = (dominant == pollutant).astype(float)
    table['cams_dom_other'] = (~dominant.isin(['PM2.5', 'PM10', 'O3'])).astype(float)
    when = pd.to_datetime(table['target_date'])
    table['doy_sin'] = np.sin(2 * np.pi * when.dt.dayofyear / 365.25)
    table['doy_cos'] = np.cos(2 * np.pi * when.dt.dayofyear / 365.25)
    table['month'] = when.dt.month
    table['dow'] = when.dt.dayofweek
    table['weekend'] = (table['dow'] >= 5).astype(float)
    table['season'] = table['month'].map(SEASONS)
    table['season_index'] = table['season'].map(SEASON_INDEX)
    table['censored'] = table['y_status'] == 'LOWER_BOUND'

    # Audit columns: what a reviewer needs to re-check a row.
    cut = {day: Cutoffs.for_target(day) for day in dates}
    table['issue_utc'] = table['target_date'].map(lambda d: cut[d].issue)
    table['measurement_cutoff_utc'] = table['target_date'].map(lambda d: cut[d].measurement)
    table['fire_cutoff_utc'] = table['target_date'].map(lambda d: cut[d].fire)
    table['weather_latest_run_bound_utc'] = table['target_date'].map(lambda d: cut[d].weather_latest_run)
    table['latest_daily_lag_date'] = table['target_date'].map(lambda d: d - timedelta(days=2))
    table['latest_neighbour_bin_end_utc'] = table.groupby('target_date')['latest_measured_bin_end_utc'].transform('max')
    table['cams_source'] = CAMS_SOURCE
    table['cams_issue_time_valid'] = False
    table['feature_version'] = FEATURE_VERSION
    table['data_version'] = data.data_version()
    table['protocol_sha256'] = protocol['_sha256']
    for column in features('ABCDEF'):
        table[column] = pd.to_numeric(table[column], errors='coerce')

    # Every row is re-checked by the same guard a reviewer would use.
    verified = 0
    for row in table[['target_date', 'latest_measured_bin_end_utc', 'latest_neighbour_bin_end_utc',
                      'latest_daily_lag_date', 'latest_fire_acquired_utc',
                      'weather_latest_run_bound_utc']].to_dict('records'):
        row = {k: (None if (v is None or v is pd.NaT or (isinstance(v, float) and np.isnan(v))) else v)
               for k, v in row.items()}
        guard_snapshot(row)
        verified += 1

    table = table.copy()
    minimum = int(protocol['stations']['minimum_valid_target_days'])
    days = table.groupby('station_id')['y'].count()
    eligible = set(days[days >= minimum].index)
    table['station_eligible'] = table['station_id'].isin(eligible)
    table = table.sort_values(['target_date', 'station_id']).reset_index(drop=True)

    summary = summarise(table, stations, audits, protocol, verified, hours, extra_lag_hours)
    if write:
        data.DERIVED.mkdir(parents=True, exist_ok=True)
        table.to_parquet(TABLE, index=False)
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
        write_snapshot_audit(table, summary)
        write_availability(table)
    return table, summary


def summarise(table, stations, audits, protocol, verified, hours, extra_lag_hours):
    used = table[table['station_eligible']]
    rejected = {}
    for audit in audits.values():
        for info in audit.values():
            for reason, count in (info.get('rejected') or {}).items():
                rejected[reason] = rejected.get(reason, 0) + count
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'protocol_version': protocol['protocol_version'], 'protocol_sha256': protocol['_sha256'],
        'data_version': data.data_version(), 'feature_version': FEATURE_VERSION,
        'extra_measurement_lag_hours': extra_lag_hours,
        'window': [str(table['target_date'].min()), str(table['target_date'].max())],
        'stations_fetched': int(sum(1 for s in hours['stations'].values() if s.get('complete'))),
        'stations_with_any_target': int(table['station_id'].nunique()),
        'stations_eligible': int(used['station_id'].nunique()),
        'cities': int(used['city'].nunique()), 'urban_clusters': int(used['cluster'].nunique()),
        'states': int(used['state'].nunique()), 'regions': used['region'].value_counts().to_dict(),
        'cams_cells': int(used['cell_id'].nunique()),
        'station_days': int(len(used)),
        'station_days_exact': int((~used['censored']).sum()),
        'station_days_censored_severe': int(used['censored'].sum()),
        'station_days_with_cams': int(used['cams_matched'].notna().sum()),
        'station_days_with_persistence': int(used['persistence'].notna().sum()),
        'primary_evaluation_rows': int((used['cams_matched'].notna() & used['persistence'].notna()
                                        & ~used['censored']).sum()),
        'target_dates': int(used['target_date'].nunique()),
        'category_counts': used['y_category'].value_counts().sort_index().to_dict(),
        'dominant_pollutant': used['y_dominant'].value_counts().to_dict(),
        'measured_support': used['y_support'].value_counts().to_dict(),
        'season_counts': used['season'].value_counts().to_dict(),
        'hourly_bins_rejected': rejected,
        'hourly_bins_kept': int(sum(info.get('kept', 0) for audit in audits.values() for info in audit.values())),
        'upstream_provider': 'CPCB (OpenAQ provider field) for every station; values are not an official CPCB export',
        'snapshot_rows_verified_by_guard': verified,
        'target_note': 'AirGuard CPCB-style AQI from measured hourly concentrations; not an official bulletin value.',
    }


def write_snapshot_audit(table, summary):
    """A small, committed record that the snapshot table passed its own guard."""
    sample = table[table['station_eligible']].sample(n=min(5, len(table)), random_state=42)
    columns = ['station_id', 'station_name', 'target_date', 'issue_utc', 'measurement_cutoff_utc',
               'latest_measured_bin_end_utc', 'latest_daily_lag_date', 'fire_cutoff_utc',
               'latest_fire_acquired_utc', 'weather_latest_run_bound_utc', 'cams_source',
               'cams_issue_time_valid', 'feature_version', 'data_version', 'y', 'cams_matched', 'persistence']
    SNAPSHOTS.write_text(json.dumps({
        'generated_at': summary['generated_at'], 'table': config.portable(TABLE),
        'rows': int(len(table)), 'rows_verified_by_guard': summary['snapshot_rows_verified_by_guard'],
        'guard': 'src/research/calibration/availability.py::guard_snapshot',
        'issue_time_valid_end_to_end': False,
        'why_not': 'The CAMS feature group is a short-lead proxy; every other group passed its cutoff on every row.',
        'audit_columns': columns[3:14],
        'how_to_audit_a_row': 'python -m src.research.calibration.dataset audit <station_id> <YYYY-MM-DD>',
        'sample_rows': json.loads(sample[columns].to_json(orient='records', date_format='iso')),
    }, indent=1, default=str), encoding='utf-8')


def write_availability(table):
    """Machine-readable availability metadata and the document generated from it."""
    record = {'feature_version': FEATURE_VERSION, 'generated_at': datetime.now(timezone.utc).isoformat(),
              'groups': {}}
    lines = ['# Feature availability', '',
             'Generated by `python -m src.research.calibration.dataset` from '
             '`src/research/calibration/availability.py`. Do not edit by hand.', '',
             'For every candidate feature the question is the same: when would this value have become '
             'available in real life? A feature whose answer is later than the issue time is refused by '
             'a guard that raises rather than filters.', '',
             '| Group | Source | Value time | Provider issue time | Latest permissible use | '
             'Issue-time valid | Reconstructable | Features |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for group, names in GROUPS.items():
        meta = FEATURE_AVAILABILITY[GROUP_KEYS[group]]
        present = [n for n in names if n in table.columns]
        record['groups'][group] = dict(meta, features=present,
                                       missing_share={n: float(table[n].isna().mean()) for n in present})
        lines.append(f"| {group} | {meta['source']} | {meta['value_time']} | {meta['provider_issue_time']} | "
                     f"{meta['latest_permissible_use']} | {'yes' if meta['issue_time_valid'] else '**no**'} | "
                     f"{'yes' if meta['operationally_reconstructable'] else '**no**'} | {len(present)} |")
    lines += ['', '## What is not issue-time valid', '',
              FEATURE_AVAILABILITY['A_cams']['reason'], '',
              'Consequence: no result of the retrospective study may be described as issue-time valid end '
              'to end. The raw-CAMS baseline and the correction model read the same fields, so their '
              'comparison is like for like, but the absolute error of both is likely optimistic.', '',
              '## Guards', '',
              '- `guard_measurement`: a measured hourly bin must have ended by 17:00 IST on D-1.',
              '- `guard_daily_lag`: a complete measured day must be D-2 or earlier.',
              '- `guard_fire`: a detection must have been acquired by the fire cutoff.',
              '- `guard_weather_run`: a weather run must have been initialised by the issue time.',
              '- `guard_snapshot`: re-checks a stored row from its audit columns alone.', '',
              'Tests in `tests/test_calibration_leakage.py` build rows that violate each rule and assert '
              'that the pipeline refuses them.', '']
    (config.PROJECT_ROOT / 'results/research/feature_availability.json').write_text(
        json.dumps(record, indent=1), encoding='utf-8')
    (config.PROJECT_ROOT / 'docs/research/FEATURE_AVAILABILITY.md').write_text('\n'.join(lines), encoding='utf-8')


def load():
    return pd.read_parquet(TABLE)


def audit(station_id, target_date):
    """Print one forecast case with every timestamp that bears on its validity."""
    table = load()
    rows = table[(table['station_id'] == int(station_id)) & (table['target_date'].astype(str) == str(target_date))]
    if rows.empty:
        print('No such forecast case.')
        return 1
    row = rows.iloc[0].to_dict()
    cutoffs = guard_snapshot({k: (None if pd.isna(v) else v) if not isinstance(v, (list, dict)) else v
                              for k, v in row.items()})
    print(json.dumps({
        'station': row['station_name'], 'target_date': str(row['target_date']),
        'issue_utc': str(cutoffs.issue), 'measurement_cutoff_utc': str(cutoffs.measurement),
        'latest_measured_bin_end_utc': str(row.get('latest_measured_bin_end_utc')),
        'latest_daily_lag_date': str(row.get('latest_daily_lag_date')),
        'fire_cutoff_utc': str(cutoffs.fire), 'latest_fire_acquired_utc': str(row.get('latest_fire_acquired_utc')),
        'weather_latest_run_bound_utc': str(cutoffs.weather_latest_run),
        'cams_source': row['cams_source'], 'cams_issue_time_valid': bool(row['cams_issue_time_valid']),
        'observed_index': row['y'], 'raw_cams_matched': row['cams_matched'], 'persistence': row['persistence'],
        'verdict': 'every non-CAMS input predates its cutoff; the CAMS input is a short-lead proxy',
    }, indent=1, default=str))
    return 0


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == 'audit':
        return audit(sys.argv[2], sys.argv[3])
    _table, summary = build()
    print(json.dumps({k: summary[k] for k in (
        'stations_eligible', 'cities', 'urban_clusters', 'cams_cells', 'station_days', 'station_days_exact',
        'station_days_censored_severe', 'primary_evaluation_rows', 'target_dates', 'category_counts',
        'measured_support', 'snapshot_rows_verified_by_guard')}, indent=1, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
