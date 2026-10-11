import copy
import gzip
import json
from datetime import datetime, timedelta, timezone

import pytest

from src import config
from src.research.calibration import data, repair_archive as repair
from src.research.calibration.openaq_archive import PAGE, write_rows


START = datetime(2025, 5, 1, tzinfo=timezone.utc)


@pytest.fixture
def inherited(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(data, 'ROOT', tmp_path / 'data/research')
    path = tmp_path / 'data/research/openaq_hours/17/pm25_123.csv.gz'
    rows = [(START.isoformat(), (START + timedelta(hours=1)).isoformat(), 10, 'ug/m3', 100, 0)]
    file_hash, content_hash = write_rows(path, rows)
    sensor = {'sensor_id': 123, 'parameter': 'pm25', 'pollutant': 'PM2.5', 'units': 'ug/m3',
              'first_utc': START.isoformat(), 'last_utc': (START + timedelta(hours=1000)).isoformat(),
              'file': config.portable(path), 'rows': 1, 'sha256': file_hash,
              'content_sha256': content_hash, 'first_row': rows[0][0], 'last_row': rows[-1][0],
              'requests': [{'from': START.isoformat(), 'to': (START + timedelta(hours=1000)).isoformat(),
                            'returned': PAGE, 'warning': 'page_limit_reached'},
                           {'from': (START + timedelta(hours=1000)).isoformat(),
                            'to': (START + timedelta(hours=1100)).isoformat(), 'returned': 1}]}
    source = tmp_path / 'results/research/data_manifests/openaq_hours_manifest.json'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({'stations': {'17': {'complete': True, 'sensors': {'PM2.5': sensor}}}}))
    output = source.with_name('openaq_repairs.json')
    return path, source, output, sensor


def result(hour, value=20):
    begin = START + timedelta(hours=hour)
    return {'value': value, 'parameter': {'name': 'pm25', 'units': 'ug/m3'},
            'period': {'datetimeFrom': {'utc': begin.isoformat()},
                       'datetimeTo': {'utc': (begin + timedelta(hours=1)).isoformat()}},
            'coverage': {'percentCoverage': 100}, 'flagInfo': {'hasFlags': False}}


def payload(page, rows):
    return {'meta': {'page': page, 'limit': PAGE, 'found': len(rows)}, 'results': rows}


class MockClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, path, params):
        self.calls.append((path, copy.deepcopy(params)))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def execute(inherited, client, **kwargs):
    _, source, output, _ = inherited
    return repair.run(source_paths=[source], repairs_path=output, client=client, **kwargs)


def test_repair_adds_only_extra_pages_and_preserves_original_files(inherited):
    old, source, output, sensor = inherited
    original = old.read_bytes(), source.read_bytes()
    client = MockClient([payload(2, [result(0, 10.0), result(1)])])
    manifest = execute(inherited, client)
    entry = manifest['stations']['17']['PM2.5']
    assert entry['status'] == 'repaired' and entry['added_rows'] == 1
    assert entry['base_sha256'] == sensor['sha256'] and entry['old_path'] == sensor['file']
    replacement = config.PROJECT_ROOT / entry['replacement']['file']
    assert replacement != old and '.repair-v1-' in replacement.name
    assert entry['replacement']['rows'] == 2
    assert b',20,ug/m3,100,0' in gzip.decompress(replacement.read_bytes())
    assert (old.read_bytes(), source.read_bytes()) == original
    assert client.calls == [('/sensors/123/hours', {
        'datetime_from': sensor['requests'][0]['from'], 'datetime_to': sensor['requests'][0]['to'],
        'limit': PAGE, 'page': 2})]
    complete_bytes = output.read_bytes(), replacement.read_bytes()
    assert execute(inherited, client) == manifest
    assert len(client.calls) == 1
    assert (output.read_bytes(), replacement.read_bytes()) == complete_bytes


def test_full_page_without_extra_rows_is_checked_once_and_has_no_replacement(inherited):
    old, source, _, _ = inherited
    before = old.read_bytes(), source.read_bytes()
    client = MockClient([payload(2, [])])
    manifest = execute(inherited, client)
    entry = manifest['stations']['17']['PM2.5']
    assert entry['status'] == 'no_missing_rows' and 'replacement' not in entry
    assert execute(inherited, client) == manifest and len(client.calls) == 1
    assert len(list(old.parent.glob('*.csv.gz'))) == 1
    assert (old.read_bytes(), source.read_bytes()) == before


def test_bad_base_checksum_fails_before_network_and_is_explicit(inherited):
    old, _, _, _ = inherited
    old.write_bytes(old.read_bytes() + b'tampered')
    client = MockClient([])
    manifest = execute(inherited, client)
    entry = manifest['stations']['17']['PM2.5']
    assert entry['status'] == 'failed' and entry['last_failed_check'] == 'base_checksum_validation'
    assert not client.calls and not entry['windows'] and 'replacement' not in entry


def test_failure_resumes_at_next_page_without_redownloading_completed_page(inherited):
    # Repeated identical results exercise the full-page pagination checkpoint.
    client = MockClient([payload(2, [result(1)] * PAGE), TimeoutError('secret URL omitted')])
    manifest = execute(inherited, client)
    entry = manifest['stations']['17']['PM2.5']
    assert entry['status'] == 'failed'
    assert [call[1]['page'] for call in client.calls] == [2, 3]
    assert 'secret URL' not in json.dumps(manifest)
    resume = MockClient([payload(3, [result(2)])])
    final = execute(inherited, resume)['stations']['17']['PM2.5']
    assert [call[1]['page'] for call in resume.calls] == [3]
    assert final['status'] == 'repaired' and final['added_rows'] == 2
    assert final['replacement']['rows'] == 3 and len(final['failures']) == 1


@pytest.mark.parametrize('response', [
    {'results': []},
    payload(1, []),
    payload(2, [{'value': 1}]),
    payload(2, [{**result(1), 'parameter': {'name': 'pm10', 'units': 'ug/m3'}}]),
])
def test_invalid_response_metadata_never_marks_no_missing_rows(inherited, response):
    client = MockClient([response])
    entry = execute(inherited, client)['stations']['17']['PM2.5']
    assert entry['status'] == 'failed' and 'replacement' not in entry
    assert entry['repair_request_log'][0]['status'] == 'failed'


def test_conflicting_duplicate_preserves_base_and_successful_page_checkpoint(inherited):
    old, source, _, _ = inherited
    before = old.read_bytes(), source.read_bytes()
    client = MockClient([payload(2, [result(0, 999)])])
    entry = execute(inherited, client)['stations']['17']['PM2.5']
    assert entry['status'] == 'failed' and 'replacement' not in entry
    assert (old.read_bytes(), source.read_bytes()) == before
    execute(inherited, client)
    assert len(client.calls) == 1


def test_unflagged_sensor_is_never_requested(inherited):
    _, source, _, _ = inherited
    manifest = json.loads(source.read_text())
    manifest['stations']['17']['sensors']['PM2.5']['requests'][0].pop('warning')
    source.write_text(json.dumps(manifest))
    client = MockClient([])
    assert execute(inherited, client)['stations'] == {}
    assert not client.calls


def test_complete_sensor_of_unfinished_station_is_repaired(inherited):
    _, source, _, _ = inherited
    manifest = json.loads(source.read_text())
    manifest['stations']['17']['complete'] = False
    source.write_text(json.dumps(manifest))
    entry = execute(inherited, MockClient([payload(2, [result(1)])]))['stations']['17']['PM2.5']
    assert entry['status'] == 'repaired'


def test_completed_override_metadata_is_immutable(inherited):
    _, _, output, _ = inherited
    client = MockClient([payload(2, [])])
    execute(inherited, client)
    manifest = json.loads(output.read_text())
    manifest['stations']['17']['PM2.5']['added_rows'] = 999
    output.write_text(json.dumps(manifest))
    before = output.read_bytes()
    with pytest.raises(ValueError, match='override metadata checksum'):
        execute(inherited, client)
    assert output.read_bytes() == before and len(client.calls) == 1


def test_page_saved_before_manifest_checkpoint_is_recovered_without_request(inherited):
    # Simulate interruption after storing page 2, before its manifest checkpoint.
    client = MockClient([payload(2, [result(1)] * PAGE), TimeoutError()])
    execute(inherited, client)
    _, _, output, _ = inherited
    manifest = json.loads(output.read_text())
    entry = manifest['stations']['17']['PM2.5']
    window = next(iter(entry['windows'].values()))
    window['pages'].pop('2')
    entry['repair_request_log'] = [r for r in entry['repair_request_log'] if r['params']['page'] != 2]
    output.write_text(json.dumps(manifest))
    resume = MockClient([payload(3, [])])
    final = execute(inherited, resume)['stations']['17']['PM2.5']
    assert final['status'] == 'repaired'
    assert [call[1]['page'] for call in resume.calls] == [3]
    assert any(r['status'] == 'recovered_checkpoint' for r in final['repair_request_log'])


def test_page_checkpoint_tamper_fails_without_another_request(inherited):
    client = MockClient([payload(2, [result(1)] * PAGE), TimeoutError()])
    first = execute(inherited, client)
    window = next(iter(first['stations']['17']['PM2.5']['windows'].values()))
    page_path = config.PROJECT_ROOT / window['pages']['2']['file']
    stored = json.loads(page_path.read_text())
    stored['payload']['results'][0]['value'] = 999
    page_path.write_text(json.dumps(stored))
    no_calls = MockClient([])
    failed = execute(inherited, no_calls)['stations']['17']['PM2.5']
    assert failed['status'] == 'failed' and failed['last_failed_check'] == 'page_checkpoint_validation'
    assert not no_calls.calls and 'replacement' not in failed
