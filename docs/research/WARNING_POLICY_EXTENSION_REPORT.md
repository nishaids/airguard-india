# Exploratory warning operating points

Checkpoint: 2026-10-13T19:16:03.423817+00:00. Research branch; code checkpoint `9ac8b5a607246ced7150bfa47591c3398d72b5d8`. Final test remains sealed.

History-available population: 31,928 outcomes including censored Severe categories. These are newer exploratory learners and must not replace the frozen paper's weather-only warning numbers.

| Policy | Under-warning | Over-warning | Serious under-warning | Poor+ under-warning |
| --- | --- | --- | --- | --- |
| persistence | 16.421% | 16.800% | 1.704% | 43.121% |
| ridge_history | 19.961% | 16.509% | 2.543% | 79.262% |
| ridge_persistence_residual | 19.957% | 16.496% | 2.540% | 79.186% |
| lgbm_history | 19.018% | 15.983% | 2.875% | 77.542% |
| max_persistence_ridge | 12.108% | 22.792% | 1.466% | 43.020% |
| quantile_0.5 | 22.144% | 11.526% | 3.436% | 82.094% |
| quantile_0.6 | 17.602% | 15.948% | 2.600% | 72.205% |
| quantile_0.7 | 13.734% | 21.483% | 2.023% | 64.416% |
| quantile_0.75 | 11.905% | 25.539% | 1.766% | 59.965% |
| quantile_0.8 | 10.163% | 29.526% | 1.450% | 54.021% |
| quantile_0.9 | 6.386% | 42.583% | 1.005% | 37.860% |
| quantile_0.95 | 4.435% | 55.750% | 0.780% | 29.009% |

No policy is selected: a defensible error-cost ratio has not been specified. A higher quantile reduces missed categories while increasing excess alerts, and aggregate under-warning does not establish vulnerable-cohort conditional control or clinical benefit. Primary P0-P3 calibration remains pending genuine CAMS comparisons.
