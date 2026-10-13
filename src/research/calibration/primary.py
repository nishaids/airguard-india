"""Entry guard and model ladder for the genuine operational CAMS experiment.

This module never accepts the inherited short-lead archive. Target-specific
pollutant support is an evaluation annotation and cannot become a predictor.
Importing actual GRIB files and their dimensional/unit mapping must be verified
against the ADS response before constructing this table.
"""
import hashlib
import json
import math
import re
from datetime import datetime, timezone, timedelta
from numbers import Real
from pathlib import Path
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from src.research.calibration.availability import Cutoffs, LeakageError, guard_snapshot
from src.research.calibration.checkpoint import CAMS_ARCHIVE_STATUS
from src.research.calibration.checkpoint import canonical_hash
from src import config

ARCHIVE_SOURCE = 'COPERNICUS_ADS_OPERATIONAL_FORECAST'
ARCHIVE_DATASET = 'cams-global-atmospheric-composition-forecasts'
UNIT_AUDIT_VERSION = 'cams-operational-unit-audit-v1'


class ArchiveBlocked(RuntimeError):
    pass


def _timestamp(value, name, *, serialized=False):
    if serialized and isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError as error:
            raise LeakageError(f'{name} is not a valid timestamp') from error
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LeakageError(f'{name} requires an aware timestamp')
    return value.astimezone(timezone.utc)


def _checked_file(record, version):
    if not isinstance(record, dict) or not isinstance(record.get('file'), str):
        raise ArchiveBlocked('An operational file record is required')
    relative = Path(record['file'])
    root = (config.PROJECT_ROOT / 'data/research').resolve()
    path = (config.PROJECT_ROOT / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root) or version not in path.relative_to(root).parts[:-1]:
        raise ArchiveBlocked('Operational evidence must use a versioned data/research path')
    expected = record.get('sha256')
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ArchiveBlocked('Operational evidence requires a SHA256 digest')
    if not path.is_file():
        raise ArchiveBlocked('Operational evidence file is missing or its checksum differs')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ArchiveBlocked('Operational evidence file is missing or its checksum differs')
    return path


def _lead_hours(value):
    if not isinstance(value, list) or not value:
        raise ArchiveBlocked('Operational forecast lead metadata is required')
    result = []
    for lead in value:
        if isinstance(lead, bool) or not isinstance(lead, (str, Real)):
            raise ArchiveBlocked('Invalid operational forecast lead')
        try:
            number = float(lead)
        except ValueError as error:
            raise ArchiveBlocked('Invalid operational forecast lead') from error
        if not math.isfinite(number) or number < 0 or not number.is_integer():
            raise ArchiveBlocked('Operational forecast leads must be nonnegative integer hours')
        result.append(int(number))
    if len(set(result)) != len(result):
        raise ArchiveBlocked('Duplicate operational forecast leads')
    return result


def _single_request_value(value):
    return value[0] if isinstance(value, list) and len(value) == 1 else value


def require_operational_archive(manifest):
    """Validate per-run archive evidence; no GRIB decoding/conversion occurs here.

    A future importer must preserve actual ADS requests and decoded metadata.
    The unit-audit JSON binds verified conversion descriptions to exact raw-file
    hashes. A boolean or a file name alone can never release this blocker.
    """
    if not isinstance(manifest, dict) or manifest.get('source') != ARCHIVE_SOURCE:
        raise ArchiveBlocked(CAMS_ARCHIVE_STATUS)
    if manifest.get('dataset') != ARCHIVE_DATASET:
        raise ArchiveBlocked('A genuine CAMS global operational forecast archive is required')
    if manifest.get('source_type') != 'forecast':
        raise LeakageError('CAMS reanalysis/analysis is not an operational forecast')
    if manifest.get('issue_time_valid') is not True or manifest.get('units_verified') is not True:
        raise ArchiveBlocked('Explicit verified issue-time and unit evidence is required')
    version = manifest.get('archive_version')
    if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', version):
        raise ArchiveBlocked('An immutable operational archive version is required')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ArchiveBlocked('Downloaded operational files are required')
    file_hashes, variables = {}, {}
    for record in files.values():
        _checked_file(record, version)
        if record.get('source_type') != 'forecast' or record.get('dataset') != ARCHIVE_DATASET:
            raise LeakageError('Operational file provenance is not the required forecast dataset')
        name = record['file']
        if name in file_hashes:
            raise ArchiveBlocked('Duplicate operational file records')
        request = record.get('request')
        if not isinstance(request, dict) or request.get('dataset') != ARCHIVE_DATASET or request.get('type') != 'forecast':
            raise ArchiveBlocked('The exact ADS dataset/request provenance is required')
        if record.get('request_sha256') != canonical_hash(request):
            raise ArchiveBlocked('Operational request provenance checksum differs')
        initialized = _timestamp(record.get('run_initialized_utc'), 'run_initialized_utc', serialized=True)
        available = _timestamp(record.get('available_at_utc'), 'available_at_utc', serialized=True)
        if initialized > available:
            raise LeakageError('Operational forecast availability precedes initialization')
        if initialized.second or initialized.microsecond or \
           _single_request_value(request.get('date')) != initialized.date().isoformat() or \
           _single_request_value(request.get('time')) != initialized.strftime('%H:%M'):
            raise ArchiveBlocked('ADS request and operational initialization differ')
        leads = _lead_hours(record.get('lead_hours'))
        if set(leads) != set(_lead_hours(request.get('leadtime_hour'))):
            raise ArchiveBlocked('ADS request and decoded forecast leads differ')
        valid_times = record.get('valid_times_utc')
        if not isinstance(valid_times, list) or len(valid_times) != len(leads):
            raise ArchiveBlocked('Decoded operational forecast valid times are required')
        if any(_timestamp(valid, 'valid_times_utc', serialized=True) != initialized + timedelta(hours=lead)
               for lead, valid in zip(leads, valid_times)):
            raise LeakageError('Operational valid times do not equal initialization plus lead')
        requested = request.get('variable')
        if not isinstance(requested, list) or not requested or any(not isinstance(v, str) or not v for v in requested):
            raise ArchiveBlocked('Requested operational variables are required')
        if len(set(requested)) != len(requested) or record.get('variables') != requested:
            raise ArchiveBlocked('ADS request and decoded variable identities differ')
        file_hashes[name], variables[name] = record['sha256'], set(requested)
    audit_path = _checked_file(manifest.get('unit_audit'), version)
    try:
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
    except (UnicodeError, ValueError) as error:
        raise ArchiveBlocked('Unit audit is not valid JSON evidence') from error
    if not isinstance(audit, dict) or audit.get('unit_audit_version') != UNIT_AUDIT_VERSION or \
       audit.get('source') != ARCHIVE_SOURCE or audit.get('dataset') != ARCHIVE_DATASET or \
       audit.get('archive_version') != version or audit.get('units_verified') is not True or \
       audit.get('metadata_source') != 'decoded_operational_files' or audit.get('file_sha256') != file_hashes:
        raise ArchiveBlocked('Unit audit is not bound to the exact operational files')
    _timestamp(audit.get('audited_at_utc'), 'unit audit time', serialized=True)
    decoder = audit.get('decoder')
    if not isinstance(decoder, dict) or not all(isinstance(decoder.get(k), str) and decoder[k] for k in ('name', 'version')):
        raise ArchiveBlocked('The unit-audit metadata decoder identity is required')
    conversions = audit.get('conversions')
    if not isinstance(conversions, dict) or set(conversions) != set(file_hashes):
        raise ArchiveBlocked('Unit audit does not cover every operational file')
    for name, expected_variables in variables.items():
        inspected = conversions[name]
        if not isinstance(inspected, dict) or set(inspected) != expected_variables:
            raise ArchiveBlocked('Unit audit does not cover every decoded variable')
        for conversion in inspected.values():
            if not isinstance(conversion, dict) or conversion.get('verified') is not True or not all(
                    isinstance(conversion.get(k), str) and conversion[k].strip()
                    for k in ('source_units', 'target_units', 'conversion_description')):
                raise ArchiveBlocked('Verified decoded units and conversion evidence are required')
    return True


def guard_primary_row(row, features):
    if row.get('cams_issue_time_valid') is not True:
        raise LeakageError('CAMS issue-time validity requires explicit verified evidence')
    guard_snapshot(row,require_issue_time_valid_cams=True)
    if row.get('cams_source') != ARCHIVE_SOURCE:
        raise LeakageError('CAMS source is not the genuine operational archive')
    cut=Cutoffs.for_target(row['target_date'])
    initialized = _timestamp(row.get('cams_run_initialized_utc'), 'cams_run_initialized_utc')
    available = _timestamp(row.get('cams_available_at_utc'), 'cams_available_at_utc')
    if not initialized <= available <= cut.issue:
        raise LeakageError('CAMS timestamps must obey initialized <= available <= issue')
    frozen = row.get('cams_aqi_frozen')
    if isinstance(frozen, bool) or not isinstance(frozen, Real) or not math.isfinite(frozen) or frozen < 0:
        raise LeakageError('Frozen CAMS AQI must be a finite nonnegative numeric scalar')
    for name in features:
        if not isinstance(name, str):
            raise LeakageError('Primary predictor names must be strings')
        if name.startswith(('y_','target_', 'cams_matched')) or name in ('censored','quality_flags','y_support', 'matched_support_equals_frozen_support'):
            raise LeakageError('Outcome-dependent pollutant support/target metadata cannot be a predictor')
        value = row.get(name)
        if value is None or (isinstance(value, Real) and math.isnan(value)):
            continue  # missing predictors contribute no observed future input
        daily_history = name.startswith(('history_lag', 'history_roll7')) or name in ('bias_lag2', 'bias_roll7')
        if daily_history:
            if row.get('latest_daily_lag_date') is None:
                raise LeakageError('Daily history requires date provenance')
        if not daily_history and name.startswith(('obs', 'measured_', 'history_', 'bias_')):
            end = _timestamp(row.get('latest_measured_bin_end_utc'), 'latest_measured_bin_end_utc')
            if end > cut.measurement:
                raise LeakageError('Measured history ends after its declared cutoff')
        if name.startswith(('nbr', 'region_obs')):
            if name in ('nbr50_count', 'nbr150_count') and value == 0:
                continue  # no measured value was consumed for an empty donor set
            end = _timestamp(row.get('latest_neighbour_bin_end_utc'), 'latest_neighbour_bin_end_utc')
            if end > cut.measurement:
                raise LeakageError('Neighbour history ends after its declared cutoff')
        if name.startswith(('wx_', 'weather_')):
            run = _timestamp(row.get('weather_latest_run_bound_utc'), 'weather_latest_run_bound_utc')
            if run > cut.issue or row.get('weather_source_type') != 'forecast':
                raise LeakageError('Weather inputs require pre-issue forecast-run provenance')
        if name.startswith('fire_'):
            acquired = _timestamp(row.get('latest_fire_acquired_utc'), 'latest_fire_acquired_utc')
            published = _timestamp(row.get('latest_fire_published_utc'), 'latest_fire_published_utc')
            if acquired > cut.fire or not acquired <= published <= cut.issue:
                raise LeakageError('Fire inputs require acquisition cutoff and pre-issue publication')


def learner(family,params=None):
    params=params or {}
    if family=='ridge':
        model=make_pipeline(StandardScaler(),Ridge(alpha=params.get('alpha',10.)))
    elif family=='lightgbm':
        from lightgbm import LGBMRegressor
        model=LGBMRegressor(n_estimators=params.get('n_estimators',600),learning_rate=.05,
            num_leaves=params.get('num_leaves',31),min_child_samples=params.get('min_child_samples',60),
            subsample=.8,colsample_bytree=.8,random_state=42,n_jobs=2,verbosity=-1)
    elif family=='xgboost':
        from xgboost import XGBRegressor
        model=XGBRegressor(n_estimators=params.get('n_estimators',600),learning_rate=.05,
            max_depth=params.get('max_depth',4),min_child_weight=params.get('min_child_weight',5),
            subsample=.8,colsample_bytree=.8,random_state=42,n_jobs=2)
    else:
        raise ValueError(f'Unknown learner: {family}')
    return make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),model)


def predict(train,test,columns,family='ridge',residual=True,params=None):
    """Exact labels only; selected settings must originate in an inner train fold."""
    for frame in (train,test):
        for row in frame.to_dict('records'):
            guard_primary_row(row,columns)
    exact=train[~train.censored & train.target_valid & train.cams_aqi_frozen.notna()]
    if exact.empty:
        raise ValueError('No exact operational training pairs')
    if test.cams_aqi_frozen.isna().any():
        raise ValueError('All compared methods require the identical frozen CAMS baseline rows')
    model=learner(family,params)
    response=exact.y_aqi-exact.cams_aqi_frozen if residual else exact.y_aqi
    model.fit(exact[columns],response)
    corrected=model.predict(test[columns])+(test.cams_aqi_frozen.to_numpy() if residual else 0)
    return np.maximum(0,corrected)
