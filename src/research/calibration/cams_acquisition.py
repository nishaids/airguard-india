"""Frozen development-only ADS requests; resumable jobs, secret-silent transport.

No target labels, model fitting, final-test access or production writes here.
The minimum supported rectangular ADS subset covers the frozen station sample.
New jobs are submitted sequentially, after all existing jobs finish. A missing/ambiguous job ID never
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
    container = ads_probe.validate_grib_container(path)
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
                if tuple(ec.codes_get(g,k) for k in ('centre','marsClass','marsStream','marsType')) != ('ecmf','mc','oper','fc'):
                    raise ValueError('Not the ECMWF CAMS operational forecast product')
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
    if seen != required or count != container['messages']:
        raise ValueError('Incomplete operational parameter/date/lead cube')
    return {'status':'VERIFIED_GRIB', 'messages':count, 'grid':grid,
            'container_validation':container,
            'parameter_units':expected, 'hybrid_coefficients':pv,
            'reference_dates':job['request']['date'], 'lead_hours':sorted(leads),
            'product_metadata':{'centre':'ecmf','marsClass':'mc','marsStream':'oper','marsType':'fc'},
            'reference_time_range_utc':[datetime.strptime(str(d),'%Y%m%d').replace(tzinfo=timezone.utc).isoformat() for d in (min(dates),max(dates))],
            'valid_time_range_utc':[(datetime.strptime(str(d),'%Y%m%d').replace(tzinfo=timezone.utc)+timedelta(hours=h)).isoformat() for d,h in ((min(dates),min(leads)),(max(dates),max(leads)))],
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


def step(*, poll_only=False):
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
                    if poll_only or record.get('submission_control',{}).get('new_requests_authorized') is False:
                        continue
                    active = sum(j['status'] in ('SUBMITTING','SUBMITTED','accepted','running','successful') for j in record['jobs'].values())
                    # Also block on unresolved failures: review/recover the existing
                    # ID instead of adding load or silently leaving a data gap.
                    unresolved = any(j['status'] != 'VERIFIED_GRIB' for j in record['jobs'].values())
                    if active or unresolved: continue
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


def pause_new_requests():
    """Persist the author's submission pause without changing IDs or the plan."""
    record = json.loads(STATE.read_text(encoding='utf-8'))
    with lease(ROOT/'data/research/cams_operational'/record['plan_sha256']):
        record = json.loads(STATE.read_text(encoding='utf-8'))
        record['submission_control'] = {
            'new_requests_authorized': False, 'recorded_at_utc': ads_probe.now(),
            'reason': 'Author requested existing-request reconciliation only; no new ADS submissions.'}
        write_json(STATE, record)
    return {'new_requests_authorized':False,'request_ids_preserved':True}


def reconcile_existing(request_ids):
    """Poll an explicit scope of known IDs, reuse/download, hash and decode only.

    No retrieve/submit endpoint is called. Provider replies and download URLs
    are never printed or stored; only allowlisted non-secret fields are retained.
    """
    if len(request_ids) != len(set(request_ids)) or not request_ids:
        raise ValueError('A unique nonempty existing-request scope is required')
    plan = freeze()
    probe_path = ROOT/'results/research/cams_ads_probe.json'
    probe = json.loads(probe_path.read_text(encoding='utf-8'))
    folder = ROOT/'data/research/cams_operational'/plan['sha256']
    report_path = ROOT/'results/research/cams_archive_status.json'
    with lease(folder):
        record = json.loads(STATE.read_text(encoding='utf-8'))
        known = {e['request_id']:(j,e) for j in plan['jobs']
                 if (e:=record['jobs'].get(j['id'],{})).get('request_id')}
        if probe.get('request_id') in known:
            raise ValueError('Probe and archive request IDs overlap')
        unknown = set(request_ids) - set(known) - {probe.get('request_id')}
        if unknown:
            raise ValueError('Unknown request ID; reconciliation cannot submit it')
        if record.get('submission_control',{}).get('new_requests_authorized') is not False:
            raise ValueError('Pause new submissions before reconciling existing requests')
        rows = []
        old_logging = logging.root.manager.disable
        logging.disable(sys.maxsize)
        try:
            with open(os.devnull,'w') as silent, contextlib.redirect_stdout(silent), contextlib.redirect_stderr(silent):
                import cdsapi
                client = cdsapi.Client(url='https://ads.atmosphere.copernicus.eu/api',quiet=True,
                    debug=False,progress=False,retry_max=1,timeout=60,wait_until_complete=False,delete=False)
                for request_id in request_ids:
                    is_probe = request_id == probe['request_id']
                    job, entry = (None,probe) if is_probe else known[request_id]
                    row = {'request_id':request_id,'scope':'probe' if is_probe else 'development_chunk',
                           'downloaded_locally':False,'content_valid':False,'checksum_verified':False,
                           'protocol_accepted_primary_chunk':False,'status_checked_at_utc':ads_probe.now(),
                           'submitted_at_utc':entry.get('submitted_at_utc')}
                    if job:
                        row.update(job_sha256=job['id'],group=job['group'],
                                   reference_date_range=[job['request']['date'][0],job['request']['date'][-1]])
                    try:
                        remote = client.client.get_remote(request_id)
                        reply = remote.json
                        server = {k:reply.get(k) for k in ('status','processID','created','started','finished','updated')}
                        if server['status'] not in ('accepted','running','successful','failed','rejected','dismissed','deleted'):
                            raise ValueError('Unknown provider status')
                        if server['processID'] != ads_probe.DATASET:
                            raise ValueError('Provider collection differs from the CAMS forecast dataset')
                        row['server'] = server
                        entry['server_metadata'] = server
                        if server['status'] == 'successful':
                            target = ROOT/entry['file'] if entry.get('file') else folder/(job['id']+'.grib')
                            existed = target.exists()
                            if not existed:
                                temporary = target.with_suffix('.grib.partial')
                                remote.download(str(temporary))
                                temporary.replace(target)
                                entry.update(file=target.relative_to(ROOT).as_posix(),retrieved_at_utc=ads_probe.now())
                            digest = sha(target)
                            row.update(downloaded_locally=True,reused_local_artifact=existed,
                                       file=target.relative_to(ROOT).as_posix(),bytes=target.stat().st_size,sha256=digest,
                                       retrieved_at_utc=entry.get('retrieved_at_utc'))
                            if entry.get('sha256') and entry['sha256'] != digest:
                                raise ValueError('Existing artifact checksum differs')
                            row['checksum_verified'] = True
                            if is_probe:
                                # Re-decode the original tiny binary; never submit another probe.
                                ads_probe.audit()
                                entry = probe = json.loads(probe_path.read_text(encoding='utf-8'))
                                entry['server_metadata'] = server
                                row.update(decoded_fields=probe['decoded_fields'],
                                           container_validation=probe['container_validation'],
                                           probe_accepted=True,
                                           explanation='One complete GRIB1 PM2.5 surface message, nine grid values; smoke validation only, not a primary archive chunk.')
                                if target.stat().st_size <= 256:
                                    row['binary_hex'] = target.read_bytes().hex()
                            else:
                                decoded = validate_file(target,job)
                                entry.update(decoded,bytes=target.stat().st_size,sha256=digest)
                                row.update(content_validation=decoded,protocol_accepted_primary_chunk=True)
                            row['content_valid'] = True
                            row['validated_at_utc'] = ads_probe.now()
                        else:
                            row['validation_not_attempted'] = 'Provider result is not successful'
                    except Exception as error:
                        row['error'] = ads_probe.safe_error(error)
                        # Exception text may contain signed URLs or secrets: record class only.
                        row['exception_class'] = type(error).__name__
                        if not is_probe and row.get('downloaded_locally') and not row['content_valid']:
                            entry['status'] = 'RETRIEVAL_OR_VALIDATION_FAILED'
                            entry['error'] = row['error']
                    rows.append(row)
        finally:
            logging.disable(old_logging)
        probe['server_metadata'] = next((r['server'] for r in rows if r['scope']=='probe' and 'server' in r),probe.get('server_metadata',{}))
        write_json(probe_path,probe)
        if probe.get('file'):
            write_json((ROOT/probe['file']).parent/'retrieval.json',probe)
        probe_row = next((r for r in rows if r['scope']=='probe'),None)
        if probe_row:
            write_json(ROOT/'results/research/cams_ads_probe_status.json', {
                'local_status':probe['status'],'remote_status':probe_row.get('server',{}).get('status'),
                'checked_at_utc':probe_row['status_checked_at_utc']})
        record['checked_at_utc'] = ads_probe.now()
        record['counts'] = {s:sum(j['status']==s for j in record['jobs'].values()) for s in sorted({j['status'] for j in record['jobs'].values()})}
        record['complete'] = len(record['jobs'])==len(plan['jobs']) and all(j['status']=='VERIFIED_GRIB' for j in record['jobs'].values())
        record['reconciliation'] = {'request_ids':request_ids,'checked_at_utc':record['checked_at_utc'],
                                    'report':report_path.relative_to(ROOT).as_posix(),'new_requests_submitted':0}
        write_json(STATE,record)
        extra = [{'request_id':rid,'job_sha256':job['id'],'status':entry['status'],
                  'submitted_at_utc':entry.get('submitted_at_utc'),
                  'reference_date_range':[job['request']['date'][0],job['request']['date'][-1]],
                  'reason':'Pre-existing request outside the nine reported successes; preserved, not polled or downloaded by this reconciliation.'}
                 for rid,(job,entry) in known.items() if rid not in request_ids]
        counts = {'ads_requests_in_reported_scope':len(rows),
                  'ads_server_side_successful':sum(r.get('server',{}).get('status')=='successful' for r in rows),
                  'downloaded_locally':sum(r['downloaded_locally'] for r in rows),
                  'content_valid':sum(r['content_valid'] for r in rows),
                  'checksum_verified':sum(r['checksum_verified'] for r in rows),
                  'protocol_accepted_primary_chunks':sum(r['protocol_accepted_primary_chunk'] for r in rows),
                  'accepted_probe_artifacts':sum(r.get('probe_accepted',False) for r in rows),
                  'overall_cams_chunks_verified':record['counts'].get('VERIFIED_GRIB',0),
                  'required_cams_chunks':len(plan['jobs'])}
        report = {'status':'EXISTING_REQUESTS_RECONCILED','generated_at_utc':ads_probe.now(),
                  'dataset':ads_probe.DATASET,'plan_sha256':plan['sha256'],
                  'protocol_sha256':plan['protocol_sha256'],'counts':counts,'requests':rows,
                  'additional_preexisting_requests':extra,'total_known_request_ids':len(known)+1,
                  'new_requests_submitted':0,'replacement_requests_submitted':0,
                  'invalid_or_unverified_request_ids':[r['request_id'] for r in rows if not r['content_valid']],
                  'final_test_accessed':False,'new_submissions_paused':True,
                  'scientific_scope':'CAMS operational forecast development archive; the probe is not counted among the 36 primary chunks.'}
        write_json(report_path,report)
    return counts


def reopen_transport_failure(job_prefix, note):
    """Reviewed recovery of one existing remote ID after a transport failure.

    Nothing is submitted. The entry returns to a pollable state only when the
    recorded failure carried no provider status and no file was written, so a
    rejected request or a validation failure can never be reopened this way.
    """
    plan = freeze()
    folder = ROOT/'data/research/cams_operational'/plan['sha256']
    with lease(folder):
        record = json.loads(STATE.read_text(encoding='utf-8'))
        if record['plan_sha256'] != plan['sha256']:
            raise ValueError('Archive state belongs to a different frozen plan')
        matches = [key for key in record['jobs'] if key.startswith(job_prefix)]
        if len(job_prefix) < 8 or len(matches) != 1:
            raise ValueError('Exactly one existing job must match the reviewed identifier')
        entry, error = record['jobs'][matches[0]], record['jobs'][matches[0]].get('error') or {}
        if (entry['status'] != 'RETRIEVAL_OR_VALIDATION_FAILED' or not entry.get('request_id') or entry.get('file')
                or error.get('category') != 'CLIENT_OR_SERVICE_ERROR' or error.get('http_status') is not None
                or (folder/(matches[0]+'.grib')).exists()):
            raise ValueError('Only a transport failure with an existing remote ID and no downloaded file may be reopened')
        entry.setdefault('recovery_history', []).append({'reopened_at_utc':ads_probe.now(), 'previous_status':entry['status'],
            'previous_error':error, 'review_note':str(note), 'new_request_submitted':False})
        entry['status'] = 'running'  # re-polled under the original ID by the next step
        entry.pop('error', None)
        record['checked_at_utc'] = ads_probe.now()
        record['counts'] = {s:sum(j['status']==s for j in record['jobs'].values()) for s in sorted({j['status'] for j in record['jobs'].values()})}
        record['complete'] = False
        write_json(STATE, record)
        return {'reopened':matches[0][:12], 'counts':record['counts'], 'new_request_submitted':False}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--step',action='store_true')
    parser.add_argument('--poll-only',action='store_true',help='Recheck/download existing IDs; never submit a request')
    parser.add_argument('--reopen-transport-failure',metavar='JOB_PREFIX',help='Reviewed re-poll of one existing remote ID; never submits')
    parser.add_argument('--review-note',default='')
    parser.add_argument('--pause-new-requests',action='store_true')
    parser.add_argument('--reconcile-request-ids',nargs='+',help='Recheck only these already-recorded request IDs; never submit')
    parser.add_argument('--worker-hours',type=float,default=0); args=parser.parse_args()
    if args.pause_new_requests:
        print(json.dumps(pause_new_requests()))
        if not args.reconcile_request_ids:return
    if args.reconcile_request_ids:
        print(json.dumps(reconcile_existing(args.reconcile_request_ids)));return
    if args.reopen_transport_failure:
        if not args.review_note.strip():
            raise ValueError('A review note is required')
        print(json.dumps(reopen_transport_failure(args.reopen_transport_failure, args.review_note))); return
    if not args.step and not args.worker_hours and not args.poll_only:
        p=freeze(); print(json.dumps({k:p[k] for k in ('sha256','run_range','run_count','area','station_count')})); return
    deadline=time.monotonic()+min(24,max(0,args.worker_hours))*3600
    while True:
        result=step(poll_only=args.poll_only); print(json.dumps(result),flush=True)
        if result['complete'] or time.monotonic()>=deadline or any('FAILED' in s or s in ('failed','rejected') for s in result['counts']): break
        time.sleep(60)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # Transport/configuration exceptions can contain secrets; never traceback.
        print(json.dumps({'status':'BLOCKED','exception_class':type(error).__name__, 'error':ads_probe.safe_error(error)}))
        sys.exit(1)
