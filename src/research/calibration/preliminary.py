"""Non-CAMS preliminary experiments. The primary CAMS study remains blocked.

No final-test label enters this runner. Configuration is frozen before fitting;
each dataset revision writes a separate immutable result directory.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor
from src import config
from src.research.calibration import data, splits, metrics
from src.research.calibration.checkpoint import OUT, canonical_hash, write_json
from src.research.calibration.measured import STRICT_FEATURES, CONDITIONAL_FEATURES, strict_guard
from src.research.calibration.protocol import load
from src.research.calibration.statistics import finite_quantile, paired, holm, warning, select_risk_quantile

PLAN = {'experiment':'NON_CAMS_PRELIMINARY', 'version':'non-cams-plan-v1', 'seed':42,
        'primary_experiment_completed':False, 'final_test':'SEALED; no scoring or selection',
        'station_selection':'>=30 valid measured targets in that fold training window only; never test coverage',
        'minimum_training_valid_days':30, 'ridge_alpha':10.,
        'strict_features':STRICT_FEATURES, 'conditional_features':CONDITIONAL_FEATURES,
        'comparisons':'strict Ridge versus climatology; conditional history Ridge versus persistence and climatology',
        'ablation':'calendar/coordinates; add forecast weather; conditional add measured history',
        'quantile_model':{'family':'GradientBoostingRegressor','estimators':60,'depth':2,'min_samples_leaf':60,'learning_rate':.05},
        'uncertainty':'80/90% split conformal; 90% CQR; forecast-band Mondrian >=30 exact calibration pairs',
        'risk_policy':'v3.1 candidate quantiles; (k+1)/(n+1); calibration only; no guarantee under dependent days',
        'publication_caveat':'historical station labels and local history assume healthy-feed 3-hour latency; unavailable release logs prevent strict operational validation',
        'CAMS_ARCHIVE_STATUS':'PENDING_MANUAL_ADS_CREDENTIAL'}


def freeze_plan(protocol):
    value = {**PLAN,'protocol_sha256':protocol['_sha256']}
    path = OUT / 'non_cams_plan.json'
    if path.exists() and json.loads(path.read_text()) != value:
        raise ValueError('Preliminary plan changed; version it before a new experiment')
    if not path.exists():
        write_json(path,value)
    return canonical_hash(value)


def eligible(train, test):
    counts = train[train.target_valid].groupby('station_id').size()
    ids = counts[counts >= PLAN['minimum_training_valid_days']].index
    return train[train.station_id.isin(ids)], test[test.station_id.isin(ids)]


def estimator(columns):
    return make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),
                         StandardScaler(),Ridge(alpha=PLAN['ridge_alpha']))


def fit_predict(train, parts, columns):
    exact = train[~train.censored & train.target_valid]
    if len(exact) < 30:
        raise ValueError('Too few exact training targets')
    model = estimator(columns)
    model.fit(exact[columns], exact.y_aqi)
    return [np.maximum(0,model.predict(part[columns])) for part in parts]


def climatology(train, test):
    exact = train[train.target_valid & ~train.censored]
    monthly = exact.groupby(['station_id','month']).y_aqi.mean()
    station = exact.groupby('station_id').y_aqi.mean()
    return np.asarray([monthly.get((s,m),station.get(s,exact.y_aqi.mean())) for s,m in zip(test.station_id,test.month)])


def score(frame, column):
    return metrics.summary(frame.y_aqi,frame[column],frame.y_category,frame.censored)


def interval_score(test, lower, upper, nominal):
    exact = ~test.censored.to_numpy()
    y = test.y_aqi.to_numpy()
    result = {'nominal':nominal, 'n_exact':int(exact.sum()),
              'coverage_exact':float(((lower[exact]<=y[exact]) & (y[exact]<=upper[exact])).mean()) if exact.any() else None,
              'mean_width':float(np.mean(upper-lower)), 'median_width':float(np.median(upper-lower)),
              'n_censored':int((~exact).sum()), 'censored_upper_reaches_401':float((upper[~exact]>=401).mean()) if (~exact).any() else None,
              'censoring_note':'upper >=401 is compatibility with a lower bound, not identified coverage of the true index'}
    for field in ('y_category','season','region'):
        result[field] = {}
        for name, group in test.groupby(field):
            indices = test.index.get_indexer(group.index)
            keep = indices[~group.censored.to_numpy()]
            result[field][str(name)] = {'n_exact':len(keep),'coverage':float(((lower[keep]<=y[keep]) & (y[keep]<=upper[keep])).mean()) if len(keep)>=30 else None}
    return result


def uncertainty(train, cal, test, columns):
    pred_cal, pred = fit_predict(train,[cal,test],columns)
    exact = ~cal.censored.to_numpy()
    residual = np.abs(cal.y_aqi.to_numpy()[exact]-pred_cal[exact])
    intervals = {}
    for nominal in (.8,.9):
        radius = finite_quantile(residual,nominal)
        if radius is not None:
            intervals[f'split_{nominal}'] = interval_score(test,np.maximum(0,pred-radius),pred+radius,nominal)
    # Mondrian membership uses the prediction, never the observed test category.
    radii = np.full(len(test),np.nan)
    for band in range(6):
        values = residual[metrics.bands(pred_cal[exact])==band]
        radius = finite_quantile(values,.9) if len(values)>=30 else None
        if radius is not None:
            radii[metrics.bands(pred)==band] = radius
    keep = np.isfinite(radii)
    if keep.any():
        intervals['mondrian_0.9'] = interval_score(test.loc[keep],np.maximum(0,pred[keep]-radii[keep]),pred[keep]+radii[keep],.9)
        intervals['mondrian_0.9']['abstained_rows'] = int((~keep).sum())
    exact_train = train[~train.censored & train.target_valid]
    imputer = SimpleImputer(strategy='median',keep_empty_features=True)
    xtrain = imputer.fit_transform(exact_train[columns])
    xcal, xtest = imputer.transform(cal[columns]), imputer.transform(test[columns])
    predictions_cal, predictions_test = {}, {}
    quantiles = sorted(set([.05,.1,.5,.65,.75,.85,.9,.95,.975]))
    cfg = PLAN['quantile_model']
    for q in quantiles:
        model = GradientBoostingRegressor(loss='quantile',alpha=q,n_estimators=cfg['estimators'],
                   max_depth=cfg['depth'],min_samples_leaf=cfg['min_samples_leaf'],learning_rate=cfg['learning_rate'],random_state=42)
        model.fit(xtrain,exact_train.y_aqi)
        predictions_cal[q], predictions_test[q] = model.predict(xcal), model.predict(xtest)
    # Sort quantiles row-wise to repair crossing without using any test labels.
    ordered_cal = np.sort(np.stack([predictions_cal[q] for q in quantiles]),axis=0)
    ordered_test = np.sort(np.stack([predictions_test[q] for q in quantiles]),axis=0)
    predictions_cal = dict(zip(quantiles,ordered_cal))
    predictions_test = dict(zip(quantiles,ordered_test))
    cqr_scores = np.maximum(predictions_cal[.05][exact]-cal.y_aqi.to_numpy()[exact],cal.y_aqi.to_numpy()[exact]-predictions_cal[.95][exact])
    correction = finite_quantile(cqr_scores,.9)
    if correction is not None:
        correction = max(0,correction)
        intervals['cqr_0.9'] = interval_score(test,np.maximum(0,predictions_test[.05]-correction),predictions_test[.95]+correction,.9)
    advisory = {'P0':warning(test.y_category,pred)}
    for q,name in ((.5,'P1'),(.75,'P2')):
        correction = finite_quantile(cal.y_aqi.to_numpy()[exact]-predictions_cal[q][exact],q)
        if correction is not None:
            advisory[name] = warning(test.y_category,np.maximum(0,predictions_test[q]+correction))
            advisory[name]['censored_calibration_labels_excluded'] = int((~exact).sum())
    candidates = {q:predictions_cal[q] for q in quantiles if q>=.5}
    for target in (.1,.05):
        chosen = select_risk_quantile(cal.y_category,candidates,target)
        advisory[f'P3_target_{target}'] = {'selected_quantile':chosen,'target':target,
            'status':'NO_CALIBRATION_CANDIDATE' if chosen is None else 'EMPIRICAL_POLICY_NO_DEPENDENCE_GUARANTEE',
            **(warning(test.y_category,predictions_test[chosen]) if chosen is not None else {})}
    return intervals,advisory


def run():
    protocol = load()
    plan_hash = freeze_plan(protocol)
    quality = json.loads((OUT/'measured_dataset.json').read_text())
    table = pd.read_parquet(config.PROJECT_ROOT/quality['table'])
    table['target_date'] = pd.to_datetime(table.target_date).dt.date
    all_folds = splits.rolling_folds(data.study_dates(protocol),protocol)
    splits.check(all_folds)
    final = next(f for f in all_folds if f['role']=='final_test')
    # Physically remove final rows before any fitting, diagnostics or selection.
    table = table[~table.target_date.isin(final['test'])].copy()
    table = table[table.target_valid].copy()
    for row in table[['target_date','weather_latest_run_bound_utc']].to_dict('records'):
        strict_guard(row,STRICT_FEATURES)
    code_hash = canonical_hash([(p.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(Path(__file__).parent.glob('*.py'))])
    run_id = canonical_hash([quality['dataset_hash'],plan_hash,code_hash])
    destination = OUT/'preliminary'/run_id
    if (destination/'results.json').exists():
        result = json.loads((destination/'results.json').read_text())
        write_json(OUT/'preliminary_latest.json',result)
        return result
    destination.mkdir(parents=True,exist_ok=True)
    fold_results, predictions, interval_results, advisory_results = [],[],{},{}
    # Expanding is primary; fixed 90-day rolling window is a labelled sensitivity.
    for design in ('expanding','sliding_90d'):
        for fold in [f for f in all_folds if f['role']=='rolling']:
            train_dates = fold['train'] if design=='expanding' else fold['train'][-90:]
            train = table[table.target_date.isin(train_dates)]
            test = table[table.target_date.isin(fold['test'])]
            cal = table[table.target_date.isin(fold['calibration'])]
            train,test = eligible(train,test)
            cal = cal[cal.station_id.isin(train.station_id.unique())]
            if len(train)<30 or not len(test):
                fold_results.append({'design':design,'fold':fold['name'],'status':'INSUFFICIENT_DATA'})
                continue
            test = test.copy()
            test['climatology'] = climatology(train,test)
            test['ridge_strict'] = fit_predict(train,[test],STRICT_FEATURES)[0]
            base_columns = [c for c in STRICT_FEATURES if not c.startswith('wx_')]
            test['ridge_calendar_spatial'] = fit_predict(train,[test],base_columns)[0]
            common = test[test.obs24_aqi.notna()].copy()
            conditional_train = train[train.obs24_aqi.notna()]
            if len(conditional_train[~conditional_train.censored])>=30 and len(common):
                common['persistence'] = common.obs24_aqi
                common['ridge_history'] = fit_predict(conditional_train,[common],STRICT_FEATURES+CONDITIONAL_FEATURES)[0]
            entry = {'design':design,'fold':fold['name'],'train_range':fold['train_range'] if design=='expanding' else [str(train_dates[0]),str(train_dates[-1])],
                     'calibration_range':fold['calibration_range'],'test_range':fold['test_range'],
                     'stations_training_eligible':train.station_id.nunique(),
                     'strict':{name:score(test,name) for name in ('climatology','ridge_strict','ridge_calendar_spatial')},
                     'conditional':{name:score(common,name) for name in ('climatology','ridge_strict','persistence','ridge_history')} if 'ridge_history' in common else {}}
            fold_results.append(entry)
            if design=='expanding':
                test['fold'] = fold['name']
                test['persistence'],test['ridge_history'] = np.nan,np.nan
                if 'ridge_history' in common:
                    test.loc[common.index,['persistence','ridge_history']] = common[['persistence','ridge_history']]
                predictions.append(test)
                if len(cal[~cal.censored])>=30:
                    intervals,advisory = uncertainty(train,cal,test,STRICT_FEATURES)
                    interval_results[fold['name']],advisory_results[fold['name']] = intervals,advisory
            print(f'{design} {fold["name"]}: {len(test)} validation targets',flush=True)
    spatial = []
    geometry = splits.spatial_frame(data.study_dates(protocol),protocol)
    base_train = table[table.target_date.isin(geometry['train'])]
    base_test = table[table.target_date.isin(geometry['test'])]
    # Group assignments use metadata only; coverage checks use training only.
    for group in ('city','cluster','station_id','region'):
        assignment = splits.grouped_folds(table[group],k=10) if group!='region' else {g:g for g in table[group].unique()}
        for heldout in sorted(set(assignment.values())):
            members = [g for g,f in assignment.items() if f==heldout]
            train = base_train[~base_train[group].isin(members)]
            test = base_test[base_test[group].isin(members)].copy()
            if len(train[~train.censored])<30 or len(test)<30:
                spatial.append({'group':group,'holdout':str(heldout),'n':len(test),'status':'INSUFFICIENT_DATA'})
                continue
            if set(train[group]) & set(test[group]):
                raise ValueError('Spatial holdout overlaps')
            # Held-out station coverage never determines which held-out stations get scored.
            test['ridge_strict'] = fit_predict(train,[test],STRICT_FEATURES)[0]
            test['reference_all_stations'] = fit_predict(base_train,[test],STRICT_FEATURES)[0]
            spatial.append({'group':group,'holdout':str(heldout),'n':len(test),'held_out_groups':len(members),
                            'ridge_strict':score(test,'ridge_strict'),'reference_same_rows':score(test,'reference_all_stations')})
    combined = pd.concat(predictions,ignore_index=True) if predictions else pd.DataFrame()
    comparisons, subgroups = {},{}
    if len(combined):
        comparisons['ridge_strict_vs_climatology'] = paired(combined,'ridge_strict','climatology')
        comparisons['weather_ablation'] = paired(combined,'ridge_strict','ridge_calendar_spatial')
        common = combined.dropna(subset=['ridge_history','persistence'])
        if len(common):
            comparisons['ridge_history_vs_persistence'] = paired(common,'ridge_history','persistence')
            comparisons['history_ablation_conditional'] = paired(common,'ridge_history','ridge_strict')
        holm(comparisons)
        for field in ('season','region','y_category'):
            subgroups[field] = {str(name):{'n':len(group),'metrics':score(group,'ridge_strict') if len(group)>=30 else None} for name,group in combined.groupby(field)}
        combined[['station_id','city','target_date','y_aqi','y_category','censored','fold','climatology','ridge_strict','ridge_calendar_spatial','persistence','ridge_history']].to_csv(destination/'predictions.csv',index=False)
    result = {'generated_at':datetime.now(timezone.utc).isoformat(),'experiment':'NON_CAMS_PRELIMINARY','run_id':run_id,
              'status':'PRELIMINARY_COMPLETE_ON_PARTIAL_DATA' if quality['status']=='PARTIAL_COLLECTION' else 'PRELIMINARY_COMPLETE',
              'dataset_hash':quality['dataset_hash'],'data_version':quality['data_version'],'plan_hash':plan_hash,
              'code_sha256':code_hash,'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'protocol_sha256':protocol['_sha256'],'final_test_range':final['test_range'],'final_test_scored':False,
              'folds':fold_results,'spatial':spatial,'subgroups':subgroups,'paired_comparisons':comparisons,
              'uncertainty':interval_results,'advisory':advisory_results,
              'primary_baseline_complete':False,'CAMS_ARCHIVE_STATUS':'PENDING_MANUAL_ADS_CREDENTIAL',
              'legacy':'NOT_COMPARABLE: city-level 2015-2020 target and inputs differ; inherited results remain separate',
              'conditional_history_notice':PLAN['publication_caveat'],
              'advisory_limits':'Empirical validation only; not a vulnerable-cohort health benefit or exchangeability guarantee',
              'primary_experiments_blocked':['Raw CAMS','Direct ML versus raw CAMS','Residual Ridge','Residual LightGBM','Residual XGBoost','CAMS feature ablation','CAMS correction uncertainty/advisory'],
              'artifact':config.portable(destination/'results.json')}
    write_json(destination/'results.json',result)
    write_json(OUT/'preliminary_latest.json',result)
    return result


if __name__=='__main__':
    result=run()
    print(json.dumps({k:result[k] for k in ('status','run_id','final_test_scored','artifact')},indent=2))
