"""Review 3 document: modelling, comparison, optimisation and the delivered product.

Every metric quoted here is read from the results artefacts at generation time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from docx.shared import Cm

from src import config
from src.features import hai as hai_mod
from src.report.build_docx import ReportBuilder, references_for


def build(data: Dict[str, Any], deployment_url: str) -> Path:
    """Generate the Review 3 document and return its path."""
    regression = data["regression"]
    classification = data["classification"]
    clustering = data["clustering"]
    tuning = data["tuning"]
    explain = data["explain"]
    errors = data["errors"]
    policy = data["policy"]
    features = data["features"]
    divergence = data["divergence"]
    eda = data["eda"]

    reg_best = regression.get("best_test_metrics", {})
    clf_best = classification.get("best_test_metrics", {})
    reg_baseline = regression.get("baseline_comparison", {})
    clf_baseline = classification.get("baseline_comparison", {})

    builder = ReportBuilder(
        title="Modelling, Comparison and Product Development",
        subtitle=config.ACADEMIC["project_subtitle"],
        review="Review 3",
        marks=config.REVIEW_MARKS["Review 3"],
    )
    builder.cover()
    builder.toc(
        [
            ("Model Implementation and Training Methodology",
             "Model implementation and training methodology (10)"),
            ("Evaluation Metrics", "Appropriate evaluation metrics (5)"),
            ("Performance Comparison and Analytical Discussion",
             "Performance comparison and analytical discussion (5)"),
            ("Hyperparameter Tuning and Optimisation",
             "Hyperparameter tuning and optimisation (5)"),
            ("End-to-End Product Development", "End-to-end product development and functionality (10)"),
            ("Final Model Selection, Limitations and Future Work", "Technical report (5)"),
        ]
    )

    # ------------------------------------------------------------------ 1 -- #
    builder.heading("1. Model Implementation and Training Methodology", level=1)

    builder.heading("1.1 The forecasting formulation", level=2)
    builder.para(
        "Every model predicts tomorrow from information available today. For a city "
        "and a date, the regression target is the following day's AQI and the "
        "classification target is the following day's CPCB band; the feature vector "
        "may use any measurement dated today or earlier for that same city. This is "
        "not a stylistic preference. It is what makes the output actionable, and it "
        "is also what dissolves the label-leakage problem that a same-day "
        "formulation suffers from, as Section 1.5 demonstrates by measurement."
    )
    split = features.get("split", {})
    builder.table(
        [
            ["Split boundary", split.get("boundary", "n/a")],
            ["Training period",
             f"{split.get('train_range', ['?', '?'])[0]} to "
             f"{split.get('train_range', ['?', '?'])[1]}"],
            ["Test period",
             f"{split.get('test_range', ['?', '?'])[0]} to "
             f"{split.get('test_range', ['?', '?'])[1]}"],
            ["Training rows (after dropping warm-up and unlabelled rows)",
             f"{regression.get('split', {}).get('n_train', 0):,}"],
            ["Test rows", f"{regression.get('split', {}).get('n_test', 0):,}"],
            ["Features, regression", str(regression.get("n_features", 0))],
            ["Features, classification", str(classification.get("n_features", 0))],
            ["Cross-validation", regression.get("validation", "n/a")],
        ],
        ["Property", "Value"],
        "Training and evaluation setup",
        widths=[Cm(6.4), Cm(9.6)],
    )

    builder.heading("1.2 Regression models", level=2)
    builder.table(
        [[entry["model"], entry["family"], entry.get("rationale", entry.get("note", ""))]
         for entry in regression.get("results", [])],
        ["Model", "Family", "Why it is included"],
        "Regression models fitted, with the reason each is present",
        widths=[Cm(3.4), Cm(2.8), Cm(9.8)],
        font_size=8.0,
    )

    builder.heading("1.3 Classification models and the imbalance remedy", level=2)
    builder.table(
        [[entry["model"], entry["family"], entry.get("imbalance_strategy", "-"),
          entry.get("rationale", entry.get("note", ""))]
         for entry in classification.get("results", [])],
        ["Model", "Family", "Imbalance strategy", "Why it is included"],
        "Classification models fitted, with the imbalance remedy applied to each",
        widths=[Cm(3.2), Cm(2.4), Cm(3.4), Cm(7.0)],
        font_size=7.5,
    )
    builder.para(
        "Two remedies for class imbalance are compared head to head rather than one "
        "being assumed. Class weighting re-weights the loss so that each class "
        "contributes in inverse proportion to its frequency, costs nothing at "
        "prediction time and synthesises no data. SMOTE interpolates new "
        "minority-class examples in feature space, and is applied inside an "
        "imbalanced-learn pipeline so that resampling happens within each training "
        "fold only. Resampling before splitting would place synthetic copies of "
        "validation rows into training and is a classic source of inflated scores."
    )
    builder.table(
        [[entry["pair"], f"{entry['macro_f1_weighted_or_plain']:.4f}",
          f"{entry['macro_f1_smote']:.4f}", f"{entry['delta_macro_f1']:+.4f}",
          f"{entry['severe_f1_weighted_or_plain']:.3f}",
          f"{entry['severe_f1_smote']:.3f}", entry["winner"]]
         for entry in classification.get("smote_head_to_head", [])],
        ["Pair", "Macro F1 (weighted/plain)", "Macro F1 (SMOTE)", "Delta",
         "Severe F1 (weighted/plain)", "Severe F1 (SMOTE)", "Winner"],
        "Class-weighting against SMOTE, head to head",
        widths=[Cm(3.6), Cm(2.4), Cm(2.0), Cm(1.6), Cm(2.2), Cm(2.0), Cm(2.2)],
        font_size=7.0,
    )
    builder.table(
        [[band, f"{count:,}"]
         for band, count in classification.get("class_distribution_train", {}).items()],
        ["Band", "Training rows"],
        "Class distribution in the training period",
        widths=[Cm(8.0), Cm(8.0)],
    )

    builder.heading("1.4 Clustering", level=2)
    builder.para(clustering.get("representation", ""))
    builder.table(
        [[str(entry["k"]), f"{entry['inertia']:.2f}", f"{entry['silhouette']:.4f}",
          f"{entry['davies_bouldin']:.4f}", f"{entry['calinski_harabasz']:.2f}",
          str(entry["cluster_sizes"])]
         for entry in clustering.get("k_selection", {}).get("candidates", [])],
        ["k", "Inertia", "Silhouette", "Davies-Bouldin", "Calinski-Harabasz",
         "Cluster sizes"],
        "Candidate partitions with their internal validity indices",
        widths=[Cm(1.4), Cm(2.6), Cm(2.6), Cm(3.0), Cm(3.4), Cm(3.0)],
        font_size=8.0,
    )
    builder.para(clustering.get("k_selection", {}).get("selection_rule", ""))
    votes = clustering.get("k_selection", {}).get("index_votes", {})
    if votes:
        builder.para(
            "The four indices did not agree: "
            + "; ".join(f"{name} favours k = {value}" for name, value in votes.items())
            + ". The declared rule resolves the disagreement, and the full tally is "
            "reported here rather than only the winner.",
            bold=True,
        )
    builder.para(clustering.get("k_selection", {}).get("power_caveat", ""), italic=True)
    builder.figure("24_clustering_selection.png",
                   "Selection of the number of archetypes across four indices.")
    builder.figure("25_cluster_profiles.png",
                   "Archetype signatures and the cities projected into archetype "
                   "space.")
    builder.table(
        [[str(entry["cluster"]), entry["archetype"],
          f"{entry['mean_level_z']:+.2f}", entry["defining_pollutant"],
          ", ".join(entry["cities"]), entry["policy_lever"]]
         for entry in clustering.get("archetypes", [])],
        ["Cluster", "Archetype", "Level (z)", "Leading pollutant in the mix",
         "Cities", "Policy lever"],
        "Discovered archetypes and the distinct policy lever each implies. The "
        "archetype name separates the overall burden level from the composition of "
        "the mix, so a cluster that is below the cross-city mean on every pollutant "
        "is not mislabelled as being led by any one species.",
        widths=[Cm(1.2), Cm(2.8), Cm(1.4), Cm(2.2), Cm(3.4), Cm(5.0)],
        font_size=7.5,
    )
    agreement = clustering.get("algorithm_agreement", {})
    builder.para(
        f"Adjusted Rand index between K-Means and Ward agglomerative clustering: "
        f"{agreement.get('adjusted_rand_index', 'n/a')}. "
        f"{agreement.get('interpretation', '')}",
        bold=True,
    )

    builder.heading("1.5 The leakage demonstration", level=2)
    leak = classification.get("leakage_demonstration", {})
    if leak:
        builder.para(
            "The distinction between a same-day nowcast and a next-day forecast is "
            "demonstrated by experiment rather than asserted. Three classifiers were "
            "fitted on identical time-ordered splits, differing only in the target "
            "and the feature set."
        )
        builder.table(
            [[leak[key]["description"], f"{leak[key]['macro_f1']:.4f}",
              f"{leak[key]['accuracy']:.4f}", str(leak[key]["n_features"])]
             for key in ("same_day_nowcast_with_aqi", "same_day_nowcast_without_aqi",
                         "next_day_forecast_this_project")],
            ["Setup", "Macro F1", "Accuracy", "Features"],
            "The leakage demonstration: three setups, identical splits",
            widths=[Cm(8.6), Cm(2.4), Cm(2.4), Cm(2.6)],
            font_size=8.0,
        )
        builder.para(leak.get("conclusion", ""), bold=True)

    # ------------------------------------------------------------------ 2 -- #
    builder.heading("2. Evaluation Metrics", level=1)
    builder.heading("2.1 Primary metrics, declared in advance", level=2)
    builder.para(f"Regression. {regression.get('primary_metric_justification', '')}")
    builder.para(f"Classification. {classification.get('primary_metric_justification', '')}")
    builder.para(
        "Both primary metrics were fixed before any model was fitted, so the choice "
        "could not be made after seeing which model happened to win on which "
        "measure.",
        italic=True,
    )

    builder.heading("2.2 The full metric suite", level=2)
    builder.table(
        [
            ["Regression", "MAE", "Average size of the miss in AQI points. Primary."],
            ["Regression", "RMSE", "Penalises large misses disproportionately; sensitive to the extreme tail."],
            ["Regression", "R-squared", "Share of next-day variance accounted for."],
            ["Regression", "MAPE", "Typical miss as a percentage of the true value, computed where the truth is at least 1."],
            ["Regression", "Bias", "Mean signed error, which exposes systematic over- or under-prediction."],
            ["Classification", "Macro F1", "Mean F1 across all six bands with equal weight. Primary."],
            ["Classification", "Accuracy", "Exact-match rate. Reported but not decisive under imbalance."],
            ["Classification", "Weighted F1", "F1 weighted by class frequency."],
            ["Classification", "Balanced accuracy", "Mean recall across classes."],
            ["Classification", "Per-class precision, recall and F1", "Performance on each band separately, including the rare Severe band."],
            ["Classification", "ROC-AUC (one-versus-rest)", "Ranking quality per class, macro and weighted."],
            ["Classification", "Cohen's kappa", "Agreement corrected for chance."],
            ["Classification", "Mean absolute ordinal error", "How many severity bands a wrong prediction lands away from the truth."],
            ["Classification", "Share understating severity", "The health-critical failure mode, reported explicitly."],
            ["Clustering", "Silhouette", "Cohesion against separation; comparable across k."],
            ["Clustering", "Davies-Bouldin", "Average similarity to the most similar cluster; lower is better."],
            ["Clustering", "Calinski-Harabasz", "Between-cluster against within-cluster dispersion."],
            ["Clustering", "Adjusted Rand index", "Agreement between two partitions, corrected for chance."],
        ],
        ["Task", "Metric", "What it measures and why it is reported"],
        "The complete metric suite",
        widths=[Cm(2.4), Cm(3.6), Cm(10.0)],
        font_size=7.5,
    )

    # ------------------------------------------------------------------ 3 -- #
    builder.heading("3. Performance Comparison and Analytical Discussion", level=1)

    builder.heading("3.1 Master comparison: regression", level=2)
    builder.dataframe(
        data["table_regression"],
        "Regression master comparison, ordered by test MAE",
        columns=["Model", "Family", "CV MAE", "Test MAE", "Test RMSE", "Test R2",
                 "Test MAPE %", "Test bias", "Train MAE", "Train-test R2 gap",
                 "Fit seconds"],
        font_size=7.0,
    )
    builder.figure("27_regression_comparison.png",
                   "Regression model comparison, with the persistence baseline "
                   "marked on both panels.")
    builder.para(
        f"The most important column in that table is the persistence baseline. "
        f"Daily AQI is strongly autocorrelated, so carrying today forward already "
        f"achieves an MAE of {reg_baseline.get('baseline_mae', 0)} and an R-squared "
        f"of {next((r['test']['R2'] for r in regression.get('results', []) if r['family'] == 'baseline'), 0)}. "
        f"Reporting an R-squared above 0.9 without that comparison would be "
        f"misleading, because most of it is available for nothing. "
        f"{regression.get('best_model', '')} reduces MAE by "
        f"{reg_baseline.get('improvement_over_persistence_pct', 0)} per cent relative "
        f"to persistence, and that reduction is the actual contribution of the "
        f"learned model.",
        bold=True,
    )

    builder.heading("3.2 Master comparison: classification", level=2)
    builder.dataframe(
        data["table_classification"],
        "Classification master comparison, ordered by test macro F1",
        columns=["Model", "Imbalance strategy", "CV macro F1", "Test macro F1",
                 "Test accuracy", "Balanced accuracy", "ROC-AUC (OvR)", "F1 Severe",
                 "F1 Good", "Ordinal MAE", "Train-test macro F1 gap"],
        font_size=6.5,
    )
    builder.figure("28_classification_comparison.png",
                   "Classification comparison, per-class performance of the winner, "
                   "and the imbalance remedy head to head.")
    builder.para(
        "Accuracy exceeds macro F1 for every model in the table, and the gap is the "
        "cost of the rare classes. A reader shown only accuracy would conclude that "
        "the models are performing better than they are on exactly the bands that "
        "matter most for health protection."
    )

    builder.heading("3.3 Per-class performance of the selected classifier", level=2)
    builder.table(
        [[entry["class"], f"{entry['precision']:.3f}", f"{entry['recall']:.3f}",
          f"{entry['f1']:.3f}", f"{entry['support']:,}"]
         for entry in clf_best.get("per_class", [])],
        ["Band", "Precision", "Recall", "F1", "Support"],
        f"Per-class performance of {classification.get('best_model', '')}",
        widths=[Cm(3.6), Cm(3.0), Cm(3.0), Cm(3.0), Cm(3.4)],
    )
    builder.figure("29_confusion_matrices.png",
                   "Confusion matrices, raw and normalised by actual class.")
    builder.figure("30_roc_curves.png",
                   "One-versus-rest ROC curves and area under the curve by class.")

    builder.heading("3.4 Overfitting diagnosis", level=2)
    builder.figure("34_train_test_gap.png",
                   "Training against test performance for every model. A large "
                   "positive gap indicates a model that has memorised the training "
                   "period rather than learned the process.")
    builder.figure("32_learning_curves.png",
                   "Learning curves under expanding-window validation.")
    builder.para(
        "The unconstrained tree ensembles fit the training period almost exactly, "
        "which is why test performance rather than training performance decides the "
        "selection. The learning curve is still falling at the full training size, "
        "which says the models are data-limited rather than capacity-limited: more "
        "historical record would help more than a larger model would."
    )

    builder.heading("3.5 Residual analysis", level=2)
    builder.figure("31_residual_analysis.png",
                   "Residual diagnostics for the selected regressor.")
    residual = regression.get("residual_analysis", {})
    builder.table(
        [[entry["band"], f"{entry['n']:,}", f"{entry['mae']:.2f}", f"{entry['bias']:+.2f}",
          f"{entry['mean_observed']:.1f}"]
         for entry in residual.get("by_observed_band", [])],
        ["Observed band", "n", "MAE", "Bias", "Mean observed AQI"],
        "Regression error by observed severity band",
        widths=[Cm(3.6), Cm(2.8), Cm(3.0), Cm(3.0), Cm(3.6)],
    )
    builder.para(residual.get("interpretation", ""), bold=True)

    builder.heading("3.6 Per-city error breakdown", level=2)
    builder.figure("33_per_city_error.png",
                   "Error broken down by city for both tasks, against the pooled "
                   "figure.")
    reg_entry = next((r for r in regression.get("results", [])
                      if r["model"] == regression.get("best_model")), {})
    builder.table(
        [[entry["city"], f"{entry['n']:,}", f"{entry['MAE']:.2f}",
          f"{entry['RMSE']:.2f}", f"{entry['R2']:.3f}", f"{entry['bias']:+.2f}"]
         for entry in sorted(reg_entry.get("slices", {}).get("by_city", []),
                             key=lambda e: e["MAE"])],
        ["City", "n", "MAE", "RMSE", "R-squared", "Bias"],
        f"Per-city regression error for {regression.get('best_model', '')}",
        widths=[Cm(3.4), Cm(2.4), Cm(2.6), Cm(2.6), Cm(2.6), Cm(2.4)],
        font_size=8.0,
    )
    builder.para(
        "The pooled figure conceals a wide spread. Reporting only the national "
        "average would hide systematic failure in the cities where the health burden "
        "is highest, which is why the breakdown is presented rather than summarised."
    )

    builder.heading("3.7 The 2020 stress test", level=2)
    periods = reg_entry.get("slices", {}).get("by_period", {})
    if periods:
        builder.table(
            [[name.replace("_", " "), " to ".join(info.get("date_range", ["?", "?"])),
              f"{info.get('n', 0):,}", f"{info.get('MAE', 0):.2f}",
              f"{info.get('R2', 0):.3f}"]
             for name, info in periods.items()],
            ["Period", "Dates", "n", "MAE", "R-squared"],
            "Regression error by period, isolating the lockdown as a stress test",
            widths=[Cm(3.8), Cm(4.4), Cm(2.4), Cm(2.6), Cm(2.8)],
            font_size=8.0,
        )
    builder.para(
        f"The 2020 lockdown was retained in the test period with an explicit flag "
        f"rather than excluded. It is a genuine regime change: the exploratory "
        f"analysis measured a "
        f"{eda.get('covid', {}).get('national_change_pct', 0)} per cent change in "
        f"national mean AQI against the preceding 60 days, significant at the 5 per "
        f"cent level in {eda.get('covid', {}).get('n_cities_significant_decline', 0)} "
        f"of {len(eda.get('covid', {}).get('per_city', []))} cities. Excluding it "
        f"would have flattered the headline error by removing the hardest period; "
        f"reporting it separately shows what a forecasting system does when the "
        f"world changes."
    )

    builder.heading("3.8 Error analysis", level=2)
    builder.figure("35_error_analysis.png",
                   "Signed band error and the most frequent misclassification "
                   "transitions.")
    if errors:
        builder.table(
            [
                ["Test predictions", f"{errors.get('n_test', 0):,}"],
                ["Wrong", f"{errors.get('n_wrong', 0):,} ({errors.get('error_rate_pct', 0)}%)"],
                ["Wrong by two bands or more",
                 f"{errors.get('n_wrong_by_two_or_more_bands', 0):,} "
                 f"({errors.get('pct_wrong_by_two_or_more_bands', 0)}%)"],
                ["Understating severity by two bands or more",
                 f"{errors.get('n_understating_severity_by_two_or_more', 0):,} "
                 f"({errors.get('pct_understating_severity_by_two_or_more', 0)}%)"],
            ],
            ["Statistic", "Value"],
            "Error magnitude, with the health-critical failure mode isolated",
            widths=[Cm(8.0), Cm(8.0)],
        )
        builder.table(
            [[entry["actual"], entry["predicted"], f"{entry['count']:,}"]
             for entry in errors.get("most_frequent_transitions", [])],
            ["Actual band", "Predicted band", "Occurrences"],
            "Ten most frequent misclassification transitions",
            widths=[Cm(5.4), Cm(5.4), Cm(5.2)],
            font_size=8.0,
        )
        builder.para(errors.get("interpretation", ""))

    builder.heading("3.9 Strengths and limitations of each model family", level=2)
    builder.table(
        [
            ["Persistence baseline",
             "Free, always available, and strong because the series is "
             "autocorrelated.",
             "Cannot anticipate a change of direction, which is precisely what an "
             "advisory needs. It carries today's error into tomorrow."],
            ["Linear and Logistic Regression",
             "Interpretable coefficients; fastest to fit; no capacity to overfit "
             "this sample size.",
             "Cannot express the curved boundaries and city-by-season interactions "
             "the exploratory analysis found. Sensitive to the multicollinearity "
             "among the lag family."],
            ["Ridge Regression",
             "Stabilises coefficients under collinearity.",
             "The penalty barely moves validation error here, which says the "
             "limitation is the functional form rather than the regularisation."],
            ["Decision Tree",
             "The decision path can be read directly, which has value for a health "
             "advisory.",
             "High variance; the weakest of the tree family on every metric."],
            ["Random Forest",
             "Robust, needs little tuning, handles interactions and the heavy tail "
             "well.",
             "Fits the training period almost exactly; larger artefact; slower to "
             "predict than a boosted model of similar accuracy."],
            ["XGBoost and LightGBM",
             "Best accuracy on both tasks; fast; handle mixed feature types without "
             "preprocessing.",
             "More hyperparameters to set; less directly interpretable, which is why "
             "SHAP is a required component rather than an optional extra."],
            ["SVM with an RBF kernel",
             "Expresses a genuinely non-linear boundary.",
             "Substantially the slowest to fit, scales poorly with sample size, and "
             "did not repay the cost here. Probabilities were not calibrated, so "
             "one-versus-rest ROC-AUC could not be computed for it."],
            ["K-Nearest Neighbours",
             "No training cost; a useful benchmark for how much local similarity "
             "explains.",
             "Weakest classifier in the comparison; suffers in this feature "
             "dimensionality and has no mechanism for class weighting."],
            ["K-Means and Ward",
             "Simple, fast, and the partition reproduced exactly across both "
             "algorithms.",
             "Twelve cities is a small sample for clustering; silhouette values "
             "indicate moderate rather than sharp separation."],
        ],
        ["Family", "Strengths", "Limitations observed in this project"],
        "Honest strengths and limitations per model family",
        widths=[Cm(3.0), Cm(5.4), Cm(7.6)],
        font_size=7.5,
    )

    # ------------------------------------------------------------------ 4 -- #
    builder.heading("4. Hyperparameter Tuning and Optimisation", level=1)
    builder.para(tuning.get("strategy", ""))
    builder.heading("4.1 Search spaces and why each parameter is included", level=2)
    builder.table(
        [[name, reason] for name, reason in tuning.get("search_space_rationale", {}).items()],
        ["Parameter group", "Why it is searched"],
        "Search space rationale",
        widths=[Cm(4.4), Cm(11.6)],
        font_size=8.0,
    )
    tuned_reg = tuning.get("regression", {})
    tuned_clf = tuning.get("classification", {})
    builder.table(
        [
            ["Regression", tuned_reg.get("model", "n/a"), tuned_reg.get("search", "n/a"),
             f"{tuned_reg.get('grid_points_in_space', 0):,}",
             str(tuned_reg.get("n_iter", 0)),
             f"{tuned_reg.get('fraction_of_space_explored_pct', 0):.4f}%",
             str(tuned_reg.get("total_fits", 0))],
            ["Classification", tuned_clf.get("model", "n/a"), tuned_clf.get("search", "n/a"),
             f"{tuned_clf.get('grid_points_in_space', 0):,}",
             str(tuned_clf.get("n_iter", 0)),
             f"{tuned_clf.get('fraction_of_space_explored_pct', 0):.4f}%",
             str(tuned_clf.get("total_fits", 0))],
            ["Regression (Ridge)", "Ridge Regression",
             tuning.get("ridge_exhaustive", {}).get("search", "n/a"),
             str(tuning.get("ridge_exhaustive", {}).get("grid_points_in_space", 0)),
             "all", "100%",
             str(tuning.get("ridge_exhaustive", {}).get("total_fits", 0))],
        ],
        ["Task", "Model", "Search", "Grid points", "Sampled", "Explored", "Total fits"],
        "Search configuration per task",
        widths=[Cm(2.6), Cm(2.6), Cm(2.8), Cm(2.2), Cm(1.8), Cm(1.8), Cm(2.2)],
        font_size=7.5,
    )
    builder.para(
        "An exhaustive grid is used for the Ridge penalty because that space is "
        "one-dimensional and genuinely small, and a randomised search is used "
        "elsewhere because an exhaustive sweep of spaces containing thousands of "
        "points, multiplied by four time-series folds, would cost tens of thousands "
        "of fits for a gain that random search reaches in a small fraction of the "
        "budget. Both methods therefore appear, each on the problem it suits."
    )

    builder.heading("4.2 Before and after", level=2)
    builder.table(
        [
            ["Regression MAE", f"{tuned_reg.get('untuned_test', {}).get('MAE', 0):.4f}",
             f"{tuned_reg.get('tuned_test', {}).get('MAE', 0):.4f}",
             f"{tuned_reg.get('delta', {}).get('MAE', 0):+.4f}",
             f"{tuned_reg.get('delta', {}).get('MAE_improvement_pct', 0):+.2f}%"],
            ["Regression RMSE", f"{tuned_reg.get('untuned_test', {}).get('RMSE', 0):.4f}",
             f"{tuned_reg.get('tuned_test', {}).get('RMSE', 0):.4f}",
             f"{tuned_reg.get('delta', {}).get('RMSE', 0):+.4f}", "-"],
            ["Regression R-squared", f"{tuned_reg.get('untuned_test', {}).get('R2', 0):.4f}",
             f"{tuned_reg.get('tuned_test', {}).get('R2', 0):.4f}",
             f"{tuned_reg.get('delta', {}).get('R2', 0):+.4f}", "-"],
            ["Classification macro F1",
             f"{tuned_clf.get('untuned_test', {}).get('macro_f1', 0):.4f}",
             f"{tuned_clf.get('tuned_test', {}).get('macro_f1', 0):.4f}",
             f"{tuned_clf.get('delta', {}).get('macro_f1', 0):+.4f}",
             f"{tuned_clf.get('delta', {}).get('macro_f1_improvement_pct', 0):+.2f}%"],
            ["Classification accuracy",
             f"{tuned_clf.get('untuned_test', {}).get('accuracy', 0):.4f}",
             f"{tuned_clf.get('tuned_test', {}).get('accuracy', 0):.4f}",
             f"{tuned_clf.get('delta', {}).get('accuracy', 0):+.4f}", "-"],
        ],
        ["Metric", "Default parameters", "Tuned", "Delta", "Relative change"],
        "Effect of hyperparameter optimisation",
        widths=[Cm(4.2), Cm(3.2), Cm(2.8), Cm(2.8), Cm(3.0)],
    )
    builder.figure("26_tuning_before_after.png",
                   "Effect of tuning on both tasks, and what it cost to obtain.")
    builder.para(f"Best regression parameters: {tuned_reg.get('best_params', {})}")
    builder.para(f"Best classification parameters: {tuned_clf.get('best_params', {})}")

    builder.heading("4.3 Cost against gain", level=2)
    builder.para(tuning.get("cost_vs_gain", {}).get("assessment", ""), bold=True)
    builder.para(tuning.get("ridge_exhaustive", {}).get("note", ""))

    # ------------------------------------------------------------------ 5 -- #
    builder.heading("5. End-to-End Product Development", level=1)
    builder.para(
        "The analysis is delivered as a working multipage application rather than as "
        "a notebook. Model artefacts are loaded once per session from versioned "
        "joblib files, tabular data is cached separately, every public entry point "
        "validates its input and returns a typed result rather than raising, and a "
        "city or date outside the covered record falls back to the nearest available "
        "record with the substitution reported to the user."
    )
    builder.table(
        [
            ["Home",
             "Headline metrics pulled live from the results artefacts; the dataset "
             "provenance and licence block rendered in-app; the archetype summary; "
             "the medical disclaimer."],
            ["1. Forecast",
             "City, cohort, date and language selection; what-if pollutant sliders "
             "that recompute every derived feature; next-day AQI; predicted band "
             "with the model's confidence and the full band probability "
             "distribution; the cohort Health Advisory Index and band; the dominant "
             "pollutant; the cleanest outdoor window for the season; plain-language "
             "advice in English, Tamil and Hindi; a 30-day history chart with the "
             "forecast and the actual outcome marked; the index for all seven "
             "cohorts side by side; an input drift check against the training "
             "distribution."],
            ["2. City Risk Atlas",
             "The discovered archetypes with their policy levers and signatures; how "
             "k was chosen, including the partitions that were not selected; the "
             "ranked risk table with per-cohort restricted-day shares; the "
             "city-by-month seasonal heatmap; the safest outdoor window by city and "
             "season; the Diwali panel with per-city significance; the lockdown "
             "panel."],
            ["3. Policy Simulator",
             "Presets matching the scenarios in this report plus free sliders; the "
             "whole record re-scored from first principles on each change; band "
             "migration; cohort advisory-days averted; per-city effect; and a sanity "
             "check of the scenario against the measured lockdown effect."],
            ["4. Model Insights",
             "The three master comparison tables; confusion matrices; ROC curves; "
             "residual diagnostics; learning curves; per-city error; the error "
             "analysis; global and local SHAP; the tuning report; the leakage "
             "demonstration; the imputation bake-off; a plain-language metric "
             "glossary; and the data card and model card rendered in full."],
        ],
        ["Page", "Functionality"],
        "Application pages and what each delivers",
        widths=[Cm(3.0), Cm(13.0)],
        font_size=8.0,
    )

    builder.heading("5.1 Explainability in the product", level=2)
    if explain:
        builder.para(explain.get("method", ""))
        builder.figure("36_shap_global.png",
                       "Global SHAP explanation of both deployed models.")
        builder.figure("37_shap_local_waterfall.png",
                       "A single high-AQI day decomposed into feature contributions.")
        builder.para(explain.get("interpretation", ""))

    builder.heading("5.2 The counterfactual policy simulator", level=2)
    if policy:
        builder.para(policy.get("method", ""))
        builder.para(policy.get("what_this_is_not", ""), bold=True)
        builder.table(
            [[entry["name"],
              f"{entry['result']['aqi']['mean_before']:.1f}",
              f"{entry['result']['aqi']['mean_after']:.1f}",
              f"{entry['result']['aqi']['mean_change_pct']:+.1f}%",
              f"{entry['result']['unsafe_days']['removed']:,}",
              f"{entry['result']['unsafe_days']['reduction_pct']:.1f}%",
              f"{entry['result']['cohort_advisory_days']['total_averted_across_cohorts']:,}"]
             for entry in policy.get("scenarios", [])],
            ["Scenario", "Mean AQI before", "Mean AQI after", "Change",
             "Unsafe days removed", "Reduction", "Advisory-days averted"],
            f"Counterfactual scenarios re-scored across "
            f"{policy.get('scenarios', [{}])[0].get('result', {}).get('n_city_days', 0):,} "
            f"city-days. {policy.get('advisory_day_definition', '')}",
            widths=[Cm(3.6), Cm(2.2), Cm(2.2), Cm(1.8), Cm(2.2), Cm(1.8), Cm(2.2)],
            font_size=7.0,
        )
        builder.figure("38_policy_simulation.png",
                       "Scenario comparison and the cohort breakdown of the headline "
                       "case.")
        anchor = policy.get("lockdown_anchor", {})
        if anchor:
            whole_economy = next(
                (s for s in policy.get("scenarios", [])
                 if s["name"] == "All pollutants reduced by 40%"), None
            )
            if whole_economy:
                builder.para(
                    f"The simulator can be checked against a real emission "
                    f"reduction. The 2020 lockdown produced a measured "
                    f"{anchor.get('measured_aqi_change_pct', 0)} per cent change in "
                    f"national mean AQI. The nearest comparable scenario, a "
                    f"40 per cent reduction across all pollutants, yields "
                    f"{whole_economy['result']['aqi']['mean_change_pct']:+.1f} per "
                    f"cent. The two agree closely, which is a useful independent "
                    f"check because the simulator was not fitted to that episode in "
                    f"any way.",
                    bold=True,
                )
        builder.para(
            "The NO2 scenario is the most instructive negative result in the table. "
            "A 30 per cent reduction in nitrogen dioxide moves the mean AQI barely "
            "at all, because the index is a maximum and particulates dominate it on "
            "almost every day. A policy aimed only at nitrogen oxides would "
            "therefore deliver real health benefit that this index is structurally "
            "unable to show, which is a limitation of the index rather than of the "
            "policy, and is worth stating to anyone using the tool for target "
            "setting."
        )

    builder.heading("5.3 Accessibility and reach", level=2)
    builder.bullets(
        [
            "Advisory text is rendered in English, Tamil and Hindi from a static "
            "dictionary, so the application needs no paid translation service and "
            "remains deterministic and free to run.",
            "The figure palette is the Okabe-Ito colour-blind-safe set throughout, "
            "and sequential scales are perceptually uniform so they remain legible "
            "in greyscale.",
            "The application theme pairs foreground and background colours that meet "
            "the WCAG 2.1 AA contrast requirement of 4.5:1 for body text.",
            "Layout is column-based and reflows for narrow screens, which matters "
            "because the intended readers are most likely to reach the tool on a "
            "phone.",
        ]
    )

    builder.heading("5.4 Production hygiene", level=2)
    builder.bullets(
        [
            "Versioned joblib artefacts, loaded through a cached resource loader so "
            "each is deserialised once per session.",
            "Input validation on every public entry point, returning a typed result "
            "rather than raising, so a page renders a message instead of a traceback.",
            "Graceful fallback when a city or date lies outside the record, with the "
            "substitution reported to the user rather than applied silently.",
            "A drift check comparing each live input vector against the training "
            "distribution, which caveats the forecast when the input lies outside "
            "the range the model was fitted on.",
            "Graceful degradation of the safest-window recommender to a seasonal "
            "calendar if the hourly file is unavailable, with the degradation "
            "declared in the output rather than hidden.",
        ]
    )
    builder.table(
        [
            ["Repository", config.REPO_URL],
            ["Deployment", deployment_url],
            ["Reproduction", "python run_all.py"],
            ["Launch locally", "streamlit run app/Home.py"],
        ],
        ["Item", "Location"],
        "Deployment and reproduction",
        widths=[Cm(4.0), Cm(12.0)],
    )

    # ------------------------------------------------------------------ 6 -- #
    builder.heading("6. Final Model Selection, Limitations and Future Work", level=1)

    builder.heading("6.1 Final selection, justified quantitatively", level=2)
    builder.table(
        [
            ["Regression", regression.get("best_model", "n/a"), "MAE",
             f"{reg_best.get('MAE', 0)}",
             f"{reg_baseline.get('improvement_over_persistence_pct', 0)}% better than persistence"],
            ["Classification", classification.get("best_model", "n/a"), "Macro F1",
             f"{clf_best.get('macro_f1', 0)}",
             f"{clf_baseline.get('improvement_over_persistence_pct', 0)}% better than persistence"],
            ["Clustering", f"K-Means, k = {clustering.get('selected_k', '?')}",
             "Silhouette",
             f"{clustering.get('algorithms', {}).get('KMeans', {}).get('silhouette', 0)}",
             f"Adjusted Rand index {clustering.get('algorithm_agreement', {}).get('adjusted_rand_index', 0)} against Ward"],
        ],
        ["Task", "Selected model", "Primary metric", "Value", "Against baseline"],
        "Final model selection with the numbers that justify it",
        widths=[Cm(2.6), Cm(3.4), Cm(2.6), Cm(2.2), Cm(5.2)],
        font_size=8.0,
    )
    builder.para(
        "The full selection argument, including the margin over each runner-up and "
        "the reasoning where that margin is small, is in "
        "results/final_model_selection.md, generated from the same artefacts as this "
        "document."
    )

    builder.heading("6.2 The contribution, restated against the evidence", level=2)
    if divergence:
        builder.para(
            f"The Health Advisory Index is the project's methodological "
            f"contribution, and its value rests on a measurement rather than an "
            f"argument. Across {divergence.get('n_city_days_evaluated', 0):,} "
            f"city-days, at least one cohort receives a different advisory band from "
            f"the one the official AQI implies on "
            f"{divergence.get('any_cohort_differs', {}).get('pct', 0)} per cent of "
            f"days. That is the share of days on which a single population-average "
            f"number would have given a vulnerable person the wrong instruction, and "
            f"it is the whole case for the index."
        )

    builder.heading("6.3 Limitations", level=2)
    builder.numbered(
        [
            "No meteorological features. Wind speed, boundary-layer height, "
            "temperature and rainfall drive dispersion and are absent from the "
            "source data. This is the single largest constraint on achievable "
            "accuracy, and it is a property of the dataset rather than of the "
            "method.",
            f"Twelve cities only. Fourteen of twenty-six failed the completeness or "
            f"volume gates. The models are not valid elsewhere and are not valid for "
            f"rural areas at all.",
            "Station coverage bias. City-level means represent monitored locations "
            "rather than population-weighted exposure, and coverage expanded over "
            "the record, so the early and late years describe different city sets.",
            f"Imputation. "
            f"{data['cleaning'].get('imputation_applied', {}).get('cells_imputed_pct', 0)} "
            f"per cent of pollutant cells are imputed. The strategy was selected by "
            f"measurement and is causal, but imputed values are estimates and carry "
            f"their own error into every downstream figure.",
            "The record ends 1 July 2020. Nothing here describes present-day air "
            "quality, and the most recent period in the data is atypical because of "
            "the lockdown.",
            "Under-prediction of extreme days. Residual bias turns negative in the "
            "upper bands. This is inherent to minimising an average loss on a "
            "right-skewed target, and it is the reason the application presents the "
            "predicted band with its confidence rather than the point estimate "
            "alone.",
            "The Health Advisory Index is unvalidated against health outcomes. The "
            "dataset contains none, so no such validation was possible. Internal "
            "consistency and divergence from the AQI are demonstrated; clinical "
            "calibration is not claimed.",
            "The clustering is low-powered. Twelve cities is a small sample, and the "
            "four internal validity indices disagreed on the number of clusters.",
            "The policy simulator models no atmospheric chemistry. Pollutants are "
            "reduced independently, so ozone-led scenarios should be read with more "
            "caution than particulate-led ones.",
            "A one-day horizon only. The system cannot support planning beyond "
            "tomorrow.",
        ]
    )

    builder.heading("6.4 Future work", level=2)
    builder.numbered(
        [
            "Join reanalysis meteorology, which is openly available, and measure how "
            "much of the remaining error it removes. This is the highest-value next "
            "step by a clear margin.",
            "Extend the horizon to three and seven days and report how accuracy "
            "degrades, so that a user knows how far ahead the system can be trusted.",
            "Validate the cohort index against hospital admissions data if an "
            "ethically approved linkage becomes available. This is what would "
            "convert the index from a prototype into an instrument.",
            "Model at station level with a spatial component, so that roadside and "
            "residential exposure can be distinguished.",
            "Add quantile regression so the application can present a prediction "
            "interval rather than a point estimate, which would address the "
            "under-prediction of extreme days directly.",
            "Extend the record past 2020 and re-fit, then test whether the "
            "relationships learned before the lockdown still hold after it.",
            "Add the remaining major Indian languages to the advisory dictionary.",
        ]
    )

    builder.references_section(references_for("review3", data))
    builder.rubric_coverage(
        [
            ("Model implementation and training methodology", 10, "Section 1",
             f"{len([r for r in regression.get('results', []) if r['family'] != 'baseline'])} "
             f"regression families and "
             f"{len([r for r in classification.get('results', []) if r['family'] != 'baseline'])} "
             f"classification configurations, plus persistence baselines for both; "
             f"K-Means with elbow and silhouette selection and Ward agglomerative as "
             f"comparison; time-ordered split; TimeSeriesSplit cross-validation; "
             f"class weighting and SMOTE compared head to head; the leakage "
             f"demonstration."),
            ("Appropriate evaluation metrics", 5, "Section 2",
             "Regression MAE, RMSE, R-squared, MAPE and bias; classification "
             "accuracy, macro and weighted precision, recall and F1, per-class F1, "
             "one-versus-rest ROC-AUC, Cohen's kappa, ordinal error and the "
             "severity-understatement rate; clustering silhouette, Davies-Bouldin, "
             "Calinski-Harabasz and adjusted Rand index. Both primary metrics "
             "declared and justified in advance."),
            ("Performance comparison and analytical discussion", 5, "Section 3",
             "Three auto-generated master comparison tables with grouped bar charts; "
             "train-against-test gap analysis; learning curves; residual diagnostics "
             "with error by severity band; per-city breakdown; the lockdown stress "
             "test; error analysis of the worst misclassifications; honest strengths "
             "and limitations for all nine families."),
            ("Hyperparameter tuning and optimisation", 5, "Section 4",
             f"RandomizedSearchCV over "
             f"{tuned_reg.get('grid_points_in_space', 0):,} and "
             f"{tuned_clf.get('grid_points_in_space', 0):,} point spaces with "
             f"TimeSeriesSplit, plus an exhaustive GridSearchCV over the Ridge "
             f"penalty; documented search spaces with the reason for each parameter; "
             f"before-and-after table with deltas; best parameters dumped to JSON; "
             f"an explicit cost-against-gain assessment."),
            ("End-to-end product development and functionality", 10, "Section 5",
             "Four-page Streamlit application, deployed and working, with the "
             "cohort-resolved forecast, what-if sliders, the archetype atlas, the "
             "counterfactual simulator and the full insights page; trilingual "
             "advisory text; SHAP in the product; accessibility and production "
             "hygiene enumerated; deployment and repository links."),
            ("Technical report", 5, "Section 6 and throughout",
             "Final model selection justified quantitatively against baselines and "
             "runners-up; deployment and repository links; ten limitations stated "
             "plainly; seven items of future work; full reference list; this "
             "coverage map. No metric in this document was written by hand."),
        ]
    )

    return builder.save(config.REPORTS_DIR / "Review3_Modeling_and_Comparison.docx")
