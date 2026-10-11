"""Enable approved AirGuard jobs and verify the Vault-authenticated dispatch."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import requests
from src.ingestion.settings import load_env, secret, redact, SECRET_NAMES
from src.nationwide.store import Store

PRODUCTION = 'https://webapp-phi-taupe.vercel.app'
JOBS = {
    'airguard-nationwide-refresh': '17 * * * *',
    'airguard-research-prefetch': '20 14 * * *',
    'airguard-research-issue': '30 14 * * *',
    'airguard-research-verify': '30 1 * * *',
}


def main():
    load_env()
    # No bypass headers: Supabase must reach the public production domain.
    health = requests.get(PRODUCTION+'/api/health', timeout=30)
    assert health.status_code == 200 and health.json()['database']=='CONNECTED'
    research = requests.get(PRODUCTION+'/api/research/status', timeout=30)
    assert research.status_code == 200 and research.json()['protocol']['protocol_version']=='airguard-dayahead-20ist-v1'
    store = Store()
    with store.cursor() as c:
        c.execute("select count(*)=1 and bool_and(decrypted_secret=%s) matches from vault.decrypted_secrets where name='airguard_cron_secret'", (secret('CRON_SECRET'),))
        assert c.fetchone()['matches'], 'Vault scheduler credential does not match the configured credential'
        c.execute("select jobid,jobname,schedule,command,active from cron.job where jobname=any(%s)", (list(JOBS),))
        rows = [dict(r) for r in c.fetchall()]
        assert len(rows)==len(JOBS)
        assert all(r['schedule']==JOBS[r['jobname']] and r['command']=='select airguard.enqueue_refresh();' for r in rows)
        for row in rows: c.execute('select cron.alter_job(%s,active:=true)', (row['jobid'],))
        c.execute('select airguard.enqueue_refresh() request_id')
        request_id = c.fetchone()['request_id']
    print(json.dumps({'phase':'ACTIVATED','jobs':len(rows),'supabase_http_request_id':request_id}), flush=True)
    deadline = time.monotonic()+330
    response = None
    while time.monotonic()<deadline:
        with store.cursor() as c:
            c.execute('select id,status_code,timed_out,error_msg,content,created from net._http_response where id=%s',(request_id,))
            row = c.fetchone()
        if row:
            response = dict(row)
            break
        time.sleep(3)
    content = None
    if response and response['status_code']==200 and not response['timed_out']:
        try:
            content = json.loads(response['content'])
        except (TypeError, ValueError):
            pass
    valid = content and content.get('ok') and content.get('status') in ('SUCCESS','PARTIAL','SKIPPED_OVERLAP')
    if not valid:
        with store.cursor() as c:
            for row in rows: c.execute('select cron.alter_job(%s,active:=false)', (row['jobid'],))
        message = redact(response.get('error_msg') or f"HTTP {response.get('status_code')}" ) if response else 'No Supabase HTTP response before deadline'
        raise RuntimeError('Cloud validation failed; jobs disabled: '+message)
    with store.cursor() as c:
        c.execute("select jobid,jobname,schedule,active from cron.job where jobname=any(%s) order by jobname",(list(JOBS),))
        schedules = [dict(r) for r in c.fetchall()]
        c.execute("select j.jobname,r.status,r.start_time,r.end_time from cron.job_run_details r join cron.job j using(jobid) where j.jobname=any(%s) order by r.start_time desc limit 8", (list(JOBS),))
        history = [dict(r) for r in c.fetchall()]
    assert all(r['active'] for r in schedules)
    report = {'generated_at':datetime.now(timezone.utc).isoformat(),'production_url':PRODUCTION,'schedules':schedules,
        'dispatch':{'request_id':request_id,'http_status':200,'timed_out':False,'refresh_status':content['status'],'response':content},
        'schedule_run_history':history,'verification_notice':'The exact Vault-authenticated enqueue function was invoked from Supabase; future calendar triggers are not backdated or counted as completed runs.',
        'fixed_issuance_window_ist':'20:00–20:10','prefetch_ist':'19:50','verification_ist':'07:00','hourly_refresh_ist':'Every hour at minute 47'}
    body = json.dumps(report,indent=2,default=str)
    assert all(not secret(name) or secret(name) not in body for name in SECRET_NAMES)
    destination = Path(__file__).resolve().parents[1]/'results/research/cloud_ingestion_activation.json'
    destination.write_text(body,encoding='utf-8')
    print(json.dumps({'phase':'VERIFIED','active_jobs':len(schedules),'supabase_http_status':200,'refresh_status':content['status']}), flush=True)


if __name__ == '__main__': main()
