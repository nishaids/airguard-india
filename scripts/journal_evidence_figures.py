"""Publication figures from immutable preliminary artifacts, not primary results."""
import json
import hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from src.research.calibration.checkpoint import write_json

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=json.loads((ROOT/'results/research/preliminary_latest.json').read_text())
    if p!=json.loads((ROOT/p['artifact']).read_text()) or p['final_test_scored']:
        raise ValueError('Only the immutable non-CAMS development artifact is allowed')
    out=ROOT/'paper/figures'; out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':9,'pdf.fonttype':42})
    fig,ax=plt.subplots(figsize=(6.8,2.8),layout='constrained')
    cats=['Good','Satisfactory','Moderate','Poor','Very Poor']
    for offset,method,color in [(-.18,'split_0.8','#176B87'),(.18,'split_0.9','#A54C26')]:
        r=p['uncertainty']['fold_01'][method]
        coverage=[r['y_category'][str(float(i))]['coverage'] for i in range(5)]
        ax.bar(np.arange(5)+offset,[v if v is not None else np.nan for v in coverage],.35,color=color,label=f"Nominal {r['nominal']:.0%}")
        ax.axhline(r['nominal'],ls='--',color=color,lw=.8)
    counts=[p['uncertainty']['fold_01']['split_0.8']['y_category'][str(float(i))]['n_exact'] for i in range(5)]
    ax.set_xticks(range(5),[f'{c}\nn={n}' for c,n in zip(cats,counts)])
    ax.set(ylim=(0,1.04),ylabel='Exact-target empirical coverage',title='NON-CAMS preliminary: first development fold')
    ax.text(3,.3,'Withheld\nn < 30',ha='center',fontsize=8)
    ax.text(4,.09,'Both 0%',ha='center',fontsize=8)
    ax.legend(loc='lower left',fontsize=8);fig.savefig(out/'coverage_vs_severity.pdf');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.8,2.8),layout='constrained')
    for method,color in [('split_0.8','#176B87'),('split_0.9','#A54C26')]:
        values=[v[method]['mean_width'] for v in p['uncertainty'].values()]
        ax.plot(range(1,len(values)+1),values,'o-',color=color,label=method.replace('split_','Nominal '))
    ax.set(xlabel='Development fold',ylabel='Mean interval width (AQI units)',title='NON-CAMS preliminary: split-conformal interval widths')
    ax.legend();ax.grid(alpha=.2);fig.savefig(out/'interval_widths.pdf');plt.close(fig)
    for name,labels in [('data_pipeline',['Archived CAMS run\n00:00 UTC D-1','Measurements end\n17:00 IST D-1','Issue snapshot\n20:00 IST D-1','Target day D\n00:00–24:00 IST']),
                        ('model_workflow',['CAMS + pre-issue\nhistory/weather','Direct or residual\nRidge / LGBM / XGB','Rolling + spatial\ncalibration/tests','Selection lock\nthen approval gate'])]:
        fig,ax=plt.subplots(figsize=(7.2,1.7),layout='constrained');ax.axis('off');ax.set(xlim=(0,4),ylim=(0,1))
        for i,label in enumerate(labels):
            ax.text(i+.45,.5,label,ha='center',va='center',fontsize=8,bbox=dict(boxstyle='round',fc='#EAF2F5',ec='#176B87'))
            if i<3:ax.annotate('',xy=(i+1.02,.5),xytext=(i+.9,.5),arrowprops=dict(arrowstyle='->'))
        ax.set_title('Issue-time data contract' if name=='data_pipeline' else 'Planned primary experiment; no selected model yet',fontsize=10)
        fig.savefig(out/(name+'.pdf'));plt.close(fig)
    paths=[out/(name+'.pdf') for name in ('coverage_vs_severity','interval_widths','data_pipeline','model_workflow')]
    write_json(ROOT/'paper/journal/figure_manifest.json',{'preliminary_artifact':p['artifact'],
        'preliminary_sha256':hashlib.sha256((ROOT/p['artifact']).read_bytes()).hexdigest(),
        'scope':'NON_CAMS_PRELIMINARY metrics; protocol diagrams; no primary/final results',
        'files':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}})


if __name__=='__main__':main()
