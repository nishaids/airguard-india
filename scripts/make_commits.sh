#!/usr/bin/env bash
# Build a phase-wise commit history that tells the project story.
#
# Run once, from the repository root, after `python run_all.py` has completed:
#
#     bash scripts/make_commits.sh
#
# Each commit groups the files that belong to one phase of the work, so a reader
# of `git log` sees the sequence in which the project was actually built rather
# than a single undifferentiated change.

set -euo pipefail
cd "$(dirname "$0")/.."

commit() {
  local message="$1"; shift
  git add -- "$@" 2>/dev/null || true
  if git diff --cached --quiet; then
    echo "  (nothing staged for: ${message%%$'\n'*})"
    return 0
  fi
  git commit -q -m "$message"
  echo "  committed: ${message%%$'\n'*}"
}

echo "Building phase-wise history..."

# --- Phase 0: scaffold ------------------------------------------------------ #
commit "chore: scaffold repository, configuration and pinned dependencies

Adds the project skeleton, the single source of configuration truth and the
pinned runtime. config.py carries the global seed, the CPCB National AQI
breakpoints, the documented event windows and the academic metadata, so no
module re-derives any of them.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  .gitignore LICENSE requirements.txt src/config.py src/__init__.py

# --- Phase 1: acquisition and provenance ------------------------------------ #
commit "feat(data): acquire the dataset with a machine-verified provenance record

Implements both acquisition paths and emits an audit trail a reviewer can
re-verify independently: SHA-256 checksums for every file, the licence string
scraped from the live dataset page at download time rather than assumed, and a
column-level schema profile rendered as a figure.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/data/__init__.py src/data/acquire.py data/raw/PROVENANCE.json \
  reports/dataset_provenance.md

# --- Phase 2: quality ------------------------------------------------------- #
commit "feat(data): data quality assessment and city retention gates

Assesses missingness, duplicates, physical plausibility, unit sanity and
outliers under two rules before any cleaning decision is taken. Verifies
empirically that AQI_Bucket is reproducible from AQI, which establishes the
label-leakage hazard rather than assuming it. Applies two completeness gates and
records a reason for every excluded city.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/data/quality.py results/data_quality_report.json

# --- Phase 3: cleaning ------------------------------------------------------ #
commit "feat(data): cleaning with an event-aware outlier policy and measured imputation

The outlier rule separates sensor artefacts from genuine pollution episodes on
physical grounds and exempts documented Diwali, crop-burning and lockdown
windows, so no real event is removed as an outlier.

The imputation strategy is selected by a masking experiment over five
candidates rather than by preference. Linear interpolation scores best but is
non-causal, so the best causal strategy is adopted instead and the cost of that
constraint is reported as a measured number.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/data/clean.py results/cleaning_report.json

# --- Phase 4: features and the Health Advisory Index ------------------------ #
commit "feat(features): engineered feature matrix and the Health Advisory Index

Adds temporal, cyclical, event, per-city lag, rolling and pollutant-ratio
features, leakage-safe encodings and a three-stage selection filter fitted on
training rows only.

The Health Advisory Index is the project's methodological contribution: a
vulnerability-weighted composite for seven cohorts, grounded in cited
exposure-response literature. Its properties are asserted in code, including the
guarantee that it is never less protective than the official AQI.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/features/__init__.py src/features/hai.py src/features/build.py \
  results/feature_engineering_report.json results/hai_divergence.json

# --- Phase 5: safe windows -------------------------------------------------- #
commit "feat(features): safe-exposure window recommender from the hourly record

Builds the recommendation from instantaneous hourly concentrations rather than
the supplied hourly AQI column, because that column is a 24-hour rolling
quantity and is nearly flat within a day by construction. Both diurnal swings
are measured and reported so the choice is justified rather than asserted.

Degrades to a seasonal calendar if the hourly file is unavailable, and declares
the degradation in its output.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/features/safe_window.py results/safe_windows.json

# --- Phase 6: exploratory analysis ------------------------------------------ #
commit "feat(eda): exploratory figures, statistics and the numbered insight list

Univariate, bivariate, multivariate, temporal and event analysis. Every figure
carries a written interpretation that states the modelling consequence it
drives; no chart is left uninterpreted.

Quantifies both natural experiments in the record with significance tests: the
2020 lockdown and the Diwali window against a matched seasonal baseline.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/eda/__init__.py src/eda/plots.py results/eda_statistics.json \
  results/eda_insights.json

# --- Phase 7: supervised models --------------------------------------------- #
commit "feat(models): regression, classification and clustering

Five regression families and six classification configurations, each scored
against a persistence baseline so that the learned models' actual contribution
is visible rather than implied by a high R-squared.

Class imbalance is addressed by comparing class weighting against SMOTE head to
head rather than assuming either. The leakage a same-day formulation would
suffer is demonstrated by experiment.

City archetypes are discovered unsupervised and labelled by composition with the
overall burden level reported separately, so a cluster below the cross-city mean
on every pollutant is not mislabelled as led by any one species.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/models/__init__.py src/models/common.py src/models/train_regression.py \
  src/models/train_classification.py src/models/train_clustering.py \
  results/evaluation_regression.json results/evaluation_classification.json \
  results/evaluation_clustering.json

# --- Phase 8: tuning, evaluation, explainability ---------------------------- #
commit "feat(models): hyperparameter optimisation, comparison tables and SHAP

Randomised search over large spaces and an exhaustive grid over the
one-dimensional Ridge penalty, both under TimeSeriesSplit, with an explicit
cost-against-gain assessment rather than a bare improvement figure.

Adds the master comparison tables, residual and learning-curve diagnostics, the
per-city breakdown, the lockdown stress-test slice, an error analysis that
isolates the health-critical failure mode, and TreeSHAP global and local
explanations.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/models/tune.py src/models/evaluate.py src/models/explain.py \
  results/tuning_report.json results/explainability.json \
  results/error_analysis.json results/evaluation_summary.json \
  results/final_model_selection.md results/master_comparison_regression.csv \
  results/master_comparison_classification.csv \
  results/master_comparison_clustering.csv

# --- Phase 9: policy simulator ---------------------------------------------- #
commit "feat(simulate): counterfactual policy simulator

Re-scores the whole historical record from first principles under a chosen
emission reduction and reports cohort advisory-days averted rather than an
abstract index change.

States plainly what it does not claim: the reduction is an input, not a
prediction, and no atmospheric chemistry is modelled. Sanity-checked against the
measured effect of the 2020 lockdown, which it was not fitted to.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/simulate/__init__.py src/simulate/policy.py results/policy_simulation.json

# --- Phase 10: application -------------------------------------------------- #
commit "feat(app): Streamlit application with a trilingual cohort advisory

Four pages over the pipeline artefacts: the cohort-resolved forecast with
what-if sliders, the city risk atlas, the counterfactual simulator and the model
insights page.

Production hygiene: cached artefact loading, input validation returning a typed
result rather than raising, graceful fallback for out-of-range cities and dates,
and a drift check against the training distribution.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  app/

# --- Phase 11: models and figures ------------------------------------------- #
commit "chore(artifacts): versioned model artefacts and generated figures

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  models/ reports/figures/

# --- Phase 12: reports and responsible-AI artefacts ------------------------- #
commit "docs: review documents, data card, model card and phase notebooks

All three review documents, both cards and the README results table are
generated from results/*.json. No metric anywhere in them is written by hand, so
re-running the pipeline updates every document with it.

The notebooks carry orchestration and narrative only; all logic is imported from
src/, so they cannot drift from the code that produced the committed results.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  src/report/ notebooks/ reports/ README.md DEPLOY.md

# --- Phase 13: reproduction and verification -------------------------------- #
commit "test: smoke tests, one-command pipeline runner and a Definition-of-Done audit

run_all.py reproduces every artefact from a fresh clone in dependency order.

The smoke tests exercise every city against every cohort at four dates each,
which is the evidence behind the claim that the application does not raise on
any valid input. The audit verifies each completion criterion by inspecting the
artefacts on disk rather than by assertion in prose.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  run_all.py tests/ scripts/ results/definition_of_done.json

# --- Anything remaining ----------------------------------------------------- #
commit "chore: remaining generated artefacts

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  .

echo
echo "History:"
git log --oneline
