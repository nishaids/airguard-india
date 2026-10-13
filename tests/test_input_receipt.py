"""Receipt-time evidence must not alter raw payloads or invent a model run."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.nationwide import providers
from src.nationwide.store import digest


def test_provider_receipt_preserves_raw_json_and_excludes_request_credentials(monkeypatch):
    body={'results':[{'id':1}]}
    start=datetime(2026,10,13,8,tzinfo=timezone.utc)
    clock=iter([start,start+timedelta(seconds=2)])
    monkeypatch.setattr(providers,'utcnow',lambda:next(clock))
    response=SimpleNamespace(json=lambda:body,headers={'Date':'Tue, 13 Oct 2026 08:00:01 GMT'})
    client=SimpleNamespace(get=lambda *args,**kwargs:response)
    store=SimpleNamespace(event=lambda *args,**kwargs:None)
    result=providers.Providers(store,client)._get_json('openaq','https://api.openaq.org/v3/locations',headers={'X-API-Key':'TEST_ONLY_SECRET'})
    assert result==body and digest(result)==digest(body)
    assert json.loads(json.dumps(result))==body
    assert result.receipt['request_started_at']==start.isoformat()
    assert result.receipt['response_received_at']==(start+timedelta(seconds=2)).isoformat()
    assert result.receipt['provider_http_date']==(start+timedelta(seconds=1)).isoformat()
    assert result.receipt['provider_http_date_is_forecast_initialization'] is False
    assert 'TEST_ONLY_SECRET' not in json.dumps(result.receipt)


def test_forecast_availability_uses_response_receipt_without_inventing_initialization():
    received='2026-10-13T08:00:02+00:00'
    raw={'latitude':13.2,'longitude':80.0,'hourly':{'time':[1791882000],'pm2_5':[20.0]},'hourly_units':{'pm2_5':'μg/m³'}}
    receipt={'source':'open_meteo','request_started_at':'2026-10-13T08:00:00+00:00','response_received_at':received,'provider_http_date':None,'provider_http_date_is_forecast_initialization':False}
    records=[]
    store=SimpleNamespace(records=lambda rows:records.extend(rows))
    value=providers.Providers(store,SimpleNamespace()).parse_series(providers.ReceivedPayload(raw,receipt),13.2,80.0,{'pm2_5':'PM2.5'},'open_meteo','cams_global','modelled_forecast',providers.AIR_URL)
    assert value['fetched_at']==received and value['provider_issued_at'] is None
    assert value['raw_reference']==digest(raw) and value['input_receipt']==receipt
    assert records[0]['provenance']['input_receipt']==receipt
    assert records[0]['provider_issued_at'] is None
