"""Check staged or public production without exposing local credentials."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.parse import urlencode, urlparse

import requests
from src.ingestion.settings import load_env, secret, SECRET_NAMES
from src.nationwide.contracts import validate_summary

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--protected', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    load_env()
    parsed = urlparse(args.url)
    if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.startswith('webapp-') or not parsed.hostname.endswith('.vercel.app') or parsed.path:
        raise ValueError('Supply this project deployment origin.')
    cli = None
    if args.protected:
        packages = (Path(os.environ['LOCALAPPDATA']) / 'npm-cache/_npx').glob('*/node_modules/vercel/package.json')
        cli = next(p.parent / 'dist/vc.js' for p in packages if json.loads(p.read_text())['version'] == '63.1.2')

    def request(path, expected=200, marker=None, method='GET', authorized=False, attempt=0):
        if args.protected:
            command = [shutil.which('node'), str(cli), 'curl', path, '--deployment', args.url, '--', '--silent', '--show-error', '--max-time', '310', '--request', method, '--write-out', 'HTTP_STATUS:%{http_code}']
            header_input = None
            if method == 'POST':
                command += ['--data', '{}', '--header', 'Content-Type: application/json']
            if authorized:
                command += ['--header', '@-']
                header_input = 'Authorization: Bearer ' + secret('CRON_SECRET') + '\n'
            response = subprocess.run(command, input=header_input, cwd=ROOT/'webapp', capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=330)
            body, _, status = response.stdout.rpartition('HTTP_STATUS:')
            assert response.returncode == 0 and status.isdigit(), 'Deployment transport failed'
            status = int(status)
        else:
            headers = {'Authorization': 'Bearer ' + secret('CRON_SECRET')} if authorized else {}
            response = requests.request(method, args.url + path, json={} if method == 'POST' else None, headers=headers, timeout=(15,310), allow_redirects=False)
            body, status = response.text, response.status_code
            if marker:
                for name in ('Content-Security-Policy','X-Content-Type-Options','X-Frame-Options','Permissions-Policy'):
                    assert name in response.headers, 'Missing production security header'
        assert all(not secret(name) or secret(name) not in body for name in SECRET_NAMES), 'Configured secret in response'
        if status==202 and expected==200 and method=='GET' and attempt<24:
            pending=json.loads(body)
            assert pending['state'] in ('QUEUED','IN_PROGRESS') and 'current' not in pending
            time.sleep(5)
            return request(path,expected,marker,method,authorized,attempt+1)
        assert status == expected, f'{path.split("?")[0]} unexpected HTTP {status}'
        if marker:
            assert marker in body, 'Expected page marker absent'
            value = None
        else:
            value = json.loads(body)
        result = {'path': path, 'status': status, 'method': method, 'authorized': authorized, 'kind': 'SSR HTML' if marker else 'HTTP JSON'}
        print(json.dumps(result), flush=True)
        return result, value

    read_jobs = [
        ('/',200,'AirGuard'),('/live',200,'AirGuard'),('/research',200,'Station-calibrated forecasting research'),
        ('/research/track-record',200,'Prospective forecast ledger'),('/research/legacy',200,'AirGuard'),('/methods',200,'CPCB'),
        ('/forecast',200,'Forecast &amp; advisory'),('/city-atlas',200,'Air quality across selected places'),
        ('/policy-simulator',200,'Policy scenarios'),('/status',200,'Live system status'),
        ('/api/health',200,None),('/api/research/status',200,None),('/api/providers/status',200,None),
        ('/api/status/scheduler',200,None),
        ('/api/air-quality/tomorrow?lat=13.1147&lon=80.10981&name=Avadi',200,None),
        ('/api/air-quality/context?lat=13.1147&lon=80.10981&name=Avadi',200,None),
        ('/api/research/status?unexpected=1',400,None),('/api/providers/status?view=refresh',400,None),
        ('/api/air-quality/summary?lat=999&lon=80',400,None),('/api/internal/refresh',405,None),('/api/live_forecast',410,None),
        ('/api/locations/search?q=600054',200,None),('/api/live',200,None),
    ]
    locations = [('Avadi',13.1149,80.0969),('Chennai',13.0827,80.2707),('Delhi',28.6139,77.209),('Mumbai',19.076,72.8777),('Bengaluru',12.9716,77.5946),('Kolkata',22.5726,88.3639),('Hyderabad',17.385,78.4867),('Kochi',9.9312,76.2673)]
    if args.protected:
        locations = locations[:2]
    for name,lat,lon in locations:
        read_jobs.append(('/api/air-quality/summary?'+urlencode({'lat':lat,'lon':lon,'name':name}),200,None))
    read_jobs.append(('/api/air-quality/summary?lat=23.4&lon=70.4&name=Remote',200,None))
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(lambda job:request(*job), read_jobs))
    evidence = {}
    for check, value in responses:
        path = check['path']
        if path == '/api/health': assert value['database']=='CONNECTED'
        if path == '/api/status/scheduler':
            assert len(value['schedules']) == 4 and all(s['active'] for s in value['schedules'])
            evidence['scheduler'] = value
        if path.startswith('/api/air-quality/tomorrow?'):
            assert 'tomorrow' in value and 'current' not in value and value['hourly_forecast']
        if path.startswith('/api/air-quality/context?'):
            assert 'weather_context' in value and 'fire_context' in value and 'tomorrow' not in value
        if path == '/api/research/status':
            assert value['protocol']['protocol_version']=='airguard-dayahead-20ist-v1'
            assert value['archive_experiment']=='PENDING \u2014 ADS credential/terms required'
            evidence['research'] = value['prospective']
        if path.startswith('/api/air-quality/summary?') and check['status']==200:
            validate_summary(value)
            tomorrow = value['tomorrow']
            assert tomorrow['aqi'] is not None and tomorrow['forecast_mode']=='CAMS_BASED_NATIONWIDE'
            assert tomorrow['corrected_aqi'] is None and tomorrow['prediction_interval'] is None
            assert tomorrow['date'] > datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date().isoformat()
            if 'name=Remote' in path: assert value['current']['measured_or_modelled']=='MODELLED'
            if 'name=Avadi' in path: evidence['avadi'] = {'current':value['current'],'tomorrow':tomorrow,'provenance':value['provenance']}
    checks = [r[0] for r in responses]
    summary = next(value for check,value in responses if check['path'].startswith('/api/air-quality/summary?') and 'name=Avadi' in check['path'])
    reference = {'forecast_run_id':summary['tomorrow']['forecast_run_id'],'location_key':summary['location']['key']}
    def scenario(reductions, expected=200):
        payload={**reference,'reductions':reductions}
        path='/api/air-quality/scenario'
        if args.protected:
            command=[shutil.which('node'),str(cli),'curl',path,'--deployment',args.url,'--','--silent','--show-error','--max-time','90','--request','POST','--header','Content-Type: application/json','--data',json.dumps(payload),'--write-out','HTTP_STATUS:%{http_code}']
            response=subprocess.run(command,cwd=ROOT/'webapp',capture_output=True,text=True,encoding='utf-8',timeout=110)
            body,_,status=response.stdout.rpartition('HTTP_STATUS:');status=int(status)
        else:
            response=requests.post(args.url+path,json=payload,timeout=(15,90),allow_redirects=False);body=response.text;status=response.status_code
        assert status==expected, 'Scenario response failed'
        assert all(not secret(n) or secret(n) not in body for n in SECRET_NAMES), 'Secret in scenario response'
        checks.append({'path':path,'status':status,'method':'POST','kind':'HTTP JSON'})
        return json.loads(body)
    zero=scenario({});changed=scenario({'PM2.5':.2});scenario({'PM2.5':2},400)
    assert zero['baseline']==zero['scenario'] and zero['baseline']['aqi']==summary['tomorrow']['aqi']
    assert changed['forecast_run_id']==reference['forecast_run_id'] and changed['scenario']['aqi']<=zero['baseline']['aqi']
    assert changed['input_reference']==zero['input_reference']
    checks.append(request('/api/internal/refresh',401,method='POST')[0])
    if args.refresh:
        check, refresh = request('/api/internal/refresh',method='POST',authorized=True)
        assert refresh['status'] in ('SUCCESS','PARTIAL','SKIPPED_OVERLAP')
        checks.append(check); evidence['refresh'] = refresh
    report = {'generated_at':datetime.now(timezone.utc).isoformat(),'url':args.url,'environment':'STAGED_PRODUCTION' if args.protected else 'PUBLIC_PRODUCTION','checks':checks,'passed':len(checks),'evidence':evidence,'browser_visual_qa':'NOT_EXECUTED'}
    destination = ROOT/'results/research'/('staged_production_acceptance.json' if args.protected else 'production_acceptance.json')
    destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':len(checks),'environment':report['environment']}))


if __name__ == '__main__': main()
