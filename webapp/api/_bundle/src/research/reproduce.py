"""Cross-platform evidence entry point. Missing evidence is PENDING, never a score.

python -m src.research.reproduce data|features|backtest|results|figures|paper|test
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from src import config
from src.nationwide.store import Store, digest
from src.ingestion.settings import load_env
from src.research.study_protocol import STUDY,STUDY_HASH

ROOT=config.PROJECT_ROOT
REQUIRED_RESULTS=('backtest_main','backtest_spatial','ablation','bias_atlas','uncertainty','advisory_tradeoff',
    'hai_v2','hai_sensitivity','clusters_v2','events_deweathered','population_exposure')


def write(name, value):
    p=ROOT/'results'/f'{name}.json';p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str,allow_nan=False),encoding='utf-8')


def inputs():
    from src.research.pipeline import dataset
    from src.research.storage import ResearchStore
    return dataset(ResearchStore())


def data():
    from src.qa.hourly import audit
    store=Store()
    with store.cursor() as c:
        c.execute("select record_key,station_pk,source_type,pollutant,normalized_value,normalized_unit,valid_at,fetched_at,provenance from airguard.environmental_records where source_type='measured' order by station_pk,valid_at,record_key limit 500001")
        rows=[dict(x) for x in c.fetchall()]
        if len(rows)>500000:raise ValueError('Explicit bounded export required before larger research QA')
        c.execute('select source_id,count(*) stations from airguard.stations group by source_id')
        station_registry=[dict(x) for x in c.fetchall()]
    qa=audit(rows);qa.update(generated_at=datetime.now(timezone.utc).isoformat(),input_hash=digest(rows),source='Supabase measured environmental records; not a CPCB census')
    write('qa_summary',qa)
    frame,manifest=inputs()
    complete={}
    for day in qa['daily_completeness']:
        if day['complete']:complete.setdefault((day['station_pk'],day['date']),set()).add(day['pollutant'])
    valid={}
    for (station,day),pollutants in complete.items():
        if len(pollutants)>=3 and {'PM2.5','PM10'} & pollutants: valid.setdefault(station,set()).add(day)
    one_year=sum(len(days)>=365 for days in valid.values())
    coverage={'generated_at':datetime.now(timezone.utc).isoformat(),'study_protocol':STUDY['protocol_version'],'study_hash':STUDY_HASH,
        'collection_manifest':manifest,'station_registry_by_source':station_registry,'measured_rows_audited':len(rows),
        'stations_with_365_complete_candidate_days':one_year,'eligible_paired_rows':len(frame),
        'hourly_input_hash':qa['input_hash'],'data_version':digest([manifest['data_version'],qa['input_hash']]),
        'status':'PENDING_MATCHED_ARCHIVE_AND_STATION_TARGETS','accepted':False,
        'notice':'Candidate 16-hour coverage is not a valid gas-window or daily AQI target. Full central target construction and matching genuine issue-time forecast inputs remain required.',
        'archive_experiment':'PENDING — ADS credential/terms required'}
    write('data_coverage',coverage)
    private=ROOT/'data/interim/qa_measured_export.json';private.parent.mkdir(parents=True,exist_ok=True)
    private.write_text(json.dumps(rows,default=str,allow_nan=False),encoding='utf-8')
    return coverage


def features():
    frame,manifest=inputs()
    payload={'generated_at':datetime.now(timezone.utc).isoformat(),'status':'AVAILABLE' if len(frame) else 'PENDING_MATCHED_ISSUE_TIME_PAIRS',
        'collection_protocol':manifest['protocol_version'],'analysis_protocol':STUDY['protocol_version'],
        'study_hash':STUDY_HASH,'feature_columns':list(frame.columns),'paired_rows':len(frame),'manifest':manifest}
    write('issue_time_features',payload);return payload


def backtest():
    from src.research.evaluation import evaluate,folds
    frame,manifest=inputs()
    eligible=False
    if len(frame):
        support=frame.groupby('station_pk').target_date.nunique()
        eligible=int((support>=365).sum())>=STUDY['minimum_stations'] and bool(folds(frame,protocol=STUDY))
    if not eligible:
        for name in ('backtest_main','backtest_spatial','ablation','bias_atlas','uncertainty','advisory_tradeoff'):
            write(name,{'status':'PENDING','accepted':False,'metrics':None,'n':len(frame),'study_hash':STUDY_HASH,
                'data_version':manifest['data_version'],'reason':'Insufficient genuine issue-time station pairs for preregistered 365/30/30 and locked 90-day temporal/spatial evaluation.'})
        return {'status':'PENDING','n':len(frame),'trained_models':0,'accepted':False}
    # A final test lock is fixed before the evaluator reads final outcomes.
    identity=digest([manifest['data_version'],STUDY_HASH,source_hash()])
    lock=ROOT/'results/research_v2/final_test_lock.json';lock.parent.mkdir(parents=True,exist_ok=True)
    if lock.exists() and json.loads(lock.read_text(encoding='utf-8'))['identity']!=identity:
        raise ValueError('Final test already locked for other data/code; a new preregistration is required')
    if not lock.exists():lock.write_text(json.dumps({'identity':identity,'study_hash':STUDY_HASH,'data_version':manifest['data_version'],'locked_at':datetime.now(timezone.utc).isoformat()},indent=2),encoding='utf-8')
    experiment=evaluate(frame,protocol=STUDY)
    # This existing evaluator is direct-AQI/residual CQR. It does not implement
    # all pollutant MOS/EnbPI/region/bias experiments; never pass those gates.
    write('backtest_main',{**experiment,'study_hash':STUDY_HASH,'data_version':manifest['data_version'],
          'accepted':False,'remaining':['pollutant MOS','region holdouts','formal Holm comparisons','EnbPI']})
    write('backtest_spatial',{'status':'PARTIAL','accepted':False,'city_station':experiment.get('spatial'),'region_coastal':None})
    return {'status':experiment['status'],'accepted':False,'n':len(frame)}


def source_hash():
    paths=[p for p in (ROOT/'src').rglob('*') if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts and p.name!='readiness.json']
    return digest([(p.relative_to(ROOT).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(paths)])


def results():
    coverage=data();features();backtest()
    for name in ('hai_v2','hai_sensitivity','clusters_v2','events_deweathered','population_exposure'):
        write(name,{'status':'PENDING','accepted':False,'metrics':None,'study_hash':STUDY_HASH,
            'reason':{'hai_v2':'Verified coefficients/exposure definitions and human evidence review required.',
                'hai_sensitivity':'Evidence-grounded coefficients and matched pollutant exposure data required.',
                'clusters_v2':'Versioned coverage-gated station/compositional features and stability experiments required.',
                'events_deweathered':'Retrospective ERA5/event coverage and preregistered analysis required; not forecast input.',
                'population_exposure':'Licensed versioned population counts and forecast-cell intersection required.'}[name]})
    artifacts={name:{'path':f'results/{name}.json','sha256':hashlib.sha256((ROOT/'results'/f'{name}.json').read_bytes()).hexdigest()} for name in REQUIRED_RESULTS}
    evidence={'generated_at':datetime.now(timezone.utc).isoformat(),'status':'COLLECTING_NOT_PAPER_READY','study_protocol':STUDY,
        'source_hash':source_hash(),'data_version':coverage['data_version'],'artifacts':artifacts,
        'paper_submittable':False,'all_phases_accepted':False,'pending':'Real matched archive/station data, verified HAI evidence, human review and elapsed prospective outcomes.'}
    write('evidence_index',evidence);return evidence


def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    coverage=json.loads((ROOT/'results/data_coverage.json').read_text(encoding='utf-8'))
    figures=ROOT/'paper/figures';figures.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(figsize=(3.4,2.4));values=[coverage['measured_rows_audited'],coverage['eligible_paired_rows']]
    ax.bar(['Measured hourly\nrecords audited','Eligible issue-time\nforecast/target pairs'],values,color=['#0072b2','#e69f00'])
    ax.set(ylabel='Actual records',title='Available evidence, not forecast skill');ax.tick_params(labelsize=8)
    for i,v in enumerate(values):ax.text(i,v,str(v),ha='center',va='bottom',fontsize=8)
    fig.tight_layout();fig.savefig(figures/'evidence_coverage.pdf');plt.close(fig)
    write('figures',{'status':'PARTIAL','generated':['paper/figures/evidence_coverage.pdf'],
        'input':'results/data_coverage.json','empirical_skill_figures':'PENDING; no invented prediction plots'})
    return {'status':'PARTIAL','generated':1}


def paper():
    index=json.loads((ROOT/'results/evidence_index.json').read_text(encoding='utf-8'))
    if not index['paper_submittable']:
        print('Paper submission build blocked: research evidence, bibliography/author review and CFP are pending. Draft source is preserved.')
        return {'status':'PENDING_RESEARCH_AND_HUMAN_REVIEW','accepted':False}
    raise ValueError('Conference compiler/CFP must be explicitly configured before submission build')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['data','features','backtest','results','figures','paper','test','register']);args=parser.parse_args()
    load_env()
    if args.stage=='register':
        from src.research.study_protocol import register
        register(Store());value={'registered':STUDY['protocol_version'],'definition_hash':STUDY_HASH,'live_collection_protocol_unchanged':True}
    elif args.stage=='test':
        result=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT)
        if result.returncode:raise SystemExit(result.returncode)
        npm=shutil.which('npm.cmd') or shutil.which('npm')
        if not npm:raise SystemExit('Node/npm is required for frontend tests')
        # Use the native npm launcher; no shell-built credential commands.
        for stage in ('test','typecheck','lint'):
            result=subprocess.run([npm,'run',stage],cwd=ROOT/'webapp')
            if result.returncode:raise SystemExit(result.returncode)
        value={'status':'PASS'}
    else:value=globals()[args.stage]()
    print(json.dumps({k:v for k,v in value.items() if k in ('status','n','accepted','registered','definition_hash','live_collection_protocol_unchanged','paper_submittable','all_phases_accepted','generated')},default=str))
    if args.stage=='paper' and value.get('accepted') is False:raise SystemExit(2)


if __name__=='__main__':main()
