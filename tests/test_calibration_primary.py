"""Synthetic, offline fixtures for the blocked genuine-archive entry guards.

No fixture is operational CAMS data and no GRIB decoder is implemented here.
"""
import copy
import hashlib
import json
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from src.research.calibration import primary
from src.research.calibration.availability import Cutoffs, LeakageError
from src.research.calibration.checkpoint import canonical_hash


def file_record(path, root):
    return {'file': path.relative_to(root).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def archive(tmp_path, monkeypatch):
    monkeypatch.setattr(primary.config, 'PROJECT_ROOT', tmp_path)
    directory = tmp_path / 'data/research/cams_operational/test-only-v1'
    directory.mkdir(parents=True)
    raw = directory / 'synthetic.bin'
    raw.write_bytes(b'TEST FIXTURE ONLY; not an operational CAMS file')
    initialized = datetime(2025, 5, 31, tzinfo=timezone.utc)
    request = {'dataset': primary.ARCHIVE_DATASET, 'type': 'forecast',
               'date': '2025-05-31', 'time': '00:00',
               'leadtime_hour': ['24'], 'variable': ['particulate_matter_2.5um']}
    record = {**file_record(raw, tmp_path), 'source_type': 'forecast',
              'dataset': primary.ARCHIVE_DATASET, 'request': request,
              'request_sha256': canonical_hash(request),
              'run_initialized_utc': initialized.isoformat(),
              'available_at_utc': (initialized + timedelta(hours=8)).isoformat(),
              'lead_hours': [24], 'valid_times_utc': [(initialized + timedelta(hours=24)).isoformat()],
              'variables': request['variable']}
    audit = {'unit_audit_version': primary.UNIT_AUDIT_VERSION,
             'source': primary.ARCHIVE_SOURCE, 'dataset': primary.ARCHIVE_DATASET,
             'archive_version': 'test-only-v1', 'units_verified': True,
             'metadata_source': 'decoded_operational_files',
             'audited_at_utc': '2026-10-12T00:00:00+00:00',
             'decoder': {'name': 'synthetic-test-fixture', 'version': '1'},
             'file_sha256': {record['file']: record['sha256']},
             'conversions': {record['file']: {'particulate_matter_2.5um': {
                 'source_units': 'kg/m3', 'target_units': 'ug/m3',
                 'conversion_description': 'Test-only conversion metadata; multiply by 1e9',
                 'verified': True}}}}
    audit_path = directory / 'units.json'
    audit_path.write_text(json.dumps(audit), encoding='utf-8')
    manifest = {'source': primary.ARCHIVE_SOURCE, 'dataset': primary.ARCHIVE_DATASET,
                'source_type': 'forecast', 'issue_time_valid': True, 'units_verified': True,
                'archive_version': 'test-only-v1', 'files': {'run': record},
                'unit_audit': file_record(audit_path, tmp_path)}
    return manifest, audit, raw, audit_path, tmp_path


def rewrite_audit(archive, change):
    manifest, audit, _, path, root = archive
    change(audit)
    path.write_text(json.dumps(audit), encoding='utf-8')
    manifest['unit_audit'] = file_record(path, root)


def test_complete_synthetic_evidence_contract_passes(archive):
    assert primary.require_operational_archive(archive[0]) is True


@pytest.mark.parametrize('field', ['issue_time_valid', 'units_verified'])
@pytest.mark.parametrize('value', [None, False, 1, 'true', 'false'])
def test_archive_flags_require_literal_true(archive, field, value):
    archive[0][field] = value
    with pytest.raises(primary.ArchiveBlocked):
        primary.require_operational_archive(archive[0])


def test_reanalysis_refused_before_missing_file_evidence():
    with pytest.raises(LeakageError):
        primary.require_operational_archive({'source': primary.ARCHIVE_SOURCE,
            'dataset': primary.ARCHIVE_DATASET, 'source_type': 'reanalysis'})


def test_empty_file_record_or_files_are_blocked(archive):
    manifest = archive[0]
    manifest['files'] = {'absent.grib': {}}
    with pytest.raises(primary.ArchiveBlocked):
        primary.require_operational_archive(manifest)
    manifest = copy.deepcopy(archive[0])
    manifest['files'] = {}
    with pytest.raises(primary.ArchiveBlocked):
        primary.require_operational_archive(manifest)


@pytest.mark.parametrize('field', ['unit_audit', 'archive_version'])
def test_missing_unit_audit_or_version_blocks_archive(archive, field):
    del archive[0][field]
    with pytest.raises(primary.ArchiveBlocked):
        primary.require_operational_archive(archive[0])


def test_missing_or_modified_raw_files_block_archive(archive):
    manifest, _, raw, _, _ = archive
    raw.write_bytes(b'Modified test fixture')
    with pytest.raises(primary.ArchiveBlocked, match='checksum'):
        primary.require_operational_archive(manifest)
    raw.unlink()
    with pytest.raises(primary.ArchiveBlocked, match='missing'):
        primary.require_operational_archive(manifest)


@pytest.mark.parametrize('unversioned', [False, True])
def test_raw_file_must_be_inside_versioned_research_directory(archive, unversioned):
    manifest, _, raw, _, root = archive
    location = root / ('data/research/unversioned.bin' if unversioned else 'outside-test-only-v1.bin')
    location.write_bytes(raw.read_bytes())
    manifest['files']['run'].update(file_record(location, root))
    with pytest.raises(primary.ArchiveBlocked, match='versioned'):
        primary.require_operational_archive(manifest)


def test_unit_audit_file_checksum_is_verified(archive):
    archive[3].write_text('{}', encoding='utf-8')
    with pytest.raises(primary.ArchiveBlocked, match='checksum'):
        primary.require_operational_archive(archive[0])


def test_checksummed_audit_still_requires_exact_raw_file_hash_binding(archive):
    rewrite_audit(archive, lambda audit: audit.update(file_sha256={'different.bin': 'a' * 64}))
    with pytest.raises(primary.ArchiveBlocked, match='exact operational files'):
        primary.require_operational_archive(archive[0])


@pytest.mark.parametrize('change', [
    lambda audit: audit.update(units_verified='true'),
    lambda audit: audit.update(metadata_source='uninspected_request'),
    lambda audit: audit.update(decoder={}),
    lambda audit: audit.update(conversions={}),
    lambda audit: audit['conversions'][next(iter(audit['conversions']))]['particulate_matter_2.5um'].update(verified='true'),
    lambda audit: audit['conversions'][next(iter(audit['conversions']))]['particulate_matter_2.5um'].update(source_units=''),
])
def test_unit_audit_requires_decoded_unit_details_and_full_coverage(archive, change):
    rewrite_audit(archive, change)
    with pytest.raises(primary.ArchiveBlocked):
        primary.require_operational_archive(archive[0])


def test_request_hash_and_run_lead_variable_binding(archive):
    record = archive[0]['files']['run']
    record['request']['date'] = '2025-06-01'
    with pytest.raises(primary.ArchiveBlocked, match='checksum'):
        primary.require_operational_archive(archive[0])
    record['request_sha256'] = canonical_hash(record['request'])
    with pytest.raises(primary.ArchiveBlocked, match='initialization'):
        primary.require_operational_archive(archive[0])


@pytest.mark.parametrize('field,value,error', [
    ('available_at_utc', '2025-05-30T23:00:00+00:00', LeakageError),
    ('run_initialized_utc', '2025-05-31T00:00:00', LeakageError),
    ('lead_hours', [True], primary.ArchiveBlocked),
    ('lead_hours', [-1], primary.ArchiveBlocked),
    ('lead_hours', [25], primary.ArchiveBlocked),
    ('valid_times_utc', ['2025-06-02T00:00:00+00:00'], LeakageError),
    ('variables', ['different_pollutant'], primary.ArchiveBlocked),
    ('source_type', 'analysis', LeakageError),
])
def test_archive_run_metadata_cannot_disagree_with_request(archive, field, value, error):
    archive[0]['files']['run'][field] = value
    with pytest.raises(error):
        primary.require_operational_archive(archive[0])


@pytest.fixture
def row():
    cut = Cutoffs.for_target(date(2025, 6, 1))
    return {'target_date': cut.target_date, 'cams_source': primary.ARCHIVE_SOURCE,
            'cams_issue_time_valid': True, 'cams_aqi_frozen': 100.,
            'cams_run_initialized_utc': cut.issue - timedelta(hours=14),
            'cams_available_at_utc': cut.issue - timedelta(hours=6)}


def test_valid_frozen_primary_row(row):
    primary.guard_primary_row(row, ['cams_aqi_frozen'])


@pytest.mark.parametrize('value', [None, np.nan, np.inf, -np.inf, -1., True, '100', [100]])
def test_frozen_cams_requires_finite_scalar(row, value):
    row['cams_aqi_frozen'] = value
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, ['cams_aqi_frozen'])


@pytest.mark.parametrize('value', [False, 'true', 1, np.bool_(True)])
def test_row_validity_requires_literal_true(row, value):
    row['cams_issue_time_valid'] = value
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [])


def test_cams_availability_cannot_precede_initialization_or_follow_issue(row):
    cut = Cutoffs.for_target(row['target_date'])
    row['cams_available_at_utc'] = row['cams_run_initialized_utc'] - timedelta(seconds=1)
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [])
    row['cams_available_at_utc'] = cut.issue + timedelta(seconds=1)
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [])


@pytest.mark.parametrize('feature', ['obs24_aqi', 'obs_pm25_last6_mean', 'history_mean', 'bias_now'])
def test_nonmissing_history_requires_pre_cutoff_bin_provenance(row, feature):
    row[feature] = 100.
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [feature])
    cut = Cutoffs.for_target(row['target_date'])
    row['latest_measured_bin_end_utc'] = cut.measurement
    primary.guard_primary_row(row, [feature])
    row['latest_measured_bin_end_utc'] += timedelta(seconds=1)
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [feature])


def test_missing_predictor_has_no_observed_future_input(row):
    row.update(obs24_aqi=np.nan, wx_temp_mean=None, fire_n50_24h=np.nan)
    primary.guard_primary_row(row, ['obs24_aqi', 'wx_temp_mean', 'fire_n50_24h'])


@pytest.mark.parametrize('feature', ['nbr50_obs24_mean', 'nbr50_count', 'region_obs24_mean'])
def test_neighbour_inputs_require_their_own_bin_provenance(row, feature):
    row[feature] = 1.
    row['latest_measured_bin_end_utc'] = Cutoffs.for_target(row['target_date']).measurement
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [feature])
    row['latest_neighbour_bin_end_utc'] = row['latest_measured_bin_end_utc']
    primary.guard_primary_row(row, [feature])


@pytest.mark.parametrize('feature', ['wx_temp_mean', 'weather_temperature'])
def test_weather_requires_pre_issue_forecast_provenance(row, feature):
    row[feature] = 28.
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [feature])
    cut = Cutoffs.for_target(row['target_date'])
    row.update(weather_latest_run_bound_utc=cut.issue, weather_source_type='forecast')
    primary.guard_primary_row(row, [feature])
    row['weather_source_type'] = 'reanalysis'
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [feature])
    row.update(weather_source_type='forecast', weather_latest_run_bound_utc=cut.issue + timedelta(seconds=1))
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [feature])


def test_fire_requires_acquisition_and_actual_publication_before_issue(row):
    cut = Cutoffs.for_target(row['target_date'])
    row['fire_n50_24h'] = 1.
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, ['fire_n50_24h'])
    row['latest_fire_acquired_utc'] = cut.fire
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, ['fire_n50_24h'])
    row['latest_fire_published_utc'] = cut.issue
    primary.guard_primary_row(row, ['fire_n50_24h'])
    for acquired, published in ((cut.fire, cut.issue + timedelta(seconds=1)),
                                (cut.fire + timedelta(seconds=1), cut.issue),
                                (cut.fire, cut.fire - timedelta(seconds=1))):
        row.update(latest_fire_acquired_utc=acquired, latest_fire_published_utc=published)
        with pytest.raises(LeakageError):
            primary.guard_primary_row(row, ['fire_n50_24h'])


@pytest.mark.parametrize('feature', ['y_aqi', 'y_support', 'target_valid', 'cams_matched', 'quality_flags'])
def test_outcome_dependent_predictors_remain_forbidden(row, feature):
    with pytest.raises(LeakageError):
        primary.guard_primary_row(row, [feature])
