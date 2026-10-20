# Development model selection: NOT READY

Checkpoint: 20 October 2026 (IST), branch `research/station-calibration`. Supersedes the 13 October text, preserved in git history. Final test remains sealed.

No primary model is selected. The current 103-date operational join has no protocol-eligible complete rolling fold; the first that can qualify is fold_05, which needs CAMS through 2025-11-16 (10 more verified files; see CAMS_STATION_MATCHING_REPORT.md). The join was rebuilt on 2026-10-20 with identical hashes. The sealed protocol requires training-only tuning, identical baseline pairs and mean rolling-fold MAE selection with declared Ridge/residual ties; retain raw CAMS if no learned candidate improves that criterion. A stronger persistence result must still be reported honestly.

Direct/residual Ridge, LightGBM and XGBoost, spatial holdouts, fixed-learner ablation, uncertainty, advisory and paired-statistics infrastructure are implemented and tested on synthetic fixtures. Their real primary experiments remain blocked by archive coverage. The refreshed preflight records `fitting_performed=false`.

The locked station eligibility requirement is 120 valid training targets per station. There are only 103 acquired development dates in total; every fold has zero eligible training stations and missing declared dates. No window, station minimum or protocol rule was relaxed.

The preserved paper establishes Weather Ridge versus climatology, not versus raw CAMS; its History Ridge gain over persistence is not established. The exploratory extension does not select the primary learner. No `MODEL_SELECTION_LOCK` or surrogate lock has been created.
