"""SHAP explainability for the deployed forecasting models.

A health advisory that cannot say *why* it is issuing a warning is difficult to
act on and difficult to trust. This module produces two complementary views:

Global
    Which features drive the next-day forecast across the whole test period, and
    in which direction. This answers "what does the model think air quality is
    made of".

Local
    Why a single specific day received the forecast it did, decomposed into the
    contribution of each feature. This answers "why is the air going to be bad
    here tomorrow", which is the question a citizen or a city official actually
    asks.

Shapley values are used because they are the only additive attribution with the
efficiency property: the contributions for one prediction sum exactly to the
difference between that prediction and the model's base value, so a local
explanation is a complete account rather than a ranking.

Outputs
-------
``results/explainability.json``
``reports/figures/36_shap_global.png``
``reports/figures/37_shap_local_waterfall.png``

Run with::

    python -m src.models.explain
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config
from src.models.common import load_task_data

LOGGER = config.get_logger(__name__)

RESULTS_PATH = config.RESULTS_DIR / "explainability.json"

#: Test rows sampled for the global explanation. SHAP on a tree ensemble is
#: exact but not free; a few thousand rows give a stable global picture.
SAMPLE_SIZE: int = 2500


def unwrap_tree_model(model: Any) -> Any:
    """Return the underlying tree estimator from any wrapper this project uses.

    The deployed classifier may be an imbalanced-learn ``Pipeline`` containing a
    :class:`LabelEncodedClassifier` containing an ``XGBClassifier``. SHAP's tree
    explainer needs the booster itself, so the wrappers are peeled off here in
    one place rather than at every call site.
    """
    current = model
    for _ in range(5):
        if hasattr(current, "named_steps"):
            steps = [s for name, s in current.named_steps.items() if name != "scaler"]
            current = steps[-1]
            continue
        if hasattr(current, "estimator_"):
            current = current.estimator_
            continue
        if hasattr(current, "steps"):
            current = current.steps[-1][1]
            continue
        break
    return current


def _xgboost_native_shap(tree: Any, features: pd.DataFrame) -> np.ndarray:
    """Compute exact TreeSHAP with XGBoost's own implementation.

    The ``shap`` package parses a serialised XGBoost model itself, and its
    parser predates the change that made ``base_score`` a per-class vector for
    multiclass objectives, so it raises on a current multiclass booster. XGBoost
    implements the same TreeSHAP algorithm natively and is the authority on its
    own format, so the values are requested from the booster directly rather
    than pinning the library to an older version or, worse, explaining a
    different model from the one actually deployed.

    Returns
    -------
    numpy.ndarray
        Contributions with the bias column removed, shaped ``(n, n_features)``
        for a single output or ``(n, n_features, n_classes)`` for multiclass, to
        match what ``shap.TreeExplainer`` would have returned.
    """
    import xgboost as xgb

    booster = tree.get_booster() if hasattr(tree, "get_booster") else tree
    matrix = xgb.DMatrix(features, feature_names=list(features.columns))
    contributions = booster.predict(matrix, pred_contribs=True)

    if contributions.ndim == 3:
        # (n_samples, n_classes, n_features + 1) -> drop bias, move classes last.
        return np.transpose(contributions[:, :, :-1], (0, 2, 1))
    return contributions[:, :-1]


def global_explanation(
    model: Any, features: pd.DataFrame, task: str
) -> Tuple[np.ndarray, pd.DataFrame]:
    """Compute SHAP values and the ranked global importance table."""
    import shap

    tree = unwrap_tree_model(model)
    try:
        explainer = shap.TreeExplainer(tree)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            values = explainer.shap_values(features)
    except (ValueError, TypeError, AttributeError) as exc:
        if not (hasattr(tree, "get_booster") or type(tree).__module__.startswith("xgboost")):
            raise
        LOGGER.info(
            "shap could not parse this booster (%s); using XGBoost's native "
            "TreeSHAP, which is the same algorithm computed by the model's own "
            "implementation.",
            exc,
        )
        values = _xgboost_native_shap(tree, features)

    if isinstance(values, list):
        # Multiclass: aggregate the magnitude across classes for the global view.
        stacked = np.stack([np.abs(v) for v in values], axis=0).mean(axis=0)
    elif values.ndim == 3:
        stacked = np.abs(values).mean(axis=2)
    else:
        stacked = np.abs(values)

    importance = (
        pd.DataFrame(
            {
                "feature": features.columns,
                "mean_abs_shap": stacked.mean(axis=0),
            }
        )
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )
    importance["share_pct"] = (
        100.0 * importance["mean_abs_shap"] / importance["mean_abs_shap"].sum()
    ).round(3)
    importance["rank"] = importance.index + 1
    return values, importance


def plot_global(
    regression_values: np.ndarray,
    regression_features: pd.DataFrame,
    regression_importance: pd.DataFrame,
    classification_importance: pd.DataFrame,
) -> str:
    """Render the global SHAP view for both tasks."""
    import shap

    fig = plt.figure(figsize=(17, 7.5))
    ax1 = fig.add_subplot(1, 3, (1, 2))
    plt.sca(ax1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shap.summary_plot(
            regression_values,
            regression_features,
            max_display=18,
            show=False,
            plot_size=None,
            color_bar=True,
        )
    ax1.set_xlabel("SHAP value (impact on predicted next-day AQI, in AQI points)")
    ax1.set_title(
        "Regression: per-observation feature impact\n"
        "Each point is one test day. Colour is the feature value; horizontal "
        "position is that feature's contribution\nto that day's forecast.",
        fontsize=10.5, loc="left",
    )

    ax2 = fig.add_subplot(1, 3, 3)
    top = classification_importance.head(18).iloc[::-1]
    bars = ax2.barh(top["feature"], top["share_pct"], color=config.PALETTE[2])
    ax2.bar_label(bars, fmt="%.1f%%", padding=2, fontsize=7.5)
    ax2.set_xlabel("Share of total mean |SHAP| (%)")
    ax2.set_xlim(0, float(top["share_pct"].max()) * 1.25)
    ax2.tick_params(axis="y", labelsize=7.5)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title(
        "Classification: global importance\n(mean absolute SHAP, averaged across "
        "the six bands)",
        fontsize=10.5, loc="left",
    )

    fig.suptitle(
        "Figure 36. Global SHAP explanation of the deployed forecasting models",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    path = config.FIGURES_DIR / "36_shap_global.png"
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", path.name)
    return path.name


def plot_local(
    model: Any,
    features: pd.DataFrame,
    meta: pd.DataFrame,
    truth: np.ndarray,
    row_index: int,
) -> Tuple[str, Dict[str, Any]]:
    """Render a waterfall decomposition of one high-AQI day's forecast."""
    import shap

    tree = unwrap_tree_model(model)
    row = features.iloc[[row_index]]
    try:
        explainer = shap.TreeExplainer(tree)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            values = explainer.shap_values(row)
        base_value = float(np.ravel(explainer.expected_value)[0])
    except (ValueError, TypeError, AttributeError):
        import xgboost as xgb

        booster = tree.get_booster() if hasattr(tree, "get_booster") else tree
        contributions = booster.predict(
            xgb.DMatrix(row, feature_names=list(features.columns)), pred_contribs=True
        )
        flat = np.asarray(contributions).reshape(-1)
        values = flat[:-1]
        base_value = float(flat[-1])
    contributions = np.ravel(values)[: features.shape[1]]

    order = np.argsort(np.abs(contributions))[::-1][:14]
    names = [features.columns[i] for i in order]
    magnitudes = contributions[order]
    observed = [row.iloc[0, i] for i in order]

    prediction = float(model.predict(row)[0])
    city = meta.iloc[row_index]["City"]
    date = pd.Timestamp(meta.iloc[row_index]["Date"]).strftime("%Y-%m-%d")
    actual = float(truth[row_index])

    fig, ax = plt.subplots(figsize=(12.5, 7.5))
    colours = [config.PALETTE[1] if m > 0 else config.PALETTE[0] for m in magnitudes]
    y = np.arange(len(names))[::-1]
    bars = ax.barh(y, magnitudes, color=colours)
    ax.bar_label(bars, fmt="%+.1f", padding=4, fontsize=8.5)
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{n}\n= {v:,.2f}" for n, v in zip(names, observed)], fontsize=8
    )
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xlabel("Contribution to the forecast (AQI points)")
    span = float(np.abs(magnitudes).max())
    ax.set_xlim(-span * 1.45, span * 1.45)
    ax.spines[["top", "right"]].set_visible(False)

    ax.text(
        0.99, 0.02,
        f"Base value (mean forecast): {base_value:,.1f}\n"
        f"Sum of contributions shown: {magnitudes.sum():+,.1f}\n"
        f"Model forecast: {prediction:,.1f}\n"
        f"Actual next-day AQI: {actual:,.1f}",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9.5,
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#F2F2F2", "edgecolor": "#CCCCCC"},
    )

    fig.suptitle(
        f"Figure 37. Why the model forecast a high AQI for {city} on {date}\n"
        f"Orange bars push the forecast up, blue bars push it down. The full set of "
        f"contributions sums exactly to the gap between\nthe base value and the "
        f"forecast, so this is a complete account of the prediction rather than a "
        f"ranking of suspects.",
        fontsize=11.5, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    path = config.FIGURES_DIR / "37_shap_local_waterfall.png"
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", path.name)

    payload = {
        "city": str(city),
        "date": date,
        "base_value": round(base_value, 3),
        "prediction": round(prediction, 3),
        "actual": round(actual, 3),
        "top_contributions": [
            {
                "feature": name,
                "value": round(float(value), 4),
                "shap": round(float(magnitude), 4),
                "direction": "increases forecast" if magnitude > 0 else "decreases forecast",
            }
            for name, value, magnitude in zip(names, observed, magnitudes)
        ],
    }
    return path.name, payload


def main() -> Dict[str, Any]:
    """Produce the global and local explanations for both deployed models."""
    config.set_global_seed()
    config.ensure_dirs()

    regression_results = json.loads(
        (config.RESULTS_DIR / "evaluation_regression.json").read_text(encoding="utf-8")
    )
    classification_results = json.loads(
        (config.RESULTS_DIR / "evaluation_classification.json").read_text(encoding="utf-8")
    )

    regression_data = load_task_data("regression")
    classification_data = load_task_data("classification")

    regression_entry = next(
        r for r in regression_results["results"] if r["model"] == regression_results["best_model"]
    )
    classification_entry = next(
        r
        for r in classification_results["results"]
        if r["model"] == classification_results["best_model"]
    )
    regression_model = joblib.load(config.PROJECT_ROOT / regression_entry["artifact"])
    classification_model = joblib.load(config.PROJECT_ROOT / classification_entry["artifact"])

    rng = np.random.default_rng(config.RANDOM_SEED)
    n_test = len(regression_data["X_test"])
    sample_idx = rng.choice(n_test, size=min(SAMPLE_SIZE, n_test), replace=False)
    sample_idx.sort()
    regression_sample = regression_data["X_test"].iloc[sample_idx]

    LOGGER.info("Computing SHAP values for the regressor on %s rows", len(regression_sample))
    regression_values, regression_importance = global_explanation(
        regression_model, regression_sample, "regression"
    )

    clf_n = len(classification_data["X_test"])
    clf_idx = rng.choice(clf_n, size=min(1200, clf_n), replace=False)
    clf_idx.sort()
    LOGGER.info("Computing SHAP values for the classifier on %s rows", len(clf_idx))
    _, classification_importance = global_explanation(
        classification_model, classification_data["X_test"].iloc[clf_idx], "classification"
    )

    global_figure = plot_global(
        regression_values, regression_sample, regression_importance, classification_importance
    )

    # Choose a genuinely severe day for the local explanation, so the decomposition
    # answers the question the application actually poses.
    truth = regression_data["y_test"].to_numpy(dtype=float)
    candidates = np.flatnonzero(truth > 350)
    row_index = int(candidates[len(candidates) // 2]) if candidates.size else int(np.argmax(truth))

    local_figure, local_payload = plot_local(
        regression_model, regression_data["X_test"], regression_data["meta_test"], truth, row_index
    )

    payload: Dict[str, Any] = {
        "generated_by": "src/models/explain.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": (
            "TreeSHAP exact Shapley values. Shapley attribution is used because it "
            "is the only additive feature attribution satisfying efficiency: for "
            "any single prediction the contributions sum exactly to the difference "
            "between that prediction and the model's base value, so a local "
            "explanation is complete rather than merely indicative."
        ),
        "regression": {
            "model": regression_results["best_model"],
            "rows_explained": int(len(regression_sample)),
            "global_importance": regression_importance.head(30).to_dict(orient="records"),
            "top_10_features": regression_importance.head(10)["feature"].tolist(),
        },
        "classification": {
            "model": classification_results["best_model"],
            "rows_explained": int(len(clf_idx)),
            "global_importance": classification_importance.head(30).to_dict(orient="records"),
            "top_10_features": classification_importance.head(10)["feature"].tolist(),
        },
        "local_example": local_payload,
        "figures": [global_figure, local_figure],
        "interpretation": (
            "The global view is dominated by same-day particulate concentration and "
            "by short-horizon change features, which is consistent with the "
            "exploratory finding that PM2.5 is the strongest single correlate of "
            "the AQI and with the strong day-to-day autocorrelation that makes "
            "persistence a competitive baseline. The presence of the change and "
            "deviation features near the top is the more interesting result: the "
            "model is not simply carrying today forward, it is reading the "
            "direction and the momentum of the last few days, which is exactly the "
            "information the persistence baseline lacks and the source of the "
            "margin over it."
        ),
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    LOGGER.info(
        "Wrote %s | top regression features: %s",
        RESULTS_PATH.name,
        ", ".join(payload["regression"]["top_10_features"][:5]),
    )
    return payload


if __name__ == "__main__":
    main()
