# Development model selection: NOT READY

Checkpoint: 2026-10-13T19:16:03.423817+00:00. Research branch; code checkpoint `9ac8b5a607246ced7150bfa47591c3398d72b5d8`. Final test remains sealed.

No primary model is selected. The current 72-date operational join has no protocol-eligible complete rolling fold. The sealed protocol requires training-only tuning, identical baseline pairs and mean rolling-fold MAE selection with declared Ridge/residual ties; retain raw CAMS if no learned candidate improves that criterion. A stronger persistence result must still be reported honestly.

Direct/residual Ridge, LightGBM and XGBoost, spatial holdouts, fixed-learner ablation, uncertainty, advisory and paired-statistics infrastructure are implemented and tested on synthetic fixtures. Their real primary experiments remain blocked by archive coverage. The refreshed preflight records `fitting_performed=false`.

The preserved paper establishes Weather Ridge versus climatology, not versus raw CAMS; its History Ridge gain over persistence is not established. The exploratory extension does not select the primary learner. No `MODEL_SELECTION_LOCK` or surrogate lock has been created.
