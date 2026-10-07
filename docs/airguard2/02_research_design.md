# Part 2 — Research design

How the hypotheses in Part 1 will be tested. Everything in this part is **Proposed** unless marked otherwise. Each choice states why it was made, what was considered instead, and what evidence would confirm or overturn it.

Each element is classified: **ER** essential for research · **EP** essential for product · **HV** high-value optional · **FW** future work.

## H. Dataset strategy

### H.1 Sources, and what was actually verified

Access was tested from the development machine on 7 October 2026. "Verified" means a real request returned real data on that date.

| Source | Role | Access | Status on 7 Oct 2026 | Constraint to respect |
| --- | --- | --- | --- | --- |
| **CPCB real-time AQI on data.gov.in** | Official live station measurements | Free API key from the portal | **Not verified.** `api.data.gov.in` refused the connection; the resource page blocks automated reading. One search result reported the API as not currently offered. | Must be confirmed with the team's own key before the design depends on it |
| **CPCB CCR portal** | Official station history | Manual download, limited span per request | Documented; no API found | Backfill only; cannot feed a scheduler |
| **OpenAQ v3** | Aggregated station measurements | Free API key | Endpoint reachable; returns 401 without a key | Label as *OpenAQ, originating from CPCB* — never as an official CPCB feed. India freshness to be checked with a key |
| **CAMS global, via Open-Meteo Air Quality API** | Modelled pollutant analysis and 5-day hourly forecast | No key | **Verified.** Returned current PM2.5, PM10, NO2, SO2, O3, CO for Chennai and Delhi | Modelled on a ~45 km grid, not measured. Attribution to CAMS and Open-Meteo required. History from August 2022 |
| **Open-Meteo Forecast API** | Day-ahead meteorology | No key | **Verified.** Temperature, humidity, wind speed and direction, pressure, precipitation, **boundary-layer height**, radiation | Free tier is non-commercial; any paid offering needs their commercial tier or self-hosting |
| **Open-Meteo Previous Runs API** | Archived forecasts *at their original lead time* | No key | **Verified.** Returned the forecast made one and two days earlier for a past date | Starts January 2024. This is what makes leakage-free training on forecast weather possible |
| **Open-Meteo Historical Weather (ERA5)** | Reanalysis for 2015–2020 | No key | Documented, not probed | Reanalysis is not a forecast; see H.3 |
| **NASA FIRMS** | Active fires (VIIRS 375 m) | Free MAP_KEY | Documented, not probed | 5,000 transactions per 10 minutes |
| **Sentinel-5P / MODIS AOD** | Satellite columns | Earth Engine or Copernicus | Not probed | Cloud gaps, one overpass a day; kept only if the ablation earns it |
| **India Meteorological Department** | Official weather | — | No openly documented API was found in this review | Not used. Open-Meteo is therefore labelled a third-party source |
| **Traffic** | Congestion proxy | — | No legally clean free source identified | **FW** |
| Kaggle city-day 2015–2020 (in use) | Historical baseline | CC0 | In the repository | Ends July 2020; city-level |
| Princeton CPCB 2015–2019 | Station-hour history | Open | Located, not downloaded | Station-level complement to the file above |

**Why Open-Meteo for weather, given the brief asks for official sources first.** Considered: IMD (no documented open API found), direct ECMWF or NOAA GFS access (free but requires GRIB handling and an archive the project would have to build itself). Open-Meteo redistributes those same national models, and uniquely offers forecasts archived at lead time, which no other free source reviewed provides. **Evidence that would overturn this:** an IMD API with archived forecasts, or measured skill for Indian cities that is clearly worse than an alternative.

### H.2 Provenance contract — EP

Every stored measurement carries: `source`, `source_station_id`, `station_name`, `city`, `latitude`, `longitude`, `pollutant`, `value`, `unit`, `averaging_period`, `observed_at` (UTC), `retrieved_at` (UTC), `quality_flag`, and `is_modelled`. The interface shows a measured value and a modelled value differently and never merges them silently. When no fresh measurement exists, the interface says **"Data temporarily unavailable"** and may show the modelled estimate, labelled as such.

### H.3 Two training tracks, kept separate — ER

The historical file and the live sources do not overlap in time, and they cannot be mixed without leaking information.

| | Track A — historical | Track B — operational |
| --- | --- | --- |
| Period | 2015 – mid-2020 | January 2024 – present |
| Pollution | Kaggle city-day; Princeton station-hour | Station measurements via OpenAQ or CPCB |
| Weather | ERA5 reanalysis | Forecasts archived at one-day lead |
| CAMS | Not available | Forecast archive from August 2022 |
| Use | Method development, long-run evaluation, the 2015–2020 pilot | **The model that is deployed** |
| What it can claim | An **upper bound** on the value of weather (a "perfect-prognosis" experiment) | Real skill under real forecast error |

Reanalysis describes the weather that happened. Feeding tomorrow's reanalysis to a model predicts tomorrow with knowledge no forecaster has. Track A weather results are therefore always labelled an upper bound, and no Track A weather model is ever served.

The period from July 2020 to the end of 2023 is backfilled with pollution-only data where the station archive allows, and is used to test stability across years.

### H.4 The prediction-time contract — ER

A forecast for day *D + 1* is issued at a fixed time on day *D* (18:00 IST proposed). A feature may use an observation only if its `observed_at` precedes the issue time by the source's publication delay, and a forecast variable only if the model run was available by then. At issue time the full feature vector is written to a snapshot table and is never recomputed. Training reads snapshots, so the model can only ever be trained on what it would actually have seen.

## I. Preprocessing pipeline — ER

Retained from 1.0 without change: chronological split; statistics fitted on training data only; event-aware outlier rule; causal imputation with a stated cost; the leakage demonstration.

Added for 2.0:

1. **Unit and time normalisation.** All timestamps to UTC with the IST calendar day as the target period; CO in mg/m³, everything else in µg/m³, converted at ingestion with the conversion recorded.
2. **Station quality gates.** Flat-line detection (identical values for six or more hours), range checks against the existing plausibility ceilings, spike checks against neighbouring stations, and a completeness rule for daily aggregates (a minimum number of valid hours per day, set from the CPCB index method document and recorded in configuration).
3. **Staleness.** A station with no reading for three hours is marked stale; a stale station contributes no feature and triggers the integrity path in section N.
4. **Duplicates.** A uniqueness constraint on (source, station, pollutant, observed_at, averaging_period); ingestion is idempotent.
5. **Targets computed, not downloaded.** The next-day AQI is recomputed from concentrations with the CPCB breakpoints, as 1.0 already does, so the label is identical across sources.
6. **Feature selection stays inside each training fold.** In 1.0 selection ran once on the training period; in rolling-origin evaluation it is repeated per origin.
7. **Event flags are kept by rule, not by selection.** They were discarded in 1.0 by a statistical filter; rare events have low marginal importance and high importance on the days they occur.

## J. Model benchmark plan — ER

The current LightGBM is the baseline to beat, not the presumed winner.

| Tier | Models | Admitted when |
| --- | --- | --- |
| 0 — References | Persistence; 7-day seasonal persistence; city-and-day-of-year climatology; **raw CAMS forecast** | Always |
| 1 — Linear | Ridge; SARIMAX with exogenous terms | Always; SARIMAX only if residual autocorrelation warrants it |
| 2 — Trees | LightGBM (current), XGBoost, CatBoost, random forest; quantile variants of each | Always |
| 3 — Sequence | GRU, temporal convolutional network, PatchTST, Temporal Fusion Transformer | Only with station-hour data on the order of a million rows |
| 4 — Spatiotemporal | Graph networks with stations as nodes and edges from distance and forecast wind direction | Only with roughly a hundred or more stations each having two years of history |

**Adoption rule.** A model from a higher tier replaces the best lower-tier model only if all three hold: its rolling-origin MAE is lower by more than the bootstrap confidence interval (and a Diebold–Mariano test rejects equal accuracy); its bias on *Poor*-or-worse days is not worse; and it fits the serving budget. Otherwise the simpler model is kept and the comparison is reported as a negative result.

**Why this, and not "use a transformer".** The corpus contains many deep spatiotemporal models (AirFormer, PM2.5-GNN, E-STGCN) trained on hundreds to thousands of stations. On twelve city series the pilot already shows a pooled tree model transferring across cities with a 3.5% loss. Depth will be earned by data volume or not used.

**Targets.** Primary: next-day AQI per station and per city. Also evaluated: next-day concentration per pollutant, with AQI and dominant pollutant *computed* from the predicted concentrations, compared against predicting AQI directly. Hourly profile for the next day, for the exposure window. Days two and three are produced but **shown only if** their skill against persistence is positive with its confidence interval and their interval coverage holds.

## K. Evaluation plan — ER

### K.1 Protocols

| Protocol | Question it answers |
| --- | --- |
| Rolling origin, monthly refits, expanding window | Skill on the future, across many test periods rather than one |
| Strict final holdout (most recent winter, untouched until the end) | The number that goes in the abstract |
| Leave-one-city-out | Transfer to a city absent from training |
| Excluded-city test | Transfer to the cities the completeness gates removed |
| Station holdout within a city | Transfer to a new monitor |
| Regime slices | Error by AQI band, season, festival window, and extreme episodes |

No random split is used anywhere. No synthetic sample ever enters a validation or test fold.

### K.2 Metrics

| Aspect | Metrics |
| --- | --- |
| Point forecast | MAE (primary), RMSE, bias; skill score against persistence and against CAMS; all reported by band, city, season |
| Extremes | MAE and bias on *Poor*-or-worse days; hit rate and false-alarm ratio for AQI > 300 |
| Category | Macro-F1, per-class recall with *Severe* recall stated, ordinal error |
| Probability | Expected calibration error, Brier score, reliability diagram |
| Intervals | Coverage and mean width, overall and **conditional** on band, city and season; interval score |
| Advisory | Under-warning rate on polluted days; over-warning rate; both per cohort |
| Uncertainty of the metrics | Block bootstrap confidence intervals on every headline number |

*Severe* days are few (44 in the 1.0 test set). Every claim about them carries its sample size and interval, and conclusions are not drawn from a difference inside that interval.

### K.3 Ablation — ER

Components are added one at a time and kept only if they pay:

`persistence → + lag and rolling features → + calendar and event flags → + forecast meteorology → + CAMS forecast → + fire counts upwind → + neighbouring stations → + satellite columns`

Each step reports the change in MAE, in *Poor*-or-worse bias and in interval width, with a confidence interval. A step whose gain lies inside the interval is dropped and reported as such.

## Uncertainty and the risk-controlled advisory — ER

### One predictive distribution

1.0 runs a regressor and a separate classifier that can disagree. 2.0 fits quantile models and conformalises them, giving a full predictive distribution for next-day AQI. Everything shown is read from it: the expected value, the likely range, and the probability of each band (the mass of the distribution falling inside that band's limits). The band probabilities and the number can no longer contradict each other.

**Candidates for the conformal layer:** conformalised quantile regression (pilot: 90.2% overall, 75% on *Severe*); Mondrian conditioning on predicted band and season; adaptive conformal inference, which adjusts the level online as the series drifts. **Chosen by:** conditional coverage on *Poor*-or-worse days and interval score, on rolling origins.

### The advisory as a controlled decision

For cohort *c*, choose in advance the largest acceptable rate of under-warning, α_c. The advisory band is read from quantile *q* of the predictive distribution, and *q* is set on a calibration window as the smallest value whose under-warning rate there does not exceed α_c (conformal risk control). Because the loss is monotone in *q*, the procedure has a finite-sample guarantee under exchangeability; because pollution series drift, the calibration window rolls forward and the guarantee is checked empirically rather than assumed.

Consequences:

- Vulnerability enters twice and separably: in how the mixture is scored (section L) and in how much risk is tolerated. A cardiac patient's advisory is issued further up the distribution than a healthy adult's.
- The cost is visible. Every setting reports its over-warning rate beside its under-warning rate, as in pilot P5.
- The α values are **value judgements, not statistics**. They are proposed with a public-health reviewer, published, and never presented as derived.

**Alternatives considered.** Shifting every vulnerable cohort up one band (what official tiers effectively do): simple, used as the main baseline, expected to over-warn. Abstaining under uncertainty: rejected on pilot P4. A fixed high quantile for everyone: a second baseline. **Evidence that would overturn the choice:** if the controlled rule does not beat the one-band shift on over-warning at matched under-warning, the simpler rule is adopted and that is the finding.

### What a user sees

*Expected AQI 187 · likely range 165–211 · most likely "Moderate" (62%), "Poor" (31%).* A confidence word (high, moderate, low) is defined by the interval's width relative to the band it sits in, with the definition published. The phrase "low-confidence forecast — interpret cautiously" appears when the range spans three or more bands.

## L. Health Advisory Index methodology — ER / FW

The index remains **informational decision support**. It is not a clinical score and is not described as one anywhere.

### L.1 What changes

| Issue in 1.0 | Change in 2.0 |
| --- | --- |
| Ceiling at 100 makes six cohorts identical on bad days | Unbounded index with labelled bands; saturation reported as a metric |
| Weights hand-set | Two-layer design below |
| No evidence of robustness | Published sensitivity analysis |
| Text not reviewed | Advisory text and translations reviewed by a clinician or public-health professional before release |

### L.2 Two layers

**Layer 1 — tiers that authorities already publish (EP).** CPCB attaches health statements to each AQI category; the UK, Hong Kong, the EEA and the US EPA publish separate guidance for at-risk groups, which in effect starts their advice one category earlier. Each AirGuard cohort is mapped to these published tiers, with the source cited beside every sentence of advice. This layer makes no new scientific claim.

**Layer 2 — pollutant-specific emphasis (ER, exploratory).** The finer differences between cohorts (for example, more weight on SO2 and O3 for asthma) remain a constructed prototype. They are shown as such, and are tested rather than asserted:

- *Sensitivity.* Each factor is perturbed by ±20% and the co-exposure coefficient across 0 to 0.5. The reported quantity is the share of city-days whose advisory band changes. If advice is unstable under plausible perturbation, the layer is simplified.
- *Anchoring.* An alternative index is built in the AQHI form — the sum of excess risk per pollutant — using Indian concentration–response estimates (George et al. 2025 for Delhi and Varanasi; de Bont et al. 2024 for ten cities). The two indices are compared day by day. Where they disagree is where the hand-set weights need justification.

### L.3 What would count as validation — FW

Agreement with health outcomes: daily respiratory and cardiovascular admissions or emergency visits by age group, from a hospital or health-department partner. That data is not available to the project. Until it is, the index is described as *evidence-informed and unvalidated*, and Forecaster.health is cited as the system that has done this properly for Europe.

### L.4 Privacy

Users pick a broad cohort; no diagnosis, name or account is required. The selection is kept on the device.

## Lowest-exposure window 2.0 — EP

Tomorrow's hourly profile is forecast from the CAMS hourly shape, corrected by each station's own learned diurnal pattern and by forecast boundary-layer height and wind. The output states three things together: the two-hour window with the lowest expected exposure, how much lower it is than the day's peak and mean, and **the absolute level in that window with its band for the selected cohort**. If the best window is still in a restrictive band for that cohort, the answer is "No suitable lower-exposure outdoor window identified." The word "safe" is not used.

Measured by regret (exposure in the recommended window minus exposure in the true best window, relative to the daily mean) and by how often the recommendation falls in the true lowest three hours, against the 1.0 seasonal climatology as baseline.

## Policy scenarios 2.0 — EP

The simulator stays a **concentration scenario**: "if PM2.5 had been 20% lower", never "if this measure were adopted". Added: up to three scenarios side by side with a baseline; a range for every output, obtained by repeating the scenario by year and season; a weather-normalised baseline before any before/after comparison is described; population weighting where census ward or city populations are available, with the population source cited; and an explicit statement beside the result that pollutants are reduced independently and atmospheric chemistry is not simulated. Linking a named intervention to a concentration change requires a source-apportionment model of the kind the Delhi Decision Support System runs, and is **FW**.

## Explanation 2.0 — EP

Attribution is computed for the forecast on screen, not for a stored example. The hundred features are grouped into a few named drivers — recent trend, today's level, weather tomorrow, season and calendar, regional background — and their contributions summed, which also removes the collinearity artefact noted in the audit. The citizen view renders the two largest groups as one sentence generated from a fixed template, so the wording cannot drift from the numbers. The researcher view keeps the full attribution, dependence plots, residuals, calibration and error by band, city and season. Every explanation carries the line: *this describes what the model used, not what causes pollution.*

## Trust and failure behaviour — EP / ER

| Condition | Detection | Behaviour |
| --- | --- | --- |
| Station stale or missing | No reading within three hours | Forecast withheld for that station: "No fresh data for this station since 14:00." Nearest valid station or the modelled value offered, labelled |
| Implausible reading | Range, flat-line and neighbour checks | Reading excluded and flagged; shown in the data-source panel |
| Input far from training experience | Distance in feature space, assessed **within the predicted band** so that pollution alone does not trigger it | Forecast shown with a caution and the widened range |
| High pollution with wide range | Predictive distribution | **Never withheld.** Advisory escalates to the cautious quantile |
| Model drift | Rolling error and rolling interval coverage against their training-time values | Alert to maintainers; coverage figure shown on the trust page |
| Upstream API failure | Scheduler | Last successful retrieval time shown; nothing fabricated |
