# Part 1 — Evidence

What exists today, what others have already built, what is genuinely missing, and what the data in hand says about each proposed gap. Nothing in this part is a plan; every statement is either read from the repository, measured on the deployed system, measured in a pilot experiment, or taken from a cited source.

Status vocabulary used throughout the blueprint:

| Tag | Meaning |
| --- | --- |
| **Implemented** | Exists in the repository and the deployment, and has been verified |
| **Partial** | Exists, but falls short of what its description implies |
| **Proposed** | Designed in this blueprint; not built |
| **Future research** | Requires data or validation that is not yet available |

## A. Existing system audit

### A.1 What the system is

| Item | Fact | Source |
| --- | --- | --- |
| Dataset | *Air Quality Data in India (2015–2020)*, CPCB data mirrored on Kaggle, licence CC0, SHA-256 recorded | `data/raw/PROVENANCE.json` |
| Temporal coverage | 2015-01-01 to 2020-07-01. **Nothing after 1 July 2020 exists in the system.** | data card |
| Spatial unit | One value per city per day (mean over that city's stations). No station identity survives. | data card |
| Cities | 26 in the source; **12 retained** by two pre-declared gates (≥ 80% AQI completeness, ≥ 730 labelled days) | data card |
| Rows | 29,531 raw → 18,395 after cleaning | cleaning report |
| Pollutants | PM2.5, PM10, NO, NO2, NOx, NH3, CO, SO2, O3, benzene, toluene, xylene | config |
| Meteorology | **None.** No wind, temperature, humidity, rain or boundary-layer height | data card |
| Features | 178 candidates → 100 (regression) and 102 (classification) after selection: lags, rolling statistics, ratios, calendar terms, sub-indices, a city target encoding | feature report |
| Split | Chronological. Train 10,331 rows to 2019-05-25; test 4,397 rows from 2019-05-26 to 2020-06-30 | evaluation files |
| Regression | Tuned LightGBM, MAE 15.05, RMSE 23.41, R² 0.9125. Persistence baseline MAE 18.90 (−20.1%) | tuning report |
| Classification | Reported best: XGBoost + SMOTE, macro-F1 0.7411 (tuned 0.7452). **Deployed on Vercel: LightGBM + SMOTE, macro-F1 0.7145** | evaluation, deployment report |
| Clustering | K-Means, k = 2 on 12 cities, silhouette 0.355, reproduced by Ward linkage | clustering report |
| Explainability | TreeSHAP, global and one local example, precomputed | explainability report |
| Deployment | Next.js static pages plus two Python serverless functions on Vercel; trees exported to JSON and evaluated without ML libraries | `DEPLOY_VERCEL.md` |

### A.2 Capability audit

| Capability | How it works today | Keep? | Weakness found | Recommended change |
| --- | --- | --- | --- | --- |
| **Provenance and reproducibility** — Implemented | Checksummed acquisition, 20-stage pipeline, every reported number read from JSON | **Keep unchanged** | None material | Extend the same discipline to live data: every measurement carries source, station, timestamps and a quality flag |
| **Event-aware cleaning, causal imputation** — Implemented | Outlier rule exempts festival, stubble and lockdown windows; forward-fill chosen over a better-scoring non-causal method | **Keep** | Forward-fill is applied at city-day level only | Re-apply at station-hour level when station data arrives |
| **Next-day regression** — Implemented | LightGBM on today's pollutants and their history | **Keep as the baseline to beat** | MAE on *Severe* days is 58.8 with a bias of −22.6: the model under-predicts exactly the days that matter. No weather inputs. No interval | Add forecast meteorology; report by band; add calibrated intervals |
| **Next-day band classification** — Partial | Deployed model differs from the reported one | Replace | The deployed classifier is overconfident (see pilot P1). A separate classifier can contradict the regression | Derive the band and its probabilities from one calibrated predictive distribution |
| **Persistence baseline and leakage demonstration** — Implemented | Baseline scored on the same split; same-day leakage shown by experiment | **Keep** | — | Add CAMS as a second baseline: the forecast a user can already get for free |
| **Health Advisory Index** — Partial | `min(100, D + 0.25·C)` over cohort-weighted sub-indices; seven cohorts | Keep the idea, rebuild the index | Weights are hand-set, a fact the code states and the interface does not. **The index saturates:** on Delhi, 5 Nov 2019, all six vulnerable cohorts read exactly 100.0, so it cannot tell them apart on the days it exists for | Remove the ceiling; anchor to published guidance and Indian concentration–response evidence; publish a sensitivity analysis (Part 2, L) |
| **Lowest-exposure window** — Partial | Mean hourly profile per city and season from the historical hourly file | Keep the correction about hourly AQI | A climatology, not a forecast: it gives the same answer every day of a season. Labelled as a "cleanest window" without stating that air may still be unhealthy | Forecast tomorrow's hourly profile; always state the absolute level alongside the relative one |
| **Policy simulator** — Implemented | Re-scores the full record under a proportional concentration change | **Keep** — already labelled as a scenario, not a prediction | No uncertainty; no weather adjustment; days are counted, people are not | Add sensitivity bands, side-by-side scenarios, population weighting where census data supports it |
| **Lockdown and festival analysis** — Partial | Before/after comparison against a matched baseline | Keep as description | Not adjusted for weather, so it is not a causal estimate. The agreement between the simulator (−37.0%) and the lockdown (−34.0%) is a plausibility check, not a validation | Apply meteorological normalisation (Grange et al. 2018) before any causal wording |
| **City archetypes** — Partial | K-Means on pollutant-mix shape | Keep as exploratory | Twelve points; one cluster has three members. Too little data to support a general claim | Recompute at station level when a few hundred stations are available |
| **SHAP explanations** — Partial | Precomputed global ranking and one fixed local example | Keep method | Not computed for the forecast the user is looking at. Explanations are technical, not plain language | Per-forecast attribution, grouped into a few named drivers, with a plain-language sentence |
| **Drift check** — Partial | Flags inputs more than 3 SD from the training mean | Keep as one signal | On polluted days it fires constantly, because pollution *is* the tail (pilot P4) | Separate data-integrity failures from high-pollution conditions |
| **Web application** — Implemented | Five pages, responsive grid, dark theme | Rework information architecture | Replays historical dates without saying so prominently; English only (the Streamlit app had Tamil and Hindi); severity is conveyed mainly by colour | Part 4 |
| **API** — Partial | Two POST endpoints | Extend | No versioning, rate limiting or schema validation; a malformed body returns HTTP 500 with the Python error text | Part 3 |

### A.3 Corrections required before anything is submitted or presented

These are places where the project currently says more than its evidence supports. They are listed first because a reviewer who finds one will discount everything else.

1. **The live site's "confidence" is not a probability.** It shows the deployed classifier's top-class score, which is overconfident: 41.3% of test forecasts are displayed at 95% or higher, and 88.9% of those are correct (pilot P1).
2. **"Modelled with an explicit lockdown flag" is false.** Six event flags were offered to feature selection (`festival_flag`, `days_from_diwali`, `stubble_season_flag`, `lockdown_flag`, `post_lockdown_flag`, `covid_year_flag`); none was retained by either model. The sentence appears in the application and in the generated insights.
3. **The SHAP finding about the HAI is over-read.** The healthy-adult HAI ranks first, but it is an arithmetic re-expression of today's sub-indices, strongly collinear with AQI and PM2.5. Its rank shows how attribution is shared among correlated inputs. It is not independent evidence that the index is valid, and earlier project text that says so should be withdrawn.
4. **The site replays history.** Asked for today's date, the API silently substitutes 2020-07-01 and the page headlines "forecast for 2 July 2020". It must be labelled a historical replay until live data exists.
5. **The simulator's agreement with the lockdown is not a validation** (see the table above).
6. **The Tamil and Hindi advisory text is unreviewed.** It was machine-drafted. It is health advice, and it should not be shown to the public until a fluent reviewer has checked it.
7. **Cross-validation and test error disagree.** Four-fold expanding-window CV gives MAE 29.9 ± 10.0; the held-out test gives 15.1. The test year is cleaner than the training years and includes the lockdown, so the single-holdout figure flatters the model. Rolling-origin evaluation across several years is required.

### A.4 Deployed system, measured on 7 October 2026

| Check | Result |
| --- | --- |
| Forecast endpoint latency | 4.9 s cold, 0.9 s warm |
| Policy endpoint latency | 4.8 s (re-scores 18,395 rows on each call) |
| Unknown city | Handled: HTTP 400 with the list of covered cities |
| Malformed JSON body | **HTTP 500**, Python exception text returned to the caller |
| What-if input range | **Not validated.** A reduction of −500% is accepted and multiplies PM2.5 six-fold to 1,142 µg/m³, above the pipeline's own plausibility ceiling, and returns "99% confidence" |
| Security headers | HSTS present. No Content-Security-Policy, X-Frame-Options or X-Content-Type-Options. CORS is `*` |
| Languages | English only |
| Data freshness indicator | None |

## A+. Pilot evidence on the existing record

Before committing a roadmap to uncertainty, cross-city generalisation and abstention, each was tested on data already in hand (`python -m src.research.pilot_trust`, results in `results/pilot_trust.json`). These are pilots: historical data only, models refitted on a proper-training slice so that a calibration slice (18 Nov 2018 – 25 May 2019, 2,073 rows) stays unseen. They indicate where the real problems are. They are not results to publish.

### P1. Is the displayed confidence honest?

| Classifier | Accuracy | Mean confidence | Expected calibration error | Shown as ≥ 95% | Correct when shown ≥ 95% |
| --- | --- | --- | --- | --- | --- |
| LightGBM + SMOTE — **what the live site serves** | 76.9% | 86.2% | **0.093** | 41.3% of forecasts | **88.9%** |
| XGBoost + SMOTE, tuned — the reported model | 79.3% | 79.7% | 0.019 | 11.4% of forecasts | 98.0% |

The reported model is well calibrated. The one substituted for it to fit the serverless size limit is not. The substitution cost 2.7 points of macro-F1, which was disclosed, and also the meaning of the confidence figure, which was not known until now.

### P2. Do distribution-free intervals reach nominal coverage?

Nominal coverage 90%, scored on the 4,397-row future test set.

| Method | Overall coverage | Mean width (AQI points) | *Good* days | *Severe* days (n = 44) |
| --- | --- | --- | --- | --- |
| Split conformal, constant width | 94.7% | 96.1 | 99.3% | **56.8%** |
| Conformalised quantile regression | 90.2% | 67.5 | 79.0% | **75.0%** |
| Mondrian, by predicted band | 91.0% | 70.3 | 94.3% | **65.9%** |

Marginal coverage is easy and is met. Coverage on the days that matter is not: no method reaches 90% on *Severe* days. An interval that is right on average and wrong when the air is worst is the specific failure a public advisory cannot afford. Forty-four *Severe* days is a small sample, which is itself a constraint the full study must address with more winters of data.

### P3. How much is lost on a city the model has never seen?

For each city, a model was fitted on the other eleven and scored on the held-out city's test period, with the city-identity feature removed from both arms.

| | MAE, city in training | MAE, city unseen | Persistence |
| --- | --- | --- | --- |
| Weighted mean over 12 cities | 15.14 | 15.67 (**+3.5%**) | 18.91 |
| Worst case: Lucknow | 20.76 | 24.08 (+16.0%) | 28.13 |
| Only failure: Thiruvananthapuram | 8.77 | 9.16 | 8.79 |

The unseen-city model still beats persistence in 11 of 12 cities. **This gap is smaller than the mission brief assumed.** A pooled model built on each city's own recent history transfers well, because what it learns is short-term dynamics, not the city. Two cautions follow. First, an "unseen" city here still supplies its own lag history at prediction time; a city with no monitor at all is a different and much harder problem. Second, all twelve cities passed the same completeness gates. The stronger test is on the fourteen cities those gates excluded.

### P4. If the model declines to answer when least certain, which days does it decline?

| Abstention rule | Declined | MAE on answered | Share of *Severe* days declined | Share of all polluted days declined |
| --- | --- | --- | --- | --- |
| None | 0% | 15.20 | — | — |
| Widest 10% of intervals | 10% | 12.89 | **81.8%** | 54.1% |
| Widest 20% of intervals | 20% | 11.18 | **100%** | 91.8% |
| Highest 10% of relative width | 10% | 14.80 | 2.3% | 2.5% |
| Most novel 10% of inputs (z-score) | 10% | 14.33 | **97.7%** | 36.7% |

Abstaining on uncertainty improves average error and removes the forecast on four in five *Severe* days. Uncertainty and pollution are confounded: the model is least sure when the air is worst. **Naive abstention makes the system silent exactly when it is needed**, so it is rejected as a design. Abstention is kept only for data-integrity failures (stale or missing sensors), where no forecast is the honest output.

### P5. Does advising from a higher quantile fix under-warning?

The alternative to silence is caution: issue the advisory from an upper quantile of the predictive distribution instead of its centre. "Polluted" means the observed band was *Poor* or worse (523 test days).

| Advisory issued from | Polluted days under-warned | *Severe* days under-warned (of 44) | Days over-warned | Exact band |
| --- | --- | --- | --- | --- |
| Point forecast | 94 (**18.0%**) | 8 | 13.7% | 78.9% |
| 65th percentile | 78 (14.9%) | 6 | 17.0% | 77.3% |
| 75th percentile | 47 (**9.0%**) | 5 | 23.7% | 72.5% |
| 85th percentile | 24 (4.6%) | 3 | 33.9% | 64.4% |
| Upper bound of the 90% interval | 10 (1.9%) | 2 | 51.9% | 47.6% |

This is a clean, monotone trade-off between two kinds of error, and the point forecast sits at one arbitrary position on it: it misses nearly one polluted day in five. Choosing where to sit is a decision about whose mistakes are more costly, and that differs by cohort. This is the strongest signal in the pilot and it shapes the hypothesis in section E.

## B. Prior-art analysis

### B.1 Method and scope

Forty-seven external systems were reviewed on 7 October 2026: operational government systems, commercial products, health-impact tools, methods papers, Indian forecasting papers and open student projects. Each was located by web search and its facts taken from the cited page; the full record, with URLs, is `docs/airguard2/prior_art_corpus.csv`. This is a comparison corpus, **not a census of everything ever built**, and every "not found" below is scoped to these 47 sources.

{{include:_generated/prior_art_tables.md}}

### B.4 What the corpus shows

1. **Every individual feature AirGuard has is already established.** Next-day forecasting (23 of 47), cohort or sensitive-group advice (14), sub-city resolution (19), explanation (8) and scenario analysis (4) all exist in operational systems. None of these may be claimed as novel.
2. **India already has operational physical-model forecasting** that a tabular model on city-day data will not out-resolve: 400 m for Delhi (AQEWS), district-level nationwide (UrbanEmissions), 72 hours in four cities (SAFAR), and a decision-support system that attributes Delhi's pollution to sectors and districts.
3. **Cohort-differentiated advice is standard practice** — the UK, Hong Kong, the EEA and the US EPA publish separate guidance for at-risk groups, and Google's API returns recommendations for six groups in over 100 countries. AirGuard's seven cohorts are an extension in granularity, not a new idea.
4. **The closest conceptual prior art is Forecaster.health** (ISGlobal): operational, forecast-driven mortality-risk alerts by sex and age for 653 European regions, built on epidemiological models. It is methodologically stronger than a hand-weighted index. It does not cover India, does not differentiate by condition or occupation, and documents no error guarantee on its alerts.
5. **Health-based indices exist and one has been derived for India.** Canada's AQHI sums excess mortality risk across pollutants; George et al. (2025) derived city-specific versions for Delhi and Varanasi and showed a pooled index misstates local risk. An index that claims to reflect health must now be measured against this standard.
6. **Uncertainty lives in research papers, not in advisories.** Five sources document uncertainty; all are methods papers. **None of the 47 documents forecast, cohort advice and uncertainty together, and none connects uncertainty to the advice it issues.**
7. **Percentage-reduction scenarios are a twenty-year-old technique** (BenMAP's roll-back), and BenMAP and AirQ+ translate them into deaths and illness avoided, which is more than counting advisory-days. None of the 47 links a scenario to cohort-level advisory burden, which is a reporting difference rather than a methodological one.
8. **Leave-one-city-out is an established protocol** (Janku et al. 2026), and the pilot shows the effect is small here.
9. **Published Indian AQI-prediction work frequently reports near-perfect accuracy** from same-day formulations and random splits. A strictly chronological, baseline-referenced evaluation is a real point of difference, but it is rigour, not novelty.

## C. Closest-system comparison

:::landscape

● yes, documented · ◐ partly · · not documented in the source reviewed. "2.0 target" is a design goal, **not an existing capability**.

| # | Question | Google AQ API | Forecaster. health | SAFAR | AQEWS / DSS Delhi | Urban Emissions | IQAir | Plume | E-STGCN | AirGuard 1.0 (today) | AirGuard 2.0 target |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Data used | undisclosed | AQ forecasts + mortality | stations + model | WRF-Chem + assimilation | WRF + CAMx | stations + sensors | sensors + model | 37 Delhi stations | CPCB city-day 2015–20 | stations + CAMS + forecast weather |
| 2 | Live data | ● | ◐ | ● | ● | · | ● | ● | · | **no** | Proposed |
| 3 | Predicts tomorrow's AQI | ● | ◐ risk, not AQI | ● | ● | ● | ● | ◐ 24 h | ● | ● replay only | Proposed |
| 4 | Forecasts individual pollutants | ◐ | ◐ | ◐ | ● | ● | · | · | ● | **no** | Proposed |
| 5 | Uses weather forecasts | · | ◐ | ● | ● | ● | · | · | · | **no** | Proposed |
| 6 | Station-level or finer | ● 500 m | ◐ region | ◐ | ● 400 m | ◐ district | ◐ | · | ● | **no** | Proposed |
| 7 | Multiple cities | ● | ● | ● 4 | Delhi | ● | ● | ● | Delhi | ● 12 | ● |
| 8 | Tested on unseen cities | · | · | · | · | · | · | · | · | pilot: +3.5% MAE | Proposed |
| 9 | Quantifies uncertainty | · | · | · | · | · | · | · | ● | **no** | Proposed |
| 10 | Detects out-of-distribution input | · | · | · | · | · | · | · | · | ◐ z-score | Proposed |
| 11 | Detects model drift | · | · | · | · | · | · | · | · | **no** | Proposed |
| 12 | Abstains when unreliable | · | · | · | · | · | · | · | · | **no** | data-integrity only |
| 13 | Personalised guidance | ● 6 groups | ● sex, age | ◐ generic | · | · | ◐ | ◐ activities | · | ● 7 cohorts | ● |
| 14 | Guidance driven by the forecast | · | ● | ◐ | · | · | · | ● | · | ● | ● |
| 15 | Cohort-specific exposure advice | ● | ◐ | · | · | · | · | ◐ | · | ● unvalidated | Proposed, anchored |
| 16 | Lower-exposure window | · | · | · | · | · | · | ● | · | ◐ | Proposed |
| 17 | Window from history or forecast | — | — | — | — | — | — | forecast | — | history | forecast |
| 18 | Explainable AI | · | · | · | ◐ source shares | · | · | · | · | ◐ fixed example | per forecast |
| 19 | Scenario or causal analysis | · | · | · | ● causal, by sector | · | · | · | · | ● scenario only | scenario + sensitivity |
| 20 | Scenario linked to vulnerable groups | · | · | · | · | · | · | · | · | ● advisory-days | ● |
| 21 | Research-grade diagnostics exposed | · | · | · | ◐ papers | · | · | · | ◐ paper | ● | ● |
| 22 | Data and model provenance exposed | · | ◐ | · | ◐ | ◐ | · | · | ◐ | ● | ● |
| 23 | Externally validated | · | ◐ | · | ● peer-reviewed | · | · | · | ◐ preprint | **no** | Future research |
| 24 | Reproducible | · | ◐ open access | · | · | · | · | · | ◐ | ● one command | ● |
| 25 | Nature | product | research operational | government | government | NGO | product | product | paper | student project | research platform |

:::

## D. Gap-to-solution matrix

Every major 2.0 feature answers a row here. A feature that answers no row is not built.

| Existing limitation | Evidence | Why it matters | AirGuard 2.0 response | Experiment | Success metric |
| --- | --- | --- | --- | --- | --- |
| Advisories are issued from a point forecast with no stated error rate | 0 of 47 sources link uncertainty to advice; pilot P5: 18.0% of polluted days under-warned | A missed warning harms the people the advisory exists for | Issue each cohort's advisory from a quantile chosen to hold under-warning below a declared target | Risk-controlled advisory on rolling-origin data | Realised under-warning ≤ target on unseen future data, with fewer over-warnings than a uniform one-band shift |
| Intervals fail on extreme days | Pilot P2: 57–75% coverage on *Severe* days at 90% nominal | Average-case calibration hides the worst case | Regime-aware conformal intervals with weather features | Conditional coverage by band and season | ≥ 85% coverage on *Poor*-or-worse days at 90% nominal |
| Forecast confidence shown to users is uncalibrated | Pilot P1: ECE 0.093 on the live classifier | A wrong "99%" destroys trust | One predictive distribution; band probabilities derived from it | Reliability diagram on future data | ECE ≤ 0.03 |
| Systems always answer | 0 of 23 forecasting sources document abstention; pilot P4 shows naive abstention is unsafe | Silence when air is worst is worse than a cautious answer | Withhold only on data-integrity failure; otherwise widen and escalate | Compare three policies on declined-day composition | No *Severe* day declined for uncertainty alone |
| No weather in the model | Audit; *Severe* bias −22.6 | Dispersion drives next-day change | Day-ahead forecast meteorology, archived at true lead time | Ablation: pollution → + weather → + CAMS → + fire | MAE and *Severe*-day bias, each with a bootstrap interval |
| Statistical forecasts are rarely compared with the free physical forecast | CAMS is public and global | Beating persistence is not the bar a user faces | CAMS as a baseline and as an input | Station model vs raw CAMS vs CAMS post-processed | Skill score against CAMS |
| Cohort weights are hand-set | Audit; George et al. 2025 and de Bont et al. 2024 provide Indian evidence | An index that claims health relevance must trace to evidence | Anchor to published guidance tiers and Indian concentration–response functions; publish sensitivity | Advisory flips under ±20% weight perturbation | Share of advisories stable under perturbation |
| Index saturates | Audit: six cohorts at 100.0 on one day | No discrimination on the worst days | Unbounded scale with labelled bands | Distribution of the index on *Very Poor* and *Severe* days | No more than 1% of values at any cap |
| Lowest-exposure window is a climatology | Audit | Same answer every day of a season | Hourly forecast for tomorrow, with the absolute level stated | Hit rate of the recommended window against the observed minimum | Better than the climatological window on held-out days |
| Single chronological holdout | Audit: CV MAE 29.9 vs test 15.1 | One easy test year flatters the model | Rolling-origin evaluation across years | Per-origin error | Report the distribution, not one number |
| Not live | Audit | The product claim depends on it | Ingestion with provenance and quality flags | Seven days of unattended ingestion | ≥ 95% of scheduled runs succeed; staleness always shown |
| Scenario results carry no uncertainty | Audit | A single number overstates precision | Sensitivity bands; weather-normalised baseline | Scenario repeated across years and seasons | Range reported with every scenario |

### D.1 Feature novelty classification

| AirGuard feature | Class | Reason |
| --- | --- | --- |
| Next-day AQI forecasting | Existing / common | 23 of 47 sources |
| Gradient-boosted trees, SHAP | Existing / common | Standard |
| Live dashboard, map | Existing / common | Standard |
| Cohort-specific advice | Improved implementation | Tiers exist; seven cohorts is finer granularity |
| Lowest-exposure window from a forecast | Improved implementation | Plume Labs did this for 24 hours |
| Percentage-reduction scenarios | Existing / common | BenMAP roll-back |
| Scenario → cohort advisory-days | Integration contribution | Not found among the 47; a reporting choice |
| Forecast + cohort advice + calibrated uncertainty in one pipeline | Integration contribution | Co-occurrence not found among the 47 |
| Chronological evaluation, leakage demonstration, persistence and CAMS baselines for Indian cities | Experimental contribution | Counters a documented weakness in the Indian literature |
| Leave-one-city-out and excluded-city tests | Experimental contribution | Protocol exists; this application does not appear among the 47 |
| Evidence that uncertainty-based abstention silences severe days | Experimental contribution | Pilot P4; to be confirmed on new data |
| **Risk-controlled cohort advisories** | **Methodological contribution (candidate)** | Section E |
| Unified citizen / researcher / policymaker interface | Product contribution | Not a research claim |

## E. Research hypothesis

Selected because it is the one gap where the corpus is empty, the pilot shows a large measurable effect, and an existing method (conformal risk control) offers a principled route.

> **H1 (primary).** For next-day air-quality advisories in Indian cities, an advisory issued from a quantile of a calibrated predictive distribution, with the quantile set per cohort by conformal risk control, holds the rate of under-warning on polluted days at or below a pre-declared cohort-specific target on unseen future data, and does so with significantly fewer over-warnings than (a) a point forecast shifted up by one band and (b) a fixed quantile chosen without calibration.

Supporting hypotheses, each a separate experiment:

- **H2 — Meteorology.** Day-ahead forecast meteorology, used strictly at its true lead time, reduces MAE and specifically reduces the under-prediction on *Poor*-or-worse days, relative to the pollution-only model.
- **H3 — Conditional coverage.** Regime-aware conformal intervals reach at least 85% coverage on *Poor*-or-worse days at 90% nominal, where the three pilot methods reach 57–75% on *Severe* days.
- **H4 — Beyond the free forecast.** A station-level statistical model that takes CAMS as an input beats both raw CAMS and the pollution-only model.
- **H5 — Transfer.** H1's guarantee continues to hold in cities absent from training and in the cities the original completeness gates excluded.

Every hypothesis is falsifiable and each has a pre-declared metric in the matrix above. A negative result on any of them is reported.

## F. Novelty statement

What may be said, on the evidence so far:

> *We propose a framework in which next-day air-quality advisories for vulnerability cohorts are issued from a calibrated predictive distribution at a cohort-specific risk level, so that the rate of under-warning is controlled rather than incidental. Among the 47 operational systems, products and papers we reviewed, none documents forecast-driven cohort advice together with calibrated uncertainty, and none attaches a stated error rate to the advice it issues.*

What may **not** be said:

- That AirGuard is the first, or the only, system to do any single thing in the feature list. Each is prior art.
- That the Health Advisory Index is validated, clinical, or evidence-derived, until Part 2 section L is carried out.
- That the simulator predicts the effect of any intervention.
- That the risk-controlled advisory is new to the literature. A review of 47 sources does not establish that. A dedicated search of conformal decision-making, cost-loss forecasting and impact-based warning literature is a precondition for the word "novel", and is scheduled as the first task of the paper phase.
