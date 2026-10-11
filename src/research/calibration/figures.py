"""Scientific preliminary-study plots, generated only from immutable results."""
import json
import hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src import config
from src.research.calibration.checkpoint import OUT, write_json


def generate():
    latest=json.loads((OUT/'preliminary_latest.json').read_text())
    result_path=config.PROJECT_ROOT/latest['artifact']
    result=json.loads(result_path.read_text())
    if result!=latest or result['final_test_scored'] is not False:
        raise ValueError('Figures require an immutable preliminary result with the final test sealed')
    destination=OUT/'preliminary'/result['run_id']
    folds=[f for f in result['folds'] if f['design']=='expanding' and f.get('strict')]
    fig,axes=plt.subplots(2,2,figsize=(11,7.5),layout='constrained')
    colors=['#5c677d','#006d77','#b5651d']
    x=np.arange(len(folds))+1
    for name,label,color in zip(('climatology','ridge_calendar_spatial','ridge_strict'),
                               ('Climatology','Calendar + coordinates Ridge','Weather + calendar + coordinates Ridge'),colors):
        axes[0,0].plot(x,[f['strict'][name]['mae'] for f in folds],marker='o',ms=4,label=label,color=color)
    axes[0,0].set(xlabel='Expanding validation fold',ylabel='Exact-target MAE (AQI)',title='Chronological preliminary baselines')
    axes[0,0].legend(fontsize=7)
    entries=[(k,v) for k,v in result['paired_comparisons'].items() if v.get('ci95')]
    for i,(name,value) in enumerate(entries):
        delta=value['mae_difference'];lo,hi=value['ci95']
        axes[0,1].plot([lo,hi],[i,i],lw=3,color='#006d77')
        axes[0,1].scatter([delta],[i],s=25,color='#003c44')
    labels={'ridge_strict_vs_climatology':'Weather Ridge − climatology',
            'weather_ablation':'Weather Ridge − calendar Ridge',
            'ridge_history_vs_persistence':'History Ridge − persistence*',
            'history_ablation_conditional':'History Ridge − same-training strict Ridge*'}
    axes[0,1].set_yticks(range(len(entries)),[labels.get(k,k) for k,_ in entries],fontsize=7)
    axes[0,1].axvline(0,color='#555',lw=1,ls='--')
    axes[0,1].set(xlabel='Paired MAE difference (AQI); negative favours first',title='95% seven-day block intervals')
    methods=[('split_0.8','Split 80%'),('split_0.9','Split 90%'),('cqr_0.9','CQR 90%')]
    for (key,label),color in zip(methods,colors):
        points=[(i+1,result['uncertainty'].get(f['fold'],{}).get(key,{}).get('coverage_exact')) for i,f in enumerate(folds)]
        points=[(a,b) for a,b in points if b is not None]
        if points:
            axes[1,0].plot(*zip(*points),marker='o',ms=4,label=label,color=color)
    for target in (.8,.9):axes[1,0].axhline(target,color='#888',ls=':',lw=.8)
    axes[1,0].set(xlabel='Expanding validation fold',ylabel='Exact-target interval coverage',ylim=(0,1),
                  title='Calibration windows precede validation')
    axes[1,0].legend(fontsize=7)
    for name,label,color in zip(('climatology','ridge_strict'),('Climatology','Weather Ridge'),colors):
        points=[(i+1,f['strict'][name]['censored_severe']['share_forecast_below_401']) for i,f in enumerate(folds)]
        points=[(a,b) for a,b in points if b is not None]
        if points:axes[1,1].plot(*zip(*points),marker='o',ms=4,label=label,color=color)
    axes[1,1].set(xlabel='Expanding validation fold',ylabel='Share below 401 on censored Severe days',ylim=(0,1.05),
                  title='Severe lower bounds: no fabricated regression error')
    axes[1,1].legend(fontsize=7)
    for ax in axes.flat:ax.grid(alpha=.15)
    fig.suptitle('Stream B: NON-CAMS preliminary study — locked final test unscored',fontsize=13)
    fig.supxlabel('* Measured-history sensitivity assumes historical feed latency.\n'
                  'Intervals and warnings are empirical; no CAMS-improvement or health-benefit claim.',fontsize=8)
    png,pdf=destination/'preliminary_diagnostics.png',destination/'preliminary_diagnostics.pdf'
    fig.savefig(png,dpi=180)
    fig.savefig(pdf,metadata={'Title':'AirGuard non-CAMS preliminary diagnostics'})
    plt.close(fig)
    report={'run_id':result['run_id'],'dataset_hash':result['dataset_hash'],'final_test_scored':False,
        'result_artifact_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest(),
        'files':{config.portable(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (png,pdf)}}
    write_json(destination/'figures.json',report)
    return report


if __name__=='__main__':print(json.dumps(generate(),indent=2))
