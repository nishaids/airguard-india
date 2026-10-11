# Targeted review continuation, 12 October 2026

This extends the inherited review and bibliography. It does not replace them.
Full-text extraction, a documented exhaustive search and claim-by-claim author
review are incomplete; `literature_review_complete` remains false.

| Primary source | Relevance and implication for AirGuard |
| --- | --- |
| [Riccio and Chianese, 2024](https://acp.copernicus.org/articles/24/1673/2024/) | CAMS post-processing with EMOS, spatial inference, meteorology and probabilistic calibration on Italian monitoring stations already exists. This directly overlaps the proposed correction and uncertainty story. Geographic application alone does not establish methodological novelty. |
| [Petetin et al., 2022](https://acp.copernicus.org/articles/22/11603/2022/) | Station MOS for CAMS ozone compares moving averages, quantile mapping, Kalman filters, analogs and boosting, alongside persistence. Its continuous/categorical trade-off motivates reporting exceedance misses and false alarms alongside MAE. |
| [Calibrating CAMS European multi-model forecasts, 2022](https://arxiv.org/abs/2201.13355) | Additional overlapping calibration work; abstract and bibliographic record inspected. Full-text methodology comparison remains pending. |
| [Romano et al., CQR, 2019](https://arxiv.org/abs/1905.03222) | Conformalized quantile regression is established. Applying it requires held-out calibration, finite-sample ranks, interval-width reporting and subgroup coverage diagnostics. A national application is not a new interval algorithm. |
| [Angelopoulos et al., Conformal Risk Control](https://arxiv.org/abs/2208.02814) | Risk calibration has established theory. AirGuard's dependent daily records and empirical under-warning policy do not automatically inherit an exchangeability-based guarantee. |
| [Online conformal prediction with decaying step sizes, 2024](https://proceedings.mlr.press/v235/angelopoulos24a.html) | Online calibration is relevant to a changing operational feed. A future adaptive method would require its own declared update policy and comparison; it is not implemented by a static split-conformal radius. |
| [Colette et al., CAMS regional system, 2025](https://gmd.copernicus.org/articles/18/6835/2025/) | The system describes CAMS-MOS station optimisation, including meteorology-dependent ensemble errors. Station correction is established operational practice. |
| [Indian surface PM2.5 estimation with MERRA-2, 2026](https://www.nature.com/articles/s41598-026-37934-9) | A measured-station Indian ML application uses reanalysis predictors. It is relevant regional prior art, but does not establish an issue-time operational forecast comparator for this study. |
| [Conformal PM2.5 mapping under spatial shift, 2026 preprint](https://arxiv.org/abs/2604.22787) | Spatial validation and region-specific interval failures are relevant. Satellite/reanalysis mapping is distinct from next-day forecasting; reported spatial calibration should not be transferred to operational India. Preprint status is retained. |

Candidate contribution: an evaluated Indian station-calibration procedure with
audited issue-time inputs, chronological and spatial tests, explicit censored
Severe evaluation, vulnerability-stratified warning trade-offs and real forward
verification. This remains a hypothesis until the genuine CAMS comparison and
prospective station outcomes exist. No world's-first claim is supported.

The vulnerability targets (10% for general adults, 5% for the other declared
cohorts) are preregistered policy aims. They are not estimated medical risks,
validated health coefficients or evidence that an advisory improves health.

## Source-availability evidence

[Open-Meteo Previous Runs documentation](https://open-meteo.com/en/docs/previous-runs-api)
describes `previous_day2` as predictions at a 48-hour offset. These are forecast
inputs, not weather reanalysis. The cached manifest preserves the chosen model,
lead and requested variables. It provides no corresponding operational CAMS
run archive for the air-quality past-fields cache.

[ADS setup](https://ads.atmosphere.copernicus.eu/how-to-api) requires manual
dataset Terms of Use acceptance and a personal access token. The relevant
[CAMS global forecast dataset](https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts?tab=overview)
must be requested with forecast initialisation and lead time preserved.
