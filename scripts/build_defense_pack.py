"""Author a Markdown defense pack from checked artifacts; never fit or score.

This script does not generate a paper, PPT, target dataset or forecast. Numerical
research statements are read from existing immutable preliminary artifacts.
Qualitative risks are explicitly judgments, not measured event probabilities.
"""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/defense'
def artifact(name):
    p=ROOT/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}

def table(headers, rows):
    clean=lambda x:str(x).replace('|','/').replace('\n',' ')
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(map(clean,row))+' |\n' for row in rows)

def main():
    measured=artifact('results/research/measured_dataset.json')
    preliminary=artifact('results/research/preliminary_latest.json')
    immutable=artifact(preliminary.get('artifact','results/research/preliminary_latest.json'))
    if preliminary!=immutable or preliminary.get('final_test_scored') is not False:
        raise ValueError('Only the verified immutable preliminary result with sealed final test is allowed')
    probe=artifact('results/research/cams_ads_probe.json')
    archive=artifact('results/research/cams_development_acquisition.json')
    prospective=artifact('results/research/prospective_audit.json')
    tests=artifact('results/project_hardening/verification.json')
    OUT.mkdir(parents=True,exist_ok=True)
    documents={}
    anchor=(f"\n\nEvidence checkpoint: measured dataset `{measured['dataset_hash']}`; "
            f"preliminary run `{preliminary['run_id']}`; protocol `{measured['protocol_sha256']}`. "
            "Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. "
            "See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).\n")
    def write(name,title,body,evidence=True):
        documents[name]='# '+title+'\n\n'+body.strip()+'\n'+(anchor if evidence else '')
    metrics=preliminary['paired_comparisons']
    strict=metrics['ridge_strict_vs_climatology']; persistence=metrics['ridge_history_vs_persistence']
    summary=(f"The retained measured table contains {measured['station_days']:,} station-days: "
        f"{measured['valid_targets']:,} valid and {measured['rejected_targets']:,} rejected targets, "
        f"{measured['usable_stations']} usable stations in {measured['usable_cities']} parsed cities. "
        "Its dates are 2025-02-19 through 2026-10-07; rejection records are retained. "
        "The final 90 days, 2026-07-10 through 2026-10-07, remain sealed at this checkpoint. "
        f"In the NON_CAMS_PRELIMINARY development comparison, strict Ridge minus climatology MAE is "
        f"{strict['mae_difference']:.2f} AQI (95% date-block interval [{strict['ci95'][0]:.2f}, {strict['ci95'][1]:.2f}]). "
        f"Conditional history Ridge minus persistence is {persistence['mae_difference']:+.2f} "
        f"([{persistence['ci95'][0]:.2f}, {persistence['ci95'][1]:.2f}]); an improvement is not established. "
        "Every strict baseline forecast on 363 evaluated censored Severe validation days fell below 401. "
        "This serious failure is disclosed prominently. These are not CAMS-comparison or final-test results.")
    write('ONE_PAGE_RESULTS.md','Results to say accurately',summary+"\n\n"
        +table(['Result','Scope','Can claim'],[
            ['24 temporal evaluations; 36 spatial holdouts','Non-CAMS preliminary only','Development experiments completed'],
            ['12 uncertainty/advisory calibration windows','Same preliminary study','Methods assessed; subgroup reliability not assured'],
            [probe.get('status','PENDING'),'One PM2.5 GRIB smoke file','Archive access works if VERIFIED; not a complete baseline'],
            [str(archive.get('counts',{})),'Development archive acquisition','Collection status only'],
            [f"{prospective.get('verified_days',0)} verified days",'Last prospective audit','Not 30 verified days'],
            ['Primary CAMS results pending','Genuine archived comparison','No improvement claim or selected production correction'],
        ]))
    interval_rows=[]
    for method in ('split_0.8','split_0.9','cqr_0.9','mondrian_0.9'):
        items=[fold[method] for fold in preliminary['uncertainty'].values() if method in fold]
        n=sum(i['n_exact'] for i in items)
        coverage=sum(i['coverage_exact']*i['n_exact'] for i in items if i['coverage_exact'] is not None)/n if n else None
        total=sum(i['n_exact']+i['n_censored'] for i in items)
        width=sum(i['mean_width']*(i['n_exact']+i['n_censored']) for i in items)/total if total else None
        interval_rows.append([method,n,f'{coverage:.3f}' if coverage is not None else 'undefined',
                              f'{width:.1f}' if width is not None else 'undefined',
                              sum(i.get('abstained_rows',0) for i in items)])
    policy_rows=[]
    for policy in ('P0','P1','P2'):
        items=[fold[policy] for fold in preliminary['advisory'].values() if policy in fold]
        n=sum(i['n'] for i in items)
        policy_rows.append([policy,n,
            f"{sum(i['under_warning']*i['n'] for i in items)/n:.3f}" if n else 'undefined',
            f"{sum(i['over_warning']*i['n'] for i in items)/n:.3f}" if n else 'undefined'])
    write('UNCERTAINTY_ADVISORY_DEFENSE.md','Uncertainty and advisory trade-offs: verified preliminary only',
        "These aggregates are station-day weighted from the existing twelve chronological non-CAMS validation "
        "artifacts. They are not CAMS correction, final-test or clinical results. Width uses all rows returned "
        "by each method; exact coverage excludes censored labels. Mondrian unsupported rows are listed separately.\n\n"
        +table(['Method','Exact validation pairs','Weighted exact coverage','Weighted mean width (AQI)','Unsupported rows'],interval_rows)
        +"\nNominal coverage does not establish conditional reliability. In fold_01 the split-80 interval "
        "covered zero of 35 exact Very Poor targets; its Poor-or-worse coverage was also zero among 48 pairs. "
        "Inspect every severity/season/region artifact rather than quoting a pooled average alone. Severe upper "
        "endpoint >=401 is lower-bound compatibility, not identified coverage of the unknown true index.\n\n"
        +table(['Policy','Validation pairs','Weighted under-warning','Weighted over-warning'],policy_rows)
        +"\nP0 uses the point category; P1 the calibrated median; P2 the fixed calibrated 0.75 quantile. "
        "P3 selects the smallest candidate satisfying the declared calibration-window empirical target; inspect "
        "each fold’s target-specific feasibility and held-out errors in preliminary_latest.json. Dependent days "
        "prevent a general finite-sample health-risk guarantee. Lower under-warning can cost more over-warning, "
        "and no cohort-specific clinical outcomes were collected.\n\n"
        "The moving seven-day date-block intervals and Holm-adjusted paired comparisons remain in the immutable "
        "result artifact; this file does not invent a new significance test or recalibrate any policy.")
    write('ONE_PAGE_PROJECT.md','AirGuard in one page',
        "AirGuard India combines source-labelled air-quality information, a CPCB-style index engine, "
        "next-day modelled forecasts and environmental exposure guidance. Select an Indian place or coordinates; "
        "inspect measured versus modelled current data, tomorrow’s forecast, missing data and provenance. "
        "Nationwide fallback uses the CAMS global grid and does not establish street-level precision.\n\n"
        "Built: bounded ingestion, caching, station selection, mass-unit checks, AQI aggregation, source labels, "
        "APIs, frontend, immutable prospective records and research/QC/split/reproduction infrastructure. "
        "Still being established: a validated CAMS station correction, operational intervals and a 30-day verified record.\n\n"+summary)
    write('ONE_PAGE_NOVELTY.md','Novelty in one page',
        "Defensible addition: an auditable integration of Indian station targets, a shared CPCB-style engine, "
        "explicit issue-time rules, temporal/spatial/severity evaluation and exposure-advisory trade-offs. "
        "This is an engineering and validation contribution under investigation, not a proven new atmospheric model. "
        "Bias correction, conformal prediction and pollution advisories already exist in research.\n\n"
        "CAMS supplies the atmospheric forecast. OpenAQ distributes upstream measurements. AirGuard owns the "
        "integration, QC, provenance, index transformation and evaluation code. Correction superiority and "
        "vulnerable-cohort benefit remain unproved. Never say ‘world first’ or ‘more accurate than CAMS’ yet.")
    write('ONE_PAGE_ML.md','ML in one page',
        "Primary ladder: raw CAMS, climatology, persistence, direct Ridge/LightGBM/XGBoost and their residual variants. "
        "Residual = exact measured AQI minus the frozen issue-time CAMS index; add the same baseline back at inference. "
        "Standardise Ridge inputs and fit imputation/scaling on training rows only. Tune inside each fold’s training dates. "
        "Carry forward the lowest mean rolling-fold MAE, preferring simpler learners on ties, or raw CAMS if no learner wins.\n\n"
        "Severe targets are >=401 lower bounds: exclude exact regression fitting/error, retain warning/exceedance/shortfall checks. "
        "Conformal intervals use separate chronological calibration days and cannot guarantee subgroup or time-dependent coverage. "
        "No primary model has been selected while the complete CAMS archive is pending.")
    write('ONE_PAGE_DATASETS.md','Datasets in one page',
        "Measured: OpenAQ-hosted CPCB-provider station readings, with original upstream identity, times, units and quality flags. "
        "Modelled: genuine operational CAMS forecasts from ADS; GFS weather forecasts via Open-Meteo previous runs. "
        "Satellite context: NASA FIRMS fire detections, not measured breathing-zone pollutant concentrations. "
        "Derived: CPCB-style station AQI, feature summaries, categories and QC decisions.\n\n"
        "QC v3.1 rejects exact zeros, flagged/under-covered bins, unsupported units and six-hour stuck sequences. "
        "Spikes and PM2.5>PM10 are flagged and kept. Daily targets require >=16 hourly bins per pollutant, >=3 pollutants "
        "including particulate, complete CO/O3 eight-hour windows. Current-catalogue survivorship and unknown OpenAQ ingestion "
        "times are limitations. Research data are not synthetic; offline fault fixtures are synthetic and labelled tests.")
    write('ONE_PAGE_ARCHITECTURE.md','Architecture in one page',
        "Location → validated service-region coordinates → cache/lease/budget → bounded provider adapters → "
        "unit/provenance checks → shared index engine → source-labelled current/tomorrow payload → browser response "
        "validation → environmental advisory. Optional weather/fire failures are disclosed. No validated experimental "
        "correction is deployed. Research archive/model selection is a separate process.\n\n"
        "Python supplies provider orchestration and APIs; Next.js supplies UI; Postgres/Supabase supplies cache, "
        "quotas, snapshots and immutable prospective ledgers. Native forecast cells are around 40 km. "
        "The API can return 202 for queued work, 429 for budgets, 400 for invalid input or 503 for unavailable data.")
    write('ONE_PAGE_IMPACT.md','People impact in one page',
        "Use forecasts to discuss shifting outdoor activity, preparing for high-pollution periods and checking data freshness. "
        "Useful audiences include families, schools, commuters and outdoor workers. Benefit is plausible information support; "
        "no exposure reduction, hospitalisation reduction or clinical outcome has been measured. "
        "Many people cannot change work hours or commute routes. Relatively lower exposure is not safety. "
        "Display absent measurements and uncertainty rather than false precision.")
    write('ONE_PAGE_LIMITATIONS.md','Limitations to disclose first',
        "1. CAMS correction/final-test results are pending.\n2. All strict preliminary Severe forecasts under-warned.\n"
        "3. Coarse global cells cannot establish street-level variation.\n4. Historical station ingestion timestamps are missing.\n"
        "5. Current active-station selection introduces survivorship.\n6. Rejected station-days and missing gases reduce coverage.\n"
        "7. Conformal calibration is conditional on data regime and dependent days weaken guarantees.\n"
        "8. Advisory strata have no clinical calibration.\n9. Third-party APIs and network availability remain dependencies.\n"
        "10. The 30-day verified prospective requirement is not met. Source fixes have not been released to production.")
    write('OWNED_CONTRIBUTIONS.md','What did you actually build?',
        table(['External resource','What it supplies','AirGuard-owned work','Evidence'],[
            ['OpenAQ / CPCB upstream','Station measurements and metadata','Resumable acquisition, QC ledger, station selection and daily targets','src/research/calibration/measured.py'],
            ['CAMS / Copernicus','Physics-based atmospheric composition forecast','Archived-run checks, grid matching and CPCB-style transformation; correction is pending','src/research/calibration/cams_acquisition.py'],
            ['Open-Meteo / GFS','Air-quality access and weather forecasts','Provider validation, time cutoffs, cache/budget/orchestration','src/nationwide/providers.py'],
            ['NASA FIRMS','Satellite active-fire detections','Optional proximity context; withheld as strict historical predictor','src/nationwide/optional_ingestion.py'],
            ['Supabase/Postgres','Database service','Application schema, request leases/budgets, snapshots and immutable forecast pairing','src/nationwide/store.py; src/research/storage.py'],
            ['Next.js / sklearn / boosting libraries','Frameworks and learners','Frontend/API integration, tests and research evaluation protocol','webapp/app; src/research/calibration'],
        ])+"\nThese resources are dependencies and must be credited. We did not build CAMS, operate CPCB monitors, "
        "invent Ridge/conformal prediction, establish causal source attribution or validate a clinical decision system.")
    write('ARCHITECTURE_DEFENSE.md','Architecture defense',
        "The live and research paths have distinct evidence requirements. The live UI currently issues a modelled "
        "CAMS-based nationwide estimate; the station correction remains experimental.\n\n"
        "```mermaid\nflowchart TD\n U[User selects location] --> V[Validate region and labels]\n"
        " V --> C[Shared cache, lease and quota]\n C --> O[OpenAQ: MEASURED]\n C --> M[CAMS: MODELLED]\n"
        " C --> W[Weather: MODELLED]\n C --> F[FIRMS: satellite detection context]\n"
        " O --> Q[QC and provenance]\n M --> Q\n W --> Q\n F --> Q\n Q --> A[CPCB-style AQI: DERIVED]\n"
        " A --> P[Next-day forecast: PREDICTED]\n P --> E[Exposure guidance: ADVISORY]\n"
        " E --> API[Validated API payload]\n API --> UI[Frontend with explicit missing/stale states]\n"
        " P -. separate research, pending archive .-> R[Residual model and calibrated uncertainty]\n```\n\n"
        +table(['Value','Classification','Meaning'],[
            ['Station pollutant concentration','MEASURED','Instrument/provider observation, subject to QC'],
            ['CAMS pollutant field','MODELLED','Atmospheric forecast at grid scale'],
            ['Weather forecast','MODELLED','Future weather estimate, not observed outcome'],
            ['AQI/sub-index/category','DERIVED','Index arithmetic under AirGuard’s convention'],
            ['Tomorrow’s index','PREDICTED','Forecast transformation or a future validated correction'],
            ['Activity guidance','ADVISORY','Exposure guidance, not diagnosis or individual disease risk'],
        ])+"\nCache values expire against source-age and IST boundaries. Missing measured support permits labelled modelled "
        "fallback, not a synthetic station observation. If all forecast data fail, prediction is withheld. "
        "Experimental model artifacts never automatically replace the production forecast.")
    write('DATASET_DEFENSE.md','Dataset and issue-time defense',
        summary+"\n\n"
        "**Is this synthetic?** Research targets are acquired station measurements. CAMS/weather are real model output, "
        "not measured targets. Synthetic fixtures exercise failures in tests and must never become evidence of forecast skill.\n\n"
        "**Why trust it?** Preserve original files and hashes, source/sensor identity, units, time windows, rejection reasons "
        "and deterministic reconstruction. Trust is bounded: QC cannot establish instrument truth, OpenAQ publication "
        "latency is unknown, and station coverage is uneven.\n\n"
        "**Why three pollutants?** The engine enforces the declared minimum including PM2.5 or PM10. Unsupported ppb "
        "station gases are excluded without invented temperature/pressure. This measured cohort’s valid targets use "
        "PM2.5, PM10 and O3. NO2/SO2/CO target support is zero here.\n\n"
        "**Issue-time rules:** target D issued D-1 20:00 IST; measurements must end by 17:00 IST on D-1. "
        "Weather uses archived forecast provenance. ADS init + lead must equal valid time. Detection acquisition time "
        "alone does not prove FIRMS publication time, so strict historical fire features remain withheld. "
        "The documented CAMS 00 UTC dissemination bound is distinct from ADS retrieval latency; per-run historical "
        "release logs remain a limitation.\n\n"
        "The original protocol’s target-matched pollutant support is an evaluation annotation. A forecast feature "
        "cannot use tomorrow’s missingness or QC. Freeze operational support before issue time; disclose this correction "
        "to the implementation without rewriting the locked protocol or previous hashes.\n\n"
        "Final targets must not enter selection. The new archive plan covers development only; acquiring held-out "
        "forecasts and reading final labels require the separately committed selection lock and one-shot evaluation gate.")
    write('ML_DEFENSE.md','Model and validation defense',
        table(['Question','Viva answer'],[
            ['Why Ridge?','Stable, interpretable regularised linear baseline; scale on training only and tune alpha inside training dates.'],
            ['Why LightGBM?','Tabular nonlinearities and interactions with controlled complexity; it must beat simpler baselines on identical development rows.'],
            ['Why XGBoost?','Independent boosted-tree implementation for a preregistered learner comparison; similarity to LightGBM does not guarantee gain.'],
            ['Why not Random Forest?','It is a reasonable future comparator, but adding learners after observing final outcomes would break selection discipline.'],
            ['Why not LSTM?','Incomplete station sequences require explicit masks and careful state/time boundaries. We have not demonstrated that recurrent complexity improves the declared tabular baselines.'],
            ['Why not GRU?','Fewer recurrent parameters do not establish spatial transfer or extreme-event skill. A future declared comparison should test it on identical data/windows.'],
            ['Why not Transformer?','Attention can model dependencies but needs suitable data, time masks and capacity. It has not been tested here; complexity is not evidence of better forecasting.'],
            ['Why not an LLM?','It is not a substitute for numerical pollutant forecasts and verified time-series evaluation. No LLM generates the AQI value.'],
            ['Why not use CAMS directly?','The current nationwide product already uses it. Correction is a hypothesis, and raw CAMS must be carried forward if learned models fail to improve the locked development criterion.'],
            ['Why residual correction?','It starts from physics forecast structure and learns measured-minus-CAMS differences; it can fail and must compete with raw CAMS and direct prediction.'],
            ['Why persistence/climatology?','They expose whether complex forecasting beats current conditions or seasonal station averages.'],
            ['Why rolling origin?','Training precedes calibration and testing across global dates; random date splits can leak regime and lag information.'],
            ['Why spatial holdout?','It measures transfer to unseen monitors or clusters rather than memorisation at familiar coordinates.'],
            ['Why ablation?','Test which feature families contribute on identical rows; absence of gain is a valid result.'],
            ['Why conformal?','Separate residual/quantile calibration is auditable; exchangeability and subgroup limitations must still be disclosed.'],
            ['Why not maximise R²?','MAE and severe under-warning affect the use case; R² is variance-relative fit and can be negative.'],
            ['Why Severe is hard?','Sparse extremes, distribution shift and an open-ended label prevent exact upper-range regression scoring.'],
        ])+"\nPrimary development and model selection remain pending archive completeness. Preliminary Ridge findings "
        "do not justify deploying a residual correction. Model-selection lock must bind features, preprocessing, "
        "parameters, data/archive/protocol/source hashes, calibration rules and software versions before final access.")
    write('SECURITY_DEFENSE.md','Security and privacy defense',
        "Credentials live in server/private runtime configuration, not the browser. ADS acquisition suppresses "
        "client output, exception bodies and download URLs; its audit stores allowlisted request/status/checksum "
        "metadata. The private ADS credential file is never displayed or read by the audit script.\n\n"
        "Browser persistence: selected location and advisory cohort are stored locally. Location is also included "
        "in shareable URLs and sent to the service/providers. This is not anonymous from infrastructure operators. "
        "Cohort is evaluated browser-side and not included in the current summary request; do not claim no data is stored.\n\n"
        "Server database stores environmental observations, source snapshots, cache keys/location requests, "
        "provider events, budgets, forecasts and verification pairs. No diagnosis is required by this flow. "
        "Raw location-linked cache records could still reveal a place of interest. Retention and institutional "
        "privacy policy require product review before large-scale use.\n\n"
        "Controls: fixed outbound provider URLs; allowlisted API operations; coordinate and label validation; "
        "bounded requests/body sizes; parameterised SQL; RLS; authenticated internal refresh; safe generic HTTP "
        "errors; immutable issuance; client response validation; security headers. Service-role privileges stay "
        "server-side. RLS is not a substitute for server authorisation when privileged credentials are used.\n\n"
        "Evidence: `results/release/secret_audit.json`, `database_audit.json`, `src/qa/security.py`, security "
        "and request-scope tests. These are scoped audits, not penetration certification. No credential values "
        "or database connection strings belong in viva screenshots, logs or demo slides.")
    write('COST_AND_SCALABILITY.md','Cost and scalability defense',
        "No commercial price or measured million-user capacity is asserted. Separate prototype, research and "
        "production budgets.\n\n"+table(['Stage','Main resource','Cost/limit issue','Control'],[
            ['Prototype','Hosting/database + provider free tiers','Free does not mean unlimited, guaranteed or commercially licensed','Cache, quotas, scoped demo and clear attribution'],
            ['Research','Archive downloads, local CPU/RAM/disk','Large dated forecasts and repeated fitting; ADS latency is a time cost','Minimum subset, immutable files, incremental jobs and train-only tuning'],
            ['Production','Paid hosting/database/provider licences','Traffic, cold starts, DB contention, retention, support and egress','Batch by forecast grid, bounded storage, shared cache and monitored SLA'],
        ])+"\n[Open-Meteo](https://open-meteo.com/en/pricing) states that its free API is non-commercial, "
        "has limits and no uptime guarantee; commercial use needs a suitable licence. "
        "[OpenAQ](https://docs.openaq.org/using-the-api/rate-limits) currently lists general limits of "
        "60 requests/minute and 2,000/hour per API key; read headers and terms rather than multiplying keys. "
        "AirGuard’s runtime budgets are intentionally smaller and shared across requests.\n\n"
        "Ten users: shared cache and grid reuse reduce provider calls, subject to actual warm-state tests. "
        "Ten thousand users: precompute popular grid/time summaries, isolate provider queues, measure DB contention "
        "and use licensed capacities. One million users: no claim that the prototype supports this; require "
        "load tests, CDN strategy, partitioned storage, durable queues, capacity budgets and paid service planning.\n\n"
        "Station calibration scales with station-day training rows, not individual users. CAMS acquisition scales "
        "with date × parameter × lead × grid cells. Per-user provider calls are the wrong national architecture. "
        "Outstanding cost risk: monitoring/support and mandatory commercial terms, not just model inference CPU.")
    write('ETHICS_AND_LIMITATIONS.md','Ethics and limitations',
        "Environmental guidance must not imply diagnosis, medical treatment, zero exposure risk or an official "
        "CPCB forecast. Advisory cohorts represent exposure sensitivity contexts; they are not validated disease "
        "probabilities. Users with limited control over work or transport need options, not blame.\n\n"
        "Under-warning risks false reassurance; excessive alerts cause fatigue and unequal opportunity costs. "
        "Report both and disclose severe misses. Uneven monitoring can favour well-observed cities; a modelled "
        "fallback improves availability but does not establish equal accuracy.\n\n"
        "Intervals must show absence of validation and conditional failures. Explanations of feature importance "
        "describe model behaviour, not causal pollution sources. A counterfactual slider recalculates assumed "
        "concentrations; it cannot estimate the effect of a real policy intervention.\n\n"
        "Publish provenance, QC exclusions, failed comparisons and remaining blockers. Preserve prior artifacts "
        "when correcting metadata. Product responsibility includes accessible error states, responsible location "
        "retention, commercial licensing and user testing before relying on the system at scale.")
    write('WHY_AIRGUARD_MATTERS.md','Why use AirGuard when AQI apps exist?',
        "AirGuard’s defensible purpose is to connect tomorrow’s source-labelled forecast with Indian index "
        "conventions and practical exposure planning, while making missing measurements and validation limits "
        "visible. Existing portals, APIs and apps remain useful and may already provide forecasts or advice.\n\n"
        "Scientifically, the project supplies an auditable station/day-ahead evaluation rather than assuming a "
        "physics forecast needs correction. For users, it combines provenance, temporal variation and advisory "
        "context in one flow. Engineering work makes provider failure and fallback explicit. Public benefit "
        "would depend on accurate warnings, usability and feasible action; none is established by a demo alone.\n\n"
        "The case is strongest as a transparent research/prototype integration. It weakens if correction fails "
        "to beat raw CAMS, extreme events are missed, or users misunderstand the grid’s precision. Those are "
        "testable questions, not reasons to hide negative results.")
    comparisons=[
        ['CPCB portal','Official monitoring/index reporting','Yes','Do not assume all portal products','Yes','Not audited here','Not audited here','Public guidance exists','Not evaluated here','Not evaluated here','AirGuard adds an explicitly non-official next-day integration'],
        ['OpenAQ','Measurement access/aggregation','Upstream','API is principally observations','Raw concentrations, not AirGuard index','No AirGuard calibration','Not this project’s intervals','Not a clinical advisory service','Not a forecasting comparison','Not a forecasting comparison','AirGuard adds QC/index/forecast evaluation'],
        ['CAMS','Atmospheric composition forecasts','Assimilation sources; output modelled','Yes','Pollutant output; AirGuard transforms index','Independent CAMS evaluation exists','Product dependent; not audited','Not AirGuard cohort policy','Independent operational verification','Independent operational verification','AirGuard tests India station post-processing'],
        ['Common AQI/weather apps','Consumer information','Provider dependent','Some do','Product dependent','Unknown without specific audit','Product dependent','Some do','Usually not disclosed publicly','Usually not disclosed publicly','No blanket superiority claim'],
        ['Conventional ML research','Forecasting experiments','Study dependent','Yes','Some Indian studies','Often','Some studies','Some studies','Study dependent','Study dependent','AirGuard binds split/QC/artifacts to its deployed prototype'],
    ]
    write('COMPETITOR_MATRIX.md','Fair competitor comparison',
        "Unknown means not audited, not absent. No commercial competitor ranking is claimed. "
        "Sources: [CPCB](https://airquality.cpcb.gov.in/AQI_India/), [OpenAQ](https://docs.openaq.org/), "
        "[CAMS](https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts), "
        "and the project’s primary-source literature matrix.\n\n"
        +table(['System','Primary function','Measured data?','Forecast?','Indian AQI?','Station calibration?','Uncertainty?','Vulnerability advisory?','Temporal validation?','Spatial validation?','AirGuard difference'],comparisons))
    novelty=[
        ['CPCB/current portals','Measured current conditions','Not this prototype’s day-ahead experiment','Explicit forecast/provenance flow','src/nationwide/service.py','Non-official, incomplete monitor coverage'],
        ['OpenAQ','Open station data access','Does not constitute this AQI forecast system','QC/rejection ledger and target reconstruction','measured_dataset.json','Upstream faults and missing ingestion time'],
        ['CAMS','Physics forecast','Coarse grid bias may exist','Test station correction versus raw CAMS','CAMS archive plan; primary factories','Superiority pending'],
        ['Weather apps','Weather and sometimes AQI','Capabilities vary by product','Audit issue-time and Indian AQI conventions','availability.py; aqi.py','No universal app superiority'],
        ['AQI dashboards','Situation display','Presentation alone cannot validate forecasting','Rolling/spatial/severity protocol','locked v3.1; preliminary results','CAMS primary pending'],
        ['Generic ML AQI projects','Learned predictions','Random splits may overstate transfer; not all do','Chronology, final seal and matched rows','splits.py; tests','Does not invent a learner'],
        ['Station-only models','Local measured history','No-monitor transfer can weaken','Nationwide modelled fallback','service.py','Fallback accuracy differs'],
        ['Weather-only models','Meteorological relationship','May lack atmospheric transport/composition baseline','CAMS/direct/residual comparison','primary.py','Comparison unfinished'],
        ['Spatiotemporal systems','Transfer across time/space','Existing sophisticated methods','India-specific reproducible deployment/evaluation','preliminary spatial artifacts','No claim of new spatial theory'],
        ['Uncertainty-aware systems','Intervals/probabilities','Average coverage may hide failures','Severity/region/season interval diagnostics','preliminary uncertainty','No dependent-day guarantee'],
        ['Advisory systems','Exposure communication','Risk thresholds and costs differ','Measured under-/over-warning trade-offs','preliminary advisory','No clinical outcomes'],
    ]
    write('NOVELTY_MATRIX.md','Novelty and remaining limits',
        "The contribution is a reproducible combination to evaluate, not proof of a world first.\n\n"
        +table(['Comparator','Capability','Limitation relevant here','AirGuard addition','Evidence','Remaining limitation'],novelty)
        +"\nLiterature review access and acceptance remain incomplete: see `docs/research/LITERATURE_FULLTEXT_REVIEW.md`. "
        "Do not interpret this feature comparison as a systematic novelty proof.")

    failures=[
        ('Geolocation denied','Possible','Moderate','permission callback','manual place/coordinate search','Permission unavailable; search still works','No, after valid manual selection','No inferred user location','Retry only on user click'),
        ('Geolocation inaccurate','Possible','High','user compares selected place/coordinate','manual correction','Show selected coordinates and coarse grid','No, if valid region','Wrong place invalidates local relevance','Choose correct place'),
        ('Station unavailable','Likely','High','no supported nearby station','labelled CAMS grid forecast','No measured station; modelled estimate','Station correction yes; raw model no','No measured truth at this place','Use another supported monitor; disclose distance'),
        ('Station offline','Likely','High','old last observation / incomplete coverage','same modelled fallback','Station stale/unavailable','Measured current value yes','Missingness may be informative','Await actual new readings'),
        ('Station stale','Likely','High','age of every contributing pollutant','fresh source or labelled fallback','Stale label with timestamp','Fresh measured claim yes','History-latency assumptions fail','Refresh feed; do not backdate'),
        ('Missing station pollutants','Very Likely','High','distinct valid pollutant count','modelled forecast; pollutant context only','Insufficient measured AQI','Measured AQI below minimum yes','Target rejection reduces coverage','Await >=3 supported pollutants incl PM'),
        ('Exact-zero readings','Possible','High','v3.1 QC ledger','reject affected research bins','Research exclusion reason','Target if support fails','Cannot distinguish outage from exact zero','Keep raw; apply locked rule'),
        ('Stuck sensor','Possible','High','six identical consecutive hourly values','reject full run under v3.1','Research stuck-sequence flag','Target if support fails','Fault detection can remove stable real readings','Investigate upstream; preserve rule'),
        ('Extreme spike','Possible','High','potential-spike flag','keep flagged data','Potential spike; not silently erased','Not automatically','Could be genuine extreme pollution','Inspect provenance; no outcome-driven QC'),
        ('PM2.5 > PM10','Possible','Moderate','paired mass comparison','keep with flag','Inconsistency disclosed','Not automatically','Which instrument is wrong is unidentified','Review upstream sensor metadata'),
        ('OpenAQ outage','Likely','High','HTTP/schema/budget failure','fresh model or bounded stale fallback','Measured source unavailable','Measured prediction yes if absent','Cannot verify target until measurements return','Bounded retry; honour rate headers'),
        ('CAMS outage','Possible','Critical','forecast missing/invalid/expired','bounded labelled stale result if allowed','Forecast unavailable or stale','Yes if no valid forecast','Correction cannot invent atmospheric baseline','Retry existing archive job / refresh live source'),
        ('Weather outage','Possible','Moderate','provider status / missing context','AQ forecast may remain available','Weather unavailable','Weather-dependent validated correction yes if required','Optional-context loss differs from model feature missingness','Retry weather separately'),
        ('FIRMS outage','Possible','Moderate','optional source status','omit satellite context','FIRMS context unavailable','No for core AQ forecast','No fire attribution or predictor proof','Retry optional acquisition'),
        ('Supabase outage','Possible','Critical','connection timeout / API 503','fail closed; browser search state retained','Live data temporarily unavailable','Yes when backend cannot serve validated cache','Ledger may have gaps; no fake verification','Restore service and audit missing issuance'),
        ('Frontend timeout','Possible','High','abort timeout / queued polling bound','retry/manual navigation','Retry shortly; no substitute values','Yes absent valid response','No stale data silently labelled fresh','Retry after network recovery'),
        ('Backend timeout','Possible','High','bounded transport/SQL timeout','cache only within age limits','503 or explicit stale label','Yes without acceptable cache','Missingness and operational reliability need reporting','Inspect bounded provider event classes'),
        ('API rate limit','Likely','High','HTTP 429 / shared quota','existing cache; delay new request','Budget reached; retry later','New result yes if unavailable','Request capacity is not forecast skill','Back off; never rotate keys to evade limits'),
        ('Malformed JSON','Possible','High','transport parser / browser contract','fail closed','Incomplete data; retry','Yes for invalid payload','Cannot infer absent fields','Repair adapter against actual schema'),
        ('Null output','Likely','High','nullable AQI / insufficient status','display missing state','Dash/insufficient data','Yes for missing AQI','No imputed truth','Await enough valid data'),
        ('Duplicate data','Possible','High','unique keys/time checks','reject duplicate hours; idempotent record keys','Unavailable if invalid series','Yes for invalid series','Duplicate samples must not inflate coverage','Audit unique keys and repeat-safe manifests'),
        ('Delayed data','Likely','High','receipt versus valid/last-observed time','freshness-qualified fallback','Age and delay visible','Fresh measurement claim yes','Healthy-feed latency is conditional','Acquire late data without rewriting issue record'),
        ('Unsupported location','Possible','Moderate','region/coordinate validation','search supported India place','Outside service region','Yes','Bounding box is not a political boundary','Correct coordinates'),
        ('Unseen station','Likely','High','station absent from training/coverage support','raw grid forecast','No validated station correction','Unsupported correction yes','Station-transfer evidence required','Use frozen spatial-support policy'),
        ('Unseen city','Likely','High','city/cluster spatial holdout identity','raw grid forecast','Modelled regional estimate','Unsupported correction yes','No learned local accuracy claim','Evaluate transfer without outcome-based selection'),
        ('Very high AQI','Possible','Critical','Severe category/lower-bound qualifier','high-pollution advisory; disclose limitations','Severe >=401, no fake upper value','Exact upper numerical claim yes','Censoring and strict-model under-warning matter','Preserve extreme diagnostics; no relabelled success'),
        ('Wide interval','Possible','High','validated interval width/coverage','communicate uncertainty, cautious guidance','Large uncertainty; no safety guarantee','Not solely due to width','Width is not confidence in subgroup coverage','Check calibration and source support'),
        ('Model disagreement','Possible','High','development comparison / predictions differ','carry frozen selected rule or raw baseline','Do not cherry-pick attractive output','Unsupported combination yes','No post-final model switching','Investigate in future version'),
        ('Forecast unavailable','Possible','Critical','null tomorrow / unavailable status','no predicted AQI','Tomorrow forecast unavailable','Yes','Absence must not become false low-risk estimate','Restore source; record outage'),
        ('Database corruption','Rare','Critical','constraints/checksums/immutable-ledger mismatch','fail closed; incident response','Service unavailable','Yes if provenance cannot be trusted','Verification/reproducibility invalid','Restore verified backup; independently audit'),
        ('Timezone mismatch','Possible','High','aware UTC plus IST boundaries','reject inconsistent provenance','Unavailable if period invalid','Yes for invalid period','Wrong target day can leak or mispair','Correct parser and replay under locked rules'),
        ('Invalid lat/lon','Possible','High','numeric finite region checks','no outbound call','Invalid input; correct coordinates','Yes','No forced nearest supported city','Enter valid finite numbers'),
        ('Network disconnect','Possible','High','fetch failure/abort','bounded cached data labelled; retry','Connection unavailable','Yes absent acceptable result','Operational availability is distinct from model error','Reconnect and refresh'),
        ('Provider schema change','Possible','High','adapter and frontend contract','fail closed','Provider data incomplete','Yes for invalid core response','New semantics require a versioned adapter audit','Inspect official docs and actual payload'),
        ('Partial coverage','Very Likely','High','hour-count/pollutant support ledger','show available pollutant context, not complete AQI','Insufficient support','AQI yes below declared minimum','Rejection counts must remain visible','Await adequate source coverage'),
    ]
    likelihood={'Rare':1,'Unlikely':2,'Possible':3,'Likely':4,'Very Likely':5}
    impact={'Low':1,'Moderate':2,'High':3,'Critical':4}
    risk=lambda l,i:'CRITICAL' if likelihood[l]*impact[i]>=15 else 'HIGH' if likelihood[l]*impact[i]>=8 else 'MEDIUM' if likelihood[l]*impact[i]>=4 else 'LOW'
    write('FAILURE_MATRIX.md','Failure matrix',
        "Likelihood is a qualitative engineering judgment, not an observed event probability. Impact reflects "
        "misinformation/availability consequences. Research QC behaviour is distinguished from live behaviour; "
        "the v3.1 stuck/zero rules are implemented for research and must not be claimed deployed universally.\n\n"
        +table(['Scenario','Likelihood','Impact','Risk','Detection','Automatic fallback','User-facing response','Prediction withheld?','Scientific implication','Recovery'],
            [[n,l,i,risk(l,i),d,f,u,w,s,r] for n,l,i,d,f,u,w,s,r in failures])
        +"\nRating rubric: likelihood 1–5 × impact 1–4; 15–20 CRITICAL, 8–14 HIGH, 4–7 MEDIUM, 1–3 LOW. "
        "This prioritisation is not actuarial probability. Tests cover many controlled faults, not every upstream outage.")
    write('RISK_PROBABILITY_MATRIX.md','Risk and qualitative probability matrix',
        "Likelihood levels: Rare, Unlikely, Possible, Likely, Very Likely. Impact: Low, Moderate, High, Critical. "
        "No percentage is supported without a monitored denominator and time horizon.\n\n"
        +table(['Risk','Likelihood','Impact','Rating','Mitigation','Residual risk'],[
            ['Data outage','Likely','High','HIGH','Caches, budgets, status and bounded retries','Concurrent provider/network failure'],
            ['Station malfunction','Possible','High','HIGH','Locked QC, rejection ledger and provenance','Unflagged instrument drift'],
            ['CAMS latency','Likely','High','HIGH','Resume job IDs; freeze run policy','ADS delay and historical release uncertainty'],
            ['Distribution shift','Likely','High','HIGH','Temporal/season/region monitoring','New regimes may invalidate calibration'],
            ['Extreme underprediction','Likely','Critical','CRITICAL','Report Severe misses and threshold diagnostics','Already observed in strict preliminary baselines'],
            ['Over-warning','Possible','High','HIGH','Joint under-/over-warning evaluation','Alert fatigue and lost work/activity'],
            ['Missing city coverage','Very Likely','High','CRITICAL','Label raw-grid fallback','Unknown local station error'],
            ['Provider dependency','Likely','High','HIGH','Replaceable adapters and explicit outages','No data if essential sources fail'],
            ['Model drift','Likely','High','HIGH','Frozen prospective verification before releases','Sparse delayed measured outcomes'],
            ['Security incident','Possible','Critical','HIGH','Server secrets, RLS, quotas and safe errors','Penetration testing/retention review incomplete'],
            ['API/compute cost','Possible','High','HIGH','Grid caching and commercial terms review','No measured national capacity budget'],
            ['Network failure','Possible','High','HIGH','Timeout/error state and manual retry','Offline forecast cannot be invented'],
            ['Database outage','Possible','Critical','HIGH','Bounded queries and incident recovery','Core ledger/cache unavailable'],
            ['Uncertainty miscalibration','Likely','High','HIGH','Conditional diagnostics and time-separated calibration','Dependence and extreme-event failures'],
            ['False confidence','Likely','Critical','CRITICAL','Source/status/limitations prominent','Users may still misread AQI as safety'],
        ]))
    groups=[
        ('Children','Outdoor play on polluted days','Forecast/category and limitations','Consider a less strenuous or differently timed activity','Better-informed planning','No individual dose or clinical protection proved'),
        ('Older adults','Sensitive outdoor routines','Environmental guidance','Discuss plans with usual support/care context','Preparation','Cannot estimate personal health risk'),
        ('Asthma-sensitive populations','Potential trigger exposure','High-pollution context','Use existing professional care advice; adjust optional exposure','Awareness','No medication advice or diagnosis'),
        ('Outdoor workers','Long unavoidable shifts','Timing/severity context','Discuss feasible breaks or task timing with employer','Planning support','Employment constraints and no measured dose'),
        ('Traffic police','Roadside exposure','Regional forecast','Institutional planning and exposure awareness','Preparation','Street-level pollution not established'),
        ('Delivery workers','Variable routes and shifts','Temporal forecast context','Compare feasible timing; avoid unsupported route precision','Awareness','No route-level validated benefit'),
        ('Commuters','Travel timing','Relatively lower-exposure periods','Adjust discretionary departure time','Planning','Weather/traffic and local variability matter'),
        ('Parents','Children’s schedules','Forecast source and category','Discuss optional activity timing','Clearer information','Not a safe/unsafe medical verdict'),
        ('Schools','Sports and outdoor assemblies','Next-day high-pollution context','Plan indoor alternatives where feasible','Preparedness','Local policies and official guidance still matter'),
        ('Athletes','Strenuous outdoor exercise','Severity and temporal variation','Choose less strenuous/alternative timing where feasible','Awareness','No personalised exercise clearance'),
        ('Hospitals/public institutions','Visitor/staff exposure planning','Environmental outlook','Communicate general pollution preparation','Institutional awareness','No prediction of admissions or clinical outcomes'),
        ('City administrators','Public communication','Source-labelled regional forecast','Use as supplementary information, verify official sources','Transparency','Not source attribution or causal policy evaluation'),
        ('Environmental researchers','Reproducible forecast evaluation','QC/manifests/splits and failures','Inspect or reproduce the study','Research utility','Incomplete primary archive/literature acceptance'),
    ]
    write('PEOPLE_IMPACT.md','Realistic people impact',
        "These are plausible uses, not observed intervention benefits or medical advice.\n\n"
        +table(['Group','Problem','AirGuard information','Possible action','Expected practical benefit','Limitation'],groups))
    uses=[
        ('Parent planning outdoor exercise','Select place and tomorrow; show category/provenance; no medical clearance'),
        ('School sports planning','Compare periods and prepare an indoor option under applicable policy'),
        ('Outdoor shift preparation','Show regional forecast and feasible timing context, not employer guarantees'),
        ('Morning versus evening commute','Compare complete relative exposure windows, not street-route safety'),
        ('Traveller entering another city','Search coordinates; raw-grid fallback works without local calibration claim'),
        ('High pollution forecast tomorrow','Display category and explicit source; disclose uncertainty validation status'),
        ('City without monitor','Display modelled fallback and absent measured evidence'),
        ('Unreliable monitoring station','Freshness/QC prevents stale station being presented as fresh truth'),
        ('CAMS available, station absent','Keep a modelled estimate; no station correction claim'),
        ('Station available, CAMS absent','Measured current context can remain; tomorrow may be withheld'),
        ('All sources down','Show unavailable state, not an invented clean-air value'),
        ('Location permission denied','Manual search/coordinates remain available'),
        ('Coordinates outside service region','Reject input before provider call'),
        ('PIN code unmatched','Show honest empty search; do not guess a city'),
        ('Share forecast with another person','URL carries selected location; warn that it reveals place of interest'),
        ('Sensitive cohort selected','Guidance changes locally; no clinical risk probability'),
        ('Hourly pollutant missing','Keep gaps; do not fill zero and call it clean air'),
        ('Two-hour period lacks common pollutants','Do not rank an incomplete relative exposure window'),
        ('Prospective score not yet available','Show no eligible pairs; historical scores are separate'),
        ('Severe observation recorded','Retain >=401 censoring and report under-warning'),
        ('Policy slider used','Recalculate assumed concentrations; label non-causal scenario'),
        ('Weather outage','AQ forecast may display while weather context is unavailable'),
        ('Satellite fire context missing','Core AQ display remains, no source attribution inferred'),
        ('Stale cache during provider failure','Show age-qualified stale state only within allowed boundary'),
        ('IST midnight crossed','Invalidate day cache/in-flight result; recompute target date'),
        ('Previously unseen station','Use only a validated support rule; fall back to raw grid'),
        ('Very wide research interval','Disclose width and conditional calibration limits; no guarantee of safety'),
        ('Malformed provider payload','Reject at adapter/browser boundary with retry state'),
        ('Researcher reproduces target table','Use checked raw caches and locked code/protocol; no new targets invented'),
        ('Investor asks national scaling','Discuss caches/licences/load testing; no million-user benchmark claimed'),
    ]
    write('USE_CASES.md','Thirty practical scenarios',table(['Scenario','Expected AirGuard behaviour'],uses))

    qa_text=r'''
Problem
Why forecast rather than show current AQI?|Tomorrow’s information supports planning; it is useful only with validated provenance and honest uncertainty.
Who needs this most?|People planning outdoor exposure, especially those with fewer flexible options; benefit has not been measured.
What problem can you actually prove?|Fragmented source, forecast and quality information; our code integrates them with explicit limitations.
What would falsify the project’s value?|Poor warnings, misunderstood precision or no useful action in user studies would weaken its case.
Does everyone need another AQI app?|No; existing apps are useful. We must demonstrate clearer trustworthy decisions, not assume demand.
What is the biggest current weakness?|The primary CAMS experiment is unfinished and strict preliminary Severe forecasts all under-warned.
Existing systems
Isn’t this just CAMS with a UI?|CAMS supplies physics forecasts; we built QC, provenance, index transformation, APIs and auditable evaluation. Correction benefit is pending.
Why not simply show CPCB values?|They are valuable official monitoring information; this prototype explores a separate non-official next-day workflow.
Why not use Google AQI?|Product capabilities vary; we claim transparent methodology and reproducibility, not universal superiority.
Why not use OpenAQ directly?|OpenAQ provides measurements; we add QC, aggregation, forecast integration and user-facing failure states.
Do other apps already give advice?|Yes. Our proposed distinction is explicit evidence and trade-off evaluation, which still needs validation.
Are you unfairly comparing competitors?|Unknown features are marked unknown; no absence or inferiority is asserted without a product audit.
Novelty
What is your real novelty?|An auditable Indian station/forecast/index/advisory integration and its validation design, not a new atmospheric model.
Hasn’t this already been done?|Components have been studied; full-review acceptance is incomplete, so we avoid originality claims beyond our implementation.
What exactly did you build?|Provider orchestration, QC, index engine, station matching, APIs/UI, immutable ledgers and reproducible experiments.
Did you invent residual learning?|No. We evaluate an established technique against direct learners and raw CAMS.
Can you claim world first?|No verified systematic evidence supports that claim.
What would strengthen novelty evidence?|Complete the targeted literature comparison, primary experiment and prospective evaluation without outcome-driven amendments.
Datasets
Is this synthetic data?|Targets are real station measurements; CAMS/weather are model output. Synthetic fault fixtures are tests only.
What is actually measured?|Pollutant concentrations at instruments distributed by OpenAQ with upstream provider identity.
What is modelled?|CAMS atmospheric fields and weather forecasts; derived AQI is index arithmetic, not a new measurement.
How large is the measured study?|The current verified artifact lists 107,280 rows, 64,799 valid targets and 179 usable stations in 100 parsed cities.
Why should we trust the datasets?|Hashes, provenance, locked QC and reconstruction support auditing; they cannot prove every instrument is accurate.
Can you call all 481 stations training data?|No. That is the eligible catalogue; the frozen sample and acquired/usable cohorts are smaller.
CPCB
Is AirGuard an official CPCB forecast?|No. It is an AirGuard CPCB-style forecast using a declared aggregation convention.
Why use the maximum pollutant sub-index?|The central implementation follows the selected index methodology; it is not a sum of disease risks.
Why require three pollutants including PM?|It is the declared engine minimum; otherwise the index is insufficient rather than a fabricated value.
Why CO and ozone use eight-hour windows?|The shared engine applies complete trailing windows; high ozone also needs its declared one-hour treatment.
Is AQI 401 an exact Severe observation?|No. It represents a lower bound when the open-ended band prevents identifying the true index.
Why not convert every ppb station gas?|Reliable conversion needs atmospheric conditions and trustworthy unit semantics; those station labels are not assumed valid.
OpenAQ
Does OpenAQ operate these monitors?|It distributes upstream measurements; provider/owner and sensor identities must be retained.
What if OpenAQ lists a retired sensor first?|Rank evidenced sensor dates and coverage, not list order or larger sensor ID.
Can old readings be used as fresh current data?|No; contributing pollutant age and coverage determine eligibility/freshness.
How do you handle failed station downloads?|Resume checksummed completed work; retain unavailable station records and the upstream failure.
Why is Chhatikara incomplete?|The audited upstream endpoints returned HTTP 500; no readings or sensor dates were fabricated.
Do you know original publication latency?|OpenAQ ingestion times are absent; historical observation features are conditional on the declared healthy-feed assumption.
CAMS
What did the 134-byte probe prove?|It decoded as nine PM2.5 grid values with forecast type, run, lead and valid time; size alone is not validity.
Why is archived forecast different from reanalysis?|A forecast is tied to an initialisation and future leads; reanalysis can use later observations.
How do you prove forecast timing?|Decode init, lead and valid time and check valid equals init plus lead; retain request and raw checksum.
Why not download the whole globe?|The frozen station envelope and required dates/parameters/leads are sufficient and cheaper to audit.
Can current past-hours fields replace the archive?|No; missing historical run identity cannot be repaired by relabelling present API fields.
Does a smoke file prove a complete baseline?|No. Every required cube, gas conversion, grid/time match and availability bound still needs validation.
Weather
Why include weather?|Meteorology can explain conditional bias, but only ablation on identical development rows establishes useful contribution.
Can observed tomorrow weather be a feature?|No; its outcome availability would leak future information.
What does previous_day2 mean here?|The existing weather archive uses a conservative forecast lead; run provenance is checked before use.
What if boundary-layer height is missing?|It is unavailable in the inherited archive; do not impute a fabricated forecast feature.
Can all weather units be assumed correct?|No. Adapter metadata and transformation must be checked before feature construction.
Did weather improve the preliminary Ridge?|Its paired MAE addition improved the non-CAMS comparison; this does not establish gain with CAMS present.
FIRMS
Does a fire pixel measure local AQI?|No; it is satellite active-fire context, not breathing-zone concentration.
Does acquisition time prove publication time?|No; that is why strict historical fire predictors remain withheld without release evidence.
Can you say a fire caused this pollution?|No. Proximity and forecast feature importance are not causal attribution.
What happens if FIRMS is unavailable?|Optional context is absent; a valid core forecast can remain available.
Why is fire not automatically included?|It needs issue-time provenance and the locked ablation admission rule, not intuitive plausibility alone.
Do no detections mean no smoke?|No; satellite detection limits and transport prevent that inference.
Data quality
What if the sensor data are wrong?|QC catches declared defects, preserves raw data/reasons and discloses remaining undetected error.
Why reject exact zeros?|The locked v3.1 rule treats indistinguishable outage zeros conservatively; it can also remove genuine near-zero ozone.
Why reject six repeated hourly values?|It flags a declared stuck-run defect; the threshold is not changed after final results.
Why keep extreme spikes?|Real pollution episodes can be spikes; automatic deletion would bias extreme-event evaluation.
Why keep PM2.5 above PM10?|The pair is inconsistent but does not identify which instrument is wrong; flag and retain it.
Do you silently drop rejected days?|No; the station-day ledger retains invalid targets and reason counts.
ML
Why Ridge?|Regularisation gives a stable simple reference with train-only scaling and alpha selection.
Why LightGBM?|It handles tabular nonlinear interactions; it must earn its complexity through fair development comparison.
Why XGBoost?|It supplies another preregistered boosted-tree candidate; its brand is not evidence of better forecasting.
Why not deep learning?|Incomplete heterogeneous histories do not automatically justify complexity; a future preregistered study can test it.
Why not an LLM?|Numeric environmental forecasting must be tied to data and verified errors, not generated plausible numbers.
What if a learner performs worse than CAMS?|Report it and carry raw CAMS forward under the frozen selection rule.
Feature engineering
Can station IDs memorise locations?|Yes; spatial holdouts and static-support policies must expose that transfer limitation.
Can target-day missingness be a predictor?|No. Freeze support before issue; target-matched support is an evaluation annotation only.
Why recent measured-minus-CAMS bias?|It may describe systematic local error, but only completed pre-issue pairs can contribute.
Can neighbouring observations leak?|Yes, if later bins or outcome-based station selection enter; apply the same cutoffs to neighbours.
What if a feature is mostly missing?|Fit missingness handling on training only and assess whether it adds supported information.
Are feature importance explanations causal?|No. They describe fitted prediction behaviour, not intervention effects.
Baselines
Why climatology?|It tests whether a forecast adds skill beyond station-season average conditions.
Why persistence?|Pollution can persist; beating yesterday/current levels is a meaningful operational hurdle.
Why raw CAMS?|Correction must demonstrate added value over the physics forecast it starts from.
Is the old 2015–2020 city model comparable?|Not directly to this station/day target; legacy results remain separate.
Are baseline rows identical?|Primary evaluation requires the declared common availability set; pair counts must be reported.
Can you mark baselines complete without CAMS?|Only for an explicitly non-CAMS preliminary study; primary readiness remains false.
Metrics
Is R² your accuracy?|No. It is variance-relative regression fit and can be negative.
Why MAE is primary?|It is interpretable in index units and less dominated by large errors than squared loss.
Why also RMSE and bias?|They reveal large-error sensitivity and systematic under-/overprediction that average absolute loss hides.
Does category accuracy capture severe misses?|Not adequately; also report severity-specific under-warning and exceedance diagnostics.
Can a lower average error still be dangerous?|Yes. Severe misses or badly calibrated tails can coexist with improved average MAE.
What does a confidence interval include?|The declared paired date-block resampling uncertainty, not all data/model/operational uncertainty.
Leakage
How do you prove there is no leakage?|Timestamp guards, chronological/global-date partitions, train-only preprocessing and final isolation provide evidence, not an absolute universal proof.
Why not random date splits?|They mix future/past regimes and can leak lagged or repeated station information.
Can future station selection leak?|Yes; training-only eligibility and frozen catalogue membership prevent outcome-based final selection.
Can scaling on all data leak?|Yes. Fit scaler and imputer only on each training partition.
Can calibration see test labels?|No. Calibration and policy selection use their own preceding window.
What would invalidate your research?|Final-test tuning, fabricated archive provenance, outcome-driven QC or broken target/availability semantics.
Temporal validation
Why expanding windows?|They reproduce accumulating historical information under the locked date geometry.
Why an embargo?|It separates adjacent partitions and reduces boundary contamination; it is not a cure for every dependency.
Do all stations move together by date?|Yes. A global date belongs to one role, preventing cross-station future-date leakage.
What if the first fold lacks 120 training days?|Report insufficient eligibility; do not weaken the primary threshold after observing results.
How do you show temporal degradation?|Report every fold and seasonal errors beside pooled comparisons.
Is development validation the final test?|No. The latest 90 days are held separately until committed model selection.
Spatial validation
What happens at an unseen station?|Raw-grid fallback remains; station correction requires validated transfer/support evidence.
Why hold cities or clusters out?|Nearby stations can share pollution and grid context, inflating station-only transfer estimates.
Why 25 km clusters?|That is the locked grouping convention; it is not proof of atmospheric independence.
Can a held-out station use its own history?|The protocol reports both with-history and no-local-monitor regimes separately.
Are spatial groups selected from outcome coverage?|No. Group assignments use frozen metadata, with training-only coverage checks.
Can you claim nationwide calibrated precision?|No; missing regions/monitors and coarse forecast cells limit transfer claims.
Severe AQI
Why exclude Severe from exact regression fitting?|The true value is unidentified above the lower bound; training on a fabricated exact 401 biases the model.
How do you score Severe?|Category/exceedance detection, share below 401 and lower-bound shortfall.
What negative result did you get?|All strict preliminary baseline forecasts on 363 censored Severe validation days fell below 401.
Can an interval reaching 401 prove Severe coverage?|No. It is compatibility with a lower bound, not coverage of the unknown true upper value.
Can you repair Severe performance after final test?|Not in that evaluation; any change requires a future version and fresh held-out evidence.
Is Severe rarity an excuse?|No. Report sample size and failures prominently, even when learning extremes is difficult.
Uncertainty
Does 90% nominal mean every user gets 90% coverage?|No. Marginal calibration can fail by location, season, severity and dependent days.
Why conformal prediction?|A separate empirical calibration step is auditable and can complement point forecasts.
What is Mondrian conformal here?|Calibration by forecast-defined groups, not by unknowable observed test categories.
What if an interval is huge?|Communicate its width and limitations; width alone does not justify a safety claim or automatic abstention.
What if group calibration has few samples?|Disclose insufficient support or use a declared fallback; do not invent precise conditional guarantees.
Can calibrated intervals be deployed now?|Not as validated CAMS correction intervals while the primary experiment remains incomplete.
Health/advisory
Is the health advisory medically validated?|No. It is environmental exposure guidance with no clinical outcome calibration.
Does vulnerability mean personal disease risk?|No. Cohorts are communication/exposure strata, not diagnoses.
How is under-warning defined?|Issued category lower than the observed category; serious under-warning is at least two categories below.
Why measure over-warning?|Unnecessary restrictions and alert fatigue are real trade-offs, even for cautious policies.
Is P3 a guaranteed risk controller?|No dependent-day guarantee is claimed; its calibration-window target is an empirical aim.
Can you change cohort thresholds after final results?|No. Keep the committed policy and report its actual performance.
Architecture
Why separate live and research paths?|Production availability and scientific issue-time validation have different provenance and release requirements.
Where is AQI calculated?|The shared Python engine supplies targets, forecasts and scenario calculations under one version.
What if cache serves the wrong day?|IST-aware expiry and browser rollover tests prevent stale target-day reuse.
Why bounded concurrent provider work?|It limits latency and quotas while permitting independent source failures to be reported.
Does caching improve scientific accuracy?|No. It improves availability/cost and must preserve freshness/source identity.
Can experimental code silently replace live forecast?|No automatic promotion occurs; production release is a separate approval and verification step.
Frontend
What if geolocation is denied?|Manual place or coordinate search remains available.
What if JSON is malformed?|The response contract fails before caching/rendering, showing an error rather than fabricated values.
What if search results have invalid coordinates?|Filter them with the same service-region check and reject malformed result arrays.
Can old requests overwrite a newly selected place?|Cancellation/state guards and regression tests protect against that race.
Is the browser storing my health diagnosis?|It stores a locally selected advisory cohort, not a diagnosis; location links still reveal selected coordinates.
What if charts fail?|Text tables and explicit missing states provide a usable fallback; accessibility is still subject to user testing.
Backend
What happens if all APIs fail?|No substitute AQI is invented; the API returns unavailable and the UI shows it.
How are invalid inputs handled?|Allowlisted parameters, finite service-region coordinates and bounded labels are checked before provider calls.
Do retries bypass limits?|No; each transport attempt consumes shared quotas and uses bounded retry logic.
Can user input choose an outbound URL?|No. Adapters use fixed provider endpoints rather than arbitrary hosts.
Why HTTP 202?|It represents queued provider work, not a completed forecast.
Do errors reveal database credentials?|Public errors are generic and logs should retain safe classes/redacted diagnostics only.
Database
What do you store?|Environmental records, caches, quotas, snapshots, forecast artifacts and verification pairs; no diagnosis is required.
Does RLS make service-role endpoints safe?|Not by itself; privileged server credentials still require operation authorisation and input validation.
Why immutable forecasts?|Verification must compare a forecast actually issued before the outcome, not a rewritten prediction.
How do you pair verification?|Use issue/target/location/station/method identity and retain provenance; never bind stations after seeing outcomes.
What if a forecast lacks a station binding?|Report the gap; do not manufacture a measured-station verification later.
What if the database is corrupted?|Fail closed, restore verified evidence and audit pairing/checksums before claiming valid performance.
Security
Where is the ADS token displayed?|Nowhere in output; the official client consumes private configuration with logging suppressed.
Can the client receive the service-role key?|Server-only secret names/values are audited out of browser source/assets.
Is a secret scan a penetration test?|No. It is a scoped static/material check with explicit remaining security limits.
Can URLs disclose a place of interest?|Yes. Shareable location parameters and infrastructure logs create privacy considerations.
How are internal refresh operations protected?|Authenticated server routes and allowlisted operations; public selectors cannot invoke refresh.
What remains before commercial release?|Privacy/retention review, penetration testing, licensing, load testing and approved release validation.
Deployment
Have you deployed this correction?|No. Experimental station correction and source hardening remain separate from the existing production release.
What commit produced a research result?|Each immutable result records its source SHA; current code changes do not rewrite prior provenance.
Why not merge automatically?|Research selection does not authorise a production deployment; release requires explicit permission.
Can a successful build prove live reliability?|No. Real provider, database, browser and failure checks are needed too.
How does local demo run?|Run the Python API on 8787 and Next development server on 3000; development rewrites connect them.
What is the backup if providers fail?|Show a clearly labelled archived research/fault-demo artifact; never pretend it is live data.
Cost
Is everything free?|No. Free tiers have quotas/terms, and commercial licences/support/hosting can require payment.
What is the biggest research cost?|Archive latency/storage and repeated development fitting, separate from user-serving inference.
Can you quote production cost exactly?|Not without measured traffic, retention, licences and current provider quotes.
Does one user require new provider calls?|A validated shared grid/cache hit can avoid them; cache freshness still matters.
Could API quota kill a demo?|Yes; use bounded cached locations and an honest backup, not evasion or fake success.
Why not promise zero-cost national deployment?|Licensing, infrastructure, monitoring and support scale beyond a prototype.
Scalability
What happens with ten users?|Shared cache/leases reduce redundant work, but cold misses and upstream availability still matter.
What about ten thousand users?|Batch popular grids, measure contention, licence APIs and capacity-test queues/cache/database.
What about one million users?|The prototype has no such load evidence; require a redesigned capacity plan and empirical tests.
Why batch by grid?|Many nearby users share the same atmospheric cell and forecast run.
What is the storage bottleneck?|Dated parameter/lead/grid fields and immutable ledgers under retention requirements.
Can station models train per user request?|They should be trained offline; user-serving requests apply frozen versions, never tune from outcomes.
Ethics
Can you call a lower-pollution time safe?|No. It is relatively lower exposure, not zero risk or medical clearance.
Does an explanation prove causation?|No. Feature importance and scenario arithmetic are predictive/assumptive, not intervention effects.
Who is disadvantaged by missing stations?|Poorly monitored regions and people without flexible work options; fallback availability does not equal accuracy.
Could warnings cause harm?|Under-warning can reassure falsely; over-warning can impose costs or fatigue. Both are evaluated.
Why disclose failures to judges?|Scientific integrity requires reporting them; hiding poor Severe performance defeats the project’s use case.
Is this personalised healthcare?|No. It is environmental information with broad exposure strata.
Failure handling
What if the forecast interval is huge?|Display uncertainty and limits; do not manufacture confidence or equate width with guaranteed danger.
What if a sensor is stuck?|Research QC rejects the locked run and retains its reason; do not claim universal live deployment.
What if CAMS acquisition is delayed?|Resume existing IDs and continue independent hardening/documentation; never substitute reanalysis.
What if only one provider works?|Display only what its provenance supports and withhold unsupported claims.
What if stale data look plausible?|Plausibility does not make them fresh; show timestamp/status and enforce cutoffs.
What if a provider changes schema?|Fail closed, inspect actual metadata and version the adapter before accepting new semantics.
People impact
How does this help society?|It may support preparation and exposure-aware planning; no measured clinical or behavioural benefit is claimed.
Who will actually use it?|Families, schools, commuters, outdoor workers and researchers are hypotheses to validate through user studies.
What if users cannot change activity timing?|Acknowledge constraints and provide context without blaming individuals or promising protection.
Can hospitals rely on it for admissions planning?|Not as a validated clinical demand forecast; only supplementary environmental context.
Can traffic police use street-level predictions?|No street-level accuracy is established from a coarse grid; institutional local monitoring remains important.
How would you measure benefit next?|Preregister usability, decision comprehension and feasible-action studies; separate them from clinical claims.
Research contribution
Are you cherry-picking results?|Report all declared folds/learners, paired rows, negatives and immutable artifacts; final isolation is tested.
Why not publish only the best season?|That would hide transfer degradation; seasons/regions and insufficient sample counts must be listed.
Does preliminary success prove CAMS correction?|No. The current Ridge comparison lacks raw archived CAMS and must be labelled non-CAMS.
What is reproducible today?|The measured table and preliminary artifacts have raw-cache/fresh-checkout evidence with a reused pinned runtime.
What is not yet reproduced?|The primary CAMS model experiment and an independent installed environment need their own audits.
How do you select the final model?|Development rolling-fold mean MAE under the locked tie/fallback rule, then commit all configuration/hashes before final access.
Limitations
Can AirGuard predict my street?|It returns a grid-scale estimate; street-level variation is unsupported.
Can you guarantee every location has measured AQI?|No. Coverage/units/freshness can fail and must be visible.
What is your most serious negative result?|Complete under-warning by strict preliminary baselines on evaluated censored Severe days.
Does current station selection create bias?|Yes. Selecting active current monitors creates survivorship; disclose it rather than claiming historical representativeness.
Does conformal fix distribution shift?|No. It calibrates under assumptions that shift or dependence can violate.
What is missing from research readiness?|Complete genuine CAMS evaluation, accepted literature review, primary reproduction and a real 30-day verified record.
Future work
What should happen immediately after archive arrival?|Validate complete fields/units/times, match frozen data and run development only before selecting a model.
When can final test run?|Only after a committed MODEL_SELECTION_LOCK with isolation/hash/configuration checks; the latest request authorises one such evaluation.
What happens after poor final performance?|Report it without retuning; future changes need a new study and held-out evidence.
When can a correction be deployed?|After validated evidence plus explicit separate production-release approval.
Would deep learning be future work?|Possibly, with sufficient data, preregistered comparisons and proper cost/transfer evaluation.
What prospective milestone remains?|Thirty real elapsed and verified days; it cannot be achieved by backdating or synthetic outcomes.
Commercialization
How could this become a product?|Validate demand, warnings and usability, obtain licences, test capacity/privacy/security and release conservatively.
Who is a plausible customer?|Institutions or users needing transparent environmental planning; willingness to pay is unmeasured.
Is the research score a revenue argument?|Not directly. Reliability, decisions, distribution and compliance need separate evidence.
Could you sell vulnerability risk predictions?|Not as personal medical risk without the appropriate independent validation; current scope is environmental guidance.
What would an investor criticise most?|Unproven demand, provider dependence and unfinished forecasting advantage; acknowledge those honestly.
What is the defensible commercial promise now?|An auditable prototype and research workflow, not nationwide calibrated accuracy or health outcomes.
'''
    qa=[]; section=None
    for line in qa_text.strip().splitlines():
        if '|' not in line:
            section=line.strip(); continue
        question,answer=line.split('|',1); qa.append((section,question.strip(),answer.strip()))
    if len(qa)<200: raise ValueError('At least 200 distinct cross-questions required')
    if len({q for _,q,_ in qa})!=len(qa): raise ValueError('Duplicate questions')
    blocks=[]; previous=None
    for i,(section,q,a) in enumerate(qa,1):
        if section!=previous: blocks.append('\n## '+section+'\n'); previous=section
        blocks.append(f"{i}. **{q}**\n\n   {a}\n")
    write('JURY_QA.md',f'{len(qa)} difficult viva questions with concise answers',
        "Answers describe the current evidence, not promised future results. Source-specific numbers are anchored below. "
        "Practice saying limitations directly.\n\n"+'\n'.join(blocks))
    personas=[
        ('AI/ML professor',['ML','Metrics','Baselines'],'No primary CAMS advantage has been established.','Strong baseline and train-only selection discipline.','Learner complexity can hide extreme-event failure.'),
        ('Atmospheric scientist',['CAMS','CPCB','FIRMS'],'Coarse cells and forecast-to-hour interpolation limit local meaning.','Actual archived-run metadata and explicit unit checks.','Gas density/vertical-level mismatch or publication assumption.'),
        ('Software architect',['Architecture','Backend','Deployment'],'Provider/database coupling creates availability bottlenecks.','Bounded orchestration, shared cache and explicit failure states.','Cold misses and queues can dominate latency.'),
        ('Data engineer',['Datasets','OpenAQ','Data quality'],'QC and current-catalogue survivorship do not establish instrument truth.','Immutable raw hashes and retained rejection ledgers.','Unexpected schema/unit drift.'),
        ('Research reviewer',['Research contribution','Leakage','Temporal validation'],'Novelty acceptance and primary reproduction remain incomplete.','Preregistered splits, final seal and disclosed negative results.','Any post-outcome change would contaminate inference.'),
        ('Hackathon judge',['Problem','Frontend','People impact'],'A useful demo is not proof of measured benefit.','A coherent source-labelled location-to-advisory workflow.','Live provider failure during presentation.'),
        ('Public-health reviewer',['Health/advisory','Ethics','Severe AQI'],'Strict preliminary Severe under-warning defeats reassurance claims.','Censoring, warning-cost analysis and no clinical claims.','False reassurance to users with limited choices.'),
        ('Investor',['Commercialization','Cost','Scalability'],'Demand, commercial licences and capacity are unproven.','Auditable implementation and potential institutional planning use.','Provider costs and weak differentiation.'),
        ('Cybersecurity reviewer',['Security','Database','Backend'],'A scoped secret scan is not penetration certification.','Server secret separation, authorisation and safe failure paths.','Location retention and privileged credential misuse.'),
        ('Ordinary user',['Frontend','Failure handling','Limitations'],'Source/status distinctions may still be misunderstood.','Manual location search and explicit missing/stale states.','Mistaking a grid estimate or lower-exposure period for safety.'),
    ]
    persona_blocks=[]
    for person,categories,criticism,positive,project_risk in personas:
        questions=[(q,a) for group,q,a in qa if group in categories][:10]
        persona_blocks.append('## '+person+'\n\n'+
            f"Strongest criticism: {criticism}\n\nStrongest positive point: {positive}\n\nProject risk: {project_risk}\n\n"
            +table(['Question','Recommended concise answer'],questions))
    write('JUDGE_PERSONAS.md','Ten practice reviewer personas',
        "These are authored practice simulations, not quotes, endorsements or actual external reviews. "
        "Each persona has ten cross-questions and evidence-limited answers.\n\n"+'\n\n'.join(persona_blocks))
    demo_headers=['What to click','What appears','What to say','Technical concept','Likely question','Answer']
    demo3=[
        ['Open /live','Selected Indian place; current/tomorrow cards','We distinguish measured observations from modelled forecasts.','Provenance','Is this official?','No; AirGuard CPCB-style forecast.'],
        ['Search Avadi or known cached city','Validated location results and loading','A national grid fallback does not require a local training-city list.','Location/provider orchestration','Can you predict a street?','Only grid-scale relevance is supported.'],
        ['Inspect current source/freshness','Measured or modelled label and time','No station observation is manufactured when a monitor is absent.','Fallback/QC','What if station offline?','Labelled modelled fallback or unavailable state.'],
        ['Open Forecast & advisory; choose cohort','Tomorrow category and environmental guidance','This is exposure guidance, not personal health risk.','Advisory','Is it medically validated?','No clinical outcome validation.'],
        ['Open How was this calculated?','Sources, aggregation and forecast record','The shared engine and immutable record make the calculation auditable.','Method/prospective identity','What did you build?','Integration, QC, index logic, APIs/UI and research infrastructure.'],
        ['Show ONE_PAGE_RESULTS.md','Verified development facts and failures','Strict Ridge beat climatology preliminarily; it did not establish improvement over persistence or CAMS.','Honest evaluation','What negative result?','All strict Severe validation forecasts under-warned.'],
    ]
    write('DEMO_3_MIN.md','Three-minute live demo',
        "Budget roughly 30 seconds per step. Rehearse source availability first; never promise a particular AQI value. "
        "The commands are in README.md. Do not show credentials, terminal environment dumps or the ADS setup file.\n\n"
        +table(demo_headers,demo3))
    demo8=demo3[:4]+[
        ['Open hourly text table/chart','Forecast hours, gaps and categories','These concentrations are modelled; the relative exposure window is not a safety label.','Forecast temporal support','Can missing hours be zero?','No. Gaps stay missing.'],
        ['Open measured pollutant context','Station identity/distance/last observation','Measured coverage and individual pollutant age matter.','Station support','Are all sensors current?','Dedicated metadata selection checks dates; old sensor order is not evidence.'],
        ['Open Policy scenarios; choose a small reduction','Original saved forecast baseline and recalculated scenario','This is arithmetic under assumed concentration changes, not policy causality.','Shared engine/immutability','Will this intervention reduce AQI?','The simulator cannot predict actual intervention effects.'],
        ['Open /city-atlas; table/map','Modelled cells distinguished from monitors','Availability across India does not establish calibrated precision everywhere.','Spatial fallback','What about unseen city?','Raw-grid estimate with explicit support limits.'],
        ['Open /research then track record','Readiness and eligible verification count','A 30-day track record requires real elapsed days and paired outcomes.','Prospective audit','Can historical scores stand in?','No; these evidence streams are separate.'],
        ['Open FAILURE_MATRIX.md','Thirty-five fault scenarios','Failure handling includes honest withholding, not fabricated continuity.','Reliability','What if all sources fail?','Unavailable message and backup demonstration.'],
        ['Open CLAIM_EVIDENCE_MATRIX.md','Allowed versus pending claims','The CAMS correction/final results stay pending until their actual experiment.','Scientific integrity','Are you cherry-picking?','All declared folds and negative artifacts remain auditable.'],
        ['Finish with limitations and next gate','MODEL_SELECTION_LOCK pending','Archive, development selection and final evaluation occur in that order.','Reproducibility','Can you change after final?','No retuning or threshold changes in that evaluation.'],
    ]
    write('DEMO_8_MIN.md','Eight-minute technical demo',
        "Budget 35–45 seconds per step, shortening navigation as needed. Use an already checked location.\n\n"+table(demo_headers,demo8))
    write('DEMO_FAILURE_MODE.md','Demo backup and controlled failures',
        "A provider outage should change the demonstration, not the truth of the numbers. Label all recorded "
        "screenshots/research artifacts as historical. Do not rewrite frontend live values or load synthetic fault "
        "fixtures as if they are current observations.\n\n"+table(demo_headers,[
            ['Deny geolocation','Manual search remains','Permission denial does not block place search.','Graceful location fallback','Do you track me automatically?','Geolocation starts only after a user action.'],
            ['Enter invalid coordinates via search','Validation error','Invalid inputs do not become forced nearest-city predictions.','Input boundary','What if NaN?','Rejected before provider use.'],
            ['DevTools offline, then refresh in a controlled local demo','Unavailable/retry state','No substitute clean-air number is shown.','Network failure','Does caching hide outage?','Source/age bounds still apply.'],
            ['Open ONE_PAGE_RESULTS.md or stored screenshot','Clearly historical checkpoint','This is a recorded research artifact, not live conditions.','Backup provenance','Why not fake a successful live result?','That would mislead users and invalidate evidence.'],
            ['Open JURY_QA.md and FAILURE_MATRIX.md','Failure/recovery explanations','We distinguish upstream failure from forecast error.','Operational honesty','What remains blocked?','Read the current acquisition manifest and checkpoint report.'],
        ]))
    slides=[
        ('Problem',['Outdoor decisions need forward information','Monitoring and forecasts have different meanings','Missing/stale data create false confidence','Practical action is constrained'],'Person planning tomorrow + source labels','Start with a concrete planning need and acknowledge that benefit requires measurement.','Why another AQI app?'),
        ('Existing gap',['Existing services remain valuable','A dashboard is not forecasting validation','Coarse forecasts need local testing','Advisory benefits are unproved'],'Fair competitor matrix','Do not downgrade competitors; describe the auditable workflow you want to test.','Has this already been done?'),
        ('Solution',['Source-labelled nationwide estimate','Central CPCB-style AQI engine','Exposure guidance and missing states','Research correction kept separate'],'Live current/tomorrow cards','Explain the user flow while naming current validation limits.','What is live versus experimental?'),
        ('Architecture',['Validated location input','Bounded provider/cache orchestration','Shared index and provenance','API contract to frontend'],'ARCHITECTURE_DEFENSE mermaid','Trace one location from request to display and point out withholding boundaries.','What if APIs fail?'),
        ('Data',['OpenAQ-hosted upstream measurements','Genuine dated CAMS runs','Forecast weather and optional fire','Locked QC and rejection ledger'],'MEASURED/MODELLED/DERIVED classification','Read counts from the measured artifact; never call model output ground truth.','Is this synthetic?'),
        ('AI/ML',['Raw CAMS plus simple baselines','Direct versus residual ladder','Train-only tuning/preprocessing','Censored Severe excluded from exact error'],'Residual equation + fold diagram','The hypothesis is that correction helps; raw CAMS wins if evidence says so.','Why no deep learning?'),
        ('Validation/results',['Chronological and spatial tests','Preliminary non-CAMS results only','Severe under-warning disclosed','Primary/final results pending'],'Verified preliminary diagnostics figure','Quote the results sheet with its scope, sample counts and intervals.','Are you cherry-picking?'),
        ('Novelty',['Auditable India-specific integration','Provenance/QC/validation infrastructure','Uncertainty/advisory trade-off study','No world-first assertion'],'NOVELTY_MATRIX','Separate owned engineering from CAMS physics and established ML methods.','Is it CAMS with a UI?'),
        ('People impact and failures',['Plausible exposure-aware planning','No clinical benefit established','Manual/fallback/unavailable states','Coverage and access inequities'],'Scenario + failure matrix','Describe feasible use, not guaranteed health improvement.','Who benefits if shifts cannot change?'),
        ('Conclusion',['Prototype flow is tested','Evidence gates remain explicit','Archive → selection lock → one final test','Production correction needs separate approval'],'Claim-evidence checklist','Finish with the current blocker and the next evidence gate instead of a marketing claim.','What is your biggest weakness?'),
    ]
    slide_blocks=[]
    for i,(title,bullets,visual,talk,question) in enumerate(slides,1):
        slide_blocks.append(f"## {i}. {title}\n\n"+'\n'.join('- '+b for b in bullets)
            +f"\n\nBest visual: {visual}\n\n30-second explanation: {talk}\n\nLikely cross-question: {question}\n")
    write('PRESENTATION_10_SLIDES.md','Content for ten presentation slides',
        "Content only; no PPT file or research paper is generated. Keep each slide to these four bullets.\n\n"+'\n'.join(slide_blocks))
    write('PITCHES.md','One sentence, thirty seconds, one minute and three minutes',
        "**One sentence:** AirGuard is a source-labelled Indian air-quality planning prototype with a CPCB-style "
        "forecast engine and an auditable research workflow.\n\n"
        "**Thirty seconds:** We combine measured station context with a modelled next-day forecast, show whether "
        "data are missing or stale, and provide environmental exposure guidance. Our own work is the QC, index, "
        "integration, interfaces and evaluation infrastructure. A station correction must still beat raw CAMS "
        "under the locked experiment; no clinical or street-level accuracy claim is made.\n\n"
        "**One minute:** Select a place or coordinates. AirGuard validates the request, reuses bounded caches and "
        "calls configured sources. Measurements and forecasts remain labelled separately; the central engine "
        "constructs an AirGuard CPCB-style index and explicit insufficient-data states. The research dataset "
        "retains QC exclusions and censored Severe labels. Preliminary non-CAMS development results are real, "
        "but they are not proof of CAMS correction. Genuine archived forecasts are being acquired before direct "
        "and residual comparison. We disclose extreme under-warning, privacy/cost limits and provider dependence.\n\n"
        "**Three-minute technical explanation:** AirGuard India addresses a planning question: what information "
        "can help someone prepare for tomorrow’s air-quality conditions? Current AQI alone describes a different "
        "time. Forecasts are useful only if we explain their source, their spatial scale and what happens when "
        "measurements or providers fail. Existing AQI services remain valuable; we are testing an auditable "
        "integration rather than claiming to have invented atmospheric forecasting.\n\n"
        "The user selects a place or coordinates. The backend validates the input, applies shared request "
        "budgets and caches, and retrieves measured station context and modelled forecasts. A central "
        "CPCB-style engine constructs the index. The frontend labels measured and modelled information, "
        "shows timestamps and missing data, and gives environmental exposure guidance. A coarse CAMS cell "
        "does not establish street-level precision. If no valid forecast exists, the system withholds the "
        "value instead of inventing clean air.\n\n"
        "Our research targets are real OpenAQ-hosted CPCB-provider station measurements. The retained "
        "table has 107,280 station-days, including 64,799 valid and 42,481 rejected targets. Raw files and "
        "rejection reasons remain available. The locked QC rules reject outage zeros, stuck sequences and "
        "unsupported units while retaining flagged spikes and PM2.5-above-PM10 inconsistencies. Severe "
        "indices are lower bounds of at least 401, so we exclude them from exact regression fitting/error "
        "and evaluate category misses, exceedances and lower-bound shortfall.\n\n"
        "The scientific question is whether Indian station correction adds value over raw CAMS. We compare "
        "direct and residual Ridge, LightGBM and XGBoost with persistence and climatology. All methods must "
        "use the same eligible observations and date windows. Training-only tuning, chronological calibration "
        "and spatial holdouts test temporal and geographic transfer. Intervals and advisory policies are "
        "evaluated for both under-warning and over-warning, not described as clinical risk guarantees.\n\n"
        "The completed preliminary study is explicitly non-CAMS: strict Ridge improved MAE over climatology "
        "by 8.96 index units, but history Ridge did not establish improvement over persistence. All strict "
        "baseline forecasts on 363 evaluated censored Severe days under-warned. Those failures matter more "
        "than a flattering average alone. Genuine archived CAMS files have now passed the probe and initial "
        "cube checks; the complete primary comparison remains pending acquisition. Selection must be locked "
        "and committed before the final test. Real prospective verification and user studies are still needed "
        "before stronger accuracy, health-benefit or commercial-readiness claims.\n\n"
        "**Novelty:** An auditable combination of Indian index, station QC, forecast provenance and validation.\n\n"
        "**People impact:** Better information may support feasible exposure-aware preparation; benefit is not measured.\n\n"
        "**Limitation:** Primary CAMS superiority and extreme-event reliability remain unestablished.\n\n"
        "**Future work:** Finish the locked experiment and prospective/user evaluations before a separately approved release.")
    claims=[
        ['Measured targets built with v3.1 QC','Verified measured report and rejection ledger','results/research/measured_dataset.json','High within audited scope','VERIFIED','Yes, with counts/date scope','Yes'],
        ['Dataset reproducible in fresh checkout','Raw-input reconstruction report','results/research/non_cams_clean_clone_reproduction.json','High; reused runtime','VERIFIED','Yes, disclose scope','Yes'],
        ['Strict Ridge beats climatology','Paired development MAE/CI','preliminary_latest.json','Development only','DEVELOPMENT ONLY','Yes, label non-CAMS','Yes, label non-CAMS'],
        ['History Ridge beats persistence','CI includes zero','preliminary_latest.json','Not established','UNSUPPORTED','No','Explain negative result'],
        ['CAMS probe is an operational forecast','Decoded run/lead/valid/PM/grid checksum','cams_ads_probe.json','High for one field','VERIFIED','Yes if verified status','Yes'],
        ['Complete primary CAMS archive/baseline','Collection manifest incomplete','cams_development_acquisition.json','Pending','PENDING','No completion claim','Explain status'],
        ['AirGuard correction improves CAMS','No primary comparison yet','primary.py is infrastructure only','Unknown','PENDING','No','State experiment pending'],
        ['Final test verified','No committed selection lock/evaluation','MODEL_SELECTION_LOCK absent','Not established','PENDING','No','State sealed'],
        ['Thirty-day prospective skill','Real verified-day count below requirement','prospective_audit.json','Not established','PENDING','No','Quote actual count'],
        ['Live prospective forecasts exist','Immutable ledger audit','prospective_audit.json','Within audit scope','PROSPECTIVE ONLY','Yes, not skill','Yes'],
        ['Street-level precision','Coarse grid and no validation','providers.py / CAMS grid','Unsupported','UNSUPPORTED','No','Explicitly deny'],
        ['Medical benefit','No clinical outcome study','advisory methods only','Unsupported','UNSUPPORTED','No','Explicitly deny'],
        ['World first','No completed exhaustive novelty proof','literature review access limitations','Unsupported','UNSUPPORTED','No','Explicitly deny'],
        ['Failure handling is tested','Unit/component/E2E artifacts','results/project_hardening/verification.json','Within tested scope','VERIFIED if tests pass','State actual checks only','Yes, with limits'],
        ['Million-user production ready','No load benchmark','cost/scalability plan','Unknown','UNSUPPORTED','No','Describe required capacity tests'],
        ['Research Severe performance adequate','All strict preliminary Severe forecasts below 401','preliminary_latest.json','Evidence against claim','UNSUPPORTED','No; disclose failure','Disclose failure'],
    ]
    write('CLAIM_EVIDENCE_MATRIX.md','Claim-evidence ledger',
        "Status vocabulary: VERIFIED, DEVELOPMENT ONLY, FINAL TEST VERIFIED, PROSPECTIVE ONLY, PENDING, "
        "UNSUPPORTED. No row currently receives FINAL TEST VERIFIED. Confidence is a qualitative audit judgment, "
        "not a forecast probability. Paths below are repository-relative.\n\n"
        +table(['Claim','Evidence','Source artifact','Confidence','Status','Can say in demo?','Can say in viva?'],claims))
    hostile=[
        ['CRITICAL','Strict preliminary Severe under-warning','All three strict baselines below 401 on 363 evaluated days','Disclose failure; no operational reliability/correction claim','Open scientific limitation'],
        ['CRITICAL','Final contamination risk','Primary selection and final run not yet executed','Keep final sealed; create immutable committed selection lock first','Gate remains unmet'],
        ['HIGH','Tomorrow support used as forecast feature','Inherited matched-support design could leak target QC/missingness','Freeze pre-issue support; evaluation-only annotations','Primary implementation audit required'],
        ['HIGH','Missing historical publication evidence','OpenAQ ingestion/FIRMS release times unavailable','Conditional history sensitivity; withhold strict fire','Cannot reconstruct missing evidence'],
        ['HIGH','CAMS units/time interpolation mismatch','Gas mixing ratios require same-run thermodynamics/level','Validate actual GRIB cube/coefficients before fitting','First model-level archive pending'],
        ['HIGH','Malformed frontend payload crash','Components previously trusted nested response/search fields','Boundary validator, timeout/filter tests and safe error states','Tested source, not production release'],
        ['HIGH','Weak novelty/overclaims','Established methods; primary and literature incomplete','Fair comparator/claim matrix and explicit limitations','No world-first or superiority claim'],
        ['HIGH','Clinical overclaim','No clinical/cohort outcomes','Environmental guidance terminology and trade-off-only claims','User misunderstanding still possible'],
        ['HIGH','Provider/licensing/capacity dependence','Free tiers and no million-user benchmark','Bounded cache/quotas, source fallback, commercial planning','Licences/load testing remain external work'],
        ['HIGH','Prospective pairing gaps','Existing audit has unbound forecasts and missing historical issuance SHA','Preserve old records; future tested source fixes need approved release','No backfilled evidence or 30-day claim'],
        ['MEDIUM','Current-catalogue survivorship','Modern active sample is not contemporaneous historical inventory','Disclose frozen selection basis and training-only eligibility','Representativeness unresolved'],
        ['MEDIUM','Uncertainty conditional failure','Dependence, censoring and sparse strata','Report coverage/width by severity/region/season','No subgroup guarantee'],
        ['MEDIUM','Privacy/privileged access','Location URLs/cache + server credentials','Clear local/server storage disclosure, RLS and auth','Penetration/retention review pending'],
        ['MEDIUM','Reproduction scope','Fresh checkout reused current runtime/input files','State exact scope and require primary independent audit','No independent environment claim'],
    ]
    write('HOSTILE_AUDIT.md','Hostile project audit',
        "This is an internal attempt to reject overclaims. A documentation fix does not repair missing scientific evidence. "
        "Open limitations remain visible; no critical/high scientific result is hidden.\n\n"
        +table(['Priority','Attack','Evidence','Safe remedy performed/planned','Residual status'],hostile))
    write('README.md','AirGuard jury and viva defense index',
        "Start with ONE_PAGE_PROJECT, ONE_PAGE_RESULTS and CLAIM_EVIDENCE_MATRIX. This pack is a checkpoint "
        "defense of actual implementation/evidence, not a research paper or a claim that all experiments finished.\n\n"
        "## Launch a local demo\n\nFrom the repository root, in two terminals:\n\n"
        "```powershell\n.\\.venv-live\\Scripts\\python.exe -m webapp.dev_api_server --port 8787\n```\n\n"
        "```powershell\ncd webapp\nnpm run dev -- --hostname 127.0.0.1 --port 3000\n```\n\n"
        "Open http://127.0.0.1:3000/live. Use the configured private server environment; never print it. "
        "Choose an already checked place, rehearse live source states and use DEMO_FAILURE_MODE if a provider fails. "
        "No experimental correction deployment is included.\n\n"
        "## Evidence and navigation\n\n"+'\n'.join(f'- [{name.removesuffix(".md").replace("_"," ").title()}]({name})' for name in sorted(documents))+
        "\n\n- [Completion report](COMPLETION_REPORT.md)\n- [Build/verification evidence](../../results/project_hardening/verification.json)\n"
        "- [Literature access and novelty limits](../research/LITERATURE_FULLTEXT_REVIEW.md)\n"
        "- [Locked research protocol](../research/research_protocol.yaml)\n"
        "- [Patched dependencies and audit scope](DEPENDENCY_SECURITY.md)\n",evidence=False)
    for name,text in documents.items():
        (OUT/name).write_text(text,encoding='utf-8')
    manifest={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'generator':'scripts/build_defense_pack.py',
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'paper_generated':False,'question_count':len(qa),'failure_scenarios':len(failures),'use_cases':len(uses),
        'judge_personas':len(personas),'questions_per_persona':10,'presentation_slides':len(slides),
        'measured_dataset_hash':measured['dataset_hash'],'preliminary_run_id':preliminary['run_id'],
        'files':{name:hashlib.sha256(text.encode()).hexdigest() for name,text in documents.items()}}
    dependency_doc=OUT/'DEPENDENCY_SECURITY.md'
    if dependency_doc.exists(): manifest['files'][dependency_doc.name]=hashlib.sha256(dependency_doc.read_bytes()).hexdigest()
    target=ROOT/'results/project_hardening/defense_pack_manifest.json'; target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'documents':len(documents),'questions':len(qa),'failure_scenarios':len(failures),'use_cases':len(uses)}))

if __name__=='__main__': main()
