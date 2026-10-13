"""Protocol-bound DEVELOPMENT comparisons. There is no final-test execution path.

Partial cubes report incomplete folds, never shorten their declared windows.
Hyperparameters and early stopping use only the last 30 TRAINING dates.
Models and imputers never consume calibration/test labels during fitting.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from itertools import product
from pathlib import Path
import argparse
import inspect
from importlib.metadata import version
import json
import platform
import time
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from src import config
from src.research.calibration import metrics, splits, operational_features
from src.research.calibration.cams_acquisition import sha
from src.research.calibration.checkpoint import canonical_hash, write_json
from src.research.calibration.primary import guard_primary_row
from src.research.calibration.primary_dataset import read_development, final_start
from src.research.calibration.preliminary import climatology
from src.research.calibration.protocol import load
from src.research.calibration.validation import normalized_text_sha256
from src.research.calibration.statistics import paired, holm

ROOT=config.PROJECT_ROOT
LEARNERS=('ridge','lightgbm','xgboost')
METHODS=('climatology','persistence','raw_cams',*[f'{mode}_{family}' for family in LEARNERS for mode in ('residual','direct')])


def grids(family, protocol):
    settings=protocol['models']['hyperparameters']
    if family=='ridge':return [{'alpha':a} for a in settings['ridge_alpha']]
    cfg=settings[family]
    keys=('num_leaves','min_child_samples') if family=='lightgbm' else ('max_depth','min_child_weight')
    return [dict(zip(keys,values)) for values in product(*(cfg[k] for k in keys))]


def feature_groups(columns):
    groups={k:[] for k in 'ABCDE'}
    for name in columns:
        if name.startswith('cams_'):group='A'
        elif name.startswith(('obs','history_','bias_')):group='B'
        elif name.startswith('wx_'):group='C'
        elif name in ('doy_sin','doy_cos','month','dow','weekend','season_index'):group='D'
        elif name.startswith(('nbr','region_obs')) or name in ('latitude','longitude','elevation','cell_row','cell_column','cell_station_count','nearest_station_km'):group='E'
        else:raise ValueError('Unknown predictor group: '+name)
        groups[group].append(name)
    return groups


def audit_rows(frame, columns, protocol):
    if frame.empty:return
    if (pd.to_datetime(frame.target_date).dt.date >= final_start(protocol)).any():
        raise ValueError('Locked final date refused before fitting or diagnostics')
    if frame.duplicated(['station_id','target_date']).any():raise ValueError('Duplicate station/day')
    for raw in frame.to_dict('records'):
        row={k:None if pd.isna(v) else v for k,v in raw.items()}
        guard_primary_row(row,columns)


def exact_train(frame):
    return frame[frame.target_valid & ~frame.censored & frame.y_aqi.notna() & frame.cams_aqi_frozen.notna()]


def tuning_supported(train, dates):
    """Coverage eligibility alone cannot supply exact inner training labels."""
    inner, validation = splits.inner_validation(dates, 30)
    return len(exact_train(train[train.target_date.isin(inner)])) >= 30 and bool(
        len(exact_train(train[train.target_date.isin(validation)])))


@dataclass
class Fitted:
    imputer: object
    estimator: object
    columns: list
    residual: bool
    params: dict
    protocol: dict

    def predict(self, frame):
        if not len(frame):return np.empty(0)
        audit_rows(frame,self.columns,self.protocol)
        values=self.estimator.predict(self.imputer.transform(frame[self.columns]))
        return np.maximum(0,values+(frame.cams_aqi_frozen.to_numpy() if self.residual else 0))


def fit(train, columns, family, residual, params, protocol, validation=None, quantile=None):
    audit_rows(train,columns,protocol)
    if validation is not None:audit_rows(validation,columns,protocol)
    train=exact_train(train)
    if train.empty:raise ValueError('No exact training pairs')
    imputer=SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True)
    x=imputer.fit_transform(train[columns])
    y=train.y_aqi.to_numpy()-(train.cams_aqi_frozen.to_numpy() if residual else 0)
    cfg=protocol['models']['hyperparameters'].get(family,{})
    if family=='ridge':
        model=make_pipeline(StandardScaler(),Ridge(alpha=params['alpha']))
        model.fit(x,y)
    else:
        shared={'learning_rate':cfg['learning_rate'],'n_estimators':params.get('n_estimators',cfg['max_rounds']),
                'subsample':cfg['subsample'],'colsample_bytree':cfg['colsample_bytree'],
                'random_state':protocol['models']['seed'],'n_jobs':2}
        extra={k:v for k,v in params.items() if k!='n_estimators'}
        validation=exact_train(validation) if validation is not None else None
        kwargs={}
        if validation is not None and len(validation):
            vx=imputer.transform(validation[columns])
            vy=validation.y_aqi.to_numpy()-(validation.cams_aqi_frozen.to_numpy() if residual else 0)
            kwargs['eval_set']=[(vx,vy)]
        if family=='lightgbm':
            from lightgbm import LGBMRegressor, early_stopping
            model=LGBMRegressor(**shared,**extra,subsample_freq=1,verbosity=-1,metric='quantile' if quantile is not None else 'l1',
                                **({'objective':'quantile','alpha':quantile} if quantile is not None else {}))
            kwargs['eval_metric']='quantile' if quantile is not None else 'l1'
            if 'eval_set' in kwargs:
                kwargs['callbacks']=[early_stopping(cfg['early_stopping_rounds'],verbose=False)]
                if 'eval_X' in inspect.signature(model.fit).parameters:
                    kwargs['eval_X'],kwargs['eval_y']=kwargs.pop('eval_set')[0]
        elif family=='xgboost':
            from xgboost import XGBRegressor
            model=XGBRegressor(**shared,**extra,eval_metric='mae',**({'early_stopping_rounds':cfg['early_stopping_rounds']} if kwargs else {}))
            kwargs['verbose']=False
        else:raise ValueError('Unknown family')
        model.fit(x,y,**kwargs)
    return Fitted(imputer,model,list(columns),residual,dict(params),protocol)


def tune(train, train_dates, columns, family, residual, protocol):
    if not set(train.target_date).issubset(set(train_dates)):
        raise ValueError('Tuning frame contains a date outside the training window')
    inner_dates,validation_dates=splits.inner_validation(train_dates,30)
    inner=train[train.target_date.isin(inner_dates)]
    validation=exact_train(train[train.target_date.isin(validation_dates)])
    if len(exact_train(inner))<30 or not len(validation):raise ValueError('Insufficient inner training/validation')
    trials=[]
    for params in grids(family,protocol):
        model=fit(inner,columns,family,residual,params,protocol,validation)
        score=metrics.regression(validation.y_aqi,model.predict(validation))['mae']
        chosen=dict(params)
        if family=='lightgbm':chosen['n_estimators']=int(model.estimator.best_iteration_ or protocol['models']['hyperparameters'][family]['max_rounds'])
        if family=='xgboost':chosen['n_estimators']=int(model.estimator.best_iteration+1)
        trials.append({'params':chosen,'inner_mae':score})
    best=min(enumerate(trials),key=lambda item:(item[1]['inner_mae'],item[0]))[1]
    return fit(train,columns,family,residual,best['params'],protocol), {'selected':best,'trials':trials,
        'inner_train_range':[str(inner_dates[0]),str(inner_dates[-1])],
        'inner_validation_range':[str(validation_dates[0]),str(validation_dates[-1])],
        'tuning_outside_training':False}


def fixed_booster(train, dates, columns, protocol, quantile=None):
    if not set(train.target_date).issubset(set(dates)):
        raise ValueError('Fixed booster contains a nontraining date')
    inner,valid=splits.inner_validation(dates,30)
    params={'num_leaves':31,'min_child_samples':60}
    preliminary=fit(train[train.target_date.isin(inner)],columns,'lightgbm',True,params,protocol,
                    train[train.target_date.isin(valid)],quantile)
    params['n_estimators']=int(preliminary.estimator.best_iteration_ or protocol['models']['hyperparameters']['lightgbm']['max_rounds'])
    return fit(train,columns,'lightgbm',True,params,protocol,quantile=quantile)


def eligible(train, others, protocol):
    # Target-valid Severe days count for coverage eligibility, but never fitting.
    counts=train[train.target_valid].groupby('station_id').size()
    ids=counts[counts>=protocol['stations']['minimum_valid_target_days']].index
    return train[train.station_id.isin(ids)], [x[x.station_id.isin(ids)] for x in others]


def summarize(frame, name):
    return metrics.summary(frame.y_aqi,frame[name],frame.y_category,frame.censored)


def score_sets(frame):
    secondary=frame[frame.target_valid & frame.cams_aqi_frozen.notna()]
    primary=secondary[secondary.obs24_aqi.notna()]
    return {'primary':{m:summarize(primary,m) for m in METHODS},
            'secondary':{m:summarize(secondary,m) for m in METHODS if m!='persistence'},
            'primary_pair_keys_sha256':canonical_hash([(int(s),str(d)) for s,d in zip(primary.station_id,primary.target_date)]),
            'n_primary_rows':len(primary),'n_secondary_rows':len(secondary)}


def rolling(frame, columns, protocol):
    reports=[];predictions=[];calibration=[]
    folds=splits.rolling_folds(splits.calendar(protocol),protocol);splits.check(folds)
    dates=set(frame.target_date)
    for fold in folds:
        if fold['role']=='final_test':continue
        entry={k:v for k,v in fold.items() if k.endswith('_range') or k=='name'}
        train=frame[frame.target_date.isin(fold['train'])]
        cal=frame[frame.target_date.isin(fold['calibration'])]
        test=frame[frame.target_date.isin(fold['test'])]
        train,(cal,test)=eligible(train,[cal,test],protocol)
        missing=sorted(set(fold['train']+fold['calibration']+fold['test'])-dates)
        entry.update(eligible_training_stations=int(train.station_id.nunique()),missing_archive_dates=len(missing))
        if train.empty or not len(test[test.target_valid]) or missing or not tuning_supported(train,fold['train']):
            entry['status']='INSUFFICIENT_DATA_OR_ARCHIVE'
            reports.append(entry);continue
        cal=cal[cal.target_valid].copy();test=test[test.target_valid].copy()
        for part in (cal,test):
            part['raw_cams']=part.cams_aqi_frozen
            part['persistence']=part.obs24_aqi
            part['climatology']=climatology(train,part)
        tuning={}
        for family in LEARNERS:
            for residual in (True,False):
                name=('residual_' if residual else 'direct_')+family
                model,tuning[name]=tune(train,fold['train'],columns,family,residual,protocol)
                cal[name]=model.predict(cal);test[name]=model.predict(test)
        entry.update(status='EVALUATED_DEVELOPMENT',tuning=tuning,**score_sets(test))
        test['fold']=fold['name'];cal['fold']=fold['name']
        predictions.append(test);calibration.append(cal);reports.append(entry)
        print(json.dumps({'fold':fold['name'],'primary_pairs':entry['n_primary_rows']}),flush=True)
    return reports,(pd.concat(predictions,ignore_index=True) if predictions else pd.DataFrame()),(pd.concat(calibration,ignore_index=True) if calibration else pd.DataFrame())


def select(reports):
    used=[r for r in reports if r.get('status')=='EVALUATED_DEVELOPMENT' and r['n_primary_rows'] and r['primary']['raw_cams']['mae'] is not None]
    if not used:return {'status':'NO_ELIGIBLE_FOLDS','selected':None}
    means={m:float(np.mean([r['primary'][m]['mae'] for r in used])) for m in METHODS}
    # Baselines are reported; the locked carry-forward rule is raw CAMS versus
    # learned candidates, even when persistence is the stronger warning baseline.
    ordering=['residual_ridge','direct_ridge','residual_lightgbm','direct_lightgbm','residual_xgboost','direct_xgboost']
    best=min(ordering,key=lambda m:(means[m],ordering.index(m)))
    chosen=best if means[best]<means['raw_cams'] else 'raw_cams'
    return {'status':'DEVELOPMENT_CANDIDATE_ONLY','selected':chosen,'mean_fold_mae':means,
            'median_fold_mae':{m:float(np.median([r['primary'][m]['mae'] for r in used])) for m in METHODS},
            'evaluated_folds':len(used),'strongest_reported_baseline':min(('raw_cams','persistence','climatology'),key=means.get),
            'selection_rule':'locked lowest mean rolling-fold MAE; Ridge/residual ties; retain raw CAMS if no learned gain',
            'not_a_committed_selection_lock':True}


def preflight(frame, columns, protocol):
    audit_rows(frame,columns,protocol)
    groups=feature_groups(columns)
    if any(not v for v in groups.values()):raise ValueError('Required A-E feature group missing')
    if frame[frame.target_valid].matched_support_equals_frozen_support.eq(False).any():
        raise ValueError('Matched and frozen support differ; primary comparison needs review')
    coverage=[]
    for fold in splits.rolling_folds(splits.calendar(protocol),protocol):
        if fold['role']=='final_test':continue
        training=frame[frame.target_date.isin(fold['train'])]
        training,others=eligible(training,[frame[frame.target_date.isin(fold['test'])]],protocol)
        missing=len(set(fold['train']+fold['calibration']+fold['test'])-set(frame.target_date))
        coverage.append({'fold':fold['name'],'eligible_training_stations':int(training.station_id.nunique()),
                         'missing_archive_dates':missing,'can_fit':bool(len(training) and len(others[0][others[0].target_valid]) and not missing
                            and tuning_supported(training,fold['train']))})
    return {'feature_groups':groups,'folds':coverage,'final_test_accessed':False,
            'can_execute_any_fold':any(f['can_fit'] for f in coverage)}


def spatial(frame, columns, protocol):
    geometry=splits.spatial_frame(splits.calendar(protocol),protocol)
    base_train=frame[frame.target_date.isin(geometry['train'])]
    base_test=frame[frame.target_date.isin(geometry['test']) & frame.target_valid]
    base_train,(base_test,)=eligible(base_train,[base_test],protocol)
    if base_train.empty or base_test.empty or not tuning_supported(base_train,geometry['train']):
        return [{'status':'INSUFFICIENT_SPATIAL_DATA','geometry':{k:v for k,v in geometry.items() if k.endswith('_range')}}]
    missing=set(geometry['train']+geometry['test'])-set(frame.target_date)
    if missing:return [{'status':'INCOMPLETE_SPATIAL_ARCHIVE','missing_dates':len(missing)}]
    groups=feature_groups(columns)
    reference={}
    for regime in ('with_local_history','without_local_station'):
        use=columns if regime=='with_local_history' else [c for c in columns if c not in groups['B']]
        reference[regime]={}
        for family in LEARNERS:
            for residual in (True,False):
                name=('residual_' if residual else 'direct_')+family
                reference[regime][name],_=tune(base_train,geometry['train'],use,family,residual,protocol)
    metadata=frame[['station_id','cluster','region','city']].drop_duplicates('station_id')
    reports=[]
    for unit in ('cluster','station_id','region','city'):
        if unit=='region':
            assignments={name:i for i,name in enumerate(protocol['subgroups']['regions'])}
        else:assignments=splits.grouped_folds(metadata[unit],10,42)
        for number in range(6 if unit=='region' else 10):
            held=set(metadata.loc[metadata[unit].map(assignments)==number,'station_id'])
            training=base_train[~base_train.station_id.isin(held)]
            testing=base_test[base_test.station_id.isin(held)]
            for regime in ('with_local_history','without_local_station'):
                entry={'unit':unit,'holdout':number,'regime':regime,'held_station_count':len(held),
                       'status':'INSUFFICIENT_SPATIAL_DATA','city_holdout_is_sensitivity':unit=='city'}
                if not len(testing) or not tuning_supported(training,geometry['train']):reports.append(entry);continue
                use=columns if regime=='with_local_history' else [c for c in columns if c not in groups['B']]
                train=training.copy();test=testing.copy()
                if regime=='without_local_station':
                    donors=set(frame.station_id)-held
                    for part in (train,test):
                        neighbour=operational_features.neighbour_features(part,frame,donor_ids=donors)
                        for c in neighbour:part[c]=neighbour[c]
                audit_rows(train,use,protocol);audit_rows(test,use,protocol)
                test['raw_cams']=test.cams_aqi_frozen;test['persistence']=test.obs24_aqi
                test['climatology']=climatology(train,test)
                tuning={};reference_scores={}
                for family in LEARNERS:
                    for residual in (True,False):
                        name=('residual_' if residual else 'direct_')+family
                        model,tuning[name]=tune(train,geometry['train'],use,family,residual,protocol)
                        test[name]=model.predict(test)
                        test['reference_'+name]=reference[regime][name].predict(test)
                        common=test[test.obs24_aqi.notna()]
                        reference_scores[name]=summarize(common,'reference_'+name)
                entry.update(status='EVALUATED_DEVELOPMENT',training_stations=int(train.station_id.nunique()),
                             tuning=tuning,reference_primary=reference_scores,**score_sets(test))
                entry['seen_cluster_rows']=int(test.cluster.isin(set(train.cluster)).sum())
                entry['donor_policy']='all available pre-issue feeds' if regime=='with_local_history' else 'all held-out feeds removed; identical test predictors for held-out and all-station models'
                reports.append(entry)
    return reports


def ablation(frame, columns, protocol):
    groups=feature_groups(columns)
    variants={'A1':['A','C','D'],'A2':['A','B','D'],'A3':['A','B','C','D'],'A4':['A','B','C','D','E']}
    reports=[];predictions=[]
    for fold in splits.rolling_folds(splits.calendar(protocol),protocol):
        if fold['role']=='final_test':continue
        train=frame[frame.target_date.isin(fold['train'])]
        test=frame[frame.target_date.isin(fold['test']) & frame.target_valid]
        train,(test,)=eligible(train,[test],protocol)
        if train.empty or test.empty or set(fold['train']+fold['test'])-set(frame.target_date) or not tuning_supported(train,fold['train']):
            reports.append({'fold':fold['name'],'status':'INSUFFICIENT_DATA_OR_ARCHIVE'});continue
        test=test[test.obs24_aqi.notna()].copy()
        if test.empty:reports.append({'fold':fold['name'],'status':'NO_COMMON_PRIMARY_PAIRS'});continue
        test['A0']=test.cams_aqi_frozen
        entry={'fold':fold['name'],'status':'EVALUATED_DEVELOPMENT','A0':summarize(test,'A0')}
        for name,keep in variants.items():
            use=[c for group in keep for c in groups[group]]
            started=time.perf_counter()
            model=fixed_booster(train,fold['train'],use,protocol)
            trained=time.perf_counter();test[name]=model.predict(test);ended=time.perf_counter()
            entry[name]={**summarize(test,name),'training_seconds':trained-started,
                         'inference_seconds':ended-trained,'feature_count':len(use),
                         'configuration':'fixed 31 leaves/60 child samples; training-only early stopping; no hyperparameter search',
                         'fitted_rounds':model.params['n_estimators']}
        entry['A5']={'status':'UNAVAILABLE_HISTORICAL_FIRE_PUBLICATION_EVIDENCE','fire_admitted':False}
        test['fold']=fold['name'];predictions.append(test);reports.append(entry)
    return reports,(pd.concat(predictions,ignore_index=True) if predictions else pd.DataFrame())


def measured_sensitivity(frame, columns, *, lag_days=1, withheld=False):
    """Change only available measured inputs, never CAMS/weather or labels."""
    groups=feature_groups(columns)
    measured=groups['B']+[c for c in groups['E'] if c.startswith(('nbr','region_obs'))]
    provenance=['latest_measured_bin_end_utc','latest_daily_lag_date','latest_neighbour_bin_end_utc']
    out=frame.copy()
    if withheld:
        for name in measured:out[name]=np.nan
        for name in provenance:out[name]=None
        return out
    lookup=frame.set_index(['station_id','target_date'])
    keys=pd.MultiIndex.from_arrays([frame.station_id,frame.target_date-pd.to_timedelta(lag_days,unit='D')])
    # date arithmetic avoids shifting over missing rows. Reindex keys use date
    # objects, matching the immutable development table.
    from datetime import timedelta
    keys=pd.MultiIndex.from_arrays([frame.station_id,[d-timedelta(days=lag_days) for d in frame.target_date]])
    source=lookup.reindex(keys)
    for name in measured+provenance:
        if name in source:out[name]=source[name].to_numpy()
    return out


def stale_feed(frame, columns, reports, selected, protocol):
    result=[]
    if selected is None:return result
    altered={name:measured_sensitivity(frame,columns,withheld=name=='withheld') for name in ('lagged_24h','withheld')}
    fold_map={r['name']:r for r in reports if r.get('status')=='EVALUATED_DEVELOPMENT'}
    for fold in splits.rolling_folds(splits.calendar(protocol),protocol):
        if fold['role']=='final_test' or fold['name'] not in fold_map:continue
        train=frame[frame.target_date.isin(fold['train'])]
        test=frame[frame.target_date.isin(fold['test']) & frame.target_valid & frame.obs24_aqi.notna()]
        train,(test,)=eligible(train,[test],protocol)
        if selected!='raw_cams':
            mode,family=selected.split('_',1)
            params=fold_map[fold['name']]['tuning'][selected]['selected']['params']
            model=fit(train,columns,family,mode=='residual',params,protocol)
        for name,source in altered.items():
            part=source.loc[test.index]
            part=part.copy()
            part['selected_prediction']=part.cams_aqi_frozen if selected=='raw_cams' else model.predict(part)
            result.append({'fold':fold['name'],'sensitivity':name,'same_original_primary_pairs':True,
                           'retuned_or_recalibrated':False,**summarize(part,'selected_prediction')})
    return result


def run(execute=False):
    protocol=load()
    alignment=json.loads((ROOT/'results/research/cams_development_alignment.json').read_text())
    if sha(ROOT/alignment['table'])!=alignment['sha256']:raise ValueError('Alignment checksum mismatch')
    frame=read_development(ROOT/alignment['table'],protocol)
    if len(frame)!=alignment['rows']:raise ValueError('Filtered row count differs from alignment manifest')
    columns=alignment['predictors']
    audit=preflight(frame,columns,protocol)
    plan={'experiment':'GENUINE_CAMS_DEVELOPMENT','version':'primary-development-runner-v1',
          'protocol_sha256':protocol['_sha256'],'dataset_sha256':alignment['sha256'],
          'feature_version':alignment['feature_version'],'features':columns,
          'seed':42,'methods':METHODS,'hyperparameters':protocol['models']['hyperparameters'],
          'runtime':{'python':platform.python_version(),**{name:version(name) for name in ('numpy','pandas','scikit-learn','lightgbm','xgboost','pyarrow')}},
          'station_minimum':protocol['stations']['minimum_valid_target_days'],
          'source_sha256':normalized_text_sha256(Path(__file__)),
          'dependency_source_sha256':{name:normalized_text_sha256(Path(__file__).with_name(name+'.py'))
              for name in ('primary','primary_dataset','primary_uncertainty','operational_features','splits','metrics','statistics','availability')},
          'final_test':'SEALED; no executor in this module'}
    identity=canonical_hash(plan);folder=ROOT/'results/research/primary_development'/identity
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'plan.json').exists() and json.loads((folder/'plan.json').read_text())!=json.loads(json.dumps(plan)):
        raise ValueError('Immutable experiment plan differs')
    if not (folder/'plan.json').exists():write_json(folder/'plan.json',plan)
    report={'experiment':plan['experiment'],'protocol_sha256':protocol['_sha256'],
            'dataset_sha256':alignment['sha256'],'run_id':identity,'preflight':audit,
            'status':'BLOCKED_NO_ELIGIBLE_FOLDS' if not audit['can_execute_any_fold'] else 'PREPARED',
            'final_test_scored':False,'model_selection_lock_created':False,'fitting_performed':False,
            'remaining_stages':['spatial comparisons','ablation','uncertainty/advisory','paired statistics','selection lock and final-executor audit']}
    if execute and audit['can_execute_any_fold']:
        immutable=folder/'results.json'
        if immutable.exists():
            prior=json.loads(immutable.read_text())
            for output in prior.get('outputs',{}).values():
                if sha(ROOT/output['file'])!=output['sha256']:raise ValueError('Immutable prediction checksum differs')
            return prior
        reports,predictions,calibration=rolling(frame,columns,protocol)
        selection=select(reports)
        point=selection['selected']
        spatial_results=spatial(frame,columns,protocol)
        ablations,ablation_predictions=ablation(frame,columns,protocol)
        stale=stale_feed(frame,columns,reports,point,protocol)
        six=frame.copy();six['cams_aqi_frozen']=six.cams_six
        six_reports,_,_=rolling(six,columns,protocol)
        intervals={};comparisons={};feature_comparisons={}
        if point is not None:
            from src.research.calibration.primary_uncertainty import evaluate
            for fold in splits.rolling_folds(splits.calendar(protocol),protocol):
                if fold['role']=='final_test':continue
                test=predictions[predictions.fold==fold['name']]
                cal=calibration[calibration.fold==fold['name']]
                if test.empty or cal.empty:continue
                train=frame[frame.target_date.isin(fold['train'])]
                train,(cal,test)=eligible(train,[cal,test],protocol)
                if len(exact_train(cal))<30:
                    intervals[fold['name']]={'status':'INSUFFICIENT_EXACT_CALIBRATION'};continue
                intervals[fold['name']]=evaluate(train,cal,test,columns,point,fold['train'],protocol)
            common=predictions[predictions.obs24_aqi.notna()]
            comparisons=holm({f'{point}_vs_{name}':paired(common,point,name)
                              for name in ('raw_cams','persistence','climatology','residual_ridge')})
            if not ablation_predictions.empty:
                feature_comparisons={f'{name}_vs_A4':paired(ablation_predictions,name,'A4') for name in ('A1','A2','A3')}
        # Predictions are development only, stored outside Git with checksums.
        datafolder=ROOT/'data/research/cams_operational/experiments'/identity
        datafolder.mkdir(parents=True,exist_ok=True)
        outputs={}
        for name,table in [('predictions',predictions),('calibration',calibration),('ablation_predictions',ablation_predictions)]:
            path=datafolder/(name+'.parquet')
            if path.exists():raise ValueError('Interrupted development artifact exists; audit before retry')
            table.to_parquet(path,index=False);outputs[name]={'file':str(path.relative_to(ROOT)),'sha256':sha(path)}
        acquisition=json.loads((ROOT/'results/research/cams_development_acquisition.json').read_text())
        report.update(status='DEVELOPMENT_ANALYSES_COMPLETE_LOCK_AUDIT_PENDING' if acquisition['complete'] else 'PARTIAL_DEVELOPMENT_ANALYSES_ARCHIVE_INCOMPLETE',
                      folds=reports,spatial=spatial_results,ablation=ablations,uncertainty_advisory=intervals,
                      stale_feed_sensitivity=stale,six_pollutant_sensitivity=six_reports,
                      six_pollutant_sensitivity_used_for_selection=False,
                      statistical_comparison=comparisons,ablation_comparisons=feature_comparisons,
                      candidate_selection=selection,fitting_performed=True,outputs=outputs,
                      archive_complete=acquisition['complete'],
                      remaining_stages=['model selection/configuration lock','clean-clone primary reproduction','one-shot final-executor audit'])
        report['subgroups']={}
        if point is not None:
            for field in ('region','season','large_city'):
                if field not in predictions:continue
                report['subgroups'][field]={}
                for name,part in predictions.groupby(field):
                    report['subgroups'][field][str(name)]=summarize(part,point) if len(part)>=protocol['subgroups']['minimum_n'] else {'n':len(part),'status':'BELOW_MINIMUM_N_METRICS_WITHHELD'}
        write_json(immutable,report)
    write_json(folder/'preflight.json',report)
    write_json(ROOT/'results/research/primary_development_preflight.json',report)
    print(json.dumps({'status':report['status'],'fitting_performed':report['fitting_performed'],'final_test_scored':False}))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-development',action='store_true')
    run(parser.parse_args().run_development)
