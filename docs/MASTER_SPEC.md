# AirGuard India → National-Level Research System + IEEE Paper
## Master prompt for Codex

> **How to use:** paste this whole file into Codex, or commit it to the repo root as `CODEX_TASK.md` and tell Codex: *"Follow CODEX_TASK.md phase by phase. Start with Phase 0."*
> **Audit basis:** live deployment `https://webapp-phi-taupe.vercel.app` (all routes, its public API and static JSON), audited on 11 Oct 2026 IST. The GitHub repo `nishaids/airguard-india` was private, so code-level claims below are inferred from runtime behaviour and must be confirmed in Phase 0.

---

## 0. ROLE, MISSION, GROUND RULES

**You are** a senior research engineer (air-quality forecasting, ML evaluation, full-stack Next.js + Python + Supabase on Vercel) and a co-author helping three B.Tech AI&DS students at Rajalakshmi Engineering College, Chennai, turn **AirGuard India** into:

1. a **national-level, station-validated** next-day air-quality forecasting and health-advisory platform;
2. a **reproducible evidence package** (data, code, protocol, results JSON, figures);
3. a **6-page IEEE conference paper** (double column) and a separate **Medium article**.

**Non-negotiable rules**

1. **No fabricated numbers.** Every number in the UI, paper, or article is produced by a committed script from versioned data and written to `results/*.json`. The paper pulls tables from generated `.tex` files; never type a result by hand.
2. **No fabricated references.** Every BibTeX entry must resolve via DOI (Crossref) or an official URL. Items tagged `[VERIFY]` in Part G must be checked; drop anything you cannot verify.
3. **Keep the project's honesty features.** Measured vs modelled labels, readiness gates, "claims not supported" lists, and the prospective ledger stay. Never mark a readiness gate as passed without the evidence artefact that proves it.
4. **Issue-time discipline.** No feature may use information that was not available at 20:00 IST on the issue day. Reanalysis (ERA5, CAMS reanalysis) is allowed only for retrospective analyses (deweathering), never as a forecast input.
5. **Do not break production.** Feature branches, small PRs, preview deploys, reversible migrations, tests green before merge.
6. **Secrets** never in code, logs, static JSON, or the client bundle.
7. **Never bypass CAPTCHAs, logins, or terms of service** to collect data. If a source needs a credential or manual download, write it to `HUMAN_ACTIONS.md` and continue with what you can do.
8. **Attribution is not causation.** SHAP, clustering, and Mann–Whitney results are descriptive. Do not write causal or clinical claims.

**First actions (Phase 0)**
- Read the whole repo. Write `docs/AUDIT_CONFIRMATION.md`: for each limitation L01–L52 in Part B, mark CONFIRMED / REFUTED / PARTLY, with file paths and line numbers.
- Write `PLAN.md` (phases, PR list, risks) and `HUMAN_ACTIONS.md` (seed it from Part I).
- Do not start Phase 1 until both files exist.

---

## PART A — WHAT EXISTS TODAY (audited)

**Identity (from `/data/meta.json`):** *"AirGuard India — A Vulnerability-Weighted Health Advisory Index and Next-Day Air Quality Forecasting System for Indian Cities"*, AD23532 Principles of Data Science, REC, Sem V, 2026-27. Team list contains Nishanth Rajendran plus two entries whose names are the literal placeholder `<NAME>`.

**Stack (inferred):** Next.js (Turbopack build) on Vercel; Python serverless API routes; Supabase (storage + scheduled jobs named `airguard-research-issue` `30 14 * * *` UTC, `airguard-research-prefetch` `20 14 * * *`, `airguard-research-verify` `30 1 * * *`); static research JSON under `/data/*.json`; a separate Streamlit deployment of the legacy app.

**Routes**

| Route | What it does |
|---|---|
| `/`, `/live`, `/city-atlas` | Search a place → current AQI + tomorrow's AQI from CAMS global (Open-Meteo, 0.4°), CPCB-style engine `airguard-cpcb-2014-v1`, hourly chart, pollutant table, cohort guidance, weather + NASA FIRMS context, "lower-exposure window". `/city-atlas` adds the historical City Risk Atlas (archetypes, ranked risk, seasonality, Diwali, COVID lockdown). |
| `/research` | Research questions, locked protocol `airguard-dayahead-20ist-v1`, 17 readiness gates (3 passed). |
| `/research/track-record` | Fixed 20:00 IST prospective ledger: **0 forecasts, 0 outcomes**. |
| `/research/legacy` | 2015–2020 Kaggle research summary + live ingestion status. |
| `/forecast` | Historical next-day replay for 12 cities × 7 cohorts with HAI and what-if sliders. |
| `/policy-simulator` | Proportional concentration reductions → re-scored AQI/HAI (arithmetic, no chemistry). |
| `/model-insights` | Regression/classification/clustering tables, leakage demo, imputation study, SHAP, model cards. |
| `/methods` | Methodology, timing, resolution, licensing, research separation. |

**APIs:** `GET /api/air-quality/summary?lat&lon&name&region` (returns current, tomorrow, 30-h hourly forecast, measured_context, weather_context, fire_context, provenance, data_quality, track_record) and `GET /api/research/status`.

**Legacy research numbers (Kaggle "Air Quality Data in India (2015–2020)", CPCB origin, CC0, 29,531 city-days, 26 cities in source, 12 used):**
- Regression (next-day AQI), test: LightGBM MAE 15.10, RMSE 23.50, R² 0.912; Linear Regression MAE 15.91; Persistence MAE 18.91. CV MAE ≈ 28.5–32.0.
- Classification (next-day band), test macro-F1: XGBoost+SMOTE 0.741 (CV 0.571); Persistence 0.680; deployed LightGBM+SMOTE 0.7145.
- Clustering: 12 cities, k=2, silhouette 0.355, DB 1.046, CH 7.27; K-Means = Ward (ARI 1.0).
- HAI: 7 cohorts, hand-set vulnerability factors, co-exposure λ = 0.25; "66.9% of city-days at least one cohort differs from AQI band".
- AQI reconstruction audit vs supplied AQI: MAE 24.8, r 0.923, exact bucket agreement 67.7%.
- Diwali: national uplift +72.9%, 9/12 cities significant. Lockdown: −34.0% national mean, 12/12 significant.

---

## PART B — COMPLETE LIMITATIONS AUDIT

Severity: **C** = blocks a credible paper, **H** = high, **M** = medium, **L** = low. "→ WPn" = where it is fixed.

### B1. Data and measurement
| ID | Sev | Limitation | Evidence from audit | Fix |
|---|---|---|---|---|
| L01 | C | **No CPCB CAAQMS station data reaches the live system.** The "measured" path depends on OpenAQ, which returned only US-embassy AirNow (PM2.5-only) and AirGradient low-cost sensors in the places tested. | Avadi → nearest station "Chennai" (AirNow, PM2.5 only, 18.5 km, DELAYED) → INSUFFICIENT_DATA. Delhi → AirGradient + AirNow (STALE), PM2.5 only → INSUFFICIENT_DATA. India has 565 CAAQMS (2025). | WP1 |
| L02 | C | **CPCB/data.gov.in ingestion is failing.** | `/research/legacy`: "CPCB/data.gov.in FAILED · 0 stored". The data.gov.in real-time AQI resource page states its API does not exist. | WP1 |
| L03 | H | **Stale observations.** | OpenAQ: 9 usable current readings, 971 latest readings older than 24 h. | WP1 |
| L04 | C | **No archived CAMS forecasts**, so no honest backtest of the live forecaster exists. | `/research`: "PENDING — ADS credential/terms required". | WP1, Part I |
| L05 | H | **Research dataset is old and narrow.** Ends 1 Jul 2020; city-level daily averages (not stations); only 12 of 26 cities used. | `/data/meta.json` date bounds; legacy page. | WP1, WP5 |
| L06 | H | **Supplied vs recomputed AQI disagree** (MAE 24.8; exact bucket agreement 67.7%), worst on CO/O3-dominated days, because city_day lacks 8-h maxima. | `hai_divergence.json` → `aqi_recomputation_audit`. | WP1 (station hourly data removes this) |
| L07 | M | **NH3 and Pb never available from CAMS**, so live AQI uses 6 of 8 CPCB pollutants. Disclosed, but can understate AQI where NH3 matters (agricultural belts). | API `missing_CAMS_pollutants`. | WP1 (station NH3), paper limitation |
| L08 | M | **No data QA/QC layer is visible for station data** (flat-lines, spikes, PM2.5 > PM10, unit errors). CPCB real-time data is not quality-checked at source. | CEEW 2021 on CPCB QA/QC; no QA flags in API. | WP1 |
| L09 | M | **Weather inputs are not archived as issued.** Weather comes from Open-Meteo `gfs_seamless` at request time; no historical issued-weather store for training. | API `weather_context`. | WP1 |
| L10 | L | **Fire context is shown but unused** (correctly), and no smoke-transport feature exists. | API `fire_context` "no AQI adjustment". | WP2 ablation F |

### B2. Forecast science and accuracy
| ID | Sev | Limitation | Evidence | Fix |
|---|---|---|---|---|
| L11 | C | **Live forecast is raw CAMS, uncorrected and unvalidated.** | `correction_status: NOT_VALIDATED`, `corrected_aqi: null`, `prediction_interval: null`, `track_record: []`. | WP2 |
| L12 | C | **Likely CAMS ozone over-prediction drives the headline AQI.** O3 is the dominant pollutant in Avadi (135/141) and in Delhi's tomorrow (239) in October, when PM usually dominates (confirm against CPCB daily bulletins for the same dates in Phase 0). Literature reports CAMS O3 high bias vs OpenAQ stations and ~35% O3 over-estimation by regional models over India (NOx titration). | API outputs; Pérez et al. EGU22; Pommier et al. 2018. | WP2 (per-pollutant correction), Fig. 2 |
| L13 | H | **PM2.5 may be under-predicted.** Single sample: Avadi 24-h CAMS PM2.5 26.9 µg/m³ vs nearest measured 36.8 µg/m³ (≈27% low). Anecdotal, but consistent with known under-prediction of operational systems (Delhi AQEWS ~30–35% per CEEW, 2025). | API current vs measured_context. | WP2 |
| L14 | H | **0.4° (~45 km) grid** cannot resolve neighbourhoods; one cell spans Avadi and central Chennai. | `/methods`. | WP2 (station-level MOS), WP7 (show grid honestly) |
| L15 | H | **Upstream model run time not recorded**; "issued_at" is retrieval time. Lead time is therefore unknown in the ledger. | API `provider_issued_at: null`. | WP1 (ADS archive gives run time) |
| L16 | C | **Legacy CV is not chronological.** CV MAE ≈ 30 vs test MAE ≈ 15; CV macro-F1 0.571 vs test 0.741. The site itself warns folds were city-ordered. `TimeSeriesSplit` on a city-stacked panel splits by city, not time. | `/research/legacy` banner; `/model-insights`. | WP2 (date-blocked CV) |
| L17 | H | **ML barely beats linear.** Linear Regression MAE 15.91 vs LightGBM 15.10 (≈5%). Persistence 18.91. A reviewer will ask why boosting is needed. | `/model-insights`. | WP2 (state honestly; use as baseline ladder) |
| L18 | M | **"Within 1 band" ≈ 99% is uninformative** (persistence scores 99.41%). | `/model-insights`. | WP2 (replace with POD/FAR/CSI for Poor+) |
| L19 | H | **Uncalibrated class probabilities.** Replay shows "model score 99%". SMOTE distorts probabilities; SMOTE on time-ordered data creates synthetic days that never existed. | `/forecast`. | WP3 |
| L20 | M | **Deployed model ≠ reported best model** (LightGBM+SMOTE 0.7145 vs XGBoost+SMOTE 0.7411) because of the Vercel 250 MB function limit. Two apps (Streamlit and Vercel) serve different models. | `/model-insights` note. | WP6 (move inference to the scheduled job) |
| L21 | M | **Replay shows "Regression: unknown"** — model provenance missing in UI. | `/forecast` footer. | WP6/WP7 |
| L22 | H | **No severity-stratified skill** (Severe days are censored at ≥401 and excluded from regression metrics; no POD/CSI for Very Poor+). | `/methods`, `/research`. | WP2 |
| L23 | M | **No significance testing between models** (no Diebold–Mariano, no bootstrap CIs). | `/model-insights`. | WP2 |

### B3. Health Advisory Index (the main novelty claim)
| ID | Sev | Limitation | Evidence | Fix |
|---|---|---|---|---|
| L24 | C | **Vulnerability factors are hand-set**, not derived from concentration–response evidence (e.g., children NO2 1.55, asthma SO2 1.75, cardiac PM2.5 1.70, λ = 0.25). | `hai_divergence.json`. | WP4 |
| L25 | C | **The headline "66.9% of city-days differ" is partly circular**: it follows from the chosen factors and from the aggregation change itself (healthy-adult reference already differs on 25.95% of days with all factors = 1). | `aggregation_effect`. | WP4 (sensitivity analysis) |
| L26 | H | **Prior work overlaps**: a city-specific AQHI for Delhi and Varanasi built from Indian mortality time series (George et al., ERL 2025) and Canada's AQHI (Stieb et al., 2008). Novelty must be re-scoped (cohort + forecast + uncertainty), not "first health-weighted index". | Literature. | Part C, WP4 |
| L27 | H | **No validation against any health outcome** (hospital admissions, mortality) — the index cannot claim it protects health. | — | WP4 (state as advisory heuristic; optional outcome check if data access exists) |
| L28 | M | **Cohort rules are deterministic**; no individual risk, and live guidance uses only general text per cohort. | `/methods`. | WP7 copy, paper limitation |

### B4. Historical analyses (City Risk Atlas)
| ID | Sev | Limitation | Evidence | Fix |
|---|---|---|---|---|
| L29 | H | **Clustering on 12 points.** Silhouette 0.355; indices disagree (DB and elbow vote k=4). The 9-vs-3 split mirrors burden level (north vs rest) although the method claims "shape not magnitude". | `evaluation_clustering.json`. | WP5 |
| L30 | H | **Policy levers asserted without source apportionment.** Chennai and Thiruvananthapuram labelled "vehicular NOx led" from a +0.128 shape score. | Atlas text. | WP5 |
| L31 | H | **Diwali and lockdown effects are not meteorologically normalised.** Lockdown (Mar–May) and Diwali (post-monsoon stagnation, stubble fires) both coincide with seasonal weather shifts. | Atlas methods. | WP5 (RF deweathering) |
| L32 | M | **No multiple-testing correction** (12 Mann–Whitney tests per panel). | Atlas. | WP5 (Holm) |
| L33 | M | **Anomalies unexplained**: Amaravati Diwali −39%. | Atlas. | WP5 (check coverage) |
| L34 | M | **Two inconsistent "clean window" methods**: historical uses instantaneous concentrations, 2-h window; live uses rolling CPCB AQI, 3-h window — the method the historical module explicitly rejected. | `safe_windows.json` vs API. | WP5, WP7 |
| L35 | H | **Live "lower-exposure window" recommends 04:00–07:00 IST** for Avadi, when forecast boundary-layer height is 35–110 m (near the day's minimum; it reaches ~2,000 m by midday). The dip comes largely from rolling-average lag and night-time CAMS O3, not demonstrably cleaner air — near-surface PM typically peaks under such shallow mixing. | API `lower_exposure_window` + `weather_context`. | WP5, WP7 |
| L36 | L | **Policy simulator reduces pollutants independently** (no chemistry; disclosed). | `/policy-simulator`. | Paper: exclude or keep as demo only |

### B5. Evidence and research readiness
| ID | Sev | Limitation | Evidence | Fix |
|---|---|---|---|---|
| L37 | C | **Readiness 3/17 gates.** Pending: literature review, issue-time dataset, baselines, rolling-origin, spatial validation, ablation, uncertainty, extreme events, advisory evaluation, prospective logging, 30-day record, statistics, reproducibility, security. | `/api/research/status`. | WP2–WP6, Part H |
| L38 | C | **Fixed-time scheduled issuance has produced 0 forecasts** although schedules show "active"; `prospective_logging_active: false`. | `/research/track-record`. | WP6 |
| L39 | M | **On-demand ledger has duplicates** for near-identical coordinates (e.g., Coimbatore 11.0168,76.9558 and 11.0055,76.9661; Kolkata, Hyderabad, Kochi pairs; 23.40,70.40 issued 3×). | `/api/research/status` → `on_demand_forecasts`. | WP6 |

### B6. Server, performance, security
| ID | Sev | Limitation | Evidence | Fix |
|---|---|---|---|---|
| L40 | C | **Very slow first load.** Summary API took 14.5 s (Avadi) and 18.6 s (Delhi); the first request was aborted; `/live` still showed "Loading…" after 10 s. | Network timing. | WP6 |
| L41 | H | **Local machine path leaked in public JSON**: `D:\PODS Project\airguard-india\data\raw\city_hour.csv`. | `/data/safe_windows.json`. | WP6 |
| L42 | M | **"Data and model cards" tab froze the page in testing** (>30 s unresponsive; reproduce in Phase 0); `/research` showed "Loading the research evidence…" for >8 s. | Browser test. | WP7 |
| L43 | M | **Text-encoding bugs**: "Open the forecast â†’", "Â·". | `/research/legacy`. | WP7 |
| L44 | M | **Licensing for scale**: Open-Meteo's free hosted API is non-commercial with quotas; OpenAQ licences vary by provider. | `/methods`. | WP6, Part I |
| L45 | M | **No visible rate limiting, input validation, monitoring, or uptime alerting.** | Runtime only; confirm in code. | WP6 |

### B7. UI, UX, accessibility
| ID | Sev | Limitation | Evidence | Fix |
|---|---|---|---|---|
| L46 | H | **The "Atlas" has no map.** No map container (Leaflet/MapLibre/canvas/iframe) on `/city-atlas` or `/live`; the "atlas" is cards, tables and bar charts. | DOM check. | WP7 |
| L47 | H | **Mobile layout breaks** at 375 px: 6 of 8 nav links and data tables overflow horizontally. | Viewport test. | WP7 |
| L48 | M | **English only**; Hindi and Tamil "await review". | Footer. | WP7 |
| L49 | M | **No alerts or notifications**, no PWA manifest, no OpenGraph tags (links share badly). | DOM check. | WP7 |
| L50 | M | **Uncertainty is invisible to users** (only a daily min–max range labelled "not a confidence interval"). | Live card. | WP3, WP7 |

### B8. People impact and paper readiness
| ID | Sev | Limitation | Evidence | Fix |
|---|---|---|---|---|
| L51 | H | **No measured user or population impact** (no usage study, no population-exposure estimate, no stakeholder pilot). Human-subject work needs an ethics statement under IEEE policy. | — | WP8 |
| L52 | C | **Paper blockers**: Kaggle 2015–2020 AQI prediction is a saturated topic; author placeholders; AI-use disclosure needed in Acknowledgment; 6-page limit forces focus. | `meta.json`; IEEE policy. | Part C, Part E |

---

## PART C — TARGET RESEARCH CONTRIBUTION

**Re-scoped research question (the paper's spine):**
> *Can a lightweight, station-calibrated post-processing of the CAMS global forecast, issued under a strict 20:00 IST protocol, deliver next-day AQI forecasts with calibrated uncertainty across Indian CPCB stations, and can those calibrated forecasts drive cohort-specific advisories that reduce under-warning for vulnerable groups at a measured over-warning cost?*

**Hypotheses (pre-register in `docs/PROTOCOL.md` before looking at test data):**
- H1: Station MOS correction lowers next-day AQI MAE vs raw CAMS and vs persistence on held-out dates **and** held-out cities (Diebold–Mariano, Holm-corrected).
- H2: Raw CAMS has systematic, region- and season-dependent bias over India (expected: O3 high, PM2.5 low in winter IGP); correction removes most of it.
- H3: Adaptive conformal intervals reach nominal 80%/90% coverage within ±3 points across seasons and severity regimes.
- H4: A calibrated cohort-warning policy achieves under-warning ≤ 5% for vulnerable cohorts and ≤ 10% for general adults on the locked test set, and the paper reports the over-warning cost.

**Contributions (claim only those the results support):**
- **C1. Nationwide station-calibrated CAMS correction** under an issue-time protocol, evaluated on temporal and spatial holdouts across ≥100 CPCB stations; plus a first-of-its-kind (verify) bias atlas of CAMS O3/PM2.5 over Indian stations by region and season.
- **C2. Uncertainty-aware advisories:** conformal intervals propagated exactly to AQI (the CPCB AQI is monotone non-decreasing in every concentration, so AQI bounds = AQI computed at concentration bounds), and a cost-sensitive cohort-warning rule.
- **C3. Evidence-grounded cohort Health Advisory Index (HAI v2):** factors derived from published concentration–response coefficients with sensitivity analysis — positioned against the CPCB AQI and AQHI-style indices (Stieb 2008; George et al. 2025).
- **C4. Open, provenance-preserving system** with a prospective, append-only forecast ledger and public readiness gates.

**Novelty gap (Table I in the paper; verify every cell):**

| System / study | Coverage | Forecast? | Station-calibrated? | Uncertainty? | Cohort advisories? | Open + prospective ledger? |
|---|---|---|---|---|---|---|
| CPCB AQI / SAMEER | National | No (observed) | — | No | No | Data only |
| Delhi AQEWS (Jena et al. 2021) | Delhi | Yes (WRF-Chem) | Assimilation | No | No | No |
| George et al. 2025 AQHI | Delhi, Varanasi | No | — | No | City-level | No |
| Stieb et al. 2008 AQHI | Canada | No | — | No | Population | — |
| CAMS global | Global | Yes | No | No | No | Archive |
| **AirGuard (target)** | **National, CPCB stations** | **Yes** | **Yes** | **Yes (conformal)** | **Yes (7 cohorts)** | **Yes** |

**Legacy Kaggle work:** keep as a short "historical baseline and leakage lesson" subsection or move to the Medium article. It is not the paper's headline.

**Title candidates (pick after results):**
1. *AirGuard-India: Station-Calibrated, Uncertainty-Aware Next-Day Air-Quality Forecasts with Cohort-Specific Health Advisories*
2. *Correcting CAMS for India: Issue-Time Station Calibration and Conformal Health Advisories at National Scale*
3. *From Grid to Guidance: Calibrated Day-Ahead AQI and Vulnerable-Group Warnings for Indian Cities*

---

## PART D — WORK PACKAGES (do in order; one PR per bullet group)

### WP0 — Repo audit and scaffolding
- `docs/AUDIT_CONFIRMATION.md`, `PLAN.md`, `HUMAN_ACTIONS.md` (see Phase 0).
- Add `Makefile` targets: `data`, `features`, `backtest`, `results`, `figures`, `paper`, `test`.
- Pin dependencies; add `CITATION.cff`, `LICENSE` check (code MIT; data licences per source).
- **Accept when:** `make test` runs; the audit file covers L01–L52.

### WP1 — Data layer (fixes L01–L09, L15)
1. **Station universe:** CPCB CAAQMS metadata (id, name, lat/lon, city, state, agency, commissioning date). Store in Supabase `stations`.
2. **Historical station data (hourly, 2019-01-01 → present):** priority (a) CPCB CCR portal exports (manual/assisted download if required — no CAPTCHA bypass; log to `HUMAN_ACTIONS.md`); (b) OpenAQ v3 archive where present; (c) WAQI API only for real-time verification, subject to its terms. Keep `source`, `licence`, `retrieved_at` on every row.
3. **Real-time ingestion:** replace the failing data.gov.in path. Implement provider adapters with retries, backoff, health table `ingestion_runs(provider, started_at, status, rows, error)`.
4. **QA/QC module** `src/qa/` (flags, never silent deletion): negative/zero, flat-line ≥ 6 h, rolling-MAD spikes (z > 6) with event-window exemption (Diwali, fire days), PM2.5 > PM10, unit sanity (CO mg/m³ vs µg/m³), completeness ≥ 16 h/day per pollutant (CPCB rule). Output `results/qa_summary.json` (counts per flag, per station).
5. **Archived CAMS forecasts** from the Copernicus Atmosphere Data Store dataset *"CAMS global atmospheric composition forecasts"* (0.4°, 2015→present, two runs/day, hourly to 120 h) via `cdsapi` with the ADS key as a secret. Determine empirically which run is available by 20:00 IST (expected: the 00 UTC run of the issue date → target-day leads ≈ 18.5–42.5 h). Record `run_init_utc` and `lead_h` on every row (fixes L15).
6. **Issued weather:** Open-Meteo Historical Forecast API (archived forecasts; verify start date and variable coverage for India, incl. boundary-layer height) for training; ERA5 only for retrospective deweathering (WP5).
7. **Static features:** elevation, coastal distance, urban fraction, population density (WorldPop or GHS-POP), CAMS cell id.
8. **Dataset card** `docs/DATASET_CARD.md` (datasheet style): sources, licences, coverage map, completeness table, QA counts, SHA-256 hashes, known biases (station siting, urban bias).
- **Accept when:** ≥ 100 stations with ≥ 1 year of QA'd daily targets and matching archived CAMS forecasts; `results/data_coverage.json` + coverage figure exist; data.gov.in failure no longer appears on the status page.

### WP2 — Forecasting and accuracy (fixes L11–L18, L22–L23)
1. **Targets:** station daily values per CPCB rules (PM2.5, PM10, NO2, SO2, NH3: IST 24-h mean; CO, O3: max 8-h running mean ending in the day; Severe ≥ 401 censored). Then CPCB-style AQI.
2. **Two strategies, compared:** (i) correct each pollutant, then compute AQI (interpretable, keeps dominant-pollutant logic); (ii) predict AQI directly.
3. **Baseline ladder (same rows for all):** persistence (yesterday measured), climatology (station × day-of-year window), raw CAMS, linear MOS per station, ridge residual correction, LightGBM global MOS (station static features + CAMS + issue-time lags + issued weather + calendar), quantile LightGBM. Add XGBoost only if it adds skill.
4. **Validation:** rolling-origin by **global date** (train ≥ 365 d, calibration 30 d, test 30 d, step 30 d, 1-day embargo) — this replaces the city-ordered folds (L16). **Spatial holdout:** GroupKFold by city and leave-one-region-out (North/IGP, West, South, East, Northeast; coastal vs inland). **Locked final test:** latest 90 days, touched once.
5. **Metrics:** MAE (primary), RMSE, mean bias, R², MAE skill vs persistence and vs raw CAMS; categories: macro-F1, POD / FAR / CSI for Poor+ and Very Poor+, ordinal MAE. Drop "within 1 band" from headlines (L18).
6. **Statistics:** Diebold–Mariano with HAC variance (or moving-block bootstrap CIs) on daily loss differentials; Holm correction; 95% CIs on every headline number.
7. **Stratified results:** by region, season, severity, dominant pollutant, station density, distance to nearest station (for spatial holdout).
8. **Bias atlas:** per-station raw-CAMS bias for O3 and PM2.5 by season → Fig. 2 (tests H2, L12–L13).
9. **Ablations:** feature groups A (CAMS), B (issue-time lags), C (weather), D (calendar), E (location), F (fire) — one at a time.
10. **Explainability:** SHAP on the correction model; text must say attribution ≠ causation.
- **Accept when:** `results/backtest_main.json`, `results/backtest_spatial.json`, `results/ablation.json`, `results/bias_atlas.json` exist and regenerate from `make backtest`; readiness gates *baseline, rolling-origin, spatial, ablation, extreme-event, statistical comparison* flip to passed with artefact links.

### WP3 — Uncertainty and advisory decisions (fixes L19, L50)
1. Per-pollutant prediction intervals: quantile LightGBM + split conformal calibration, updated online with **Adaptive Conformal Inference** (Gibbs & Candès 2021); compare with EnbPI (Xu & Xie 2021).
2. **Exact AQI interval:** AQI_lower = AQI(all concentration lower bounds), AQI_upper = AQI(all upper bounds) — valid because each sub-index is non-decreasing and AQI = max of sub-indices. Prove this in one paragraph of the paper.
3. **Band probabilities:** from quantiles → P(band ≥ Poor). Report reliability diagrams and Brier score. Remove SMOTE from any probability-producing model (L19).
4. **Cohort-warning policy:** warn cohort c if P(AQI ≥ threshold_c) ≥ q_c; pick q_c on the calibration window to keep under-warning ≤ target (5% vulnerable, 10% general) with minimum over-warning; report the trade-off curve. State clearly: empirical control under time dependence, not a guarantee.
5. **Metrics:** coverage@80/90 by regime, mean interval width, pinball loss / CRPS from quantiles, under- and over-warning per cohort.
- **Accept when:** `results/uncertainty.json`, `results/advisory_tradeoff.json`; gates *uncertainty* and *advisory evaluation* pass.

### WP4 — HAI v2: evidence-grounded cohort index (fixes L24–L27)
1. Re-formulate HAI in AQHI style: excess risk ER = Σ_p (exp(β_p · C_p) − 1), with β_p from published short-term concentration–response coefficients — prefer Indian estimates (de Bont et al. 2024 for PM2.5; George et al. 2025 for PM2.5/NO2/O3 in Delhi and Varanasi), else WHO-2021-guideline systematic reviews (`[VERIFY]` Orellano et al. 2020). Map ER to a 0–10 or 0–100 scale with bands anchored to CPCB band boundaries for a healthy adult.
2. Cohort modifiers only where effect-modification evidence exists (age ≥ 65, children, pre-existing respiratory/cardiac disease, pregnancy, outdoor work dose). Each factor in `config/hai_factors.yaml` carries `value`, `ci_low`, `ci_high`, `citation`, `evidence_note`. No evidence → factor = 1, stated.
3. **Sensitivity analysis:** Monte Carlo over coefficient CIs → distribution of "% days a cohort band differs from AQI"; report median and 95% interval (replaces the single 66.9% headline, L25). Separate the pure aggregation effect from the vulnerability effect.
4. Compare HAI v2 with CPCB AQI and with an AQHI-style index on the same days.
5. Optional, only if data access exists: correlate HAI with any public daily hospital/mortality series; otherwise state it as future work.
6. Keep the legacy HAI v1 in `/forecast` labelled "v1 (heuristic, superseded)".
- **Accept when:** `results/hai_v2.json`, `results/hai_sensitivity.json`, factor table with citations auto-exported to `paper/tables/hai_factors.tex`.

### WP5 — Historical analyses done properly (fixes L29–L36)
1. Extend clustering beyond 12 cities (all 26 Kaggle cities passing gates, then CPCB stations 2019+). Use compositional features (centred log-ratio of pollutant shares) + seasonal shape; bootstrap stability (mean Jaccard ≥ 0.75 to report a cluster); consensus clustering. Call results "exploratory archetypes".
2. Remove causal "policy lever" sentences unless backed by a cited source-apportionment study for that city.
3. **Deweather** Diwali and lockdown analyses with random-forest meteorological normalisation (Grange et al. 2018; Shi et al. 2021 approach) using ERA5; then test; Holm-correct across cities; investigate and explain the Amaravati anomaly (coverage near Diwali dates).
4. **One clean-window method everywhere:** instantaneous hourly exposure index, practical-hours filter (default 06:00–21:00 IST, user-adjustable), show boundary-layer caveat when the window falls at the shallowest-BLH hours; same window length live and historical (L34–L35).
5. Policy simulator: keep as a demo; exclude from the paper's claims.
- **Accept when:** `results/clusters_v2.json` with stability, `results/events_deweathered.json`, and the live API's window logic shares code with the historical module.

### WP6 — Server, data platform, reliability, security (fixes L20–L21, L38–L41, L44–L45)
1. **Precompute, don't compute on request:** scheduled job issues forecasts for all CPCB station locations + top Indian towns into `forecasts` table; the API reads cached rows. Split `/summary` into `/current`, `/tomorrow`, `/context`; `Cache-Control: s-maxage=600, stale-while-revalidate=3600`; on-demand path for arbitrary coordinates returns a skeleton immediately and fills asynchronously.
   **Targets:** p95 TTFB ≤ 800 ms cached, ≤ 4 s uncached; measured with k6/autocannon; results in `results/perf.json`.
2. **Fix fixed-time issuance (L38):** diagnose why the 14:30 UTC job produced 0 forecasts (cron engine, function timeout, auth, wrong DB role). Make issuance idempotent with a unique key `(protocol_version, station_id, target_date)`; add a heartbeat table and an alert (email/Telegram) when a run is missed. Start the 30-day prospective record immediately after the fix.
3. **Dedupe locations (L39):** canonical key = CAMS grid cell + bound station; unique constraints; migration to merge duplicates.
4. **Model serving (L20):** run inference inside the scheduled Python job (no 250 MB serverless limit) or export to ONNX/treelite; one model registry entry per release (`model_version`, hash, training data hash); UI shows the exact model version (fixes "Regression: unknown").
5. **Security:** remove local paths from all generated JSON and add a CI grep that fails on `[A-Z]:\\` or `/Users/` (L41); Supabase RLS on every table; service-role key server-only; rate limiting per IP; validate lat/lon ranges and string lengths; CORS allow-list; dependency audit.
6. **Observability:** structured logs, error tracking (free tier), uptime monitor, `/status` page from `ingestion_runs` + heartbeat.
7. **Licensing (L44):** keep deployment non-commercial or fetch CAMS directly from ADS and self-host Open-Meteo for scale; licence table in `docs/LICENSES.md`.
8. **Tests and CI:** unit tests for the CPCB engine against the CPCB report's breakpoints and worked examples; property tests (monotonicity, max-of-sub-indices); API contract tests; Playwright e2e for all routes at 375 px and 1280 px; GitHub Actions on every PR.
- **Accept when:** prospective ledger shows daily fixed-time forecasts; perf targets met; security gate passes; reproducibility gate passes from a clean clone with `make results`.

### WP7 — UI/UX (fixes L34–L35, L42–L43, L46–L50)
1. **Make the Atlas a map:** MapLibre GL + OSM-based tiles (with attribution). Layers: CPCB stations (measured AQI, solid markers), CAMS/corrected grid (hatched to signal "modelled"), toggle *today / tomorrow*, cohort filter, click → station card. Legend states measured vs modelled.
2. **Forecast card:** corrected AQI with 80% interval, band probabilities as a small bar, dominant pollutant, measured/modelled badge, model version, issue time and lead time. Replace "model score 99%" with calibrated probability.
3. **Cohort-first flow:** cohort picker near the top; advisory card shows HAI v2 band + one plain-language action; no medical claims.
4. **Mobile (L47):** bottom tab bar or hamburger nav; tables become card lists < 640 px; Playwright asserts no horizontal overflow.
5. **Fix freezes and loading (L42):** lazy-render/virtualise "Data and model cards"; skeletons + error states with retry on `/research` and `/live`.
6. **Encoding (L43):** fix mojibake at source; enforce UTF-8.
7. **Languages (L48):** Tamil and Hindi with `next-intl`; translations reviewed by a named human; reviewer recorded in `docs/I18N_REVIEW.md`.
8. **Alerts (L49):** opt-in web push / email / Telegram "tomorrow is Poor+ for your cohort". Store only grid cell + cohort + channel token; deletion on request.
9. **Shareability:** PWA manifest, icons, OpenGraph/Twitter cards.
10. **Accessibility:** WCAG 2.2 AA — check AQI colour contrast for text, never colour-only meaning, keyboard navigation, chart text alternatives (already partly present). Lighthouse mobile ≥ 90 for performance and accessibility.
- **Accept when:** screenshots at 375 px and 1280 px for every route in `docs/screens/`; Lighthouse reports in `results/lighthouse/`.

### WP8 — People impact (fixes L51)
1. **Population exposure:** overlay tomorrow's forecast bands with gridded population → number of people in Poor+ areas per day; vulnerable-population estimates from Census age shares (label as estimates).
2. **Advisory value:** per cohort, days where calibrated HAI v2 warns but CPCB AQI does not, with the over-warning cost.
3. **User study (optional, needs ethics approval):** n ≥ 30, within-subject comparison of a CPCB AQI card vs the AirGuard cohort card; measures: comprehension accuracy, intended protective action, SUS score; informed consent; ethics statement in the paper (IEEE requires this for human-subject research). Put the protocol in `docs/USER_STUDY.md`; do not collect names in analytics.
4. **Stakeholder pilot:** share with schools/resident associations; log feedback in `docs/PILOT_LOG.md` (no personal data).
- **Accept when:** `results/population_exposure.json`; if a study was run, `results/user_study.json` + ethics approval reference.

### WP9 — Paper and article artefacts
- `paper/` (IEEEtran conference), `paper/figures/*.pdf` (vector, generated by `src/viz/`), `paper/tables/*.tex` (generated from `results/`), `paper/refs.bib` (verified), `paper/CHECKLIST.md` (Part E rules), `article/medium.md`.
- **Accept when:** `make paper` builds a ≤ 6-page PDF with fonts embedded and no hyperlinks; every number traces to a `results/*.json` key.

---

## PART E — IEEE PAPER BLUEPRINT (≤ 6 pages, double column)

**Format rules (from the call + IEEE):**
- `\documentclass[conference]{IEEEtran}` from the official IEEE conference template; paper size per the conference CFP; 10-pt body.
- **≤ 6 pages total** (assume references count unless the CFP says otherwise).
- **No headers, footers, or page numbers.** Do not add `\pagestyle`, `fancyhdr`, or a copyright footer until camera-ready instructions say so.
- **No embedded links.** Do not load `hyperref` (or load it with `draft`); URLs appear as plain text in references via the `url` package; no clickable DOIs.
- **No scanned images.** All figures are vector PDFs generated from code; fonts embedded (check with `pdffonts`); ≥ 8 pt text in figures; colour-blind safe and legible in greyscale.
- **Author block:** full names, department, "Rajalakshmi Engineering College, Chennai, India", email for each author. Every listed author must meet IEEE authorship criteria (contribution, drafting/revising, approval of final version).
- **Original work only.** Similarity check before submission; do not reuse the Medium article's sentences.
- **AI-use disclosure** in the Acknowledgment: name the AI system(s), the sections where AI-generated content (text, figures, code) was used, and the level of use. Grammar-only editing is exempt but disclosure is recommended; never let an AI tool edit the reference list.
- **Ethics statement** if any human-subject data was collected.
- If the CFP requires it, validate the PDF with IEEE PDF eXpress.

**Section plan and page budget**

| Section | Budget | Content |
|---|---|---|
| Title, authors, abstract (150–200 words), index terms | 0.35 p | Problem → method → key numbers (from results) → impact. |
| I. Introduction | 0.6 p | India's monitoring scale (565 CAAQMS in 2025) vs forecast gap; one-number AQI problem; contributions C1–C4 as a bullet list. |
| II. Related Work | 0.6 p | CPCB AQI; Delhi AQEWS; AQHI (Stieb 2008; George 2025); Indian mortality evidence (de Bont 2024); CAMS biases; ML/DL AQ forecasting in India (incl. CAMS-based DL); conformal prediction. **Table I** (novelty gap). |
| III. Data and Protocol | 0.75 p | Sources, QA, coverage; 20:00 IST issue-time protocol; **Fig. 1** (pipeline + timeline: prefetch 19:50 → freeze 20:00 → target day → verification). |
| IV. Methods | 1.2 p | A. CPCB-style AQI engine (averaging rules, censoring); B. Station MOS correction; C. Conformal intervals + exact AQI interval propagation (short proof); D. Cohort-warning policy; E. HAI v2 formulation. |
| V. Results | 1.6 p | **Table II** main results with 95% CIs and DM tests; **Fig. 2** CAMS bias atlas + correction skill map; **Fig. 3** skill by region × season / severity; **Fig. 4** coverage + reliability + cohort under/over-warning trade-off; **Table III** uncertainty & advisory metrics; one ablation sentence or small table if space. |
| VI. Discussion, Limitations, Ethics | 0.45 p | Grid resolution, station representativeness, unpublished CPCB QA/QC, short prospective record, literature-derived cohort factors ≠ individual risk, not medical advice, licensing. |
| VII. Conclusion | 0.15 p | What holds, what's next (prospective 90-day record, more cohorts, sensors). |
| Acknowledgment | 0.1 p | Data providers + AI disclosure. |
| References | 0.7 p | 25–30 verified entries, IEEE style. |

**Abstract skeleton (fill only from `results/`):**
> India operates {N_CAAQMS} continuous monitors, yet residents receive a same-day, population-average index. We present AirGuard-India, an open system that corrects the CAMS global forecast at {N_stations} CPCB stations under a fixed 20:00 IST issue-time protocol, attaches adaptive conformal intervals, and converts them into cohort-specific advisories. On a locked {N_days}-day test, station correction reduced next-day AQI MAE by {x}% vs raw CAMS and {y}% vs persistence (DM p < {p}); on unseen cities by {z}%. 90% intervals achieved {cov}% coverage. The calibrated warning policy held under-warning for vulnerable cohorts at {uw}% with {ow}% over-warning. Raw CAMS showed {O3_bias} O3 and {PM_bias} PM2.5 bias, strongest in {region/season}.

**Writing rules for Codex:** every claim maps to a figure, table, or citation; hedge where CIs overlap; no "state-of-the-art" or "first" without a verified search; include the negative results (e.g., ML ≈ linear on the legacy data).

---

## PART F — MEDIUM ARTICLE (`article/medium.md`)
- 1,200–1,800 words, plain language, story-led ("Why Avadi's forecast said ozone"), 3–4 re-drawn figures, link to the live app and to the preprint/accepted paper.
- **Timing and originality:** publish after submission with the note "submitted to an IEEE conference", or after acceptance. Write fresh prose — identical sentences will hit the conference's similarity check. Preprints on arXiv/TechRxiv are allowed by IEEE; add the required notice, then the IEEE copyright notice after acceptance.
- Include the same limitations box as the paper and the "not medical advice" line.

---

## PART G — LITERATURE SEED LIST (verify each; add more via search)

Verified during the audit (still confirm DOIs/pages):
1. CPCB, *National Air Quality Index* technical report (2014), `airquality.cpcb.gov.in/ccr_docs/FINAL-REPORT_AQI_.pdf`.
2. D. M. Stieb et al., "A new multipollutant, no-threshold air quality health index based on short-term associations observed in daily time-series analyses," *J. Air Waste Manage. Assoc.*, 58(3):435–450, 2008, doi:10.3155/1047-3289.58.3.435.
3. F. George, P. Joshi, S. Dey, R. K. Mall, "A framework for city-specific air quality health index: a comparative assessment of Delhi and Varanasi, India," *Environ. Res. Lett.*, 20(8), 2025, doi:10.1088/1748-9326/aded26.
4. J. de Bont et al., "Ambient air pollution and daily mortality in ten cities of India: a causal modelling study," *Lancet Planet. Health*, 2024 (ScienceDirect PII S2542519624001141) `[VERIFY volume/pages/DOI]`. Key: +1.4% daily mortality per 10 µg/m³ PM2.5; 3.6% in causal IV analysis; effects below the 60 µg/m³ Indian standard.
5. C. Jena et al., "Performance of high resolution (400 m) PM2.5 forecast over Delhi," *Sci. Rep.*, 11:4104, 2021, doi:10.1038/s41598-021-83467-8.
6. M. Pommier et al., "Impact of regional climate change and future emission scenarios on surface O3 and PM2.5 over India," *Atmos. Chem. Phys.*, 18:103–127, 2018 (O3 overestimated ~35%, attributed to under-estimated NOx titration).
7. A. Pérez, M. Santa Cruz, J. Flemming, M. Razinger, "A deep learning approach to de-bias air quality forecasts, using heterogeneous open data sources as reference," EGU General Assembly 2022, EGU22-1255 (CAMS biases vs OpenAQ: O3 +44.3, PM2.5 +12.7, NO2 −22.8).
8. S. K. Grange, D. C. Carslaw, A. C. Lewis, E. Boleti, C. Hueglin, "Random forest meteorological normalisation models for Swiss PM10 trend analysis," *Atmos. Chem. Phys.*, 18:6223–6239, 2018.
9. Z. Shi et al., "Abrupt but smaller than expected changes in surface air quality attributable to COVID-19 lockdowns," *Sci. Adv.*, 2021, doi:10.1126/sciadv.abd6696.
10. I. Gibbs, E. Candès, "Adaptive conformal inference under distribution shift," *NeurIPS*, 2021.
11. C. Xu, Y. Xie, "Conformal prediction for time series" (EnbPI), arXiv:2010.09107 `[VERIFY ICML 2021 version]`.
12. A. Kushwaha, K. Gopalan, "A comparison of lightweight deep learning models for particulate-matter nowcasting in the Indian subcontinent," arXiv:2511.11185, 2025 (CAMS 0.4° analyses, no ground stations).
13. M. Pandey et al., "Spatio-temporal forecasting of PM2.5 via spatial-diffusion guided encoder-decoder architecture," arXiv:2412.13935, 2024 (Bihar, 511 low-cost sensors).
14. T. Ganguly, L. S. Kurinji, G. Pradhan, "India's air pollution: democratising air quality data," CEEW, 2021 (portal reliability, no API, unpublished QA/QC).
15. CREA, "Tracing the Hazy Air 2026: Progress report on NCAP," Jan 2026 (565 CAAQMS, 1,035 manual stations in 2025).
16. PTI/CEEW, Oct 2025 — Delhi AQEWS under-predicts PM2.5 by ~30–35% due to outdated emission inventories (grey literature; cite carefully or omit).
17. Copernicus ADS, "CAMS global atmospheric composition forecasts" dataset documentation.
18. Vopani (R. Rao), "Air Quality Data in India (2015–2020)," Kaggle, CC0.

From background knowledge — must verify before use:
19. `[VERIFY]` A. Inness et al., "The CAMS reanalysis of atmospheric composition," *ACP*, 19:3515–3556, 2019.
20. `[VERIFY]` P. Orellano et al., short-term PM/NO2/O3 and mortality meta-analysis, *Environ. Int.*, 142:105876, 2020.
21. `[VERIFY]` G. Ke et al., "LightGBM," *NeurIPS*, 2017.
22. `[VERIFY]` S. Lundberg, S.-I. Lee, "A unified approach to interpreting model predictions," *NeurIPS*, 2017.
23. `[VERIFY]` F. X. Diebold, R. S. Mariano, "Comparing predictive accuracy," *J. Bus. Econ. Stat.*, 1995.
24. `[VERIFY]` T. Gneiting, A. E. Raftery, "Strictly proper scoring rules, prediction, and estimation," *JASA*, 2007.
25. `[VERIFY]` WHO Global Air Quality Guidelines, 2021.

Search to fill gaps: Indian city-scale ML AQ forecasting with CPCB stations (2022–2026), CAMS evaluation over India specifically, effect modification of PM2.5 by age/comorbidity in India or South Asia, risk communication of AQI in India.

---

## PART H — DEFINITION OF DONE (maps to the site's 17 readiness gates)

| Gate | Evidence artefact |
|---|---|
| literature_review_complete | `docs/LITERATURE_MATRIX.md` (≥ 25 verified sources, gap table) |
| research_question_locked / protocol_locked | `docs/PROTOCOL.md` hash unchanged since pre-registration |
| issue_time_dataset_validated | `results/issue_time_audit.json` (availability timestamps ≤ cutoff for every feature) |
| cpcb_method_verified | engine unit tests pass |
| baseline_complete | `results/backtest_main.json` with all baselines |
| rolling_origin_complete | date-blocked folds in `results/backtest_main.json` |
| spatial_validation_complete | `results/backtest_spatial.json` |
| ablation_complete | `results/ablation.json` |
| uncertainty_complete | `results/uncertainty.json` |
| extreme_event_analysis_complete | severity-stratified table + CSI for Poor+/Very Poor+ |
| advisory_evaluation_complete | `results/advisory_tradeoff.json` |
| prospective_logging_active | ≥ 7 consecutive fixed-time issuances |
| 30_day_track_record_complete | ≥ 30 valid target days verified (cannot be backdated) |
| statistical_comparison_complete | DM/bootstrap results with Holm correction |
| reproducibility_passed | clean clone → `make results` reproduces hashes |
| security_passed | RLS, secrets scan, path-leak CI, rate limiting verified |

**Paper is submittable when:** WP1–WP4 accepted, WP6 items 1–2 done, Part E checklist green. The 30-day prospective record may be reported as "ongoing" if the deadline comes first — say so explicitly; the archived-forecast backtest carries the main results.

---

## PART I — HUMAN ACTIONS (Codex cannot do these)
1. Give Codex access to the private repo `nishaids/airguard-india`.
2. Create a Copernicus ADS account, accept the CAMS dataset licence, add the API key as a secret.
3. Download CPCB CCR historical station data where the portal needs manual steps or CAPTCHA.
4. Provide teammates' full names, emails, author order, and affiliation wording (replace the `<NAME>` placeholders); confirm all meet IEEE authorship criteria.
5. Choose the target conference; confirm from its CFP: deadline, paper size, whether references count in 6 pages, similarity threshold, PDF eXpress, fees.
6. Obtain institutional ethics approval before any user study.
7. Arrange native reviewers for Tamil and Hindi health text.
8. Decide licensing if anything becomes commercial (Open-Meteo, OpenAQ provider terms).
9. Check Vercel/Supabase plan limits (cron, function duration, DB size).
10. Start the fixed-time prospective ledger as soon as WP6.2 lands — every day of delay is a day missing from the 30-day record.

**Suggested timeline:** Week 1 → WP0, WP1, WP6.1–6.2 · Weeks 2–3 → WP2, WP3 · Week 3 → WP4, WP5 · Week 4 → WP7, WP8 core, WP9 paper draft · prospective ledger runs throughout.
