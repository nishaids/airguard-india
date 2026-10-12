"""Frozen development-only ADS requests; resumable jobs, secret-silent transport.

No target labels, model fitting, final-test access or production writes here.
The minimum supported rectangular ADS subset covers the frozen station sample.
Two jobs at most are submitted concurrently. A missing/ambiguous job ID never
causes an automatic replacement request.
"""
import argparse
import contextlib
import hashlib
import itertools
import json
import logging
import math
import os
from pathlib import Path
import sys
import time
from datetime import date, datetime, timedelta, timezone

from src.research.calibration import ads_probe
from src.research.calibration.checkpoint import canonical_hash, write_json
from src.research.calibration.protocol import load
from src.research.calibration.splits import calendar
from src.research.calibration.catalogue import SELECTION

ROOT = ads_probe.ROOT
PLAN = ROOT / 'results/research/cams_development_acquisition_plan.v2.json'
STATE = ROOT / 'results/research/cams_development_acquisition.json'
PARAMETERS = {
    'particulate_matter_2.5um': (210073, 'kg m**-3'),
    'particulate_matter_10um': (210074, 'kg m**-3'),
    'surface_pressure': (134, 'Pa'),
    'ozone': (210203, 'kg kg**-1'), 'nitrogen_dioxide': (210121, 'kg kg**-1'),
    'sulphur_dioxide': (210122, 'kg kg**-1'), 'carbon_monoxide': (210123, 'kg kg**-1'),
    'temperature': (130, 'K'), 'specific_humidity': (133, 'kg kg**-1'),
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def make_plan(protocol, selection):
    days = calendar(protocol)
    final_start = days[-int(protocol['splits']['final_test_days'])]
    # D-2 supplies the previous-day forecast descriptor; D-1 supplies target D.
    first_run, last_run = days[0] - timedelta(days=2), final_start - timedelta(days=2)
    stations = selection['stations']
    cells = [list(cell) for cell in sorted({(round(round(s['latitude']/.4)*.4, 1),
                     round(round(s['longitude']/.4)*.4, 1)) for s in stations})]
    area = [max(c[0] for c in cells), min(c[1] for c in cells),
            min(c[0] for c in cells), max(c[1] for c in cells)]
    jobs, start = [], first_run
    while start <= last_run:
        # Bounded calendar-month chunks with no duplicate dates.
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = min(last_run, next_month-timedelta(days=1))
        dates = [(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
        groups = (
            ('surface', ['particulate_matter_2.5um','particulate_matter_10um','surface_pressure'], list(range(11,43))),
            ('lowest_model_level', ['ozone','nitrogen_dioxide','sulphur_dioxide','carbon_monoxide','temperature','specific_humidity'], list(range(9,43,3))),
        )
        for group, variables, leads in groups:
            request = {'variable':variables, 'date':dates, 'time':['00:00'],
                       'leadtime_hour':[str(x) for x in leads], 'type':['forecast'],
                       'data_format':'grib', 'area':area}
            if group == 'lowest_model_level':
                request['model_level'] = ['137']
            identity = canonical_hash({'dataset':ads_probe.DATASET, 'request':request})
            jobs.append({'id':identity,'group':group,'request':request})
        start = end + timedelta(days=1)
    value = {'version':'cams-development-acquisition-v2', 'dataset':ads_probe.DATASET,
             'plan_refinement':'before any acquisition/model fitting; omitted unused final interpolation brackets +43h surface/+45h model level; original v1 preserved',
             'protocol_sha256':protocol['_sha256'], 'selection_sha256':canonical_hash(selection),
             'target_range':[str(days[0]),str(final_start-timedelta(days=1))],
             'final_test_range':[str(final_start),str(days[-1])], 'final_test_acquisition':False,
             'run_range':[str(first_run),str(last_run)],'run_count':(last_run-first_run).days+1,
             'station_count':len(stations),'station_cells':cells,'area':area,
             'matching':'nearest 0.4 degree grid centre; no outcome-dependent selection',
             'issue_policy':'00 UTC on D-1 for target D; previous descriptor from D-2 00 UTC',
             'availability_basis':'documented nominal 00 UTC dissemination by 10 UTC; historical delay logs unavailable; do not claim empirical per-run publication proof',
             'availability_source':'https://confluence.ecmwf.int/pages/viewpage.action?pageId=673323626',
             'time_sampling':'linear interpolation of same-run fields to IST hourly bin starts; 3-hour gas steps bracket 11.5..41.5h; no later forecast run',
             'gas_conversion':'same-run lowest-level T,q and hybrid pressure from GRIB pv plus surface pressure; refuse absent coefficients or inconsistent coordinates/times/units',
             'support_policy':'freeze PM2.5/PM10/O3 from original pre-issue sensor metadata; target-matched support only as evaluation annotation, never predictor',
             'fire_policy':'withheld unless actual historical publication evidence exists',
             'jobs':jobs}
    value['sha256'] = canonical_hash(value)
    return value


def freeze():
    probe = json.loads((ROOT/'results/research/cams_ads_probe.json').read_text(encoding='utf-8'))
    if probe.get('status') != 'VERIFIED_OPERATIONAL_FORECAST' or sha(ROOT/probe['file']) != probe['sha256']:
        raise ValueError('The existing verified probe and checksum are required')
    ads_probe.verify_fields(probe['decoded_fields'])
    value = make_plan(load(), json.loads(SELECTION.read_text(encoding='utf-8')))
    if PLAN.exists() and json.loads(PLAN.read_text(encoding='utf-8')) != value:
        raise ValueError('Acquisition plan changed: version rather than overwrite it')
    if not PLAN.exists():
        write_json(PLAN, value)
    return value


def validate_file(path, job):
    import eccodes as ec
    import numpy as np
    expected = {PARAMETERS[v][0]: PARAMETERS[v][1] for v in job['request']['variable']}
    dates = {int(x.replace('-','')) for x in job['request']['date']}
    leads = {int(x) for x in job['request']['leadtime_hour']}
    seen, grid, pv, missing, count = set(), None, None, 0, 0
    with Path(path).open('rb') as f:
        while (g := ec.codes_grib_new_from_file(f)) is not None:
            try:
                reference, step, parameter = (ec.codes_get(g,k) for k in ('dataDate','step','paramId'))
                identity = (reference, int(step), parameter)
                if (identity in seen or reference not in dates or int(step) not in leads or float(step) != int(step)
                        or parameter not in expected or ec.codes_get(g,'units') != expected[parameter]
                        or ec.codes_get(g,'dataType') != 'fc' or ec.codes_get(g,'dataTime') != 0
                        or ec.codes_get(g,'stepUnits') != 1):
                    raise ValueError('Unexpected or duplicate operational field metadata')
                actual_valid = datetime.strptime(str(ec.codes_get(g,'validityDate'))+f"{ec.codes_get(g,'validityTime'):04d}",'%Y%m%d%H%M')
                if actual_valid != datetime.strptime(str(reference),'%Y%m%d')+timedelta(hours=int(step)):
                    raise ValueError('Operational valid time does not equal run plus lead')
                level_type = ec.codes_get(g,'typeOfLevel')
                if job['group']=='lowest_model_level':
                    if level_type != 'hybrid' or ec.codes_get(g,'level') != 137:
                        raise ValueError('Gas and thermodynamics require the lowest model level 137')
                    coefficients = ec.codes_get_array(g,'pv').tolist()
                    if len(coefficients) != 276 or (pv is not None and pv != coefficients):
                        raise ValueError('Missing/inconsistent 137-level hybrid coefficients')
                    pv = coefficients
                elif level_type != 'surface':
                    raise ValueError('Surface parameter requires a surface field')
                info = {k:ec.codes_get(g,k) for k in ('Ni','Nj','latitudeOfFirstGridPointInDegrees',
                    'longitudeOfFirstGridPointInDegrees','latitudeOfLastGridPointInDegrees',
                    'longitudeOfLastGridPointInDegrees','iDirectionIncrementInDegrees','jDirectionIncrementInDegrees')}
                if grid is not None and grid != info:
                    raise ValueError('Operational grid changes within the requested chunk')
                grid = info
                area = job['request']['area']
                actual_area = [info['latitudeOfFirstGridPointInDegrees'],info['longitudeOfFirstGridPointInDegrees'],
                               info['latitudeOfLastGridPointInDegrees'],info['longitudeOfLastGridPointInDegrees']]
                if not np.allclose(area, actual_area, atol=1e-6) or not all(abs(info[k]-.4)<1e-6 for k in ('iDirectionIncrementInDegrees','jDirectionIncrementInDegrees')):
                    raise ValueError('Requested spatial subset/0.4-degree grid differs')
                values = ec.codes_get_values(g)
                if not np.isfinite(values).all() or ec.codes_get(g,'numberOfMissing'):
                    raise ValueError('Missing or nonfinite values in operational field')
                seen.add(identity); count += 1
            finally:
                ec.codes_release(g)
    required = set(itertools.product(dates, leads, expected))
    if seen != required:
        raise ValueError('Incomplete operational parameter/date/lead cube')
    return {'status':'VERIFIED_GRIB', 'messages':count, 'grid':grid,
            'parameter_units':expected, 'hybrid_coefficients':pv,
            'reference_dates':job['request']['date'], 'lead_hours':sorted(leads),
            'valid_time_rule':'reference date 00 UTC + lead hours',
            'decoder':'eccodes '+ec.codes_get_api_version()}


@contextlib.contextmanager
def lease(folder):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder/'acquisition.lock').open('a+b') as f:
        f.seek(0); f.write(b'0'); f.flush(); f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            f.seek(0)
            if os.name == 'nt': msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(f, fcntl.LOCK_UN)


def step():
    plan = freeze()
    folder = ROOT/'data/research/cams_operational'/plan['sha256']
    with lease(folder):
        record = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {
            'plan_sha256':plan['sha256'],'dataset':ads_probe.DATASET,'jobs':{}, 'final_test_accessed':False}
        if record['plan_sha256'] != plan['sha256']:
            raise ValueError('Archive state belongs to a different frozen plan')
        def save():
            record['checked_at_utc'] = ads_probe.now()
            record['counts'] = {s:sum(j['status']==s for j in record['jobs'].values()) for s in sorted({j['status'] for j in record['jobs'].values()})}
            record['complete'] = len(record['jobs'])==len(plan['jobs']) and all(j['status']=='VERIFIED_GRIB' for j in record['jobs'].values())
            write_json(STATE,record)
        logging.disable(sys.maxsize)
        with open(os.devnull,'w') as silent, contextlib.redirect_stdout(silent), contextlib.redirect_stderr(silent):
            import cdsapi
            client = cdsapi.Client(url='https://ads.atmosphere.copernicus.eu/api',quiet=True,
                debug=False,progress=False,retry_max=1,timeout=60,wait_until_complete=False,delete=False)
            for job in plan['jobs']:
                entry = record['jobs'].get(job['id'])
                if entry and entry['status']=='VERIFIED_GRIB':
                    if sha(ROOT/entry['file']) != entry['sha256']: raise ValueError('Archive file checksum differs')
                    continue
                if entry and entry['status'] not in ('SUBMITTED','accepted','running','successful'):
                    continue  # failures and ambiguous submits require review, never replacement
                if not entry:
                    active = sum(j['status'] in ('SUBMITTING','SUBMITTED','accepted','running','successful') for j in record['jobs'].values())
                    if active >= 2: continue
                    # Verify the first surface+model-level chunks before further jobs.
                    if job not in plan['jobs'][:2] and not all(record['jobs'].get(j['id'],{}).get('status')=='VERIFIED_GRIB' for j in plan['jobs'][:2]): continue
                    entry = record['jobs'][job['id']] = {'status':'SUBMITTING','request':job['request'],
                        'request_sha256':job['id'],'dataset':ads_probe.DATASET,'started_at_utc':ads_probe.now()}
                    save()
                    try:
                        remote = client.retrieve(ads_probe.DATASET,job['request'])
                        entry.update(status='SUBMITTED',request_id=remote.request_id,submitted_at_utc=ads_probe.now())
                        save()
                    except Exception as error:
                        entry.update(status='SUBMISSION_FAILED',error=ads_probe.safe_error(error)); save(); continue
                try:
                    remote = client.client.get_remote(entry['request_id'])
                    state = remote.status
                    if state not in ('accepted','running','successful','failed','rejected','dismissed','deleted'):
                        raise ValueError('Unknown provider job status')
                    entry['status'] = state
                    if entry['status']=='successful':
                        target = folder/(job['id']+'.grib')
                        if not target.exists():
                            temp = target.with_suffix('.grib.partial')
                            remote.download(str(temp)); temp.replace(target)
                        entry.update(file=target.relative_to(ROOT).as_posix(),bytes=target.stat().st_size,
                                     sha256=sha(target),retrieved_at_utc=ads_probe.now())
                        entry.update(validate_file(target,job))
                    save()
                except Exception as error:
                    entry.update(status='RETRIEVAL_OR_VALIDATION_FAILED',error=ads_probe.safe_error(error)); save()
            save()
        return {'complete':record['complete'],'counts':record['counts'],'total_jobs':len(plan['jobs'])}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--step',action='store_true')
    parser.add_argument('--worker-hours',type=float,default=0); args=parser.parse_args()
    if not args.step and not args.worker_hours:
        p=freeze(); print(json.dumps({k:p[k] for k in ('sha256','run_range','run_count','area','station_count')})); return
    deadline=time.monotonic()+min(24,max(0,args.worker_hours))*3600
    while True:
        result=step(); print(json.dumps(result),flush=True)
        if result['complete'] or time.monotonic()>=deadline or any('FAILED' in s or s in ('failed','rejected') for s in result['counts']): break
        time.sleep(60)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # Transport/configuration exceptions can contain secrets; never traceback.
        print(json.dumps({'status':'BLOCKED','exception_class':type(error).__name__, 'error':ads_probe.safe_error(error)}))
        sys.exit(1)
