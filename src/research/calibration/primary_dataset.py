"""Join verified CAMS forecasts to existing development targets, never rebuild targets.

This partial alignment artifact is not permission to fit models or open final
labels. Target support is an evaluation annotation, never a predictor. The
frozen three-species CAMS forecast exists independently of observed missingness.
"""
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from src import config
from src.research.calibration import cams_acquisition as archive
from src.research.calibration.availability import Cutoffs
from src.research.calibration.checkpoint import canonical_hash, write_json
from src.research.calibration.primary import ARCHIVE_SOURCE, guard_primary_row
from src.research.calibration.protocol import load
from src.research.calibration.splits import calendar, rolling_folds
from src.research.calibration.validation import normalized_text_sha256
from src.research.calibration import operational_features, primary

ROOT = config.PROJECT_ROOT
FEATURE_VERSION = 'operational-cams-station-alignment-v2'
FIXED_SUPPORT = frozenset(('PM2.5', 'PM10', 'O3'))


def final_start(protocol):
    return calendar(protocol)[-int(protocol['splits']['final_test_days'])]


def read_development(path, protocol):
    """Push the sealed-date exclusion into the Arrow scanner, before materialisation."""
    dataset = ds.dataset(path, format='parquet')
    return dataset.to_table(filter=ds.field('target_date') < final_start(protocol)).to_pandas()


def predictors(frame):
    allowed = ('cams_conc_', 'cams_sub_', 'cams_hourly_', 'obs24_conc_', 'obs_pm25_', 'wx_', 'history_', 'bias_', 'nbr', 'region_obs')
    names = [n for n in frame if n.startswith(allowed) and n != 'wx_hours']
    names += [n for n in ('cams_aqi_frozen', 'cams_six', 'obs24_aqi', 'latitude', 'longitude',
                         'cell_row', 'cell_column', 'cell_station_count', 'nearest_station_km',
                         'doy_sin', 'doy_cos', 'month', 'dow', 'weekend', 'season_index',
                         'elevation', 'cams_previous_day', 'cams_day_change') if n in frame]
    return names


def align(measured, forecasts, protocol, *, enrich=False):
    boundary = final_start(protocol)
    for table in (measured, forecasts):
        if table.empty or (pd.to_datetime(table.target_date).dt.date >= boundary).any():
            raise ValueError('Only nonempty development data may enter CAMS alignment')
        if table.duplicated(['station_id', 'target_date']).any():
            raise ValueError('Duplicate station-day input')
    frame = measured.merge(forecasts, on=['station_id', 'target_date'], how='inner',
                           validate='one_to_one', suffixes=('', '_forecast'))
    if frame.empty:
        raise ValueError('No observed development rows overlap verified forecasts')
    for coordinate in ('latitude', 'longitude'):
        if not np.isclose(frame[coordinate], frame[coordinate+'_forecast'], atol=1e-6).all():
            raise ValueError('Forecast and measured station coordinates differ')
    frame['cams_aqi_frozen'] = frame.cams_aqi_static_three
    frame['cams_source'] = ARCHIVE_SOURCE
    frame['cams_run_initialized_utc'] = pd.to_datetime(frame.reference_time_utc, utc=True)
    frame['cams_available_at_utc'] = frame.cams_run_initialized_utc + timedelta(hours=10)
    frame['cams_issue_time_valid'] = True
    frame['weather_source_type'] = 'forecast'
    frame['feature_version'] = FEATURE_VERSION
    # Nominal documented dissemination is an explicit historical assumption,
    # not a fabricated per-run delivery log or the later ADS retrieval time.
    frame['cams_publication_time_empirically_verified'] = False
    frame['cams_availability_assumption'] = 'nominal_00UTC_run_dissemination_by_10UTC'
    matched, support_equivalent = [], []
    for row in frame.to_dict('records'):
        support = row['y_support'].split('+') if isinstance(row['y_support'], str) and row['y_support'] else row['y_support']
        support = support or []
        values = [row.get('cams_sub_'+p) for p in support]
        values = [float(v) for v in values if v is not None and pd.notna(v)]
        matched.append(max(values) if row['target_valid'] and len(values) == len(support) and values else np.nan)
        support_equivalent.append(bool(row['target_valid'] and frozenset(support) == FIXED_SUPPORT))
        if pd.Timestamp(row['issue_time_utc']) != pd.Timestamp(Cutoffs.for_target(row['target_date']).issue):
            raise ValueError('Forecast issue timestamp differs from locked 20:00 IST clock')
    frame['cams_matched_evaluation_only'] = matched
    frame['matched_support_equals_frozen_support'] = support_equivalent
    if enrich:
        frame = pd.concat([frame, operational_features.history_features(frame, measured, forecasts),
                           operational_features.neighbour_features(frame, measured)], axis=1)
        elevation_path = ROOT/'data/research/catalogue/elevation.json'
        elevations = json.loads(elevation_path.read_text(encoding='utf-8')) if elevation_path.exists() else {}
        frame['elevation'] = frame.station_id.astype(str).map(elevations)
    columns = predictors(frame)
    for row in frame.to_dict('records'):
        checked = {k: None if pd.isna(v) else v for k, v in row.items()}
        guard_primary_row(checked, columns)
    return frame.sort_values(['station_id', 'target_date']).reset_index(drop=True), columns


def build():
    protocol = load()
    baseline = json.loads((ROOT/'results/research/cams_raw_baseline_derivation.json').read_text(encoding='utf-8'))
    measured = json.loads((ROOT/'results/research/measured_dataset.json').read_text(encoding='utf-8'))
    if archive.sha(ROOT/baseline['table']) != baseline['sha256']:
        raise ValueError('Derived CAMS checksum differs')
    # Outcomes are materialised only after the sealed-date scanner filter.
    observations = read_development(ROOT/measured['table'], protocol)
    forecasts = pd.read_parquet(ROOT/baseline['table'])
    frame, columns = align(observations, forecasts, protocol, enrich=True)
    identity = canonical_hash({'feature_version': FEATURE_VERSION, 'protocol': protocol['_sha256'],
                               'measured_semantic_hash': measured['dataset_hash'],
                               'measured_file_hash': archive.sha(ROOT/measured['table']),
                               'cams_table_hash': baseline['sha256'],
                               'code_hash': normalized_text_sha256(Path(__file__)),
                               'features_code_hash': normalized_text_sha256(Path(operational_features.__file__)),
                               'primary_guard_code_hash': normalized_text_sha256(Path(primary.__file__)),
                               'elevation_cache_hash': archive.sha(ROOT/'data/research/catalogue/elevation.json')})
    folder = ROOT/'data/research/cams_operational/aligned'/identity
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/'development_alignment.parquet'
    manifest = folder/'manifest.json'
    if manifest.exists():
        prior = json.loads(manifest.read_text(encoding='utf-8'))
        if not path.exists() or archive.sha(path) != prior['sha256']:
            raise ValueError('Immutable alignment checksum differs')
    if not path.exists():
        frame.to_parquet(path, index=False)
    folds = []
    for fold in rolling_folds(calendar(protocol), protocol):
        if fold['role'] == 'final_test':
            continue
        training = frame[frame.target_date.isin(fold['train']) & frame.target_valid]
        counts = training.groupby('station_id').size()
        eligible = counts[counts >= protocol['stations']['minimum_valid_target_days']]
        folds.append({'name': fold['name'], 'eligible_training_stations': len(eligible),
                      'archive_dates_in_test_window': int(frame[frame.target_date.isin(fold['test'])].target_date.nunique())})
    valid = frame[frame.target_valid]
    report = {'status': 'PARTIAL_GUARDED_DEVELOPMENT_ALIGNMENT', 'dataset_identity': identity,
              'table': path.relative_to(ROOT).as_posix(), 'sha256': archive.sha(path),
              'protocol_sha256': protocol['_sha256'], 'protocol_version': protocol['protocol_version'],
              'feature_version': FEATURE_VERSION, 'measured_dataset_hash': measured['dataset_hash'],
              'raw_cams_table_sha256': baseline['sha256'], 'rows': len(frame),
              'stations': int(frame.station_id.nunique()), 'cities': int(frame.city.nunique()),
              'dates': int(frame.target_date.nunique()), 'valid_targets': len(valid),
              'rejected_targets_retained': int((~frame.target_valid).sum()),
              'censored_severe_retained': int((frame.target_valid & frame.censored).sum()),
              'valid_target_support_mismatches': int((~valid.matched_support_equals_frozen_support).sum()),
              'target_support_is_evaluation_annotation_only': True, 'predictors': columns,
              'guarded_rows': len(frame), 'final_test_accessed': False,
              'reader_filter': 'target_date < '+str(final_start(protocol)),
              'per_run_publication_empirically_verified': False,
              'availability_limitation': 'Documented nominal dissemination; historical delivery logs unknown. Measured history assumes a healthy feed with 3h latency.',
              'complete_primary_feature_dataset': False, 'model_fitting_performed': False,
              'remaining_features': ['cutoff-aligned CAMS bias_now descriptor', 'spatial-regime donor masking in primary runner', 'fire historical publication evidence'],
              'history_policy': 'D-2/D-3/D-7 date-keyed exact history; censored lag indicator retained; no exact bias on censored targets',
              'elevation_missing_rows': int(frame.elevation.isna().sum()),
              'fold_coverage': folds}
    if not manifest.exists():
        write_json(manifest, report)
    write_json(ROOT/'results/research/cams_development_alignment.json', report)
    return report


if __name__ == '__main__':
    value = build()
    print(json.dumps({k: value[k] for k in ('status', 'rows', 'valid_targets', 'dates', 'guarded_rows', 'final_test_accessed')}))
