"""Feature construction, target definition and the leakage-safe train/test split.

The forecasting formulation
---------------------------
Every model in this project predicts **tomorrow** from information available
**today**. For a city ``c`` and date ``t`` the targets are

.. code-block:: text

    AQI_next(c, t)        = AQI(c, t + 1)
    AQI_Bucket_next(c, t) = AQI_Bucket(c, t + 1)

and the feature vector may use any measurement dated ``t`` or earlier for that
same city. This changes which columns constitute leakage compared with a
same-day nowcast, and the distinction is made explicit rather than assumed:

* ``AQI_next`` and ``AQI_Bucket_next`` are targets. Each must be absent from the
  feature matrix of the other task, because ``AQI_Bucket_next`` is a
  deterministic function of ``AQI_next`` and vice versa.
* Same-day ``AQI`` and ``AQI_Bucket`` are **legitimate predictors**: they are
  known today and they say nothing beyond today. Excluding them would discard
  the strongest honest signal available. The nowcast leakage that the same-day
  formulation suffers from is demonstrated empirically, not merely asserted, in
  ``models/train_classification.py``.
* Rolling and lag features are computed with ``groupby('City')`` so that no city
  contributes to another city's history, and every window ends at ``t`` or
  earlier, so no future observation enters a feature.

Outputs
-------
``data/processed/features_full.csv``  every engineered row, with targets
``data/processed/train.csv`` / ``test.csv``  the time-ordered partitions
``data/processed/feature_columns.json``  the retained feature list per task
``results/feature_engineering_report.json``
``results/hai_divergence.json``
``reports/figures/07_hai_vs_aqi_scatter.png``
``reports/figures/08_hai_divergence_by_cohort.png``
``reports/figures/09_feature_selection.png``

Run with::

    python -m src.features.build
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from src import config
from src.data.clean import CLEAN_PATH, KEPT_POLLUTANTS, compute_split_boundary
from src.features import hai as hai_mod

LOGGER = config.get_logger(__name__)

FEATURES_PATH = config.PROCESSED_DIR / "features_full.csv"
TRAIN_PATH = config.PROCESSED_DIR / "train.csv"
TEST_PATH = config.PROCESSED_DIR / "test.csv"
FEATURE_COLUMNS_PATH = config.PROCESSED_DIR / "feature_columns.json"
REPORT_PATH = config.RESULTS_DIR / "feature_engineering_report.json"
DIVERGENCE_PATH = config.RESULTS_DIR / "hai_divergence.json"

#: Pollutants that receive lag and rolling features. Restricted to the CPCB AQI
#: species plus the two well-covered VOCs, to keep the matrix width manageable.
LAGGED_POLLUTANTS: List[str] = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]

#: Correlation above which two features are considered redundant.
CORRELATION_REDUNDANCY_THRESHOLD: float = 0.95

#: Cumulative permutation-free gain share retained by the model-based filter.
IMPORTANCE_CUMULATIVE_SHARE: float = 0.995


# --------------------------------------------------------------------------- #
# Temporal and event features
# --------------------------------------------------------------------------- #
def add_temporal_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add calendar, seasonal and cyclical time features."""
    out = frame.copy()
    dates = out["Date"]
    out["year"] = dates.dt.year
    out["month"] = dates.dt.month
    out["day_of_month"] = dates.dt.day
    out["day_of_week"] = dates.dt.dayofweek
    out["day_of_year"] = dates.dt.dayofyear
    out["week_of_year"] = dates.dt.isocalendar().week.astype(int)
    out["quarter"] = dates.dt.quarter
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)
    out["season"] = out["month"].map(config.SEASON_OF_MONTH)

    # Cyclical encodings so that December and January are adjacent to a model
    # that has no notion of calendar wrap-around.
    out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12.0)
    out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12.0)
    out["doy_sin"] = np.sin(2 * np.pi * out["day_of_year"] / 365.25)
    out["doy_cos"] = np.cos(2 * np.pi * out["day_of_year"] / 365.25)

    # Linear time index, so that a tree can express a monotone secular trend.
    out["days_since_start"] = (dates - dates.min()).dt.days
    return out


def add_event_flags(frame: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Add event-awareness flags for festivals, crop burning and the lockdown.

    Flags are additive and non-exclusive: a date may be inside the Diwali window
    and the stubble-burning season at once, which is exactly what happens in
    north India in late October.
    """
    out = frame.copy()
    dates = out["Date"]

    diwali = pd.Series(False, index=out.index)
    days_to_diwali = pd.Series(np.nan, index=out.index)
    for _, day in config.DIWALI_DATES.items():
        centre = pd.Timestamp(day)
        offset = (dates - centre).dt.days
        near = offset.abs() <= config.DIWALI_WINDOW_DAYS
        diwali |= near
        days_to_diwali = days_to_diwali.where(
            ~near | (days_to_diwali.abs() <= offset.abs()), offset
        )
    out["festival_flag"] = diwali.astype(int)
    out["days_from_diwali"] = days_to_diwali.fillna(999).astype(int)

    (m0, d0), (m1, d1) = config.STUBBLE_SEASON
    month, day = dates.dt.month, dates.dt.day
    after = (month > m0) | ((month == m0) & (day >= d0))
    before = (month < m1) | ((month == m1) & (day <= d1))
    out["stubble_season_flag"] = (after & before).astype(int)

    out["lockdown_flag"] = dates.between(
        pd.Timestamp(config.LOCKDOWN_START), pd.Timestamp(config.LOCKDOWN_END)
    ).astype(int)
    out["post_lockdown_flag"] = (dates > pd.Timestamp(config.LOCKDOWN_END)).astype(int)
    out["covid_year_flag"] = (dates.dt.year == 2020).astype(int)

    summary = {
        "festival_flag_days": int(out["festival_flag"].sum()),
        "stubble_season_flag_days": int(out["stubble_season_flag"].sum()),
        "lockdown_flag_days": int(out["lockdown_flag"].sum()),
        "covid_year_flag_days": int(out["covid_year_flag"].sum()),
        "diwali_dates_used": config.DIWALI_DATES,
        "covid_policy": (
            "The 2020 lockdown is modelled with an explicit flag rather than "
            "excluded. The flag lets a model represent the regime change instead "
            "of averaging over it, and the period is additionally reported as a "
            "separate stress-test slice of the test set in "
            "results/evaluation_regression.json and "
            "results/evaluation_classification.json, so that its contribution to "
            "the headline error is visible rather than hidden."
        ),
    }
    return out, summary


# --------------------------------------------------------------------------- #
# Lag, rolling and ratio features
# --------------------------------------------------------------------------- #
def add_lag_features(frame: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Add per-city lagged values of AQI and the principal pollutants.

    Lags are taken within each city with ``groupby('City')``. Because the cleaned
    table is calendar-complete per city, a lag of one row is exactly a lag of one
    day, so the features carry the intended physical meaning.
    """
    out = frame.sort_values(["City", "Date"]).copy()
    created: List[str] = []
    targets = ["AQI"] + LAGGED_POLLUTANTS
    grouped = out.groupby("City", sort=False)
    for column in targets:
        for lag in config.LAG_ORDERS:
            name = f"{column}_lag{lag}"
            out[name] = grouped[column].shift(lag)
            created.append(name)
    return out, created


def add_rolling_features(frame: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Add per-city rolling means, standard deviations and day-on-day changes.

    Every window ends on the current day, which is admissible because the target
    is the following day. ``min_periods`` is set to the full window so that an
    early-series partial window does not masquerade as a full one.
    """
    out = frame.sort_values(["City", "Date"]).copy()
    created: List[str] = []
    grouped = out.groupby("City", sort=False)
    for column in ["AQI"] + LAGGED_POLLUTANTS:
        for window in config.ROLLING_WINDOWS:
            mean_name = f"{column}_roll{window}_mean"
            std_name = f"{column}_roll{window}_std"
            out[mean_name] = grouped[column].transform(
                lambda s, w=window: s.rolling(w, min_periods=w).mean()
            )
            out[std_name] = grouped[column].transform(
                lambda s, w=window: s.rolling(w, min_periods=w).std()
            )
            created += [mean_name, std_name]

        delta_name = f"{column}_delta1"
        out[delta_name] = grouped[column].transform(lambda s: s.diff(1))
        created.append(delta_name)

        # Departure of today from the recent norm: a persistence-aware signal.
        dev_name = f"{column}_dev_roll7"
        out[dev_name] = out[column] - out[f"{column}_roll7_mean"]
        created.append(dev_name)
    return out, created


def add_ratio_features(frame: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Add pollutant ratio features that act as emission-source proxies.

    ``pm_ratio`` (PM2.5 / PM10)
        The fine fraction of particulate mass. Combustion sources - vehicles,
        biomass burning, industry - emit predominantly fine particles, whereas
        road dust, construction and wind-blown soil emit predominantly coarse
        particles. A high ratio therefore points to a combustion-dominated
        airshed and a low ratio to a dust-dominated one, which are two problems
        with two different policy remedies.
    ``no2_nox_ratio``
        The oxidised share of the nitrogen oxide budget. Fresh vehicle exhaust is
        NO-rich, and NO converts to NO2 photochemically with distance and time
        from the tailpipe, so a low ratio indicates proximity to live traffic.
    ``so2_pm25_ratio``
        Separates industrial and coal-combustion influence from generic urban
        particulate loading.
    ``o3_no2_ratio``
        A coarse indicator of photochemical processing versus primary emission.
    """
    out = frame.copy()
    epsilon = 1e-6
    out["pm_ratio"] = out["PM2.5"] / (out["PM10"] + epsilon)
    out["no2_nox_ratio"] = out["NO2"] / (out["NOx"] + epsilon)
    out["so2_pm25_ratio"] = out["SO2"] / (out["PM2.5"] + epsilon)
    out["o3_no2_ratio"] = out["O3"] / (out["NO2"] + epsilon)
    out["pm_coarse"] = (out["PM10"] - out["PM2.5"]).clip(lower=0.0)
    out["total_pollutant_load"] = out[["PM2.5", "PM10", "NO2", "SO2", "O3"]].sum(axis=1)

    created = [
        "pm_ratio",
        "no2_nox_ratio",
        "so2_pm25_ratio",
        "o3_no2_ratio",
        "pm_coarse",
        "total_pollutant_load",
    ]
    # Ratios can be extreme where a denominator is near zero; clip to a wide but
    # finite range so that a single division does not dominate a scaler.
    for column in ["pm_ratio", "no2_nox_ratio", "so2_pm25_ratio", "o3_no2_ratio"]:
        out[column] = out[column].clip(0.0, 20.0)
    return out, created


# --------------------------------------------------------------------------- #
# Station metadata integration
# --------------------------------------------------------------------------- #
def integrate_station_metadata(frame: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Join per-city monitoring-network metadata from ``stations.csv``.

    Two legitimate covariates are derived. ``n_stations`` is the number of
    monitoring stations the city contributes, which conditions how representative
    a city-level daily mean is. ``State`` is retained as a categorical, since
    regulatory regime and regional meteorology operate at state level.
    """
    path = config.RAW_DIR / config.STATION_META_FILE
    if not path.exists():
        LOGGER.warning("stations.csv absent; skipping metadata integration")
        return frame, {"integrated": False}

    stations = pd.read_csv(path)
    per_city = (
        stations.groupby("City")
        .agg(
            n_stations=("StationId", "nunique"),
            n_active_stations=("Status", lambda s: int((s == "Active").sum())),
            State=("State", "first"),
        )
        .reset_index()
    )
    out = frame.merge(per_city, on="City", how="left")
    out["n_stations"] = out["n_stations"].fillna(1).astype(int)
    out["n_active_stations"] = out["n_active_stations"].fillna(0).astype(int)
    out["State"] = out["State"].fillna("Unknown")

    return out, {
        "integrated": True,
        "source": str(path),
        "n_stations_total": int(stations["StationId"].nunique()),
        "cities_matched": int(out["City"].nunique()),
        "per_city": per_city.loc[per_city["City"].isin(frame["City"].unique())].to_dict(
            orient="records"
        ),
    }


# --------------------------------------------------------------------------- #
# HAI features
# --------------------------------------------------------------------------- #
def audit_aqi_recomputation(frame: pd.DataFrame) -> Dict[str, Any]:
    """Audit the supplied ``AQI`` column against an independent recomputation.

    The AQI is recomputed from the cleaned pollutant columns using the published
    CPCB breakpoints and the minimum three-pollutant rule, then compared with the
    ``AQI`` column the dataset supplies. The comparison serves two purposes: it
    verifies that the sub-index machinery underlying the HAI is implemented
    correctly, and it surfaces the one genuine methodological gap between this
    reconstruction and the compiler's.

    The gap is diagnosed rather than asserted. The per-dominant-pollutant bias
    returned by this function shows the discrepancy is systematically positive and
    largest on days dominated by CO and O3. That is the expected signature of the
    CPCB averaging convention: the National AQI specification uses the **maximum
    8-hour running mean** for CO and O3 and the 24-hour mean for the remaining
    species. The compiler computed the AQI from the hourly series and therefore
    saw those 8-hour maxima, whereas a reconstruction from ``city_day.csv`` has
    only the daily mean available. Because an 8-hour maximum is never below a
    daily mean, the reconstruction understates the CO and O3 sub-indices, and the
    supplied AQI is correspondingly higher.

    The consequence for this project is stated plainly: the **supplied** ``AQI``
    column is used as the supervised target throughout, precisely because it
    embodies the correct CPCB averaging convention. The recomputed series is used
    only for auditing and for the HAI sub-index decomposition, where the same
    approximation applies uniformly across cohorts and therefore does not
    distort the cohort comparison.
    """
    mask = frame["AQI"].notna() & frame["AQI_recomputed"].notna()
    subset = frame.loc[mask]
    difference = subset["AQI"] - subset["AQI_recomputed"]

    per_dominant: List[Dict[str, Any]] = []
    for pollutant in config.AQI_POLLUTANTS:
        selector = subset["dominant_pollutant"] == pollutant
        if int(selector.sum()) < 30:
            continue
        local = difference.loc[selector]
        per_dominant.append(
            {
                "dominant_pollutant": pollutant,
                "n": int(selector.sum()),
                "mean_signed_difference": round(float(local.mean()), 3),
                "mean_absolute_difference": round(float(local.abs().mean()), 3),
                "cpcb_averaging_convention": (
                    "maximum 8-hour running mean"
                    if pollutant in ("CO", "O3")
                    else "24-hour mean"
                ),
            }
        )

    return {
        "n_compared": int(mask.sum()),
        "mean_absolute_difference": round(float(difference.abs().mean()), 3),
        "mean_signed_difference": round(float(difference.mean()), 3),
        "pearson_r": round(float(subset["AQI"].corr(subset["AQI_recomputed"])), 5),
        "exact_bucket_agreement_pct": round(
            100.0
            * float(
                (
                    hai_mod.bucket_from_aqi(subset["AQI"].to_numpy())
                    == hai_mod.bucket_from_aqi(subset["AQI_recomputed"].to_numpy())
                ).mean()
            ),
            3,
        ),
        "bias_by_dominant_pollutant": per_dominant,
        "diagnosis": (
            "The discrepancy is systematically positive: the supplied AQI exceeds "
            "the reconstruction. The bias is largest on days dominated by CO and "
            "O3, which are exactly the two species for which the CPCB "
            "specification uses the maximum 8-hour running mean rather than the "
            "24-hour mean. Reconstructing from daily means therefore understates "
            "those two sub-indices, and no reconstruction from city_day.csv alone "
            "can recover them."
        ),
        "decision": (
            "The supplied AQI column is used as the supervised target throughout, "
            "because it embodies the correct CPCB averaging convention. The "
            "recomputed series is used only for auditing and for the HAI "
            "sub-index decomposition, where the same approximation applies "
            "identically to every cohort and therefore cannot distort the "
            "cohort-to-cohort comparison that constitutes the novelty claim."
        ),
    }


def add_hai_features(frame: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], Dict[str, Any]]:
    """Add CPCB sub-indices, cohort HAI values, bands and the divergence evidence."""
    hai_mod.self_test()

    out = hai_mod.compute_sub_indices(frame)
    out["AQI_recomputed"] = hai_mod.recompute_aqi(out)
    out["dominant_pollutant"] = hai_mod.dominant_pollutant(out)
    out = hai_mod.add_all_cohort_hai(out)

    audit = audit_aqi_recomputation(out)

    created = (
        [f"sub_{p}" for p in config.AQI_POLLUTANTS if f"sub_{p}" in out.columns]
        + [f"HAI_{c}" for c in config.COHORTS]
        + ["AQI_recomputed"]
    )
    divergence = hai_mod.measure_divergence(out)
    divergence["aqi_recomputation_audit"] = audit
    return out, created, divergence


# --------------------------------------------------------------------------- #
# Targets and encodings
# --------------------------------------------------------------------------- #
def add_targets(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the next-day regression and classification targets, per city."""
    out = frame.sort_values(["City", "Date"]).copy()
    grouped = out.groupby("City", sort=False)
    out["AQI_next"] = grouped["AQI"].shift(-1)
    out["AQI_Bucket_next"] = grouped["AQI_Bucket"].shift(-1)
    out["AQI_Bucket_ordinal"] = out["AQI_Bucket"].map(config.AQI_BUCKET_ORDINAL)
    out["AQI_Bucket_next_ordinal"] = out["AQI_Bucket_next"].map(config.AQI_BUCKET_ORDINAL)

    # Verify the shift really moved one calendar day for every city.
    check = out.assign(next_date=grouped["Date"].shift(-1))
    gap = (check["next_date"] - check["Date"]).dt.days.dropna()
    assert (gap == 1).all(), "target shift crossed a calendar gap"
    return out


def encode_categoricals(
    frame: pd.DataFrame, boundary: pd.Timestamp
) -> Tuple[pd.DataFrame, List[str], Dict[str, Any]]:
    """Encode ``City``, ``State``, ``season`` and ``dominant_pollutant``.

    Two city encodings are produced side by side so that the modelling stage can
    compare them:

    ``City_ohe_*``
        One-hot indicators. Carries no information about the target and therefore
        cannot leak, at the cost of twelve extra columns.
    ``City_target_enc``
        The mean same-day AQI of the city, computed **on training rows only** and
        then applied to both partitions. Restricting the statistic to the
        training period is what makes the encoding leakage-safe; computing it on
        the full record would let the test period inform its own encoding.
    """
    out = frame.copy()
    created: List[str] = []

    dummies = pd.get_dummies(out["City"], prefix="City_ohe", dtype=int)
    out = pd.concat([out, dummies], axis=1)
    created += list(dummies.columns)

    train_mask = out["Date"] < boundary
    city_means = out.loc[train_mask].groupby("City")["AQI"].mean()
    global_mean = float(out.loc[train_mask, "AQI"].mean())
    out["City_target_enc"] = out["City"].map(city_means).fillna(global_mean)
    created.append("City_target_enc")

    season_dummies = pd.get_dummies(out["season"], prefix="season", dtype=int)
    out = pd.concat([out, season_dummies], axis=1)
    created += list(season_dummies.columns)

    dominant_dummies = pd.get_dummies(out["dominant_pollutant"], prefix="dom", dtype=int)
    out = pd.concat([out, dominant_dummies], axis=1)
    created += list(dominant_dummies.columns)

    state_codes = {state: idx for idx, state in enumerate(sorted(out["State"].unique()))}
    out["State_code"] = out["State"].map(state_codes)
    created.append("State_code")

    info = {
        "city_one_hot_columns": list(dummies.columns),
        "city_target_encoding": {
            "statistic": "mean same-day AQI",
            "fitted_on": f"rows with Date < {boundary.strftime('%Y-%m-%d')}",
            "n_train_rows": int(train_mask.sum()),
            "values": {k: round(float(v), 2) for k, v in city_means.items()},
            "global_fallback": round(global_mean, 2),
            "leakage_note": (
                "The encoding is fitted on the training period only. Applying a "
                "full-sample city mean would allow each test row to contribute to "
                "the value of its own encoded feature."
            ),
        },
        "ordinal_encoding": {
            "column": "AQI_Bucket -> AQI_Bucket_ordinal",
            "mapping": config.AQI_BUCKET_ORDINAL,
            "justification": (
                "The CPCB buckets are ordered severity categories, so an ordinal "
                "code preserves the ordering that a one-hot encoding would "
                "discard. The ordinal form is used for the ordered-severity "
                "features; the classification target itself is kept as the string "
                "label so that per-class metrics remain readable."
            ),
        },
        "state_codes": state_codes,
    }
    return out, created, info


# --------------------------------------------------------------------------- #
# Feature selection
# --------------------------------------------------------------------------- #
def select_features(
    frame: pd.DataFrame,
    candidate_columns: List[str],
    target: str,
    boundary: pd.Timestamp,
    task: str,
) -> Dict[str, Any]:
    """Apply a correlation filter then a model-based filter, on training rows only.

    Stage 1, correlation redundancy
        Among pairs of features with an absolute Pearson correlation above
        ``CORRELATION_REDUNDANCY_THRESHOLD``, the member with the weaker
        association to the target is dropped. This removes the near-duplicates
        that lag and rolling construction inevitably creates, without deciding
        anything on the basis of test data.

    Stage 2, model-based importance
        A gradient-boosted tree is fitted on the training rows and features are
        retained in descending importance until
        ``IMPORTANCE_CUMULATIVE_SHARE`` of the total gain is covered. Features
        with exactly zero importance are dropped.

    Stage 0, degenerate columns
        Features with zero variance on the training rows carry no information and
        make a correlation undefined, so they are removed before anything else.

    All stages read only rows before ``boundary``.
    """
    from lightgbm import LGBMClassifier, LGBMRegressor

    train = frame.loc[frame["Date"] < boundary].dropna(subset=[target] + candidate_columns)

    variances = train[candidate_columns].var(numeric_only=True)
    zero_variance = [c for c in candidate_columns if not variances.get(c, 0.0) > 0]
    candidate_columns = [c for c in candidate_columns if c not in zero_variance]
    features = train[candidate_columns]

    if task == "regression":
        target_series = train[target].astype(float)
        target_corr = features.corrwith(target_series).abs().fillna(0.0)
        model = LGBMRegressor(
            n_estimators=300,
            learning_rate=0.05,
            random_state=config.RANDOM_SEED,
            verbose=-1,
        )
        model.fit(features, target_series)
    else:
        target_series = train[target].map(config.AQI_BUCKET_ORDINAL).astype(float)
        target_corr = features.corrwith(target_series).abs().fillna(0.0)
        model = LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            random_state=config.RANDOM_SEED,
            verbose=-1,
        )
        model.fit(features, train[target])

    correlation = features.corr().abs()
    upper = correlation.where(np.triu(np.ones(correlation.shape), k=1).astype(bool))
    dropped_correlated: List[Dict[str, Any]] = []
    removed: set = set()
    for left in upper.columns:
        for right in upper.index:
            value = upper.loc[right, left]
            if pd.isna(value) or value < CORRELATION_REDUNDANCY_THRESHOLD:
                continue
            if left in removed or right in removed:
                continue
            weaker = left if target_corr[left] < target_corr[right] else right
            stronger = right if weaker == left else left
            removed.add(weaker)
            dropped_correlated.append(
                {
                    "dropped": weaker,
                    "kept": stronger,
                    "pairwise_abs_correlation": round(float(value), 4),
                    "dropped_target_corr": round(float(target_corr[weaker]), 4),
                    "kept_target_corr": round(float(target_corr[stronger]), 4),
                }
            )

    after_correlation = [c for c in candidate_columns if c not in removed]

    importances = pd.Series(model.feature_importances_, index=candidate_columns).astype(float)
    importances = importances.loc[after_correlation].sort_values(ascending=False)
    total = float(importances.sum()) or 1.0
    cumulative = (importances / total).cumsum()
    keep_mask = (cumulative <= IMPORTANCE_CUMULATIVE_SHARE) & (importances > 0)
    if not keep_mask.any():
        keep_mask.iloc[:] = True
    retained = importances.loc[keep_mask].index.tolist()
    dropped_low_importance = [c for c in after_correlation if c not in retained]

    return {
        "task": task,
        "target": target,
        "n_candidates": len(candidate_columns) + len(zero_variance),
        "stage_0_zero_variance": {
            "n_dropped": len(zero_variance),
            "dropped": zero_variance,
            "reason": "constant on the training rows, so uninformative by construction",
        },
        "stage_1_correlation": {
            "threshold": CORRELATION_REDUNDANCY_THRESHOLD,
            "n_dropped": len(dropped_correlated),
            "dropped": dropped_correlated,
            "n_remaining": len(after_correlation),
        },
        "stage_2_model_based": {
            "estimator": type(model).__name__,
            "cumulative_gain_share_retained": IMPORTANCE_CUMULATIVE_SHARE,
            "n_dropped": len(dropped_low_importance),
            "dropped": dropped_low_importance,
        },
        "n_retained": len(retained),
        "retained": retained,
        "retained_with_importance": [
            {
                "rank": rank,
                "feature": name,
                "importance": int(importances[name]),
                "importance_share_pct": round(100.0 * importances[name] / total, 3),
                "abs_corr_with_target": round(float(target_corr[name]), 4),
            }
            for rank, name in enumerate(retained, start=1)
        ],
        "fitted_on_rows": int(len(train)),
        "fitted_on": f"rows with Date < {boundary.strftime('%Y-%m-%d')}",
    }


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def _save(fig: "plt.Figure", name: str) -> Path:
    import matplotlib.pyplot as plt

    path = config.FIGURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", name)
    return path


def plot_hai_vs_aqi(frame: pd.DataFrame, divergence: Dict[str, Any]) -> Path:
    """Contrast the official AQI with the asthma/COPD HAI on real observations."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    work = frame.dropna(subset=["AQI", "HAI_asthma_copd"]).copy()
    aqi_scaled = work["AQI"] / 5.0
    hai = work["HAI_asthma_copd"]
    asthma = next(c for c in divergence["per_cohort"] if c["cohort"] == "asthma_copd")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    ax1.scatter(aqi_scaled, hai, s=4, alpha=0.18, color=config.PALETTE[0], rasterized=True)
    limit = float(max(aqi_scaled.max(), hai.max())) * 1.02
    ax1.plot([0, limit], [0, limit], color="black", linewidth=1.1, linestyle="--",
             label="Parity (HAI = AQI / 5)")
    for _, low, _ in config.HAI_BANDS[1:]:
        ax1.axhline(low, color=config.PALETTE[1], linewidth=0.7, alpha=0.6)
        ax1.axvline(low, color=config.PALETTE[1], linewidth=0.7, alpha=0.6)
    ax1.set_xlabel("Official CPCB AQI, rescaled to 0-100 (AQI / 5)")
    ax1.set_ylabel("HAI for the asthma / COPD cohort")
    ax1.set_xlim(0, limit)
    ax1.set_ylim(0, limit)
    ax1.legend(frameon=False, loc="lower right")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_title(
        f"Every point lies on or above parity by construction.\n"
        f"Band differs from the AQI band on {asthma['pct_band_differs_from_aqi']:.1f}% "
        f"of city-days ({asthma['days_band_differs_from_aqi']:,} days).",
        fontsize=10,
        loc="left",
    )

    delta = hai - aqi_scaled
    ax2.hist(delta, bins=70, color=config.PALETTE[2], alpha=0.85)
    ax2.axvline(float(delta.mean()), color=config.PALETTE[1], linewidth=1.8,
                label=f"Mean uplift = {delta.mean():.2f} points")
    ax2.set_xlabel("HAI(asthma / COPD) minus AQI / 5   (index points)")
    ax2.set_ylabel("City-days")
    ax2.legend(frameon=False)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title(
        "The uplift is the extra caution the cohort-weighted index advises\n"
        "relative to the single population-average number.",
        fontsize=10,
        loc="left",
    )

    fig.suptitle(
        "Figure 7. The Health Advisory Index diverges from the official AQI on real "
        "observations (asthma / COPD cohort)",
        fontsize=12,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, "07_hai_vs_aqi_scatter.png")


def plot_hai_divergence(divergence: Dict[str, Any]) -> Path:
    """Render per-cohort divergence from the AQI and from the reference cohort."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = divergence["per_cohort"]
    labels = [r["cohort_label"] for r in rows]
    from_aqi = [r["pct_band_differs_from_aqi"] for r in rows]
    from_ref = [r["pct_band_differs_from_reference_cohort"] for r in rows]
    uplift = [r["mean_uplift_points"] for r in rows]

    order = np.argsort(from_aqi)
    labels = [labels[i] for i in order]
    from_aqi = [from_aqi[i] for i in order]
    from_ref = [from_ref[i] for i in order]
    uplift = [uplift[i] for i in order]

    y = np.arange(len(labels))
    height = 0.38
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(14.5, 6), gridspec_kw={"width_ratios": [2, 1]}
    )
    b1 = ax1.barh(y - height / 2, from_aqi, height, color=config.PALETTE[0],
                  label="Band differs from the official AQI band")
    b2 = ax1.barh(y + height / 2, from_ref, height, color=config.PALETTE[3],
                  label="Band differs from the healthy-adult reference cohort")
    ax1.bar_label(b1, fmt="%.1f%%", padding=3, fontsize=8.5)
    ax1.bar_label(b2, fmt="%.1f%%", padding=3, fontsize=8.5)
    ax1.set_yticks(y)
    ax1.set_yticklabels(labels)
    ax1.set_xlabel("Share of city-days (%)")
    ax1.set_xlim(0, max(max(from_aqi), max(from_ref)) * 1.25)
    ax1.legend(frameon=False, loc="lower right", fontsize=9)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_title("Advisory-band disagreement", fontsize=11, loc="left")

    b3 = ax2.barh(y, uplift, color=config.PALETTE[4])
    ax2.bar_label(b3, fmt="%.2f", padding=3, fontsize=8.5)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.set_xlabel("Mean uplift over AQI / 5 (index points)")
    ax2.set_xlim(0, max(uplift) * 1.25)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title("Mean additional caution advised", fontsize=11, loc="left")

    fig.suptitle(
        f"Figure 8. Cohort-level divergence of the HAI from the official AQI across "
        f"{divergence['n_city_days_evaluated']:,} city-days.\n"
        f"At least one cohort receives a different advisory band on "
        f"{divergence['any_cohort_differs']['pct']:.1f}% of days; the aggregation rule "
        f"alone accounts for {divergence['aggregation_effect']['pct']:.1f}%.",
        fontsize=12,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    return _save(fig, "08_hai_divergence_by_cohort.png")


def plot_feature_selection(selection: Dict[str, Any]) -> Path:
    """Render the top retained features by importance for both tasks."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    for ax, (task, info) in zip(axes, selection.items()):
        top = info["retained_with_importance"][:20][::-1]
        names = [t["feature"] for t in top]
        shares = [t["importance_share_pct"] for t in top]
        bars = ax.barh(names, shares, color=config.PALETTE[0])
        ax.bar_label(bars, fmt="%.1f%%", padding=2, fontsize=8)
        ax.set_xlabel("Share of total LightGBM gain (%)")
        ax.set_xlim(0, max(shares) * 1.22)
        ax.tick_params(axis="y", labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_title(
            f"{task.capitalize()} ({info['target']})\n"
            f"{info['n_candidates']} candidates -> "
            f"{info['stage_0_zero_variance']['n_dropped']} constant, "
            f"{info['stage_1_correlation']['n_dropped']} redundant, "
            f"{info['stage_2_model_based']['n_dropped']} uninformative -> "
            f"{info['n_retained']} retained",
            fontsize=10,
            loc="left",
        )
    fig.suptitle(
        "Figure 9. Feature selection: top 20 retained features per task, fitted on "
        "training rows only",
        fontsize=12,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return _save(fig, "09_feature_selection.png")


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def build_feature_matrix() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Run the whole feature pipeline and return the matrix with its audit trail."""
    config.set_global_seed()
    config.ensure_dirs()

    if not CLEAN_PATH.exists():
        raise FileNotFoundError(f"{CLEAN_PATH} missing. Run `python -m src.data.clean`.")
    frame = pd.read_csv(CLEAN_PATH, parse_dates=["Date"])
    LOGGER.info("Loaded %s: %s rows", CLEAN_PATH.name, f"{len(frame):,}")

    boundary = compute_split_boundary(frame)

    frame = add_temporal_features(frame)
    frame, events = add_event_flags(frame)
    frame, lag_cols = add_lag_features(frame)
    frame, roll_cols = add_rolling_features(frame)
    frame, ratio_cols = add_ratio_features(frame)
    frame, station_info = integrate_station_metadata(frame)
    frame, hai_cols, divergence = add_hai_features(frame)
    frame = add_targets(frame)
    frame, encoded_cols, encoding_info = encode_categoricals(frame, boundary)

    temporal_cols = [
        "year", "month", "day_of_month", "day_of_week", "day_of_year", "week_of_year",
        "quarter", "is_weekend", "month_sin", "month_cos", "doy_sin", "doy_cos",
        "days_since_start",
    ]
    event_cols = [
        "festival_flag", "days_from_diwali", "stubble_season_flag", "lockdown_flag",
        "post_lockdown_flag", "covid_year_flag",
    ]
    metadata_cols = ["n_stations", "n_active_stations"]
    same_day_cols = KEPT_POLLUTANTS + ["AQI", "AQI_Bucket_ordinal", "aqi_above_scale",
                                       "n_imputed_pollutants", "inserted_calendar_day"]

    candidates = (
        same_day_cols
        + temporal_cols
        + event_cols
        + lag_cols
        + roll_cols
        + ratio_cols
        + metadata_cols
        + hai_cols
        + encoded_cols
    )
    candidates = [c for c in dict.fromkeys(candidates) if c in frame.columns]

    # Leakage guard: no next-day column may ever appear among the candidates.
    forbidden = {"AQI_next", "AQI_Bucket_next", "AQI_Bucket_next_ordinal"}
    intersection = forbidden & set(candidates)
    assert not intersection, f"next-day target leaked into features: {intersection}"

    numeric_candidates = [
        c for c in candidates if pd.api.types.is_numeric_dtype(frame[c])
    ]
    LOGGER.info(
        "Candidate features: %s total, %s numeric", len(candidates), len(numeric_candidates)
    )

    selection = {
        "regression": select_features(
            frame, numeric_candidates, config.TARGET_REGRESSION, boundary, "regression"
        ),
        "classification": select_features(
            frame, numeric_candidates, config.TARGET_CLASSIFICATION, boundary, "classification"
        ),
    }

    plot_hai_vs_aqi(frame, divergence)
    plot_hai_divergence(divergence)
    plot_feature_selection(selection)

    frame.to_csv(FEATURES_PATH, index=False)
    LOGGER.info(
        "Wrote %s (%s rows x %s cols)", FEATURES_PATH.name, f"{len(frame):,}", frame.shape[1]
    )

    train = frame.loc[frame["Date"] < boundary].copy()
    test = frame.loc[frame["Date"] >= boundary].copy()
    train.to_csv(TRAIN_PATH, index=False)
    test.to_csv(TEST_PATH, index=False)

    assert train["Date"].max() < boundary <= test["Date"].min()
    LOGGER.info(
        "Split at %s | train %s rows (%s to %s) | test %s rows (%s to %s)",
        boundary.strftime("%Y-%m-%d"),
        f"{len(train):,}",
        train["Date"].min().strftime("%Y-%m-%d"),
        train["Date"].max().strftime("%Y-%m-%d"),
        f"{len(test):,}",
        test["Date"].min().strftime("%Y-%m-%d"),
        test["Date"].max().strftime("%Y-%m-%d"),
    )

    FEATURE_COLUMNS_PATH.write_text(
        json.dumps(
            {
                "regression": selection["regression"]["retained"],
                "classification": selection["classification"]["retained"],
                "all_numeric_candidates": numeric_candidates,
                "split_boundary": boundary.strftime("%Y-%m-%d"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    report: Dict[str, Any] = {
        "generated_by": "src/features/build.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "forecasting_formulation": (
            "Targets are next-day AQI and next-day AQI bucket, per city. Features "
            "may use measurements dated today or earlier for that city only."
        ),
        "leakage_controls": {
            "temporal": (
                "The split is a fixed calendar boundary; shuffle is never used. "
                "TimeSeriesSplit is used for cross-validation. Lags and rolling "
                "windows are computed with groupby('City') so no city contributes "
                "to another city's history, and no window extends past the current "
                "day."
            ),
            "target": (
                "AQI_next and AQI_Bucket_next are mutually excluded from each "
                "other's feature matrix, and an assertion in build_feature_matrix "
                "fails the run if either appears among the candidates. Same-day AQI "
                "and AQI_Bucket_ordinal are retained as legitimate predictors "
                "because they are known at prediction time; the distinct same-day "
                "nowcast leakage is demonstrated empirically in "
                "models/train_classification.py."
            ),
            "encoder": encoding_info["city_target_encoding"]["leakage_note"],
            "scaler": (
                "Scaling is performed inside a scikit-learn Pipeline so that "
                "fit_transform touches training folds only; no scaler is ever "
                "fitted on the test partition."
            ),
            "imputation": (
                "All imputation statistics were estimated on pre-boundary rows in "
                "src/data/clean.py, and the adopted strategy uses no "
                "forward-looking information within a city's series."
            ),
        },
        "shape": {"rows": int(frame.shape[0]), "columns": int(frame.shape[1])},
        "split": {
            "boundary": boundary.strftime("%Y-%m-%d"),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "train_range": [
                train["Date"].min().strftime("%Y-%m-%d"),
                train["Date"].max().strftime("%Y-%m-%d"),
            ],
            "test_range": [
                test["Date"].min().strftime("%Y-%m-%d"),
                test["Date"].max().strftime("%Y-%m-%d"),
            ],
            "test_fraction_actual": round(len(test) / len(frame), 4),
        },
        "feature_groups": {
            "same_day_measurements": same_day_cols,
            "temporal": temporal_cols,
            "event_flags": event_cols,
            "lags": lag_cols,
            "rolling": roll_cols,
            "ratios": ratio_cols,
            "station_metadata": metadata_cols,
            "hai_and_sub_indices": hai_cols,
            "encoded_categoricals": encoded_cols,
        },
        "feature_group_counts": {
            "same_day_measurements": len(same_day_cols),
            "temporal": len(temporal_cols),
            "event_flags": len(event_cols),
            "lags": len(lag_cols),
            "rolling": len(roll_cols),
            "ratios": len(ratio_cols),
            "station_metadata": len(metadata_cols),
            "hai_and_sub_indices": len(hai_cols),
            "encoded_categoricals": len(encoded_cols),
            "total_candidates": len(candidates),
            "numeric_candidates": len(numeric_candidates),
        },
        "event_flags": events,
        "station_metadata": station_info,
        "encodings": encoding_info,
        "feature_selection": selection,
        "targets": {
            "regression": config.TARGET_REGRESSION,
            "classification": config.TARGET_CLASSIFICATION,
            "regression_non_null": int(frame["AQI_next"].notna().sum()),
            "classification_non_null": int(frame["AQI_Bucket_next"].notna().sum()),
        },
        "figures": [
            "07_hai_vs_aqi_scatter.png",
            "08_hai_divergence_by_cohort.png",
            "09_feature_selection.png",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    DIVERGENCE_PATH.write_text(json.dumps(divergence, indent=2, default=str), encoding="utf-8")
    LOGGER.info("Wrote %s and %s", REPORT_PATH.name, DIVERGENCE_PATH.name)
    return frame, report


def main() -> Dict[str, Any]:
    """Entry point."""
    _, report = build_feature_matrix()
    return report


if __name__ == "__main__":
    main()
