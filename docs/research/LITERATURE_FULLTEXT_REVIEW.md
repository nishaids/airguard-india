# Targeted primary-text literature matrix

Reviewed 12 October 2026. This extends the inherited [prior-art catalogue](prior_art.json), [continuation](LITERATURE_CONTINUATION.md) and [evidence gate](EVIDENCE_REVIEW.md). The structured companion is [literature_fulltext_review.json](../../results/research/literature_fulltext_review.json).

Fifteen primary-source entries record the task, geography/data, validation, input availability, uncertainty/advisory scope, overlap and limitations. Selected full-text sections were read where accessible. Indexed publisher/PMC body sections, official overviews and access failures are labelled separately. “Not established” means not demonstrated by inspected text; it does not assert absence. No reproduction audit is claimed.

| Source / inspected text | Concrete implication for this study |
| --- | --- |
| [Riccio and Chianese, 2024](https://acp.copernicus.org/articles/24/1673/2024/) · 10.5194/acp-24-1673-2024<br>fulltext selected sections | Spatial and next-day validation; operational-weather versus ERA5 discrepancy. |
| [Petetin et al., 2022](https://acp.copernicus.org/articles/22/11603/2022/) · 10.5194/acp-22-11603-2022<br>fulltext selected sections | Expanding past-data MOS; prior-observation availability ablation and warning trade-offs. |
| [Casciaro, Cavaiola and Mazzino, 2022](https://arxiv.org/html/2201.13355) · 2201.13355v1<br>fulltext selected sections | 2019/2020 separation plus rolling calibration; probabilistic station correction. |
| [Colette et al., 2025](https://gmd.copernicus.org/articles/18/6835/2025/) · 10.5194/gmd-18-6835-2025<br>fulltext selected sections | Operational CAMS-MOS precedent; distinguishes forecast and reanalysis diagnostics. |
| [Jena et al., 2021](https://www.nature.com/articles/s41598-021-83467-8) · 10.1038/s41598-021-83467-8<br>primary indexed fulltext sections | Indian operational forecast precedent; indexed body only; spatial independence unresolved. |
| [Natarajan et al., 2024](https://www.nature.com/articles/s41598-024-54807-1) · 10.1038/s41598-024-54807-1<br>primary indexed fulltext sections | Indian AQI regression; issue-time horizon and split isolation unestablished. |
| [Govardhan et al., 2024](https://gmd.copernicus.org/articles/17/2617/2024/) · 10.5194/gmd-17-2617-2024<br>fulltext selected sections | Indian five-day operational evaluation; peak underprediction and categorical diagnostics. |
| [Singh et al., 2026](https://www.nature.com/articles/s41598-026-37934-9) · 10.1038/s41598-026-37934-9<br>publisher manuscript and indexed sections | Indian reanalysis correction; 75/25 and K-fold study, distinct task. |
| [Pande et al., 2024](https://www.sciencedirect.com/science/article/abs/pii/S0269749124007541) · 10.1016/j.envpol.2024.124040<br>abstract and primary indexed body sections | Daily Delhi AQI prior art; indexed sections; timing/split details pending. |
| [Romano, Patterson and Candes, 2019](https://arxiv.org/html/1905.03222) · 1905.03222<br>fulltext selected sections | Marginal exchangeability guarantee; separate calibration and test are essential. |
| [Angelopoulos, Bates, Fisch, Lei and Schuster, 2024](https://arxiv.org/html/2208.02814) · 2208.02814v4<br>fulltext selected sections | Expected monotone-loss control; dependent cohort warning guarantee does not follow. |
| [Angelopoulos, Barber and Bates, 2024](https://proceedings.mlr.press/v235/angelopoulos24a.html) · 2402.01139v2<br>fulltext selected sections | Sequential dependence-relevant calibration; long-run coverage is a distinct guarantee. |
| [Adjei et al., 2026](https://arxiv.org/html/2604.22787) · 2604.22787v1<br>fulltext selected sections | Spatial conformal mapping preprint; reanalysis and inner-validation audit limits. |
| [WHO Regional Office for Europe, 2024](https://www.who.int/publications/i/item/WHO-EURO-2024-9115-48887-72806)<br>official overview only | Official overview only; full action-specific evidence acceptance remains pending. |
| [US EPA / AirNow, undated webpages inspected 2026-10-12](https://www.airnow.gov/aqi/aqi-basics/)<br>official webpages | Sensitive-group guidance precedent; US thresholds cannot replace CPCB. |

The matrix supports methodological overlap, not an exhaustive novelty conclusion. Station-specific CAMS correction and probabilistic calibration are established in [Riccio and Chianese](https://acp.copernicus.org/articles/24/1673/2024/), [Petetin et al.](https://acp.copernicus.org/articles/22/11603/2022/), [Casciaro et al.](https://arxiv.org/html/2201.13355) and the operational [CAMS-MOS description](https://gmd.copernicus.org/articles/18/6835/2025/). An India application alone does not establish a new correction method.

Riccio's main §2.2 describes operational ECMWF weather; [supplement Table S1](https://acp.copernicus.org/articles/24/1673/2024/acp-24-1673-2024-supplement.pdf) instead lists ERA5 weather variables. This unresolved discrepancy is an input-provenance limitation, not evidence authorizing reanalysis in AirGuard's experiment.

[Petetin](https://acp.copernicus.org/articles/22/11603/2022/) and the [Delhi DSS study](https://gmd.copernicus.org/articles/17/2617/2024/) motivate reporting missed exceedances and false alarms alongside continuous errors. Our inference is to preserve separate under-warning/over-warning diagnostics, identical evaluation pairs and censored-Severe threshold evaluation. Their numerical results are not AirGuard results.

[CQR](https://arxiv.org/html/1905.03222), [CRC](https://arxiv.org/html/2208.02814) and [online conformal prediction](https://arxiv.org/html/2402.01139v2) provide different guarantees under stated assumptions. Marginal exchangeable coverage, expected monotone-loss risk and long-run sequential coverage must remain distinct. None directly certifies AirGuard's dependent daily/cohort-conditional warning risk. Region and severity diagnostics remain empirical requirements.

The Indian [MERRA-2 study](https://www.nature.com/articles/s41598-026-37934-9) and African [spatial mapping preprint](https://arxiv.org/html/2604.22787) concern retrospective estimation/mapping. They cannot substitute genuine archived operational CAMS forecasts. Contemporary pollutant-to-AQI regression also requires a proven lag/availability design before comparison with a next-day forecast.

[WHO's overview](https://www.who.int/publications/i/item/WHO-EURO-2024-9115-48887-72806) and [AirNow guidance](https://www.airnow.gov/air-quality-and-health/asthma-and-heart-disease/) do not validate AirGuard medical coefficients or the preregistered 10%/5% warning policy targets. Those targets are policy choices, not disease probabilities. US AQI thresholds must not replace CPCB thresholds.

The candidate contribution remains an evaluated Indian station-correction study with audited issue-time inputs, chronological/spatial testing, censored-Severe evaluation, calibrated uncertainty, warning trade-offs and immutable prospective verification. This is a research hypothesis pending matched CAMS results and actual prospective outcomes. No world's-first or clinical-benefit claim is supported.

`literature_review_complete=false`, `human_evidence_acceptance=false` and `health_coefficient_acceptance=false` remain explicit in the companion. No `literature_review_acceptance.json` was created. Outstanding work includes inaccessible complete methods/supplements, the WHO action-specific report, independent coefficient review, reference editing and human claim-by-claim acceptance. The protocol and locked final test remain unchanged.
