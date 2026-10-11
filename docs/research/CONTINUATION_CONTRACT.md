# Continuation contract

The inherited v3.1 YAML and its lock are unchanged. This contract records the
user's later restriction against using the short-lead CAMS proxy for the
operational primary comparison. No protocol amendment or retrospective
rewriting is implied.

**Stream A:** genuine current forecasts frozen before the issue cutoff, with
immutable issue artifacts. Production remains on the deployed prospective v1
protocol; new experimental corrections are never deployed by this workflow.

**Stream B:** historical measured targets under v3.1 QC. The independent
`NON_CAMS_PRELIMINARY` plan is frozen before fitting. Strict predictor groups
are archived 48-hour-offset weather, calendar and coordinates. Persistence and
measured-history Ridge are separate sensitivities conditional on OpenAQ's
assumed healthy-feed latency. Historical publication timestamps are absent.
FIRMS acquisition timestamps alone are insufficient proof of publication;
fire predictors are withheld from the strict preliminary experiment.

Station/catalogue selection is inherited and unchanged. It is based on current
catalogue metadata, not an historical contemporaneous station inventory. This
survivorship limitation must be disclosed. The preliminary eligibility check
uses training-window coverage only, with its own declared 30-day minimum; it
does not claim acceptance under the full primary protocol's 120-day threshold.

The original builder matches CAMS to the pollutant support observed in a target
day. That support is outcome information. It may annotate a like-for-like
evaluation, but cannot choose an issued predictor or the baseline added back
to a residual prediction. A future primary builder must freeze pollutant
support using pre-issue metadata and use `cams_aqi_frozen` in the model ladder.
It must report differences from the preregistered matched-support analysis
transparently, before primary fitting. The old proxy builder is explicitly
blocked; its source and data remain available for audit.

Primary models are Raw CAMS, Direct ML, Residual Ridge, Residual LightGBM and
Residual XGBoost. The residual is measured AQI minus the frozen CAMS AQI, with
that same frozen baseline added to the predicted residual. Severe lower bounds
are excluded from regression fitting and exact regression errors.

The final 90 days (2026-07-10 through 2026-10-07) are removed before preliminary
fitting or evaluation. Quality reporting may count those records; it cannot
select a model, station, hyperparameter, feature or advisory policy from them.
No final-test result is produced by this continuation.

Primary readiness gates remain unsatisfied by preliminary results. The primary
archive state is `PENDING_MANUAL_ADS_CREDENTIAL`. The 30-day prospective gate
requires both actual elapsed calendar time and actual verified target days.
