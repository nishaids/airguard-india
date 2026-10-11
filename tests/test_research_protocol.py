"""Constructed data here exercises implementation; never contributes paper metrics."""
from datetime import datetime,timedelta,timezone
from copy import deepcopy
from contextlib import contextmanager
import json
import numpy as np
import pandas as pd
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from src.research.protocol import aware,check_inputs,build_features,cutoff_for,period,daily_target,VERSION,PROTOCOL
from src.research.evaluation import folds,scores,paired_block_bootstrap,warning_scores,select_policy,correction,drift,cqr
from src.research.serving import choose_forecast
from src.research.storage import ResearchStore,Json
from src.ingestion.db import connect

CUTOFF=cutoff_for('2026-10-10')


def model_input(kind='modelled_forecast'):
    start,end=period('2026-10-11')
    rows=[{'time':(start-timedelta(hours=7)+timedelta(hours=i)).isoformat(),'PM2.5':40,'PM10':60,'NO2':30,'CO':.5,'O3':45,'temperature_2m':25} for i in range(31)]
    return {'source_type':kind,'model':'cams_global' if kind=='modelled_forecast' else 'gfs_seamless','rows':rows,
            'available_at':(CUTOFF-timedelta(minutes=10)).isoformat(),'retrieved_at':(CUTOFF-timedelta(minutes=10)).isoformat(),'reference_time':None}


def observations(start,hours=48,station=7):
    return [{'source_type':'measured','station_pk':station,'valid_at':(start+timedelta(hours=i)).isoformat(),
        'valid_end':(start+timedelta(hours=i+1)).isoformat(),'pollutant':p,'normalized_value':v,'normalized_unit':'ug/m3',
        'quality_state':'VALID','available_at':CUTOFF.isoformat(),'retrieved_at':CUTOFF.isoformat(),'fetched_at':CUTOFF.isoformat(),
        'record_key':f'{i}-{p}'} for i in range(hours) for p,v in [('PM2.5',40),('PM10',60),('NO2',30)]]


@pytest.mark.parametrize('field',['available_at','retrieved_at','reference_time'])
def test_deliberate_future_forecast_rejected(field):
    value=model_input();value[field]=(CUTOFF+timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError,match='leakage'):check_inputs([value],CUTOFF)


def test_future_observed_bin_rejected_even_if_retrieval_claims_earlier():
    value=observations(CUTOFF)[0]
    with pytest.raises(ValueError,match='future observation'):check_inputs([value],CUTOFF)


def test_naive_timestamp_rejected():
    with pytest.raises(ValueError,match='Timezone'):aware('2026-10-10T20:00:00')


def test_actual_tomorrow_weather_forbidden_reanalysis_forbidden():
    value=model_input('reanalysis')
    with pytest.raises(ValueError,match='Unapproved'):check_inputs([value],CUTOFF)


def test_forecast_future_valid_times_allowed_if_issued_before_cutoff():
    result=build_features(model_input(),model_input('weather_forecast'),observations(CUTOFF-timedelta(hours=48)), '2026-10-10',13.1,80.1,7)
    assert result['cams_aqi']==67 and result['features']['C_temperature_2m_mean']==25
    assert result['features']['B_persistence_aqi']==67
    assert result['target_date']=='2026-10-11'
    assert result['protocol_version']==VERSION


def test_stale_baseline_rejected():
    value=model_input();value['available_at']=value['retrieved_at']=(CUTOFF-timedelta(hours=4)).isoformat()
    with pytest.raises(ValueError,match='Stale'):build_features(value,None,[],'2026-10-10',13,80)


def test_measured_hour_duplicates_do_not_inflate_features():
    rows=observations(CUTOFF-timedelta(hours=24),24)
    result=build_features(model_input(),None,rows*2,'2026-10-10',13,80,7)
    assert result['features']['B_PM2.5_hours24']==24


def test_target_station_identity_and_completeness():
    start,end=period('2026-10-09');rows=observations(start,24)
    target=daily_target(rows,'2026-10-09',7,CUTOFF)
    assert target['eligible_regression'] and target['calculation']['aqi']==67
    with pytest.raises(ValueError,match='exactly one'):daily_target(rows,'2026-10-09',8,CUTOFF)
    invalid=deepcopy(rows);invalid[0]['source_type']='modelled_forecast'
    with pytest.raises(ValueError,match='measured'):daily_target(invalid,'2026-10-09',7,CUTOFF)
    assert not daily_target(rows[:30],'2026-10-09',7,CUTOFF)['eligible_regression']
    with pytest.raises(ValueError,match='complete'):daily_target(rows,'2026-10-09',7,start)


def test_severe_censored_target_not_exact_mae_training():
    start,end=period('2026-10-09');rows=observations(start,24)
    for r in rows:
        if r['pollutant']=='PM2.5':r['normalized_value']=500
    target=daily_target(rows,'2026-10-09',7,CUTOFF)
    assert target['calculation']['qualifier']=='LOWER_BOUND' and not target['eligible_regression']


def frame(days=240):
    rows=[]
    for i in range(days):
        day=(datetime(2025,1,1)+timedelta(days=i)).date();issue=cutoff_for(day)-timedelta(days=1)
        for station in (1,2):
            rows.append({'target_date':str(day),'issue_time':issue.isoformat(),'target_available_at':(period(day)[1]+timedelta(hours=6)).isoformat(),
                'station_pk':station,'city':'A' if station==1 else 'B','season':'winter','month':day.month,'target_aqi':float(70+i%10),
                'cams_aqi':float(80+i%10),'B_persistence_aqi':70.,'A_cams_aqi':float(80+i%10),'C_temp':25.,'D_weekday':day.weekday(),'E_lat':float(station)})
    return pd.DataFrame(rows)


def test_date_blocked_folds_and_locked_final_test():
    data=frame();split=folds(data)
    assert len(split)>=3 and split[-1]['role']=='final_test'
    final=set(data.loc[split[-1]['test'],'target_date'])
    for fold in split:
        train=set(data.loc[fold['train'],'target_date']);cal=set(data.loc[fold['calibration'],'target_date']);test=set(data.loc[fold['test'],'target_date'])
        assert max(train)<min(cal)<max(cal)<min(test)
        assert not train&test and not train&cal
        if fold['role']=='validation':assert not final&test
    assert len(folds(data,expanding=False))==len(split)


def test_partition_availability_leakage_rejected():
    data=frame();data.loc[0,'target_available_at']='2030-01-01T00:00:00Z'
    with pytest.raises(ValueError,match='Split leakage'):folds(data)


def test_legacy_date_splitter_does_not_trust_city_order():
    from src.models.common import time_series_cv
    data=frame(30).sort_values(['city','target_date']).reset_index(drop=True)
    for tr,va in time_series_cv(n_splits=3,dates=data.target_date).split(data):
        assert data.iloc[tr].target_date.max()<data.iloc[va].target_date.min()
        assert not set(data.iloc[tr].target_date)&set(data.iloc[va].target_date)
    with pytest.raises(ValueError,match='metadata'):time_series_cv()


def test_residual_model_floor_and_common_baseline():
    data=frame(100);pred,model,info=correction(data.iloc[:150],data.iloc[150:],['A_cams_aqi'],'ridge')
    assert np.max(np.abs(pred-data.iloc[150:].target_aqi.to_numpy()))<1 and info['clipped_below_zero']==0


def test_uncertainty_framework_bounds_and_n():
    data=frame(100);lo,hi,report=cqr(data.iloc[:100],data.iloc[100:160],data.iloc[160:],['A_cams_aqi'],.9)
    assert len(lo)==40 and np.all(lo<=hi) and report['calibration_days']==30 and report['n']==40


def test_error_definitions_and_no_fake_zero_severe_scores():
    result=scores([50,150],[70,140]);assert result['bias']==5 and result['severe_recall'] is None
    warning=warning_scores([150,50],[50,150]);assert warning['underwarning_rate']==.5 and warning['overwarning_rate']==.5
    assert warning_scores([],[])['underwarning_rate'] is None


def test_paired_bootstrap_preserves_days_and_requires_blocks():
    y=np.full(60,100.);dates=[str(datetime(2025,1,1).date()+timedelta(days=i//2)) for i in range(60)]
    report=paired_block_bootstrap(y,y+20,y+5,dates,repetitions=50)
    assert report['days']==30 and report['absolute_mae_improvement']==15 and report['ci95']==[15,15]
    assert paired_block_bootstrap(y[:2],y[:2]+20,y[:2],dates[:2])['ci95'] is None


def test_advisory_selection_is_calibration_only_and_insufficient_n_honest():
    selected=select_policy(np.full(10,150),{.5:np.full(10,140),.95:np.full(10,200)},list(range(10)),.05)
    assert selected['selected'] is None and selected['status']=='RISK_CONTROL_NOT_ESTABLISHED'


def approved():
    return {'deployment_status':'VALIDATED','protocol_version':VERSION,'feature_version':PROTOCOL['feature_version'],'validated_stations':[7],
        'model_version':'test-only','gates':{k:True for k in ('temporal','spatial','severity','uncertainty','advisory','paired_comparison')},'required_features':['A_cams_aqi']}


@pytest.mark.parametrize('case',['unvalidated','unseen','model_failure','missing','stale','version','gate'])
def test_safe_fallback_to_cams(case):
    model=approved();features={'features':{'A_cams_aqi':100},'feature_cutoff':CUTOFF.isoformat()};station=7;now=CUTOFF
    if case=='unvalidated':model=None
    if case=='unseen':station=99
    if case=='missing':features['features']={}
    if case=='stale':now=CUTOFF+timedelta(hours=5)
    if case=='version':model['feature_version']='wrong'
    if case=='gate':model['gates']['severity']=False
    infer=lambda _:(_ for _ in ()).throw(RuntimeError()) if case=='model_failure' else (90,80,110)
    result=choose_forecast(100,model,station,features,now,infer)
    assert result['forecast_mode']=='CAMS_BASED_NATIONWIDE' and result['aqi']==100 and result['prediction_interval'] is None


def test_wide_interval_not_automatically_abstained():
    result=choose_forecast(100,approved(),7,{'features':{'A_cams_aqi':100},'feature_cutoff':CUTOFF.isoformat()},CUTOFF,lambda _:(100,0,450))
    assert result['forecast_mode']=='STATION_CALIBRATED_AIRGUARD' and result['prediction_interval']['upper']==450


def test_out_of_window_never_backdates_prospective_record():
    assert ResearchStore().capture({'key':'test'},'2026-10-10',CUTOFF+timedelta(hours=1))['status']=='OUTSIDE_FIXED_ISSUANCE_WINDOW'


def test_drift_small_n_not_interpreted_as_evidence():
    assert drift([1,2],[5,6])['status']=='INSUFFICIENT_DATA'


def test_full_experiment_framework_on_constructed_fixture_only():
    from src.research.evaluation import evaluate
    result=evaluate(frame(182))
    assert result['status']=='EVALUATED_NOT_DEPLOYED' and result['final_test']['B2_raw_CAMS']['n']==60
    assert len(result['spatial'])==4 and set(result['uncertainty'])=={'0.8','0.9'}
    assert len(result['advisory'])==7 and result['deployment'].startswith('Disabled')


@pytest.mark.parametrize('violation',['future_feature','backdated_forecast'])
def test_real_database_rejects_leakage_and_backdating(violation):
    from src.ingestion.settings import load_env, secret
    load_env()
    if not secret('DATABASE_URL'):pytest.skip('DATABASE_URL not configured')
    connection=connect()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as c:
            c.execute('select location_key from airguard.locations limit 1');key=c.fetchone()['location_key']
            start,end=period('2026-10-11');latest=CUTOFF+timedelta(minutes=1) if violation=='future_feature' else CUTOFF-timedelta(minutes=1)
            if violation=='future_feature':
                with pytest.raises(psycopg2.Error,match='check constraint'):
                    c.execute('''insert into airguard.feature_snapshots(snapshot_hash,protocol_version,feature_version,location_key,issue_time,feature_cutoff,
                        latest_input_available_at,target_date,target_start,target_end,features,provenance) values('test-only-future',%s,'test',%s,%s,%s,%s,'2026-10-11',%s,%s,'{"A_cams_aqi":100}','{}')''',
                        (VERSION,key,CUTOFF,CUTOFF,latest,start,end))
            else:
                c.execute('''insert into airguard.feature_snapshots(snapshot_hash,protocol_version,feature_version,location_key,issue_time,feature_cutoff,
                    latest_input_available_at,target_date,target_start,target_end,features,provenance) values('test-only-backdate',%s,'test',%s,%s,%s,%s,'2026-10-11',%s,%s,'{"A_cams_aqi":100}','{}')''',
                    (VERSION,key,CUTOFF,CUTOFF,latest,start,end))
                with pytest.raises(psycopg2.Error,match='issue-time'):
                    c.execute('''insert into airguard.research_forecast_runs(protocol_version,location_key,feature_snapshot_hash,forecast_mode,issued_at,
                        feature_cutoff,target_date,target_start,target_end,cams_aqi,predicted_aqi,methodology_version,artifact)
                        values(%s,%s,'test-only-backdate','CAMS_BASED_NATIONWIDE',%s,%s,'2026-10-11',%s,%s,100,100,%s,'{}')''',
                        (VERSION,key,CUTOFF,CUTOFF,start,end,PROTOCOL['methodology_version']))
    finally:connection.rollback();connection.close()


def test_real_database_private_immutable_protocol_and_duplicate():
    from src.ingestion.settings import load_env, secret
    load_env()
    if not secret('DATABASE_URL'):pytest.skip('DATABASE_URL not configured')
    connection=connect()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as c:
            c.execute('select count(*) n from airguard.research_protocols where protocol_version=%s',(VERSION,));assert c.fetchone()['n']==1
            c.execute('insert into airguard.research_protocols(protocol_version,definition,definition_hash) values(%s,%s,%s) on conflict do nothing',(VERSION,Json(PROTOCOL),'ignored'));assert c.rowcount==0
            c.execute("select has_schema_privilege('anon','airguard','USAGE') allowed");assert not c.fetchone()['allowed']
            c.execute("select relrowsecurity from pg_class join pg_namespace on pg_namespace.oid=relnamespace where nspname='airguard' and relname='feature_snapshots'");assert c.fetchone()['relrowsecurity']
            with pytest.raises(psycopg2.Error,match='immutable'):c.execute('update airguard.research_protocols set definition_hash=%s where protocol_version=%s',('bad',VERSION))
    finally:connection.rollback();connection.close()
