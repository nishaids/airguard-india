# Raw CAMS against station measurements — exploratory development diagnostic

**Status: EXPLORATORY, NOT THE PRIMARY EXPERIMENT.** No model was fitted, tuned or selected. Two baselines the locked protocol already defines were scored on the same station-days of the guarded development join, which ends before the sealed final test. Script: `scripts/explore_raw_cams_development.py`; numbers: `results/research/extensions/raw_cams_development_diagnostic.json`.

## Result

On **9,510 station-days** (21 February to 1 June 2025, exact targets only):

| Baseline | MAE (AQI) | Bias | Category agreement | Poor-or-worse days missed |
| --- | --- | --- | --- | --- |
| Raw archived CAMS, matched pollutants (B2) | 93.4 | **+82.6** | 32% | 55% of 572 |
| Raw CAMS, all six pollutants (as the live site shows) | 93.4 | +82.6 | 32% | 55% |
| Persistence, measured 24-hour index at the cutoff (B1) | 25.7 | +1.0 | 69% | 51% |

Raw CAMS minus persistence, paired MAE difference: **+67.7 AQI** (95% seven-day block-bootstrap interval 60.8 to 77.5, 91 dates).

## Why

**Ozone.** CAMS ozone averaged 140 µg/m³ against 54 measured (2.6 times), so ozone set the CAMS index on 81% of station-days, against 15% in the measurements. PM2.5 was close on average (46 against 43); PM10 was higher (149 against 103). The bias was worst in the North (MAE 122, bias +113) and grew from February (MAE 62) to May (107). Matched and six-pollutant indices were identical on every station-day here, because NO₂, SO₂ and CO never set the index.

The raw model is too high on ordinary days yet still misses over half of the Poor-or-worse days: it is mostly wrong about *which* days are bad, not uniformly high.

## What follows, and what does not

- The live product shows a raw CAMS-based AQI. Since 20 October 2026 the page states these figures and warns when ozone leads the estimate. Nothing is corrected, because an uncorrected correction would be an unvalidated model.
- This is the strongest motivation yet for station calibration, and a reason to expect it to help. It is **not** evidence that calibration works: that needs the primary experiment on locked folds.
- One season only (no winter, few Poor-or-worse days). Persistence assumes a healthy feed with 3-hour latency.
