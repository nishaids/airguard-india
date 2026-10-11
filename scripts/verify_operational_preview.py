"""Protected-preview HTTP acceptance. Does not promote or change production."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlencode
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.ingestion.settings import load_env, secret, SECRET_NAMES
from src.nationwide.contracts import validate_summary


def main():
    load_env()
    url = sys.argv[1].rstrip('/')
    if not url.startswith('https://webapp-') or not url.endswith('.vercel.app'): raise ValueError('Supply the webapp preview URL.')
    cli = next(p.parent/'dist/vc.js' for p in (Path(os.environ['LOCALAPPDATA'])/'npm-cache/_npx').glob('*/node_modules/vercel/package.json') if json.loads(p.read_text())['version']=='63.1.2')
    checks = []
    def request(path, payload=None, expected=200, marker=None):
        args = [shutil.which('node'),str(cli),'curl',path,'--deployment',url,'--','--silent','--show-error','--max-time','90','--write-out','HTTP_STATUS:%{http_code}']
        if payload is not None: args.extend(['--request','POST','--header','Content-Type: application/json','--data',json.dumps(payload)])
        response = subprocess.run(args,cwd=ROOT/'webapp',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=115)
        body,_,status = response.stdout.rpartition('HTTP_STATUS:')
        assert response.returncode==0 and status==str(expected), f'Unexpected HTTP result on {path}: {status}'
        assert all(not secret(n) or secret(n) not in body for n in SECRET_NAMES), 'Unexpected secret in response'
        if marker is not None:
            assert marker in body, f'Missing route marker on {path}'
            value = body
        else: value = json.loads(body)
        check = {'path':path,'status':expected,'kind':'SSR HTML' if marker else 'HTTP JSON'}; checks.append(check); print(json.dumps(check),flush=True)
        return value
    pages = [('/live','Air quality, with its evidence'),('/forecast','Forecast &amp; advisory'),('/policy-simulator','Policy scenarios'),('/city-atlas','Air quality across selected places'),('/research','LIVE / OPERATIONAL RESEARCH'),('/historical-replay','AirGuard'),('/research/historical-atlas','AirGuard'),('/research/historical-policy','AirGuard'),('/model-insights','AirGuard'),('/research/legacy','AirGuard'),('/methods','One operational data flow')]
    with ThreadPoolExecutor(max_workers=3) as pool: list(pool.map(lambda pair:request(pair[0],marker=pair[1]),pages))
    health = request('/api/health'); assert health['database']=='CONNECTED'
    cities = [('Avadi',13.1147,80.10981),('Delhi',28.6139,77.209),('Mumbai',19.076,72.8777),('Chennai',13.0827,80.2707),('Coimbatore',11.0168,76.9558),('Kochi',9.9312,76.2673)]
    def summary(place):
        name,lat,lon = place
        value = request('/api/air-quality/summary?'+urlencode({'lat':lat,'lon':lon,'name':name})); validate_summary(value)
        assert value['tomorrow']['aqi'] is not None and value['tomorrow']['forecast_run_id'] > 0
        assert value['tomorrow']['forecast_mode']=='CAMS_BASED_NATIONWIDE' and value['tomorrow']['corrected_aqi'] is None and value['tomorrow']['prediction_interval'] is None
        assert value['tomorrow']['date'] > datetime.now(timezone.utc).date().isoformat()
        assert sum(1 for h in value['hourly_forecast'] if value['tomorrow']['window_start'] <= h['time'] < value['tomorrow']['window_end'])==24
        return name,value
    with ThreadPoolExecutor(max_workers=2) as pool: summaries = dict(pool.map(summary,cities))
    avadi = summaries['Avadi']; t=avadi['tomorrow']; reference={'forecast_run_id':t['forecast_run_id'],'location_key':avadi['location']['key']}
    zero=request('/api/air-quality/scenario',{**reference,'reductions':{}})
    assert zero['baseline']['aqi']==t['aqi'] and zero['scenario']==zero['baseline']
    changed=request('/api/air-quality/scenario',{**reference,'reductions':{'PM2.5':.2}})
    assert changed['baseline']['aqi']==t['aqi'] and changed['forecast_run_id']==t['forecast_run_id'] and changed['input_reference']==zero['input_reference']
    assert changed['scenario']['aqi'] <= t['aqi'] and changed['methodology_version']==avadi['provenance']['methodology_version']
    request('/api/air-quality/scenario',{'reductions':{'PM2.5':.2}},expected=400)
    request('/api/air-quality/scenario',{**reference,'reductions':{'PM2.5':2}},expected=400)
    request('/api/air-quality/scenario',{**reference,'location_key':'wrong','reductions':{}},expected=404)
    request('/api/air-quality/scenario',expected=405)
    research=request('/api/research/status'); assert research['correction_status']=='NOT_VALIDATED' and research['archive_experiment']=='PENDING — ADS credential/terms required'
    remote=request('/api/air-quality/summary?lat=23.4&lon=70.4&name=Remote'); assert remote['current']['measured_or_modelled']=='MODELLED'
    old=request('/api/forecast',{'city':'Delhi','date':'2020-07-01','cohort':'healthy_adult'}); assert old['ok']
    historical_policy=request('/api/policy_simulate',{'reductions':{'PM2.5':.1}}); assert historical_policy['ok']
    meta=request('/data/meta.json'); assert meta['date_bounds']['Delhi']['min']=='2015-01-01' and meta['date_bounds']['Delhi']['max']=='2020-07-01'
    audit=json.loads((ROOT/'results/ui_integration/audit.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in audit['preserved_artifact_sha256'].items())
    def describe(s):
        return {'location':s['location'],'current':{k:s['current'].get(k) for k in ('aqi','qualifier','source','timestamp','freshness','measured_or_modelled')},'tomorrow':{k:s['tomorrow'].get(k) for k in ('aqi','qualifier','date','issued_at','forecast_mode','forecast_run_id','freshness','dominant_pollutant')},'methodology':s['provenance']['methodology_version'],'provider_status':s['provider_status']}
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'deployment_url':url,'passed':len(checks),'checks':checks,'cities':{n:describe(s) for n,s in summaries.items()},'avadi_flow':{'Live':describe(avadi),'Forecast & Advisory':'Same shared Summary object, verified by actual route-component navigation test','Policy baseline':zero['baseline']['aqi'],'forecast_run_id':t['forecast_run_id'],'PM2.5_minus_20_percent':changed['scenario'],'input_reference':changed['input_reference']},'research':research['prospective'],'archive_experiment':research['archive_experiment'],'historical_model_and_data_hashes_unchanged':True,'production_changed':False,'visual_browser_qa':'NOT_EXECUTED — browser navigation was blocked by the environment; no alternative browser bypass used','coverage':'Actual React route components under one provider + protected preview SSR/API/Supabase integration. HTTP Playwright tests are not browser-driven E2E.'}
    (ROOT/'results/ui_integration/preview_acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (ROOT/'results/ui_integration/avadi_summary.json').write_text(json.dumps(avadi,indent=2),encoding='utf-8')
    print(json.dumps({'passed':len(checks),'Avadi_current':avadi['current']['aqi'],'Avadi_tomorrow':t['aqi'],'scenario':changed['scenario']['aqi'],'forecast_run_id':t['forecast_run_id']}))

if __name__=='__main__': main()
