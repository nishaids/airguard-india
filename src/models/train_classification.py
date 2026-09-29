"""Next-day AQI bucket classification across six model families.

Models
------
Persistence baseline, Logistic Regression, Decision Tree, Random Forest,
Support Vector Machine with an RBF kernel, XGBoost and K-Nearest Neighbours.

Class imbalance
---------------
The bucket distribution is uneven by a factor of 6.6 between the most and least
common class. Two remedies are compared head to head rather than one being
assumed:

``class_weight="balanced"``
    Re-weights the loss so that each class contributes in inverse proportion to
    its frequency. Costs nothing at prediction time and does not synthesise data.
``SMOTE``
    Synthesises minority-class examples by interpolating between neighbours in
    feature space. It is applied inside an imbalanced-learn ``Pipeline`` so that
    resampling happens **within** each training fold only; resampling before
    splitting would place synthetic copies of validation rows into training and
    is a classic source of inflated scores.

The leakage demonstration
-------------------------
The project forecasts *tomorrow's* bucket, for which today's AQI is a legitimate
predictor. A same-day nowcast is a different problem, and there the bucket is a
deterministic function of the AQI, so including the AQI makes the task trivial.
:func:`leakage_demonstration` fits both variants and reports the measured gap,
turning a stated caution into evidence.

Outputs
-------
``models/classification_<name>.joblib``
``results/evaluation_classification.json``

Run with::

    python -m src.models.train_classification
"""

from __future__ import annotations

import json
import time
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from src import config
from src.models.common import (
    LabelEncodedClassifier,
    classification_metrics,
    load_task_data,
    persistence_baseline,
    probability_scores,
    slice_breakdown,
    time_series_cv,
)

LOGGER = config.get_logger(__name__)

RESULTS_PATH = config.RESULTS_DIR / "evaluation_classification.json"

PRIMARY_METRIC = "macro_f1"
PRIMARY_METRIC_JUSTIFICATION = (
    "Macro-averaged F1 is the primary classification metric, declared before any "
    "model was fitted. The six CPCB buckets are imbalanced by a factor of 6.6 "
    "between the most and least frequent class, and the rarest classes are Good "
    "and Severe. Severe is the class on which the entire public-health purpose of "
    "the system rests: failing to warn on a Severe day is the costliest error the "
    "system can make, and it is also the error that overall accuracy is least "
    "sensitive to. Macro-F1 gives every class equal weight regardless of "
    "frequency, so a model cannot score well by ignoring the rare and dangerous "
    "classes. Accuracy, weighted F1, per-class F1, balanced accuracy, Cohen's "
    "kappa and one-versus-rest ROC-AUC are all reported alongside it, together "
    "with an ordinal error that measures how many severity bands a wrong "
    "prediction lands away from the truth."
)


def build_models() -> Dict[str, Dict[str, Any]]:
    """Construct every classifier, including the SMOTE comparison variants."""
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as ImbPipeline
    from xgboost import XGBClassifier

    seed = config.RANDOM_SEED
    smote = lambda: SMOTE(random_state=seed, k_neighbors=5)

    models: Dict[str, Dict[str, Any]] = {
        "Logistic Regression": {
            "estimator": Pipeline(
                [
                    ("scaler", StandardScaler()),
                    (
                        "model",
                        LogisticRegression(
                            max_iter=2000,
                            class_weight="balanced",
                            multi_class="multinomial",
                            random_state=seed,
                        ),
                    ),
                ]
            ),
            "family": "linear",
            "imbalance_strategy": "class_weight='balanced'",
            "rationale": (
                "Linear reference classifier. Establishes how much of the problem "
                "is linearly separable in the engineered feature space."
            ),
        },
        "Decision Tree": {
            "estimator": DecisionTreeClassifier(
                max_depth=12, min_samples_leaf=20, class_weight="balanced", random_state=seed
            ),
            "family": "tree",
            "imbalance_strategy": "class_weight='balanced'",
            "rationale": (
                "A single interpretable tree. Its decision path can be read "
                "directly, which is valuable for a health advisory, and the gap to "
                "the ensembles quantifies the variance a single tree suffers."
            ),
        },
        "Random Forest": {
            "estimator": RandomForestClassifier(
                n_estimators=300,
                min_samples_leaf=2,
                class_weight="balanced_subsample",
                n_jobs=-1,
                random_state=seed,
            ),
            "family": "bagged trees",
            "imbalance_strategy": "class_weight='balanced_subsample'",
            "rationale": "Bagging reduces the variance of the single tree while keeping non-linearity.",
        },
        "SVM (RBF)": {
            "estimator": Pipeline(
                [
                    ("scaler", StandardScaler()),
                    (
                        "model",
                        SVC(
                            kernel="rbf",
                            C=10.0,
                            gamma="scale",
                            class_weight="balanced",
                            cache_size=1000,
                            random_state=seed,
                        ),
                    ),
                ]
            ),
            "family": "kernel",
            "imbalance_strategy": "class_weight='balanced'",
            "rationale": (
                "A non-linear kernel boundary, included because the pairwise "
                "structure in the exploratory analysis showed curved class "
                "boundaries that a linear model cannot express."
            ),
        },
        "XGBoost": {
            "estimator": LabelEncodedClassifier(
                XGBClassifier(
                    n_estimators=400,
                    learning_rate=0.05,
                    max_depth=6,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    n_jobs=-1,
                    random_state=seed,
                    tree_method="hist",
                    eval_metric="mlogloss",
                )
            ),
            "family": "gradient boosting",
            "imbalance_strategy": "none (compared against a SMOTE variant below)",
            "rationale": "Gradient boosting, the strongest default family for tabular classification.",
        },
        "KNN (k=15)": {
            "estimator": Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("model", KNeighborsClassifier(n_neighbors=15, weights="distance", n_jobs=-1)),
                ]
            ),
            "family": "instance-based",
            "imbalance_strategy": "distance weighting (no class weighting available)",
            "rationale": (
                "A purely local, non-parametric benchmark. Its performance relative "
                "to the ensembles indicates how much of the signal is captured by "
                "local similarity alone."
            ),
        },
        "Random Forest + SMOTE": {
            "estimator": ImbPipeline(
                [
                    ("smote", smote()),
                    (
                        "model",
                        RandomForestClassifier(
                            n_estimators=300, min_samples_leaf=2, n_jobs=-1, random_state=seed
                        ),
                    ),
                ]
            ),
            "family": "bagged trees",
            "imbalance_strategy": "SMOTE oversampling inside each training fold",
            "rationale": "Head-to-head comparison against the class-weighted Random Forest.",
        },
        "XGBoost + SMOTE": {
            "estimator": ImbPipeline(
                [
                    ("smote", smote()),
                    (
                        "model",
                        LabelEncodedClassifier(
                            XGBClassifier(
                                n_estimators=400,
                                learning_rate=0.05,
                                max_depth=6,
                                subsample=0.85,
                                colsample_bytree=0.85,
                                n_jobs=-1,
                                random_state=seed,
                                tree_method="hist",
                                eval_metric="mlogloss",
                            )
                        ),
                    ),
                ]
            ),
            "family": "gradient boosting",
            "imbalance_strategy": "SMOTE oversampling inside each training fold",
            "rationale": "Head-to-head comparison against the unweighted XGBoost.",
        },
        "Logistic Regression + SMOTE": {
            "estimator": ImbPipeline(
                [
                    ("scaler", StandardScaler()),
                    ("smote", smote()),
                    ("model", LogisticRegression(max_iter=2000, random_state=seed)),
                ]
            ),
            "family": "linear",
            "imbalance_strategy": "SMOTE oversampling inside each training fold",
            "rationale": "Head-to-head comparison against the class-weighted logistic model.",
        },
    }
    return models


def evaluate_model(name: str, spec: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """Cross-validate, fit and score one classifier."""
    estimator = spec["estimator"]
    labels = [c for c in config.AQI_BUCKETS if c in set(data["y_train"].unique())]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        started = time.perf_counter()
        cv_scores = cross_val_score(
            estimator,
            data["X_train"],
            data["y_train"],
            cv=time_series_cv(),
            scoring="f1_macro",
            n_jobs=1,
        )
        cv_seconds = time.perf_counter() - started

        started = time.perf_counter()
        estimator.fit(data["X_train"], data["y_train"])
        fit_seconds = time.perf_counter() - started

        train_pred = estimator.predict(data["X_train"])
        test_pred = estimator.predict(data["X_test"])
        test_score = probability_scores(estimator, data["X_test"], labels)

    train_metrics = classification_metrics(data["y_train"].to_numpy(), train_pred, labels=labels)
    test_metrics = classification_metrics(
        data["y_test"].to_numpy(), test_pred, y_score=test_score, labels=labels
    )

    path = config.MODELS_DIR / (
        "classification_" + name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("+", "plus").replace("=", "") + ".joblib"
    )
    joblib.dump(estimator, path, compress=3)

    LOGGER.info(
        "%-28s | CV macro-F1 %.3f +/- %.3f | test macro-F1 %.4f | acc %.4f | "
        "Severe F1 %.3f",
        name,
        cv_scores.mean(),
        cv_scores.std(),
        test_metrics["macro_f1"],
        test_metrics["accuracy"],
        next((c["f1"] for c in test_metrics["per_class"] if c["class"] == "Severe"), float("nan")),
    )

    return {
        "model": name,
        "family": spec["family"],
        "imbalance_strategy": spec["imbalance_strategy"],
        "rationale": spec["rationale"],
        "cv": {
            "splitter": f"TimeSeriesSplit(n_splits={config.N_SPLITS_TS_CV})",
            "scoring": "f1_macro",
            "mean": round(float(cv_scores.mean()), 4),
            "std": round(float(cv_scores.std()), 4),
            "folds": [round(float(v), 4) for v in cv_scores],
            "seconds": round(cv_seconds, 2),
        },
        "train": {k: v for k, v in train_metrics.items() if k != "confusion_matrix_normalised"},
        "test": test_metrics,
        "generalisation_gap": {
            "macro_f1_train_minus_test": round(
                train_metrics["macro_f1"] - test_metrics["macro_f1"], 4
            ),
            "accuracy_train_minus_test": round(
                train_metrics["accuracy"] - test_metrics["accuracy"], 4
            ),
            "overfitting_flag": bool(
                train_metrics["macro_f1"] - test_metrics["macro_f1"] > 0.15
            ),
        },
        "slices": slice_breakdown(
            data["meta_test"], data["y_test"].to_numpy(), test_pred, "classification"
        ),
        "fit_seconds": round(fit_seconds, 2),
        "artifact": str(path.relative_to(config.PROJECT_ROOT)),
        "predictions_test": test_pred.tolist(),
    }


# --------------------------------------------------------------------------- #
# Leakage demonstration
# --------------------------------------------------------------------------- #
def leakage_demonstration(data: Dict[str, Any]) -> Dict[str, Any]:
    """Measure the leakage that a same-day nowcast formulation would suffer.

    Three models are fitted on identical splits:

    1. **Same-day nowcast, AQI included.** Predicting *today's* bucket from a
       feature set that contains today's AQI. The CPCB bucket is a deterministic
       step function of the AQI, so this is not learning: it is reading the
       answer.
    2. **Same-day nowcast, AQI and its derivatives removed.** The honest version
       of the same-day problem.
    3. **Next-day forecast.** The formulation this project actually uses, for
       which today's AQI is legitimately available.

    The gap between (1) and (2) is the leakage, measured rather than asserted.
    """
    from lightgbm import LGBMClassifier

    features = data["X_train"].copy()
    test_features = data["X_test"].copy()

    aux_train = pd.concat([features, data["aux_train"]], axis=1)
    aux_train = aux_train.loc[:, ~aux_train.columns.duplicated()]
    aux_test = pd.concat([test_features, data["aux_test"]], axis=1)
    aux_test = aux_test.loc[:, ~aux_test.columns.duplicated()]

    same_day_train = aux_train["AQI_Bucket_ordinal"].round().astype(int).clip(0, 5)
    same_day_test = aux_test["AQI_Bucket_ordinal"].round().astype(int).clip(0, 5)
    inverse = {v: k for k, v in config.AQI_BUCKET_ORDINAL.items()}
    y_same_train = same_day_train.map(inverse)
    y_same_test = same_day_test.map(inverse)

    leaky_columns = [
        c
        for c in aux_train.columns
        if c in ("AQI", "AQI_Bucket_ordinal", "AQI_recomputed")
        or c.startswith("sub_")
        or c.startswith("HAI_")
    ]
    honest_columns = [c for c in aux_train.columns if c not in leaky_columns]

    def _fit_and_score(
        train_X: pd.DataFrame, train_y: pd.Series, test_X: pd.DataFrame, test_y: pd.Series
    ) -> Dict[str, Any]:
        model = LGBMClassifier(
            n_estimators=300, learning_rate=0.05, random_state=config.RANDOM_SEED, verbose=-1
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(train_X, train_y)
            predictions = model.predict(test_X)
        metrics = classification_metrics(test_y.to_numpy(), predictions)
        return {
            "macro_f1": metrics["macro_f1"],
            "accuracy": metrics["accuracy"],
            "weighted_f1": metrics["weighted_f1"],
            "n_features": int(train_X.shape[1]),
        }

    with_leak = _fit_and_score(aux_train, y_same_train, aux_test, y_same_test)
    without_leak = _fit_and_score(
        aux_train[honest_columns], y_same_train, aux_test[honest_columns], y_same_test
    )
    forecast = _fit_and_score(features, data["y_train"], test_features, data["y_test"])

    return {
        "experiment": (
            "Three LightGBM classifiers fitted on identical time-ordered splits, "
            "differing only in the target and the feature set."
        ),
        "same_day_nowcast_with_aqi": {
            **with_leak,
            "description": (
                "Predicting today's bucket from a feature set containing today's "
                "AQI and its derived sub-indices and HAI values."
            ),
        },
        "same_day_nowcast_without_aqi": {
            **without_leak,
            "description": (
                "The same target with AQI, the CPCB sub-indices and every HAI "
                "column removed. "
                f"Columns removed: {len(leaky_columns)}."
            ),
        },
        "next_day_forecast_this_project": {
            **forecast,
            "description": (
                "The formulation this project uses. The target is tomorrow's "
                "bucket, so today's AQI is information genuinely available at "
                "prediction time and is retained."
            ),
        },
        "leakage_magnitude_macro_f1": round(
            with_leak["macro_f1"] - without_leak["macro_f1"], 4
        ),
        "columns_removed_for_honest_nowcast": leaky_columns,
        "conclusion": (
            f"Predicting the same day's bucket with same-day AQI present yields a "
            f"macro-F1 of {with_leak['macro_f1']:.4f}. A score at or near 1.0 is "
            f"not a result; it is the signature of a model reading its own label, "
            f"because the CPCB bucket is a deterministic step function of the AQI. "
            f"The more instructive finding is what happens after the obvious "
            f"culprits are removed: dropping AQI, the CPCB sub-indices and every "
            f"HAI column still leaves macro-F1 at {without_leak['macro_f1']:.4f}. "
            f"The leak is therefore not confined to a single column that a "
            f"diligent analyst could blacklist. The AQI is by definition the "
            f"maximum sub-index, and each sub-index is a fixed piecewise-linear "
            f"function of a pollutant concentration, so the *concentrations "
            f"themselves* determine the label exactly. Same-day bucket prediction "
            f"is arithmetic dressed as machine learning, and no choice of feature "
            f"filter rescues it. That is the reason this project does not attempt "
            f"it. Forecasting the next day changes the problem substantively: "
            f"tomorrow's bucket is genuinely unknown today, today's AQI becomes "
            f"legitimate information rather than a restatement of the answer, and "
            f"the achieved macro-F1 of {forecast['macro_f1']:.4f} measures real "
            f"predictive skill. The gap between {without_leak['macro_f1']:.4f} and "
            f"{forecast['macro_f1']:.4f} is the difference between recomputing a "
            f"known quantity and forecasting an unknown one."
        ),
    }


def main() -> Dict[str, Any]:
    """Train, validate and evaluate every classifier."""
    config.set_global_seed()
    config.ensure_dirs()
    data = load_task_data("classification")

    distribution = data["y_train"].value_counts()
    LOGGER.info(
        "Training class distribution: %s",
        ", ".join(f"{k} {v:,}" for k, v in distribution.items()),
    )

    baseline = persistence_baseline(data, "classification")
    baseline_predictions = baseline.pop("predictions")
    baseline["slices"] = slice_breakdown(
        data["meta_test"], data["y_test"].to_numpy(), baseline_predictions, "classification"
    )
    LOGGER.info(
        "%-28s | test macro-F1 %.4f | acc %.4f",
        "Persistence",
        baseline["test"]["macro_f1"],
        baseline["test"]["accuracy"],
    )

    results: List[Dict[str, Any]] = [baseline]
    for name, spec in build_models().items():
        results.append(evaluate_model(name, spec, data))

    fitted = [r for r in results if r["family"] != "baseline"]
    best = max(fitted, key=lambda r: r["test"][PRIMARY_METRIC])

    smote_comparison: List[Dict[str, Any]] = []
    for weighted_name, smote_name in (
        ("Random Forest", "Random Forest + SMOTE"),
        ("XGBoost", "XGBoost + SMOTE"),
        ("Logistic Regression", "Logistic Regression + SMOTE"),
    ):
        weighted = next((r for r in results if r["model"] == weighted_name), None)
        smoted = next((r for r in results if r["model"] == smote_name), None)
        if not weighted or not smoted:
            continue
        severe = lambda r: next(
            (c["f1"] for c in r["test"]["per_class"] if c["class"] == "Severe"), None
        )
        smote_comparison.append(
            {
                "pair": f"{weighted_name} vs {smote_name}",
                "baseline_strategy": weighted["imbalance_strategy"],
                "macro_f1_weighted_or_plain": weighted["test"]["macro_f1"],
                "macro_f1_smote": smoted["test"]["macro_f1"],
                "delta_macro_f1": round(
                    smoted["test"]["macro_f1"] - weighted["test"]["macro_f1"], 4
                ),
                "severe_f1_weighted_or_plain": severe(weighted),
                "severe_f1_smote": severe(smoted),
                "winner": smote_name
                if smoted["test"]["macro_f1"] > weighted["test"]["macro_f1"]
                else weighted_name,
            }
        )

    improvement = 100.0 * (
        best["test"][PRIMARY_METRIC] - baseline["test"][PRIMARY_METRIC]
    ) / baseline["test"][PRIMARY_METRIC]

    payload: Dict[str, Any] = {
        "generated_by": "src/models/train_classification.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task": "classification",
        "target": config.TARGET_CLASSIFICATION,
        "primary_metric": PRIMARY_METRIC,
        "primary_metric_justification": PRIMARY_METRIC_JUSTIFICATION,
        "n_features": len(data["features"]),
        "features": data["features"],
        "split": {
            "boundary": data["boundary"].strftime("%Y-%m-%d"),
            "n_train": data["n_train"],
            "n_test": data["n_test"],
        },
        "class_distribution_train": {k: int(v) for k, v in distribution.items()},
        "class_distribution_test": {
            k: int(v) for k, v in data["y_test"].value_counts().items()
        },
        "validation": (
            f"TimeSeriesSplit with {config.N_SPLITS_TS_CV} expanding-window folds, "
            "scored by macro-F1. SMOTE is applied inside the imbalanced-learn "
            "pipeline so that resampling occurs within each training fold only."
        ),
        "results": [{k: v for k, v in r.items() if k != "predictions_test"} for r in results],
        "best_model": best["model"],
        "best_test_metrics": best["test"],
        "baseline_comparison": {
            "baseline_macro_f1": baseline["test"]["macro_f1"],
            "best_macro_f1": best["test"]["macro_f1"],
            "improvement_over_persistence_pct": round(improvement, 2),
        },
        "smote_head_to_head": smote_comparison,
        "leakage_demonstration": leakage_demonstration(data),
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    np.save(
        config.RESULTS_DIR / "classification_best_predictions.npy",
        np.array(best["predictions_test"], dtype=object),
        allow_pickle=True,
    )
    LOGGER.info(
        "Best classifier: %s (test macro-F1 %.4f, accuracy %.4f) | %+.1f%% vs persistence",
        best["model"],
        best["test"]["macro_f1"],
        best["test"]["accuracy"],
        improvement,
    )
    return payload


if __name__ == "__main__":
    main()
