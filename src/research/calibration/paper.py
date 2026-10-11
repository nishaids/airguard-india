"""Generate a standalone six-page IEEE skeleton from verified local artifacts."""
import json
import math
import re
import hashlib
from pathlib import Path
from src import config
from src.research.calibration.checkpoint import OUT, write_json
from src.research.calibration.protocol import load

PREVIOUS_RUNS_URL = 'https://open-meteo.com/en/docs/previous-runs-api'
COMPARISONS = {
    'ridge_strict_vs_climatology': ('Strict Ridge', 'climatology'),
    'ridge_history_vs_persistence': ('History Ridge', 'persistence'),
}


def tex_escape(value):
    """Escape text, preserving existing BibTeX escapes and protective groups."""
    replacements = {'&': r'\&', '_': r'\_', '%': r'\%', '$': r'\$', '#': r'\#',
                    '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return re.sub(r'\\[&_%$#{}]|[&_%$#~^]',
                  lambda match: match.group() if match.group().startswith('\\') else replacements[match.group()],
                  str(value))


def tex_identifier(value):
    """Keep complete artifact hashes, allowing line breaks inside IEEE columns."""
    value = str(value)
    return r'\allowbreak'.join(r'\texttt{' + tex_escape(value[i:i+16]) + '}'
                              for i in range(0, len(value), 16))


def _balanced(text, begin, opening='{', closing='}'):
    depth, end = 1, begin
    while end < len(text) and depth:
        if text[end] == '\\':
            end += 2
            continue
        depth += (text[end] == opening) - (text[end] == closing)
        end += 1
    if depth:
        raise ValueError('Unbalanced inherited BibTeX entry')
    return text[begin:end-1], end


def _bib_fields(body):
    """Parse braced, quoted and bare values without discarding verified fields."""
    fields, position = {}, 0
    while match := re.search(r'([A-Za-z]+)\s*=\s*', body[position:]):
        name = match.group(1).lower()
        begin = position + match.end()
        if body[begin] == '{':
            value, end = _balanced(body, begin+1)
        elif body[begin] == '"':
            end = begin+1
            while end < len(body) and (body[end] != '"' or body[end-1] == '\\'):
                end += 1
            if end == len(body):
                raise ValueError('Unterminated inherited BibTeX value')
            value, end = body[begin+1:end], end+1
        else:
            end = body.find(',', begin)
            if end < 0:
                end = len(body)
            value = body[begin:end].strip()
        fields[name], position = value, end
    return fields


def _linked_text(value):
    parts = re.split(r'(https?://[^\s{}]+)', value)
    return ''.join(r'\url{' + part + '}' if part.startswith(('https://', 'http://'))
                   else tex_escape(part) for part in parts)


def _bib_content(fields):
    pieces = []
    if fields.get('author'):
        pieces.append(tex_escape(fields['author']))
    if fields.get('title'):
        pieces.append('``' + tex_escape(fields['title']) + "''")
    for name in ('journal', 'booktitle', 'institution', 'howpublished', 'series', 'publisher'):
        if fields.get(name):
            pieces.append(_linked_text(fields[name]))
    for name, label in (('volume', 'vol. '), ('number', 'no. '), ('pages', 'pp. ')):
        if fields.get(name):
            pieces.append(label + tex_escape(fields[name]))
    if fields.get('year'):
        pieces.append(tex_escape(fields['year']))
    if fields.get('eprint'):
        prefix = fields.get('archiveprefix', 'eprint')
        identifier = fields['eprint']
        value = r'\url{https://arxiv.org/abs/' + identifier + '}' if prefix.lower() == 'arxiv' else tex_escape(identifier)
        pieces.append(tex_escape(prefix) + ': ' + value)
    if fields.get('doi'):
        pieces.append('DOI: ' + r'\url{https://doi.org/' + fields['doi'] + '}')
    if fields.get('url'):
        pieces.append(r'\url{' + fields['url'] + '}')
    if fields.get('note'):
        pieces.append(_linked_text(fields['note']))
    return ', '.join(pieces) + '.'


def bib_entries(text=None):
    """Read generated, inherited BibTeX; no new references are authored here."""
    if text is None:
        text=(config.PROJECT_ROOT/'paper/refs.bib').read_text(encoding='utf-8')
    wanted={'cams2024forecasts','openaq2026','openmeteo2026','cpcb2014aqi',
            'gibbs2021aci','xu2021enbpi','diebold1995comparing','gneiting2007scoring','jena2021delhi'}
    entries=[]
    for match in re.finditer(r'@\w+\s*\{\s*([^,]+),',text):
        key=match.group(1).strip()
        if key not in wanted:
            continue
        body, _ = _balanced(text, match.end())
        entries.append(r'\bibitem{'+key+'} ' + _bib_content(_bib_fields(body)))
    return '\n'.join(entries)


def comparison_findings(result):
    """Report the stored signed differential; no direction is baked into prose."""
    findings = []
    for key, (first, second) in COMPARISONS.items():
        entry = result.get('paired_comparisons', {}).get(key, {})
        delta, interval = entry.get('mae_difference'), entry.get('ci95')
        if delta is None or not math.isfinite(delta):
            findings.append(f'{first} versus {second}: paired evidence unavailable.')
            continue
        relation = 'lower paired MAE than' if delta < 0 else 'higher paired MAE than' if delta > 0 else 'the same paired MAE as'
        phrase = f'{first} had {relation} {second} (signed difference {delta:+.2f} AQI'
        if interval is not None and len(interval) == 2 and all(math.isfinite(x) for x in interval):
            low, high = interval
            if low > high:
                raise ValueError('Stored paired confidence interval is reversed')
            phrase += f'; 95% date-block interval [{low:+.2f}, {high:+.2f}]'
            conclusion = ('lower MAE supported by this interval' if high < 0 else
                          'higher MAE supported by this interval' if low > 0 else
                          'a nonzero MAE difference is not established by this interval')
        else:
            conclusion = 'confidence-interval evidence unavailable'
        phrase += f'; n={entry.get("n", "unreported")} exact pairs); {conclusion}.'
        findings.append(phrase)
    return tex_escape(' '.join(findings))


def find_experiment_quality(result, current_quality):
    """Resolve counts from the exact dataset used by the immutable experiment."""
    if result['dataset_hash'] == current_quality['dataset_hash']:
        if result['data_version'] != current_quality['data_version']:
            raise ValueError('Experiment/acquisition data-version disagreement')
        return current_quality
    root = config.PROJECT_ROOT/'data/research/derived'/result['data_version']
    for path in sorted(root.glob('*/quality_report.json')):
        value = json.loads(path.read_text(encoding='utf-8'))
        if value['dataset_hash'] == result['dataset_hash'] and value['data_version'] == result['data_version']:
            return value
    raise ValueError('The exact experiment dataset quality artifact is unavailable; do not substitute acquisition counts')


def dataset_evidence(quality, experiment_quality, result):
    if experiment_quality['dataset_hash'] != result['dataset_hash'] or experiment_quality['data_version'] != result['data_version']:
        raise ValueError('Experiment quality counts do not match its dataset identity')
    fields = ('usable_stations', 'usable_cities', 'valid_targets', 'rejected_targets', 'severe_days')
    return {'acquisition_dataset_hash': quality['dataset_hash'],
            'acquisition_data_version': quality['data_version'],
            'experiment_dataset_hash': result['dataset_hash'],
            'experiment_data_version': result['data_version'],
            'datasets_identical': quality['dataset_hash'] == result['dataset_hash'],
            'acquisition_minus_experiment_counts': {k: quality[k]-experiment_quality[k] for k in fields},
            'experiment_input_counts': {k: experiment_quality[k] for k in fields},
            'acquisition_counts': {k: quality[k] for k in fields}}


def prospective_findings(prospect):
    pieces = []
    if 'station_bound_forecasts' in prospect:
        missing = prospect['forecasts']-prospect['station_bound_forecasts']
        pieces.append(f'{prospect["station_bound_forecasts"]} forecasts have a bound station; {missing} do not.')
        if missing:
            pieces.append('Unbound records cannot be made station forecasts by retrospectively selecting an outcome monitor.')
    if 'historical_forecasts_missing_git_sha' in prospect:
        pieces.append(f'{prospect["historical_forecasts_missing_git_sha"]} historical forecasts lack an issuance Git SHA; missing identities will not be invented.')
    if prospect.get('correction_deployed') is False:
        pieces.append('No experimental correction is deployed.')
    elif prospect.get('correction_deployed') is True:
        pieces.append('The audit reports a deployed correction; its validation evidence requires separate review.')
    return tex_escape(' '.join(pieces))


def render_source(quality, result, prospect, experiment_quality, protocol, selection, references):
    evidence = dataset_evidence(quality, experiment_quality, result)
    source=r'''\documentclass[conference]{IEEEtran}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,booktabs,url}
\title{AirGuard India: Station Calibration, Uncertainty and Prospective Verification of Day-Ahead Air Quality}
\author{\IEEEauthorblockN{Nishanth R, NAME, NAME}
\IEEEauthorblockA{Affiliations and author consent pending}}
\begin{document}
\maketitle
\begin{abstract}
This unsubmitted skeleton documents an India-specific station-calibration
protocol locked before model fitting; the manuscript itself is not a new
preregistration. The intended comparison is raw operational CAMS versus direct learning
and residual correction, followed by uncertainty calibration and exposure
advisory evaluation. Hourly quality rules, chronological and spatial validation,
and a sealed final test constrain the analysis. The genuine historical CAMS
issue-time archive remains unavailable. A separate preliminary measured-data
study is reported as infrastructure evidence, without a CAMS improvement claim.
Real prospective forecasts are frozen, but matched measured outcomes remain
pending. [RESULT PENDING CAMS ARCHIVE EXPERIMENT]
\end{abstract}
\begin{IEEEkeywords}CAMS, air quality, India, calibration, prospective verification\end{IEEEkeywords}
\section{Problem and Related Work}
The research question is whether a correction learned at Indian stations
improves next-day CPCB-style AQI while retaining useful uncertainty and warning
behaviour. Atmospheric forecasts and measured concentrations have different
provenance. Existing Indian forecasting systems establish that this is an
evaluation problem, not an unoccupied application domain \cite{jena2021delhi}.
Station MOS, CAMS statistical post-processing, conformal intervals and risk
calibration are established methods. The targeted review records overlapping
European CAMS work and distinguishes Indian reanalysis mapping from genuine
issue-time prediction. No world's-first claim is made. The contribution under
test is the audited Indian operational procedure and its empirical warning
trade-offs. Full-text novelty review remains incomplete.
\section{Study Status}
Two streams are kept separate: frozen current forecasts constitute the
prospective study; measured historical targets support non-CAMS preliminary
research. Neither substitutes for the blocked primary archive comparison.
\clearpage
\section{Data, Targets and Quality}
OpenAQ preserves upstream CPCB-provider station identity; its measurements are
not an official CPCB bulletin or licensed CCR export \cite{openaq2026}.
The inherited catalogue contains @CATALOGUE_STATIONS@ eligible stations across @CATALOGUE_CITIES@ parsed cities;
the metadata-only stratified sample selects @SELECTED_STATIONS@ stations in @SELECTED_CITIES@ cities. Current
catalogue selection can introduce survivorship bias and is disclosed.
The locked v3.1 window is @STUDY_START@ through @STUDY_END@. The protocol was
locked at @LOCKED_AT@; its prior version and hash remain in the lock history.
Its immutable hash is recorded in the result artifact. This acquisition checkpoint has
@STATIONS@ usable stations, @CITIES@ cities, @VALID@ valid targets and @REJECTED@
retained rejected station-days. These are partial-collection counts, not
national study acceptance.

@DATASET_IDENTITIES@

The single CPCB-style engine applies pollutant breakpoints, at least sixteen
distinct hours per pollutant, at least three supported pollutants and a required
particulate species \cite{cpcb2014aqi}. Particulates and the designated gases use
24-hour means; CO and ozone use the maximum complete trailing eight-hour mean.
Targets are labelled AirGuard CPCB-style AQI. Exact zeros, provider flags, poor
coverage and six-hour identical runs are rejected. PM2.5 above PM10 and potential
spikes are flagged and retained. Raw caches and row-addressable rejection ledgers
preserve exclusions. Unsupported ppb conversion is refused.

Severe AQI is an open lower bound of at least 401. The checkpoint contains
@SEVERE@ censored Severe days. They cannot supply exact residual labels or
identified MAE, RMSE, bias or coefficient-of-determination values. Category,
exceedance, forecasts below 401 and lower-bound shortfall remain estimable.
\section{Issue-Time Availability}
Issue time is 20:00 IST on the preceding day. Observation bins must end by
17:00 IST; daily history is D-2 or earlier. Historical OpenAQ publication time
is unknown, so measured-history analyses explicitly assume a healthy feed.
Archived weather uses the documented 48-hour Previous Runs offset
at \url{@PREVIOUS_RUNS_URL@}. The Air Quality API documentation is a separate
source \cite{openmeteo2026}. FIRMS acquisition time alone does not establish release
time. CAMS past fields without their producing run are excluded from the primary
experiment. Every admitted snapshot passes its guard.
\clearpage
\section{Primary Forecast and Correction}
The genuine CAMS global forecast archive \cite{cams2024forecasts} must retain
initialisation, lead, valid time, units and evidence of pre-issue availability.
Reanalysis is prohibited as a replacement. The locked v3.1 protocol specifies
target-support-matched CAMS scoring and a six-pollutant secondary comparator.
Later target support is an evaluation annotation and cannot become a predictor.
Verification of an operational pollutant-support policy and its compatible
primary runner remains pending archive integration. Any change to the locked
comparison requires a transparent protocol amendment before primary fitting,
without consulting final-test outcomes.
All methods share observations and evaluation windows. With frozen CAMS index
$b_{s,d}$ and exact measured index $y_{s,d}$, residual learning uses
\begin{equation}r_{s,d}=y_{s,d}-b_{s,d},\qquad
\widehat y_{s,d}=b_{s,d}+\widehat r_{s,d}.\end{equation}
The ladder comprises raw CAMS, direct ML, residual Ridge, residual LightGBM and
residual XGBoost, with persistence and prior-only climatology as operational
floors. There is no assumption that correction wins. The legacy city model has
a different period, target and input representation, and is reported separately.

\begin{table}[h]\centering\caption{Primary comparison contract}
\begin{tabular}{ll}\toprule Method & Result \\\midrule
Raw operational CAMS & Pending archive \\
Direct ML & Pending archive \\
Residual Ridge & Pending archive \\
Residual LightGBM & Pending archive \\
Residual XGBoost & Pending archive \\\bottomrule\end{tabular}\end{table}

\section{Selection and Ablation}
Model settings use training-only inner validation. The locked protocol fixes
90 training days initially, 30 calibration days, 30 test days, a 30-day step and
one-day embargo gaps, with expanding training windows. Each fold is reported.
The latest @FINAL_DAYS@ dates, @FINAL_START@ through @FINAL_END@, are sealed.
@FINAL_STATUS@ Feature ablation separates CAMS, measured history,
forecast weather, calendar, spatial context and optional fires. Fire admission
requires a date-block interval supporting its benefit. An additional sliding
90-day non-CAMS sensitivity is labelled separately.
[RESULT PENDING CAMS ARCHIVE EXPERIMENT]
\clearpage
\section{Temporal and Spatial Verification}
Primary evaluation will report exact-target MAE, RMSE, signed forecast bias,
coefficient of determination, six-category diagnostics, threshold detection,
false alarms and censored-Severe shortfall. Poor, Very Poor and Severe events
receive explicit diagnostics. Seasonal and regional groups below thirty pairs
are listed with counts and withheld metrics.
Spatial tests isolate cities, 25-km connected urban clusters, stations and
regions. Local-history and monitor-free inference are distinct conditions.
Held-out station targets cannot determine training eligibility. The all-station
reference is scored on the identical held-out test rows.

Paired comparison uses seven-day moving date blocks with 5,000 resamples and
a two-sided Diebold--Mariano daily loss comparison with Newey--West variance
and Holm multiplicity adjustment \cite{diebold1995comparing}. A confidence
interval containing zero does not establish improvement.
\section{Preliminary Results Contract}
The separate non-CAMS run completed @FOLDS@ temporal evaluations,
@SPATIAL@ spatial holdouts and @CALIBRATIONS@ calibration-window evaluations;
@FOLDS_SKIPPED@ temporal and @SPATIAL_SKIPPED@ spatial entries lacked sufficient data.
Its predictions and per-fold metrics come from the exact immutable artifact
identified above. @COMPARISON_FINDINGS@
These preliminary comparisons do not establish production approval. They do not answer
whether CAMS station correction improves a genuine operational baseline.
The definitive results table and skill figure remain:
[RESULT PENDING CAMS ARCHIVE EXPERIMENT]

\section{Reproducibility}
Files and decompressed cache content have SHA-256 manifests. Dataset identity,
feature version, protocol hash, source hash and run configuration accompany each
result. Local station reconstruction is audited independently of derived caches.
A complete clean-clone primary reproduction remains pending. Numerical values
in this skeleton are generated from evidence artifacts, never filled manually.
\clearpage
\section{Uncertainty Calibration}
Split conformal intervals at 80\% and 90\%, quantile calibration and
forecast-category Mondrian calibration use only the preceding calibration
window. Coverage and widths are reported by category, season and region.
For a censored Severe outcome, an upper bound reaching 401 is merely compatible
with the known lower bound; it does not identify true-value coverage.
Calibration under temporal and spatial shift is evaluated empirically;
exchangeability guarantees are not asserted for dependent station-days
\cite{gibbs2021aci,xu2021enbpi}. Proper uncertainty scoring requires identified
outcomes \cite{gneiting2007scoring}.
\section{Vulnerability-Aware Advisory Evaluation}
Declared exposure strata include general adults, children, older adults,
asthma/COPD, heart conditions, pregnancy and outdoor workers. They are not
personal medical-risk predictions. P0 uses the point forecast; P1 the calibrated
median; P2 the calibrated 0.75 quantile; P3 the smallest calibration-window
candidate achieving the corrected empirical under-warning aim $(k+1)/(n+1)$.
The aims are 10\% for general adults and 5\% for the other declared strata.
If no candidate qualifies, the policy reports that fact.
Under-warning, over-warning, serious under-warning and high-pollution misses
are reported alongside date-block confidence intervals. A lower warning rate
does not demonstrate a health benefit. Unsupported cohort coefficients remain
unadopted. [RESULT PENDING CAMS ARCHIVE EXPERIMENT]
\section{Prospective Verification}
The current ledger contains @FORECASTS@ real forecasts across @ISSUED_DAYS@
target days, and @VERIFIED_DAYS@ verified days. @PROSPECTIVE_FINDINGS@
Station binding and deployment identity must be present before future issue. Issued
forecasts are immutable; a thirty-day track record requires real elapsed days
and matched outcomes.
\clearpage
\section{Limitations and Planned Completion}
ADS credentials and manual dataset terms acceptance block the genuine CAMS
comparison. Partial station acquisition, current-catalogue survivorship,
unknown historical observation latency and limited extreme-event support bound
the preliminary analysis. Optional fire release time remains unproven. The
initial station-free prospective forecasts do not establish station forecast
skill. Final-test isolation, transparent artifacts and explicit missing results
are necessary conditions for completion, not evidence of improved accuracy.
The intended completed narrative is CAMS baseline, India-specific correction,
rolling/spatial testing, calibrated uncertainty, cohort advisory trade-offs and
prospective station verification.
\section{Conclusion}
The recovery preserves the existing protocol and acquisition checkpoint, and
extends measured-data and non-CAMS infrastructure. Correction performance,
operational intervals, advisory risk attainment and thirty-day verification
remain hypotheses. [RESULT PENDING CAMS ARCHIVE EXPERIMENT]
\section*{Ethics and AI Disclosure}
No human-subject data was collected. Cohort guidance is environmental exposure
advice, not validated medical advice. Any participant study requires prior
ethics approval and consent. Claude Code and OpenAI Codex assisted software,
tests and drafting. Authors must review the methods, bibliography, disclosures
and generated claims before submission. Author placeholders remain unresolved.
\begin{thebibliography}{99}
@REFERENCES@
\end{thebibliography}
\end{document}
'''
    changes = evidence['acquisition_minus_experiment_counts']
    difference = ('Both checkpoints have the same dataset identity.' if evidence['datasets_identical'] else
                  'The acquisition and experiment datasets differ; acquisition counts must not be attributed '
                  'to this experiment. Acquisition minus experiment counts are '
                  f'{changes["usable_stations"]:+d} usable stations, {changes["usable_cities"]:+d} cities, '
                  f'{changes["valid_targets"]:+d} valid targets, {changes["rejected_targets"]:+d} rejected '
                  f'station-days and {changes["severe_days"]:+d} censored Severe days.')
    identities = ('The acquisition dataset SHA-256 is ' + tex_identifier(quality['dataset_hash']) + '. '
                  'The preliminary experiment input dataset SHA-256 is ' + tex_identifier(result['dataset_hash']) + ', '
                  f'with {experiment_quality["usable_stations"]} usable stations, '
                  f'{experiment_quality["usable_cities"]} cities, {experiment_quality["valid_targets"]} valid '
                  f'targets, {experiment_quality["rejected_targets"]} retained rejected station-days and '
                  f'{experiment_quality["severe_days"]} censored Severe days before final-test isolation. '
                  + tex_escape(difference) + ' The immutable preliminary run is ' + tex_identifier(result['run_id']) + '.')
    complete_folds = [f for f in result['folds'] if f.get('strict')]
    complete_spatial = [f for f in result['spatial'] if f.get('ridge_strict')]
    scored = result.get('final_test_scored')
    final_status = ('The referenced result artifact declares final-test scoring; selection provenance requires audit.'
                    if scored is True else
                    'The referenced result artifact declares that no final-test scoring was performed.' if scored is False else
                    'Final-test scoring status is unavailable in the referenced result artifact.')
    replacements={'STATIONS':quality['usable_stations'],'CITIES':quality['usable_cities'],
                  'VALID':quality['valid_targets'],'REJECTED':quality['rejected_targets'],'SEVERE':quality['severe_days'],
                  'CATALOGUE_STATIONS':selection['universe']['eligible_stations'],
                  'CATALOGUE_CITIES':selection['universe']['eligible_cities'],
                  'SELECTED_STATIONS':selection['selected']['stations'],'SELECTED_CITIES':selection['selected']['cities'],
                  'STUDY_START':protocol['study_window']['first_date'],'STUDY_END':protocol['study_window']['last_date'],
                  'LOCKED_AT':tex_escape(protocol['_locked_at']),
                  'FINAL_DAYS':protocol['splits']['final_test_days'],
                  'FINAL_START':result['final_test_range'][0],'FINAL_END':result['final_test_range'][1],
                  'FINAL_STATUS':final_status,'DATASET_IDENTITIES':identities,
                  'PREVIOUS_RUNS_URL':PREVIOUS_RUNS_URL,
                  'FOLDS':len(complete_folds),'FOLDS_SKIPPED':len(result['folds'])-len(complete_folds),
                  'SPATIAL':len(complete_spatial),'SPATIAL_SKIPPED':len(result['spatial'])-len(complete_spatial),
                  'CALIBRATIONS':len(result['uncertainty']),'COMPARISON_FINDINGS':comparison_findings(result),
                  'FORECASTS':prospect['forecasts'],'ISSUED_DAYS':prospect['issued_target_days'],'VERIFIED_DAYS':prospect['verified_days'],
                  'PROSPECTIVE_FINDINGS':prospective_findings(prospect),'REFERENCES':references}
    for name,value in replacements.items():
        source=source.replace('@'+name+'@',str(value))
    return source


def generate():
    quality=json.loads((OUT/'measured_dataset.json').read_text())
    latest=json.loads((OUT/'preliminary_latest.json').read_text())
    result_path=config.PROJECT_ROOT/latest['artifact']
    result=json.loads(result_path.read_text())
    if latest != result:
        raise ValueError('Latest preliminary pointer disagrees with the immutable result artifact')
    experiment_quality=find_experiment_quality(result,quality)
    prospect_path=OUT/'prospective_audit.json'
    prospect=json.loads(prospect_path.read_text())
    protocol=load()
    if any(protocol['_sha256'] != artifact['protocol_sha256'] for artifact in (result,quality,experiment_quality)):
        raise ValueError('Paper artifacts do not share the locked protocol identity')
    snapshot_path=(config.PROJECT_ROOT/quality['table']).parent.parent/'inputs.json'
    snapshot=json.loads(snapshot_path.read_text())
    if snapshot['data_version'] != quality['data_version']:
        raise ValueError('Acquisition catalogue snapshot has the wrong data version')
    source=render_source(quality,result,prospect,experiment_quality,protocol,snapshot['selection'],bib_entries())
    path=config.PROJECT_ROOT/'paper/station_calibration_skeleton.tex'
    path.write_text(source,encoding='utf-8')
    write_json(OUT/'paper_skeleton.json',{'source':config.portable(path),
        **dataset_evidence(quality,experiment_quality,result),
        'dataset_hash':result['dataset_hash'],
        'preliminary_result_artifact':config.portable(result_path),
        'preliminary_result_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest(),
        'protocol_sha256':protocol['_sha256'],'protocol_locked_at':protocol['_locked_at'],
        'previous_runs_source':PREVIOUS_RUNS_URL,
        'primary_support_policy':'PENDING_OPERATIONAL_SUPPORT_VERIFICATION',
        'preliminary_run_id':result['run_id'],'author_details':'PENDING','primary_results':'PENDING_CAMS_ARCHIVE',
        'intended_pages':6,'page_count_verified':False,'submission_ready':False,
        'bibliography_source':'inherited generated paper/refs.bib; no new manually authored entries'})
    return path


if __name__=='__main__':
    print(config.portable(generate()))
