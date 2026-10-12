"""Incremental non-CAMS measured targets, including every rejected station-day.

The locked v3.1 file is read, never rewritten. Raw rejected bins stay in their
immutable caches; the rejection ledger identifies their file and row number.
Historical publication time for OpenAQ/FIRMS is unknown. Measured-history
features are therefore conditional sensitivity inputs, not proven availability.
"""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from src import config
from src.nationwide import aqi
from src.nationwide.aqi import normalize
from src.research.calibration import data, availability
from src.research.calibration.availability import Cutoffs, guard_snapshot, LeakageError
from src.research.calibration.checkpoint import capture, canonical_hash, write_json, OUT
from src.research.calibration.dataset import SEASONS, SEASON_INDEX, GROUPS
from src.research.calibration.protocol import load

FEATURE_VERSION = 'non-cams-preliminary-v1'
BUILDER_VERSION = 'measured-v3.1-causal-qc-v1'
STRICT_FEATURES = GROUPS['C'] + GROUPS['D'] + ['latitude', 'longitude']
CONDITIONAL_FEATURES = ['obs24_aqi', 'obs_pm25_last6_mean', 'obs_pm25_last6_slope']


def builder_code_hash():
    """Include transitive scientific dependencies; normalize checkout newlines."""
    paths = [Path(__file__), Path(data.__file__), Path(aqi.__file__), Path(availability.__file__)]
    return canonical_hash([(config.portable(p), hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest())
                           for p in paths])


def causal_rejection_times(bins):
    """The earliest bin END at which a six-hour stuck run can be detected."""
    result, run = {}, []
    previous_time, previous_value = None, None
    def finish():
        if len(run) >= data.STUCK_RUN:
            known = run[data.STUCK_RUN - 1] + data.HOUR
            result.update({t: max(known, t + data.HOUR) for t in run})
    for t in sorted(bins):
        if previous_time is None or t - previous_time != data.HOUR or bins[t] != previous_value:
            finish()
            run = []
        run.append(t)
        previous_time, previous_value = t, bins[t]
    finish()
    return result


def qc_station(entry):
    rows, before_stuck, rejection_times = {}, {}, {}
    audit, ledger, day_counts = {}, [], defaultdict(Counter)
    for pollutant, sensor in entry.get('sensors', {}).items():
        if not sensor.get('file'):
            continue
        kept, rejected = data.read_sensor(sensor['file'], pollutant)
        candidates, _ = data.read_sensor(sensor['file'], pollutant, apply_stuck=False)
        rejection_times[pollutant] = causal_rejection_times(candidates)
        audit[pollutant] = {'raw': sensor.get('rows', 0), 'kept': len(kept), 'rejected': dict(rejected)}
        for t, value in kept.items():
            rows.setdefault(t, {})[pollutant] = value
        for t, value in candidates.items():
            before_stuck.setdefault(t, {})[pollutant] = value
        values = np.asarray(list(kept.values()))
        q1, q3 = np.quantile(values, [.25, .75]) if len(values) else (0, 0)
        with gzip.open(config.PROJECT_ROOT / sensor['file'], 'rt', encoding='utf-8', newline='') as handle:
            for number, raw in enumerate(csv.DictReader(handle), 2):
                t, value, reason = data.validate_hourly_row(raw, pollutant)
                flag = None
                if reason is None and t not in kept:
                    reason = 'stuck_sensor_run'
                if reason is None and q3 > q1 and value > q3 + 3 * (q3 - q1):
                    flag = 'potential_spike_kept'
                if reason or flag:
                    ledger.append({'file': sensor['file'], 'csv_row': number, 'pollutant': pollutant,
                                   'valid_from_utc': raw.get('valid_from_utc'), 'reason': reason, 'flag': flag})
                    if t is not None:
                        day_counts[t.astimezone(data.IST).date()][reason or flag] += 1
    for t, pollutants in rows.items():
        if pollutants.get('PM2.5', -1) > pollutants.get('PM10', float('inf')):
            day_counts[t.astimezone(data.IST).date()]['pm25_above_pm10_kept'] += 1
    return rows, before_stuck, rejection_times, audit, ledger, day_counts


def station_frames(key, entry, dates):
    rows, candidates, reject_at, audit, ledger, day_counts = qc_station(entry)
    series = data.HourlySeries(rows)
    causal = data.HourlySeries(candidates)
    records = []
    for day in dates:
        cut = Cutoffs.for_target(day)
        result = data.daily_index(series, cut.target_start, cut.target_end)
        target_reasons = []
        if result.get('status') == 'INSUFFICIENT_DATA':
            pollutants = result.get('pollutants', {})
            supported = [p for p in data.POLLUTANTS if (pollutants.get(p) or {}).get('concentration') is not None]
            if len(supported) < 3:
                target_reasons.append('fewer_than_three_supported_pollutants')
            if not set(supported) & {'PM2.5', 'PM10'}:
                target_reasons.append('no_supported_particulate')
            for p in data.POLLUTANTS:
                info = pollutants.get(p, {})
                if info.get('valid_hours', 0) < 16:
                    target_reasons.append(f'{p}:fewer_than_16_hours')
                elif p in ('CO', 'O3') and info.get('concentration') is None:
                    target_reasons.append(f'{p}:no_complete_8h_window')
        # Prefix QC: later identical readings must not revise an earlier feature.
        history = causal.between(cut.measurement - timedelta(hours=32), cut.measurement)
        visible = {}
        for row in history:
            t = row['time']
            if t + data.HOUR > cut.measurement:
                continue
            allowed = {p: value for p, value in row.items() if p != 'time'
                       and reject_at.get(p, {}).get(t, datetime.max.replace(tzinfo=timezone.utc)) > cut.measurement}
            if allowed:
                visible[t] = allowed
        past = data.HourlySeries(visible)
        seen = data.daily_index(past, cut.measurement - timedelta(hours=24), cut.measurement)
        latest = max(visible, default=None)
        source_times = series.between(cut.target_start, cut.target_end)
        record = {'station_id': int(key), 'target_date': day, **data.engine_fields(result, 'y_'),
                  **data.engine_fields(seen, 'obs24_'), **data._short_window(past, cut),
                  'censored': result.get('status') == 'LOWER_BOUND',
                  'target_valid': result.get('status') in ('VALID', 'LOWER_BOUND'),
                  'target_rejection_reasons': json.dumps(target_reasons),
                  'quality_flags': json.dumps(dict(day_counts[day]), sort_keys=True),
                  'source_first_bin_utc': min((r['time'] for r in source_times), default=None),
                  'source_last_bin_end_utc': max((r['time'] + data.HOUR for r in source_times), default=None),
                  'source_retrieved_at': entry.get('retrieved_at'),
                  'source_retrieval_time_basis': 'station acquisition start; per-bin original publication time unavailable',
                  'source_sensor_ids': json.dumps({p: s.get('sensor_id') for p, s in entry.get('sensors', {}).items()}, sort_keys=True),
                  'source_cache_files': json.dumps({p: s.get('file') for p, s in entry.get('sensors', {}).items()}, sort_keys=True),
                  'latest_measured_bin_end_utc': latest + data.HOUR if latest else None,
                  'measured_publication_time_known': False,
                  'issue_utc': cut.issue, 'measurement_cutoff_utc': cut.measurement}
        record['y_support'] = data.support_tag([p for p in data.POLLUTANTS if record.get(f'y_conc_{p}') is not None])
        guard_snapshot(record)
        records.append(record)
    return pd.DataFrame(records), audit, ledger


def strict_guard(row, feature_names):
    """A strict experiment admits only documented forecast/calendar/static inputs."""
    if any(name not in STRICT_FEATURES for name in feature_names):
        raise LeakageError('Unproven publication time or CAMS proxy in strict non-CAMS features')
    guard_snapshot(row)
    if any(name.startswith('wx_') and pd.notna(row.get(name)) for name in feature_names):
        bound = row.get('weather_latest_run_bound_utc')
        if bound is None or pd.isna(bound):
            raise LeakageError('Weather values require an archived-run bound')


def build(snapshot_path=None):
    protocol = load()
    snapshot, recovery = capture(snapshot_path) if snapshot_path is not None else capture()
    dates = data.study_dates(protocol)
    destination = data.DERIVED / snapshot['data_version']
    cache = data.DERIVED / 'station_targets'
    cache.mkdir(parents=True, exist_ok=True)
    frames, audits = [], {}
    code_hash = builder_code_hash()
    destination = destination / code_hash
    destination.mkdir(parents=True, exist_ok=True)
    for key, entry in sorted(snapshot['stations'].items(), key=lambda kv: int(kv[0])):
        version = canonical_hash([key, [(p, s.get('sha256')) for p, s in sorted(entry['sensors'].items())],
                                  protocol['_sha256'], BUILDER_VERSION, code_hash])
        folder = cache / version
        if not (folder / 'targets.parquet').exists():
            frame, audit, ledger = station_frames(key, entry, dates)
            folder.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(ledger).to_parquet(folder / 'hourly_rejections.parquet', index=False)
            write_json(folder / 'audit.json', audit)
            frame.to_parquet(folder / 'targets.parquet', index=False)
            print(f'QC station {key}: {int(frame.target_valid.sum())}/{len(frame)} valid targets', flush=True)
        frames.append(pd.read_parquet(folder / 'targets.parquet'))
        audits[key] = {'cache': config.portable(folder), **json.loads((folder / 'audit.json').read_text())}
    if not frames:
        raise ValueError('No fully downloaded stations yet')
    table = pd.concat(frames, ignore_index=True)
    stations, _ = data.station_table(snapshot['selection'])
    table = table.merge(stations, on='station_id', validate='many_to_one')
    weather = data.weather_frame(snapshot['manifests'].get('weather', {'lead': 'previous_day2', 'files': {}}))
    weather_manifest = snapshot['manifests'].get('weather', {})
    if weather_manifest and (weather_manifest.get('lead') != 'previous_day2'
                             or weather_manifest.get('source') != 'OPEN_METEO_PREVIOUS_RUNS'
                             or weather_manifest.get('model') != 'gfs_seamless'):
        raise LeakageError('Unexpected weather archive/lead; cannot establish issue-time bound')
    if not weather.empty:
        table = table.merge(weather, on=['weather_point', 'target_date'], how='left', validate='many_to_one')
    for column in GROUPS['C']:
        if column not in table:
            table[column] = np.nan
    when = pd.to_datetime(table.target_date)
    table['doy_sin'] = np.sin(2 * np.pi * when.dt.dayofyear / 365.25)
    table['doy_cos'] = np.cos(2 * np.pi * when.dt.dayofyear / 365.25)
    table['month'], table['dow'] = when.dt.month, when.dt.dayofweek
    table['weekend'] = (table.dow >= 5).astype(float)
    table['season'] = table.month.map(SEASONS)
    table['season_index'] = table.season.map(SEASON_INDEX)
    table['weather_latest_run_bound_utc'] = table.target_date.map(lambda day: Cutoffs.for_target(day).weather_latest_run)
    table['feature_version'] = FEATURE_VERSION
    table['protocol_version'] = protocol['protocol_version']
    table['protocol_sha256'] = protocol['_sha256']
    table['data_version'] = snapshot['data_version']
    table['CAMS_ARCHIVE_STATUS'] = recovery['CAMS_ARCHIVE_STATUS']
    table = table.sort_values(['target_date', 'station_id']).reset_index(drop=True)
    for row in table.to_dict('records'):
        # Strict audit deliberately excludes the conditional history timestamps.
        strict_guard({k: v for k, v in row.items() if k != 'latest_measured_bin_end_utc'}, STRICT_FEATURES)
        guard_snapshot({k: (None if pd.isna(v) else v) for k, v in row.items()})
    valid = table[table.target_valid]
    counts = valid.groupby('station_id').size()
    eligible = counts[counts >= int(protocol['stations']['minimum_valid_target_days'])].index
    reasons = Counter()
    target_reasons = Counter()
    flag_counts = Counter()
    for value in table.target_rejection_reasons:
        target_reasons.update(json.loads(value))
    for value in table.quality_flags:
        flag_counts.update(json.loads(value))
    for audit in audits.values():
        for pollutant in data.POLLUTANTS:
            reasons.update(audit.get(pollutant, {}).get('rejected', {}))
    # Semantic identity is independent of parquet encoding and generation time.
    dataset_hash = hashlib.sha256(table.to_json(orient='records', date_format='iso').encode()).hexdigest()
    path = destination / 'non_cams_table.parquet'
    table.to_parquet(path, index=False)
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'status': 'PARTIAL_COLLECTION' if recovery['openaq_complete'] < recovery['openaq_selected'] else 'COLLECTION_COMPLETE',
              'dataset_hash': dataset_hash, 'data_version': snapshot['data_version'], 'code_sha256': code_hash,
              'feature_version': FEATURE_VERSION, 'protocol_version': protocol['protocol_version'],
              'protocol_sha256': protocol['_sha256'], 'table': config.portable(path),
              'catalogue_universe': snapshot['selection'].get('universe'), 'selected_stations': len(stations),
              'metadata_revision': snapshot['selection'].get('metadata_revision'),
              'cohort_basis': snapshot.get('cohort_basis','All completed stations in this acquisition snapshot'),
              'inherited_snapshot_data_version': snapshot.get('inherited_snapshot_data_version'),
              'raw_stations': len(snapshot['stations']), 'eligible_stations_full_window_descriptive_only': len(eligible),
              'usable_stations': valid.station_id.nunique(), 'usable_cities': valid.city.nunique(),
              'station_days': len(table), 'valid_targets': len(valid), 'rejected_targets': len(table)-len(valid),
              'target_rejection_status_counts': table.loc[~table.target_valid, 'y_status'].value_counts().to_dict(),
              'target_rejection_reason_counts': dict(target_reasons),
              'hourly_flags_kept': {k: v for k, v in flag_counts.items() if k.endswith('_kept')},
              'hourly_exclusion_reason_counts': dict(reasons), 'severe_days': int(valid.censored.sum()),
              'category_counts': valid.y_category.value_counts().sort_index().to_dict(),
              'pollutant_target_coverage': {p: int(valid[f'y_conc_{p}'].notna().sum()) for p in data.POLLUTANTS},
              'date_count': valid.target_date.nunique(), 'date_coverage': [str(valid.target_date.min()), str(valid.target_date.max())],
              'strict_snapshot_rows_passed': len(table), 'strict_features': STRICT_FEATURES,
              'conditional_features': CONDITIONAL_FEATURES, 'conditional_assumption': 'OpenAQ healthy-feed latency <= 3 hours; historical publication time is NOT observed',
              'fire_features': 'WITHHELD: acquisition time alone does not prove publication time',
              'station_eligibility': 'Full-window counts are descriptive; experiments choose stations from training dates only',
              'spike_diagnostic': 'Flag above station/pollutant Q3 + 3 IQR; retained, never an exclusion',
              'raw_rejections_retained': True, 'station_audits': audits,
              'provenance': 'OpenAQ CPCB provider; AirGuard CPCB-style targets, not official bulletin AQI',
              'CAMS_ARCHIVE_STATUS': recovery['CAMS_ARCHIVE_STATUS']}
    write_json(destination / 'quality_report.json', report)
    write_json(OUT / 'measured_dataset.json', report)
    return table, report


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,help='Earlier immutable inputs.json; unresolved pagination is refused')
    _, report = build(parser.parse_args().snapshot)
    print(json.dumps({k: report[k] for k in ('status', 'usable_stations', 'usable_cities', 'station_days', 'valid_targets', 'rejected_targets', 'severe_days', 'dataset_hash')}, indent=2))
