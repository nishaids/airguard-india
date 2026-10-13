# Exploratory uncertainty findings

Checkpoint: 2026-10-13T19:16:03.423817+00:00. Research branch; code checkpoint `9ac8b5a607246ced7150bfa47591c3398d72b5d8`. Final test remains sealed.

Nominal 90% intervals; populations must not be interchanged. Delayed online updates use outcomes from D-2 or earlier. Their censored contributions are lower-bound nonconformity scores, not exact errors. No conditional-coverage or operational guarantee is claimed.

| Population | Method | Exact coverage | Mean width | Very Poor coverage | Severe upper >=401 |
| --- | --- | --- | --- | --- | --- |
| all_pairs | split@weather_ridge (paper) | 0.8756 | 169.19 | 0.0871 | 0/363 |
| all_pairs | rolling30@weather_ridge | 0.8969 | 180.24 | 0.2041 | 0/363 |
| all_pairs | adaptive@weather_ridge | 0.9020 | 184.39 | 0.2628 | 0/363 |
| history_pairs | split@weather_ridge | 0.8708 | 167.83 | 0.1036 | 0/306 |
| history_pairs | split@persistence | 0.8928 | 121.92 | 0.6845 | 250/306 |
| history_pairs | split@ridge_history | 0.8783 | 114.67 | 0.3523 | 81/306 |
| history_pairs | split@ridge_persistence_residual | 0.8782 | 114.65 | 0.3512 | 81/306 |
| history_pairs | scaled@ridge_persistence_residual | 0.8822 | 105.73 | 0.6068 | 216/306 |
| history_pairs | mondrian_persistence_category@ridge_persistence_residual | 0.8868 | 106.43 | 0.6120 | 116/306 |
| history_pairs | rolling30_scaled@ridge_persistence_residual | 0.8903 | 109.06 | 0.6246 | 232/306 |
| history_pairs | adaptive_scaled@ridge_persistence_residual | 0.8936 | 111.02 | 0.6321 | 231/306 |

Adaptive weather calibration improves marginal coverage and Very Poor coverage, but still has no upper endpoint reaching 401 on the 363 Severe outcomes. Persistence-based intervals perform better in the severe tail on history-available pairs. Lower-bound compatibility is not coverage of the unknown true Severe index. These methods remain exploratory and unselected.
