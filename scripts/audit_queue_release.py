"""Read-only queue and scheduler checks, with no Vault/auth values exported."""
from datetime import datetime, timezone
from pathlib import Path
import json
from src.ingestion.settings import load_env
from src.nationwide.store import Store


def collect():
    load_env()
    report={'generated_at':datetime.now(timezone.utc).isoformat()}
    with Store().cursor() as cur:
        cur.execute("select e.extname,e.extrelocatable,n.nspname from pg_extension e join pg_namespace n on n.oid=e.extnamespace where e.extname='pg_net'")
        report['extension']=dict(cur.fetchone())
        cur.execute("select has_function_privilege('anon','airguard.enqueue_summary(text,double precision,double precision)','execute') anon_queue_execute,has_function_privilege('authenticated','airguard.enqueue_summary(text,double precision,double precision)','execute') authenticated_queue_execute")
        report['permissions']=dict(cur.fetchone())
        cur.execute("select provider,payload->>'status' status,count(*) n from airguard.cache_metadata where provider='summary_queue' group by provider,payload->>'status'")
        report['jobs']=[dict(r) for r in cur.fetchall()]
        cur.execute("select count(*) n, min(issued_at) first_issue,max(issued_at) last_issue from airguard.research_forecast_runs")
        report['prospective_ledger']=dict(cur.fetchone())
    report['advisor_notes']={
        'rls_enabled_no_policy':'Intentional default-deny private server tables. No public data policy is added.',
        'extension_in_public':'pg_net is not relocatable on this project; asynchronous functions use the net schema. Scheduler dispatch functions remain private.',
        'unused_indexes':'Retained pending representative workload; no destructive index removal.'}
    path=Path(__file__).resolve().parents[1]/'results/release/queue_audit.json'
    path.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps(report,default=str))


if __name__=='__main__': collect()
