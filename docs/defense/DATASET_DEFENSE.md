# Dataset and issue-time defense

The retained measured table contains 107,280 station-days: 64,799 valid and 42,481 rejected targets, 179 usable stations in 100 parsed cities. Its dates are 2025-02-19 through 2026-10-07; rejection records are retained. The final 90 days, 2026-07-10 through 2026-10-07, remain sealed at this checkpoint. In the NON_CAMS_PRELIMINARY development comparison, strict Ridge minus climatology MAE is -8.96 AQI (95% date-block interval [-12.49, -5.61]). Conditional history Ridge minus persistence is +0.61 ([-0.41, 1.70]); an improvement is not established. Every strict baseline forecast on 363 evaluated censored Severe validation days fell below 401. This serious failure is disclosed prominently. These are not CAMS-comparison or final-test results.

**Is this synthetic?** Research targets are acquired station measurements. CAMS/weather are real model output, not measured targets. Synthetic fixtures exercise failures in tests and must never become evidence of forecast skill.

**Why trust it?** Preserve original files and hashes, source/sensor identity, units, time windows, rejection reasons and deterministic reconstruction. Trust is bounded: QC cannot establish instrument truth, OpenAQ publication latency is unknown, and station coverage is uneven.

**Why three pollutants?** The engine enforces the declared minimum including PM2.5 or PM10. Unsupported ppb station gases are excluded without invented temperature/pressure. This measured cohort’s valid targets use PM2.5, PM10 and O3. NO2/SO2/CO target support is zero here.

**Issue-time rules:** target D issued D-1 20:00 IST; measurements must end by 17:00 IST on D-1. Weather uses archived forecast provenance. ADS init + lead must equal valid time. Detection acquisition time alone does not prove FIRMS publication time, so strict historical fire features remain withheld. The documented CAMS 00 UTC dissemination bound is distinct from ADS retrieval latency; per-run historical release logs remain a limitation.

The original protocol’s target-matched pollutant support is an evaluation annotation. A forecast feature cannot use tomorrow’s missingness or QC. Freeze operational support before issue time; disclose this correction to the implementation without rewriting the locked protocol or previous hashes.

Final targets must not enter selection. The new archive plan covers development only; acquiring held-out forecasts and reading final labels require the separately committed selection lock and one-shot evaluation gate.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
