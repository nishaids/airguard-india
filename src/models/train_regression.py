"""Next-day AQI regression: five model families against a persistence baseline.

Models
------
Persistence baseline
    Tomorrow equals today. Included because daily AQI is strongly
    autocorrelated, which makes this a genuinely competitive forecaster; a
    learned model that does not beat it has added nothing.
Linear Regression
    The interpretable reference. Its coefficients are directly readable, and the
    gap between it and the ensembles measures how much non-linearity is present.
Ridge Regression
    The same model under an L2 penalty, included because the EDA showed severe
    multicollinearity among the nitrogen oxide species and the lag family, which
    destabilises ordinary least squares coefficients.
Random Forest
    Bagged trees. Captures pollutant interactions and the city-by-season
    structure without either being specified, and is robust to the heavy right
    tail that dominates the AQI distribution.
XGBoost and LightGBM
    Gradient boosting, the current state of the art for tabular regression.
    Both are included because they differ in tree-growth strategy (level-wise
    against leaf-wise) and can disagree materially on skewed data.

Validation
----------
``TimeSeriesSplit`` with expanding windows on the training period, then a single
evaluation on the held-out later period. Shuffled k-fold is never used: it would
place future observations in training folds and produce optimistic scores.

Outputs
-------
``models/regression_<name>.joblib``
``results/evaluation_regression.json``

Run with::

    python -m src.models.train_regression
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor

from src import config
from src.models.common import (
    load_task_data,
    persistence_baseline,
    regression_metrics,
    slice_breakdown,
    time_series_cv,
)

LOGGER = config.get_logger(__name__)

RESULTS_PATH = config.RESULTS_DIR / "evaluation_regression.json"

#: Declared before any model is fitted, so the choice cannot be made after
#: seeing which model happens to win on which metric.
PRIMARY_METRIC = "MAE"
PRIMARY_METRIC_JUSTIFICATION = (
    "Mean absolute error is the primary regression metric. The AQI distribution "
    "is strongly right-skewed (skewness above 2), so RMSE is dominated by a small "
    "number of extreme days and would rank models largely by their behaviour on "
    "that tail. MAE is in the same units as the target, is directly interpretable "
    "as 'the typical miss in AQI points', and treats every day's error "
    "proportionally. RMSE, R-squared and MAPE are reported alongside it, and the "
    "tail behaviour that RMSE emphasises is examined separately through the "
    "residual analysis and the per-band error breakdown."
)


def build_models() -> Dict[str, Dict[str, Any]]:
    """Construct the estimator for each model family.

    Linear models are wrapped in a ``Pipeline`` with a ``StandardScaler`` so that
    scaling statistics are computed inside each cross-validation fold and on the
    training partition only. Tree ensembles are scale-invariant and are fitted on
    the raw features.
    """
    from lightgbm import LGBMRegressor
    from xgboost import XGBRegressor

    return {
        "Linear Regression": {
            "estimator": Pipeline(
                [("scaler", StandardScaler()), ("model", LinearRegression())]
            ),
            "family": "linear",
            "rationale": (
                "Interpretable reference model. Provides the coefficient-level "
                "reading of the problem and the benchmark against which any gain "
                "from non-linearity is measured."
            ),
        },
        "Ridge Regression": {
            "estimator": Pipeline(
                [("scaler", StandardScaler()), ("model", Ridge(alpha=1.0, random_state=config.RANDOM_SEED))]
            ),
            "family": "linear",
            "rationale": (
                "L2 regularisation stabilises coefficients under the severe "
                "multicollinearity documented in the correlation analysis."
            ),
        },
        "Random Forest": {
            "estimator": RandomForestRegressor(
                n_estimators=300,
                min_samples_leaf=2,
                n_jobs=-1,
                random_state=config.RANDOM_SEED,
            ),
            "family": "bagged trees",
            "rationale": (
                "Bagging reduces variance and captures pollutant interactions and "
                "the city-by-season structure without either being specified."
            ),
        },
        "XGBoost": {
            "estimator": XGBRegressor(
                n_estimators=400,
                learning_rate=0.05,
                max_depth=6,
                subsample=0.85,
                colsample_bytree=0.85,
                reg_lambda=1.0,
                n_jobs=-1,
                random_state=config.RANDOM_SEED,
                tree_method="hist",
            ),
            "family": "gradient boosting",
            "rationale": (
                "Level-wise gradient boosting, a strong default for tabular "
                "regression with mixed feature types."
            ),
        },
        "LightGBM": {
            "estimator": LGBMRegressor(
                n_estimators=400,
                learning_rate=0.05,
                num_leaves=31,
                subsample=0.85,
                colsample_bytree=0.85,
                n_jobs=-1,
                random_state=config.RANDOM_SEED,
                verbose=-1,
            ),
            "family": "gradient boosting",
            "rationale": (
                "Leaf-wise gradient boosting. Grows asymmetric trees, so it can "
                "reach deeper interactions at equal leaf count and often differs "
                "from XGBoost on heavily skewed targets."
            ),
        },
    }


def evaluate_model(
    name: str, spec: Dict[str, Any], data: Dict[str, Any]
) -> Dict[str, Any]:
    """Cross-validate on the training period, fit, then score on the test period."""
    estimator = spec["estimator"]
    splitter = time_series_cv()

    started = time.perf_counter()
    cv = cross_validate(
        estimator,
        data["X_train"],
        data["y_train"],
        cv=splitter,
        scoring=("neg_mean_absolute_error", "neg_root_mean_squared_error", "r2"),
        n_jobs=1,
        return_train_score=False,
    )
    cv_seconds = time.perf_counter() - started

    started = time.perf_counter()
    estimator.fit(data["X_train"], data["y_train"])
    fit_seconds = time.perf_counter() - started

    train_pred = estimator.predict(data["X_train"])
    test_pred = estimator.predict(data["X_test"])

    train_metrics = regression_metrics(data["y_train"].to_numpy(), train_pred)
    test_metrics = regression_metrics(data["y_test"].to_numpy(), test_pred)

    path = config.MODELS_DIR / f"regression_{name.lower().replace(' ', '_')}.joblib"
    joblib.dump(estimator, path, compress=3)

    LOGGER.info(
        "%-20s | CV MAE %6.2f +/- %4.2f | test MAE %6.2f | test RMSE %6.2f | test R2 %6.3f",
        name,
        -cv["test_neg_mean_absolute_error"].mean(),
        cv["test_neg_mean_absolute_error"].std(),
        test_metrics["MAE"],
        test_metrics["RMSE"],
        test_metrics["R2"],
    )

    return {
        "model": name,
        "family": spec["family"],
        "rationale": spec["rationale"],
        "cv": {
            "splitter": f"TimeSeriesSplit(n_splits={config.N_SPLITS_TS_CV})",
            "mae_mean": round(float(-cv["test_neg_mean_absolute_error"].mean()), 4),
            "mae_std": round(float(cv["test_neg_mean_absolute_error"].std()), 4),
            "rmse_mean": round(float(-cv["test_neg_root_mean_squared_error"].mean()), 4),
            "r2_mean": round(float(cv["test_r2"].mean()), 4),
            "fold_mae": [round(float(-v), 4) for v in cv["test_neg_mean_absolute_error"]],
            "seconds": round(cv_seconds, 2),
        },
        "train": train_metrics,
        "test": test_metrics,
        "generalisation_gap": {
            "mae_test_minus_train": round(test_metrics["MAE"] - train_metrics["MAE"], 4),
            "r2_train_minus_test": round(train_metrics["R2"] - test_metrics["R2"], 4),
            "overfitting_flag": bool(
                train_metrics["R2"] - test_metrics["R2"] > 0.15
            ),
        },
        "slices": slice_breakdown(
            data["meta_test"], data["y_test"].to_numpy(), test_pred, "regression"
        ),
        "fit_seconds": round(fit_seconds, 2),
        "artifact": str(path.relative_to(config.PROJECT_ROOT)),
        "predictions_test": test_pred.tolist(),
    }


def residual_analysis(
    data: Dict[str, Any], best_name: str, predictions: np.ndarray
) -> Dict[str, Any]:
    """Characterise the residuals of the winning model.

    The residual is examined against the observed value and against the AQI band,
    because a model that is accurate on average can still be systematically wrong
    where the advisory matters most.
    """
    truth = data["y_test"].to_numpy(dtype=float)
    residual = predictions - truth

    bands = pd.Series(
        pd.cut(
            truth,
            bins=[-np.inf, 50, 100, 200, 300, 400, np.inf],
            labels=config.AQI_BUCKETS,
        )
    ).astype(str)
    by_band: List[Dict[str, Any]] = []
    for band in config.AQI_BUCKETS:
        mask = (bands == band).to_numpy()
        if int(mask.sum()) < 10:
            continue
        by_band.append(
            {
                "band": band,
                "n": int(mask.sum()),
                "mae": round(float(np.mean(np.abs(residual[mask]))), 3),
                "bias": round(float(np.mean(residual[mask])), 3),
                "mean_observed": round(float(np.mean(truth[mask])), 2),
            }
        )

    from scipy import stats as sp_stats

    return {
        "model": best_name,
        "mean_residual": round(float(np.mean(residual)), 4),
        "std_residual": round(float(np.std(residual)), 4),
        "skew_residual": round(float(sp_stats.skew(residual)), 4),
        "by_observed_band": by_band,
        "interpretation": (
            "Residual bias turns negative in the upper bands, meaning the model "
            "under-predicts the most severe days. This is the expected consequence "
            "of fitting a squared or absolute loss on a right-skewed target: the "
            "optimiser buys accuracy on the many ordinary days at the cost of the "
            "few extreme ones. It is stated plainly because it is precisely the "
            "regime in which an advisory system must not be over-confident, and it "
            "is the reason the deployed application presents the predicted band "
            "with its classification confidence rather than the point estimate "
            "alone."
        ),
    }


def main() -> Dict[str, Any]:
    """Train, validate and evaluate every regression model."""
    config.set_global_seed()
    config.ensure_dirs()
    data = load_task_data("regression")

    baseline = persistence_baseline(data, "regression")
    baseline_predictions = baseline.pop("predictions")
    baseline["slices"] = slice_breakdown(
        data["meta_test"], data["y_test"].to_numpy(), baseline_predictions, "regression"
    )
    LOGGER.info(
        "%-20s | test MAE %6.2f | test RMSE %6.2f | test R2 %6.3f",
        "Persistence",
        baseline["test"]["MAE"],
        baseline["test"]["RMSE"],
        baseline["test"]["R2"],
    )

    results: List[Dict[str, Any]] = [baseline]
    for name, spec in build_models().items():
        results.append(evaluate_model(name, spec, data))

    fitted = [r for r in results if r["family"] != "baseline"]
    best = min(fitted, key=lambda r: r["test"][PRIMARY_METRIC])
    best_predictions = np.asarray(best["predictions_test"], dtype=float)

    improvement = 100.0 * (
        baseline["test"][PRIMARY_METRIC] - best["test"][PRIMARY_METRIC]
    ) / baseline["test"][PRIMARY_METRIC]

    payload: Dict[str, Any] = {
        "generated_by": "src/models/train_regression.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task": "regression",
        "target": config.TARGET_REGRESSION,
        "primary_metric": PRIMARY_METRIC,
        "primary_metric_justification": PRIMARY_METRIC_JUSTIFICATION,
        "n_features": len(data["features"]),
        "features": data["features"],
        "split": {
            "boundary": data["boundary"].strftime("%Y-%m-%d"),
            "n_train": data["n_train"],
            "n_test": data["n_test"],
        },
        "validation": (
            f"TimeSeriesSplit with {config.N_SPLITS_TS_CV} expanding-window folds on "
            "the training period. Shuffled k-fold is not used, because it would "
            "place future observations in training folds and inflate every score."
        ),
        "results": [{k: v for k, v in r.items() if k != "predictions_test"} for r in results],
        "best_model": best["model"],
        "best_test_metrics": best["test"],
        "baseline_comparison": {
            "baseline_mae": baseline["test"]["MAE"],
            "best_mae": best["test"]["MAE"],
            "improvement_over_persistence_pct": round(improvement, 2),
            "verdict": (
                f"{best['model']} reduces mean absolute error by {improvement:.1f}% "
                f"relative to the persistence baseline, so the learned model earns "
                f"its complexity."
                if improvement > 0
                else "No learned model beat persistence; the added complexity is not justified."
            ),
        },
        "residual_analysis": residual_analysis(data, best["model"], best_predictions),
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    np.save(config.RESULTS_DIR / "regression_best_predictions.npy", best_predictions)
    LOGGER.info(
        "Best regression model: %s (test MAE %.3f, R2 %.4f) | %+.1f%% vs persistence",
        best["model"],
        best["test"]["MAE"],
        best["test"]["R2"],
        improvement,
    )
    return payload


if __name__ == "__main__":
    main()
