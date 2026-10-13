from datetime import date, timedelta, datetime, timezone
import numpy as np
import pandas as pd
import pytest
from src.research.calibration import primary_experiments as experiment
from src.research.calibration.availability import Cutoffs
from src.research.calibration.protocol import load
from src.research.calibration.primary import guard_primary_row


def rows(n=160):
    records=[]
    for i in range(n):
        day=date(2025,2,19)+timedelta(days=i)
        cut=Cutoffs.for_target(day)
        records.append(dict(station_id=1,target_date=day,target_valid=True,censored=False,
                            y_aqi=float(20+(i%20)*2),y_category=0,month=day.month,
                            cams_aqi_frozen=50.,cams_source='COPERNICUS_ADS_OPERATIONAL_FORECAST',
                            cams_issue_time_valid=True,cams_run_initialized_utc=datetime.combine(day-timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc),
                            cams_available_at_utc=cut.issue-timedelta(hours=4),
                            latitude=float(i%20),longitude=77.,matched_support_equals_frozen_support=True))
    return pd.DataFrame(records)


def test_inner_tuning_rejects_nontraining_dates_and_sealed_input_before_fit():
    frame=rows()
    with pytest.raises(ValueError,match='outside the training'):
        experiment.tune(frame,list(frame.target_date[:-1]),['latitude'],'ridge',True,load())
    frame.loc[0,'target_date']=date(2026,7,10)
    with pytest.raises(ValueError,match='Locked final'):
        experiment.fit(frame,['latitude'],'ridge',True,{'alpha':1},load())


def test_censored_value_cannot_change_fitted_regression_or_tuning():
    frame=rows()
    frame.loc[0,'censored']=True;frame.loc[0,'y_category']=5;frame.loc[0,'y_aqi']=401
    model,selection=experiment.tune(frame,list(frame.target_date),['latitude'],'ridge',True,load())
    changed=frame.copy();changed.loc[0,'y_aqi']=99999
    alternative,other=experiment.tune(changed,list(changed.target_date),['latitude'],'ridge',True,load())
    assert np.allclose(model.predict(frame),alternative.predict(frame))
    assert selection==other
    assert selection['inner_validation_range'][0]==str(frame.target_date.iloc[-30])


def test_station_eligibility_uses_training_only_even_with_long_test_history():
    frame=rows(200)
    train,parts=experiment.eligible(frame.iloc[:119],[frame.iloc[119:]],load())
    assert train.empty and parts[0].empty
    train,parts=experiment.eligible(frame.iloc[:120],[frame.iloc[120:]],load())
    assert len(train)==120 and len(parts[0])==80


def test_censored_coverage_does_not_make_inner_regression_fit_eligible():
    frame=rows()
    assert experiment.tuning_supported(frame,list(frame.target_date))
    frame.loc[:129,'censored']=True
    assert not experiment.tuning_supported(frame,list(frame.target_date))
    frame['censored']=False
    frame.loc[130:,'censored']=True
    assert not experiment.tuning_supported(frame,list(frame.target_date))


def test_selection_preserves_raw_cams_and_predeclared_ties():
    mae={name:{'mae':10.} for name in experiment.METHODS}
    report=dict(status='EVALUATED_DEVELOPMENT',n_primary_rows=100,primary=mae)
    assert experiment.select([report])['selected']=='raw_cams'
    for name in ('direct_lightgbm','direct_ridge','residual_ridge'):mae[name]['mae']=9.
    selected=experiment.select([report])
    assert selected['selected']=='residual_ridge'
    mae['persistence']['mae']=8.
    assert experiment.select([report])['strongest_reported_baseline']=='persistence'


@pytest.mark.parametrize('name',['cams_matched_evaluation_only','matched_support_equals_frozen_support'])
def test_evaluation_support_annotations_are_forbidden_predictors(name):
    row=rows(1).iloc[0].to_dict();row[name]=1.
    with pytest.raises(ValueError,match='Outcome-dependent'):
        guard_primary_row(row,[name])


@pytest.mark.parametrize('family',['lightgbm','xgboost'])
def test_booster_training_api_and_censored_predictions(family):
    frame=rows(80)
    model=experiment.fit(frame.iloc[:60],['latitude'],family,True,{'n_estimators':5},load())
    pred=model.predict(frame.iloc[60:])
    assert len(pred)==20 and np.isfinite(pred).all()


@pytest.mark.parametrize('family',['lightgbm','xgboost'])
def test_early_stopping_uses_training_last_thirty_days(family):
    frame=rows()
    model,choice=experiment.tune(frame,list(frame.target_date),['latitude'],family,True,load())
    assert all(trial['params']['n_estimators']<=600 for trial in choice['trials'])
    assert choice['inner_validation_range']==[str(frame.target_date.iloc[-30]),str(frame.target_date.iloc[-1])]
    assert np.isfinite(model.predict(frame)).all()


def test_stale_feed_lookup_is_date_keyed_and_never_changes_outcomes():
    frame=rows(4)
    frame['obs24_aqi']=[10,20,30,40]
    frame['latest_measured_bin_end_utc']=[Cutoffs.for_target(d).measurement for d in frame.target_date]
    sparse=frame.drop(index=1)
    stale=experiment.measured_sensitivity(sparse,['cams_aqi_frozen','obs24_aqi','latitude'])
    assert np.isnan(stale.loc[2,'obs24_aqi'])
    assert stale.loc[3,'obs24_aqi']==30
    assert stale.y_aqi.equals(sparse.y_aqi) and stale.cams_aqi_frozen.equals(sparse.cams_aqi_frozen)
    withheld=experiment.measured_sensitivity(sparse,['cams_aqi_frozen','obs24_aqi','latitude'],withheld=True)
    assert withheld.obs24_aqi.isna().all()
