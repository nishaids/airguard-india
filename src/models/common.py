"""Shared loading, splitting and metric utilities for the modelling stage.

Centralising these keeps a single definition of the train/test partition, the
cross-validation scheme and every metric, so that the regression, classification
and clustering modules cannot drift apart and the comparison tables they produce
are genuinely like-for-like.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import LabelEncoder

from src import config
from src.features.build import FEATURE_COLUMNS_PATH, FEATURES_PATH

LOGGER = config.get_logger(__name__)

#: Columns always carried alongside the selected features. They are used to build
#: the persistence baseline and the leakage demonstration, never fitted on.
AUX_COLUMNS: Tuple[str, ...] = ("AQI", "AQI_Bucket_ordinal")


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
def load_feature_columns() -> Dict[str, Any]:
    """Load the retained feature lists written by ``features/build.py``."""
    return json.loads(FEATURE_COLUMNS_PATH.read_text(encoding="utf-8"))


def load_task_data(task: str) -> Dict[str, Any]:
    """Assemble the supervised matrices for a task, split on the fixed date boundary.

    Parameters
    ----------
    task:
        ``"regression"`` or ``"classification"``.

    Returns
    -------
    dict
        ``X_train``, ``y_train``, ``X_test``, ``y_test``, the retained feature
        list, the split boundary, and the ``Date``/``City`` columns of each
        partition so that error can later be broken down by city and by period.

    Notes
    -----
    Rows whose target is missing are dropped, because a supervised model cannot
    learn from or be scored on an absent label. Rows whose *features* are
    incomplete are also dropped: after cleaning the only remaining gaps are the
    warm-up rows at the head of each city's series, where a 14-day rolling window
    does not yet have 14 days behind it. Dropping them is the honest alternative
    to back-filling a window that never existed.
    """
    columns = load_feature_columns()
    features = columns[task]
    target = (
        config.TARGET_REGRESSION if task == "regression" else config.TARGET_CLASSIFICATION
    )
    boundary = pd.Timestamp(columns["split_boundary"])

    frame = pd.read_csv(FEATURES_PATH, parse_dates=["Date"])
    # Auxiliary columns are always carried, independently of what the feature
    # selector retained. They are never handed to a model; they exist so that the
    # persistence baseline and the leakage demonstration can be constructed even
    # when the selector has dropped a column as redundant for modelling purposes.
    aux = [c for c in AUX_COLUMNS if c in frame.columns and c not in features]
    keep = list(dict.fromkeys(["City", "Date", target] + features + aux))
    frame = frame[keep].dropna()

    train = frame.loc[frame["Date"] < boundary]
    test = frame.loc[frame["Date"] >= boundary]

    assert len(train) and len(test), "empty partition"
    assert train["Date"].max() < boundary <= test["Date"].min(), "split boundary violated"

    LOGGER.info(
        "%s | %s features | train %s rows (%s to %s) | test %s rows (%s to %s)",
        task,
        len(features),
        f"{len(train):,}",
        train["Date"].min().date(),
        train["Date"].max().date(),
        f"{len(test):,}",
        test["Date"].min().date(),
        test["Date"].max().date(),
    )

    return {
        "task": task,
        "features": features,
        "target": target,
        "boundary": boundary,
        "X_train": train[features].reset_index(drop=True),
        "y_train": train[target].reset_index(drop=True),
        "X_test": test[features].reset_index(drop=True),
        "y_test": test[target].reset_index(drop=True),
        "aux_train": train[[c for c in AUX_COLUMNS if c in train.columns]].reset_index(drop=True),
        "aux_test": test[[c for c in AUX_COLUMNS if c in test.columns]].reset_index(drop=True),
        "meta_train": train[["City", "Date"]].reset_index(drop=True),
        "meta_test": test[["City", "Date"]].reset_index(drop=True),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "rows_dropped_for_missing": int(
            len(pd.read_csv(FEATURES_PATH, usecols=["City"])) - len(frame)
        ),
    }


def time_series_cv(n_splits: int = config.N_SPLITS_TS_CV) -> TimeSeriesSplit:
    """Return the cross-validation splitter used everywhere in this project.

    ``TimeSeriesSplit`` produces expanding-window folds in which every validation
    fold lies strictly after its training fold. A shuffled k-fold would place
    future observations in the training set and is therefore invalid here; the
    resulting optimism would be large, because consecutive days are strongly
    autocorrelated.
    """
    return TimeSeriesSplit(n_splits=n_splits)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute the regression metric suite.

    ``MAPE`` is computed on observations whose true value is at least 1, since
    the ratio is undefined at zero and unstable just above it. The count of
    observations actually used is returned so the figure is interpretable.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    safe = np.abs(y_true) >= 1.0
    return {
        "MAE": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "RMSE": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "R2": round(float(r2_score(y_true, y_pred)), 4),
        "MAPE_pct": round(
            float(np.mean(np.abs((y_true[safe] - y_pred[safe]) / y_true[safe])) * 100), 4
        ),
        "MAPE_n_used": int(safe.sum()),
        "median_absolute_error": round(float(np.median(np.abs(y_true - y_pred))), 4),
        "bias": round(float(np.mean(y_pred - y_true)), 4),
        "n": int(len(y_true)),
    }


def classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_score: Optional[np.ndarray] = None,
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Compute the classification metric suite.

    Macro-averaged F1 is the primary metric for this project. Accuracy is
    reported but is not decisive: with a 6.6-fold imbalance between the most and
    least common bucket, a model that never predicts the rarest class can post a
    respectable accuracy while failing at exactly the task that matters for
    health protection.
    """
    labels = labels or [
        label for label in config.AQI_BUCKETS if label in set(np.unique(y_true))
    ]
    per_class_f1 = f1_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    per_class_precision = precision_score(
        y_true, y_pred, labels=labels, average=None, zero_division=0
    )
    per_class_recall = recall_score(
        y_true, y_pred, labels=labels, average=None, zero_division=0
    )
    support = [int((np.asarray(y_true) == label).sum()) for label in labels]

    metrics: Dict[str, Any] = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "macro_precision": round(
            float(precision_score(y_true, y_pred, average="macro", zero_division=0)), 4
        ),
        "macro_recall": round(
            float(recall_score(y_true, y_pred, average="macro", zero_division=0)), 4
        ),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "weighted_precision": round(
            float(precision_score(y_true, y_pred, average="weighted", zero_division=0)), 4
        ),
        "weighted_recall": round(
            float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 4
        ),
        "weighted_f1": round(
            float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4
        ),
        "cohen_kappa": round(float(cohen_kappa_score(y_true, y_pred)), 4),
        "per_class": [
            {
                "class": label,
                "precision": round(float(per_class_precision[idx]), 4),
                "recall": round(float(per_class_recall[idx]), 4),
                "f1": round(float(per_class_f1[idx]), 4),
                "support": support[idx],
            }
            for idx, label in enumerate(labels)
        ],
        "labels": labels,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "confusion_matrix_normalised": np.round(
            confusion_matrix(y_true, y_pred, labels=labels, normalize="true"), 4
        ).tolist(),
        "n": int(len(y_true)),
    }

    if y_score is not None:
        # scikit-learn requires `labels` in lexicographic order for the
        # one-versus-rest multiclass ROC-AUC. Our label list is in CPCB severity
        # order, which is what makes every other table readable, so the score
        # columns are reordered here rather than the reporting order being
        # sacrificed.
        sorted_labels = sorted(labels)
        reorder = [labels.index(label) for label in sorted_labels]
        scores_sorted = np.asarray(y_score)[:, reorder]
        try:
            metrics["roc_auc_ovr_macro"] = round(
                float(
                    roc_auc_score(
                        y_true, scores_sorted, multi_class="ovr", average="macro",
                        labels=sorted_labels,
                    )
                ),
                4,
            )
            metrics["roc_auc_ovr_weighted"] = round(
                float(
                    roc_auc_score(
                        y_true, scores_sorted, multi_class="ovr", average="weighted",
                        labels=sorted_labels,
                    )
                ),
                4,
            )
            metrics["roc_auc_per_class"] = {
                label: round(
                    float(
                        roc_auc_score(
                            (np.asarray(y_true) == label).astype(int),
                            scores_sorted[:, idx],
                        )
                    ),
                    4,
                )
                for idx, label in enumerate(sorted_labels)
                if (np.asarray(y_true) == label).any()
            }
        except ValueError as exc:
            metrics["roc_auc_ovr_macro"] = None
            metrics["roc_auc_note"] = f"not computable: {exc}"

    # Severity-aware error: how far, in ordered bucket positions, predictions land.
    true_ordinal = pd.Series(y_true).map(config.AQI_BUCKET_ORDINAL).to_numpy(dtype=float)
    pred_ordinal = pd.Series(y_pred).map(config.AQI_BUCKET_ORDINAL).to_numpy(dtype=float)
    valid = ~(np.isnan(true_ordinal) | np.isnan(pred_ordinal))
    metrics["mean_absolute_ordinal_error"] = round(
        float(np.mean(np.abs(true_ordinal[valid] - pred_ordinal[valid]))), 4
    )
    metrics["pct_within_one_band"] = round(
        float(np.mean(np.abs(true_ordinal[valid] - pred_ordinal[valid]) <= 1) * 100), 2
    )
    metrics["pct_underestimating_severity"] = round(
        float(np.mean(pred_ordinal[valid] < true_ordinal[valid]) * 100), 2
    )
    return metrics


def probability_scores(model: Any, features: pd.DataFrame, labels: List[str]) -> Optional[np.ndarray]:
    """Return class scores for ROC-AUC, using probabilities where available.

    Estimators without ``predict_proba`` (a support vector classifier fitted
    without Platt scaling, for instance) expose ``decision_function`` instead.
    One-versus-rest ROC-AUC is rank-based, so decision-function margins serve
    equally well and avoid the substantial cost of internal probability
    calibration.
    """
    classes = getattr(model, "classes_", None)
    if classes is None:
        return None

    if hasattr(model, "predict_proba"):
        scores = model.predict_proba(features)
    elif hasattr(model, "decision_function"):
        scores = model.decision_function(features)
        if scores.ndim == 1:
            scores = np.column_stack([-scores, scores])
    else:
        return None

    # Reorder columns to the caller's label order, inserting a floor for any
    # class the estimator never saw.
    order = []
    for label in labels:
        matches = np.flatnonzero(classes == label)
        order.append(int(matches[0]) if matches.size else -1)
    if any(idx < 0 for idx in order):
        padded = np.full((scores.shape[0], len(labels)), scores.min() - 1.0)
        for position, idx in enumerate(order):
            if idx >= 0:
                padded[:, position] = scores[:, idx]
        return padded
    return scores[:, order]


# --------------------------------------------------------------------------- #
# Slices
# --------------------------------------------------------------------------- #
def slice_breakdown(
    meta: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    task: str,
    y_score: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Break test performance down by city and by calendar period.

    The lockdown slice is reported separately so that the effect of the 2020
    regime change on headline error is visible rather than buried in an average.
    """
    frame = meta.copy()
    frame["y_true"] = y_true
    frame["y_pred"] = y_pred

    scorer = regression_metrics if task == "regression" else (
        lambda a, b: {
            k: v
            for k, v in classification_metrics(a, b).items()
            if k in ("accuracy", "macro_f1", "weighted_f1", "balanced_accuracy", "n")
        }
    )

    by_city = [
        {"city": city, **scorer(group["y_true"].to_numpy(), group["y_pred"].to_numpy())}
        for city, group in frame.groupby("City")
        if len(group) >= 20
    ]

    lockdown = frame["Date"].between(
        pd.Timestamp(config.LOCKDOWN_START), pd.Timestamp(config.LOCKDOWN_END)
    )
    periods: Dict[str, Any] = {}
    for name, mask in (
        ("pre_2020", frame["Date"] < pd.Timestamp("2020-01-01")),
        ("2020_before_lockdown", (frame["Date"] >= pd.Timestamp("2020-01-01")) & ~lockdown & (frame["Date"] < pd.Timestamp(config.LOCKDOWN_START))),
        ("lockdown_stress_test", lockdown),
        ("post_lockdown", frame["Date"] > pd.Timestamp(config.LOCKDOWN_END)),
    ):
        if int(mask.sum()) >= 20:
            subset = frame.loc[mask]
            periods[name] = {
                "date_range": [
                    subset["Date"].min().strftime("%Y-%m-%d"),
                    subset["Date"].max().strftime("%Y-%m-%d"),
                ],
                **scorer(subset["y_true"].to_numpy(), subset["y_pred"].to_numpy()),
            }

    return {"by_city": by_city, "by_period": periods}


def persistence_baseline(data: Dict[str, Any], task: str) -> Dict[str, Any]:
    """Score the naive persistence forecast: tomorrow equals today.

    This baseline is not decoration. Daily AQI is strongly autocorrelated, so
    persistence is a genuinely competitive forecaster, and any learned model that
    does not beat it has added nothing. Reporting it is what makes the headline
    R-squared and macro-F1 interpretable instead of merely large.
    """
    source = pd.concat([data["X_test"], data["aux_test"]], axis=1)
    source = source.loc[:, ~source.columns.duplicated()]
    if task == "regression":
        predictions = source["AQI"].to_numpy()
        metrics = regression_metrics(data["y_test"].to_numpy(), predictions)
    else:
        ordinal = source["AQI_Bucket_ordinal"].round().astype(int).clip(0, 5)
        inverse = {v: k for k, v in config.AQI_BUCKET_ORDINAL.items()}
        predictions = ordinal.map(inverse).to_numpy()
        metrics = classification_metrics(data["y_test"].to_numpy(), predictions)

    return {
        "model": "Persistence baseline (tomorrow = today)",
        "family": "baseline",
        "test": metrics,
        "predictions": predictions,
        "note": (
            "Not a fitted model. Today's observed value is carried forward as the "
            "forecast for tomorrow. Any learned model must beat this to justify "
            "itself."
        ),
    }


# --------------------------------------------------------------------------- #
# Estimator adapters
# --------------------------------------------------------------------------- #
class LabelEncodedClassifier(BaseEstimator, ClassifierMixin):
    """Adapt an estimator that requires integer labels to string class labels.

    XGBoost requires the target to be encoded as consecutive integers. Wrapping it
    keeps the rest of the pipeline working with the readable CPCB bucket names, so
    per-class metrics and confusion matrices stay interpretable without a separate
    decoding step at every call site.

    The class lives in this shared module rather than in a training script on
    purpose. Pickle records the defining module by name, so a class defined inside
    a script executed as ``__main__`` produces artefacts that only that script can
    load. Defining it here means every joblib artefact containing this wrapper can
    be deserialised by the evaluation modules and by the deployed application.
    """

    def __init__(self, estimator: Any) -> None:
        self.estimator = estimator

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "LabelEncodedClassifier":
        """Fit the wrapped estimator on integer-encoded labels."""
        self.encoder_ = LabelEncoder().fit(y)
        self.classes_ = self.encoder_.classes_
        self.estimator_ = clone(self.estimator)
        self.estimator_.fit(X, self.encoder_.transform(y))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict and decode back to the original class labels."""
        return self.encoder_.inverse_transform(self.estimator_.predict(X))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return class probabilities in the order of ``classes_``."""
        return self.estimator_.predict_proba(X)
