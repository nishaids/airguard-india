import hashlib
import json
from src.research.calibration import readiness as r


def test_probe_and_collection_cannot_release_primary_readiness(tmp_path,monkeypatch):
    monkeypatch.setattr(r.config,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(r,'OUT',tmp_path/'results/research')
    r.OUT.mkdir(parents=True)
    assert r.current_archive_status()=='PENDING_MANUAL_ADS_CREDENTIAL'
    raw=tmp_path/'data/research/test/sample.grib';raw.parent.mkdir(parents=True);raw.write_bytes(b'TEST_FIXTURE_ONLY')
    from tests.test_calibration_ads_probe import forecast_metadata
    probe={'status':'VERIFIED_OPERATIONAL_FORECAST','file':raw.relative_to(tmp_path).as_posix(),
           'sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'decoded_fields':[forecast_metadata()]}
    (r.OUT/'cams_ads_probe.json').write_text(json.dumps(probe))
    assert r.current_archive_status()=='ADS_SMOKE_VERIFIED_ARCHIVE_INCOMPLETE'
    (r.OUT/'cams_development_acquisition.json').write_text(json.dumps({'jobs':{'existing-id':{'status':'running'}},'complete':False}))
    assert r.current_archive_status()=='ADS_OPERATIONAL_ARCHIVE_ACQUIRING'
    raw.write_bytes(b'corrupt')
    assert r.current_archive_status()=='ADS_PROBE_EVIDENCE_INVALID'
