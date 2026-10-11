"""One reproducible research workflow; absent evidence produces PENDING, never scores.

python -m src.research.pipeline
python -m src.research.pipeline --warm
python -m src.research.pipeline --issue
python -m src.research.pipeline --verify
"""
from __future__ import annotations
import argparse
from datetime import datetime,timedelta,timezone
from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import numpy as np
import pandas as pd
from src import config
from src.research.protocol import PROTOCOL,VERSION,period,daily_target,aware
from src.research.storage import ResearchStore,Json
from src.research.evaluation import evaluate,drift
from src.nationwide.store import digest
from src.ingestion.settings import load_env

OUT=config.RESULTS_DIR/'research'


def write(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x),allow_nan=False),encoding='utf8')


def environment():
    deps={}
    for name in ('numpy','pandas','scikit-learn','lightgbm','xgboost','scipy','psycopg2-binary','requests'):
        try:deps[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:deps[name]='NOT_INSTALLED'
    return {'python':platform.python_version(),'dependencies':deps}


def git_identity():
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=config.PROJECT_ROOT,text=True).strip()
    # Include new/uncommitted source, not only Git HEAD; never hash credentials into a published manifest.
    paths=[]
    for folder in ('src','webapp/app','tests','db','scripts'):
        paths.extend(p for p in (config.PROJECT_ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.tsx','.js','.sql','.json') and '__pycache__' not in p.parts and p.name!='readiness.json')
    return sha,digest([(str(p.relative_to(config.PROJECT_ROOT)),hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(paths)])


def construct_targets(store):
    with store.store.cursor() as c:
        c.execute("select distinct station_pk,(valid_at at time zone 'Asia/Kolkata')::date target_day from airguard.environmental_records where source_type='measured' and valid_at<(date_trunc('day',now() at time zone 'Asia/Kolkata') at time zone 'Asia/Kolkata') order by 1,2")
        days=[dict(r) for r in c.fetchall()]
    report=[]
    for pair in days:
        start,end=period(pair['target_day']);rows=store.measured_rows(pair['station_pk'],start-timedelta(hours=7),end)
        if not rows:continue
        available=max(aware(r['fetched_at']) for r in rows)
        available=max(available,end)
        target=daily_target(rows,pair['target_day'],pair['station_pk'],available);calc=target['calculation']
        if calc['aqi'] is not None:
            with store.store.cursor() as c:
                c.execute('''insert into airguard.station_daily_targets(station_pk,target_date,available_at,methodology_version,target_aqi,qualifier,category,quality_state,evidence)
                    values(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing''',(pair['station_pk'],pair['target_day'],available,PROTOCOL['methodology_version'],calc['aqi'],calc['qualifier'],(calc['category'] or {}).get('label'),calc['status'],Json(target)))
        report.append({'station_pk':pair['station_pk'],'day':str(pair['target_day']),'status':calc['status'],'eligible_regression':target['eligible_regression'],'coverage':calc['coverage']})
    return report


def dataset(store):
    with store.store.cursor() as c:
        c.execute('''select s.snapshot_hash,s.issue_time,s.target_date,s.station_pk,s.features,s.provenance,t.target_aqi,t.available_at target_available_at,
            st.city,st.name station_name from airguard.feature_snapshots s
            join airguard.station_daily_targets t on s.station_pk=t.station_pk and s.target_date=t.target_date and t.methodology_version=%s
            join airguard.stations st on st.station_pk=s.station_pk
            where s.protocol_version=%s and t.quality_state='VALID' and t.qualifier='EXACT' order by s.target_date,s.station_pk,s.issue_time''',
            (PROTOCOL['methodology_version'],VERSION))
        pairs=[dict(r) for r in c.fetchall()]
        c.execute('select source_type,count(*) n,count(distinct station_pk) stations,min(valid_at) first,max(valid_at) last from airguard.environmental_records group by 1');coverage=[dict(r) for r in c.fetchall()]
        c.execute('select count(*) n from airguard.provider_snapshots');snapshot_count=c.fetchone()['n']
        c.execute('select count(*) n from airguard.feature_snapshots');feature_count=c.fetchone()['n']
    unique={}
    for r in pairs:
        if r['provenance']['cams_calculation']['status']!='VALID':continue
        if aware(r['target_available_at'])<=aware(r['issue_time']):raise ValueError('Target already available at issue; not a day-ahead instance')
        if 'B_persistence_aqi' not in r['features']:continue
        target_date=str(r['target_date']);month=int(target_date[5:7]);season='winter' if month in (12,1,2) else 'pre_monsoon' if month in (3,4,5) else 'monsoon' if month in (6,7,8,9) else 'post_monsoon'
        unique.setdefault((r['station_pk'],target_date),{'snapshot_hash':r['snapshot_hash'],'issue_time':str(r['issue_time']),'target_date':target_date,
            'target_available_at':str(r['target_available_at']),'station_pk':r['station_pk'],'city':r['city'] or r['station_name'],
            'target_aqi':r['target_aqi'],'cams_aqi':r['provenance']['cams_aqi'],'month':month,'season':season,**r['features']})
    rows=list(unique.values());frame=pd.DataFrame(rows)
    manifest={'protocol_version':VERSION,'methodology_version':PROTOCOL['methodology_version'],'pairs':len(rows),'candidate_pairs':len(pairs),
        'stations':frame.station_pk.nunique() if len(frame) else 0,'cities':frame.city.nunique() if len(frame) else 0,
        'dates':[frame.target_date.min(),frame.target_date.max()] if len(frame) else [],'coverage':coverage,
        'provider_snapshots':snapshot_count,'feature_snapshots':feature_count,'missingness':frame.isna().mean().to_dict() if len(frame) else {},
        'source':'Issue-time immutable snapshots paired with same-station measured hourly targets; exact CAMS and target AQI required for regression',
        'archive_experiment':'PENDING — ADS credential/terms required','legacy_experiment':'Separate 2015–2020 reported-AQI baseline; not interchangeable with hourly operational target'}
    version=digest({'rows':rows,'coverage':coverage,'provider_snapshots':snapshot_count,'feature_snapshots':feature_count});manifest['data_version']=version
    return frame,manifest


def legacy_audit():
    raw=pd.read_csv(config.RAW_DIR/'station_day.csv');meta=pd.read_csv(config.RAW_DIR/'stations.csv')
    joined=raw.merge(meta[['StationId','City','State']],on='StationId',how='left')
    reg=json.loads((config.RESULTS_DIR/'evaluation_regression.json').read_text(encoding='utf8'))
    metrics=[{'model':x['model'],'test':x['test'],'cv':x.get('cv'),'note':'Legacy city-level feature dataset; not current station forecast evidence'} for x in reg.get('results',[])]
    return {'label':'LEGACY REPORTED DAILY AQI — NOT OPERATIONAL HOURLY TARGETS', 'rows':len(raw),'stations':int(raw.StationId.nunique()),
        'cities':int(joined.City.nunique()),'dates':[str(raw.Date.min()),str(raw.Date.max())], 'reported_AQI_rows':int(raw.AQI.notna().sum()),
        'pollutant_missingness':raw[[x for x in ('PM2.5','PM10','NO2','SO2','CO','O3') if x in raw]].isna().mean().to_dict(),
        'caveats':['Daily concentration aggregates lack hourly gas windows and issue-time availability. Cannot rebuild the locked target protocol.','Existing feature selection/tuning and row-level TimeSeriesSplit require separate date-boundary audit. Lower holdout MAE is not evidence of spatial or modern generalisation.','Prior recent CAMS past-days backtest is exploratory; not archived forecast skill.'],
        'existing_metrics':metrics}


def monitoring(store):
    with store.store.cursor() as c:
        c.execute("select pollutant,normalized_value,valid_at from airguard.environmental_records where source_type='measured'")
        modern=pd.DataFrame([dict(r) for r in c.fetchall()])
        c.execute('select count(*) n from airguard.research_forecast_verifications');n=c.fetchone()['n']
        c.execute("select distinct s.station_pk,s.name,s.latitude,s.longitude from airguard.stations s join airguard.environmental_records r using(station_pk) where r.source_type='measured'")
        station_coverage=[dict(r) for r in c.fetchall()]
    legacy=pd.read_csv(config.RAW_DIR/'city_day.csv');out={}
    for p in ('PM2.5','PM10','NO2','SO2','CO','O3'):
        now=modern[modern.pollutant==p].normalized_value.to_numpy() if len(modern) else []
        out[p]=drift(legacy[p].to_numpy(),now)
    return {'status':'COLLECTING','prospective_verified_pairs':n,'recent_mae':None,'bias':None,'interval_coverage':None,
        'input_drift':out,'station_coverage':station_coverage,'prediction_drift':'INSUFFICIENT_FIXED_TIME_FORECASTS','residual_drift':'INSUFFICIENT_VERIFIED_OUTCOMES',
        'retraining_recommendation':'COLLECT_MEASURED_STATION_PAIRS','automatic_retraining':False,
        'comparability_notice':'Historical city daily means vs sparse modern station hourly records; descriptive acquisition audit, not like-for-like change estimation.'}


def generate_figures(manifest,experiment,monitor):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=config.REPORTS_DIR/'research_figures';folder.mkdir(parents=True,exist_ok=True)
    outputs=[]
    def save(fig,name):
        for ext in ('png','pdf'):fig.savefig(folder/(name+'.'+ext),dpi=300,bbox_inches='tight')
        plt.close(fig);outputs.append(name)
    fig,ax=plt.subplots(figsize=(12,3));ax.axis('off')
    nodes=[((0,1),'Issued CAMS\n+ forecast weather'),((0,-1),'Measured history\nknown by 20:00 IST'),((2,0),'Frozen issue-time\nfeatures'),((4,0),'Offline correction\n+ calibration'),((6,0),'Immutable forecast\nCAMS or supported correction'),((8,0),'Next-day measured\nverification')]
    for (x,y),label in nodes:
        ax.text(x,y,label,ha='center',va='center',bbox={'boxstyle':'round,pad=.5','facecolor':'#eef5ef','edgecolor':'#426447'},fontsize=8)
    for y in (-1,1):ax.annotate('',xy=(1.15,0),xytext=(.85,y),arrowprops={'arrowstyle':'->'})
    for x in (2,4,6):ax.annotate('',xy=(x+1.1,0),xytext=(x+.9,0),arrowprops={'arrowstyle':'->'})
    ax.text(4,-1.5,'Nationwide mode retains raw CAMS; correction requires validated support.',ha='center',fontsize=8)
    ax.set_xlim(-1.1,9.1);ax.set_ylim(-2,2);ax.set_title('AirGuard research architecture — correction remains experimental');save(fig,'01_architecture')
    fig,ax=plt.subplots(figsize=(9,2));ax.plot([-10,0,240,1680],[0,0,0,0],'o-',color='#426447')
    for x,label in [(-10,'19:50 prefetch'),(0,'20:00 cutoff'),(240,'Target starts\n00:00 IST'),(1680,'Target ends\nnext 00:00')]:ax.annotate(label,(x,0),xytext=(0,15 if x!=0 else -35),textcoords='offset points',ha='center')
    ax.set_yticks([]);ax.set_xlabel('Minutes from forecast issuance');save(fig,'02_operational_timeline')
    if monitor.get('station_coverage'):
        station_frame=pd.DataFrame(monitor['station_coverage']);fig,ax=plt.subplots(figsize=(6,6))
        ax.scatter(station_frame.longitude,station_frame.latitude,s=30,color='#426447')
        ax.set(xlim=(68,98),ylim=(6,38),xlabel='Longitude °E',ylabel='Latitude °N',title=f"Stored measured-data stations (n={len(station_frame)})")
        ax.text(.02,.02,'Coordinate coverage plot; no political boundary.\nStation presence does not establish daily AQI sufficiency.',transform=ax.transAxes,fontsize=8)
        save(fig,'03_coverage_map')
    usable=[(p,r) for p,r in monitor['input_drift'].items() if r.get('psi') is not None]
    if usable:
        fig,ax=plt.subplots(figsize=(8,4));ax.bar([p for p,r in usable],[r['psi'] for p,r in usable],color='#426447')
        ax.set(ylabel='Descriptive PSI',title='Legacy daily city means vs sparse modern hourly station records')
        ax.text(.01,-.23,'Acquisition audit with mismatched aggregation/station/season; not causal drift evidence.',transform=ax.transAxes,fontsize=8)
        save(fig,'17_drift')
    if experiment.get('predictions'):
        df=pd.DataFrame(experiment['predictions'])
        for key,name in [('cams_aqi','04_cams_vs_measured'),('airguard_aqi','05_airguard_vs_measured')]:
            fig,ax=plt.subplots();ax.scatter(df.measured_aqi,df[key],s=8,alpha=.5);ax.plot([0,400],[0,400],'k--');ax.set(xlabel='Measured CPCB-style AQI',ylabel=key,title='Untouched final test');save(fig,name)
        fig,ax=plt.subplots();ax.hist(df.airguard_aqi-df.measured_aqi,bins=25);ax.set(xlabel='Predicted minus measured AQI',ylabel='n');save(fig,'06_residual_distribution')
    requested=['01_architecture','02_operational_timeline','03_coverage_map','04_cams_vs_measured','05_airguard_vs_measured','06_residual_distribution','07_baselines','08_rolling_folds','09_leave_city_out','10_category_error','11_severe','12_ablation','13_interval_calibration','14_width_vs_coverage','15_advisory_tradeoffs','16_prospective_track_record','17_drift']
    return {'generated':outputs,'pending':[name for name in requested if name not in outputs],'note':'No plots of fabricated predictions; empirical plots await eligible issue-time pairs.'}


def run():
    load_env();OUT.mkdir(parents=True,exist_ok=True);started=datetime.now(timezone.utc)
    store=ResearchStore();store.register_protocol();targets=construct_targets(store);frame,manifest=dataset(store)
    legacy=legacy_audit()
    from src.research.legacy_cv_audit import audit
    legacy['cv_audit']=audit();write(OUT/'legacy_cv_audit.json',legacy['cv_audit'])
    experiment=evaluate(frame) if len(frame) else {'status':'INSUFFICIENT_ISSUE_TIME_PAIRS','n':0,'folds':[],'metrics':None}
    monitor=monitoring(store);figures=generate_figures(manifest,experiment,monitor);sha,tree=git_identity()
    identity=digest([manifest['data_version'],tree,VERSION,PROTOCOL['seed']]);completed=datetime.now(timezone.utc)
    with store.store.cursor() as c:
        c.execute('insert into airguard.dataset_versions(data_version,protocol_version,manifest) values(%s,%s,%s) on conflict do nothing',(manifest['data_version'],VERSION,Json(manifest)))
        c.execute('''insert into airguard.experiment_registry(experiment_id,protocol_version,data_version,git_sha,dirty_tree_hash,seed,definition,environment,status,artifacts,started_at,completed_at)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing''',(identity,VERSION,manifest['data_version'],sha,tree,42,Json({'protocol':PROTOCOL,'evaluations':experiment}),Json(environment()),experiment['status'],Json({'path':'results/research'}),started,completed))
    for name,value in [('dataset',manifest),('targets',targets),('experiments',experiment),('legacy_audit',legacy),('monitoring',monitor),('figures',figures)]:write(OUT/(name+'.json'),value)
    if len(frame):frame.to_csv(OUT/'dataset.csv',index=False)
    evaluated=experiment['status']=='EVALUATED_NOT_DEPLOYED'
    checks={'literature_review_complete':False,'research_question_locked':True,'protocol_locked':True,'issue_time_dataset_validated':bool(len(frame)),
        'cpcb_method_verified':True,'baseline_complete':evaluated,'rolling_origin_complete':evaluated,'spatial_validation_complete':bool(experiment.get('spatial')),
        'ablation_complete':False,'uncertainty_complete':bool(experiment.get('uncertainty')),'extreme_event_analysis_complete':False,
        'advisory_evaluation_complete':bool(experiment.get('advisory')),'prospective_logging_active':False,'30_day_track_record_complete':False,
        'statistical_comparison_complete':bool((experiment.get('comparison') or {}).get('ci95')),'reproducibility_passed':False,'security_passed':False}
    readiness={'status':'COLLECTING_NOT_RESEARCH_READY','checks':checks,'passed':sum(checks.values()),'total':len(checks),
        'evidence':{'experiment_id':identity,'dataset_version':manifest['data_version'],'git_sha':sha,'working_tree_hash':tree,'protocol_hash':digest(PROTOCOL)},
        'pending_archive':'PENDING — ADS credential/terms required','claims_supported':['Nationwide raw CAMS estimate','Issue-time guarded research framework','Immutable on-demand baseline forecast collection'],
        'claims_not_supported':['AirGuard improves CAMS','Calibrated operational intervals','Controlled vulnerable-cohort under-warning','Station correction generalises nationwide'],
        'generated_at':completed.isoformat()}
    write(OUT/'research_readiness.json',readiness);write(Path(__file__).with_name('readiness.json'),readiness)
    write(config.PROJECT_ROOT/'webapp/public/data/research_readiness.json',readiness)
    from src.research.reporting import generate
    generate(manifest,experiment,legacy,monitor,readiness,figures)
    print(json.dumps({'status':experiment['status'],'eligible_pairs':len(frame),'target_days_audited':len(targets),'readiness':f"{sum(checks.values())}/{len(checks)}",'artifacts':str(OUT)}))
    return readiness


def main():
    load_env()
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--warm',action='store_true');parser.add_argument('--issue',action='store_true');parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    if args.warm or args.issue or args.verify:
        from src.nationwide.service import Service
        from src.nationwide.aqi import IST
        service=Service();store=ResearchStore(service.store);store.register_protocol()
        locations=service.store.popular(12)
        if args.warm:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda x:{'location':x['key'],'ok':service.summary(x['lat'],x['lon'],x['name'],x.get('region'),force=True)['ok']},locations))
        elif args.issue:results=[store.capture(x,datetime.now(IST).date()) for x in locations]
        else:results=store.verify(service)
        print(json.dumps(results,default=str));return
    run()


if __name__=='__main__':main()
