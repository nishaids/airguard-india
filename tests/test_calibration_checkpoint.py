from datetime import date, datetime, timedelta, timezone
import csv
import gzip
import json
import numpy as np
import pandas as pd
import pytest
from src.research.calibration import data, splits, metrics
from src.research.calibration.availability import Cutoffs, guard_snapshot, LeakageError
from src.research.calibration.measured import causal_rejection_times, strict_guard, STRICT_FEATURES, station_frames
from src.research.calibration.protocol import load, digest, ProtocolChanged
from src.research.calibration.checkpoint import canonical_hash, verify
from src.research.calibration.statistics import finite_quantile, paired, holm, warning, select_risk_quantile
from src.research.calibration.preliminary import eligible, climatology, freeze_plan


@pytest.mark.parametrize('prediction',[[np.nan]*40,[400]*39,[np.inf]*40])
def test_advisory_rejects_invalid_pairs(prediction):
    with pytest.raises(ValueError):
        select_risk_quantile([5]*40,{.5:prediction},.05)
    with pytest.raises(ValueError):
        warning([5]*40,prediction)


def test_qc_ledger_uses_same_rejection_reason(tmp_path,monkeypatch):
    from src.research.calibration.measured import qc_station
    monkeypatch.setattr(data.config,'PROJECT_ROOT',tmp_path)
    path=sensor_file(tmp_path,[10],coverage=None)
    _,_,_,audit,ledger,_=qc_station({'sensors':{'PM2.5':{'file':path.name,'rows':1}}})
    assert audit['PM2.5']['rejected']=={'coverage_unknown':1}
    assert ledger[0]['reason']=='coverage_unknown'


def test_runner_audits_values_and_history_provenance():
    from src.research.calibration.preliminary import audit_features
    day=date(2025,6,1)
    with pytest.raises(LeakageError):
        audit_features(pd.DataFrame([{'target_date':day,'wx_temp_mean':28.}]))
    with pytest.raises(LeakageError):
        audit_features(pd.DataFrame([{'target_date':day,'obs24_aqi':100.,
            'latest_measured_bin_end_utc':Cutoffs.for_target(day).measurement+timedelta(seconds=1)}]))
    with pytest.raises(ValueError,match='bin-end'):
        audit_features(pd.DataFrame([{'target_date':day,'obs24_aqi':100.}]))


def test_builder_identity_includes_aqi_and_availability(tmp_path,monkeypatch):
    from src.research.calibration import measured
    original=measured.builder_code_hash()
    path=tmp_path/'aqi.py';path.write_text('scientific dependency change')
    monkeypatch.setattr(measured.aqi,'__file__',str(path))
    monkeypatch.setattr(measured.config,'portable',lambda p:str(p))
    changed=measured.builder_code_hash()
    path.write_text('different scientific dependency')
    assert measured.builder_code_hash()!=changed and changed!=original


@pytest.mark.parametrize('field,delta',[
    ('latest_measured_bin_end_utc',timedelta(hours=-3)+timedelta(seconds=1)),
    ('latest_neighbour_bin_end_utc',timedelta(hours=-3)+timedelta(seconds=1)),
    ('latest_fire_acquired_utc',timedelta(hours=-3)+timedelta(seconds=1)),
    ('weather_latest_run_bound_utc',timedelta(seconds=1))])
def test_future_rejection(field,delta):
    day=date(2025,6,1)
    with pytest.raises(LeakageError):
        guard_snapshot({'target_date':day,field:Cutoffs.for_target(day).issue+delta})


def test_final_day_lag_and_cams_refused():
    with pytest.raises(LeakageError):
        guard_snapshot({'target_date':date(2025,6,1),'latest_daily_lag_date':date(2025,5,31)})
    with pytest.raises(LeakageError):
        guard_snapshot({'target_date':date(2025,6,1)},require_issue_time_valid_cams=True)


@pytest.mark.parametrize('feature',['cams_matched','y_aqi','bias_now','obs24_aqi','fire_n50_24h'])
def test_strict_stream_refuses_unproven_features(feature):
    with pytest.raises(LeakageError):
        strict_guard({'target_date':date(2025,6,1)},[feature])


def test_weather_needs_run_bound():
    with pytest.raises(LeakageError):
        strict_guard({'target_date':date(2025,6,1),'wx_temp_mean':28.},STRICT_FEATURES)


def sensor_file(tmp_path, values, pollutant='PM2.5', unit='ug/m3', coverage=100):
    path=tmp_path/'hours.csv.gz'
    start=datetime(2025,5,1,tzinfo=timezone.utc)
    with gzip.open(path,'wt',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['valid_from_utc','valid_to_utc','value','unit','coverage_pct','flagged'])
        writer.writerows([(str(start+timedelta(hours=i)),str(start+timedelta(hours=i+1)),v,unit,coverage,0) for i,v in enumerate(values)])
    return path


def test_zero_stuck_and_spikes(tmp_path,monkeypatch):
    monkeypatch.setattr(data.config,'PROJECT_ROOT',tmp_path)
    path=sensor_file(tmp_path,[0,2,2,2,2,2,2,5000])
    kept,rejected=data.read_sensor(path.name,'PM2.5')
    assert len(kept)==1 and list(kept.values())==[5000]
    assert rejected=={'zero_reading':1,'stuck_sensor_run':6}


@pytest.mark.parametrize('coverage',[None,'bad',float('nan'),74.9])
def test_provider_coverage_must_be_evidenced(tmp_path,monkeypatch,coverage):
    monkeypatch.setattr(data.config,'PROJECT_ROOT',tmp_path)
    path=sensor_file(tmp_path,[10],coverage=coverage)
    assert not data.read_sensor(path.name,'PM2.5')[0]


def test_stuck_run_gaps_and_causal_prefix():
    start=datetime(2025,5,1,tzinfo=timezone.utc)
    bins={start+timedelta(hours=i):10 for i in range(6)}
    assert data.stuck_runs(dict(list(bins.items())[:5]))==[]
    assert len(data.stuck_runs(bins))==6
    rejection=causal_rejection_times(bins)
    before=start+timedelta(hours=5)
    assert all(known>before for known in rejection.values())
    assert all(known==start+timedelta(hours=6) for known in rejection.values())
    bins[start+timedelta(hours=2,minutes=10)]=11
    assert not data.stuck_runs(bins)


def test_rejected_station_days_are_retained():
    dates=[date(2025,6,1),date(2025,6,2)]
    table,_,_=station_frames('1',{'sensors':{}},dates)
    assert len(table)==2 and not table.target_valid.any()


def test_severe_not_a_numeric_regression_target():
    result=metrics.summary([100,401],[110,200],[1,5],[False,True])
    assert result['mae']==10 and result['n_exact']==1
    assert result['n_censored_severe']==1
    assert result['censored_severe']['mean_shortfall_lower_bound']==201
    assert result['censored_severe']['share_forecast_below_401']==1
    assert result['poor_or_worse']['misses']==1


def test_metrics_alignment_and_nan_refused():
    with pytest.raises(ValueError):
        metrics.summary([100],[np.nan],[1],[False])
    with pytest.raises(ValueError):
        metrics.summary([100],[110],[1,2],[False])
    with pytest.raises(ValueError):
        metrics.summary([401],[110],[1],[True])


def test_chronology_and_final_isolation():
    p=load()
    folds=splits.rolling_folds(splits.calendar(p),p)
    assert splits.check(folds)
    final=next(f for f in folds if f['role']=='final_test')
    assert len(final['test'])==90
    for f in folds[:-1]:
        assert not set(f['test']) & set(final['test'])
        assert (min(f['calibration'])-max(f['train'])).days==2
        assert (min(f['test'])-max(f['calibration'])).days==2
    geometry=splits.spatial_frame(splits.calendar(p),p)
    assert not set(geometry['test']) & set(final['test'])


def test_spatial_assignment_is_deterministic_and_disjoint():
    groups=['Delhi','Delhi','Pune','Chennai','Mumbai']
    first=splits.grouped_folds(groups,k=2)
    assert first==splits.grouped_folds(groups[::-1],k=2)
    for fold in set(first.values()):
        held={g for g in groups if first[g]==fold}
        trained={g for g in groups if first[g]!=fold}
        assert not held & trained


def test_eligibility_cannot_read_test_targets():
    train=pd.DataFrame({'station_id':[1]*30+[2]*29,'target_valid':True})
    test=pd.DataFrame({'station_id':[1,2],'target_valid':[False,True]})
    _,selected=eligible(train,test)
    assert list(selected.station_id)==[1]
    test['target_valid']=~test.target_valid
    assert list(eligible(train,test)[1].station_id)==[1]


def test_climatology_excludes_severe_training_and_unseen_fallback():
    train=pd.DataFrame({'station_id':[1,1,2],'target_valid':True,'censored':[False,True,False],'month':[1,1,2],'y_aqi':[100,401,50]})
    test=pd.DataFrame({'station_id':[1,3],'month':[1,1]})
    assert np.array_equal(climatology(train,test),[100,75])


def test_finite_sample_and_risk_control_refusal():
    assert finite_quantile([1,2,3,4],.8)==4
    assert finite_quantile([1,2],.9) is None
    assert select_risk_quantile([5,5],{.5:np.array([100,100]),.975:np.array([500,500])},.05) is None
    assert warning([5],[100])['serious_under_warning']==1


def test_bootstrap_reproducibility_and_pair_direction():
    f=pd.DataFrame({'target_date':pd.date_range('2025-01-01',periods=30),'y_aqi':100.,'censored':False,'good':105.,'bad':120.})
    a=paired(f,'good','bad',repetitions=100)
    assert a==paired(f,'good','bad',repetitions=100)
    assert a['ci95']==[-15,-15]
    assert a['mae_difference']==-15
    values=holm({'a':{'dm_pvalue':.01},'b':{'dm_pvalue':.03}})
    assert values['a']['holm_pvalue']==.02 and values['b']['holm_pvalue']==.03


def test_protocol_hash_unchanged_and_identity_order_independent():
    p=load()
    assert p['_sha256']==digest()
    assert canonical_hash({'a':1,'b':2})==canonical_hash({'b':2,'a':1})


def test_frozen_snapshot_refuses_path_escape(tmp_path):
    from src.research.calibration.checkpoint import capture
    with pytest.raises(ValueError,match='versioned research snapshot'):
        capture(tmp_path/'inputs.json')


def test_frozen_snapshot_refuses_identity_tampering(tmp_path,monkeypatch):
    from src.research.calibration import checkpoint
    monkeypatch.setattr(data,'DERIVED',tmp_path)
    identity={'selection_semantic_sha256':'wrong','sensors':[]}
    value={'data_version':canonical_hash(identity),'identity':identity,
        'protocol_sha256':load()['_sha256'],'selection':{},'stations':{}}
    directory=tmp_path/value['data_version']; directory.mkdir()
    path=directory/'inputs.json'; path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='Frozen selection identity'):
        checkpoint.capture(path)


def test_window_resume_makes_no_duplicate_requests(tmp_path):
    from src.research.calibration.openaq_archive import fetch_sensor
    start=datetime(2025,5,1,tzinfo=timezone.utc)
    sensor={'sensor_id':123,'first_utc':start.isoformat(),'last_utc':(start+timedelta(hours=1)).isoformat()}
    class Client:
        calls=0
        def get(self,*args,**kwargs):
            self.calls+=1
            return {'results':[]}
    client=Client()
    first=fetch_sensor(client,sensor,start,start+timedelta(hours=2),checkpoint_dir=tmp_path)
    assert fetch_sensor(client,sensor,start,start+timedelta(hours=2),checkpoint_dir=tmp_path)==first
    assert client.calls==1
    path=next(tmp_path.glob('*.json'))
    payload=json.loads(path.read_text());payload['payload']={'results':[123]}
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        fetch_sensor(client,sensor,start,start+timedelta(hours=2),checkpoint_dir=tmp_path)


def test_full_page_resumes_only_missing_extra_pages(tmp_path):
    from src.research.calibration.openaq_archive import fetch_sensor
    start=datetime(2025,5,1,tzinfo=timezone.utc)
    sensor={'sensor_id':123,'first_utc':start.isoformat(),'last_utc':(start+timedelta(hours=999)).isoformat(),
            'pollutant':'PM2.5','units':'ug/m3'}
    hourly=[{'value':i+1,'parameter':{'name':'pm25','units':'ug/m3'},'period':{
        'datetimeFrom':{'utc':(start+timedelta(hours=i)).isoformat()},
        'datetimeTo':{'utc':(start+timedelta(hours=i+1)).isoformat()}}} for i in range(1000)]
    class Client:
        pages=[]
        def get(self,path,params):
            page=params.get('page',1);self.pages.append(page)
            return {'results':hourly if page==1 else [],'meta':{'page':page,'limit':1000}}
    client=Client()
    first=fetch_sensor(client,sensor,start,start+timedelta(hours=1000),checkpoint_dir=tmp_path)
    assert client.pages==[1,2] and len(first[0])==1000
    assert first[1][0]['pagination_complete'] is True
    for path in tmp_path.glob('*.json'):
        if json.loads(path.read_text())['request'].get('page')==2:
            path.unlink()
    assert fetch_sensor(client,sensor,start,start+timedelta(hours=1000),checkpoint_dir=tmp_path)==first
    assert client.pages==[1,2,2]
    fetch_sensor(client,sensor,start,start+timedelta(hours=1000),checkpoint_dir=tmp_path)
    assert client.pages==[1,2,2]


def test_deployment_identity_is_explicit(monkeypatch):
    from src.research.storage import issuance_identity
    monkeypatch.delenv('AIRGUARD_GIT_SHA',raising=False)
    monkeypatch.delenv('VERCEL_GIT_COMMIT_SHA',raising=False)
    assert issuance_identity()['git_sha'] is None
    monkeypatch.setenv('AIRGUARD_GIT_SHA','a'*40)
    assert issuance_identity()['git_sha']=='a'*40
    monkeypatch.setenv('AIRGUARD_GIT_SHA','untrusted')
    assert issuance_identity()['git_sha'] is None


def test_primary_rejects_proxy_and_reanalysis():
    from src.research.calibration.primary import require_operational_archive, ArchiveBlocked, guard_primary_row
    with pytest.raises(ArchiveBlocked):
        require_operational_archive({'source':'CAMS_GLOBAL_VIA_OPEN_METEO_SHORT_LEAD_ARCHIVE','issue_time_valid':True})
    with pytest.raises(LeakageError):
        require_operational_archive({'source':'COPERNICUS_ADS_OPERATIONAL_FORECAST',
            'dataset':'cams-global-atmospheric-composition-forecasts','source_type':'reanalysis','files':{'x':{}},'units_verified':True})
    cut=Cutoffs.for_target(date(2025,6,1))
    row={'target_date':cut.target_date,'cams_aqi_frozen':100.,'cams_source':'COPERNICUS_ADS_OPERATIONAL_FORECAST','cams_issue_time_valid':True,
         'cams_run_initialized_utc':cut.issue-timedelta(hours=14),'cams_available_at_utc':cut.issue-timedelta(hours=6)}
    guard_primary_row(row,['cams_aqi_frozen'])
    with pytest.raises(LeakageError):
        guard_primary_row(row,['cams_matched'])
    with pytest.raises(LeakageError):
        guard_primary_row({**row,'cams_available_at_utc':cut.issue+timedelta(seconds=1)},['cams_aqi_frozen'])
