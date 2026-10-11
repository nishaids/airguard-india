"""Offline, date-blocked experiments. This module never runs in user requests."""
from __future__ import annotations
import math
import time
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from src.research.protocol import PROTOCOL, aware

EDGES = [50,100,200,300,400]
LABELS = ['Good','Satisfactory','Moderate','Poor','Very Poor','Severe']


def bands(values):
    return np.digitize(np.asarray(values,dtype=float),EDGES,right=True)


def scores(y,pred):
    y,pred = np.asarray(y,dtype=float),np.asarray(pred,dtype=float)
    if not len(y): return {'n':0,'mae':None,'rmse':None,'bias':None,'r2':None,'category_accuracy':None,'macro_f1':None,'within_one_category':None,'severe_recall':None,'severe_precision':None,'extreme_day_mae':None}
    if len(y)!=len(pred) or not np.isfinite(y).all() or not np.isfinite(pred).all(): raise ValueError('Invalid prediction pair')
    actual,forecast = bands(y),bands(pred)
    severe = actual==5; high = actual>=3
    return {'n':len(y),'mae':float(mean_absolute_error(y,pred)), 'rmse':float(math.sqrt(mean_squared_error(y,pred))),
        'bias':float((pred-y).mean()), 'r2':float(r2_score(y,pred)) if len(y)>1 and np.var(y)>0 else None,
        'category_accuracy':float((actual==forecast).mean()),'macro_f1':float(f1_score(actual,forecast,labels=range(6),average='macro',zero_division=0)),
        'within_one_category':float((np.abs(actual-forecast)<=1).mean()),
        'severe_recall':float((forecast[severe]==5).mean()) if severe.any() else None,
        'severe_precision':float((actual[forecast==5]==5).mean()) if (forecast==5).any() else None,
        'extreme_day_mae':float(np.abs(pred[high]-y[high]).mean()) if high.any() else None,
        'underprediction_rate':float((pred<y).mean()),'overprediction_rate':float((pred>y).mean())}


def severity(y,pred):
    actual=bands(y)
    return {label:scores(np.asarray(y)[actual==i],np.asarray(pred)[actual==i]) for i,label in enumerate(LABELS)}


def folds(frame, *, expanding=True, protocol=None):
    """Whole dates stay together. No target available after next partition's cutoff."""
    dates = sorted(frame.target_date.unique())
    cfg = (protocol or PROTOCOL)['splits']; tr,ca,te,gap=cfg['training_days'],cfg['calibration_days'],cfg['test_days'],cfg['embargo_days']
    # The final window belongs to this versioned protocol, not a mutable default.
    final_start = len(dates)-cfg.get('final_test_days',te)
    out=[]
    for test_start in range(tr+ca+2*gap,final_start, cfg['step_days']):
        if test_start+te>final_start: break
        train_end=test_start-ca-2*gap; cal_start=train_end+gap; cal_end=test_start-gap
        out.append(_fold(frame,dates,0 if expanding else max(0,train_end-tr),train_end,cal_start,cal_end,test_start,test_start+te,'validation'))
    if final_start>=tr+ca+2*gap:
        train_end=final_start-ca-2*gap
        out.append(_fold(frame,dates,0 if expanding else max(0,train_end-tr),train_end,train_end+gap,final_start-gap,final_start,len(dates),'final_test'))
    return out


def _fold(frame,dates,t0,t1,c0,c1,e0,e1,role):
    partitions=[]
    for start,end in ((t0,t1),(c0,c1),(e0,e1)):
        partitions.append(frame.index[frame.target_date.isin(dates[start:end])].to_numpy())
    for a,b in zip(partitions,partitions[1:]):
        cutoff=min(aware(x) for x in frame.loc[b,'issue_time'])
        if any(aware(x)>=cutoff for x in frame.loc[a,'target_available_at']):
            raise ValueError('Split leakage: previous outcomes unavailable before next cutoff')
    return {'role':role,'train':partitions[0],'calibration':partitions[1],'test':partitions[2],
        'windows':{'train':[str(dates[t0]),str(dates[t1-1])],'calibration':[str(dates[c0]),str(dates[c1-1])],'test':[str(dates[e0]),str(dates[e1-1])]}}


def paired_block_bootstrap(y,cams,pred,dates,block_days=7,repetitions=1000,seed=42):
    """Resample contiguous date blocks; all stations on a date travel together."""
    frame=pd.DataFrame({'day':dates,'improvement':np.abs(np.asarray(cams)-y)-np.abs(np.asarray(pred)-y)})
    unique=sorted(frame.day.unique()); daily=[frame[frame.day==d].improvement.to_numpy() for d in unique]
    delta=float(frame.improvement.mean())
    if len(unique)<2*block_days:return {'n':len(frame),'days':len(unique),'absolute_mae_improvement':delta,'ci95':None,'status':'INSUFFICIENT_DATE_BLOCKS','p_value':None}
    rng=np.random.default_rng(seed); samples=[]
    for _ in range(repetitions):
        selected=[]
        while len(selected)<len(unique):
            start=int(rng.integers(0,len(unique)-block_days+1)); selected.extend(range(start,start+block_days))
        samples.append(np.concatenate([daily[i] for i in selected[:len(unique)]]).mean())
    return {'n':len(frame),'days':len(unique),'absolute_mae_improvement':delta,
        'percentage_mae_improvement':100*delta/float(np.abs(np.asarray(cams)-y).mean()) if np.abs(np.asarray(cams)-y).mean() else None,
        'ci95':np.quantile(samples,[.025,.975]).tolist(),'block_days':block_days,'repetitions':repetitions,
        'p_value':None,'note':'Percentile moving-block CI; no formal DM test; station correlation preserved by day.'}


def estimator(name,quantile=None):
    if name=='ridge':return make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler(),Ridge(alpha=10))
    if name=='lightgbm':
        from lightgbm import LGBMRegressor
        kwargs={'objective':'quantile','alpha':quantile} if quantile else {'objective':'regression'}
        return LGBMRegressor(n_estimators=150,max_depth=4,num_leaves=15,min_child_samples=20,learning_rate=.05,random_state=42,n_jobs=2,verbosity=-1,**kwargs)
    if name=='xgboost':
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=150,max_depth=4,learning_rate=.05,reg_lambda=10,subsample=1,colsample_bytree=1,random_state=42,n_jobs=2,objective='reg:squarederror')
    raise ValueError('Unknown model family')


def correction(train,test,columns,family='ridge',direct=False):
    model=estimator(family); started=time.perf_counter()
    outcome=train.target_aqi if direct else train.target_aqi-train.cams_aqi
    model.fit(train[columns],outcome)
    fit=time.perf_counter()-started; started=time.perf_counter()
    pred=model.predict(test[columns])+(0 if direct else test.cams_aqi.to_numpy())
    # Physical floor only; do not invent a concentration endpoint for Severe.
    clipped=int((pred<0).sum()); pred=np.maximum(0,pred)
    return pred,model,{'fit_seconds':fit,'inference_ms':1000*(time.perf_counter()-started),'clipped_below_zero':clipped}


def baseline_predictions(train,test):
    # Train-only station/month climatology; no use of calibration/test outcomes.
    local=train.groupby(['station_pk','month']).target_aqi.median()
    months=train.groupby('month').target_aqi.median(); overall=float(train.target_aqi.median())
    climate=[local.get((r.station_pk,r.month),months.get(r.month,overall)) for r in test.itertuples()]
    if test.B_persistence_aqi.isna().any():raise ValueError('Common evaluation rows require issue-time persistence')
    return {'B0_climatology':np.asarray(climate),'B1_persistence':test.B_persistence_aqi.to_numpy(),'B2_raw_CAMS':test.cams_aqi.to_numpy()}


def interval_results(y,lower,upper,frame,nominal):
    result={'nominal_coverage':nominal,'n':len(y),'empirical_coverage':float(((y>=lower)&(y<=upper)).mean()),'mean_width':float((upper-lower).mean()),'by_category':{},'by_city':{},'by_season':{}}
    for key,group in [('by_category',bands(y)),('by_city',frame.city.to_numpy()),('by_season',frame.season.to_numpy())]:
        for g in np.unique(group):
            mask=group==g;label=LABELS[int(g)] if key=='by_category' else str(g)
            result[key][label]={'n':int(mask.sum()),'coverage':float(((y[mask]>=lower[mask])&(y[mask]<=upper[mask])).mean()),'width':float((upper[mask]-lower[mask]).mean())}
    result['Severe']=result['by_category'].get('Severe',{'n':0,'coverage':None,'width':None})
    result['guarantee']='Empirical time-ordered evaluation; exchangeability is not established.'
    return result


def cqr(train,cal,test,columns,coverage=.9):
    alpha=1-coverage; low=estimator('lightgbm',alpha/2); high=estimator('lightgbm',1-alpha/2)
    residual=train.target_aqi-train.cams_aqi
    low.fit(train[columns],residual);high.fit(train[columns],residual)
    def pair(part):
        a=low.predict(part[columns])+part.cams_aqi.to_numpy();b=high.predict(part[columns])+part.cams_aqi.to_numpy()
        return np.minimum(a,b),np.maximum(a,b)
    cl,ch=pair(cal); ll,hh=pair(test)
    # Collapse to daily maxima so simultaneous station errors do not inflate calibration n.
    errors=np.maximum.reduce([cl-cal.target_aqi.to_numpy(),cal.target_aqi.to_numpy()-ch,np.zeros(len(cal))])
    daily=pd.Series(errors,index=cal.target_date).groupby(level=0).max().to_numpy()
    rank=math.ceil((len(daily)+1)*coverage)
    if rank>len(daily):raise ValueError('Insufficient calibration dates for finite conformal interval')
    q=float(np.sort(daily)[rank-1]);lower=np.maximum(0,ll-q);upper=np.maximum(lower,hh+q)
    return lower,upper,{'calibration_days':len(daily),'widening':q,**interval_results(test.target_aqi.to_numpy(),lower,upper,test,coverage)}


def warning_scores(y,pred):
    actual,issued=bands(y),bands(pred)
    if not len(actual):return {'n':0,'underwarning_rate':None,'overwarning_rate':None,'severity_distance':None}
    return {'n':len(actual),'underwarning_rate':float((issued<actual).mean()),'overwarning_rate':float((issued>actual).mean()),
        'severity_distance':float(np.abs(issued-actual).mean()),'category_distribution':{LABELS[i]:int((actual==i).sum()) for i in range(6)}}


def select_policy(y,predictions,dates,target,protocol=None):
    """Calibration-only finite candidate selection. Serial dependence limits guarantees."""
    from scipy.stats import beta
    policy=(protocol or PROTOCOL)['advisory']
    candidates=[];confidence_alpha=.05/max(1,len(predictions)*len(policy['underwarning_targets']))
    for q,pred in predictions.items():
        errors=pd.Series(bands(pred)<bands(y),index=dates).groupby(level=0).max()
        n,k=len(errors),int(errors.sum());bound=float(beta.ppf(1-confidence_alpha,k+1,n-k)) if k<n else 1.
        candidates.append({'quantile':float(q),'days':n,'underwarning_upper_bound':bound,**warning_scores(y,pred)})
    accepted=[x for x in candidates if x['days']>=policy['minimum_calibration_days'] and x['underwarning_upper_bound']<=target]
    chosen=min(accepted,key=lambda x:(x['overwarning_rate'],x['quantile'])) if accepted else None
    return {'target':target,'selected':chosen,'candidates':candidates,'status':'EMPIRICAL_CANDIDATE' if chosen else 'RISK_CONTROL_NOT_ESTABLISHED',
        'note':'Bonferroni binomial screen on date-max errors; independence of dates is unproven. This is not a time-series risk guarantee or a clinical threshold.'}


def drift(reference,current):
    from scipy.stats import ks_2samp
    a=np.asarray(reference,dtype=float);b=np.asarray(current,dtype=float)
    missing={'reference_missingness':float((~np.isfinite(a)).mean()) if len(a) else None,'current_missingness':float((~np.isfinite(b)).mean()) if len(b) else None}
    a=a[np.isfinite(a)];b=b[np.isfinite(b)]
    if min(len(a),len(b))<30:return {**missing,'n_reference':len(a),'n_current':len(b),'status':'INSUFFICIENT_DATA','psi':None,'ks_statistic':None}
    edges=np.unique(np.quantile(a,np.linspace(0,1,11)))
    if len(edges)<3:return {**missing,'status':'DEGENERATE_REFERENCE','psi':None,'ks_statistic':float(ks_2samp(a,b).statistic)}
    edges[0],edges[-1]=-np.inf,np.inf
    p=np.maximum(np.histogram(a,edges)[0]/len(a),1e-6);q=np.maximum(np.histogram(b,edges)[0]/len(b),1e-6)
    return {**missing,'n_reference':len(a),'n_current':len(b),'psi':float(((q-p)*np.log(q/p)).sum()),'ks_statistic':float(ks_2samp(a,b).statistic),'status':'DESCRIPTIVE','note':'No causal interpretation; station/season mismatch and serial dependence must be assessed.'}


def evaluate(frame, protocol=None):
    """Fixed estimators; validation selects configuration; final test evaluated once."""
    protocol=protocol or PROTOCOL
    configurations={'A0_CAMS':('A',),'A1_CAMS_weather':('A','C','D'),'A2_CAMS_station':('A','B','D'),
        'A3_CAMS_weather_station':('A','B','C','D'),'A4_with_spatial':('A','B','C','D','E')}
    split=folds(frame,protocol=protocol);validation=[x for x in split if x['role']=='validation'];final=[x for x in split if x['role']=='final_test']
    if not validation or not final: return {'status':'INSUFFICIENT_ISSUE_TIME_PAIRS','n':len(frame),'folds':[],'metrics':None}
    results=[];validation_mae={name:[] for name in configurations}
    # Also report bounded rolling windows independently of expanding-window folds.
    schedules=[('expanding',x) for x in validation]+[('rolling',x) for x in folds(frame,expanding=False,protocol=protocol) if x['role']=='validation']
    for scheme,fold in schedules:
        train,test=frame.loc[fold['train']],frame.loc[fold['test']]; record={'scheme':scheme,'role':fold['role'],'windows':fold['windows'],'models':{}}
        for name,pred in baseline_predictions(train,test).items():record['models'][name]=scores(test.target_aqi,pred)
        for name,groups in configurations.items():
            cols=[c for c in frame if any(c.startswith(g+'_') for g in groups)]
            pred,_,complexity=correction(train,test,cols,'lightgbm');record['models'][name]={**scores(test.target_aqi,pred),**complexity}
            if scheme=='expanding':validation_mae[name].append(record['models'][name]['mae'])
        results.append(record)
    chosen=min(validation_mae,key=lambda k:np.mean(validation_mae[k]));columns=[c for c in frame if any(c.startswith(g+'_') for g in configurations[chosen])]
    fold=final[0];train,cal,test=[frame.loc[fold[k]] for k in ('train','calibration','test')]
    predictions=baseline_predictions(train,test);models={};complexities={}
    for family,direct,name in [('ridge',False,'B4_ridge_residual'),('lightgbm',False,'B5_LightGBM_residual'),('xgboost',False,'B6_XGBoost_residual'),('lightgbm',True,'LightGBM_direct')]:
        predictions[name],models[name],complexities[name]=correction(train,test,columns,family,direct)
    y=test.target_aqi.to_numpy();point=predictions['B5_LightGBM_residual']
    summary={name:{**scores(y,p),**complexities.get(name,{})} for name,p in predictions.items()}
    spatial=[]
    for grouping in ('city','station_pk'):
        for group in sorted(test[grouping].unique(),key=str):
            keep=train[grouping]!=group;held=test[grouping]==group
            if keep.sum()<90 or not held.any():continue
            pred,_,_=correction(train[keep],test[held],columns,'lightgbm')
            spatial.append({'grouping':grouping,'held_out':str(group),'training_stations':int(train[keep].station_pk.nunique()),**scores(y[held],pred)})
    uncertainty={};intervals={}
    for coverage in protocol['interval_coverages']:
        lo,hi,report=cqr(train,cal,test,columns,coverage);uncertainty[str(coverage)]=report;intervals[str(coverage)]=(lo,hi)
    policy_cal={};policy_test={}
    for q in protocol['advisory']['candidate_quantiles']:
        model=estimator('lightgbm',q);model.fit(train[columns],train.target_aqi-train.cams_aqi)
        policy_cal[q]=np.maximum(0,model.predict(cal[columns])+cal.cams_aqi.to_numpy());policy_test[q]=np.maximum(0,model.predict(test[columns])+test.cams_aqi.to_numpy())
    advisory={}
    for cohort,target in protocol['advisory']['underwarning_targets'].items():
        policy=select_policy(cal.target_aqi.to_numpy(),policy_cal,cal.target_date,target,protocol)
        chosen_policy=policy['selected'];advisory[cohort]={'calibration':policy,'median_test':warning_scores(y,policy_test[.5]),
            'selected_test':warning_scores(y,policy_test[chosen_policy['quantile']]) if chosen_policy else None}
    rows=[]
    for i,(_,row) in enumerate(test.iterrows()):
        rows.append({'station_pk':row.station_pk,'city':row.city,'target_date':row.target_date,'measured_aqi':y[i],
            'cams_aqi':predictions['B2_raw_CAMS'][i],'airguard_aqi':point[i],
            'interval80':[intervals['0.8'][0][i],intervals['0.8'][1][i]],'interval90':[intervals['0.9'][0][i],intervals['0.9'][1][i]]})
    return {'status':'EVALUATED_NOT_DEPLOYED','selected_features':chosen,'features':columns,'folds':results,'final_windows':fold['windows'],
        'final_test':summary,'comparison':paired_block_bootstrap(y,predictions['B2_raw_CAMS'],point,test.target_date),
        'severity':{name:severity(y,p) for name,p in predictions.items()},'spatial':spatial,'uncertainty':uncertainty,'advisory':advisory,
        'predictions':rows,'A5_FIRMS':'PENDING: issue-time fire snapshots and ablation required; excluded',
        'B3_legacy':'Not applicable to modern operational station pairs without separate feature/protocol validation',
        'deployment':'Disabled; successful average error alone does not establish spatial, extreme or uncertainty support.'}
