import hashlib
import json
import pytest
from src.research.calibration import sensor_recovery, catalogue
from src.research.calibration.openaq_archive import choose_sensors
from datetime import datetime,timezone


def setup(tmp_path,monkeypatch):
    location={'id':42,'name':'Site, Noida - UPPCB','provider':{'name':'CPCB'},
        'coordinates':{'latitude':28.6,'longitude':77.3},'sensors':[{'id':1,'parameter':{'name':'pm25','units':'ug/m3'}},
        {'id':2,'parameter':{'name':'pm25','units':'ug/m3'}}]}
    path=tmp_path/'catalogue.json';path.write_text(json.dumps({'results':[location]}))
    monkeypatch.setattr(sensor_recovery.config,'PROJECT_ROOT',tmp_path)
    selection={'catalogue':{'path':'catalogue.json','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
    station={'location_id':42,'name':location['name'],'latitude':28.6,'longitude':77.3}
    class Client:
        calls=[]
        def get(self,endpoint,attempts):
            self.calls.append(endpoint); key=int(endpoint.rsplit('/',1)[-1])
            return {'results':[{'id':key,'parameter':{'name':'pm25','units':'ug/m3'},
                'datetimeFirst':{'utc':'2020-01-01T00:00:00Z'},
                'datetimeLast':{'utc':'2026-10-07T00:00:00Z' if key==1 else '2024-01-01T00:00:00Z'},
                'coverage':{'observedCount':100}}]}
    return Client(),station,selection,tmp_path/'cache'


def test_individual_metadata_is_cached_and_current_sensor_is_date_selected(tmp_path,monkeypatch):
    client,station,selection,cache=setup(tmp_path,monkeypatch)
    result=sensor_recovery.fetch(client,station,selection=selection,cache_dir=cache)
    sensor_recovery.fetch(client,station,selection=selection,cache_dir=cache)
    assert client.calls==['/sensors/1','/sensors/2']
    chosen,_=choose_sensors(result['results'],datetime(2025,1,1,tzinfo=timezone.utc),datetime(2026,10,8,tzinfo=timezone.utc))
    assert chosen['PM2.5']['sensor_id']==1
    assert result['_provenance']['catalogue_sha256']==selection['catalogue']['sha256']


def test_individual_metadata_cache_tampering_is_refused(tmp_path,monkeypatch):
    client,station,selection,cache=setup(tmp_path,monkeypatch)
    sensor_recovery.fetch(client,station,selection=selection,cache_dir=cache)
    p=cache/'1.json'; r=json.loads(p.read_text());r['payload']['results'][0]['id']=99;p.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='checksum'):
        sensor_recovery.fetch(client,station,selection=selection,cache_dir=cache)


def test_recovery_refuses_catalogue_or_station_identity_change(tmp_path,monkeypatch):
    client,station,selection,cache=setup(tmp_path,monkeypatch)
    station['name']='Wrong station'
    with pytest.raises(ValueError,match='identity'):
        sensor_recovery.fetch(client,station,selection=selection,cache_dir=cache)
    assert client.calls==[]
