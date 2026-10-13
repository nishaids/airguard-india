# Station-cohort survivorship sensitivity

Checkpoint: 2026-10-13T20:05:39.026617+00:00. Research branch; code checkpoint `106c33eafac531a04dae99f19ec0005ae808ff6a`. Final test remains sealed.

Inherited rule: stations with at least 30 valid targets in the first fold training window, fixed for all folds; eligibility window `['2025-02-19', '2025-05-19']`. This applies the preliminary study's 30-valid-day rule, not the primary protocol's 120-day requirement.

| Cohort | Stations | Cities | Exact pairs | Severe | Weather MAE | Persistence MAE | History MAE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| paper_cohort | 171 | 97 | 38382 | 363 | 43.857 | 27.474 | 28.089 |
| frozen_cohort | 158 | 92 | 36993 | 354 | 43.517 | 27.313 | 27.926 |

The frozen cohort excludes 13 late-entry stations. Weather-minus-climatology remains negative and History-minus-persistence remains inconclusive; cluster and region transfer penalties remain positive. Category shares and full paired intervals are retained in the immutable extension artifact.

Catalogue metadata identify 35 monitors removed by the recent-activity rule among those reporting at the study start. They were never downloaded, so this sensitivity cannot restore lost monitors or resolve complete survivorship bias. No historical paper result is replaced.
