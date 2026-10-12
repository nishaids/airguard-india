"""Package the existing evidence-backed source; never generate model results.

Keep the standalone editor document editable. The journal entry point has the
same body split into sections, and uses the verified shared BibTeX references.
Run build_manuscript_package first when evidence changes.
"""
import hashlib
import json
import re
from pathlib import Path
from src.research.calibration.checkpoint import write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Preserve the historical packager, but keep the adopted publication
    # layouts authoritative once their formatting manifest exists.
    if (ROOT/'paper/publication_format_manifest.json').exists():
        import runpy
        runpy.run_path(str(ROOT/'scripts/format_publication_drafts.py'),run_name='__main__')
        return
    path = ROOT/'paper/station_calibration_skeleton.tex'
    source = path.read_text(encoding='utf-8')
    source = source.replace(r'\documentclass[conference]{IEEEtran}', r'\documentclass[journal]{IEEEtran}')
    if r'\usepackage[T1]{fontenc}' not in source:
        source = source.replace(r'\usepackage[utf8]{inputenc}', r'\usepackage[utf8]{inputenc}'+'\n'+r'\usepackage[T1]{fontenc}')
    author = r'''\author{Nishanth R\thanks{Nishanth R is with the Department of AI and Data Science,
Rajalakshmi Engineering College, Chennai, Tamil Nadu, India.
Email: nishanth.r.2024.aids@rajalakshmi.edu.in; backup: nishanth.artwork@gmail.com.}
\thanks{Development manuscript. Primary CAMS results and model selection are pending;
the final evaluation interval remains sealed.}}'''
    source = re.sub(r'\\author\{.*?(?=\\begin\{document\})',lambda _:author+'\n',source,flags=re.S)
    source = source.replace('This unsubmitted skeleton documents','This development manuscript documents')
    source = source.replace('Author placeholders remain unresolved.','The named author must approve the final manuscript before submission.')
    for needle in ('post-processing method, Atmos.', 'categorical skill scores, Atmos.', 'System v1.0, Geosci.'):
        source = source.replace(needle, needle.replace(', ', ",'' ",1))
    source = source.replace('across 1\ntarget days','across 1\ntarget day')
    source = source.replace('identified above.', 'recorded in the claim-evidence package.')
    source = source.replace('\u2013','--').replace('\u2014','---').replace('\u00a0',' ')
    source = re.sub(r'The acquisition dataset SHA-256 is .*?\.\n\nThe single CPCB-style',
        'The measured semantic dataset and preliminary input share SHA-256 prefix '
        r'\\texttt{4761a5da60dde059}; the immutable preliminary run has prefix '
        r'\\texttt{287c87db04a6b294}. Full hashes, denominators and artifact locations are recorded in the claim-evidence manifest.\n\nThe single CPCB-style',
        source, flags=re.S)
    path.write_text(source,encoding='utf-8')
    package=ROOT/'paper/artifacts/current_draft'
    (package/path.name).write_text(source,encoding='utf-8')
    claims=json.loads((package/'claim_to_evidence.json').read_text())
    claims['source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(package/'claim_to_evidence.json',claims)
    write_json(package/'manifest.json',{'final_test_accessed':False,'primary_results_pending':True,
        'files':{p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in package.rglob('*') if p.is_file() and p.name!='manifest.json'}})
    folder = ROOT/'paper/journal'; sections=folder/'sections'
    sections.mkdir(parents=True,exist_ok=True)
    header, body = source.split(r'\begin{abstract}',1)
    abstract, body = body.split(r'\end{IEEEkeywords}',1)
    abstract = r'\begin{abstract}'+abstract+r'\end{IEEEkeywords}'+'\n'
    content, bibliography = body.split(r'\begin{thebibliography}',1)
    parts = re.split(r'(?=\\section\{)', content)
    groups = {'introduction':[], 'related_work':[], 'data_methods':[], 'results':[], 'discussion':[], 'conclusion':[]}
    destination = {
        'Problem and Related Work':'related_work', 'Study Status':'introduction',
        'Data, Targets and Quality':'data_methods', 'Issue-Time Availability':'data_methods',
        'Primary Forecast and Correction':'data_methods', 'Selection and Ablation':'data_methods',
        'Temporal and Spatial Verification':'data_methods', 'Uncertainty Calibration':'data_methods',
        'Vulnerability-Aware Advisory Evaluation':'data_methods',
        'Preliminary Results Contract':'results','Prospective Verification':'results',
        'Reproducibility':'discussion','Limitations and Planned Completion':'discussion','Conclusion':'conclusion'}
    for part in parts:
        title=re.search(r'\\section\{([^}]+)\}',part)
        if title:
            groups[destination[title.group(1)]].append(part.replace(r'\clearpage',''))
    measured=json.loads((ROOT/'results/research/measured_dataset.json').read_text())
    alignment=json.loads((ROOT/'results/research/cams_development_alignment.json').read_text())
    tables=ROOT/'paper/tables';tables.mkdir(exist_ok=True)
    dataset_table=r'''\begin{table}[t]\centering\caption{Dataset audit. Full measured counts are inherited descriptive metadata; only development rows enter alignment.}
\begin{tabular}{lr}\toprule Item & Count\\\midrule
'''
    for label,key in [('Measured stations','raw_stations'),('Usable stations','usable_stations'),('Usable cities','usable_cities'),('Retained station-days','station_days'),('Valid targets','valid_targets'),('Rejected targets','rejected_targets'),('Censored Severe targets','severe_days')]:
        dataset_table+=label+' & '+f'{measured[key]:,}'+r'\\'+'\n'
    dataset_table+=r'\midrule'+'\n'
    for label,key in [('Aligned development rows','rows'),('Aligned dates','dates'),('Aligned valid targets','valid_targets'),('Aligned rejected targets','rejected_targets_retained'),('Aligned Severe targets','censored_severe_retained')]:
        dataset_table+=label+' & '+f'{alignment[key]:,}'+r'\\'+'\n'
    dataset_table+=r'\bottomrule\end{tabular}\end{table}'+'\n'
    (tables/'dataset_summary.tex').write_text(dataset_table,encoding='utf-8')
    params=r'''\begin{table}[t]\centering\caption{Preregistered search space, not selected hyperparameters. All model selection remains pending.}
\begin{tabular}{lp{.57\columnwidth}}\toprule Candidate & Training-only choices\\\midrule
Ridge & $\alpha\in\{0.1,1,10,100\}$\\
LightGBM & Leaves 15/31; minimum child samples 20/60\\
XGBoost & Depth 4/6; minimum child weight 5/20\\
Both boosters & Learning rate 0.05; maximum 600 rounds; early stopping 40 rounds; subsample and column fraction 0.8\\
All learners & Seed 42; direct and residual formulations\\
Selection & Mean rolling-fold MAE; simpler learner and residual formulation break ties\\
\bottomrule\end{tabular}\end{table}
'''
    (tables/'model_params.tex').write_text(params,encoding='utf-8')
    comparison=r'''\begin{table}[t]\centering\caption{Primary CAMS comparison: experiments pending. No numeric result is inferred from the non-CAMS study.}
\begin{tabular}{lp{.48\columnwidth}}\toprule Candidate & Status\\\midrule
'''
    for name in ('Climatology','Persistence','Raw CAMS','Direct Ridge','Residual Ridge','Direct LightGBM','Residual LightGBM','Direct XGBoost','Residual XGBoost'):
        comparison+=name+r' & Pending eligible development folds\\'+'\n'
    comparison+=r'\bottomrule\end{tabular}\end{table}'+'\n'
    (tables/'baseline_comparison.tex').write_text(comparison,encoding='utf-8')
    groups['data_methods'].append(dataset_table+params+r'''
\subsection{Baseline estimation and operational missingness}
Climatology is estimated from exact training targets in a station's calendar
month, with station and global means as explicit fallbacks. These statistics
are re-estimated inside each training fold. Persistence uses the measured
rolling 24-hour index ending at the cutoff, rather than the not-yet-complete
day immediately before the target. Consequently a persistence forecast can
be missing even when the eventual target is valid. The primary comparison
requires exact targets, the CAMS baseline and persistence jointly; the
secondary set relaxes only the persistence requirement. Reporting these
denominators prevents a method gaining an advantage by being evaluated on
easier, more complete days.

The implementation joins on station identifier and calendar date and rejects
duplicate keys or mismatched station coordinates. Calendar lags are looked up
by date, rather than shifted across whichever observations happen to be
present. An absent day is therefore missing, not replaced by an older reading
with the wrong lead. Censored historical values retain a lower-bound indicator;
they do not supply fabricated exact residual-bias labels. Numerical missingness
is handled by training-only imputation with indicators. This choice describes
the current implementation and remains subject to the development audit;
no imputer is fitted to a validation or final window.

Nearby-station summaries use only donor rolling measurements whose bins
ended by the cutoff. Self-donations are excluded. Spatial inference without
a local monitor must mask unavailable donor stations as well as the held-out
station's own history. A held-out target is never a contemporaneous neighbour
feature. Elevation is static cached terrain metadata, not an outcome-derived
station-selection criterion. The acquired surface cube also provides maxima,
ranges, standard deviations and daytime-minus-nighttime concentrations; all
come from the same producing run as the daily CAMS baseline.

\subsection{Scope of the operational reconstruction}
The locked YAML preserves the earlier proxy-source disclosure and its hash;
it has not been silently rewritten to claim historical operational access.
The separately frozen acquisition manifest identifies the genuine ADS
forecast stream now being integrated. That provenance improvement does not
relax the original QC, date splits, censoring or selection criteria. It also
does not prove each forecast's historical delivery time. Nominal publication
and healthy-feed assumptions remain explicit limitations of retrospective
reconstruction, to be checked prospectively.
''')
    groups['results'].append(r'''
\begin{figure}[t]\centering
\includegraphics[width=\columnwidth]{../figures/coverage_vs_severity.pdf}
\caption{First-fold non-CAMS split-conformal coverage. Poor has only 13 exact pairs and its subgroup metric is withheld; Very Poor has 35. Neither constitutes primary CAMS evidence.}
\end{figure}
\begin{figure}[t]\centering
\includegraphics[width=\columnwidth]{../figures/interval_widths.pdf}
\caption{Mean interval widths across non-CAMS development folds, directly from the immutable result. These are fold summaries, not a manufactured distribution of individual interval widths.}
\end{figure}
\subsection{Interpretation of incomplete primary evidence}
Partial forecast extraction is an integrity milestone, not a forecast-skill
result. The current matched period cannot satisfy the 120-valid-day station
rule or the prescribed calibration and evaluation windows. The pipeline
therefore emits explicit insufficient-data entries rather than training on
a shorter interval. This affects all primary candidates, including raw CAMS,
climatology and persistence, so their intended paired comparison is not
quietly replaced by a convenient short-period leaderboard.

The non-CAMS result establishes that the experimental machinery can recover
differences against climatology, but the persistence comparison does not
establish an advantage for history Ridge. Likewise, near-nominal marginal
coverage can coexist with complete failure on a sufficiently supported
high-pollution subgroup. Those observations motivate the preregistered
severity and advisory analysis; they do not select a primary model. No
primary error scatter plot, error histogram or health-effect plot is supplied
because the required primary prediction artifacts do not yet exist.
''')
    groups['discussion'].append(r'''
\subsection{Artifact lineage and release boundary}
The reproducibility package binds the protocol hash, measured semantic hash,
operational request manifest, GRIB checksums, derived table hash and feature
version. Raw files are stored outside Git, while manifests and implementation
are versioned. Resumption polls existing request identifiers before submitting
new work. Hash failures stop processing instead of replacing evidence in place.
The development reader applies its date exclusion before materialising
outcomes. The readiness report itself reads artifact metadata and hashes file
bytes; it does not run an estimator or open final labels.

Production validation and scientific validation answer different questions.
The released interface has route, API and browser checks, while the proposed
station correction still requires completed development experiments. A
successful web deployment is not a substitute for predictive validation.
Similarly, a compiled manuscript is a presentation artifact and cannot
release a research gate. A selected model, if justified later, will need a
committed feature and parameter lock, uncertainty and advisory configurations,
and a complete evidence audit before final-test authorization is requested.
''')
    (sections/'abstract.tex').write_text(abstract,encoding='utf-8')
    titles={'introduction':'Introduction','related_work':'Related Work','data_methods':'Data and Methods',
            'results':'Development Results and Pending Experiments','discussion':'Discussion and Reproducibility','conclusion':'Conclusion'}
    for name, chunks in groups.items():
        value='\n'.join(chunks).replace(r'\subsection{',r'\subsubsection{')
        value=value.replace(r'\section{',r'\subsection{')
        value=r'\section{'+titles[name]+'}\n'+value
        (sections/(name+'.tex')).write_text(value.rstrip()+'\n',encoding='utf-8')
    # Existing verified bibliography remains preserved, with publisher-verified MOS entries.
    refs=(ROOT/'paper/refs.bib').read_text(encoding='utf-8')
    additions = r'''
@article{riccio2024mos, author={Riccio, Angelo and Chianese, Elena}, title={Technical note: Accurate, reliable, and high-resolution air quality predictions by improving the Copernicus Atmosphere Monitoring Service using a novel statistical post-processing method}, journal={Atmospheric Chemistry and Physics}, volume={24}, pages={1673--1689}, year={2024}, doi={10.5194/acp-24-1673-2024}}
@article{petetin2022mos, author={Petetin, H. and others}, title={Model output statistics (MOS) applied to Copernicus Atmospheric Monitoring Service (CAMS) O3 forecasts: trade-offs between continuous and categorical skill scores}, journal={Atmospheric Chemistry and Physics}, volume={22}, pages={11603--11630}, year={2022}, doi={10.5194/acp-22-11603-2022}}
@article{colette2025cams, author={Colette, A. and others}, title={Copernicus Atmosphere Monitoring Service--Regional Air Quality Production System v1.0}, journal={Geoscientific Model Development}, volume={18}, pages={6835--6883}, year={2025}, doi={10.5194/gmd-18-6835-2025}}
'''
    refs=re.sub(r'month=July', 'month=jul', refs)
    refs=refs.replace('\u2013','--').replace('\u2014','---').replace('\u00a0',' ')
    (ROOT/'paper/references.bib').write_text(refs+additions,encoding='utf-8')
    order=['abstract','introduction','related_work','data_methods','results','discussion','conclusion']
    main=header.replace(r'\usepackage{amsmath,booktabs,url}',r'\usepackage{amsmath,booktabs,url,graphicx}')+'\n'.join(r'\input{sections/'+name+'}' for name in order)+r'''
\bibliographystyle{IEEEtran}
\bibliography{../references}
\end{document}
'''
    (folder/'main.tex').write_text(main,encoding='utf-8')
    (folder/'README.md').write_text('# IEEE journal development draft\n\n'
        'Compile main.tex from this directory with IEEEtran and BibTeX (Tectonic handles both). '
        'The existing standalone editor source remains paper/station_calibration_skeleton.tex. '
        'Section files are generated by scripts.prepare_journal_draft from that source. '
        'Run scripts.build_manuscript_package before packaging updated verified evidence.\n\n'
        'Primary results, model parameters, and MODEL_SELECTION_LOCK are pending; no numerical placeholders are treated as results. '
        'The separate preliminary non-CAMS study cannot establish an improvement over raw CAMS. '
        'PlanGen was inspected solely for presentation structure, never used as scientific content or evidence. '
        'The supplied IEEE folder contains a conference Word template; this journal draft uses IEEEtran journal mode as requested.\n',encoding='utf-8')
    files=[path,ROOT/'paper/references.bib',folder/'main.tex',*sections.glob('*.tex')]
    write_json(folder/'draft_manifest.json',{'status':'DEVELOPMENT_DRAFT_PRIMARY_RESULTS_PENDING',
        'final_test_accessed':False,'model_selected':False,
        'files':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
    print(json.dumps({'journal_source':'paper/journal/main.tex','section_files':len(order),'primary_results_pending':True}))


if __name__=='__main__': main()
