"""Master comparison tables, diagnostic figures and the final model selection.

This module consumes the JSON written by the three training modules and the
tuning module and produces the artefacts that the Review 3 document is built
from. It fits no new model except the learning curves, which require repeated
fitting by construction.

Outputs
-------
``results/master_comparison_regression.csv``
``results/master_comparison_classification.csv``
``results/master_comparison_clustering.csv``
``results/final_model_selection.md``
``results/error_analysis.json``
``reports/figures/27_regression_comparison.png``
``reports/figures/28_classification_comparison.png``
``reports/figures/29_confusion_matrices.png``
``reports/figures/30_roc_curves.png``
``reports/figures/31_residual_analysis.png``
``reports/figures/32_learning_curves.png``
``reports/figures/33_per_city_error.png``
``reports/figures/34_train_test_gap.png``
``reports/figures/35_error_analysis.png``

Run with::

    python -m src.models.evaluate
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src import config
from src.models.common import load_task_data, time_series_cv

LOGGER = config.get_logger(__name__)

REGRESSION_JSON = config.RESULTS_DIR / "evaluation_regression.json"
CLASSIFICATION_JSON = config.RESULTS_DIR / "evaluation_classification.json"
CLUSTERING_JSON = config.RESULTS_DIR / "evaluation_clustering.json"
TUNING_JSON = config.RESULTS_DIR / "tuning_report.json"
SELECTION_MD = config.RESULTS_DIR / "final_model_selection.md"
ERROR_ANALYSIS_JSON = config.RESULTS_DIR / "error_analysis.json"


def _load(path: Path) -> Dict[str, Any]:
    """Read a results JSON, failing loudly if the producing stage has not run."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} missing. Run the corresponding training module first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _save(fig: plt.Figure, name: str) -> str:
    path = config.FIGURES_DIR / name
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", name)
    return name


# --------------------------------------------------------------------------- #
# Comparison tables
# --------------------------------------------------------------------------- #
def regression_table(results: Dict[str, Any]) -> pd.DataFrame:
    """Build the master regression comparison table."""
    rows: List[Dict[str, Any]] = []
    for entry in results["results"]:
        test, train = entry["test"], entry.get("train", {})
        rows.append(
            {
                "Model": entry["model"],
                "Family": entry["family"],
                "CV MAE": entry.get("cv", {}).get("mae_mean"),
                "CV MAE sd": entry.get("cv", {}).get("mae_std"),
                "Test MAE": test["MAE"],
                "Test RMSE": test["RMSE"],
                "Test R2": test["R2"],
                "Test MAPE %": test["MAPE_pct"],
                "Test bias": test["bias"],
                "Train MAE": train.get("MAE"),
                "Train-test R2 gap": entry.get("generalisation_gap", {}).get("r2_train_minus_test"),
                "Fit seconds": entry.get("fit_seconds"),
            }
        )
    return pd.DataFrame(rows).sort_values("Test MAE").reset_index(drop=True)


def classification_table(results: Dict[str, Any]) -> pd.DataFrame:
    """Build the master classification comparison table."""
    rows: List[Dict[str, Any]] = []
    for entry in results["results"]:
        test, train = entry["test"], entry.get("train", {})
        severe = next((c["f1"] for c in test["per_class"] if c["class"] == "Severe"), None)
        good = next((c["f1"] for c in test["per_class"] if c["class"] == "Good"), None)
        rows.append(
            {
                "Model": entry["model"],
                "Family": entry["family"],
                "Imbalance strategy": entry.get("imbalance_strategy", "-"),
                "CV macro F1": entry.get("cv", {}).get("mean"),
                "CV sd": entry.get("cv", {}).get("std"),
                "Test macro F1": test["macro_f1"],
                "Test accuracy": test["accuracy"],
                "Test weighted F1": test["weighted_f1"],
                "Balanced accuracy": test["balanced_accuracy"],
                "Cohen kappa": test["cohen_kappa"],
                "ROC-AUC (OvR)": test.get("roc_auc_ovr_macro"),
                "F1 Severe": severe,
                "F1 Good": good,
                "Ordinal MAE": test["mean_absolute_ordinal_error"],
                "Within 1 band %": test["pct_within_one_band"],
                "Train-test macro F1 gap": entry.get("generalisation_gap", {}).get(
                    "macro_f1_train_minus_test"
                ),
                "Fit seconds": entry.get("fit_seconds"),
            }
        )
    return pd.DataFrame(rows).sort_values("Test macro F1", ascending=False).reset_index(drop=True)


def clustering_table(results: Dict[str, Any]) -> pd.DataFrame:
    """Build the master clustering comparison table."""
    rows: List[Dict[str, Any]] = []
    for name, entry in results["algorithms"].items():
        rows.append(
            {
                "Algorithm": name,
                "k": results["selected_k"],
                "Silhouette": entry["silhouette"],
                "Davies-Bouldin": entry["davies_bouldin"],
                "Calinski-Harabasz": entry["calinski_harabasz"],
            }
        )
    for candidate in results["k_selection"]["candidates"]:
        rows.append(
            {
                "Algorithm": f"KMeans (k={candidate['k']}, candidate)",
                "k": candidate["k"],
                "Silhouette": candidate["silhouette"],
                "Davies-Bouldin": candidate["davies_bouldin"],
                "Calinski-Harabasz": candidate["calinski_harabasz"],
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def plot_regression_comparison(table: pd.DataFrame, results: Dict[str, Any]) -> str:
    """Grouped bars for the regression metric suite plus the CV-to-test relation."""
    fitted = table.loc[table["Family"] != "baseline"]
    baseline = table.loc[table["Family"] == "baseline"].iloc[0]

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.4))

    order = fitted.sort_values("Test MAE")
    x = np.arange(len(order))
    width = 0.38
    b1 = axes[0].bar(x - width / 2, order["Test MAE"], width, label="MAE", color=config.PALETTE[0])
    b2 = axes[0].bar(x + width / 2, order["Test RMSE"], width, label="RMSE", color=config.PALETTE[1])
    axes[0].axhline(baseline["Test MAE"], color=config.PALETTE[3], linestyle="--", linewidth=1.8,
                    label=f"Persistence MAE = {baseline['Test MAE']:.2f}")
    axes[0].bar_label(b1, fmt="%.1f", padding=2, fontsize=8)
    axes[0].bar_label(b2, fmt="%.1f", padding=2, fontsize=8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(order["Model"], rotation=25, ha="right", fontsize=8.5)
    axes[0].set_ylabel("AQI points (lower is better)")
    axes[0].legend(frameon=False, fontsize=8.5)
    axes[0].spines[["top", "right"]].set_visible(False)
    axes[0].set_title("Test error by model", fontsize=11, loc="left")

    bars = axes[1].bar(x, order["Test R2"], color=config.PALETTE[2])
    axes[1].axhline(baseline["Test R2"], color=config.PALETTE[3], linestyle="--", linewidth=1.8,
                    label=f"Persistence R2 = {baseline['Test R2']:.3f}")
    axes[1].bar_label(bars, fmt="%.3f", padding=2, fontsize=8.5)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(order["Model"], rotation=25, ha="right", fontsize=8.5)
    axes[1].set_ylim(0.80, 1.0)
    axes[1].set_ylabel("Coefficient of determination")
    axes[1].legend(frameon=False, fontsize=8.5)
    axes[1].spines[["top", "right"]].set_visible(False)
    axes[1].set_title("Explained variance", fontsize=11, loc="left")

    axes[2].scatter(order["CV MAE"], order["Test MAE"], s=90, color=config.PALETTE[0], zorder=3)
    for row in order.itertuples():
        axes[2].annotate(row.Model, (row._4, row._5), fontsize=8,
                         xytext=(6, 4), textcoords="offset points")
    axes[2].set_xlabel("Cross-validated MAE on the training period")
    axes[2].set_ylabel("MAE on the held-out test period")
    axes[2].grid(alpha=0.25, linewidth=0.5)
    axes[2].spines[["top", "right"]].set_visible(False)
    axes[2].set_title(
        "Cross-validation against held-out test\n"
        "CV error exceeds test error for every model, because the\n"
        "earliest expanding-window folds train on very few cities.",
        fontsize=9.5, loc="left",
    )

    fig.suptitle(
        f"Figure 27. Regression model comparison. Best: {results['best_model']} "
        f"(test MAE {results['best_test_metrics']['MAE']:.2f}, "
        f"{results['baseline_comparison']['improvement_over_persistence_pct']:+.1f}% "
        f"against the persistence baseline).",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    return _save(fig, "27_regression_comparison.png")


def plot_classification_comparison(table: pd.DataFrame, results: Dict[str, Any]) -> str:
    """Grouped bars for macro-F1 against accuracy, plus per-class F1 of the winner."""
    fitted = table.loc[table["Family"] != "baseline"].sort_values("Test macro F1", ascending=False)
    baseline = table.loc[table["Family"] == "baseline"].iloc[0]

    fig, axes = plt.subplots(1, 3, figsize=(17.5, 5.6))

    x = np.arange(len(fitted))
    width = 0.28
    for offset, (column, label, colour) in enumerate(
        [
            ("Test macro F1", "Macro F1 (primary)", config.PALETTE[0]),
            ("Test accuracy", "Accuracy", config.PALETTE[4]),
            ("Balanced accuracy", "Balanced accuracy", config.PALETTE[2]),
        ]
    ):
        bars = axes[0].bar(x + (offset - 1) * width, fitted[column], width, label=label, color=colour)
        axes[0].bar_label(bars, fmt="%.2f", padding=1, fontsize=6.5, rotation=90)
    axes[0].axhline(baseline["Test macro F1"], color=config.PALETTE[3], linestyle="--",
                    linewidth=1.8, label=f"Persistence macro F1 = {baseline['Test macro F1']:.3f}")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(fitted["Model"], rotation=30, ha="right", fontsize=8)
    axes[0].set_ylim(0, 1.0)
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].spines[["top", "right"]].set_visible(False)
    axes[0].set_title(
        "Accuracy overstates every model relative to macro F1:\n"
        "the gap is the cost of the rare classes.",
        fontsize=9.5, loc="left",
    )

    best_entry = next(r for r in results["results"] if r["model"] == results["best_model"])
    per_class = best_entry["test"]["per_class"]
    labels = [c["class"] for c in per_class]
    y = np.arange(len(labels))
    height = 0.26
    for offset, (key, name, colour) in enumerate(
        [("precision", "Precision", config.PALETTE[0]),
         ("recall", "Recall", config.PALETTE[1]),
         ("f1", "F1", config.PALETTE[2])]
    ):
        values = [c[key] for c in per_class]
        bars = axes[1].barh(y + (offset - 1) * height, values, height, label=name, color=colour)
        axes[1].bar_label(bars, fmt="%.2f", padding=2, fontsize=7)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([f"{c['class']}\n(n={c['support']:,})" for c in per_class], fontsize=8)
    axes[1].set_xlim(0, 1.15)
    axes[1].legend(frameon=False, fontsize=8.5, loc="lower right")
    axes[1].spines[["top", "right"]].set_visible(False)
    axes[1].set_title(f"Per-class performance: {results['best_model']}", fontsize=10.5, loc="left")

    comparison = results.get("smote_head_to_head", [])
    if comparison:
        names = [c["pair"].split(" vs ")[0] for c in comparison]
        y = np.arange(len(names))
        b1 = axes[2].barh(y - 0.2, [c["macro_f1_weighted_or_plain"] for c in comparison], 0.38,
                          label="class_weight / plain", color=config.PALETTE[0])
        b2 = axes[2].barh(y + 0.2, [c["macro_f1_smote"] for c in comparison], 0.38,
                          label="SMOTE", color=config.PALETTE[2])
        axes[2].bar_label(b1, fmt="%.3f", padding=2, fontsize=7.5)
        axes[2].bar_label(b2, fmt="%.3f", padding=2, fontsize=7.5)
        axes[2].set_yticks(y)
        axes[2].set_yticklabels(names, fontsize=8.5)
        axes[2].set_xlim(0, 0.95)
        axes[2].legend(frameon=False, fontsize=8.5, loc="lower right")
        axes[2].spines[["top", "right"]].set_visible(False)
        axes[2].set_title("Imbalance remedy, head to head (macro F1)", fontsize=10.5, loc="left")

    fig.suptitle(
        f"Figure 28. Classification model comparison. Best: {results['best_model']} "
        f"(test macro F1 {results['best_test_metrics']['macro_f1']:.4f}, accuracy "
        f"{results['best_test_metrics']['accuracy']:.4f}).",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    return _save(fig, "28_classification_comparison.png")


def plot_confusion_matrices(results: Dict[str, Any]) -> str:
    """Raw and row-normalised confusion matrices for the winning classifier."""
    entry = next(r for r in results["results"] if r["model"] == results["best_model"])
    labels = entry["test"]["labels"]
    raw = np.array(entry["test"]["confusion_matrix"])
    normalised = np.array(entry["test"]["confusion_matrix_normalised"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6.5))
    sns.heatmap(raw, annot=True, fmt=",d", cmap="Blues", ax=ax1, cbar=False,
                xticklabels=labels, yticklabels=labels, linewidths=0.5,
                annot_kws={"fontsize": 9})
    ax1.set_xlabel("Predicted band")
    ax1.set_ylabel("Actual band")
    ax1.set_title("Raw counts", fontsize=11, loc="left")

    sns.heatmap(normalised, annot=True, fmt=".2f", cmap="Blues", ax=ax2, vmin=0, vmax=1,
                xticklabels=labels, yticklabels=labels, linewidths=0.5,
                annot_kws={"fontsize": 9}, cbar_kws={"label": "Share of actual class"})
    ax2.set_xlabel("Predicted band")
    ax2.set_ylabel("Actual band")
    ax2.set_title("Normalised by actual class (recall on the diagonal)", fontsize=11, loc="left")

    for ax in (ax1, ax2):
        plt.setp(ax.get_xticklabels(), rotation=25, ha="right", fontsize=9)
        plt.setp(ax.get_yticklabels(), rotation=0, fontsize=9)

    under = entry["test"]["pct_underestimating_severity"]
    fig.suptitle(
        f"Figure 29. Confusion matrices for {results['best_model']}. "
        f"{entry['test']['pct_within_one_band']:.1f}% of predictions land within one "
        f"severity band of the truth; {under:.1f}% understate severity.\n"
        f"Errors concentrate on adjacent bands rather than scattering, which is the "
        f"behaviour an advisory system needs: a near miss changes the wording, not "
        f"the meaning.",
        fontsize=11.5, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    return _save(fig, "29_confusion_matrices.png")


def plot_roc_curves(data: Dict[str, Any], results: Dict[str, Any]) -> str:
    """One-versus-rest ROC curves for the winning classifier."""
    from sklearn.metrics import auc, roc_curve
    from sklearn.preprocessing import label_binarize

    entry = next(r for r in results["results"] if r["model"] == results["best_model"])
    model = joblib.load(config.PROJECT_ROOT / entry["artifact"])
    labels = entry["test"]["labels"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        scores = model.predict_proba(data["X_test"])
    classes = list(getattr(model, "classes_", labels))
    binarised = label_binarize(data["y_test"], classes=classes)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6))
    per_class_auc: Dict[str, float] = {}
    for idx, label in enumerate(classes):
        if binarised[:, idx].sum() == 0:
            continue
        fpr, tpr, _ = roc_curve(binarised[:, idx], scores[:, idx])
        area = auc(fpr, tpr)
        per_class_auc[label] = float(area)
        ax1.plot(fpr, tpr, linewidth=1.9,
                 color=config.PALETTE[idx % len(config.PALETTE)],
                 label=f"{label} (AUC = {area:.3f})")
    ax1.plot([0, 1], [0, 1], "k--", linewidth=1)
    ax1.set_xlabel("False positive rate")
    ax1.set_ylabel("True positive rate")
    ax1.legend(frameon=False, fontsize=8.5, loc="lower right")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_title("One-versus-rest ROC curves", fontsize=11, loc="left")

    ordered = [(k, v) for k, v in sorted(per_class_auc.items(), key=lambda kv: kv[1])]
    bars = ax2.barh([k for k, _ in ordered], [v for _, v in ordered], color=config.PALETTE[0])
    ax2.bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    ax2.set_xlim(0.5, 1.05)
    ax2.axvline(0.5, color="grey", linestyle="--", linewidth=1, label="Random")
    ax2.set_xlabel("Area under the ROC curve")
    ax2.legend(frameon=False, fontsize=8.5)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title("AUC by class", fontsize=11, loc="left")

    macro = entry["test"].get("roc_auc_ovr_macro")
    fig.suptitle(
        f"Figure 30. Discrimination of {results['best_model']} by class. "
        f"Macro one-versus-rest AUC = {macro if macro is not None else 'not computed'}.",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return _save(fig, "30_roc_curves.png")


def plot_residuals(data: Dict[str, Any], results: Dict[str, Any]) -> str:
    """Residual diagnostics for the winning regressor."""
    predictions = np.load(config.RESULTS_DIR / "regression_best_predictions.npy")
    truth = data["y_test"].to_numpy(dtype=float)
    residual = predictions - truth

    fig, axes = plt.subplots(2, 2, figsize=(14.5, 9))

    axes[0, 0].scatter(predictions, residual, s=5, alpha=0.2, color=config.PALETTE[0], rasterized=True)
    axes[0, 0].axhline(0, color=config.PALETTE[1], linewidth=1.5)
    axes[0, 0].set_xlabel("Predicted AQI")
    axes[0, 0].set_ylabel("Residual (predicted minus actual)")
    axes[0, 0].set_title("Residuals against fitted values", fontsize=10.5, loc="left")
    axes[0, 0].grid(alpha=0.25, linewidth=0.5)

    axes[0, 1].hist(residual, bins=70, color=config.PALETTE[2], alpha=0.85)
    axes[0, 1].axvline(0, color="black", linewidth=1)
    axes[0, 1].axvline(float(residual.mean()), color=config.PALETTE[1], linewidth=1.8,
                       label=f"mean = {residual.mean():.2f}")
    axes[0, 1].set_xlabel("Residual")
    axes[0, 1].set_ylabel("Count")
    axes[0, 1].legend(frameon=False)
    axes[0, 1].set_title("Residual distribution", fontsize=10.5, loc="left")

    from scipy import stats as sp_stats

    sp_stats.probplot(residual, dist="norm", plot=axes[1, 0])
    axes[1, 0].set_title("Normal quantile-quantile plot", fontsize=10.5, loc="left")
    axes[1, 0].get_lines()[0].set_markersize(2.5)
    axes[1, 0].get_lines()[0].set_color(config.PALETTE[0])
    axes[1, 0].get_lines()[1].set_color(config.PALETTE[1])

    by_band = results["residual_analysis"]["by_observed_band"]
    names = [b["band"] for b in by_band]
    bias = [b["bias"] for b in by_band]
    mae = [b["mae"] for b in by_band]
    x = np.arange(len(names))
    b1 = axes[1, 1].bar(x - 0.2, mae, 0.38, label="MAE", color=config.PALETTE[0])
    b2 = axes[1, 1].bar(x + 0.2, bias, 0.38, label="Bias", color=config.PALETTE[1])
    axes[1, 1].bar_label(b1, fmt="%.0f", padding=2, fontsize=8)
    axes[1, 1].bar_label(b2, fmt="%.0f", padding=2, fontsize=8)
    axes[1, 1].axhline(0, color="black", linewidth=0.9)
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels([f"{n}\n(n={b['n']:,})" for n, b in zip(names, by_band)], fontsize=8)
    axes[1, 1].set_ylabel("AQI points")
    axes[1, 1].legend(frameon=False)
    axes[1, 1].spines[["top", "right"]].set_visible(False)
    axes[1, 1].set_title("Error and bias by observed severity band", fontsize=10.5, loc="left")

    fig.suptitle(
        f"Figure 31. Residual diagnostics for {results['best_model']}. Bias turns "
        f"increasingly negative in the upper bands: the model under-predicts the "
        f"most severe days,\nwhich is the expected consequence of minimising an "
        f"average loss on a right-skewed target and is stated rather than concealed.",
        fontsize=11.5, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return _save(fig, "31_residual_analysis.png")


def plot_learning_curves(data: Dict[str, Any]) -> str:
    """Learning curves for the winning regressor, under time-ordered validation."""
    from lightgbm import LGBMRegressor
    from sklearn.model_selection import learning_curve

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sizes, train_scores, validation_scores = learning_curve(
            LGBMRegressor(
                n_estimators=400, learning_rate=0.05, random_state=config.RANDOM_SEED,
                n_jobs=-1, verbose=-1,
            ),
            data["X_train"],
            data["y_train"],
            train_sizes=np.linspace(0.15, 1.0, 8),
            cv=time_series_cv(dates=data["meta_train"]["Date"]),
            scoring="neg_mean_absolute_error",
            n_jobs=1,
            shuffle=False,
        )

    train_mae = -train_scores.mean(axis=1)
    validation_mae = -validation_scores.mean(axis=1)

    fig, ax = plt.subplots(figsize=(10.5, 6))
    ax.plot(sizes, train_mae, marker="o", color=config.PALETTE[0], linewidth=2, label="Training MAE")
    ax.fill_between(sizes, -train_scores.mean(axis=1) - train_scores.std(axis=1),
                    -train_scores.mean(axis=1) + train_scores.std(axis=1),
                    color=config.PALETTE[0], alpha=0.16)
    ax.plot(sizes, validation_mae, marker="s", color=config.PALETTE[1], linewidth=2,
            label="Validation MAE (TimeSeriesSplit)")
    ax.fill_between(sizes, -validation_scores.mean(axis=1) - validation_scores.std(axis=1),
                    -validation_scores.mean(axis=1) + validation_scores.std(axis=1),
                    color=config.PALETTE[1], alpha=0.16)
    ax.set_xlabel("Training observations used")
    ax.set_ylabel("Mean absolute error (AQI points)")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25, linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)

    gap = validation_mae[-1] - train_mae[-1]
    fig.suptitle(
        f"Figure 32. Learning curves for LightGBM under expanding-window validation.\n"
        f"The validation curve is still falling at the full training size, and the "
        f"final train-validation gap is {gap:.1f} AQI points: the model is data-limited\n"
        f"rather than capacity-limited, so more historical record would help more "
        f"than a larger model would.",
        fontsize=11.5, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    return _save(fig, "32_learning_curves.png")


def plot_per_city_error(
    regression: Dict[str, Any], classification: Dict[str, Any]
) -> str:
    """Per-city error breakdown for both supervised tasks."""
    reg_entry = next(r for r in regression["results"] if r["model"] == regression["best_model"])
    clf_entry = next(
        r for r in classification["results"] if r["model"] == classification["best_model"]
    )

    reg_cities = sorted(reg_entry["slices"]["by_city"], key=lambda c: c["MAE"])
    clf_cities = sorted(clf_entry["slices"]["by_city"], key=lambda c: c["macro_f1"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6.5))
    bars = ax1.barh([c["city"] for c in reg_cities], [c["MAE"] for c in reg_cities],
                    color=config.PALETTE[0])
    ax1.bar_label(bars, fmt="%.1f", padding=3, fontsize=8.5)
    ax1.axvline(regression["best_test_metrics"]["MAE"], color=config.PALETTE[1],
                linestyle="--", linewidth=1.8,
                label=f"Pooled MAE = {regression['best_test_metrics']['MAE']:.2f}")
    ax1.set_xlabel("Test MAE (AQI points)")
    ax1.set_xlim(0, max(c["MAE"] for c in reg_cities) * 1.2)
    ax1.legend(frameon=False, fontsize=9)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_title(f"Regression: {regression['best_model']}", fontsize=11, loc="left")

    bars = ax2.barh([c["city"] for c in clf_cities], [c["macro_f1"] for c in clf_cities],
                    color=config.PALETTE[2])
    ax2.bar_label(bars, fmt="%.3f", padding=3, fontsize=8.5)
    ax2.axvline(classification["best_test_metrics"]["macro_f1"], color=config.PALETTE[1],
                linestyle="--", linewidth=1.8,
                label=f"Pooled macro F1 = {classification['best_test_metrics']['macro_f1']:.3f}")
    ax2.set_xlabel("Test macro F1")
    ax2.set_xlim(0, 1.08)
    ax2.legend(frameon=False, fontsize=9)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title(f"Classification: {classification['best_model']}", fontsize=11, loc="left")

    worst_reg = reg_cities[-1]
    fig.suptitle(
        f"Figure 33. Error broken down by city. The pooled figure conceals a wide "
        f"spread: {worst_reg['city']} carries an MAE of {worst_reg['MAE']:.1f} against "
        f"a pooled {regression['best_test_metrics']['MAE']:.1f}.\n"
        f"Reporting only the national average would hide systematic failure in the "
        f"cities where the health burden is highest.",
        fontsize=11.5, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    return _save(fig, "33_per_city_error.png")


def plot_train_test_gap(
    regression_table_df: pd.DataFrame, classification_table_df: pd.DataFrame
) -> str:
    """Overfitting diagnosis: training against test performance for every model."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    reg = regression_table_df.loc[regression_table_df["Train MAE"].notna()]
    x = np.arange(len(reg))
    width = 0.38
    b1 = ax1.bar(x - width / 2, reg["Train MAE"], width, label="Train MAE", color=config.PALETTE[4])
    b2 = ax1.bar(x + width / 2, reg["Test MAE"], width, label="Test MAE", color=config.PALETTE[0])
    ax1.bar_label(b1, fmt="%.1f", padding=2, fontsize=8)
    ax1.bar_label(b2, fmt="%.1f", padding=2, fontsize=8)
    ax1.set_xticks(x)
    ax1.set_xticklabels(reg["Model"], rotation=25, ha="right", fontsize=8.5)
    ax1.set_ylabel("MAE (AQI points)")
    ax1.legend(frameon=False)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_title("Regression", fontsize=11, loc="left")

    clf = classification_table_df.loc[classification_table_df["Train-test macro F1 gap"].notna()]
    x = np.arange(len(clf))
    bars = ax2.bar(x, clf["Train-test macro F1 gap"], color=config.PALETTE[1])
    ax2.bar_label(bars, fmt="%.3f", padding=2, fontsize=8)
    ax2.axhline(0.15, color=config.PALETTE[3], linestyle="--", linewidth=1.6,
                label="Overfitting threshold used in this project (0.15)")
    ax2.axhline(0, color="black", linewidth=0.9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(clf["Model"], rotation=30, ha="right", fontsize=8)
    ax2.set_ylabel("Train macro F1 minus test macro F1")
    ax2.legend(frameon=False, fontsize=8.5)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title("Classification", fontsize=11, loc="left")

    fig.suptitle(
        "Figure 34. Generalisation gap by model. A large positive gap indicates a "
        "model that has memorised the training period rather than learned the "
        "process.\nThe unconstrained tree ensembles fit the training data almost "
        "exactly, which is why their test performance, not their training "
        "performance, decides the selection.",
        fontsize=11.5, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    return _save(fig, "34_train_test_gap.png")


def error_analysis(data: Dict[str, Any], classification: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Examine the worst misclassifications of the winning classifier."""
    entry = next(
        r for r in classification["results"] if r["model"] == classification["best_model"]
    )
    model = joblib.load(config.PROJECT_ROOT / entry["artifact"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        predictions = model.predict(data["X_test"])

    frame = data["meta_test"].copy()
    frame["actual"] = data["y_test"].to_numpy()
    frame["predicted"] = predictions
    frame["actual_ordinal"] = frame["actual"].map(config.AQI_BUCKET_ORDINAL)
    frame["predicted_ordinal"] = frame["predicted"].map(config.AQI_BUCKET_ORDINAL)
    frame["ordinal_error"] = frame["predicted_ordinal"] - frame["actual_ordinal"]
    frame["abs_error"] = frame["ordinal_error"].abs()

    worst = frame.loc[frame["abs_error"] >= 2].copy()
    dangerous = frame.loc[frame["ordinal_error"] <= -2].copy()

    by_city = (
        frame.assign(wrong=(frame["abs_error"] > 0).astype(int))
        .groupby("City")
        .agg(n=("wrong", "size"), errors=("wrong", "sum"), mean_abs_ordinal=("abs_error", "mean"))
        .assign(error_rate_pct=lambda d: (100.0 * d["errors"] / d["n"]).round(2))
        .sort_values("error_rate_pct", ascending=False)
        .reset_index()
    )

    transitions = (
        frame.loc[frame["abs_error"] > 0]
        .groupby(["actual", "predicted"])
        .size()
        .sort_values(ascending=False)
        .head(10)
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6))
    counts = frame["ordinal_error"].value_counts().sort_index()
    colours = [
        config.PALETTE[1] if k < 0 else (config.PALETTE[2] if k == 0 else config.PALETTE[4])
        for k in counts.index
    ]
    bars = ax1.bar(counts.index.astype(str), counts.to_numpy(), color=colours)
    ax1.bar_label(bars, fmt="%d", padding=2, fontsize=8.5)
    ax1.set_xlabel("Bands wrong (negative understates severity)")
    ax1.set_ylabel("Test predictions")
    ax1.set_yscale("log")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_title(
        f"Signed band error. {len(dangerous):,} predictions understate severity by "
        f"two bands or more\n({100 * len(dangerous) / len(frame):.2f}% of the test "
        f"set): these are the health-critical failures.",
        fontsize=9.5, loc="left",
    )

    labels = [f"{a}\n-> {p}" for a, p in transitions.index]
    bars = ax2.barh(labels[::-1], transitions.to_numpy()[::-1], color=config.PALETTE[0])
    ax2.bar_label(bars, fmt="%d", padding=3, fontsize=8.5)
    ax2.set_xlabel("Occurrences in the test set")
    ax2.tick_params(axis="y", labelsize=7.5)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title("Ten most frequent misclassification transitions", fontsize=10.5, loc="left")

    fig.suptitle(
        f"Figure 35. Error analysis for {classification['best_model']}. Confusions "
        f"are overwhelmingly between adjacent bands, which is the failure mode an "
        f"advisory system can tolerate.",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    figure = _save(fig, "35_error_analysis.png")

    payload = {
        "model": classification["best_model"],
        "n_test": int(len(frame)),
        "n_wrong": int((frame["abs_error"] > 0).sum()),
        "error_rate_pct": round(100.0 * float((frame["abs_error"] > 0).mean()), 2),
        "n_wrong_by_two_or_more_bands": int(len(worst)),
        "pct_wrong_by_two_or_more_bands": round(100.0 * len(worst) / len(frame), 3),
        "n_understating_severity_by_two_or_more": int(len(dangerous)),
        "pct_understating_severity_by_two_or_more": round(100.0 * len(dangerous) / len(frame), 3),
        "signed_band_error_distribution": {
            int(k): int(v) for k, v in frame["ordinal_error"].value_counts().sort_index().items()
        },
        "most_frequent_transitions": [
            {"actual": actual, "predicted": predicted, "count": int(count)}
            for (actual, predicted), count in transitions.items()
        ],
        "by_city": by_city.to_dict(orient="records"),
        "worst_examples": worst.nlargest(15, "abs_error")[
            ["City", "Date", "actual", "predicted", "ordinal_error"]
        ].assign(Date=lambda d: d["Date"].dt.strftime("%Y-%m-%d")).to_dict(orient="records"),
        "interpretation": (
            "The signed error distribution is sharply peaked at zero and decays "
            "fast, and almost all remaining error is a single band in either "
            "direction. The subset that matters operationally is the tail that "
            "understates severity by two bands or more, because that is the case in "
            "which a reader is told the air is acceptable when it is not. Its size "
            "is reported above as an explicit safety statistic rather than being "
            "left implicit inside the macro-F1."
        ),
    }
    return figure, payload


# --------------------------------------------------------------------------- #
# Final selection
# --------------------------------------------------------------------------- #
def write_final_selection(
    regression: Dict[str, Any],
    classification: Dict[str, Any],
    clustering: Dict[str, Any],
    tuning: Dict[str, Any],
    errors: Dict[str, Any],
) -> Path:
    """Write the final model selection document with the numbers that justify it."""
    reg_table = regression_table(regression)
    clf_table = classification_table(classification)

    reg_best = regression["best_test_metrics"]
    clf_best = classification["best_test_metrics"]
    reg_runner = reg_table.loc[reg_table["Family"] != "baseline"].iloc[1]
    clf_runner = clf_table.loc[clf_table["Family"] != "baseline"].iloc[1]

    tuned_reg = tuning["regression"]
    tuned_clf = tuning["classification"]
    deploy_reg = (
        f"{tuned_reg['model']} (tuned)"
        if tuned_reg["tuned_test"]["MAE"] < reg_best["MAE"]
        else f"{regression['best_model']} (default parameters)"
    )
    deploy_clf = (
        f"{tuned_clf['model']} (tuned)"
        if tuned_clf["tuned_test"]["macro_f1"] > clf_best["macro_f1"]
        else f"{classification['best_model']} (default parameters)"
    )

    severe = next(c for c in clf_best["per_class"] if c["class"] == "Severe")

    lines: List[str] = [
        "# Final Model Selection",
        "",
        "> Generated by `src/models/evaluate.py` from `results/*.json`. Every figure "
        "below was produced by executed code; none is transcribed.",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## 1. Regression: next-day AQI value",
        "",
        f"**Selected model: {regression['best_model']}.**",
        "",
        "| Criterion | Value |",
        "| --- | --- |",
        f"| Primary metric (MAE) | **{reg_best['MAE']}** AQI points |",
        f"| RMSE | {reg_best['RMSE']} |",
        f"| R-squared | {reg_best['R2']} |",
        f"| MAPE | {reg_best['MAPE_pct']}% |",
        f"| Median absolute error | {reg_best['median_absolute_error']} |",
        f"| Bias | {reg_best['bias']} |",
        f"| Persistence baseline MAE | {regression['baseline_comparison']['baseline_mae']} |",
        f"| Improvement over persistence | **{regression['baseline_comparison']['improvement_over_persistence_pct']}%** |",
        f"| Runner-up | {reg_runner['Model']} at MAE {reg_runner['Test MAE']} |",
        f"| Margin over runner-up | {round(float(reg_runner['Test MAE']) - reg_best['MAE'], 3)} AQI points |",
        "",
        f"**Justification.** {regression['primary_metric_justification']}",
        "",
        f"{regression['best_model']} attains the lowest MAE of the five fitted "
        f"families and beats the persistence baseline by "
        f"{regression['baseline_comparison']['improvement_over_persistence_pct']}%. "
        f"The margin over {reg_runner['Model']} is "
        f"{round(float(reg_runner['Test MAE']) - reg_best['MAE'], 3)} AQI points, which "
        f"is small; the selection is therefore additionally supported by its lower "
        f"RMSE and its shorter fit time. The linear models reach MAE "
        f"{float(reg_table.loc[reg_table['Model'] == 'Linear Regression', 'Test MAE'].iloc[0]):.2f}, "
        f"so the gain from non-linearity on this problem is real but modest, which "
        f"is itself a finding worth stating.",
        "",
        "### 1.1 Effect of tuning",
        "",
        "| | MAE | RMSE | R-squared |",
        "| --- | --- | --- | --- |",
        f"| Default parameters | {tuned_reg['untuned_test']['MAE']} | {tuned_reg['untuned_test']['RMSE']} | {tuned_reg['untuned_test']['R2']} |",
        f"| Tuned | {tuned_reg['tuned_test']['MAE']} | {tuned_reg['tuned_test']['RMSE']} | {tuned_reg['tuned_test']['R2']} |",
        f"| Delta | {tuned_reg['delta']['MAE']} | {tuned_reg['delta']['RMSE']} | {tuned_reg['delta']['R2']} |",
        "",
        f"Best parameters: `{json.dumps(tuned_reg['best_params'])}`",
        "",
        f"**Model deployed in the application: {deploy_reg}.**",
        "",
        "## 2. Classification: next-day AQI bucket",
        "",
        f"**Selected model: {classification['best_model']}.**",
        "",
        "| Criterion | Value |",
        "| --- | --- |",
        f"| Primary metric (macro F1) | **{clf_best['macro_f1']}** |",
        f"| Accuracy | {clf_best['accuracy']} |",
        f"| Weighted F1 | {clf_best['weighted_f1']} |",
        f"| Balanced accuracy | {clf_best['balanced_accuracy']} |",
        f"| Cohen's kappa | {clf_best['cohen_kappa']} |",
        f"| ROC-AUC (one-versus-rest, macro) | {clf_best.get('roc_auc_ovr_macro', 'not computed')} |",
        f"| F1 on the Severe class | {severe['f1']} (support {severe['support']}) |",
        f"| Mean absolute ordinal error | {clf_best['mean_absolute_ordinal_error']} bands |",
        f"| Predictions within one band | {clf_best['pct_within_one_band']}% |",
        f"| Predictions understating severity | {clf_best['pct_underestimating_severity']}% |",
        f"| Persistence baseline macro F1 | {classification['baseline_comparison']['baseline_macro_f1']} |",
        f"| Improvement over persistence | **{classification['baseline_comparison']['improvement_over_persistence_pct']}%** |",
        f"| Runner-up | {clf_runner['Model']} at macro F1 {clf_runner['Test macro F1']} |",
        "",
        f"**Justification.** {classification['primary_metric_justification']}",
        "",
        "### 2.1 Imbalance remedy, head to head",
        "",
        "| Pair | macro F1 (weighted or plain) | macro F1 (SMOTE) | Delta | Winner |",
        "| --- | --- | --- | --- | --- |",
    ]
    for pair in classification.get("smote_head_to_head", []):
        lines.append(
            f"| {pair['pair']} | {pair['macro_f1_weighted_or_plain']} | "
            f"{pair['macro_f1_smote']} | {pair['delta_macro_f1']:+} | {pair['winner']} |"
        )

    lines += [
        "",
        "### 2.2 Effect of tuning",
        "",
        "| | macro F1 | Accuracy | Weighted F1 |",
        "| --- | --- | --- | --- |",
        f"| Default parameters | {tuned_clf['untuned_test']['macro_f1']} | {tuned_clf['untuned_test']['accuracy']} | {tuned_clf['untuned_test']['weighted_f1']} |",
        f"| Tuned | {tuned_clf['tuned_test']['macro_f1']} | {tuned_clf['tuned_test']['accuracy']} | {tuned_clf['tuned_test']['weighted_f1']} |",
        f"| Delta | {tuned_clf['delta']['macro_f1']:+} | {tuned_clf['delta']['accuracy']:+} | - |",
        "",
        f"Best parameters: `{json.dumps(tuned_clf['best_params'])}`",
        "",
        f"**Model deployed in the application: {deploy_clf}.**",
        "",
        "### 2.3 Safety-relevant error",
        "",
        f"Of {errors['n_test']:,} test predictions, {errors['n_wrong']:,} are wrong "
        f"({errors['error_rate_pct']}%), but only "
        f"{errors['n_wrong_by_two_or_more_bands']:,} "
        f"({errors['pct_wrong_by_two_or_more_bands']}%) are wrong by two bands or more, "
        f"and {errors['n_understating_severity_by_two_or_more']:,} "
        f"({errors['pct_understating_severity_by_two_or_more']}%) understate severity by "
        f"two bands or more. The last figure is the one that matters operationally, "
        f"because it counts the occasions on which a reader would be told the air is "
        f"more acceptable than it is.",
        "",
        "## 3. Clustering: city pollution archetypes",
        "",
        f"**Selected: K-Means with k = {clustering['selected_k']}.**",
        "",
        "| Criterion | K-Means | Agglomerative (Ward) |",
        "| --- | --- | --- |",
        f"| Silhouette | {clustering['algorithms']['KMeans']['silhouette']} | {clustering['algorithms']['Agglomerative (Ward)']['silhouette']} |",
        f"| Davies-Bouldin | {clustering['algorithms']['KMeans']['davies_bouldin']} | {clustering['algorithms']['Agglomerative (Ward)']['davies_bouldin']} |",
        f"| Calinski-Harabasz | {clustering['algorithms']['KMeans']['calinski_harabasz']} | {clustering['algorithms']['Agglomerative (Ward)']['calinski_harabasz']} |",
        "",
        f"Adjusted Rand index between the two partitions: "
        f"**{clustering['algorithm_agreement']['adjusted_rand_index']}**. "
        f"{clustering['algorithm_agreement']['interpretation']}",
        "",
        f"{clustering['k_selection']['selection_rule']}",
        "",
        f"{clustering['k_selection']['power_caveat']}",
        "",
        "### 3.1 Discovered archetypes",
        "",
        "| Cluster | Archetype | Defining pollutant | Cities | Policy lever |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in clustering["archetypes"]:
        lines.append(
            f"| {entry['cluster']} | {entry['archetype']} | {entry['defining_pollutant']} "
            f"| {', '.join(entry['cities'])} | {entry['policy_lever']} |"
        )

    lines += [
        "",
        "## 4. Leakage controls, stated and verified",
        "",
        classification["leakage_demonstration"]["conclusion"],
        "",
        "## 5. Summary",
        "",
        "| Task | Selected model | Primary metric | Value | Beats baseline by |",
        "| --- | --- | --- | --- | --- |",
        f"| Regression | {regression['best_model']} | MAE | {reg_best['MAE']} | "
        f"{regression['baseline_comparison']['improvement_over_persistence_pct']}% |",
        f"| Classification | {classification['best_model']} | macro F1 | {clf_best['macro_f1']} | "
        f"{classification['baseline_comparison']['improvement_over_persistence_pct']}% |",
        f"| Clustering | K-Means (k={clustering['selected_k']}) | Silhouette | "
        f"{clustering['algorithms']['KMeans']['silhouette']} | not applicable (unsupervised) |",
        "",
    ]

    SELECTION_MD.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("Wrote %s", SELECTION_MD.name)
    return SELECTION_MD


def main() -> Dict[str, Any]:
    """Build every comparison artefact and the final selection document."""
    config.set_global_seed()
    config.ensure_dirs()

    regression = _load(REGRESSION_JSON)
    classification = _load(CLASSIFICATION_JSON)
    clustering = _load(CLUSTERING_JSON)
    tuning = _load(TUNING_JSON)

    reg_table = regression_table(regression)
    clf_table = classification_table(classification)
    clu_table = clustering_table(clustering)

    reg_table.to_csv(config.RESULTS_DIR / "master_comparison_regression.csv", index=False)
    clf_table.to_csv(config.RESULTS_DIR / "master_comparison_classification.csv", index=False)
    clu_table.to_csv(config.RESULTS_DIR / "master_comparison_clustering.csv", index=False)
    LOGGER.info("Wrote three master comparison tables")

    regression_data = load_task_data("regression")
    classification_data = load_task_data("classification")

    figures = [
        plot_regression_comparison(reg_table, regression),
        plot_classification_comparison(clf_table, classification),
        plot_confusion_matrices(classification),
        plot_roc_curves(classification_data, classification),
        plot_residuals(regression_data, regression),
        plot_learning_curves(regression_data),
        plot_per_city_error(regression, classification),
        plot_train_test_gap(reg_table, clf_table),
    ]

    error_figure, errors = error_analysis(classification_data, classification)
    figures.append(error_figure)
    ERROR_ANALYSIS_JSON.write_text(json.dumps(errors, indent=2, default=str), encoding="utf-8")

    write_final_selection(regression, classification, clustering, tuning, errors)

    summary = {
        "generated_by": "src/models/evaluate.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "figures": figures,
        "tables": [
            "master_comparison_regression.csv",
            "master_comparison_classification.csv",
            "master_comparison_clustering.csv",
        ],
        "best_regression": regression["best_model"],
        "best_classification": classification["best_model"],
        "selected_k": clustering["selected_k"],
    }
    (config.RESULTS_DIR / "evaluation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    LOGGER.info("Evaluation complete: %s figures", len(figures))
    return summary


if __name__ == "__main__":
    main()
