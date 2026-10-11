"""Read-only evidence for the real prospective ledger; no backdated forecasts."""
from datetime import datetime, timezone
import json
import hashlib
from src import config
from src.ingestion.settings import load_env
from src.nationwide.store import Store
from src.nationwide.monitoring import scheduler_health
from src.research.calibration.checkpoint import OUT, write_json


def audit():
    load_env()
    store=Store()
    health=scheduler_health(store)
    with store.cursor() as cur:
        cur.execute('''select f.id,f.protocol_version,f.issued_at,f.target_date,f.station_pk,
            f.cams_aqi,f.corrected_aqi,f.interval,f.model_version,f.git_sha,f.artifact,s.feature_version,
            s.latest_input_available_at,s.feature_cutoff,f.target_end
            from airguard.research_forecast_runs f
            join airguard.feature_snapshots s on s.snapshot_hash=f.feature_snapshot_hash order by f.id''')
        records=[dict(r) for r in cur.fetchall()]
        cur.execute('''select count(*) n,count(distinct f.target_date) verified_days
            from airguard.research_forecast_verifications v
            join airguard.research_forecast_runs f on f.id=v.forecast_run_id
            join airguard.station_daily_targets t on t.target_id=v.target_id
            where t.station_pk=f.station_pk and t.target_date=f.target_date''')
        verification=dict(cur.fetchone())
        cur.execute('''select count(*) mismatches from airguard.research_forecast_verifications v
            join airguard.research_forecast_runs f on f.id=v.forecast_run_id
            join airguard.station_daily_targets t on t.target_id=v.target_id
            where t.station_pk is distinct from f.station_pk or t.target_date<>f.target_date''')
        mismatches=cur.fetchone()['mismatches']
        cur.execute("""select tgname from pg_trigger where tgrelid='airguard.research_forecast_runs'::regclass
            and not tgisinternal""")
        triggers=[r['tgname'] for r in cur.fetchall()]
    ledger=[]
    missing_git=0
    for row in records:
        artifact=row.pop('artifact')
        artifact_hash=hashlib.sha256(json.dumps(artifact,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
        row['artifact_sha256']=artifact_hash
        row['git_sha']=row.get('git_sha') or artifact.get('git_sha') or 'NOT_RECORDED_AT_ISSUANCE'
        missing_git+=row['git_sha']=='NOT_RECORDED_AT_ISSUANCE'
        row['raw_model_version']=row['model_version'] or 'RAW_CAMS_UPSTREAM_VERSION_NOT_EXPOSED'
        ledger.append(row)
        # Freeze an audit of each existing artifact; never mutate the issued row.
        path=config.PROJECT_ROOT/'data/research/prospective'/f"{row['id']}_{artifact_hash}.json"
        if not path.exists():
            write_json(path,{**row,'artifact':artifact})
    now=datetime.now(timezone.utc)
    elapsed=(now-min(r['issued_at'] for r in records)).total_seconds()/86400 if records else 0
    value={'generated_at':now.isoformat(),'read_only':True,'stream':'A_PROSPECTIVE_OPERATIONAL',
           'health':health,'forecasts':len(records),'issued_target_days':len({r['target_date'] for r in records}),
           'verified_days':verification['verified_days'],'verification_records':verification['n'],
           'elapsed_real_days':elapsed,'30_day_track_record_complete':verification['verified_days']>=30 and elapsed>=30,
           'verification_pairing_mismatches':mismatches,'input_availability_violations':sum(r['latest_input_available_at']>r['feature_cutoff'] for r in records),
           'immutability_triggers':triggers,'historical_forecasts_missing_git_sha':missing_git,
           'station_bound_forecasts':sum(r['station_pk'] is not None for r in records),
           'outcomes_due':sum(r['target_end']<now for r in records),
           'ledger':ledger,'correction_deployed':False,
           'metadata_gap':'Existing production issuance artifacts lack git SHA; source fix requires a later authorized production release. Historical SHA will not be invented.' if missing_git else None}
    write_json(OUT/'prospective_audit.json',value)
    return value


if __name__=='__main__':
    value=audit()
    print(json.dumps({k:value[k] for k in ('forecasts','issued_target_days','verified_days','elapsed_real_days','outcomes_due','station_bound_forecasts','historical_forecasts_missing_git_sha','input_availability_violations')},indent=2))
