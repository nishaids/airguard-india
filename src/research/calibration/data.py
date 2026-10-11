"""Raw caches to analysis frames: hourly bins, daily targets, CAMS, weather, fire.

Every daily index in the study - the measured target, the persistence baseline
and the CAMS baseline - is produced by the one CPCB-style engine in
`src/nationwide/aqi.py`. Nothing here re-implements a breakpoint or an averaging
rule; it only decides which hourly rows the engine is shown.
"""
from __future__ import annotations

import bisect
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src import config
from src.features.static_site import cams_cell
from src.nationwide.aqi import aggregate, normalize, valid
from src.research.calibration.availability import IST, Cutoffs, guard_measurement

ROOT = config.PROJECT_ROOT / 'data/research'
MANIFESTS = config.PROJECT_ROOT / 'results/research/data_manifests'
DERIVED = ROOT / 'derived'
POLLUTANTS = ('PM2.5', 'PM10', 'NO2', 'SO2', 'CO', 'O3')
CAMS_FIELDS = {'pm2_5': 'PM2.5', 'pm10': 'PM10', 'nitrogen_dioxide': 'NO2',
               'sulphur_dioxide': 'SO2', 'carbon_monoxide': 'CO', 'ozone': 'O3'}
MINIMUM_COVERAGE = 75.0
STUCK_RUN = 6
HOUR = timedelta(hours=1)


def manifest(name):
    path = MANIFESTS / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def data_version():
    """One hash over every raw-cache manifest: the identity of the study's inputs."""
    digest = hashlib.sha256()
    for name in ('station_selection.json', 'openaq_hours_manifest.json', 'cams_archive_manifest.json',
                 'weather_archive_manifest.json', 'firms_archive_manifest.json'):
        payload = manifest(name)
        if payload is None:
            continue
        files = payload.get('files') or payload.get('stations') or payload.get('stations', {})
        hashes = sorted(
            (str(key), json.dumps(value.get('sha256') or sorted(
                (p, s.get('sha256')) for p, s in (value.get('sensors') or {}).items()), sort_keys=True))
            for key, value in (files.items() if isinstance(files, dict) else []))
        digest.update(name.encode())
        digest.update(json.dumps(hashes).encode())
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# Measured hourly bins
# --------------------------------------------------------------------------- #
def read_sensor(path, pollutant):
    """Apply the protocol's hourly bin rules. Returns kept bins and why others went."""
    kept, rejected = {}, Counter()
    with gzip.open(config.PROJECT_ROOT / path, 'rt', encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            try:
                begin = datetime.fromisoformat(row['valid_from_utc'])
                end = datetime.fromisoformat(row['valid_to_utc'])
            except (KeyError, ValueError):
                rejected['unparseable_period'] += 1
                continue
            if end - begin != HOUR:
                rejected['not_an_hourly_bin'] += 1
                continue
            if row.get('flagged') == '1':
                rejected['provider_flagged'] += 1
                continue
            coverage = row.get('coverage_pct')
            if coverage not in (None, '') and float(coverage) < MINIMUM_COVERAGE:
                rejected['under_75_percent_coverage'] += 1
                continue
            try:
                raw = float(row['value'])
            except (TypeError, ValueError):
                rejected['missing_value'] += 1
                continue
            value = normalize(pollutant, raw, row.get('unit') or '')
            if value is None:
                rejected['invalid_value_or_unit'] += 1
                continue
            if value == 0:
                # Zero mass is an outage reported as a number, not an ambient reading.
                rejected['zero_reading'] += 1
                continue
            kept[begin] = value
    stuck = stuck_runs(kept)
    for begin in stuck:
        del kept[begin]
    if stuck:
        rejected['stuck_sensor_run'] += len(stuck)
    return kept, rejected


def stuck_runs(bins, minimum=STUCK_RUN):
    """Bin starts belonging to a run of identical values on consecutive hours."""
    flagged, run = [], []
    previous_time, previous_value = None, None
    for begin in sorted(bins):
        value = bins[begin]
        if previous_time is not None and value == previous_value and begin - previous_time == HOUR:
            run.append(begin)
        else:
            if len(run) >= minimum:
                flagged += run
            run = [begin]
        previous_time, previous_value = begin, value
    if len(run) >= minimum:
        flagged += run
    return flagged


def station_hourly(entry):
    """All usable bins of one station as {bin_start: {pollutant: value}}."""
    rows, audit = {}, {}
    for pollutant, sensor in (entry.get('sensors') or {}).items():
        if not sensor.get('file'):
            continue
        kept, rejected = read_sensor(sensor['file'], pollutant)
        audit[pollutant] = {'kept': len(kept), 'returned': sensor.get('rows'), 'rejected': dict(rejected),
                            'sensor_id': sensor.get('sensor_id'), 'unit': sensor.get('units')}
        for begin, value in kept.items():
            rows.setdefault(begin, {})[pollutant] = value
    return rows, audit


class HourlySeries:
    """Sorted hourly rows with slicing, in the shape the AQI engine consumes."""

    def __init__(self, rows):
        self.times = sorted(rows)
        # The engine accepts datetimes directly, which avoids re-parsing an ISO
        # string several hundred times per call.
        self.rows = [dict(rows[t], time=t) for t in self.times]

    def between(self, start, end):
        low = bisect.bisect_left(self.times, start)
        high = bisect.bisect_left(self.times, end)
        return self.rows[low:high]

    def last_time_before(self, end):
        index = bisect.bisect_left(self.times, end)
        return self.times[index - 1] if index else None


def engine_fields(result, prefix):
    """Flatten one engine result into columns."""
    pollutants = result.get('pollutants') or {}
    out = {
        f'{prefix}aqi': result.get('aqi'),
        f'{prefix}status': result.get('status'),
        f'{prefix}dominant': result.get('dominant_pollutant'),
        f'{prefix}category': (result.get('category') or {}).get('index'),
    }
    for pollutant in POLLUTANTS:
        info = pollutants.get(pollutant) or {}
        out[f'{prefix}conc_{pollutant}'] = info.get('concentration')
        out[f'{prefix}sub_{pollutant}'] = (info.get('sub_index') or {}).get('value')
        out[f'{prefix}hours_{pollutant}'] = info.get('valid_hours')
    return out


def daily_index(series, start, end, rolling=False, pollutants=None):
    """Run the engine on the rows a daily or rolling window may see."""
    rows = series.between(start - timedelta(hours=8), end)
    if pollutants is not None:
        rows = [{key: value for key, value in row.items() if key == 'time' or key in pollutants} for row in rows]
    return aggregate(rows, start, end, rolling=rolling)


def measured_station(key, entry, study_dates, extra_lag_hours=0):
    """One station's daily targets and issue-time rolling indices.

    `extra_lag_hours` moves the measurement window further into the past. It
    exists for the stale-feed sensitivity analysis and can only make the inputs
    older, never newer.
    """
    if extra_lag_hours < 0:
        raise ValueError('A measurement window can be made older, not newer.')
    station_id = int(key)
    rows, audit = station_hourly(entry)
    targets, rolling = [], []
    if not rows:
        return targets, rolling, audit
    series = HourlySeries(rows)
    for day in study_dates:
        cutoffs = Cutoffs.for_target(day)
        result = daily_index(series, cutoffs.target_start, cutoffs.target_end)
        if result.get('status') != 'INSUFFICIENT_DATA':
            targets.append({'station_id': station_id, 'target_date': day, **engine_fields(result, 'y_')})
        # Persistence: the 24 hours of bins that had ENDED by the measurement cutoff,
        # aggregated by the same rule as the target (24-hour means; for CO and O3 the
        # highest complete 8-hour mean inside the window). The engine's "rolling
        # snapshot" mode would instead demand that the final eight hours of ozone be
        # gap-free, which leaves no persistence forecast on roughly four days in ten.
        window_end = cutoffs.measurement - timedelta(hours=extra_lag_hours)
        window_start = window_end - timedelta(hours=24)
        latest = series.last_time_before(window_end - HOUR + timedelta(seconds=1))
        if latest is not None and latest >= window_start:
            guard_measurement(latest + HOUR, cutoffs)
            seen = daily_index(series, window_start, window_end)
            short = _short_window(series, cutoffs, window_end)
            rolling.append({'station_id': station_id, 'target_date': day,
                            'latest_measured_bin_end_utc': latest + HOUR,
                            **engine_fields(seen, 'obs24_'), **short})
    return targets, rolling, audit


def measured_frames(study_dates, stations_manifest, jobs=-2, extra_lag_hours=0):
    """Daily targets and issue-time rolling indices for every station."""
    from joblib import Parallel, delayed
    items = [(key, entry) for key, entry in stations_manifest.items() if entry.get('complete')]
    results = Parallel(n_jobs=jobs)(
        delayed(measured_station)(key, entry, study_dates, extra_lag_hours) for key, entry in items)
    targets, rolling, audits = [], [], {}
    for (key, _entry), (station_targets, station_rolling, audit) in zip(items, results):
        targets += station_targets
        rolling += station_rolling
        audits[key] = audit
    return pd.DataFrame(targets), pd.DataFrame(rolling), audits


def _short_window(series, cutoffs, window_end=None):
    """Level and slope of PM2.5 over the last six usable hours."""
    window_end = window_end or cutoffs.measurement
    rows = series.between(window_end - timedelta(hours=6), window_end)
    values = [(r['time'], r.get('PM2.5')) for r in rows if valid(r.get('PM2.5'))]
    for moment, _value in values:
        guard_measurement(moment + HOUR, cutoffs)
    if len(values) < 3:
        return {'obs_pm25_last6_mean': None, 'obs_pm25_last6_slope': None}
    hours = np.array([(m - window_end).total_seconds() / 3600.0 for m, _ in values])
    level = np.array([v for _, v in values], dtype=float)
    slope = float(np.polyfit(hours, level, 1)[0]) if len(set(hours)) > 1 else 0.0
    return {'obs_pm25_last6_mean': float(level.mean()), 'obs_pm25_last6_slope': slope}


# --------------------------------------------------------------------------- #
# CAMS short-lead proxy
# --------------------------------------------------------------------------- #
def cams_series(record):
    """One cell's archived hourly fields, converted to the engine's units."""
    with gzip.open(config.PROJECT_ROOT / record['file'], 'rt', encoding='utf-8') as handle:
        payload = json.load(handle)
    hourly = payload['hourly']
    units = payload.get('hourly_units') or {}
    rows = {}
    for index, stamp in enumerate(hourly['time']):
        moment = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
        row = {}
        for field, pollutant in CAMS_FIELDS.items():
            raw = (hourly.get(field) or [None])[index] if index < len(hourly.get(field) or []) else None
            value = normalize(pollutant, raw, units.get(field, 'ug/m3')) if raw is not None else None
            if value is not None:
                row[pollutant] = value
        if row:
            rows[moment] = row
    return HourlySeries(rows)


def support_tag(support):
    """Stable column tag for a pollutant support."""
    ordered = tuple(p for p in POLLUTANTS if p in set(support))
    return 'six' if ordered == POLLUTANTS else '+'.join(ordered)


def cams_cell_frame(cell_id, record, study_dates, wanted):
    series = cams_series(record)
    records = []
    for day in study_dates:
        cutoffs = Cutoffs.for_target(day)
        row = {'cell_id': cell_id, 'target_date': day}
        for support in wanted:
            tag = support_tag(support)
            result = daily_index(series, cutoffs.target_start, cutoffs.target_end, pollutants=set(support))
            row[f'cams_aqi__{tag}'] = result.get('aqi')
            row[f'cams_status__{tag}'] = result.get('status')
            if tag == 'six':
                row.update(engine_fields(result, 'cams_'))
                row.update(_diurnal(series.between(cutoffs.target_start, cutoffs.target_end)))
            # The same support over the 24 hours ending at the measurement cutoff,
            # for the "current bias" of measured against modelled.
            recent = daily_index(series, cutoffs.measurement - timedelta(hours=24), cutoffs.measurement,
                                 pollutants=set(support))
            row[f'cams24_aqi__{tag}'] = recent.get('aqi')
        records.append(row)
    return records


def cams_frames(study_dates, cams_manifest, supports, jobs=-2):
    """CAMS daily indices per cell: all six species, and matched to each measured support.

    `supports` maps cell id to the pollutant supports that stations in that cell
    actually measured, so a matched index is computed once per distinct support
    rather than once per station.
    """
    from joblib import Parallel, delayed
    items = list((cams_manifest.get('files') or {}).items())
    results = Parallel(n_jobs=jobs)(
        delayed(cams_cell_frame)(
            cell_id, record, study_dates,
            sorted({tuple(p for p in POLLUTANTS if p in set(s)) for s in supports.get(cell_id, set())}
                   | {POLLUTANTS}))
        for cell_id, record in items)
    return pd.DataFrame([row for rows in results for row in rows])


def _diurnal(rows):
    """Hourly maxima and the shape of the day in the modelled fields."""
    out = {}
    for pollutant in ('PM2.5', 'PM10', 'O3'):
        values = [r[pollutant] for r in rows if valid(r.get(pollutant))]
        out[f'cams_hourmax_{pollutant}'] = max(values) if values else None
    night, day = [], []
    for r in rows:
        if not valid(r.get('PM2.5')):
            continue
        hour = r['time'].astimezone(IST).hour
        (night if hour < 6 or hour >= 21 else day if 10 <= hour < 17 else []).append(r['PM2.5'])
    out['cams_pm25_night_day_ratio'] = (float(np.mean(night)) / float(np.mean(day))
                                        if night and day and np.mean(day) > 0 else None)
    pm = [r['PM2.5'] for r in rows if valid(r.get('PM2.5'))]
    out['cams_pm25_hourly_std'] = float(np.std(pm)) if len(pm) > 1 else None
    return out


# --------------------------------------------------------------------------- #
# Weather forecast (strictly issue-time valid) and fire detections
# --------------------------------------------------------------------------- #
def weather_frame(weather_manifest):
    """Daily summaries of the 48-hour-lead forecast, per weather point and IST day."""
    lead = weather_manifest['lead']
    frames = []
    for key, record in (weather_manifest.get('files') or {}).items():
        with gzip.open(config.PROJECT_ROOT / record['file'], 'rt', encoding='utf-8') as handle:
            payload = json.load(handle)
        hourly = payload['hourly']
        frame = pd.DataFrame({name.replace(f'_{lead}', ''): values
                              for name, values in hourly.items() if name != 'time'})
        moments = pd.to_datetime(hourly['time'], utc=True)
        frame['target_date'] = (moments + pd.Timedelta(hours=5, minutes=30)).date
        radians = np.deg2rad(frame['wind_direction_10m'])
        frame['u'] = -frame['wind_speed_10m'] * np.sin(radians)
        frame['v'] = -frame['wind_speed_10m'] * np.cos(radians)
        grouped = frame.groupby('target_date')
        daily = pd.DataFrame({
            'wx_temp_mean': grouped['temperature_2m'].mean(),
            'wx_temp_range': grouped['temperature_2m'].max() - grouped['temperature_2m'].min(),
            'wx_rh_mean': grouped['relative_humidity_2m'].mean(),
            'wx_wind_mean': grouped['wind_speed_10m'].mean(),
            'wx_wind_min': grouped['wind_speed_10m'].min(),
            'wx_u_mean': grouped['u'].mean(), 'wx_v_mean': grouped['v'].mean(),
            'wx_precip_sum': grouped['precipitation'].sum(min_count=1),
            'wx_pressure_mean': grouped['surface_pressure'].mean(),
            'wx_shortwave_mean': grouped['shortwave_radiation'].mean(),
            'wx_cloud_mean': grouped['cloud_cover'].mean(),
            'wx_hours': grouped['temperature_2m'].count(),
        }).reset_index()
        # A day summarised from a handful of hours is not a daily forecast.
        daily.loc[daily['wx_hours'] < 18, [c for c in daily.columns if c.startswith('wx_') and c != 'wx_hours']] = np.nan
        daily['weather_point'] = key
        frames.append(daily)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fire_detections(firms_manifest):
    """Every detection with its acquisition time; low-confidence detections dropped."""
    frames = []
    for _name, record in sorted((firms_manifest.get('files') or {}).items()):
        with gzip.open(config.PROJECT_ROOT / record['file'], 'rt', encoding='utf-8') as handle:
            text = handle.read()
        if text.count('\n') < 2:
            continue
        frame = pd.read_csv(io.StringIO(text), dtype={'acq_time': str})
        frames.append(frame[['latitude', 'longitude', 'acq_date', 'acq_time', 'frp', 'confidence']])
    if not frames:
        return pd.DataFrame(columns=['latitude', 'longitude', 'acquired_utc', 'frp'])
    table = pd.concat(frames, ignore_index=True).drop_duplicates()
    table = table[table['confidence'].astype(str).str.lower() != 'l']
    stamp = table['acq_date'].astype(str) + ' ' + table['acq_time'].astype(str).str.zfill(4)
    table['acquired_utc'] = pd.to_datetime(stamp, format='%Y-%m-%d %H%M', utc=True)
    return table[['latitude', 'longitude', 'acquired_utc', 'frp']].sort_values('acquired_utc').reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def urban_clusters(stations, radius_km=25.0):
    """Single-linkage clusters: stations within the radius of one another share a cluster."""
    ids = [s['location_id'] for s in stations]
    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a_index, a in enumerate(stations):
        for b in stations[a_index + 1:]:
            if haversine_km(a['latitude'], a['longitude'], b['latitude'], b['longitude']) <= radius_km:
                parent[find(a['location_id'])] = find(b['location_id'])
    roots = sorted({find(i) for i in ids})
    label = {root: index for index, root in enumerate(roots)}
    return {i: label[find(i)] for i in ids}


def station_table(selection):
    """Static per-station attributes, including the measured CAMS cell."""
    stations = selection['stations']
    clusters = urban_clusters(stations)
    large = {city for city, count in Counter(s['city'] for s in _eligible_city_counts(selection)).items()}
    rows = []
    for station in stations:
        cell = cams_cell(station['latitude'], station['longitude'])
        rows.append({
            'station_id': station['location_id'], 'station_name': station['name'], 'city': station['city'],
            'state': station.get('state'), 'region': station['region'], 'agency': station.get('agency'),
            'provider': station.get('provider'), 'owner': station.get('owner'),
            'latitude': station['latitude'], 'longitude': station['longitude'],
            'stratum': station.get('stratum'), 'cluster': clusters[station['location_id']],
            'cell_id': cell['cell_id'], 'cell_row': cell['row'], 'cell_column': cell['column'],
            'weather_point': f"{round(station['latitude'], 1):+06.1f}_{round(station['longitude'], 1):+07.1f}",
            'large_city': station.get('stratum') == 'large_city',
        })
    table = pd.DataFrame(rows)
    table['cell_station_count'] = table.groupby('cell_id')['station_id'].transform('count')
    distances = haversine_km(table['latitude'].values[:, None], table['longitude'].values[:, None],
                             table['latitude'].values[None, :], table['longitude'].values[None, :])
    np.fill_diagonal(distances, np.inf)
    table['nearest_station_km'] = distances.min(axis=1)
    del large
    return table, distances


def _eligible_city_counts(selection):
    return selection['stations']


def study_dates(protocol):
    first = date.fromisoformat(str(protocol['study_window']['first_date']))
    last = date.fromisoformat(str(protocol['study_window']['last_date']))
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
