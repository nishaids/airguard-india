"""Exercise genuinely uncached provider grids against the public live app."""
from datetime import datetime,timezone
from pathlib import Path
import argparse
import json
import time
import requests
from src.nationwide.contracts import validate_summary

ORIGIN='https://webapp-phi-taupe.vercel.app'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--follow-up',action='store_true')
    args=parser.parse_args()
    locations=[('Pilani',28.36,75.6),('Madikeri',12.42,75.73),('Nanded',19.16,77.31)] if args.follow_up else [('Jaisalmer',26.9,70.9),('Chitradurga',14.22,76.4),('Latur',18.4,76.56)]
    evidence=[]
    from src.ingestion.settings import load_env
    from src.nationwide.store import Store
    from src.nationwide.service import Service
    from src.nationwide.providers import grid
    from src.nationwide.aqi import METHOD
    load_env()
    store=Store()
    for name,lat,lon in locations:
        gx,gy=grid(lat,lon)
        with store.session():
            before={'summary_cached':bool(store.get(Service.summary_key(lat,lon))),
                    'provider_cached':bool(store.get(f'cams:{METHOD}:{gx},{gy}'))}
        assert not before['summary_cached'] and not before['provider_cached'], 'Probe requires unused coordinates/model grid'
        started=time.monotonic()
        polls=[]
        with requests.Session() as session:
            for attempt in range(24):
                r=session.get(ORIGIN+'/api/air-quality/summary',params={'lat':lat,'lon':lon,'name':name},timeout=(8,15))
                value=r.json()
                polls.append({'status':r.status_code,'ttfb_ms':round(r.elapsed.total_seconds()*1000),'state':value.get('state')})
                if r.status_code==202:
                    assert 'current' not in value and 'tomorrow' not in value
                    assert r.headers.get('Cache-Control')=='no-store'
                    time.sleep(5);continue
                assert r.status_code==200,(name,r.status_code,value.get('state'))
                validate_summary(value)
                assert value['tomorrow']['aqi'] is not None
                assert value['tomorrow']['forecast_mode']=='CAMS_BASED_NATIONWIDE'
                assert value['tomorrow']['corrected_aqi'] is None
                break
            else:raise AssertionError('Background fetch did not finish')
        row={'location':name,'coordinates':[lat,lon],'before':before,'elapsed_seconds':round(time.monotonic()-started,2),
             'requests':polls,'provider_status':value['provider_status'],'current_aqi':value['current']['aqi'],
             'tomorrow_aqi':value['tomorrow']['aqi'],'tomorrow_date':value['tomorrow']['date']}
        evidence.append(row);print(json.dumps(row),flush=True)
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'origin':ORIGIN,'passed':len(evidence),
            'note':'Three genuine provider-grid cache misses. This is a functional latency sample, not a statistically validated p95 claim.',
            'checks':evidence}
    Path('results/release/async_production.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
