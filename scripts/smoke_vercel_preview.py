"""Authenticated preview checks using the existing CLI login; no secret output.

Run from repo root: python -m scripts.smoke_vercel_preview <preview URL>
The scheduler bearer header is supplied to curl on stdin, never argv.
"""
import json
import subprocess
import sys
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlencode
from src.ingestion.settings import load_env, secret, SECRET_NAMES
from src.nationwide.contracts import validate_summary

load_env()
url=sys.argv[1]
if not url.startswith("https://webapp-") or not url.endswith(".vercel.app"):
    raise ValueError("Supply this project's Vercel preview URL.")
root=Path(__file__).resolve().parents[1]
# Invoke Node directly: Windows .cmd launchers can reinterpret query ampersands.
packages=(Path(os.environ["LOCALAPPDATA"])/"npm-cache/_npx").glob("*/node_modules/vercel/package.json")
cli=next(p.parent/"dist/vc.js" for p in packages if json.loads(p.read_text())["version"]=="63.1.2")
checks=[]
def page_check(path,marker):
    args=[shutil.which("node"),str(cli),"curl",path,"--deployment",url,"--","--silent","--show-error","--include","--max-time","60","--write-out","HTTP_STATUS:%{http_code}"]
    result=subprocess.run(args,cwd=root/"webapp",capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=90)
    body,_,status=result.stdout.rpartition("HTTP_STATUS:")
    assert status=="200" and marker in body,"Hosted page check failed: "+path
    for header in ("content-security-policy:","x-content-type-options:","x-frame-options:","permissions-policy:"):
        assert any(line.lower().startswith(header) for line in body.splitlines()),"Missing hosted security header: "+header
    checks.append({"path":path,"status":200,"rendered_marker":marker,"kind":"server-rendered HTML, not browser visual QA"})
    print(json.dumps(checks[-1]),flush=True)

page_check("/","AirGuard")
page_check("/live","AirGuard")
page_check("/research","Research")
page_check("/methods","CPCB")
def request(path,expected=200,method="GET",authorized=False):
    args=[shutil.which("node"),str(cli),"curl",path,"--deployment",url,"--","--silent","--show-error","--max-time","310","--write-out","HTTP_STATUS:%{http_code}","--request",method]
    headers=None
    if method=="POST":args += ["--data","{}","--header","Content-Type: application/json"]
    if authorized:
        args += ["--header","@-"]
        headers="Authorization: Bearer "+secret("CRON_SECRET")+"\n"
    result=subprocess.run(args,cwd=root/"webapp",input=headers,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=330)
    body,_,status=result.stdout.rpartition("HTTP_STATUS:")
    assert result.returncode==0 and status==str(expected),f"{path.split('?')[0]} unexpected HTTP {status if status.isdigit() else 'transport failure'}"
    assert all(not secret(name) or secret(name) not in body for name in SECRET_NAMES),"Response contains a configured secret"
    data=json.loads(body)
    checks.append({"path":path.split("?")[0],"status":int(status),"method":method,"authorized":authorized})
    print(json.dumps(checks[-1]),flush=True)
    return data

health=request("/api/health")
assert health["database"]=="CONNECTED"
search=request("/api/locations/search?q=Avadi")
place=next(p for p in search["results"] if p["name"].startswith("Avadi"))
query=urlencode({"lat":place["lat"],"lon":place["lon"],"name":place["name"],"region":place.get("region") or ""})
example=request("/api/air-quality/summary?"+query)
validate_summary(example)
from src.nationwide.store import Store
with Store().cursor() as cur:
    cur.execute("select issued_at from airguard.forecast_runs where id=%s",(example["tomorrow"]["forecast_run_id"],))
    assert cur.fetchone()["issued_at"].isoformat()==example["tomorrow"]["issued_at"],"Response must match the immutable saved issue time"
repeat=request("/api/air-quality/summary?"+query)
assert example["tomorrow"]["forecast_run_id"]==repeat["tomorrow"]["forecast_run_id"]
request("/api/air-quality/current?"+query)
request("/api/air-quality/forecast?"+query)
providers=request("/api/providers/status")
request("/api/air-quality/summary?lat=999&lon=80",400)
request("/api/internal/refresh",405)
request("/api/internal/refresh",401,"POST")
refresh=request("/api/internal/refresh",200,"POST",True)
request("/api/live_forecast",410)
request("/api/live")
for name in ("Delhi","Mumbai","Chennai","Bengaluru","Kolkata","Hyderabad","Coimbatore","Kochi","Guwahati","Jaipur"):
    found=request("/api/locations/search?"+urlencode({"q":name}))
    assert found["results"],"Expected an India place result for "+name
    location=found["results"][0]
    data=request("/api/air-quality/summary?"+urlencode({"lat":location["lat"],"lon":location["lon"],"name":location["name"],"region":location.get("region") or ""}))
    validate_summary(data)
    assert data["tomorrow"]["aqi"] is not None
postal=request("/api/locations/search?q=600054")
assert "Provider dependent" in postal["postal_code_support"]
remote=request("/api/air-quality/summary?"+urlencode({"lat":23.4,"lon":70.4,"name":"Remote Gujarat coordinate"}))
assert remote["current"]["measured_or_modelled"]=="MODELLED"
report={"environment":"VERCEL PREVIEW with real providers and Supabase; production remains unchanged","deployment_url":url,"checks":checks,"example":example,"providers":providers,"refresh":refresh}
(root/"results/nationwide_staging_acceptance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"passed":len(checks),"current":example["current"]["aqi"],"source":example["current"]["measured_or_modelled"],"tomorrow":example["tomorrow"]["aqi"],"refresh":refresh["status"]}))
