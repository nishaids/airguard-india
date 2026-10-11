"""Verify real records, repeated cache hits, cron authorization and provenance."""
import json
from pathlib import Path
import requests
from src.ingestion.settings import load_env, secret, redact
from src.nationwide.store import Store

load_env();store=Store()
def counts():
    with store.cursor() as cur:
        names=("environmental_records","forecast_runs","weather_forecasts","sensors","locations","forecast_verifications")
        out={}
        for name in names:
            cur.execute("select count(*) as count from airguard."+name)
            out[name]=cur.fetchone()["count"]
        return out
before=counts()
url="http://127.0.0.1:8787/api/air-quality/summary"
params={"lat":13.1147,"lon":80.10981,"name":"Avadi, Thiruvallur District, Tamil Nadu, India","region":"Tamil Nadu"}
first=requests.get(url,params=params,timeout=60);first.raise_for_status()
second=requests.get(url,params=params,timeout=60);second.raise_for_status()
assert first.json()["tomorrow"]["forecast_run_id"]==second.json()["tomorrow"]["forecast_run_id"]
assert before==counts(),"Cache hit must not append repeated records"
with store.cursor() as cur:
    cur.execute("select source_type,count(*) as count from airguard.environmental_records group by 1")
    sources=[dict(r) for r in cur.fetchall()]
    cur.execute("select count(*) as n from airguard.environmental_records where provenance='{}'::jsonb or fetched_at is null or methodology_version is null or raw_unit is null")
    missing=cur.fetchone()["n"]
    cur.execute("select count(*) as n from airguard.forecast_runs where issued_at>=target_start")
    late=cur.fetchone()["n"]
    cur.execute("select jobname,schedule,active from cron.job where jobname='airguard-nationwide-refresh'")
    cron=dict(cur.fetchone())
    cur.execute("select count(*) as n from airguard.environmental_records where record_key in (select record_key from airguard.environmental_records group by record_key having count(*)>1)")
    duplicate=cur.fetchone()["n"]
assert not (missing or late or duplicate)
refresh=requests.post("http://127.0.0.1:8787/api/internal/refresh",headers={"Authorization":"Bearer "+secret("CRON_SECRET")},json={},timeout=90)
refresh.raise_for_status()
unauthorized=requests.post("http://127.0.0.1:8787/api/internal/refresh",json={},timeout=5)
assert unauthorized.status_code==401
report={"counts":counts(),"source_counts":sources,"missing_provenance":missing,"late_forecasts":late,"duplicates":duplicate,
        "repeat_cache_hit_preserves_counts":True,"authorized_refresh":refresh.json(),"unauthorized_refresh_status":unauthorized.status_code,"supabase_cron":cron,
        "example_environment":"LOCAL, real provider inputs and Supabase persistence; not a production acceptance claim","example":second.json()}
Path("results/nationwide_acceptance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k not in ("example","authorized_refresh")},indent=2))
print("Authorized refresh status:",report["authorized_refresh"]["status"])
