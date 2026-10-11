"""Read-only production evidence. Never serializes credentials or cron commands."""
from datetime import datetime, timezone
import json
from pathlib import Path
from src.ingestion.settings import load_env, secret
from src.nationwide.store import Store

ROOT = Path(__file__).resolve().parents[1]


def collect():
    load_env()
    report = {'generated_at': datetime.now(timezone.utc).isoformat(),
              'database_url_available': bool(secret('DATABASE_URL')), 'read_only': True}
    store = Store()
    with store.cursor() as cur:
        cur.execute('select 1')
        report['connectivity'] = 'CONNECTED' if cur.fetchone() else 'FAILED'
        cur.execute("select tablename,rowsecurity from pg_tables where schemaname='airguard' order by tablename")
        report['tables'] = [dict(x) for x in cur.fetchall()]
        counts = {}
        for table in ('stations', 'air_quality_observations', 'weather_forecasts', 'fire_detections',
                      'environmental_records', 'provider_snapshots', 'feature_snapshots',
                      'forecast_runs', 'forecast_verifications', 'station_daily_targets',
                      'research_forecast_runs', 'research_forecast_verifications',
                      'model_versions', 'training_runs'):
            # Fixed table allow-list; identifiers never originate in request data.
            cur.execute('select count(*) n from airguard.' + table)
            counts[table] = cur.fetchone()['n']
        report['counts'] = counts
        cur.execute("select provider,source_type,count(*) n,count(distinct station_pk) stations,min(valid_at) first_valid,max(valid_at) last_valid,max(fetched_at) last_retrieved from airguard.environmental_records group by provider,source_type order by provider,source_type")
        report['source_coverage'] = [dict(x) for x in cur.fetchall()]
        cur.execute("select count(*) n from (select record_key from airguard.environmental_records group by record_key having count(*)>1) d")
        report['duplicate_record_keys'] = cur.fetchone()['n']
        cur.execute("select count(*) n from airguard.environmental_records where provenance is null or provenance='{}'::jsonb or fetched_at is null")
        report['missing_record_provenance'] = cur.fetchone()['n']
        cur.execute("select jobid,jobname,schedule,active from cron.job where jobname like 'airguard-%' order by jobname")
        report['schedules'] = [dict(x) for x in cur.fetchall()]
        cur.execute("select j.jobname,r.status,r.start_time,r.end_time from cron.job_run_details r join cron.job j using(jobid) where j.jobname like 'airguard-%' order by r.start_time desc limit 20")
        report['cron_dispatches'] = [dict(x) for x in cur.fetchall()]
        cur.execute("select provider,operation,status,created_at,record_count,error_class from airguard.provider_events order by created_at desc limit 20")
        report['provider_events'] = [dict(x) for x in cur.fetchall()]
        cur.execute('select filename,applied_at from airguard.schema_migrations order by filename')
        report['migrations'] = [dict(x) for x in cur.fetchall()]
    report['all_airguard_tables_rls'] = all(t['rowsecurity'] for t in report['tables'])
    path = ROOT / 'results/release/database_audit.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    return report


if __name__ == '__main__':
    evidence = collect()
    print(json.dumps({k: evidence[k] for k in ('connectivity', 'database_url_available', 'counts',
        'duplicate_record_keys', 'missing_record_provenance', 'all_airguard_tables_rls')}, indent=2))
