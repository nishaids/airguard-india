"""Pilot evidence for the AirGuard 2.0 research gaps, on the existing record.

These are *pilot* experiments. They use only the 2015-2020 historical dataset
the current system was built on, so they say nothing about live performance.
Their purpose is narrower: before a roadmap commits months of work to
uncertainty quantification, cross-city generalisation and selective
prediction, check on data already in hand whether each of those gaps shows a
real, measurable effect -- and whether the obvious fix actually behaves the way
the roadmap assumes.

Four questions:

1. **Calibration.** The application displays the classifier's top-class
   probability as "confidence". Is that number honest?
2. **Intervals.** Do distribution-free prediction intervals reach their nominal
   coverage on the held-out future, overall and on the severe days that matter?
3. **Unseen cities.** How much accuracy is lost when a city is absent from
   training entirely (leave-one-city-out)?
4. **Abstention.** If the model declines to forecast when it is least certain,
   which days does it actually decline -- and is that safe?

Nothing here touches the fitted production artefacts; every model is refitted
on a *proper training* slice so that a later *calibration* slice stays unseen.

Run with::

    python -m src.research.pilot_trust
"""

from __future__ import annotations

import json
import math
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd

from src import config
from src.models.common import load_task_data

OUTPUT_PATH = config.RESULTS_DIR / "pilot_trust.json"

ALPHA = 0.10  # 90 per cent nominal coverage
CALIBRATION_FRACTION = 0.20
CITY_IDENTITY_FEATURES = ["City_target_enc"]
BANDS = config.AQI_BUCKETS


def _band(values: np.ndarray) -> np.ndarray:
    edges = [b[2] for b in config.AQI_BUCKET_BOUNDS[:-1]]
    return np.array(BANDS)[np.digitize(values, edges, right=True)]


def _tuned_params() -> Dict[str, Any]:
    report = json.loads((config.RESULTS_DIR / "tuning_report.json").read_text(encoding="utf-8"))
    return dict(report["regression"]["best_params"])


def _fit(X: pd.DataFrame, y: pd.Series, **overrides: Any):
    from lightgbm import LGBMRegressor

    params = {**_tuned_params(), "random_state": config.RANDOM_SEED, "verbose": -1, "n_jobs": 4}
    params.update(overrides)
    model = LGBMRegressor(**params)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X, y)
    return model


def _conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    n = len(scores)
    level = min(1.0, math.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(scores, level, method="higher"))


def _coverage_table(y: np.ndarray, lo: np.ndarray, hi: np.ndarray, groups: np.ndarray, order: List[str]) -> List[Dict[str, Any]]:
    rows = []
    for g in order:
        mask = groups == g
        if not mask.any():
            continue
        rows.append(
            {
                "group": g,
                "n": int(mask.sum()),
                "coverage_pct": round(100 * float(((y[mask] >= lo[mask]) & (y[mask] <= hi[mask])).mean()), 1),
                "mean_width": round(float((hi[mask] - lo[mask]).mean()), 1),
            }
        )
    return rows


def _summary(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> Dict[str, float]:
    return {
        "coverage_pct": round(100 * float(((y >= lo) & (y <= hi)).mean()), 2),
        "mean_width": round(float((hi - lo).mean()), 2),
        "median_width": round(float(np.median(hi - lo)), 2),
    }


# --------------------------------------------------------------------------- #
# 1. Classifier calibration
# --------------------------------------------------------------------------- #
def classifier_calibration() -> Dict[str, Any]:
    data = load_task_data("classification")
    y = data["y_test"].to_numpy()
    out: Dict[str, Any] = {}

    for label, name in (
        ("deployed_on_vercel_lightgbm_smote", "deployment_classification_lightgbm.joblib"),
        ("reported_best_xgboost_smote_tuned", "tuned_classification.joblib"),
    ):
        path = config.MODELS_DIR / name
        if not path.exists():
            continue
        model = joblib.load(path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            proba = model.predict_proba(data["X_test"])
        classes = np.array(list(model.classes_))
        top = proba.argmax(axis=1)
        confidence = proba.max(axis=1)
        correct = classes[top] == y

        bins = np.linspace(0, 1, 11)
        ece = 0.0
        reliability = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            mask = (confidence > lo) & (confidence <= hi)
            if not mask.any():
                continue
            gap = abs(float(correct[mask].mean()) - float(confidence[mask].mean()))
            ece += gap * mask.mean()
            reliability.append(
                {
                    "bin": f"{lo:.1f}-{hi:.1f}",
                    "n": int(mask.sum()),
                    "mean_confidence": round(float(confidence[mask].mean()), 3),
                    "accuracy": round(float(correct[mask].mean()), 3),
                }
            )

        onehot = (classes[None, :] == y[:, None]).astype(float)
        very_sure = confidence >= 0.95
        out[label] = {
            "accuracy": round(float(correct.mean()), 4),
            "mean_confidence": round(float(confidence.mean()), 4),
            "overconfidence_gap": round(float(confidence.mean() - correct.mean()), 4),
            "expected_calibration_error": round(float(ece), 4),
            "brier_multiclass": round(float(((proba - onehot) ** 2).sum(axis=1).mean()), 4),
            "share_shown_as_95pct_or_more": round(100 * float(very_sure.mean()), 1),
            "accuracy_when_shown_as_95pct_or_more": round(100 * float(correct[very_sure].mean()), 1) if very_sure.any() else None,
            "reliability": reliability,
        }
    return out


# --------------------------------------------------------------------------- #
# 2-4. Regression: intervals, unseen cities, abstention
# --------------------------------------------------------------------------- #
def regression_experiments() -> Dict[str, Any]:
    data = load_task_data("regression")
    X_train, y_train = data["X_train"], data["y_train"]
    X_test, y_test = data["X_test"], data["y_test"].to_numpy()
    meta_train, meta_test = data["meta_train"], data["meta_test"]

    # Chronological proper-training / calibration split inside the training period.
    cut = meta_train["Date"].sort_values().iloc[int(len(meta_train) * (1 - CALIBRATION_FRACTION))]
    is_fit = (meta_train["Date"] < cut).to_numpy()
    X_fit, y_fit = X_train[is_fit], y_train[is_fit]
    X_cal, y_cal = X_train[~is_fit], y_train[~is_fit].to_numpy()

    point = _fit(X_fit, y_fit)
    pred_cal, pred_test = point.predict(X_cal), point.predict(X_test)
    observed_band = _band(y_test)
    period = np.where(
        meta_test["Date"] < pd.Timestamp(config.LOCKDOWN_START), "before lockdown",
        np.where(meta_test["Date"] <= pd.Timestamp(config.LOCKDOWN_END), "lockdown", "after lockdown"),
    )

    # --- split conformal on absolute residuals: one constant half-width ------ #
    q_abs = _conformal_quantile(np.abs(y_cal - pred_cal), ALPHA)
    lo_a, hi_a = pred_test - q_abs, pred_test + q_abs

    # --- conformalised quantile regression: width adapts to the input -------- #
    low = _fit(X_fit, y_fit, objective="quantile", alpha=ALPHA / 2)
    high = _fit(X_fit, y_fit, objective="quantile", alpha=1 - ALPHA / 2)
    cal_lo, cal_hi = low.predict(X_cal), high.predict(X_cal)
    q_cqr = _conformal_quantile(np.maximum(cal_lo - y_cal, y_cal - cal_hi), ALPHA)
    lo_c, hi_c = low.predict(X_test) - q_cqr, high.predict(X_test) + q_cqr

    # --- Mondrian: a separate residual quantile per *predicted* band --------- #
    cal_band, test_band = _band(pred_cal), _band(pred_test)
    half = np.full(len(pred_test), q_abs)
    mondrian_groups = {}
    for b in BANDS:
        scores = np.abs(y_cal - pred_cal)[cal_band == b]
        if len(scores) >= 30:
            mondrian_groups[b] = _conformal_quantile(scores, ALPHA)
            half[test_band == b] = mondrian_groups[b]
    lo_m, hi_m = pred_test - half, pred_test + half

    intervals = {
        "nominal_coverage_pct": 100 * (1 - ALPHA),
        "calibration_rows": int(len(y_cal)),
        "calibration_period": [str(meta_train["Date"][~is_fit].min().date()), str(meta_train["Date"][~is_fit].max().date())],
        "point_model_test_mae": round(float(np.abs(y_test - pred_test).mean()), 3),
        "methods": {},
    }
    for name, (lo, hi), note in (
        ("split_conformal_absolute", (lo_a, hi_a), f"constant half-width {q_abs:.1f} AQI points"),
        ("conformalised_quantile_regression", (lo_c, hi_c), f"quantile models widened by {q_cqr:.1f}"),
        ("mondrian_by_predicted_band", (lo_m, hi_m), f"half-widths {{{', '.join(f'{k}: {v:.0f}' for k, v in mondrian_groups.items())}}}"),
    ):
        intervals["methods"][name] = {
            "note": note,
            "overall": _summary(y_test, lo, hi),
            "by_observed_band": _coverage_table(y_test, lo, hi, observed_band, BANDS),
            "by_period": _coverage_table(y_test, lo, hi, period, ["before lockdown", "lockdown", "after lockdown"]),
        }

    # --- leave-one-city-out --------------------------------------------------- #
    features = [f for f in data["features"] if f not in CITY_IDENTITY_FEATURES]
    pooled = _fit(X_train[features], y_train)
    pooled_pred = pooled.predict(X_test[features])
    today_aqi = X_test["AQI"].to_numpy() if "AQI" in X_test else data["aux_test"]["AQI"].to_numpy()

    loco_rows = []
    for city in sorted(meta_test["City"].unique()):
        keep = (meta_train["City"] != city).to_numpy()
        target = (meta_test["City"] == city).to_numpy()
        held_out = _fit(X_train[features][keep], y_train[keep])
        unseen_mae = float(np.abs(y_test[target] - held_out.predict(X_test[features][target])).mean())
        seen_mae = float(np.abs(y_test[target] - pooled_pred[target]).mean())
        persistence = float(np.abs(y_test[target] - today_aqi[target]).mean())
        loco_rows.append(
            {
                "city": city,
                "n_test": int(target.sum()),
                "mae_city_seen_in_training": round(seen_mae, 2),
                "mae_city_unseen": round(unseen_mae, 2),
                "degradation_pct": round(100 * (unseen_mae - seen_mae) / seen_mae, 1),
                "mae_persistence": round(persistence, 2),
                "unseen_still_beats_persistence": bool(unseen_mae < persistence),
            }
        )
    weights = np.array([r["n_test"] for r in loco_rows])
    loco = {
        "protocol": (
            "For each city, a model is fitted on the other eleven cities' training-period rows and "
            "scored on the held-out city's test-period rows. The city-identity feature "
            f"{CITY_IDENTITY_FEATURES} is removed from both arms so the comparison is like for like."
        ),
        "per_city": loco_rows,
        "weighted_mae_seen": round(float(np.average([r["mae_city_seen_in_training"] for r in loco_rows], weights=weights)), 2),
        "weighted_mae_unseen": round(float(np.average([r["mae_city_unseen"] for r in loco_rows], weights=weights)), 2),
        "weighted_mae_persistence": round(float(np.average([r["mae_persistence"] for r in loco_rows], weights=weights)), 2),
        "cities_where_unseen_beats_persistence": int(sum(r["unseen_still_beats_persistence"] for r in loco_rows)),
    }
    loco["mean_degradation_pct"] = round(100 * (loco["weighted_mae_unseen"] - loco["weighted_mae_seen"]) / loco["weighted_mae_seen"], 1)

    # --- selective prediction -------------------------------------------------- #
    error = np.abs(y_test - pred_test)
    width = hi_c - lo_c
    polluted = np.isin(observed_band, ["Poor", "Very Poor", "Severe"])
    order = {b: i for i, b in enumerate(BANDS)}
    under_warn = np.array([order[p] < order[o] for p, o in zip(_band(pred_test), observed_band)]) & polluted

    pollutants = [p for p in config.HAI_POLLUTANTS if p in X_fit]
    z = (X_test[pollutants] - X_fit[pollutants].mean()) / X_fit[pollutants].std()
    scores = {
        "interval_width": width,
        "relative_interval_width": width / np.maximum(pred_test, 25.0),
        "input_novelty_max_abs_z": z.abs().max(axis=1).to_numpy(),
    }
    selective = {
        "baseline": {
            "mae_all": round(float(error.mean()), 2),
            "polluted_days": int(polluted.sum()),
            "under_warned_polluted_days": int(under_warn.sum()),
        },
        "rules": {},
    }
    for name, score in scores.items():
        rows = []
        for share in (0.10, 0.20):
            threshold = np.quantile(score, 1 - share)
            abstain = score > threshold
            rows.append(
                {
                    "abstain_pct": round(100 * float(abstain.mean()), 1),
                    "mae_on_answered": round(float(error[~abstain].mean()), 2),
                    "mae_on_declined": round(float(error[abstain].mean()), 2),
                    "pct_of_declined_that_were_polluted_days": round(100 * float(polluted[abstain].mean()), 1),
                    "pct_of_all_polluted_days_declined": round(100 * float(abstain[polluted].mean()), 1),
                    "pct_of_severe_days_declined": round(100 * float(abstain[observed_band == "Severe"].mean()), 1),
                    "under_warned_polluted_days_still_answered": int((under_warn & ~abstain).sum()),
                }
            )
        selective["rules"][name] = rows

    # --- risk-averse advisory: act on an upper quantile, not the point -------- #
    # The loss is asymmetric: telling someone the air is cleaner than it turns
    # out to be is worse than the reverse. Instead of declining to answer, the
    # advisory can be issued from a higher quantile of the predictive
    # distribution. Each rule is scored on both kinds of error.
    rank = np.array([order[b] for b in observed_band])
    rules = {"point_forecast": pred_test, "upper_bound_of_90pct_interval": hi_c}
    for q in (0.65, 0.75, 0.85):
        rules[f"quantile_{int(q * 100)}"] = _fit(X_fit, y_fit, objective="quantile", alpha=q).predict(X_test)
    advisory = []
    for name, value in rules.items():
        issued = np.array([order[b] for b in _band(value)])
        advisory.append(
            {
                "rule": name,
                "exact_band_pct": round(100 * float((issued == rank).mean()), 1),
                "under_warned_pct_of_all_days": round(100 * float((issued < rank).mean()), 1),
                "over_warned_pct_of_all_days": round(100 * float((issued > rank).mean()), 1),
                "under_warned_polluted_days": int(((issued < rank) & polluted).sum()),
                "under_warned_pct_of_polluted_days": round(100 * float((issued < rank)[polluted].mean()), 1),
                "under_warned_severe_days": int(((issued < rank) & (observed_band == "Severe")).sum()),
                "over_warned_by_two_or_more_bands_pct": round(100 * float((issued - rank >= 2).mean()), 2),
            }
        )

    flag_words = ("lockdown", "diwali", "festival", "stubble", "event", "covid", "holiday")
    columns = json.loads((config.PROCESSED_DIR / "feature_columns.json").read_text(encoding="utf-8"))
    return {
        "intervals": intervals,
        "leave_one_city_out": loco,
        "selective_prediction": selective,
        "risk_averse_advisory": {"severe_days": int((observed_band == "Severe").sum()), "rules": advisory},
        "event_flags": {
            "candidates_offered_to_selection": [c for c in columns["all_numeric_candidates"] if any(k in c.lower() for k in flag_words)],
            "retained_in_regression_model": [c for c in data["features"] if any(k in c.lower() for k in flag_words)],
            "retained_in_classification_model": [c for c in columns["classification"] if any(k in c.lower() for k in flag_words)],
        },
    }


def main() -> Dict[str, Any]:
    config.set_global_seed()
    payload: Dict[str, Any] = {
        "generated_by": "src/research/pilot_trust.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": (
            "PILOT. Historical 2015-2020 record only; refitted models, not the deployed artefacts. "
            "Indicates whether each research gap is real on data in hand -- not a result to publish."
        ),
        "classifier_calibration": classifier_calibration(),
        **regression_experiments(),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = main()
    print(json.dumps({k: v for k, v in result.items() if k not in ("generated_by",)}, indent=1)[:9000])
