# AirGuard India research continuation checkpoint



Generated 2026-10-12T02:49:26.445552+00:00; values describe identified snapshots, not future completed downloads.



1. **Branch and checkpoint commit:** `research/station-calibration` at `def4158d93e855622e0ba409f6dee617dd54722b`. No branch switch, reset, production merge, push or deployment.

2. **Inherited from Claude:** checkpoint 5790c3a, locked v3.1 protocol/history, metadata station catalogue/selection, sensor QC, availability guards, target/metric/split infrastructure and running OpenAQ/weather/FIRMS acquisition. Preserved.

3. **Completed by Codex:** checksum recovery, bounded pagination checks, complete-row measured QC/rejection ledgers, causal feature QC, separate frozen non-CAMS plan, audited temporal/spatial/ablation/calibration/statistical/advisory implementation, local reproduction, prospective audit, source-only operational fixes, literature matrix and generated IEEE skeleton.

4. **Downloads:** OpenAQ 180/181 selected stations (6,331,429 raw rows); weather 151/151; FIRMS 123/123. Checksum audit PASS, 921 recorded files. Proxy CAMS preserved and unused. Finite helper state: `FINISHED_WITH_FAILURES`.

5. **Usable measured snapshot:** 179 stations/100 cities; 166 stations meet the descriptive full-window 120-day count. 552 dates with valid targets across ['2025-02-19', '2026-10-07']; 596 study days; complete station calendars=True. 107,280 station-days, 64,799 valid targets. Dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; feature `non-cams-preliminary-v1`. The experiment uses dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; identities match=True.

6. **Quality exclusions:** 42,481 retained rejected targets; 383 censored Severe days. Hourly exclusion counts: `{"invalid_value_or_unit": 78, "provider_flagged": 15177, "stuck_sensor_run": 36746, "under_75_percent_coverage": 851125, "zero_reading": 90090}`. PM2.5>PM10/spikes flagged and retained. Raw exclusions remain addressable; reasons may overlap across pollutants.

7. **Leakage audit:** 107,280 rows passed the strict builder guard; runner independently checks values/provenance. Final 2026-07-10..2026-10-07 remains unscored. Strict inputs: 48-hour-offset weather, calendar, coordinates. Measured history/persistence are latency-conditional; fires withheld. Protocol hash `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8` unchanged.

8. **Baselines:** non-CAMS training-only climatology and fixed Ridge variants; conditional persistence/history Ridge on paired available rows. Legacy city model is not comparable to this station dataset. Required raw operational CAMS baseline remains incomplete.

9. **Experiments:** 24 expanding/sliding temporal evaluations; 36 metadata-assigned city/cluster/station/region holdouts (0 insufficient entries); category/extreme/season/region diagnostics; weather/history ablation; paired date-block/Holm analysis; 12 uncertainty and advisory calibration folds. These are preliminary empirical results. Local raw-cache reconstruction current/pass=True; clean-clone primary reproduction pending. Tests: status=PASS, current=True, counts={'tests': 580, 'failures': 0, 'errors': 0, 'skipped': 5, 'collected': 580, 'passed': 575, 'deselected': 4}.

10. **CAMS-blocked experiments:** raw CAMS versus Direct ML/Residual Ridge/Residual LightGBM/Residual XGBoost, CAMS ablation, primary uncertainty/advisory comparisons and definitive final-test evaluation. Operational-file/unit/run/availability evidence and pre-issue support policy must be validated before primary fitting.

11. **Prospective forecasts:** 12 immutable forecasts/1 target days; 0 bound stations. 4 production schedules audited active; source fixes are undeployed. 12 old issuance SHAs absent and not reconstructed.

12. **Prospective verification:** 0 verified days; 0 outcomes due at audit; 0 availability violations; 0 pairing mismatches. Thirty-day gate=False; unbound records cannot be paired retrospectively.

13. **Readiness:** `COLLECTING_NOT_RESEARCH_READY`, 5/17 primary gates. Passing: research_question_locked, protocol_locked, cpcb_method_verified, prospective_logging_active, security_passed. Pending: literature_review_complete, issue_time_dataset_validated, baseline_complete, rolling_origin_complete, spatial_validation_complete, ablation_complete, uncertainty_complete, extreme_event_analysis_complete, advisory_evaluation_complete, statistical_comparison_complete, reproducibility_passed, 30_day_track_record_complete. Preliminary results never satisfy primary CAMS gates.

14. **IEEE draft:** `paper/station_calibration_skeleton.tex`, six intended pages; current-source compiler success=True, page-count verified=False. Generated from exact result artifacts; acquisition/experiment identities explicit. CAMS result placeholders and author/venue acceptance remain. No submission readiness claim.

15. **Manual action:** sign into Copernicus ADS, accept CAMS global forecast dataset terms, and configure its personal token privately in user-home `.cdsapirc` with ADS API URL. See [ADS_MANUAL_SETUP.md](ADS_MANUAL_SETUP.md). Do not paste the token into chat. Genuine forecast import and unit/availability checks follow before any primary fitting. A later production release needs separate user approval.



Evidence: `results/research/continuation_checkpoint.json`, `measured_dataset.json`, `preliminary_latest.json`, `prospective_audit.json`, `test_validation.json`, `literature_fulltext_review.json` and `paper_skeleton.json`.



Downloads can continue after this snapshot; the finite helper regenerates artifacts after the observed workers finish. Status and completion flags are derived from stage outcomes. It does not mutate Git or deploy models.
