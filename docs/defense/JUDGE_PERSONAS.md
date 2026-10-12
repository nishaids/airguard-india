# Ten practice reviewer personas

These are authored practice simulations, not quotes, endorsements or actual external reviews. Each persona has ten cross-questions and evidence-limited answers.

## AI/ML professor

Strongest criticism: No primary CAMS advantage has been established.

Strongest positive point: Strong baseline and train-only selection discipline.

Project risk: Learner complexity can hide extreme-event failure.

| Question | Recommended concise answer |
| --- | --- |
| Why Ridge? | Regularisation gives a stable simple reference with train-only scaling and alpha selection. |
| Why LightGBM? | It handles tabular nonlinear interactions; it must earn its complexity through fair development comparison. |
| Why XGBoost? | It supplies another preregistered boosted-tree candidate; its brand is not evidence of better forecasting. |
| Why not deep learning? | Incomplete heterogeneous histories do not automatically justify complexity; a future preregistered study can test it. |
| Why not an LLM? | Numeric environmental forecasting must be tied to data and verified errors, not generated plausible numbers. |
| What if a learner performs worse than CAMS? | Report it and carry raw CAMS forward under the frozen selection rule. |
| Why climatology? | It tests whether a forecast adds skill beyond station-season average conditions. |
| Why persistence? | Pollution can persist; beating yesterday/current levels is a meaningful operational hurdle. |
| Why raw CAMS? | Correction must demonstrate added value over the physics forecast it starts from. |
| Is the old 2015–2020 city model comparable? | Not directly to this station/day target; legacy results remain separate. |


## Atmospheric scientist

Strongest criticism: Coarse cells and forecast-to-hour interpolation limit local meaning.

Strongest positive point: Actual archived-run metadata and explicit unit checks.

Project risk: Gas density/vertical-level mismatch or publication assumption.

| Question | Recommended concise answer |
| --- | --- |
| Is AirGuard an official CPCB forecast? | No. It is an AirGuard CPCB-style forecast using a declared aggregation convention. |
| Why use the maximum pollutant sub-index? | The central implementation follows the selected index methodology; it is not a sum of disease risks. |
| Why require three pollutants including PM? | It is the declared engine minimum; otherwise the index is insufficient rather than a fabricated value. |
| Why CO and ozone use eight-hour windows? | The shared engine applies complete trailing windows; high ozone also needs its declared one-hour treatment. |
| Is AQI 401 an exact Severe observation? | No. It represents a lower bound when the open-ended band prevents identifying the true index. |
| Why not convert every ppb station gas? | Reliable conversion needs atmospheric conditions and trustworthy unit semantics; those station labels are not assumed valid. |
| What did the 134-byte probe prove? | It decoded as nine PM2.5 grid values with forecast type, run, lead and valid time; size alone is not validity. |
| Why is archived forecast different from reanalysis? | A forecast is tied to an initialisation and future leads; reanalysis can use later observations. |
| How do you prove forecast timing? | Decode init, lead and valid time and check valid equals init plus lead; retain request and raw checksum. |
| Why not download the whole globe? | The frozen station envelope and required dates/parameters/leads are sufficient and cheaper to audit. |


## Software architect

Strongest criticism: Provider/database coupling creates availability bottlenecks.

Strongest positive point: Bounded orchestration, shared cache and explicit failure states.

Project risk: Cold misses and queues can dominate latency.

| Question | Recommended concise answer |
| --- | --- |
| Why separate live and research paths? | Production availability and scientific issue-time validation have different provenance and release requirements. |
| Where is AQI calculated? | The shared Python engine supplies targets, forecasts and scenario calculations under one version. |
| What if cache serves the wrong day? | IST-aware expiry and browser rollover tests prevent stale target-day reuse. |
| Why bounded concurrent provider work? | It limits latency and quotas while permitting independent source failures to be reported. |
| Does caching improve scientific accuracy? | No. It improves availability/cost and must preserve freshness/source identity. |
| Can experimental code silently replace live forecast? | No automatic promotion occurs; production release is a separate approval and verification step. |
| What happens if all APIs fail? | No substitute AQI is invented; the API returns unavailable and the UI shows it. |
| How are invalid inputs handled? | Allowlisted parameters, finite service-region coordinates and bounded labels are checked before provider calls. |
| Do retries bypass limits? | No; each transport attempt consumes shared quotas and uses bounded retry logic. |
| Can user input choose an outbound URL? | No. Adapters use fixed provider endpoints rather than arbitrary hosts. |


## Data engineer

Strongest criticism: QC and current-catalogue survivorship do not establish instrument truth.

Strongest positive point: Immutable raw hashes and retained rejection ledgers.

Project risk: Unexpected schema/unit drift.

| Question | Recommended concise answer |
| --- | --- |
| Is this synthetic data? | Targets are real station measurements; CAMS/weather are model output. Synthetic fault fixtures are tests only. |
| What is actually measured? | Pollutant concentrations at instruments distributed by OpenAQ with upstream provider identity. |
| What is modelled? | CAMS atmospheric fields and weather forecasts; derived AQI is index arithmetic, not a new measurement. |
| How large is the measured study? | The current verified artifact lists 107,280 rows, 64,799 valid targets and 179 usable stations in 100 parsed cities. |
| Why should we trust the datasets? | Hashes, provenance, locked QC and reconstruction support auditing; they cannot prove every instrument is accurate. |
| Can you call all 481 stations training data? | No. That is the eligible catalogue; the frozen sample and acquired/usable cohorts are smaller. |
| Does OpenAQ operate these monitors? | It distributes upstream measurements; provider/owner and sensor identities must be retained. |
| What if OpenAQ lists a retired sensor first? | Rank evidenced sensor dates and coverage, not list order or larger sensor ID. |
| Can old readings be used as fresh current data? | No; contributing pollutant age and coverage determine eligibility/freshness. |
| How do you handle failed station downloads? | Resume checksummed completed work; retain unavailable station records and the upstream failure. |


## Research reviewer

Strongest criticism: Novelty acceptance and primary reproduction remain incomplete.

Strongest positive point: Preregistered splits, final seal and disclosed negative results.

Project risk: Any post-outcome change would contaminate inference.

| Question | Recommended concise answer |
| --- | --- |
| How do you prove there is no leakage? | Timestamp guards, chronological/global-date partitions, train-only preprocessing and final isolation provide evidence, not an absolute universal proof. |
| Why not random date splits? | They mix future/past regimes and can leak lagged or repeated station information. |
| Can future station selection leak? | Yes; training-only eligibility and frozen catalogue membership prevent outcome-based final selection. |
| Can scaling on all data leak? | Yes. Fit scaler and imputer only on each training partition. |
| Can calibration see test labels? | No. Calibration and policy selection use their own preceding window. |
| What would invalidate your research? | Final-test tuning, fabricated archive provenance, outcome-driven QC or broken target/availability semantics. |
| Why expanding windows? | They reproduce accumulating historical information under the locked date geometry. |
| Why an embargo? | It separates adjacent partitions and reduces boundary contamination; it is not a cure for every dependency. |
| Do all stations move together by date? | Yes. A global date belongs to one role, preventing cross-station future-date leakage. |
| What if the first fold lacks 120 training days? | Report insufficient eligibility; do not weaken the primary threshold after observing results. |


## Hackathon judge

Strongest criticism: A useful demo is not proof of measured benefit.

Strongest positive point: A coherent source-labelled location-to-advisory workflow.

Project risk: Live provider failure during presentation.

| Question | Recommended concise answer |
| --- | --- |
| Why forecast rather than show current AQI? | Tomorrow’s information supports planning; it is useful only with validated provenance and honest uncertainty. |
| Who needs this most? | People planning outdoor exposure, especially those with fewer flexible options; benefit has not been measured. |
| What problem can you actually prove? | Fragmented source, forecast and quality information; our code integrates them with explicit limitations. |
| What would falsify the project’s value? | Poor warnings, misunderstood precision or no useful action in user studies would weaken its case. |
| Does everyone need another AQI app? | No; existing apps are useful. We must demonstrate clearer trustworthy decisions, not assume demand. |
| What is the biggest current weakness? | The primary CAMS experiment is unfinished and strict preliminary Severe forecasts all under-warned. |
| What if geolocation is denied? | Manual place or coordinate search remains available. |
| What if JSON is malformed? | The response contract fails before caching/rendering, showing an error rather than fabricated values. |
| What if search results have invalid coordinates? | Filter them with the same service-region check and reject malformed result arrays. |
| Can old requests overwrite a newly selected place? | Cancellation/state guards and regression tests protect against that race. |


## Public-health reviewer

Strongest criticism: Strict preliminary Severe under-warning defeats reassurance claims.

Strongest positive point: Censoring, warning-cost analysis and no clinical claims.

Project risk: False reassurance to users with limited choices.

| Question | Recommended concise answer |
| --- | --- |
| Why exclude Severe from exact regression fitting? | The true value is unidentified above the lower bound; training on a fabricated exact 401 biases the model. |
| How do you score Severe? | Category/exceedance detection, share below 401 and lower-bound shortfall. |
| What negative result did you get? | All strict preliminary baseline forecasts on 363 censored Severe validation days fell below 401. |
| Can an interval reaching 401 prove Severe coverage? | No. It is compatibility with a lower bound, not coverage of the unknown true upper value. |
| Can you repair Severe performance after final test? | Not in that evaluation; any change requires a future version and fresh held-out evidence. |
| Is Severe rarity an excuse? | No. Report sample size and failures prominently, even when learning extremes is difficult. |
| Is the health advisory medically validated? | No. It is environmental exposure guidance with no clinical outcome calibration. |
| Does vulnerability mean personal disease risk? | No. Cohorts are communication/exposure strata, not diagnoses. |
| How is under-warning defined? | Issued category lower than the observed category; serious under-warning is at least two categories below. |
| Why measure over-warning? | Unnecessary restrictions and alert fatigue are real trade-offs, even for cautious policies. |


## Investor

Strongest criticism: Demand, commercial licences and capacity are unproven.

Strongest positive point: Auditable implementation and potential institutional planning use.

Project risk: Provider costs and weak differentiation.

| Question | Recommended concise answer |
| --- | --- |
| Is everything free? | No. Free tiers have quotas/terms, and commercial licences/support/hosting can require payment. |
| What is the biggest research cost? | Archive latency/storage and repeated development fitting, separate from user-serving inference. |
| Can you quote production cost exactly? | Not without measured traffic, retention, licences and current provider quotes. |
| Does one user require new provider calls? | A validated shared grid/cache hit can avoid them; cache freshness still matters. |
| Could API quota kill a demo? | Yes; use bounded cached locations and an honest backup, not evasion or fake success. |
| Why not promise zero-cost national deployment? | Licensing, infrastructure, monitoring and support scale beyond a prototype. |
| What happens with ten users? | Shared cache/leases reduce redundant work, but cold misses and upstream availability still matter. |
| What about ten thousand users? | Batch popular grids, measure contention, licence APIs and capacity-test queues/cache/database. |
| What about one million users? | The prototype has no such load evidence; require a redesigned capacity plan and empirical tests. |
| Why batch by grid? | Many nearby users share the same atmospheric cell and forecast run. |


## Cybersecurity reviewer

Strongest criticism: A scoped secret scan is not penetration certification.

Strongest positive point: Server secret separation, authorisation and safe failure paths.

Project risk: Location retention and privileged credential misuse.

| Question | Recommended concise answer |
| --- | --- |
| What happens if all APIs fail? | No substitute AQI is invented; the API returns unavailable and the UI shows it. |
| How are invalid inputs handled? | Allowlisted parameters, finite service-region coordinates and bounded labels are checked before provider calls. |
| Do retries bypass limits? | No; each transport attempt consumes shared quotas and uses bounded retry logic. |
| Can user input choose an outbound URL? | No. Adapters use fixed provider endpoints rather than arbitrary hosts. |
| Why HTTP 202? | It represents queued provider work, not a completed forecast. |
| Do errors reveal database credentials? | Public errors are generic and logs should retain safe classes/redacted diagnostics only. |
| What do you store? | Environmental records, caches, quotas, snapshots, forecast artifacts and verification pairs; no diagnosis is required. |
| Does RLS make service-role endpoints safe? | Not by itself; privileged server credentials still require operation authorisation and input validation. |
| Why immutable forecasts? | Verification must compare a forecast actually issued before the outcome, not a rewritten prediction. |
| How do you pair verification? | Use issue/target/location/station/method identity and retain provenance; never bind stations after seeing outcomes. |


## Ordinary user

Strongest criticism: Source/status distinctions may still be misunderstood.

Strongest positive point: Manual location search and explicit missing/stale states.

Project risk: Mistaking a grid estimate or lower-exposure period for safety.

| Question | Recommended concise answer |
| --- | --- |
| What if geolocation is denied? | Manual place or coordinate search remains available. |
| What if JSON is malformed? | The response contract fails before caching/rendering, showing an error rather than fabricated values. |
| What if search results have invalid coordinates? | Filter them with the same service-region check and reject malformed result arrays. |
| Can old requests overwrite a newly selected place? | Cancellation/state guards and regression tests protect against that race. |
| Is the browser storing my health diagnosis? | It stores a locally selected advisory cohort, not a diagnosis; location links still reveal selected coordinates. |
| What if charts fail? | Text tables and explicit missing states provide a usable fallback; accessibility is still subject to user testing. |
| What if the forecast interval is huge? | Display uncertainty and limits; do not manufacture confidence or equate width with guaranteed danger. |
| What if a sensor is stuck? | Research QC rejects the locked run and retains its reason; do not claim universal live deployment. |
| What if CAMS acquisition is delayed? | Resume existing IDs and continue independent hardening/documentation; never substitute reanalysis. |
| What if only one provider works? | Display only what its provenance supports and withhold unsupported claims. |


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
