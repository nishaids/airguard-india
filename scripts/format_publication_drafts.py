"""Reference-inspired IEEE layouts from existing AirGuard evidence only.

The LogSight DOCX controls presentation cues, not scientific content. This
builder reads JSON summaries and the verified bibliography; no targets, ADS
credentials, model fitting, deployment or final-test evaluation are involved.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TITLE='AirGuard India: Station Calibration and Uncertainty-Aware Day-Ahead AQI Forecasting'


def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def write(path,text):
    path=ROOT/path;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.strip()+'\n',encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def source_digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def table(caption,columns,header,rows,label=''):
    return '\n'.join([r'\begin{table}[t]\centering\footnotesize',r'\caption{'+caption+'}',
        (r'\label{'+label+'}') if label else '',r'\setlength{\tabcolsep}{4pt}',
        r'\begin{tabular}{'+columns+'}',r'\toprule',header+r'\\\midrule',
        *[row+r'\\' for row in rows],r'\bottomrule\end{tabular}',r'\end{table}'])


def charts(p):
    pair=p['paired_comparisons']
    lines=[r'\newcommand{\AirGuardPaired}{%',r'\setlength{\unitlength}{1mm}',r'\begin{picture}(86,48)',
           r'\linethickness{.35pt}',r'\put(6,9){\line(1,0){74}}',r'\color{gray}\put(61.5,9){\line(0,1){29}}\color{black}']
    for value in (-15,-10,-5,0,5):
        x=6+(value+15)*3.7
        lines += [r'\put(%.2f,8){\line(0,1){2}}' % x,
                  r'\put(%.2f,5){\makebox(0,0){\scriptsize %s}}' % (x,value)]
    for key,y,label in [('ridge_strict_vs_climatology',32,'Strict Ridge versus climatology'),('ridge_history_vs_persistence',19,'History Ridge versus persistence')]:
        r=pair[key];lo,hi=[6+(v+15)*3.7 for v in r['ci95']];mean=6+(r['mae_difference']+15)*3.7
        lines += [r'\put(43,%g){\makebox(0,0){\footnotesize %s}}' % (y+6,label),
                  r'\put(%.2f,%g){\line(1,0){%.2f}}' % (lo,y,hi-lo),
                  r'\put(%.2f,%g){\line(0,1){2.8}}' % (lo,y-1.4),
                  r'\put(%.2f,%g){\line(0,1){2.8}}' % (hi,y-1.4),
                  r'\put(%.2f,%g){\circle*{1.5}}' % (mean,y)]
    lines += [r'\put(43,1){\makebox(0,0){\footnotesize Difference in MAE (AQI units)}}',r'\end{picture}}']
    first=p['uncertainty']['fold_01']
    lines += [r'\newcommand{\AirGuardCoverage}{%',r'\setlength{\unitlength}{1mm}',r'\begin{picture}(86,49)',
              r'\put(10,11){\line(1,0){72}}',r'\put(10,11){\line(0,1){29}}']
    for tick in (0,.5,1):
        y=11+tick*29
        lines += [r'\put(8,%.2f){\makebox(0,0)[r]{\scriptsize %g}}' % (y,tick)]
    for i,label in enumerate(('Good','Satis.','Moder.','Poor','V. Poor')):
        x=18+i*14
        n=first['split_0.8']['y_category'][str(float(i))]['n_exact']
        for offset,method,color in [(-3,'split_0.8','black'),(1,'split_0.9','gray')]:
            value=first[method]['y_category'][str(float(i))]['coverage']
            if value is not None and value>0:
                lines += [r'\put(%g,11){\textcolor{%s}{\rule{3.3mm}{%.3fmm}}}' % (x+offset,color,value*29)]
        if n<30:lines += [r'\put(%g,24){\makebox(0,0){\scriptsize $n<30$}}' % x]
        lines += [r'\put(%g,7){\makebox(0,0){\scriptsize %s}}' % (x,label),
                  r'\put(%g,3){\makebox(0,0){\scriptsize $n=%s$}}' % (x,n)]
    lines += [r'\put(16,45){\rule{3mm}{2mm}}\put(21,46){\makebox(0,0)[l]{\scriptsize Nominal 80\%}}',
              r'\put(52,45){\textcolor{gray}{\rule{3mm}{2mm}}}\put(57,46){\makebox(0,0)[l]{\scriptsize Nominal 90\%}}',
              r'\put(43,41){\makebox(0,0){\scriptsize Empirical exact-target coverage}}',r'\end{picture}}']
    lines += [r'\newcommand{\AirGuardWidths}{%',r'\setlength{\unitlength}{1mm}',r'\begin{picture}(86,48)',
              r'\put(12,9){\line(1,0){65}}\put(12,9){\line(0,1){31}}']
    for tick in (0,100,200,300):
        y=9+tick/320*31
        lines += [r'\put(9,%.2f){\makebox(0,0)[r]{\scriptsize %s}}' % (y,tick)]
    for i in range(12):
        x=14+i*5.5
        lines += [r'\put(%g,6){\makebox(0,0){\scriptsize %s}}' % (x,i+1)]
    for method,color in [('split_0.8','black'),('split_0.9','gray')]:
        points=[(14+i*5.5,9+f[method]['mean_width']/320*31) for i,f in enumerate(p['uncertainty'].values())]
        lines += [r'\color{'+color+'}']
        for x,y in points:lines += [f'\\put({x:.2f},{y:.2f}){{\\circle*{{1.2}}}}']
        for (x,y),(xx,yy) in zip(points,points[1:]):
            lines += [f'\\qbezier({x:.2f},{y:.2f})({(x+xx)/2:.2f},{(y+yy)/2:.2f})({xx:.2f},{yy:.2f})']
    lines += [r'\color{black}\put(42,1){\makebox(0,0){\footnotesize Chronological development fold}}',
              r'\put(43,44){\makebox(0,0){\scriptsize Mean interval width (AQI units)}}',
              r'\put(56,38){\makebox(0,0)[l]{\scriptsize Gray: 90\%}}\put(56,34){\makebox(0,0)[l]{\scriptsize Black: 80\%}}',r'\end{picture}}']
    return '\n'.join(lines)


ARCHITECTURE=r'''
\newcommand{\AirGuardArchitecture}{%
\setlength{\unitlength}{1mm}\begin{picture}(86,62)
\put(1,50){\framebox(40,11){\shortstack{Measured station bins\\Identity and locked QC}}}
\put(45,50){\framebox(40,11){\shortstack{Archived CAMS forecasts\\Run, lead, grid and units}}}
\put(21,50){\vector(0,-1){6}}\put(65,50){\vector(0,-1){6}}
\put(1,34){\framebox(84,10){\shortstack{20:00 IST feature snapshot\\Pre-issue availability guard}}}
\put(43,34){\vector(0,-1){4}}
\put(1,22){\framebox(84,8){\shortstack{Raw CAMS and direct or residual models}}}
\put(43,22){\vector(0,-1){4}}
\put(1,10){\framebox(84,8){\shortstack{Rolling and spatial tests; uncertainty and advisories}}}
\put(43,10){\vector(0,-1){4}}
\put(1,0){\framebox(84,6){Selection lock then human final-test approval}}
\end{picture}}
'''


def main():
    preliminary=read('results/research/preliminary_latest.json')
    if preliminary!=read(preliminary['artifact']) or preliminary['final_test_scored']:
        raise ValueError('An exact immutable non-CAMS development artifact is required')
    measured=read('results/research/measured_dataset.json')
    aligned=read('results/research/cams_development_alignment.json')
    archive=read('results/research/cams_development_acquisition.json')
    prospective=read('results/research/prospective_audit.json')
    lock=read('results/research/protocol_lock.json')
    actual=hashlib.sha256((ROOT/'docs/research/research_protocol.yaml').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    if actual!=lock['sha256'] or actual!=measured['protocol_sha256']:
        raise ValueError('Locked protocol mismatch')
    pair=preliminary['paired_comparisons'];first=preliminary['uncertainty']['fold_01']
    pending=r'\textit{Primary CAMS comparison: [RESULT PENDING CAMS ARCHIVE EXPERIMENT].}'
    abstract=r'''\begin{abstract}
Day-ahead air-quality forecasts require station-scale verification and an
explicit distinction between observations and modelled concentrations.
AirGuard India combines quality-controlled CPCB-provider measurements,
archived operational CAMS forecasts and a fixed 20:00 IST issue-time contract
to study station calibration, predictive uncertainty and exposure advisories.
The design compares climatology, persistence and raw CAMS with direct and
residual Ridge, LightGBM and XGBoost models using chronological and spatial
validation. Severe AQI is retained as an open-ended lower bound rather than
an exact regression label. A separate non-CAMS preliminary study finds a
paired MAE difference of -8.96 AQI units for strict Ridge versus climatology
(95\% date-block interval: -12.49 to -5.61), while history Ridge does not
establish improvement over persistence. In its first fold, both 80\% and
90\% intervals fail to cover any of 35 exact Very Poor outcomes. These
findings motivate severity-specific calibration checks and transparent
under-warning analysis. The genuine CAMS archive is partially acquired;
primary correction results remain pending and the final test remains sealed.
\end{abstract}
\begin{IEEEkeywords}air quality forecasting, CAMS, station calibration, conformal prediction, exposure advisories\end{IEEEkeywords}'''
    introduction=r'''\section{Introduction}
A useful next-day AQI forecast must describe what could have been issued
before the target day and how well that forecast agrees with measurements.
This distinction matters when an atmospheric model represents a grid cell,
while a resident or monitoring instrument represents a particular location.
Indian high-resolution pollution forecasting already has an established
research context \cite{jena2021delhi}. The present question is whether
India-specific station correction improves a genuine operational CAMS
baseline, and whether its uncertainty can support defensible warning choices.

AirGuard India fixes issuance at 20:00 IST for the next IST calendar day.
Its retrospective stream reconstructs measured targets and admissible
forecast features; its prospective stream freezes forecasts when actually
issued. A past model field without its producing run cannot establish an
operational forecast, and a deployed dashboard cannot establish predictive
skill. Both distinctions shape the evaluation.

The work provides three research components:
\begin{itemize}
\item a versioned station dataset with recorded rejection reasons, causal
history features and a shared CPCB-style AQI engine;
\item a locked comparison of raw CAMS, direct learning and residual
correction with rolling and spatial validation and censored-Severe diagnostics;
\item an uncertainty and advisory evaluation that reports coverage failures,
under-warning and over-warning, alongside immutable prospective verification.
\end{itemize}
The second and third components are evaluation commitments rather than
completed primary findings. This manuscript distinguishes existing measured-data
evidence from pending CAMS experiments and makes no world's-first claim.
'''
    related=r'''\section{Related Work}
\subsection{Atmospheric Forecast Post-processing}
Station-specific model output statistics is established. Riccio and Chianese
study statistical improvement of CAMS with spatial verification
\cite{riccio2024mos}; Petetin et al. examine the trade-off between continuous
and categorical ozone-forecast skill \cite{petetin2022mos}. Operational
regional CAMS production also includes statistical post-processing
\cite{colette2025cams}. Consequently, introducing a correction learner alone
does not establish novelty. AirGuard's contribution under investigation is
the audited Indian station evaluation and its warning behaviour.

\subsection{Uncertainty and Warning Decisions}
Conformal methods provide a framework for data-driven prediction intervals.
Time-series and distribution-shift settings require attention to dependence
and changing coverage \cite{xu2021enbpi,gibbs2021aci}. A narrow interval or
near-nominal aggregate coverage is insufficient if high-pollution categories
are systematically missed. Proper forecast evaluation also separates the
quantity predicted from the decision made from it \cite{gneiting2007scoring}.
Here, vulnerability groups specify exposure-warning tolerances; they do not
constitute clinical cohorts or individual health-risk models.

\subsection{Scope of the Comparison}
Published methods use different targets, locations and verification periods.
Their published scores are therefore not inserted into AirGuard's numerical
leaderboard. The shared-observation CAMS comparison, spatial inference
regimes and uncertainty failures must be established with this study's own
artifacts. A complete novelty assessment remains pending the primary study.
'''
    method=r'''\section{Proposed Method}
\subsection{Issue-time Data Contract}
For station $s$ and target day $d$, $X_{s,d}$ is assembled before issue time,
whereas $y_{s,d}$ is constructed later from measured pollutant concentrations.
Observations may contribute only when their bins end by 17:00 IST on $d-1$;
completed daily-history inputs are from $d-2$ or earlier. Weather summaries
use archived forecasts with a documented 48-hour Previous Runs offset.
Every admitted snapshot passes the availability guard. Historical observation
publication times are unavailable, so local-history skill is conditional on
the protocol's healthy-feed latency assumption.

\begin{figure}[t]\centering\footnotesize\AirGuardArchitecture
\caption{AirGuard study architecture. The primary model comparisons and
selection lock remain pending; prospective forecasts are a separate immutable
stream. Targets are not used to choose issue-time predictors.}\label{fig:architecture}
\end{figure}

\subsection{Measured Targets and Sensor Quality}
OpenAQ preserves the CPCB-provider station and sensor provenance
\cite{openaq2026}. Values must have convertible mass units, positive finite
concentrations, at least 75\% provider coverage and no provider rejection flag.
Exact zeros and identical sequences of six or more consecutive bins are
rejected under v3.1. Potential spikes and PM2.5 above PM10 remain flagged
observations. Feature QC uses the prefix visible at the cutoff; later readings
cannot revise an earlier feature. Rejected station-days remain in the dataset.

The common CPCB-style engine uses at least 16 distinct hours for each supported
pollutant, at least three supported species and a required particulate species
\cite{cpcb2014aqi}. Particulates and designated gases use 24-hour means;
CO and O$_3$ use the maximum complete trailing eight-hour mean, including
seven preceding support hours. For a bounded breakpoint interval,
\begin{equation}
I_p(C)=I_L+\frac{I_H-I_L}{C_H-C_L}(C-C_L),\qquad
I=\max_{p\in S}I_p(C_p).\label{eq:aqi}
\end{equation}
The result is an AirGuard CPCB-style index, not an official CPCB bulletin.
The Severe category is open-ended: $y\geq401$ is a lower bound.
Such targets are excluded from exact regression fitting and MAE/RMSE/bias;
category, exceedance, below-401 and lower-bound shortfall diagnostics retain them.

\subsection{Operational CAMS Reconstruction}
The ADS dataset is the global atmospheric-composition forecast archive,
not reanalysis \cite{cams2024forecasts}. GRIB type, producing date and time,
lead hours, valid time, grid and units are decoded and verified. The downloaded
grid is 0.4$^\circ$; matching uses the frozen nearest grid centre. At the declared
issue time the study uses the $d-1$ 00:00 UTC run, with nominal dissemination
treated explicitly as an assumption rather than an empirical delivery log.

Surface PM mass concentrations are converted from kg m$^{-3}$ to $\mu$g m$^{-3}$.
Gas mass mixing ratio $x$ uses the same run's lowest-model-level temperature
$T$, specific humidity $q$ and hybrid pressure $p$:
\begin{equation}
\rho=\frac{p}{287.05T(1+0.6078q)},\qquad C_{\mu\mathrm{g/m^3}}=10^9\rho x.
\label{eq:density}
\end{equation}
CO uses $10^6$ for mg m$^{-3}$. Model-level fields are interpolated within their
producing run before conversion. Missing brackets, hybrid coefficients or
inconsistent metadata cause rejection. Retrieval time records acquisition
provenance; it does not establish historical publication time.

\subsection{Direct and Residual Calibration}
Let $b_{s,d}$ denote the frozen raw CAMS AQI. Direct learners predict $y_{s,d}$;
residual learners fit exact measured-minus-CAMS labels:
\begin{equation}
r_{s,d}=y_{s,d}-b_{s,d},\qquad
\widehat y_{s,d}=\max\{0,b_{s,d}+f_\theta(X_{s,d})\}.\label{eq:residual}
\end{equation}
Ridge uses standardised, training-imputed features with an L2 penalty.
LightGBM and XGBoost provide nonlinear alternatives. Missing-value statistics
and learned parameters are fitted only on training rows. Predictor groups
comprise CAMS concentrations and descriptors, measured history, forecast
weather, calendar information and spatial context. Fire features remain
optional and require admissible publication evidence before evaluation.
Target-specific pollutant support is an evaluation annotation, never a predictor.
The current valid targets use the frozen PM2.5/PM10/O$_3$ support; the
six-pollutant index is a secondary comparison representing the live product.

\subsection{Uncertainty and Advisories}
Split conformal calibration uses exact calibration residuals $e_i$ with
\begin{equation}
\begin{aligned}
k&=\lceil(n+1)(1-\alpha)\rceil,\quad q_\alpha=e_{(k)},\\
\mathcal C(x)&=[\max(0,\widehat y-q_\alpha),\widehat y+q_\alpha].
\end{aligned}
\label{eq:conformal}
\end{equation}
If the finite-sample rank cannot be supported, an interval is unavailable.
Conformalised quantile LightGBM and forecast-category Mondrian calibration
are additional declared methods. Membership and quantile-crossing repair use
forecasts, never observed test categories. Censored-Severe compatibility
($U\geq401$) is not identified coverage of the unknown true index.

Advisory policies use the point forecast (P0), calibrated median (P1), fixed
0.75 quantile (P2), or the smallest candidate quantile meeting a calibration-only
under-warning target (P3). For observed category $c$ and warning category $w$,
\begin{equation}
L_-=\mathbf1\{w<c\},\quad L_+=\mathbf1\{w>c\},\quad
\widehat R_-=\frac{k_-+1}{n+1}.\label{eq:warning}
\end{equation}
The declared targets are 10\% for general adults and 5\% for the other exposure
strata. No feasible candidate is reported as such. Under dependence, these
are empirical goals rather than a guaranteed personal or clinical risk bound.
'''
    setup=r'''\section{Experimental Setup}
\subsection{Study Data and Provenance}
The locked window is 19 February 2025--7 October 2026. The metadata-only
sample selected 181 stations from an eligible catalogue of 481 stations in
255 parsed cities. Full-window counts in Table~\ref{tab:data} are inherited
descriptive metadata; final-test labels are not opened to produce this draft.
All analysis discussed here is development-only.
'''
    dataset_rows=[f'Usable measured stations / cities & {measured["usable_stations"]} / {measured["usable_cities"]}',
                  f'Retained measured station-days & {measured["station_days"]:,}',
                  f'Valid / rejected targets & {measured["valid_targets"]:,} / {measured["rejected_targets"]:,}',
                  f'Censored Severe targets & {measured["severe_days"]:,}',
                  f'Guarded CAMS-aligned development rows & {aligned["rows"]:,}',
                  f'Aligned stations / cities / dates & {aligned["stations"]} / {aligned["cities"]} / {aligned["dates"]}',
                  f'Aligned valid / rejected targets & {aligned["valid_targets"]:,} / {aligned["rejected_targets_retained"]:,}',
                  f'Verified raw archive chunks & {archive["counts"].get("VERIFIED_GRIB",0)} / 36']
    setup+=table('Measured dataset and current operational alignment. Completed measured targets are preserved; archive coverage is partial.','lr','Measure & Count',dataset_rows,'tab:data')
    setup+=r'''
\subsection{Chronological and Spatial Splits}
Expanding-window validation begins with 90 training dates, then 30 calibration
dates and 30 evaluation dates, advancing by 30 dates. One-day embargoes
separate adjacent partitions. Every station's row for a date moves together.
Station eligibility requires 120 valid training targets, so the first 90-day
training fold is necessarily insufficient; later outcomes cannot rescue it.
The latest 90 dates, 10 July--7 October 2026, remain sealed.

Spatial validation trains through 31 October 2025 and tests from 2 November
2025 through the final pre-test day. Ten-fold 25-km urban-cluster and station
holdouts, and six region holdouts, distinguish unseen cities from unseen
stations in seen clusters. Local-history and monitor-free inference are
reported separately. The all-station reference uses the same dates and test
pairs. Unavailable held-out monitor feeds must be masked in the corresponding
inference regime.

\subsection{Baselines and Training-only Tuning}
Climatology uses the station's training targets in the same month, with
station and global means as fallbacks. Persistence uses the rolling measured
24-hour index ending at the cutoff. Raw CAMS uses the same AQI engine.
The primary exact comparison requires all three baselines on identical pairs;
secondary comparisons relax only persistence availability. Severe days remain
in their category and lower-bound diagnostics.

Hyperparameters and early stopping use the last 30 dates of a fold's training
window as inner validation. Calibration and evaluation labels do not tune the
learner. All seeds are 42. The carry-forward model has the lowest mean
rolling-fold MAE, with ties favouring Ridge and residual formulations; raw
CAMS is retained if no learned model improves that criterion. Ablation fixes
the learner while varying feature groups. Fire admission requires a favourable
95\% paired date-block interval.
'''
    setup+=table('Declared primary search space. These are preregistered candidates, not selected parameters.',r'lp{.54\columnwidth}','Learner & Training-only choices',[
        r'Ridge & $\alpha\in\{0.1,1,10,100\}$',r'LightGBM & Leaves 15/31; minimum child samples 20/60',
        r'XGBoost & Depth 4/6; minimum child weight 5/20',r'Boosting controls & Rate 0.05; at most 600 rounds; early stop 40; row and column fractions 0.8'], 'tab:search')
    setup+=r'''
\subsection{Metrics and Statistical Comparison}
Exact-target MAE is primary; RMSE, signed forecast bias, coefficient of
determination and six-category diagnostics are secondary. Poor-or-worse and
Very-Poor-or-worse detection, false alarms and lower-bound Severe shortfall
are reported explicitly. Regional, seasonal and city-size subgroups below
30 pairs retain counts but withhold inferential metrics. Intervals are assessed
at 80\% and 90\% nominal coverage, with width and severity-specific coverage.

Paired comparisons preserve station/date pairs. Moving seven-day date blocks
with 5,000 resamples provide percentile intervals; daily mean loss differences
use a Diebold--Mariano comparison with Newey--West variance and Holm adjustment
\cite{diebold1995comparing}. An interval spanning zero does not establish a
nonzero difference. The immutable non-CAMS study uses a separate 30-valid-day
station rule and fixed Ridge $\alpha=10$; it cannot select the primary model.
'''
    results=r'''\section{Results and Discussion}
\subsection{Preliminary Measured-data Evidence}
The separate non-CAMS run contains 24 temporal evaluations (expanding and
sliding sensitivities), 36 spatial holdouts and 12 calibration evaluations.
Table~\ref{tab:paired} and Fig.~\ref{fig:paired} show two paired development
comparisons. Strict Ridge improves climatology on these pairs; history Ridge
does not establish improvement over persistence. These comparisons answer
neither the raw-CAMS correction question nor the locked final-test question.
'''
    rows=[]
    for key,label in [('ridge_strict_vs_climatology','Strict Ridge--climatology'),('ridge_history_vs_persistence','History Ridge--persistence')]:
        r=pair[key];rows.append(f'{label} & {r["mae_difference"]:+.2f} & [{r["ci95"][0]:+.2f}, {r["ci95"][1]:+.2f}] & {r["n"]:,}')
    results+=table('Non-CAMS preliminary paired MAE differences. Negative differences favour Ridge; intervals use seven-day date blocks.','lrrr',r'Comparison & $\Delta$MAE & 95\% interval & $n$',rows,'tab:paired')
    results+=r'''
\begin{figure}[t]\centering\AirGuardPaired
\caption{Paired non-CAMS development differences. The persistence comparison
crosses zero; a lower error than climatology does not establish a CAMS improvement.}
\label{fig:paired}\end{figure}

\subsection{Uncertainty and Extreme-event Failures}
First-fold marginal interval coverage masks a high-pollution failure.
Both nominal intervals cover none of the 35 exact Very Poor outcomes or
48 exact Poor-or-worse pairs. The individual Poor subgroup has only 13 pairs
and its subgroup metric is withheld. Figure~\ref{fig:coverage} retains these
denominators rather than treating unavailable estimates as zeros.
'''
    results+=table('First-fold non-CAMS interval diagnostics. Width is in AQI units; neither row establishes operational calibration.','lrrr',r'Nominal & Exact coverage & Mean width & $n$',[
        f'{int(first[m]["nominal"]*100)}\\% & {first[m]["coverage_exact"]:.3f} & {first[m]["mean_width"]:.1f} & {first[m]["n_exact"]:,}' for m in ('split_0.8','split_0.9')],'tab:coverage')
    results+=r'''
\begin{figure}[t]\centering\AirGuardCoverage
\caption{Non-CAMS first-fold coverage by observed category. Both Very Poor
estimates are zero; the Poor metric is unavailable at $n<30$. Satisfactory and
Moderate are abbreviated on the axis.}\label{fig:coverage}\end{figure}

\subsection{Primary CAMS Status}
'''+f'The request manifest verifies {archive["counts"].get("VERIFIED_GRIB",0)} of 36 chunks. The guarded join covers {aligned["dates"]} dates and '
    results+=f'{aligned["rows"]:,} station-days, retaining {aligned["rejected_targets_retained"]:,} rejected targets and {aligned["censored_severe_retained"]} censored Severe targets. '
    results+=r'''This coverage cannot support the locked training and verification
windows. No primary model has been fitted or selected. Missing archive months
are not replaced with reanalysis, later operational fields or fabricated data.
'''+pending+r'''

\subsection{Prospective Application}
'''+f'The audited ledger has {prospective["forecasts"]} immutable forecasts across {prospective["issued_target_days"]} target days and {prospective["verified_days"]} verified days. '
    results+=f'{prospective["station_bound_forecasts"]} forecasts have pre-issue station bindings; {prospective["historical_forecasts_missing_git_sha"]} historical entries lack an issuance Git SHA. '
    results+=r'''Missing historical identities or station bindings are not inferred
after the outcome. The production application displays raw CAMS-based estimates;
no experimental correction or unvalidated interval is deployed. Its interface
and API checks establish software behaviour, while predictive skill requires
matched outcomes and the declared research evaluation.
'''
    limitations=r'''\section{Limitations}
\subsection{Availability and Representation}
The current catalogue can introduce survivorship bias, and the measured sample
does not establish nationwide representativeness. A coarse CAMS grid and a
station describe different spatial supports. Historical station ingestion
times and empirical per-run CAMS delivery logs are unavailable; nominal
publication and healthy-feed assumptions remain explicit. Optional fire
acquisition timestamps do not prove publication before issue.

\subsection{Statistical and Advisory Scope}
Preliminary measured-data gains cannot establish correction of raw CAMS.
Temporal and spatial dependence limit textbook exchangeability arguments;
coverage and warning-risk attainment are empirical findings. Rare high-pollution
groups may be too small for stable inference. Warning groups specify exposure
guidance tolerances, not diagnoses, prescriptions, personal disease probabilities
or causal health benefits.

\subsection{Outstanding Research Gates}
Paired archive coverage, primary experiments, reproducibility and the actual
model-selection lock remain incomplete. The final interval can be opened only
after a committed configuration lock, a READY evidence audit and fresh human
approval. Formatting and software deployment cannot release that gate.
'''
    conclusion=r'''\section{Conclusion and Future Work}
AirGuard provides a measured-station dataset, an audited operational forecast
pipeline and a locked design for testing station correction and warning
calibration. Existing non-CAMS evidence supports a gain over climatology but
does not establish a gain over persistence, and shows severe subgroup failures
despite useful marginal coverage. The main CAMS comparison and final-test
results remain pending. Completing the archived cube will permit the declared
temporal, spatial, uncertainty and advisory analyses; future prospective records
must bind stations before issuance and accumulate real verified outcomes.
'''
    reproducibility=r'''\section{Reproducibility and Data Availability}
The research branch provides acquisition manifests, QC definitions, feature
guards, split utilities, experiment configurations and claim-evidence mappings.
Raw and derived files have checksums; versioned caches are outside Git.
The measured semantic hash begins \texttt{4761a5da60dde059}, the protocol hash
\texttt{e24b664747029a76}, and the immutable preliminary run
\texttt{287c87db04a6b294}. Full identifiers are supplied in the companion manifest.
A measured-data reconstruction passed its recorded semantic audit; complete
primary reproduction remains pending. Current incomplete analyses are not
represented by a fictitious model-selection lock.

\section*{Acknowledgment and Disclosure}
Claude Code and OpenAI Codex assisted software, tests and manuscript drafting.
The author is responsible for verifying the methods, citations, results and
disclosures before submission. No human-subject study or clinical validation
is claimed. The supplied LogSight paper informs presentation structure only;
its content, author list, model settings and numerical results are not reused.
'''
    journal_extra=r'''
\subsection{Feature Availability Audit}
The feature contract distinguishes a value's valid time from when it could
have been available. A forecast can describe future valid hours while still
being an admissible pre-issue input; an observation cannot. Retrieving an old
field today is insufficient without its producing-run identity. The same
distinction applies to archived weather, measured-history latency and fire
publication. Table~\ref{tab:availability} documents the admitted groups and
remaining assumptions.
'''+table('Feature availability and operational assumptions. Static metadata and the calendar do not require outcome information.',r'lp{.62\columnwidth}','Group & Admitted information',[
        'A CAMS & Verified operational run, concentrations, sub-indices and diurnal descriptors',
        'B History & Bins ending by 17:00 IST; completed daily lags from $d-2$; healthy-feed assumption',
        'C Weather & Archived previous-run forecasts with pre-issue run bound',
        'D Calendar & Target-day month, weekday and cyclical season information',
        'E Spatial & Frozen coordinates, terrain and admissible pre-issue neighbours',
        'F Fire & Optional; withheld without historical publication evidence'],'tab:availability')+r'''
\subsection{Baseline Support and Missingness}
The primary CAMS comparison does not credit a learner for removing a species
the station failed to measure. Frozen PM2.5/PM10/O$_3$ support is defined from
sensor metadata; the current valid join has no support mismatch. The
six-pollutant index remains a secondary comparator because it is closer to
the live product's display. Both are produced by the same engine, so target
and baseline breakpoints, averaging windows and Severe treatment cannot drift.

History lags use station/date keys rather than row offsets. Missing days remain
missing; neither targets nor forecast indices are borrowed from the wrong date.
Censored historical values are not fabricated exact bias labels. Neighbour
summaries use cutoff-compliant measurements and exclude self-donations.
Monitor-free spatial regimes must remove unavailable donor feeds, not merely
drop a station identifier. Missing predictors are imputed using training-only
statistics with indicators, preserving the conditions under which a forecast
could be issued.

\subsection{Advisory Evaluation Contract}
Under-warning and over-warning are evaluated jointly. Serious under-warning
(two or more categories), misses on Poor-or-worse days and warning distance
are separate diagnostics. P1 and P2 use one-sided calibration of their fixed
quantiles; P3 selects among declared raw quantile forecasts on the calibration
window. That selection is itself its calibration step. No test-window outcome
can select a warning level or repair an interval.

The candidates are $\{0.5,0.65,0.75,0.85,0.9,0.95,0.975\}$.
An absent feasible candidate is a failed empirical risk target, not an excuse
to relabel a permissive warning as controlled. Shared station outcomes across
the seven exposure strata are not seven independent clinical samples.
The final report must retain unfavourable trade-offs, including cases where
reduced under-warning requires substantial over-warning.
'''
    journal_width=r'''
\subsection{Calibration Stability Across Folds}
Figure~\ref{fig:width} displays mean interval widths for the existing non-CAMS
folds. These are fold-level summaries, not a reconstructed histogram of
individual intervals. Both width and coverage must be inspected: wider
intervals can improve marginal coverage while retaining poor subgroup
performance. A censored Severe outcome identifies a lower bound, so whether
an upper endpoint reaches 401 is reported separately from exact coverage.
\begin{figure}[t]\centering\AirGuardWidths
\caption{Non-CAMS preliminary mean widths across chronological folds.
The calibrated intervals remain development diagnostics rather than
validated operational intervals.}\label{fig:width}\end{figure}

\subsection{Evidence Boundaries}
The initial 90-day training fold cannot meet a station's 120-valid-day
eligibility requirement. It is preserved as insufficient rather than
rescued using later coverage. The preliminary non-CAMS study's separate
30-day station threshold and fixed penalty therefore must not be conflated
with primary tuning. Likewise, paired regression evidence is restricted to
exact targets; censored observations are retained for the declared category
and lower-bound analysis.

The comparison with persistence is an important negative finding.
A confidence interval containing zero does not demonstrate that two methods
are identical, but it also does not support claiming a reliable difference.
The first-fold Very Poor interval failure demonstrates why a single average
coverage number cannot justify high-pollution warnings. These observations
support the evaluation design, not a claim that station correction already
improves genuine archived CAMS.
'''
    journal_order={'abstract':abstract,'introduction':introduction,'related_work':related,
        'proposed_method':method+journal_extra,'experimental_setup':setup,
        'results_discussion':results+journal_width,'limitations':limitations,
        'conclusion':conclusion,'reproducibility':reproducibility}
    conference_order={'abstract':abstract,'introduction':introduction,'related_work':related,
        'proposed_method':method,'experimental_setup':setup,'results_discussion':results,
        'limitations':limitations,'conclusion':conclusion+reproducibility.replace(r'\section{Reproducibility and Data Availability}',r'\subsection{Reproducibility}')}
    preamble=r'''\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,booktabs,url,graphicx,xcolor,balance}
'''+ARCHITECTURE+charts(preliminary)
    journal_header=r'\documentclass[journal]{IEEEtran}'+'\n'+preamble+'\n'+r'\title{'+TITLE+'}\n'+r'''\author{Nishanth R\thanks{Nishanth R is with the Department of AI and Data Science,
Rajalakshmi Engineering College, Chennai, Tamil Nadu, India.
Email: nishanth.r.2024.aids@rajalakshmi.edu.in; backup: nishanth.artwork@gmail.com.}
\thanks{Development draft. Primary CAMS results are pending; the final test remains sealed.}}
\begin{document}\maketitle
'''
    conference_header=r'\documentclass[conference,a4paper]{IEEEtran}'+'\n'+preamble+'\n'+r'\title{'+TITLE+'}\n'+r'''\author{\IEEEauthorblockN{Nishanth R}
\IEEEauthorblockA{Department of AI and Data Science\\
Rajalakshmi Engineering College\\Chennai, Tamil Nadu, India\\
nishanth.r.2024.aids@rajalakshmi.edu.in}}
\begin{document}\maketitle
'''
    for variant,header,sections in [('journal',journal_header,journal_order),('conference',conference_header,conference_order)]:
        for name,text in sections.items():write(f'paper/{variant}/sections/{name}.tex',text)
        main=header+'\n'.join(r'\input{sections/'+name+'}' for name in sections)
        main+='\n'+r'\balance'+'\n'+r'\bibliographystyle{IEEEtran}'+'\n'+r'\bibliography{../references}'+'\n'+r'\end{document}'
        write(f'paper/{variant}/main.tex',main)
    # Standalone journal source remains in the already-open editor. Embedded
    # verified bibliography and native vector pictures require no extra files.
    old=(ROOT/'paper/station_calibration_skeleton.tex').read_text(encoding='utf-8')
    bibliography=old[old.index(r'\begin{thebibliography}'):old.index(r'\end{thebibliography}')+len(r'\end{thebibliography}')]
    flattened=journal_header+'\n'.join(journal_order.values())+'\n'+r'\balance'+'\n'+bibliography+'\n'+r'\end{document}'
    write('paper/station_calibration_skeleton.tex',flattened)
    paths=[ROOT/'paper/station_calibration_skeleton.tex',ROOT/'paper/references.bib']
    for variant in ('conference','journal'):
        paths += [ROOT/f'paper/{variant}/main.tex',*[ROOT/f'paper/{variant}/sections/{n}.tex' for n in (conference_order if variant=='conference' else journal_order)]]
    manifest={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'format_reference':'LogSight Paper.docx',
        'reference_sha256':'c939393c3fd49a975080839898d4220e29ccee26a0b3f4b18893949b6101a8c1',
        'scope':'Presentation structure only; original AirGuard evidence and methods',
        'protocol_sha256':actual,'measured_semantic_sha256':measured['dataset_hash'],
        'alignment_sha256':aligned['sha256'],'preliminary_artifact':preliminary['artifact'],
        'preliminary_sha256':digest(ROOT/preliminary['artifact']),
        'primary_model_selected':False,'final_test_accessed':False,'submission_ready':False,
        'source_hash_method':'sha256_lf_normalized',
        'files':{str(p.relative_to(ROOT)).replace('\\','/'):source_digest(p) for p in paths}}
    write('paper/publication_format_manifest.json',json.dumps(manifest,indent=2))
    write('paper/journal/draft_manifest.json',json.dumps({
        'status':'DEVELOPMENT_DRAFT_PRIMARY_RESULTS_PENDING',
        'final_test_accessed':False,'model_selected':False,
        'format_manifest':'paper/publication_format_manifest.json',
        'source_hash_method':'sha256_lf_normalized',
        'files':{path:sha for path,sha in manifest['files'].items()
                 if '/conference/' not in path}},indent=2))
    print(json.dumps({'conference':'paper/conference/main.tex','journal':'paper/journal/main.tex','standalone_edited_in_place':True,'final_test_accessed':False}))


if __name__=='__main__':main()
