"""Offline regression tests: no credentials, network or measured labels."""
import json
import logging
import sys
from types import SimpleNamespace

import pytest

from src.research.calibration import ads_probe as probe


def test_container_accepts_complete_tiny_grib1_and_multiple_messages(tmp_path):
    message=b'GRIB'+(12).to_bytes(3,'big')+b'\x01'+b'7777'
    path=tmp_path/'tiny.grib';path.write_bytes(message)
    assert probe.validate_grib_container(path)=={
        'bytes':12,'messages':1,'editions':[1],'complete_message_framing':True}
    path.write_bytes(message*2)
    assert probe.validate_grib_container(path)['messages']==2


@pytest.mark.parametrize('artifact', [b'',b'<html>error</html>',b'<?xml error>',
    b'GRIB\x00\x00\x86\x01'+b'7777',  # declared length 134, actually truncated
    b'GRIB\x00\x00\x0c\x01'+b'0000',  # bad terminator
    b'GRIB\x00\x00\x0c\x01'+b'7777'+b'junk',
    b'GRIB\x00\x00\x00\x02',            # incomplete GRIB2 header
    b'GRIB\x00\x00\x0c\x03'+b'7777'])
def test_container_rejects_text_truncation_and_trailing_bytes(tmp_path,artifact):
    path=tmp_path/'bad.grib';path.write_bytes(artifact)
    with pytest.raises(ValueError):probe.validate_grib_container(path)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, 'ROOT', tmp_path)
    monkeypatch.setattr(probe.importlib.metadata, 'version', lambda name: 'TEST')
    old = logging.root.manager.disable
    yield tmp_path
    logging.disable(old)


def test_failure_never_serializes_provider_message_or_resubmits(isolated, monkeypatch, capsys):
    calls = []
    secret = 'TEST_ONLY_NEVER_PERSIST_THIS_VALUE'
    class Client:
        def __init__(self, **kwargs):
            print(secret)
        def retrieve(self, *args):
            calls.append(args)
            error = RuntimeError('license error ' + secret)
            error.response = SimpleNamespace(status_code=403)
            raise error
    monkeypatch.setitem(sys.modules, 'cdsapi', SimpleNamespace(Client=Client))
    assert probe.run() == 1
    assert probe.run() == 1
    assert len(calls) == 1
    assert secret not in capsys.readouterr().out
    for path in isolated.rglob('*.json'):
        assert secret not in path.read_text()
    evidence = json.loads((isolated / 'results/research/cams_ads_probe.json').read_text())
    assert evidence['error'] == {'category': 'ACCESS_OR_TERMS_REJECTED', 'http_status': 403, 'terms_mentioned': True}
    assert not evidence['full_acquisition_authorized_by_probe']


def test_download_requires_decoder_and_reuse_checks_checksum(isolated, monkeypatch):
    calls = []
    class Remote:
        request_id = 'fake-request-id'
        def download(self, target):
            probe.Path(target).write_bytes(b'not-real-GRIB')
    class Client:
        def __init__(self, **kwargs):
            pass
        def retrieve(self, *args):
            calls.append(args)
            return Remote()
    monkeypatch.setitem(sys.modules, 'cdsapi', SimpleNamespace(Client=Client))
    assert probe.run() == 0
    evidence = json.loads((isolated / 'results/research/cams_ads_probe.json').read_text())
    assert not evidence['full_acquisition_authorized_by_probe']
    assert probe.run() == 0
    assert len(calls) == 1
    (isolated / evidence['file']).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='checksum'):
        probe.run()
    assert len(calls) == 1


def test_resume_uses_remote_id_without_submit(isolated, monkeypatch):
    folder = isolated / 'data/research/cams_operational/smoke-v1' / probe.request_hash()
    probe.write(folder / 'retrieval.json', {'status': 'SUBMITTED',
                'request_sha256': probe.request_hash(), 'request_id': 'existing-id'})
    calls = []
    class Remote:
        def download(self, target):
            probe.Path(target).write_bytes(b'fixture')
    class Client:
        def __init__(self, **kwargs):
            self.client = self
        def get_remote(self, request_id):
            calls.append(request_id)
            return Remote()
        def retrieve(self, *args):
            pytest.fail('An existing job must not be resubmitted')
    monkeypatch.setitem(sys.modules, 'cdsapi', SimpleNamespace(Client=Client))
    assert probe.run() == 0
    assert calls == ['existing-id']


def test_probe_is_before_locked_test_and_forecast_only():
    assert probe.REQUEST['date'] < '2026-07-10'
    assert probe.REQUEST['type'] == ['forecast']
    assert len(probe.REQUEST['variable']) == len(probe.REQUEST['leadtime_hour']) == 1


def test_status_poll_persists_only_allowlisted_metadata(isolated, monkeypatch, capsys):
    probe.write(isolated / 'results/research/cams_ads_probe.json',
                {'status': 'SUBMITTED', 'request_id': 'existing-id'})
    class Client:
        def __init__(self, **kwargs):
            self.client = self
        def get_remote(self, request_id):
            assert request_id == 'existing-id'
            print('TEST_PROVIDER_RESPONSE_MUST_NOT_BE_PERSISTED')
            return SimpleNamespace(status='accepted', headers={'authorization': 'TEST_SECRET'})
    monkeypatch.setitem(sys.modules, 'cdsapi', SimpleNamespace(Client=Client))
    assert probe.status() == 0
    record = json.loads((isolated / 'results/research/cams_ads_probe_status.json').read_text())
    assert set(record) == {'local_status', 'remote_status', 'checked_at_utc'}
    assert record['remote_status'] == 'accepted'
    assert 'TEST_' not in capsys.readouterr().out


def forecast_metadata():
    return {'dataDate': 20250218, 'dataTime': 0, 'step': 24, 'stepUnits': 1,
            'validityDate': 20250219, 'validityTime': 0, 'dataType': 'fc',
            'paramId': 210073, 'units': 'kg m**-3'}


def test_forecast_reference_lead_and_valid_time_agree():
    reference, valid = probe.verify_fields([forecast_metadata()])
    assert reference.isoformat() == '2025-02-18T00:00:00+00:00'
    assert (valid-reference).total_seconds() == 86400


@pytest.mark.parametrize('key,value', [('dataType', 'an'), ('dataDate', 20250219),
    ('dataTime', 1200), ('step', 0), ('step', 24.5), ('stepUnits', 0), ('validityTime', 100),
    ('validityDate', 20250220), ('paramId', 210074), ('units', 'kg kg**-1')])
def test_forecast_metadata_mismatch_rejected(key, value):
    field = forecast_metadata()
    field[key] = value
    with pytest.raises(ValueError, match='expected operational forecast'):
        probe.verify_fields([field])


@pytest.mark.parametrize('count', [0, 2])
def test_missing_or_extra_fields_rejected(count):
    with pytest.raises(ValueError, match='exactly one'):
        probe.verify_fields([forecast_metadata()] * count)
