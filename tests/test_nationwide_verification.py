"""Verification accepts station evidence only after the target day."""
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch
from src.nationwide import aqi, jobs, service
from tests.test_nationwide import NOW, FakeStore, hourly


class Cursor:
    def __init__(self,run):self.run=run;self.rowcount=1;self.inserts=[]
    def execute(self,sql,params=None):
        if sql.startswith("insert into airguard.forecast_verifications"):
            self.inserts.append(params)
    def fetchall(self):return [self.run]


def test_verification_uses_same_day_station_series_and_signed_error():
    start,end=aqi.tomorrow_period(NOW-timedelta(days=3))
    issued=start-timedelta(hours=12)
    run={"id":7,"latitude":13.,"longitude":80.,"issued_at":issued,"target_start":start,"target_end":end,"predicted_aqi":120,"artifact":{"forecast":{"category":{"index":2}}}}
    cursor=Cursor(run)
    class Store(FakeStore):
        @contextmanager
        def cursor(self):yield cursor
    class Provider:
        def measured(self,lat,lon,window_start,window_end):
            assert window_start==start-timedelta(hours=7) and window_end==end
            return {"stations":[{"station_pk":9,"rows":hourly(window_start,31)}]}
    s=service.Service(Store(),Provider())
    with patch("src.nationwide.service.utcnow",return_value=NOW):result=jobs.verify(s)
    assert result[0]["status"]=="VERIFIED" and result[0]["pairs"]==1
    assert cursor.inserts[0][0]==7 and cursor.inserts[0][1]==9
    assert cursor.inserts[0][6]==120-cursor.inserts[0][2]
    assert cursor.inserts[0][7]==12


def test_partial_station_never_produces_verification_metric():
    start,end=aqi.tomorrow_period(NOW-timedelta(days=3))
    run={"id":8,"latitude":13.,"longitude":80.,"issued_at":start-timedelta(hours=4),"target_start":start,"target_end":end,"predicted_aqi":120,"artifact":{"forecast":{"category":{"index":2}}}}
    cursor=Cursor(run)
    class Store(FakeStore):
        @contextmanager
        def cursor(self):yield cursor
    class Provider:
        def measured(self,*args):return {"stations":[{"station_pk":9,"rows":hourly(start,15)}]}
    with patch("src.nationwide.service.utcnow",return_value=NOW):result=jobs.verify(service.Service(Store(),Provider()))
    assert result[0]["status"]=="INSUFFICIENT_MEASURED_DATA"
    assert not cursor.inserts
