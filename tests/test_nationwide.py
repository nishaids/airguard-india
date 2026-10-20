"""Scientific boundary, provider fault, API/cache and real rollback DB checks."""
import copy
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from src.nationwide import aqi, providers, service, api
from src.nationwide.store import Store, BudgetExceeded, digest
from src.ingestion.http import HttpClient, Response, HttpError
from src.ingestion.settings import Settings, load_env, secret
from src.ingestion.db import connect, migrate

NOW=datetime(2026,10,10,12,tzinfo=timezone.utc)


@pytest.mark.parametrize("pollutant,edges",list(aqi.BREAKPOINTS.items()))
@pytest.mark.parametrize("position",range(5))
@pytest.mark.parametrize("delta",[-.0001,0,.0001])
def test_all_closed_breakpoints(pollutant,edges,position,delta):
    concentration=edges[position]+delta
    result=aqi.subindex(pollutant,concentration,ozone_hourly=concentration if pollutant=="O3" else None)
    expected=(50,100,200,300,400)[position]
    assert result["value"]== (401 if position==4 and delta>0 else expected)
    assert result["qualifier"]==("LOWER_BOUND" if position==4 and delta>0 else "EXACT")


@pytest.mark.parametrize("value",[-1,None,float("nan"),float("inf"),"10",True])
def test_bad_concentration(value):
    assert aqi.subindex("PM2.5",value) is None


def test_official_interpolation_and_minimum():
    assert aqi.subindex("PM2.5",75)["value"]==150
    assert aqi.subindex("CO",6)["value"]==150
    assert aqi.calculate({"PM2.5":75,"NO2":80,"SO2":40})["dominant_pollutant"]=="PM2.5"
    assert aqi.calculate({"PM2.5":75,"PM10":100})["status"]=="INSUFFICIENT_DATA"
    assert aqi.calculate({"NO2":40,"SO2":40,"CO":1})["aqi"] is None
    assert aqi.subindex("O3",220) is None
    assert aqi.subindex("O3",100,ozone_hourly=220)["value"]>300


def test_units_no_assumed_gas_conversion():
    assert aqi.normalize("CO",1000,"µg/m³")==1
    assert aqi.normalize("PM2.5",.03,"mg/m3")==30
    assert aqi.normalize("NO2",20,"ppb") is None
    assert aqi.normalize("CO",2,"ppm") is None
    assert aqi.normalize("O3",1,"wrong") is None


def hourly(start,count=48):
    return [{"time":(start+timedelta(hours=i)).isoformat(),"PM2.5":40,"PM10":60,"NO2":20,"SO2":5,"CO":.2,"O3":45} for i in range(count)]


def test_averaging_minimum_unique_bins_and_gas_windows():
    rows=hourly(NOW-timedelta(hours=48))
    result=aqi.aggregate(rows,NOW-timedelta(hours=24),NOW,rolling=True)
    assert result["status"]=="VALID" and result["pollutants"]["CO"]["valid_hours"]==24
    assert aqi.aggregate(rows[-15:],NOW-timedelta(hours=24),NOW)["aqi"] is None
    partial=copy.deepcopy(rows)
    partial[-4].pop("CO");partial[-4].pop("O3")
    result=aqi.aggregate(partial,NOW-timedelta(hours=24),NOW,rolling=True)
    assert result["pollutants"]["CO"]["concentration"] is None
    assert result["aqi"] is not None  # four eligible non-gas pollutants remain
    duplicates=rows[-1:]*24
    assert aqi.aggregate(duplicates,NOW-timedelta(hours=24),NOW)["aqi"] is None
    fast=[dict(rows[0],time=(NOW-timedelta(hours=2)+timedelta(minutes=i*5)).isoformat()) for i in range(24)]
    assert aqi.aggregate(fast,NOW-timedelta(hours=24),NOW)["aqi"] is None


def test_ist_tomorrow_boundaries():
    start,end=aqi.tomorrow_period(NOW)
    assert start.isoformat()=="2026-10-10T18:30:00+00:00"
    assert end-start==timedelta(hours=24)


class FakeStore:
    def __init__(self):
        self.cache={};self.events=[];self.saved=[];self.issues=[];self.locations=[]
    def get(self,k):return self.cache.get(k)
    def claim(self,*args):return "lease"
    def release(self,*args):pass
    def put(self,key,provider,payload,ttl,token):self.cache[key]={"payload":payload,"fetched_at":NOW,"expires_at":NOW+timedelta(seconds=ttl)}
    def budget(self,*args):pass
    def event(self,*args,**kwargs):self.events.append((args,kwargs))
    def records(self,records):self.saved.extend(records)
    def weather(self,*args):pass
    def location(self,r):self.locations.append(r)
    def issue(self,*args):self.issues.append(args);return 42
    def metrics(self):return []
    def fire_context(self,*args):return []


def transport(response):
    return HttpClient(Settings(http_max_retries=0,http_timeout_seconds=1),transport=lambda *args:response,sleep=lambda _:None)


def test_each_provider_retry_consumes_shared_quota():
    budgets=[]
    store=FakeStore()
    store.budget=lambda *args:budgets.append(args)
    responses=iter([Response(500,{},"failure"),Response(200,{},'{"results":[]}')])
    client=HttpClient(Settings(http_max_retries=1),transport=lambda *args:next(responses),sleep=lambda _:None)
    providers.Providers(store,client).get_json("geocoding",providers.GEO_URL)
    assert client.requests_made==2
    assert sum(b[0]=="open-meteo-all-day" for b in budgets)==2


def test_generated_vercel_entrypoints_are_detectable_and_importable():
    import ast, runpy
    from pathlib import Path
    from http.server import BaseHTTPRequestHandler
    root=Path(__file__).resolve().parents[1]/"webapp/api"
    for route in ("health","locations/search","air-quality/current","air-quality/forecast","air-quality/summary","providers/status","internal/refresh"):
        path=root/(route+".py")
        tree=ast.parse(path.read_text())
        assert any(isinstance(n,ast.ClassDef) and n.name=="handler" and any(isinstance(b,ast.Name) and b.id=="BaseHTTPRequestHandler" for b in n.bases) for n in tree.body)
        assert issubclass(runpy.run_path(str(path))["handler"],BaseHTTPRequestHandler)


def test_provider_schema_wrong_unit_and_missing_series():
    store=FakeStore()
    p=providers.Providers(store)
    with pytest.raises(HttpError):p.parse_series({},13,80,providers.AIR_FIELDS,"open_meteo","cams_global","modelled_forecast",providers.AIR_URL)
    payload={"hourly":{"time":[NOW.timestamp()],**{p:[1] for p in providers.AIR_FIELDS}},"hourly_units":{p:"ug/m3" for p in providers.AIR_FIELDS}}
    payload["hourly_units"]["ozone"]="ppm"
    with pytest.raises(HttpError):p.parse_series(payload,13,80,providers.AIR_FIELDS,"open_meteo","cams_global","modelled_forecast",providers.AIR_URL)
    assert not store.saved


@pytest.mark.parametrize("status",[429,500,401])
def test_provider_http_errors(status):
    p=providers.Providers(FakeStore(),transport(Response(status,{},"failure")))
    with pytest.raises(HttpError) as exc:p.get_json("weather",providers.WEATHER_URL)
    assert exc.value.status==status


def test_malformed_json_and_timeout():
    p=providers.Providers(FakeStore(),transport(Response(200,{},"bad json")))
    with pytest.raises(HttpError):p.get_json("weather",providers.WEATHER_URL)
    def timeout(*args):raise TimeoutError("transport timeout")
    p=providers.Providers(FakeStore(),HttpClient(Settings(http_max_retries=0),transport=timeout))
    with pytest.raises(HttpError) as exc:p.get_json("weather",providers.WEATHER_URL)
    assert exc.value.kind=="timeout"


def test_empty_open_aq_no_manufactured_aqi():
    p=providers.Providers(FakeStore(),transport(Response(200,{},'{"results":[]}')))
    with patch("src.nationwide.providers.secret",return_value="test-server-only-key"),patch("src.nationwide.providers.utcnow",return_value=NOW):
        result=p.measured(13,80)
    assert result["stations"]==[]


def test_cache_expiry_and_stale_label_then_unavailable():
    store=FakeStore();s=service.Service(store,providers=None)
    store.cache["x"]={"payload":{"fetched_at":NOW.isoformat()},"fetched_at":NOW-timedelta(hours=2),"expires_at":NOW-timedelta(hours=1)}
    def fail():raise HttpError("upstream down")
    with patch("src.nationwide.service.utcnow",return_value=NOW):
        data,state=s.cached("x","air",fail,3600,stale_seconds=6*3600)
        assert data and state["status"]=="STALE"
        store.cache["x"]["fetched_at"]=NOW-timedelta(hours=8)
        data,state=s.cached("x","air",fail,3600,stale_seconds=6*3600)
        assert data is None and state["status"]=="FAILED"


class FakeProviders:
    def air(self,*args):
        start=NOW.astimezone(aqi.IST).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)-timedelta(days=2)
        return {"rows":hourly(start,120),"fetched_at":NOW.isoformat(),"issued_at":NOW.isoformat(),"model":"cams_global","grid":{},"raw_reference":"input-hash","raw":{}}
    def weather(self,*args):raise HttpError("weather down")
    def measured(self,*args):raise HttpError("openaq down")


def test_a_summary_built_during_another_refresh_is_kept_only_briefly():
    """Seen live on 2026-10-20: two overlapping refreshes, and the losing one cached 2-hour-old CAMS data for 10 minutes."""
    class BusyStore(FakeStore):
        def claim(self,key,*args):return None if key.startswith("cams:") else "lease"
    store=BusyStore()
    old=FakeProviders().air()
    old["fetched_at"]=(NOW-timedelta(hours=2)).isoformat()
    s=service.Service(store,FakeProviders())
    gx,gy=service.grid(13.11,80.11)
    store.cache[f"cams:{service.METHOD}:{gx},{gy}"]={"payload":old,"fetched_at":NOW-timedelta(hours=2),"expires_at":NOW-timedelta(hours=1)}
    with patch("src.nationwide.service.utcnow",return_value=NOW):
        result=s.summary(13.11,80.11,"Busy place")
    assert result["ok"] and result["provider_status"]["air"]["status"]=="STALE"
    summary=store.cache[service.Service.summary_key(13.11,80.11,NOW)]
    assert summary["expires_at"]-NOW<=timedelta(seconds=service.STALE_SUMMARY_SECONDS)
    # with every source fresh the usual lifetime applies
    fresh_store=FakeStore()
    with patch("src.nationwide.service.utcnow",return_value=NOW):
        service.Service(fresh_store,FakeProviders()).summary(13.11,80.11,"Quiet place")
    fresh=fresh_store.cache[service.Service.summary_key(13.11,80.11,NOW)]
    assert fresh["expires_at"]-NOW>timedelta(seconds=service.STALE_SUMMARY_SECONDS)


def test_openaq_weather_outage_preserves_forecast():
    s=service.Service(FakeStore(),FakeProviders())
    with patch("src.nationwide.service.utcnow",return_value=NOW):
        result=s.summary(13.11,80.11,"Arbitrary place")
    assert result["ok"] and result["current"]["measured_or_modelled"]=="MODELLED"
    assert result["tomorrow"]["aqi"] is not None
    assert result["provider_status"]["measured"]["status"]=="FAILED"
    assert result["tomorrow"]["forecast_run_id"]==42
    assert len([r for r in result["hourly_forecast"] if parse_day(r)=="2026-10-11"])==24


def parse_day(r):return aqi.parse_time(r["time"]).astimezone(aqi.IST).date().isoformat()


def test_all_outage_returns_no_fake_values():
    class Down(FakeProviders):
        def air(self,*args):raise HttpError("air down")
    with patch("src.nationwide.service.utcnow",return_value=NOW):result=service.Service(FakeStore(),Down()).summary(13.11,80.11)
    assert not result["ok"] and result["tomorrow"]["aqi"] is None and result["current"]["aqi"] is None


def test_incomplete_model_cannot_issue_a_forecast_or_claim_fresh_aqi():
    class Incomplete(FakeProviders):
        def air(self,*args):
            data=super().air(*args)
            data["rows"]=[{"time":r["time"],"PM2.5":r["PM2.5"]} for r in data["rows"]]
            return data
    store=FakeStore()
    with patch("src.nationwide.service.utcnow",return_value=NOW):result=service.Service(store,Incomplete()).summary(13.11,80.11)
    assert not result["ok"] and not store.issues
    assert result["tomorrow"]["status"]=="INSUFFICIENT_DATA"
    assert result["current"]["freshness"]==result["tomorrow"]["freshness"]=="UNAVAILABLE"


@pytest.mark.parametrize("query",[{},{"lat":"NaN","lon":"80"},{"lat":"91","lon":"80"},{"lat":"13","lon":"181"},{"lat":"13","lon":"80","url":"http://private"}])
def test_bad_api_input(query):
    assert api.dispatch("summary",query,service=service.Service(FakeStore(),FakeProviders()))[0]==400


def test_refresh_auth_required_and_no_secret_response():
    s=service.Service(FakeStore(),FakeProviders())
    with patch("src.nationwide.api.secret",return_value="hidden-test-token"):
        status,data=api.dispatch("refresh",{},authorization="Bearer wrong",service=s)
    assert status==401 and "hidden-test-token" not in json.dumps(data)


def test_search_validation_and_country_filter():
    store=FakeStore()
    p=providers.Providers(store,transport(Response(200,{},json.dumps({"results":[{"name":"Avadi","country_code":"IN","latitude":13.11,"longitude":80.11,"admin1":"Tamil Nadu","admin2":"Thiruvallur"},{"country_code":"US"}]}))))
    assert p.search("Avadi")["results"][0]["region"]=="Tamil Nadu"
    assert len(p.search("Avadi")["results"])==1
    with pytest.raises(ValueError):p.search("x")
    assert service.Service(store,p).search("13.1,80.2")["results"][0]["lat"]==13.1


def test_real_database_constraints_rollback_only():
    load_env()
    if not secret("DATABASE_URL"):pytest.skip("DATABASE_URL is not configured")
    connection=connect()
    from psycopg2.extras import RealDictCursor
    class RollbackStore(Store):
        @contextmanager
        def cursor(self):
            with connection.cursor(cursor_factory=RealDictCursor) as cur:yield cur
    try:
        store=RollbackStore()
        location={"key":"test-rollback-only","name":"Test fixture","lat":13.1,"lon":80.1}
        store.location(location)
        now=providers.utcnow();start,end=aqi.tomorrow_period(now)
        calc=aqi.aggregate(hourly(start-timedelta(days=1)),start,end)
        calc["issued_at"]=now.isoformat()
        run=store.issue(location,calc,{"forecast":calc},"test-input")
        original_issue=calc["issued_at"]
        # Move earlier so the duplicate probe stays before target_start near IST midnight.
        calc["issued_at"]=(now-timedelta(minutes=10)).isoformat()
        assert store.issue(location,calc,{"forecast":calc},"test-input")==run
        assert calc["issued_at"]==original_issue
        with connection.cursor() as cur:
            cur.execute("savepoint immutable_test")
            with pytest.raises(Exception):cur.execute("update airguard.forecast_runs set predicted_aqi=1 where id=%s",(run,))
            cur.execute("rollback to savepoint immutable_test")
            cur.execute("select issued_at<target_start from airguard.forecast_runs where id=%s",(run,))
            assert cur.fetchone()[0]
            cur.execute("select bool_and(relrowsecurity) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='airguard' and c.relkind='r'")
            assert cur.fetchone()[0]
    finally:
        connection.rollback();connection.close()
