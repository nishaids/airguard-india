"""Pre-final uncertainty/advisory diagnostics using training and calibration only."""
import numpy as np
import pandas as pd
from src.research.calibration import metrics
from src.research.calibration.preliminary import interval_score
from src.research.calibration.statistics import finite_quantile, select_risk_quantile, warning_with_intervals
from src.research.calibration.primary_experiments import audit_rows, fixed_booster


def chronological(train,cal,test,protocol):
    if train.empty or cal.empty or test.empty:raise ValueError('Nonempty chronological partitions required')
    if not max(train.target_date)<min(cal.target_date)<=max(cal.target_date)<min(test.target_date):
        raise ValueError('Training/calibration/test partitions overlap or are not chronological')
    # Caller audit refuses locked final dates in any partition before statistics.
    for part in (train,cal,test):audit_rows(part,[],protocol)


def intervals_and_policies(cal,test,point_cal,point,quantiles_cal,quantiles_test,protocol):
    """Pure calibration. Quantile predictions originate from training-only models."""
    for part in (cal,test):audit_rows(part,[],protocol)
    exact=~cal.censored.to_numpy()
    y=cal.y_aqi.to_numpy()
    point_cal=np.asarray(point_cal);point=np.asarray(point)
    levels=sorted(quantiles_cal)
    if not levels or levels!=sorted(quantiles_test):raise ValueError('Quantile grids differ')
    qc={q:np.asarray(quantiles_cal[q]) for q in levels}
    qt={q:np.asarray(quantiles_test[q]) for q in levels}
    vectors=[(point_cal,len(cal)),(point,len(test)),*[(v,len(cal)) for v in qc.values()],*[(v,len(test)) for v in qt.values()]]
    if any(a.ndim!=1 or len(a)!=n or not np.isfinite(a).all() for a,n in vectors):
        raise ValueError('Forecast/calibration vectors must be aligned and finite')
    qc=dict(zip(levels,np.sort(np.stack(list(qc.values())),axis=0)))
    qt=dict(zip(levels,np.sort(np.stack(list(qt.values())),axis=0)))
    residual=np.abs(y[exact]-point_cal[exact]);results={}
    for nominal in protocol['uncertainty']['nominal_coverages']:
        q=finite_quantile(residual,nominal)
        if q is None:results[f'split_{nominal}']={'status':'INSUFFICIENT_EXACT_CALIBRATION'};continue
        results[f'split_{nominal}']=interval_score(test,np.maximum(0,point-q),point+q,nominal)
        low,high=(.1,.9) if nominal==.8 else (.05,.95)
        scores=np.maximum(qc[low][exact]-y[exact],y[exact]-qc[high][exact])
        correction=finite_quantile(scores,nominal)
        if correction is not None:
            correction=max(0,correction)
            results[f'cqr_{nominal}']=interval_score(test,np.maximum(0,qt[low]-correction),qt[high]+correction,nominal)
    for nominal in protocol['uncertainty']['nominal_coverages']:
        radii=np.full(len(test),np.nan)
        for category in range(6):
            values=residual[metrics.bands(point_cal[exact])==category]
            q=finite_quantile(values,nominal) if len(values)>=protocol['subgroups']['minimum_n'] else None
            if q is not None:radii[metrics.bands(point)==category]=q
        keep=np.isfinite(radii)
        results[f'mondrian_{nominal}']={'status':'INSUFFICIENT_FORECAST_GROUP_CALIBRATION','unsupported_rows':int((~keep).sum())}
        if keep.any():
            results[f'mondrian_{nominal}'].update(interval_score(test.loc[keep],np.maximum(0,point[keep]-radii[keep]),point[keep]+radii[keep],nominal))
            results[f'mondrian_{nominal}']['status']='EVALUATED_SUPPORTED_GROUPS'
    policies={'P0':warning_with_intervals(test,point)}
    for q,name in ((.5,'P1'),(.75,'P2')):
        shift=finite_quantile(y[exact]-qc[q][exact],q)
        policies[name]={'status':'INSUFFICIENT_EXACT_CALIBRATION'} if shift is None else {
            **warning_with_intervals(test,np.maximum(0,qt[q]+shift)),
            'censored_calibration_excluded':int((~exact).sum()),'shift':shift}
    candidates={q:qc[q] for q in protocol['advisory']['candidate_quantiles']}
    risk={}
    for target in sorted(set(protocol['advisory']['under_warning_targets'].values())):
        selected=select_risk_quantile(cal.y_category,candidates,target)
        risk[str(target)]={'selected_quantile':selected,'target':target,
            'status':'NO_CALIBRATION_CANDIDATE' if selected is None else 'EMPIRICAL_TARGET_NO_DEPENDENCE_GUARANTEE',
            **(warning_with_intervals(test,qt[selected]) if selected is not None else {})}
    policies['P3']={'by_declared_target':risk,'cohorts':protocol['advisory']['under_warning_targets'],
                    'cohorts_are_not_independent_clinical_samples':True}
    return {'intervals':results,'advisory':policies,'calibration_exact':int(exact.sum()),
            'calibration_censored':int((~exact).sum()),'selection_uses_test_labels':False,
            'quantile_crossing_repair':'row-wise sorting of forecasts only',
            'censored_note':'upper >=401 is lower-bound compatibility, not identified true-index coverage'}


def evaluate(train,cal,test,columns,point_name,train_dates,protocol):
    chronological(train,cal,test,protocol)
    for part in (train,cal,test):audit_rows(part,columns,protocol)
    qc,qt,rounds={},{},{}
    for quantile in protocol['uncertainty']['quantile_levels']:
        model=fixed_booster(train,train_dates,columns,protocol,quantile)
        qc[quantile]=model.predict(cal);qt[quantile]=model.predict(test)
        rounds[str(quantile)]=model.params['n_estimators']
    result=intervals_and_policies(cal,test,cal[point_name],test[point_name],qc,qt,protocol)
    result['quantile_training']='Residual LightGBM 31 leaves/60 child samples; training-only early stopping; add frozen raw CAMS'
    result['quantile_rounds']=rounds
    return result
