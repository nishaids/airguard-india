"""Extend the existing manuscript in place with artifact-backed draft material.

No measured labels, final outcomes, new model scores or protocol edits here.
The two numerical figures exclusively describe the immutable NON_CAMS study.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from src.research.calibration.checkpoint import write_json

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT/'paper/artifacts/current_draft'


def read(relative):
    return json.loads((ROOT/relative).read_text(encoding='utf-8'))


def replace_section(source, name, body):
    pattern = r'\\section\{'+re.escape(name)+r'\}.*?(?=\\section|\\clearpage)'
    if len(re.findall(pattern, source, flags=re.S)) != 1:
        raise ValueError('Existing manuscript section not unique: '+name)
    return re.sub(pattern, lambda _: '\\section{'+name+'}\n'+body+'\n', source, flags=re.S)


def main():
    preliminary = read('results/research/preliminary_latest.json')
    immutable = read(preliminary['artifact'])
    if preliminary != immutable or preliminary['final_test_scored']:
        raise ValueError('Draft requires the exact immutable development-only result')
    measured = read('results/research/measured_dataset.json')
    archive = read('results/research/cams_development_acquisition.json')
    alignment = read('results/research/cams_development_alignment.json')
    probe = read('results/research/cams_ads_probe.json')
    prospective = read('results/research/prospective_audit.json')
    PACKAGE.mkdir(parents=True, exist_ok=True)
    figures = PACKAGE/'figures'; figures.mkdir(exist_ok=True)
    tables = PACKAGE/'tables'; tables.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':9, 'pdf.fonttype':42, 'svg.fonttype':'none'})
    pairs = []
    for key, label in [('ridge_strict_vs_climatology', 'Strict Ridge - climatology'),
                       ('ridge_history_vs_persistence', 'History Ridge - persistence')]:
        row = preliminary['paired_comparisons'][key]
        pairs.append({'comparison':label, 'mae_difference':row['mae_difference'],
                      'ci95_lower':row['ci95'][0], 'ci95_upper':row['ci95'][1], 'n_exact':row['n']})
    pd.DataFrame(pairs).to_csv(tables/'non_cams_paired_comparisons.csv', index=False)
    fig, ax = plt.subplots(figsize=(6.8,2.65), constrained_layout=True)
    for i, row in enumerate(pairs):
        ax.errorbar(row['mae_difference'], 1-i,
                    xerr=[[row['mae_difference']-row['ci95_lower']], [row['ci95_upper']-row['mae_difference']]],
                    fmt='o', capsize=4, color=('#176B87' if i==0 else '#A54C26'))
    ax.axvline(0, color='#555555', linestyle='--', linewidth=.8)
    ax.set_yticks([1,0], [r['comparison'] for r in pairs]); ax.set_ylim(-.5,1.5)
    ax.set_xlabel('Difference in MAE (AQI units); 95% seven-day block interval')
    ax.set_title('NON-CAMS PRELIMINARY development comparisons', loc='left', fontweight='bold')
    ax.grid(axis='x', alpha=.2)
    for suffix in ('pdf','svg','png'): fig.savefig(figures/f'non_cams_paired_mae.{suffix}', dpi=300)
    plt.close(fig)
    uncertainty = []
    for fold, methods in preliminary['uncertainty'].items():
        for method, row in methods.items():
            uncertainty.append({'fold':fold, 'method':method, 'nominal':row['nominal'],
                                'n_exact':row['n_exact'], 'coverage_exact':row['coverage_exact'],
                                'mean_width':row['mean_width']})
    pd.DataFrame(uncertainty).to_csv(tables/'non_cams_uncertainty_by_fold.csv', index=False)
    fig, ax = plt.subplots(figsize=(6.8,2.65), constrained_layout=True)
    for method, color in [('split_0.8','#176B87'),('split_0.9','#A54C26')]:
        rows = [r for r in uncertainty if r['method']==method]
        ax.plot(range(1,len(rows)+1), [r['coverage_exact'] for r in rows], 'o-', label=method, color=color)
        ax.axhline(rows[0]['nominal'], linestyle='--', color=color, linewidth=.8)
    ax.set(xlabel='Chronological development fold', ylabel='Exact-target coverage', ylim=(0,1.03))
    ax.set_title('NON-CAMS PRELIMINARY: marginal coverage varies over time', loc='left', fontweight='bold')
    ax.legend(frameon=False, loc='lower right'); ax.grid(alpha=.15)
    for suffix in ('pdf','svg','png'): fig.savefig(figures/f'non_cams_interval_coverage.{suffix}', dpi=300)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8,3.2)); ax.set(xlim=(0,10),ylim=(0,4)); ax.axis('off')
    labels=[(.2,2.6,'Measured stations\nLocked QC / targets'),(.2,.4,'Archived operational CAMS\nRun / lead / valid / units'),
            (3.6,1.5,'20:00 IST snapshot\nAvailability guard'),(6.8,1.5,'Direct / residual models*\nTemporal + spatial tests*')]
    for x,y,label in labels:
        ax.add_patch(FancyBboxPatch((x,y),2.9,.9,boxstyle='round,pad=.12',facecolor='#EAF2F5',edgecolor='#176B87'))
        ax.text(x+1.45,y+.45,label,ha='center',va='center',fontsize=10)
    for a,b in [((3.2,3),(3.5,2)),((3.2,.85),(3.5,1.9)),((6.55,1.95),(6.75,1.95))]:
        ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','color':'#176B87'})
    ax.text(5,.06,'* Full primary experiments pending archive; final test requires a committed lock and fresh approval.',ha='center',fontsize=9)
    fig.savefig(figures/'architecture.svg',bbox_inches='tight'); fig.savefig(figures/'architecture.png',dpi=300,bbox_inches='tight'); plt.close(fig)
    pd.DataFrame([{'metric':k,'value':measured[k]} for k in ('usable_stations','usable_cities','station_days','valid_targets','rejected_targets','severe_days')]).to_csv(tables/'measured_dataset_summary.csv',index=False)
    pd.DataFrame([{'method':x,'status':'PENDING CAMS ARCHIVE EXPERIMENT','MAE':None,'RMSE':None,'bias':None}
                  for x in ('Climatology','Persistence','Raw CAMS','Direct Ridge','Direct LightGBM','Direct XGBoost','Residual Ridge','Residual LightGBM','Residual XGBoost')]).to_csv(tables/'primary_results_pending.csv',index=False)
    source_path = ROOT/'paper/station_calibration_skeleton.tex'
    source = source_path.read_text(encoding='utf-8')
    source = re.sub(r'\\title\{[^\n]*\}', lambda _: r'\title{AirGuard India: Station-Calibrated Day-Ahead Air Quality Forecasting with Uncertainty-Aware Vulnerability Advisories}', source, count=1)
    source = source.replace('The genuine historical CAMS\nissue-time archive remains unavailable.',
                            'The genuine historical CAMS issue-time archive has passed operational GRIB validation; development acquisition is incomplete.')
    source = source.replace('ADS credentials and manual dataset terms acceptance block the genuine CAMS\ncomparison.',
                            'ADS setup is complete. Incomplete archive coverage and primary experiments block the genuine CAMS comparison.')
    source = source.replace('The recovery preserves the existing protocol and acquisition checkpoint, and\nextends measured-data and non-CAMS infrastructure.',
                            'The study preserves its locked protocol, measured targets and immutable preliminary experiment; genuine CAMS alignment is now audited on a partial development subset.')
    source = source.replace('A complete clean-clone primary reproduction remains pending.',
                            'A clean-clone measured-dataset reconstruction passed its semantic hash audit under the recorded runtime. A complete primary reproduction remains pending.')
    source = source.replace('Any change to the locked\ncomparison requires a transparent protocol amendment before primary fitting,\nwithout consulting final-test outcomes.',
                            'The locked comparison is preserved. No primary model has been fitted and no final-test outcomes have been accessed.')
    source = source.replace('Verification of an operational pollutant-support policy and its compatible\nprimary runner remains pending archive integration.',
                            f'The partial join contains {alignment["rows"]:,} station-days, {alignment["valid_targets"]:,} valid targets and {alignment["rejected_targets_retained"]:,} retained rejected targets across {alignment["dates"]} dates. All {alignment["guarded_rows"]:,} rows pass the primary availability guard. Every valid target in this subset uses the frozen PM2.5/PM10/O3 support; outcome support remains an evaluation annotation and is excluded from predictors. Full feature integration and the primary runner remain incomplete.')
    source = re.sub(r'The partial join contains .*? rows pass the primary availability guard\.',
                    f'The partial join contains {alignment["rows"]:,} station-days, {alignment["valid_targets"]:,} valid targets and {alignment["rejected_targets_retained"]:,} retained rejected targets across {alignment["dates"]} dates. All {alignment["guarded_rows"]:,} rows pass the primary availability guard.', source, flags=re.S)
    source = replace_section(source, 'Primary comparison contract', '') if '\\section{Primary comparison contract}' in source else source
    checkpoint = f'''% BEGIN CURRENT CAMS EVIDENCE
\\subsection{{Verified operational archive checkpoint}}
The single accepted probe is a genuine forecast (GRIB type fc), initialized
2025-02-18 00:00 UTC with a 24-hour lead and valid at 2025-02-19 00:00 UTC.
Its 134-byte PM2.5 field contains nine finite values on a 0.4-degree grid.
The development manifest currently verifies {archive['counts'].get('VERIFIED_GRIB',0)} of 36 chunks.
Requests cover only the frozen station bounding box and development dates.
Initialization plus lead reconstructs valid time in every admitted field.
Surface PM mass concentrations use $10^9$ to convert kg m$^{{-3}}$ to
$\\mu$g m$^{{-3}}$. Gas mixing ratios use the same-run lowest-level
temperature $T$, specific humidity $q$ and hybrid pressure $p$:
\\begin{{equation}}
\\rho=\\frac{{p}}{{287.05T(1+0.6078q)}},\\quad C_{{\\mu g/m^3}}=10^9\\rho x.
\\end{{equation}}
CO instead uses $10^6$ for mg m$^{{-3}}$. Model-level fields are linearly
interpolated within the same producing run before density conversion;
no extrapolation, reanalysis or post-issue run is admitted. Seven preceding
hourly bins support trailing eight-hour CO/O3 windows.
Historical per-run delivery logs are unavailable: pre-issue availability
uses the documented nominal dissemination bound, explicitly an assumption.
The later ADS retrieval timestamp is provenance, not historical publication.
% END CURRENT CAMS EVIDENCE
'''
    source = re.sub(r'% BEGIN CURRENT CAMS EVIDENCE.*?% END CURRENT CAMS EVIDENCE\n', '', source, flags=re.S)
    source = source.replace('\\section{Selection and Ablation}', checkpoint+'\n\\section{Selection and Ablation}',1)
    related = r'''% BEGIN MOS RELATED WORK
Station-specific CAMS post-processing is established. Riccio and Chianese
study statistical correction with spatial verification \cite{riccio2024mos}.
Petetin et al. explicitly distinguish improvements in continuous forecast
errors from categorical ozone-warning skill \cite{petetin2022mos}.
Operational regional CAMS production also includes MOS \cite{colette2025cams}.
The proposed contribution is an audited Indian evaluation joining issue-time
availability, censored-Severe diagnostics and prospective station verification;
neither a new MOS invention nor a world's-first application is claimed.
% END MOS RELATED WORK
'''
    source = re.sub(r'% BEGIN MOS RELATED WORK.*?% END MOS RELATED WORK\n', '', source, flags=re.S)
    source = source.replace('\\clearpage', related+'\n\\clearpage',1)
    plot = ['% BEGIN PRELIMINARY FIGURE', r'\begin{figure}[h]\centering', r'\setlength{\unitlength}{1mm}',r'\begin{picture}(78,38)',
            r'\put(8,5){\line(1,0){64}}',r'\put(56,5){\line(0,1){26}}']
    for val in (-15,-10,-5,0,5):
        x=8+(val+15)*3.2
        plot += ['\\put(%.2f,4){\\line(0,1){2}}' % x, '\\put(%.2f,1){\\makebox(0,0){\\scriptsize %s}}' % (x, val)]
    for row,y,label in zip(pairs,(26,13),('Strict Ridge minus climatology','History Ridge minus persistence')):
        lo=8+(row['ci95_lower']+15)*3.2; hi=8+(row['ci95_upper']+15)*3.2; mean=8+(row['mae_difference']+15)*3.2
        plot += ['\\put(%.2f,%s){\\line(1,0){%.2f}}' % (lo, y, hi-lo),
                 '\\put(%.2f,%s){\\circle*{1.5}}' % (mean, y),
                 '\\put(40,%s){\\makebox(0,0){\\scriptsize %s}}' % (y+5, label)]
    plot += [r'\end{picture}',r'\caption{NON-CAMS preliminary paired MAE differences and 95\% seven-day date-block intervals. Zero means equal MAE; lower is better. Strict $n=38,382$; history $n=31,622$.}',r'\end{figure}', '% END PRELIMINARY FIGURE']
    source = re.sub(r'% BEGIN PRELIMINARY FIGURE.*?% END PRELIMINARY FIGURE\n', '', source, flags=re.S)
    source = source.replace('\\section{Reproducibility}', '\n'.join(plot)+'\n\\section{Reproducibility}',1)
    first = preliminary['uncertainty']['fold_01']
    uncertainty_text = f'''% BEGIN PRELIMINARY COVERAGE
\\begin{{table}}[h]\\centering\\caption{{NON-CAMS preliminary first-fold calibration failures}}
\\begin{{tabular}}{{lrr}}\\toprule Method & Exact coverage & Mean width\\\\\\midrule
80\\% split & {first['split_0.8']['coverage_exact']:.3f} & {first['split_0.8']['mean_width']:.1f}\\\\
90\\% split & {first['split_0.9']['coverage_exact']:.3f} & {first['split_0.9']['mean_width']:.1f}\\\\
\\bottomrule\\end{{tabular}}
\\end{{table}}
Marginal coverage conceals important failures: neither interval covered any
of the 35 exact Very Poor outcomes in this first fold. Poor-or-worse coverage
was also zero on 48 exact pairs. These are preliminary validation failures,
not primary CAMS or final-test findings; they preclude claiming reliable
high-pollution uncertainty from average coverage alone.
% END PRELIMINARY COVERAGE
'''
    source = re.sub(r'% BEGIN PRELIMINARY COVERAGE.*?% END PRELIMINARY COVERAGE\n', '', source, flags=re.S)
    source = source.replace('\\section{Vulnerability-Aware Advisory Evaluation}', uncertainty_text+'\n\\section{Vulnerability-Aware Advisory Evaluation}',1)
    source = source.replace('They are\nevaluated once, after selection on the rolling folds, and that evaluation\nwrites a lock file', 'They are evaluated only after selection, a committed MODEL_SELECTION_LOCK and fresh user approval; the one-shot evaluation writes an immutable result')
    source = source.replace('The referenced result artifact declares that no final-test scoring was performed.',
                            'The referenced artifact declares no final-test scoring. The primary selection rule is lowest mean rolling-fold MAE, breaking ties toward Ridge and residual formulations; raw CAMS is retained if no learned method beats it. A committed selection lock, complete isolation audit and fresh user approval are required before final evaluation.')
    additions = {
        'ARCHITECTURE': ('% END MOS RELATED WORK', r'''\begin{figure}[h]\centering
\fbox{\begin{minipage}{.91\columnwidth}\centering\small
\textbf{Measured stations}\ $\longrightarrow$\ locked QC targets\\[5pt]
\textbf{Archived CAMS runs}\ $\longrightarrow$\ unit/time audit\\[5pt]
$\Downarrow$\\[3pt]
\textbf{20:00 IST feature snapshot and availability guard}\\[5pt]
$\Downarrow$\\[3pt]
\textbf{Direct/residual models and matched baselines}*\\[5pt]
$\Downarrow$\\[3pt]
\textbf{Rolling/spatial validation; calibration; advisories}*\\[5pt]
$\Downarrow$\\[3pt]
\textbf{Committed selection lock; fresh final-test approval}*
\end{minipage}}
\caption{Study architecture. Asterisks mark unfinished primary experiment stages. Measured outcomes and forecast fields have separate provenance; final evaluation remains sealed.}
\end{figure}
\subsection{Scope of the contribution}
For station $s$ and target date $d$, the predictor $X_{s,d}$ is formed
before the declared issue time, while $y_{s,d}$ is constructed later from
quality-controlled measurements. The forecast task is next-day prediction,
not concurrent regression on target-day pollutant observations. A high-quality
interface alone cannot establish correction skill. This paper therefore
binds each proposed claim to an immutable result or an explicit pending gate.
The released operational product remains a raw CAMS estimate; offline
station-correction development is a separate research stream.'''),
        'TARGET_METHOD': ('\\section{Issue-Time Availability}', r'''\subsection{Concentration-to-index transformation}
Within a bounded CPCB interval $[C_L,C_H]$ with index endpoints $[I_L,I_H]$,
the pollutant sub-index is
\begin{equation}
I_p(C)=I_L+\frac{I_H-I_L}{C_H-C_L}(C-C_L),\quad I=\max_{p\in S}I_p.
\end{equation}
The daily support $S$ requires at least three sufficiently covered species,
including particulate matter. It is recorded as an outcome annotation, never
used to select predictors retrospectively. In the current valid development
join, $S$ equals the prerequest frozen PM2.5/PM10/O3 support. Rejected rows
retain reasons and provenance rather than disappearing from denominator
counts. An open concentration interval does not justify linear extrapolation
to a fictitious exact Severe target.
\subsection{Quality-control interpretation}
The six-hour stuck-run rule rejects the complete identical sequence, not only
its final bin. Exact-zero rejection cannot distinguish a genuinely tiny
ozone concentration from a telemetry zero and is therefore a disclosed
preregistered trade-off. Conversely, automatic spike deletion could erase
real pollution episodes. PM2.5/PM10 inconsistencies and potential spikes
remain flagged observations. Sensor rejection, unavailable target and
model error are distinct outcomes; their counts are reported separately.'''),
        'PRELIM_SCOPE': ('\\section{Reproducibility}', r'''\subsection{Limits of the preliminary experiment}
The non-CAMS plan uses 30 valid training days per station and a fixed Ridge
penalty of 10; these choices must not be mistaken for primary CAMS tuning.
The locked primary station rule remains 120 valid training days. Thus the
first 90-day primary training window cannot meet station eligibility; it
must be reported as insufficient, not rescued by future coverage or a
silent threshold reduction. Later windows are evaluated when sufficient.
Primary model selection has not begun. Absence of a primary score is not
evidence of equivalence, and preliminary skill against climatology cannot
establish benefit over archived CAMS or persistence.'''),
        'ADVISORY_METHOD': ('\\section{Prospective Verification}', r'''\subsection{Policy losses and calibration boundary}
For ordered observed category $c$ and warning category $w$, the basic losses
are $L_-=\mathbf{1}\{w<c\}$ and $L_+=\mathbf{1}\{w>c\}$.
Serious under-warning, missed Poor-or-worse and missed Very-Poor-or-worse
events remain separate diagnostics. Lower under-warning can require more
false alarms; neither objective is optimized on a test window.
The candidate quantiles are fixed before evaluation. P3 chooses on the
calibration window only and then reports its frozen test-window behavior,
including failure to find any feasible candidate. Its corrected empirical
rate $(k+1)/(n+1)$ is a policy selection statistic, not an individual disease
probability or a proven dependent-data risk bound.
\subsection{Finite-sample intervals and failure reporting}
For exact calibration residuals $e_i=|y_i-\widehat y_i|$, split conformal
uses the order statistic with rank $\lceil(n+1)(1-\alpha)\rceil$.
The interval is $[\max(0,\widehat y-q),\widehat y+q]$; missing or inadequate
calibration support is reported rather than assigned a radius of zero.
Mondrian groups use the forecast category, so observed test categories cannot
choose an interval. Quantile crossing is repaired using predictions only.
Calibration labels exclude censored Severe values from exact residuals;
Severe category/threshold behavior is still reported. Under temporal/spatial
dependence, coverage is an empirical finding, not automatically a theorem.
\subsection{Exposure guidance and clinical scope}
Declared vulnerability strata set environmental-warning tolerances. Shared
forecast outcomes do not constitute separate clinical cohort studies. The
system does not predict diagnoses, prescribe medication, estimate personal
health probabilities or demonstrate avoided illness. Its interface labels
measurement versus modelling, observation age, unsupported intervals and
raw-model uncertainty. Clinical coefficients remain unvalidated.'''),
    }
    for marker, (anchor, body) in additions.items():
        source = re.sub('% BEGIN '+marker+r'.*?% END '+marker+'\n', '', source, flags=re.S)
        block = '% BEGIN '+marker+'\n'+body+'\n% END '+marker+'\n'
        source = source.replace(anchor, (anchor+'\n'+block) if marker=='ARCHITECTURE' else (block+anchor), 1)
    references = [r'\bibitem{riccio2024mos} A. Riccio and E. Chianese, ``Technical note: Accurate, reliable, and high-resolution air quality predictions by improving the Copernicus Atmosphere Monitoring Service using a novel statistical post-processing method,'' Atmos. Chem. Phys., vol. 24, pp. 1673--1689, 2024, doi: 10.5194/acp-24-1673-2024.',
                  r'\bibitem{petetin2022mos} H. Petetin et al., ``Model output statistics (MOS) applied to Copernicus Atmospheric Monitoring Service (CAMS) O$_3$ forecasts: trade-offs between continuous and categorical skill scores,'' Atmos. Chem. Phys., vol. 22, pp. 11603--11630, 2022, doi: 10.5194/acp-22-11603-2022.',
                  r'\bibitem{colette2025cams} A. Colette et al., ``Copernicus Atmosphere Monitoring Service--Regional Air Quality Production System v1.0,'' Geosci. Model Dev., vol. 18, pp. 6835--6883, 2025, doi: 10.5194/gmd-18-6835-2025.']
    if '\\bibitem{riccio2024mos}' not in source:
        source = source.replace('\\end{thebibliography}', '\n'.join(references)+'\n\\end{thebibliography}')
    source = source.replace('pp. 11603--11628', 'pp. 11603--11630')
    source = replace_section(source, 'Prospective Verification',
        f"The current audited ledger contains {prospective['forecasts']} real forecasts across "
        f"{prospective['issued_target_days']} target days, and {prospective['verified_days']} verified days. "
        f"{prospective['station_bound_forecasts']} forecasts have a bound station. "
        f"{prospective['historical_forecasts_missing_git_sha']} historical forecasts lack an issuance Git SHA; "
        "missing historical identities will not be invented. New issuance now records its deployment identity. "
        "Unbound records cannot be made station forecasts by retrospectively selecting an outcome monitor. "
        "No experimental correction is deployed. Issued forecasts remain immutable; a thirty-day track "
        "record requires real elapsed days and matched measured outcomes. Station-level prospective "
        "evaluation remains blocked until stations are bound before issuance.")
    source_path.write_text(source, encoding='utf-8')
    shutil.copy2(source_path, PACKAGE/source_path.name)
    shutil.copy2(ROOT/'paper/refs.bib', PACKAGE/'inherited_refs.bib')
    claim_map = {'draft_status':'PRIMARY_RESULTS_PENDING_FINAL_TEST_SEALED',
                 'title':'AirGuard India: Station-Calibrated Day-Ahead Air Quality Forecasting with Uncertainty-Aware Vulnerability Advisories',
                 'generated_at_utc':datetime.now(timezone.utc).isoformat(),
                 'protocol_sha256':measured['protocol_sha256'], 'measured_semantic_sha256':measured['dataset_hash'],
                 'preliminary_run_id':preliminary['run_id'], 'probe_sha256':probe['sha256'],
                 'claims':{'measured_counts':'results/research/measured_dataset.json',
                           'operational_GRIB':'results/research/cams_ads_probe.json',
                           'CAMS_partial_alignment':'results/research/cams_development_alignment.json',
                           'prospective_ledger':'results/research/prospective_audit.json',
                           'preliminary_comparisons_and_coverage':preliminary['artifact'],
                           'primary_CAMS_improvement':'PENDING; no claim', 'final_results':'SEALED; no claim',
                           'clinical_or_causal_health_benefit':'UNSUPPORTED; no claim'},
                 'source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest()}
    write_json(PACKAGE/'claim_to_evidence.json', claim_map)
    (PACKAGE/'README.md').write_text('# Research artifact package\n\nEvidence-backed draft; primary CAMS and final-test results remain pending. '
        'The canonical editable source remains `paper/station_calibration_skeleton.tex`. This package copy is a reproducibility snapshot. '
        'No paper submission or experimental model deployment occurred.\n\n'
        'Run `python -m scripts.build_manuscript_package` after verified result updates. '
        'Compile the canonical source with Tectonic 0.17.0 or the Codex built-in compiler. '
        'Numerical figure names explicitly identify NON-CAMS PRELIMINARY scope. CSV tables retain denominators and intervals. '
        'The primary table contains empty numerical fields and pending status, never invented scores. '
        'The inherited bibliography and three MOS references embedded in the manuscript use primary publisher pages and Crossref metadata. '
        'Complete primary experiments and literature acceptance remain outstanding.\n',encoding='utf-8')
    for svg in figures.glob('*.svg'):
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    manifest = {'generated_at_utc':datetime.now(timezone.utc).isoformat(),
                'final_test_accessed':False,'primary_results_pending':True,
                'files':{p.relative_to(PACKAGE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in PACKAGE.rglob('*') if p.is_file() and p.name!='manifest.json'}}
    write_json(PACKAGE/'manifest.json',manifest)
    print(json.dumps({'draft_source':'paper/station_calibration_skeleton.tex','package_files':len(manifest['files']),'primary_results_pending':True}))


if __name__ == '__main__':
    main()
