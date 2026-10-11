# Preregistered national study

The immutable expanded definition is `src/research/study_protocol.py`, version `airguard-national-study-20ist-v2`. Register its SHA-256 definition in Supabase with `python -m src.research.reproduce register` before evaluating any final test. Active prospective collection v1 remains unchanged. Preregistration does not establish data eligibility or a trained model.

H1: station correction improves next-day MAE against raw CAMS and measured persistence on held-out dates and cities. H2: CAMS O3/PM2.5 bias depends on region and season; expected directions are hypotheses. H3: empirical 80/90% interval coverage falls within three percentage points of nominal across seasons/severity. H4: empirical vulnerable/general under-warning is at most 5/10%, with over-warning and support reported. No hypothesis is declared supported yet.

Issue at 20:00 Asia/Kolkata using only inputs actually available/retrieved by that cutoff. Record actual issuance; do not backdate. Genuine archived forecasts require run initialization, lead, availability evidence and licence. Current CAMS or reanalysis cannot impersonate such an archive. ERA5 is restricted to separately tagged retrospective deweathering.

Targets: one pre-bound station, IST daily means for eligible non-gas pollutants, complete trailing eight-hour gas windows ending in the day, minimum sixteen distinct valid hourly bins and three pollutants including a particulate. Preserve Severe lower bounds as censored category information; do not invent exact Severe regression errors. Missingness and QA decisions stay explicit.

Use at least 365 training dates, 30 calibration dates, 30 test dates, 30-day steps and a one-day embargo between partitions. Reserve the latest 90 global dates before selection. A final lock includes data, protocol and source hashes; a changed dataset/code cannot silently re-open that final test. Same-hash reruns reproduce an existing experiment. Region/coastal holdouts, pollutant MOS, EnbPI, formal Holm comparisons and probability calibration remain work requiring matched data; the existing direct-AQI/CQR evaluator is a partial implementation.

At least 100 stations with a year of valid matched forecast/target history is required for the national study. Sparse candidate 16-hour coverage alone is insufficient for a full gas-window AQI target. All baselines use identical rows. Report missing support, date-blocked confidence intervals, severity/season/region strata, dominant-pollutant bias and ablations. A marginal pollutant interval cannot be described as simultaneous AQI coverage.

No automated model activation follows from a positive average metric. The production station-support, temporal, spatial, severity, uncertainty and advisory gates must all have evidence. Paper metrics are generated from accepted result JSON, never typed into prose.
