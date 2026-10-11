"""Read-only health: cron dispatch success is not forecast issuance success."""
from datetime import datetime, timedelta, timezone
from src.nationwide.aqi import IST
from src.research.protocol import VERSION, cutoff_for


def classify(now, registered_at, schedules, latest_issue, latest_event):
    now=now.astimezone(timezone.utc);day=now.astimezone(IST).date()
    due=cutoff_for(day)
    if now < due: due-=timedelta(days=1)
    active=any(s['jobname']=='airguard-research-issue' and s['active'] for s in schedules)
    if not active: state='SCHEDULE_INACTIVE'
    elif registered_at is None or registered_at > due: state='AWAITING_FIRST_CUTOFF'
    elif now < due+timedelta(minutes=10): state='ISSUANCE_WINDOW_OPEN'
    elif latest_issue is not None and latest_issue >= due: state='ISSUED'
    elif latest_event is not None and latest_event['created_at'] >= due: state='ATTEMPTED_NO_ELIGIBLE_FORECASTS'
    else: state='MISSED_ISSUANCE'
    return {'state':state,'expected_cutoff':due.isoformat(),'next_cutoff':(due+timedelta(days=1)).isoformat(),
            'alert_required':state in ('MISSED_ISSUANCE','SCHEDULE_INACTIVE','ATTEMPTED_NO_ELIGIBLE_FORECASTS'),
            'outbound_alerts':'NOT_CONFIGURED — requires opted-in channel/recipient; no messages sent'}


def scheduler_health(store, now=None):
    now=now or datetime.now(timezone.utc)
    with store.cursor() as c:
        c.execute('select created_at from airguard.research_protocols where protocol_version=%s',(VERSION,))
        row=c.fetchone();registered=row['created_at'] if row else None
        c.execute("select jobname,schedule,active from cron.job where jobname like 'airguard-%' order by jobname")
        schedules=[dict(r) for r in c.fetchall()]
        c.execute('select max(issued_at) latest,count(*) forecasts from airguard.research_forecast_runs where protocol_version=%s',(VERSION,))
        issued=dict(c.fetchone())
        c.execute("select status,created_at,record_count,error_class from airguard.provider_events where provider='research' and operation='scheduled_issue' order by created_at desc limit 1")
        event=c.fetchone();event=dict(event) if event else None
        c.execute("select provider,operation,status,created_at,record_count,error_class from airguard.provider_events where provider in ('scheduler','research') order by created_at desc limit 12")
        heartbeat=[dict(r) for r in c.fetchall()]
    health={'ok':True,'generated_at':now.isoformat(),'protocol_version':VERSION,
            'issuance':classify(now,registered,schedules,issued['latest'],event),
            'forecasts':issued['forecasts'],'last_issue':issued['latest'],'last_issue_attempt':event,
            'schedules':schedules,'heartbeats':heartbeat,
            'notice':'Dispatch, retrieval, fixed-time issuance and measured-outcome verification are different events. No forecast is backdated.'}
    # A missed cutoff is unrecoverable, so the alert travels with the health payload
    # and reaches /status even though no outbound channel is authorised to carry it.
    from src.nationwide.alerts import render
    health['alert']=render(health)
    return health
