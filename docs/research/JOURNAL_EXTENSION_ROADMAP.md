# Journal extension roadmap

The six-page IEEE conference paper in `paper/conference_final/` is a frozen snapshot and is not changed by anything here. A journal extension must rest on **new evidence**, gathered and analysed after that snapshot, and must say so. Post-paper results are never written as if they existed at the conference paper's evaluation date.

## What the conference paper establishes, and what it does not

| Established in the paper (non-CAMS, measured targets) | Not established |
| --- | --- |
| Weather Ridge beats climatology on held-out dates (MAE 8.96 lower, 95% block interval [-12.49, -5.61]) | Anything about CAMS or its correction |
| Measured CPCB-style targets with censored Severe days, 179 stations, 100 cities | History Ridge beating persistence |
| Temporal and geographic holdouts, sealed final test | Calibrated intervals in polluted categories |
| | A warning policy that is optimal |

## Experiments that would materially strengthen a journal version

Ordered by how much each would change what can be claimed.

1. **Primary operational CAMS calibration** (the main contribution). Archived 00 UTC operational forecasts, matched to stations, compared on identical station-days against raw CAMS, persistence, climatology and the Ridge baselines, under the locked protocol. *Status*: archive 10 of 36 files; the first eligible fold needs CAMS through 2025-11-16 (`CAMS_STATION_MATCHING_REPORT.md`). *Gate*: `MODEL_SELECTION_LOCK.md` from development data only.
2. **One-time sealed final test** (10 July to 7 October 2026) of the locked model, run once after written author approval. *Gate*: `FINAL_TEST_READY_FOR_AUTHOR_APPROVAL.md` must read READY.
3. **Winter and Severe evidence.** The development window must include the 2025-26 winter so that Poor-or-worse and censored Severe days are numerous enough to evaluate the tail separately: lower-bound shortfall, reach of the Severe threshold, serious under-warning.
4. **Uncertainty under shift.** Split and Mondrian (by category) conformal intervals and conformalised quantile regression, reported by pollution category and region, with calibration-set sizes. Only marginal coverage is guaranteed; conditional coverage is measured, not claimed.
5. **Warning-policy evaluation.** Conservative and balanced operating points with an explicit two-sided cost function; report under- and over-warning, missed Poor-or-worse days and false alerts. No policy called universally optimal.
6. **Geographic transfer and survivorship.** Leave-city-out and leave-cluster-out on the CAMS data, plus the frozen-cohort sensitivity, stating that the monitor network is not nationally representative.
7. **Prospective verification.** The fixed 20:00 IST ledger (108 forecasts by 20 October 2026, 2 verified days) scored only after it holds enough verified days; the 30-day gate is in `research_readiness.json`.
8. **Comprehension study**, if ethics approval is obtained (`PUBLIC_IMPACT_EVALUATION_PLAN.md`).
9. **Reproducibility package**: clean-clone reproduction of every number from committed scripts, with dataset hashes and the lock.

## What a journal version must not do

Claim a first, state of the art, health benefit, guaranteed coverage or an optimal policy; use CAMS reanalysis or Open-Meteo's past-hours CAMS series in place of archived forecasts; or present the exploratory non-CAMS extensions as primary results.

## Practical order

Archive completion (1) runs unattended for days. While it runs, nothing else in the list can be finished except 7 (which only needs time) and 8 (which needs approval). After the archive: 1, then 3 to 6 on the same folds, then 2 once, then 9.
