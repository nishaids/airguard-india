from datetime import timedelta
import numpy as np
import pytest
from tests.test_primary_experiments import rows
from src.research.calibration.primary_uncertainty import intervals_and_policies,chronological
from src.research.calibration.protocol import load


def example():
    frame=rows(130)
    train,cal,test=frame.iloc[:50],frame.iloc[50:90].copy(),frame.iloc[90:].copy()
    cal['season']=test['season']='pre_monsoon';cal['region']=test['region']='South'
    p=load();qc={q:np.full(len(cal),q*100) for q in p['uncertainty']['quantile_levels']}
    qt={q:np.full(len(test),q*100) for q in p['uncertainty']['quantile_levels']}
    return train,cal,test,qc,qt,p


def test_policy_choice_cannot_change_with_test_outcomes():
    _,cal,test,qc,qt,p=example()
    first=intervals_and_policies(cal,test,np.full(len(cal),50),np.full(len(test),50),qc,qt,p)
    changed=test.copy();changed['y_aqi']=250.;changed['y_category']=3
    second=intervals_and_policies(cal,changed,np.full(len(cal),50),np.full(len(test),50),qc,qt,p)
    for target in first['advisory']['P3']['by_declared_target']:
        assert first['advisory']['P3']['by_declared_target'][target]['selected_quantile']==second['advisory']['P3']['by_declared_target'][target]['selected_quantile']
    assert first['advisory']['P2']['shift']==second['advisory']['P2']['shift']
    assert first['advisory']['P0']['under_warning']!=second['advisory']['P0']['under_warning']


def test_censored_calibration_is_excluded_from_exact_scores_and_chronology_guard():
    train,cal,test,qc,qt,p=example()
    cal.iloc[0,cal.columns.get_loc('censored')]=True
    cal.iloc[0,cal.columns.get_loc('y_category')]=5
    cal.iloc[0,cal.columns.get_loc('y_aqi')]=401.
    a=intervals_and_policies(cal,test,np.full(len(cal),50),np.full(len(test),50),qc,qt,p)
    cal.iloc[0,cal.columns.get_loc('y_aqi')]=99999.
    b=intervals_and_policies(cal,test,np.full(len(cal),50),np.full(len(test),50),qc,qt,p)
    assert a['intervals']==b['intervals']
    assert a['calibration_censored']==1
    chronological(train,cal,test,p)
    with pytest.raises(ValueError,match='overlap'):
        chronological(train,train,test,p)


@pytest.mark.parametrize('bad_shape', ['short','column','nonfinite'])
def test_misaligned_quantile_vectors_are_rejected_before_sorting(bad_shape):
    _,cal,test,qc,qt,p=example()
    q=next(iter(qt))
    if bad_shape=='short':qt[q]=qt[q][:-1]
    elif bad_shape=='column':qt[q]=qt[q][:,None]
    else:qt[q][0]=np.nan
    with pytest.raises(ValueError,match='aligned and finite'):
        intervals_and_policies(cal,test,np.full(len(cal),50),np.full(len(test),50),qc,qt,p)
