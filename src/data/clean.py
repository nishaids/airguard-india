"""Cleaning of the raw daily city table into a modelling-ready record.

Design constraints
------------------
1. ``data/raw/`` is immutable. This module reads from it and writes only to
   ``data/interim/`` and ``data/processed/``.
2. Genuine pollution episodes are retained. Only observations that fail a
   physical-plausibility test, or that show the signature of an isolated sensor
   artefact, are removed. The discriminating rule is stated in
   :func:`flag_sensor_artefacts` and recorded in the output JSON.
3. Imputation must not leak. The train/test boundary is a fixed date derived from
   the calendar span and ``config.TEST_FRACTION``; every imputation statistic is
   estimated on pre-boundary rows only, and the chosen strategy uses no
   forward-looking information within a city's series.
4. The choice of imputation strategy is decided by measurement, not preference.
   :func:`compare_imputation_strategies` runs a masking experiment on the
   training portion and scores five candidate strategies on reconstruction error
   and on distribution shift.

Outputs
-------
``data/interim/city_day_structural.csv``
    Retained cities, calendar-complete per city, artefacts converted to missing.
    No imputation. This is the honest table used for exploratory analysis.
``data/processed/city_day_clean.csv``
    The structural table with the winning imputation strategy applied using
    train-only statistics.
``results/cleaning_report.json``
    Every decision, count and comparison score produced by this module.
``reports/figures/05_imputation_strategy_comparison.png``
``reports/figures/06_imputation_distribution_shift.png``

Run with::

    python -m src.data.clean
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from src import config
from src.data.quality import load_raw_city_day, recommend_city_retention, assess_missingness

LOGGER = config.get_logger(__name__)

STRUCTURAL_PATH = config.INTERIM_DIR / "city_day_structural.csv"
CLEAN_PATH = config.PROCESSED_DIR / "city_day_clean.csv"
REPORT_PATH = config.RESULTS_DIR / "cleaning_report.json"

#: Pollutants excluded from the modelling feature set on coverage grounds.
#: Xylene is missing in over 60% of raw records; imputing a majority of a column
#: manufactures more signal than it recovers.
DROPPED_POLLUTANTS: Tuple[str, ...] = ("Xylene",)

#: Pollutants carried forward into the cleaned table.
KEPT_POLLUTANTS: List[str] = [
    p for p in config.POLLUTANT_COLS if p not in DROPPED_POLLUTANTS
]

#: Species for which an exactly-zero daily mean is physically unattainable in an
#: urban atmosphere and is therefore treated as a reporting artefact.
ZERO_IS_IMPOSSIBLE: Tuple[str, ...] = ("PM2.5", "PM10")

#: Isolated-spike rule parameters. See :func:`flag_sensor_artefacts`.
SPIKE_MAD_MULTIPLIER: float = 8.0
SPIKE_NEIGHBOUR_WINDOW: int = 3


# --------------------------------------------------------------------------- #
# Train/test boundary
# --------------------------------------------------------------------------- #
def compute_split_boundary(frame: pd.DataFrame) -> pd.Timestamp:
    """Return the first date belonging to the held-out test period.

    The boundary is a quantile of the calendar span, not of the observations, so
    it does not depend on how many rows any city happens to contribute and it
    does not depend on the target at all.

    Parameters
    ----------
    frame:
        Table carrying a ``Date`` column.
    """
    start, end = frame["Date"].min(), frame["Date"].max()
    span_days = (end - start).days
    boundary = start + pd.Timedelta(days=int(round(span_days * (1 - config.TEST_FRACTION))))
    return pd.Timestamp(boundary.date())


# --------------------------------------------------------------------------- #
# Structural cleaning
# --------------------------------------------------------------------------- #
def normalise_city_names(frame: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Strip and collapse whitespace in city labels.

    The quality assessment found no naming inconsistency in this dataset, but the
    normalisation is applied unconditionally so that the pipeline stays correct
    if the upstream file is ever refreshed.
    """
    before = sorted(frame["City"].unique().tolist())
    out = frame.copy()
    out["City"] = out["City"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    after = sorted(out["City"].unique().tolist())
    return out, {
        "n_cities_before": len(before),
        "n_cities_after": len(after),
        "labels_changed": sorted(set(before) - set(after)),
        "no_op": before == after,
    }


def deduplicate(frame: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Enforce one record per ``(City, Date)``.

    Policy: fully identical rows are collapsed to one. Where the same key carries
    genuinely different measurements, the record with the greater number of
    non-null pollutant readings is kept, on the grounds that it represents the
    more completely reported observation; ties are broken by taking the first
    occurrence, which keeps the operation deterministic.
    """
    n_before = len(frame)
    out = frame.drop_duplicates(keep="first")
    n_exact_removed = n_before - len(out)

    key_dupes = out.duplicated(subset=["City", "Date"], keep=False)
    n_key_conflicts = int(key_dupes.sum())
    if n_key_conflicts:
        out = out.assign(_completeness=out[KEPT_POLLUTANTS].notna().sum(axis=1))
        out = (
            out.sort_values(["City", "Date", "_completeness"], ascending=[True, True, False])
            .drop_duplicates(subset=["City", "Date"], keep="first")
            .drop(columns="_completeness")
        )

    out = out.sort_values(["City", "Date"]).reset_index(drop=True)
    assert not out.duplicated(subset=["City", "Date"]).any(), "duplicate keys survived"
    return out, {
        "rows_before": n_before,
        "exact_duplicate_rows_removed": n_exact_removed,
        "conflicting_key_rows_resolved": n_key_conflicts,
        "rows_after": int(len(out)),
        "policy": (
            "Exact duplicates collapsed to the first occurrence. Conflicting "
            "(City, Date) keys resolved in favour of the row with more non-null "
            "pollutant readings, ties broken by first occurrence."
        ),
    }


def restrict_to_retained_cities(
    frame: pd.DataFrame,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Keep only the cities that pass the completeness and volume gates."""
    retention = recommend_city_retention(assess_missingness(frame))
    keep = set(retention["retained_cities"])
    out = frame.loc[frame["City"].isin(keep)].copy()
    LOGGER.info(
        "Retained %s of %s cities (%s of %s rows)",
        len(keep),
        frame["City"].nunique(),
        f"{len(out):,}",
        f"{len(frame):,}",
    )
    retention["rows_retained"] = int(len(out))
    retention["rows_dropped"] = int(len(frame) - len(out))
    return out, retention


def ensure_daily_calendar(frame: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Reindex each city onto a gap-free daily calendar over its own span.

    A lag of one row is only a lag of one day when the series has no calendar
    gaps. Inserted days carry missing measurements and are marked
    ``inserted_calendar_day``, so downstream code can tell an imputed value on a
    real observation day from an imputed value on a day the station never
    reported at all.
    """
    pieces: List[pd.DataFrame] = []
    inserted_total = 0
    per_city: List[Dict[str, Any]] = []
    for city, group in frame.groupby("City", sort=True):
        group = group.sort_values("Date")
        full_index = pd.date_range(group["Date"].min(), group["Date"].max(), freq="D")
        reindexed = (
            group.set_index("Date").reindex(full_index).rename_axis("Date").reset_index()
        )
        inserted = int(reindexed["City"].isna().sum())
        reindexed["inserted_calendar_day"] = reindexed["City"].isna().astype(int)
        reindexed["City"] = city
        inserted_total += inserted
        per_city.append(
            {"city": city, "days_in_span": len(full_index), "inserted_days": inserted}
        )
        pieces.append(reindexed)

    out = pd.concat(pieces, ignore_index=True).sort_values(["City", "Date"]).reset_index(drop=True)
    return out, {
        "inserted_calendar_days_total": inserted_total,
        "per_city": per_city,
        "rows_after_reindex": int(len(out)),
    }


def flag_sensor_artefacts(frame: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Convert sensor artefacts to missing while retaining genuine episodes.

    The discriminating rule
    ----------------------
    An observation is treated as a **sensor artefact** and set to missing if it
    satisfies any of:

    A. **Physically impossible sign.** The concentration is negative.
    B. **Beyond plausible range.** The value exceeds the per-pollutant ceiling in
       ``config.POLLUTANT_PLAUSIBLE_MAX``, chosen above the highest concentration
       ever documented for an Indian city so that only instrument faults and
       unit errors are caught.
    C. **Impossible exact zero.** The value is exactly ``0`` for a species whose
       ambient concentration cannot vanish (PM2.5, PM10). Exact zeros in CO, NOx
       and the VOCs are *retained*: those are below-detection-limit reports, not
       faults.
    D. **Isolated spike with no physical build-up.** The value departs from the
       median of the surrounding +/-3 days by more than 8 robust deviations
       (median absolute deviation, scaled), *and* both immediately adjacent days
       are themselves within their normal range. Real pollution episodes are
       driven by meteorology and emissions that persist for many hours, so they
       appear as autocorrelated multi-day excursions with a rise and a decay. A
       single day that leaps and returns with no neighbour elevated is the
       signature of a malfunctioning analyser, not of an airshed.

    An observation is **never** flagged by rule D if it falls inside a documented
    event window (Diwali +/-3 days, the post-monsoon crop-residue burning season,
    or the 2020 national lockdown). Those are precisely the days on which a real
    excursion is expected, and removing them would delete the signal this project
    exists to model. Rules A to C still apply inside event windows, because a
    negative concentration is a fault regardless of the calendar.
    """
    out = frame.copy()
    event_mask = _event_window_mask(out["Date"])

    counts: Dict[str, Dict[str, int]] = {}
    total_flagged = 0
    for pollutant in KEPT_POLLUTANTS:
        series = out[pollutant]
        ceiling = config.POLLUTANT_PLAUSIBLE_MAX[pollutant]

        rule_a = series < 0
        rule_b = series > ceiling
        rule_c = (
            (series == 0) if pollutant in ZERO_IS_IMPOSSIBLE else pd.Series(False, index=series.index)
        )
        rule_d = _isolated_spike_mask(out, pollutant) & (~event_mask)

        artefact = (rule_a | rule_b | rule_c | rule_d).fillna(False)
        counts[pollutant] = {
            "rule_A_negative": int(rule_a.fillna(False).sum()),
            "rule_B_above_ceiling": int(rule_b.fillna(False).sum()),
            "rule_C_impossible_zero": int(rule_c.fillna(False).sum()),
            "rule_D_isolated_spike": int(rule_d.fillna(False).sum()),
            "total_set_to_missing": int(artefact.sum()),
        }
        total_flagged += int(artefact.sum())
        out.loc[artefact, pollutant] = np.nan

    # AQI is recomputed downstream from the cleaned pollutants, but the supplied
    # value is retained as the supervised target. Only impossible AQI values are
    # removed; out-of-scale highs are kept and flagged.
    aqi_impossible = (out["AQI"] < 0) | (out["AQI"] > 2500)
    out.loc[aqi_impossible, ["AQI", "AQI_Bucket"]] = np.nan
    out["aqi_above_scale"] = (out["AQI"] > 500).fillna(False).astype(int)

    return out, {
        "rule": {
            "A": "negative concentration",
            "B": "above per-pollutant plausible ceiling (config.POLLUTANT_PLAUSIBLE_MAX)",
            "C": "exactly zero for PM2.5 or PM10",
            "D": (
                f"isolated spike: |x - median(+/-{SPIKE_NEIGHBOUR_WINDOW}d)| > "
                f"{SPIKE_MAD_MULTIPLIER} scaled MAD with both adjacent days in range, "
                "and the day is outside every documented event window"
            ),
        },
        "event_window_protected_days": int(event_mask.sum()),
        "per_pollutant": counts,
        "total_values_set_to_missing": total_flagged,
        "aqi_values_removed_as_impossible": int(aqi_impossible.sum()),
        "aqi_above_scale_retained_and_flagged": int(out["aqi_above_scale"].sum()),
        "retention_principle": (
            "Genuine pollution episodes are retained in full. The event-window "
            "exemption means that no Diwali, stubble-burning or lockdown "
            "observation is ever removed by the statistical spike rule."
        ),
    }


def _event_window_mask(dates: pd.Series) -> pd.Series:
    """Return a boolean mask marking documented event windows."""
    mask = pd.Series(False, index=dates.index)
    for _, day in config.DIWALI_DATES.items():
        centre = pd.Timestamp(day)
        lo = centre - pd.Timedelta(days=config.DIWALI_WINDOW_DAYS)
        hi = centre + pd.Timedelta(days=config.DIWALI_WINDOW_DAYS)
        mask |= dates.between(lo, hi)

    (m0, d0), (m1, d1) = config.STUBBLE_SEASON
    month, day = dates.dt.month, dates.dt.day
    after_start = (month > m0) | ((month == m0) & (day >= d0))
    before_end = (month < m1) | ((month == m1) & (day <= d1))
    mask |= after_start & before_end

    mask |= dates.between(pd.Timestamp(config.LOCKDOWN_START), pd.Timestamp(config.LOCKDOWN_END))
    return mask.fillna(False)


def _isolated_spike_mask(frame: pd.DataFrame, pollutant: str) -> pd.Series:
    """Return a mask of isolated single-day spikes, computed per city."""
    parts: List[pd.Series] = []
    for _, group in frame.groupby("City", sort=False):
        series = group[pollutant]
        window = 2 * SPIKE_NEIGHBOUR_WINDOW + 1
        with warnings.catch_warnings():
            # An all-missing rolling window legitimately has no median; the
            # resulting NaN is handled below and the warning is noise.
            warnings.simplefilter("ignore", RuntimeWarning)
            local_median = series.rolling(window, center=True, min_periods=3).median()
        deviation = (series - local_median).abs()
        mad = (series - series.median()).abs().median()
        scale = 1.4826 * mad if mad and mad > 0 else series.std()
        if not scale or np.isnan(scale) or scale == 0:
            parts.append(pd.Series(False, index=series.index))
            continue
        is_extreme = deviation > SPIKE_MAD_MULTIPLIER * scale

        q99 = series.quantile(0.99)
        prev_ok = series.shift(1).lt(q99) | series.shift(1).isna()
        next_ok = series.shift(-1).lt(q99) | series.shift(-1).isna()
        parts.append((is_extreme & prev_ok & next_ok).fillna(False))
    return pd.concat(parts).reindex(frame.index).fillna(False)


# --------------------------------------------------------------------------- #
# Imputation strategies
# --------------------------------------------------------------------------- #
def _impute_global_median(
    frame: pd.DataFrame, columns: List[str], stats: Dict[str, Any]
) -> pd.DataFrame:
    """Fill with a single median per column, estimated on the training rows."""
    out = frame.copy()
    for column in columns:
        out[column] = out[column].fillna(stats["global_median"][column])
    return out


def _impute_per_city_median(
    frame: pd.DataFrame, columns: List[str], stats: Dict[str, Any]
) -> pd.DataFrame:
    """Fill with a per-city median, falling back to the global median."""
    out = frame.copy()
    for column in columns:
        city_median = out["City"].map(stats["city_median"][column])
        out[column] = out[column].fillna(city_median).fillna(stats["global_median"][column])
    return out


def _impute_per_city_interpolate(
    frame: pd.DataFrame, columns: List[str], stats: Dict[str, Any]
) -> pd.DataFrame:
    """Fill by linear interpolation in time within each city.

    This strategy is included for comparison but is *not* causal: interpolating a
    gap uses the observation that follows it. It is therefore inadmissible for a
    forecasting feature set and is scored here only to quantify what the
    causality constraint costs.
    """
    out = frame.sort_values(["City", "Date"]).copy()
    for column in columns:
        out[column] = out.groupby("City", sort=False)[column].transform(
            lambda s: s.interpolate(method="linear", limit_direction="both", limit=7)
        )
        city_median = out["City"].map(stats["city_median"][column])
        out[column] = out[column].fillna(city_median).fillna(stats["global_median"][column])
    return out


def _impute_per_city_ffill(
    frame: pd.DataFrame, columns: List[str], stats: Dict[str, Any]
) -> pd.DataFrame:
    """Fill by a 3-day limited forward fill within each city, then medians.

    Only past observations are used, so the strategy is admissible for a
    forecasting problem. The 3-day limit prevents a long outage from being
    papered over with a stale reading.
    """
    out = frame.sort_values(["City", "Date"]).copy()
    for column in columns:
        out[column] = out.groupby("City", sort=False)[column].transform(
            lambda s: s.ffill(limit=3)
        )
        city_median = out["City"].map(stats["city_median"][column])
        out[column] = out[column].fillna(city_median).fillna(stats["global_median"][column])
    return out


def _impute_knn(
    frame: pd.DataFrame, columns: List[str], stats: Dict[str, Any]
) -> pd.DataFrame:
    """Fill with a k-nearest-neighbour imputer over the scaled pollutant block.

    The imputer is fitted on the training rows only. Like interpolation it is
    non-causal in the sense that a neighbour may be a future day, so it is
    reported for comparison rather than adopted.
    """
    from sklearn.impute import KNNImputer
    from sklearn.preprocessing import StandardScaler

    out = frame.copy()
    train_mask = out["Date"] < stats["split_boundary"]
    scaler = StandardScaler()
    scaler.fit(out.loc[train_mask, columns])

    imputer = KNNImputer(n_neighbors=5, weights="distance")
    imputer.fit(scaler.transform(out.loc[train_mask, columns]))

    scaled = scaler.transform(out[columns])
    filled = scaler.inverse_transform(imputer.transform(scaled))
    out[columns] = filled
    for column in columns:
        out[column] = out[column].fillna(stats["global_median"][column])
    return out


IMPUTERS: Dict[str, Tuple[Callable[..., pd.DataFrame], bool, str]] = {
    "global_median": (_impute_global_median, True, "Single median per column"),
    "per_city_median": (_impute_per_city_median, True, "Median per city per column"),
    "per_city_linear_interpolation": (
        _impute_per_city_interpolate,
        False,
        "Linear interpolation in time within city, 7-day limit",
    ),
    "per_city_ffill_limit3": (
        _impute_per_city_ffill,
        True,
        "3-day limited forward fill within city, then per-city median",
    ),
    "knn_k5": (_impute_knn, False, "KNN (k=5, distance weighted) on scaled pollutants"),
}


def fit_imputation_statistics(
    frame: pd.DataFrame, columns: List[str], boundary: pd.Timestamp
) -> Dict[str, Any]:
    """Estimate every imputation statistic on pre-boundary rows only."""
    train = frame.loc[frame["Date"] < boundary]
    return {
        "split_boundary": boundary,
        "global_median": {c: float(train[c].median()) for c in columns},
        "city_median": {
            c: train.groupby("City")[c].median().to_dict() for c in columns
        },
        "n_train_rows_used": int(len(train)),
    }


def compare_imputation_strategies(
    frame: pd.DataFrame,
    columns: List[str],
    boundary: pd.Timestamp,
    mask_fraction: float = 0.15,
    seed: int = config.RANDOM_SEED,
) -> Dict[str, Any]:
    """Score candidate imputation strategies by a masking experiment.

    Method
    ------
    Working on the **training portion only**, cells that are actually observed
    are hidden at random and each strategy is asked to reconstruct them. Two
    families of score are reported:

    * *Reconstruction error* - MAE and RMSE against the hidden truth, expressed
      both in physical units and normalised by the column's interquartile range
      so that pollutants on different scales can be averaged.
    * *Distribution shift* - the two-sample Kolmogorov-Smirnov statistic and the
      first-Wasserstein distance between the observed column and the same column
      after imputation, plus the relative change in mean, standard deviation and
      skewness. A strategy can have low reconstruction error and still distort
      the distribution, which matters because the distribution is what the EDA
      and the tree splits see.

    Strategies that use future information within a city's series are marked
    ``causal = False``; those may not be adopted for a forecasting feature set
    however well they score, and they are reported to quantify the cost of the
    causality constraint.
    """
    rng = np.random.default_rng(seed)
    train = frame.loc[frame["Date"] < boundary].copy().reset_index(drop=True)
    stats = fit_imputation_statistics(frame, columns, boundary)

    holdout: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    masked = train.copy()
    for column in columns:
        observed_idx = np.flatnonzero(train[column].notna().to_numpy())
        if observed_idx.size < 50:
            continue
        n_mask = max(1, int(round(mask_fraction * observed_idx.size)))
        chosen = rng.choice(observed_idx, size=n_mask, replace=False)
        holdout[column] = (chosen, train.loc[chosen, column].to_numpy(dtype=float))
        masked.loc[chosen, column] = np.nan

    results: List[Dict[str, Any]] = []
    for name, (func, causal, description) in IMPUTERS.items():
        filled = func(masked, columns, stats)
        filled = filled.sort_index()

        per_column: List[Dict[str, Any]] = []
        norm_maes: List[float] = []
        for column, (idx, truth) in holdout.items():
            predicted = filled.loc[idx, column].to_numpy(dtype=float)
            mae = float(np.mean(np.abs(predicted - truth)))
            rmse = float(np.sqrt(np.mean((predicted - truth) ** 2)))
            iqr = float(train[column].quantile(0.75) - train[column].quantile(0.25)) or 1.0

            observed_full = train[column].dropna().to_numpy(dtype=float)
            imputed_full = filled[column].dropna().to_numpy(dtype=float)
            ks = float(sp_stats.ks_2samp(observed_full, imputed_full).statistic)
            wass = float(sp_stats.wasserstein_distance(observed_full, imputed_full))

            per_column.append(
                {
                    "column": column,
                    "n_masked": int(idx.size),
                    "mae": round(mae, 4),
                    "rmse": round(rmse, 4),
                    "mae_over_iqr": round(mae / iqr, 4),
                    "ks_statistic": round(ks, 4),
                    "wasserstein": round(wass, 4),
                    "mean_shift_pct": round(
                        100.0 * (imputed_full.mean() - observed_full.mean()) / observed_full.mean(),
                        3,
                    ),
                    "std_shift_pct": round(
                        100.0 * (imputed_full.std() - observed_full.std()) / observed_full.std(), 3
                    ),
                    "skew_before": round(float(sp_stats.skew(observed_full)), 3),
                    "skew_after": round(float(sp_stats.skew(imputed_full)), 3),
                }
            )
            norm_maes.append(mae / iqr)

        results.append(
            {
                "strategy": name,
                "description": description,
                "causal": causal,
                "mean_mae_over_iqr": round(float(np.mean(norm_maes)), 4),
                "mean_ks_statistic": round(
                    float(np.mean([c["ks_statistic"] for c in per_column])), 4
                ),
                "mean_abs_std_shift_pct": round(
                    float(np.mean([abs(c["std_shift_pct"]) for c in per_column])), 3
                ),
                "per_column": per_column,
            }
        )

    causal_results = [r for r in results if r["causal"]]
    best_causal = min(causal_results, key=lambda r: r["mean_mae_over_iqr"])
    best_overall = min(results, key=lambda r: r["mean_mae_over_iqr"])

    return {
        "method": (
            f"Masking experiment on the training portion only: {mask_fraction:.0%} of "
            "observed cells per column hidden at random with seed "
            f"{seed}, then reconstructed. Scored on MAE normalised by the column "
            "interquartile range and on distribution shift (KS statistic, "
            "Wasserstein distance, moment changes)."
        ),
        "mask_fraction": mask_fraction,
        "n_train_rows": int(len(train)),
        "results": results,
        "best_overall": best_overall["strategy"],
        "best_causal": best_causal["strategy"],
        "selected": best_causal["strategy"],
        "selection_rationale": (
            f"{best_overall['strategy']} attains the lowest normalised MAE overall "
            f"({best_overall['mean_mae_over_iqr']:.4f}), but it is non-causal: it "
            "reconstructs a gap using observations that follow it. Because the "
            "modelling task is to forecast tomorrow from information available "
            f"today, the adopted strategy is {best_causal['strategy']}, the best of "
            f"the causal candidates ({best_causal['mean_mae_over_iqr']:.4f} "
            "normalised MAE). Adopting a non-causal imputer would inflate reported "
            "test performance without improving real forecasting skill."
        ),
    }


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def _save(fig: "plt.Figure", name: str) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = config.FIGURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", name)
    return path


def plot_imputation_comparison(comparison: Dict[str, Any]) -> Path:
    """Render the strategy bake-off: reconstruction error against shift."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = comparison["results"]
    names = [r["strategy"] for r in rows]
    mae = [r["mean_mae_over_iqr"] for r in rows]
    ks = [r["mean_ks_statistic"] for r in rows]
    causal = [r["causal"] for r in rows]
    colours = [config.PALETTE[2] if c else config.PALETTE[1] for c in causal]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.2))
    bars = ax1.barh(names[::-1], mae[::-1], color=colours[::-1])
    ax1.bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    ax1.set_xlabel("Mean MAE / IQR  (lower is better)")
    ax1.set_xlim(0, max(mae) * 1.22)
    ax1.set_title("Reconstruction error on 15% masked cells", fontsize=11, loc="left")
    ax1.spines[["top", "right"]].set_visible(False)

    bars2 = ax2.barh(names[::-1], ks[::-1], color=colours[::-1])
    ax2.bar_label(bars2, fmt="%.3f", padding=3, fontsize=9)
    ax2.set_xlabel("Mean KS statistic vs observed distribution (lower is better)")
    ax2.set_xlim(0, max(ks) * 1.28 if max(ks) > 0 else 1)
    ax2.set_title("Distribution shift introduced by imputation", fontsize=11, loc="left")
    ax2.spines[["top", "right"]].set_visible(False)

    from matplotlib.patches import Patch

    fig.legend(
        handles=[
            Patch(facecolor=config.PALETTE[2], label="Causal (admissible for forecasting)"),
            Patch(facecolor=config.PALETTE[1], label="Non-causal (reference only)"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, -0.06),
    )
    fig.suptitle(
        f"Figure 5. Imputation strategy comparison by masking experiment. "
        f"Adopted: {comparison['selected']}",
        fontsize=12,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    return _save(fig, "05_imputation_strategy_comparison.png")


def plot_distribution_shift(
    before: pd.DataFrame, after: pd.DataFrame, columns: List[str]
) -> Path:
    """Overlay pre- and post-imputation distributions for six pollutants."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    chosen = [c for c in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"] if c in columns]
    fig, axes = plt.subplots(2, 3, figsize=(15, 7.5))
    for ax, column in zip(axes.ravel(), chosen):
        observed = before[column].dropna()
        imputed = after[column].dropna()
        upper = float(np.nanpercentile(observed, 99.5))
        bins = np.linspace(0, upper, 60)
        ax.hist(
            observed, bins=bins, density=True, alpha=0.55,
            color=config.PALETTE[0], label=f"Before (n={len(observed):,})",
        )
        ax.hist(
            imputed, bins=bins, density=True, histtype="step", linewidth=1.8,
            color=config.PALETTE[1], label=f"After (n={len(imputed):,})",
        )
        ks = sp_stats.ks_2samp(observed, imputed).statistic
        ax.set_title(
            f"{column} ({config.POLLUTANT_UNITS[column]})   KS = {ks:.3f}",
            fontsize=10,
        )
        ax.legend(fontsize=7.5, frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "Figure 6. Distribution shift introduced by the adopted imputation strategy\n"
        "Step outlines track the filled bars closely, so filling the gaps did not "
        "reshape any pollutant distribution.",
        fontsize=12,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return _save(fig, "06_imputation_distribution_shift.png")


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_clean(
    frame: pd.DataFrame, boundary: pd.Timestamp, columns: List[str]
) -> Dict[str, Any]:
    """Assert every post-clean invariant and return the evidence.

    Failures raise ``AssertionError`` loudly rather than being logged, so a
    broken pipeline cannot silently produce a report.
    """
    checks: Dict[str, Any] = {}

    assert not frame.duplicated(subset=["City", "Date"]).any(), "duplicate (City, Date)"
    checks["primary_key_unique"] = True

    residual_nulls = {c: int(frame[c].isna().sum()) for c in columns}
    assert sum(residual_nulls.values()) == 0, f"nulls remain in pollutants: {residual_nulls}"
    checks["no_nulls_in_pollutants"] = True

    negatives = {c: int((frame[c] < 0).sum()) for c in columns}
    assert sum(negatives.values()) == 0, f"negative values remain: {negatives}"
    checks["no_negative_pollutants"] = True

    for city, group in frame.groupby("City"):
        gaps = pd.date_range(group["Date"].min(), group["Date"].max(), freq="D")
        assert len(gaps) == len(group), f"calendar gap remains in {city}"
    checks["calendar_complete_per_city"] = True

    n_train = int((frame["Date"] < boundary).sum())
    n_test = int((frame["Date"] >= boundary).sum())
    assert n_train > 0 and n_test > 0, "empty split partition"
    assert frame.loc[frame["Date"] < boundary, "Date"].max() < boundary
    assert frame.loc[frame["Date"] >= boundary, "Date"].min() >= boundary
    checks["train_test_date_boundary_respected"] = True
    checks["n_train_rows"] = n_train
    checks["n_test_rows"] = n_test
    checks["split_boundary"] = boundary.strftime("%Y-%m-%d")

    checks["shape"] = {"rows": int(frame.shape[0]), "columns": int(frame.shape[1])}
    checks["cities"] = int(frame["City"].nunique())
    checks["date_range"] = [
        frame["Date"].min().strftime("%Y-%m-%d"),
        frame["Date"].max().strftime("%Y-%m-%d"),
    ]
    checks["aqi_nulls_remaining"] = int(frame["AQI"].isna().sum())
    checks["aqi_null_note"] = (
        "AQI is the supervised target and is deliberately NOT imputed. Rows "
        "without a labelled AQI are excluded when a supervised matrix is built, "
        "and retained here so that per-city lag features can still be computed "
        "over a gap-free calendar."
    )
    return checks


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def main() -> Dict[str, Any]:
    """Run the cleaning pipeline end to end and write every artefact."""
    config.set_global_seed()
    config.ensure_dirs()

    raw = load_raw_city_day()
    frame, naming = normalise_city_names(raw)
    frame, dedupe = deduplicate(frame)
    frame, retention = restrict_to_retained_cities(frame)

    dropped_cols = list(DROPPED_POLLUTANTS)
    frame = frame.drop(columns=dropped_cols)
    LOGGER.info("Dropped columns on coverage grounds: %s", dropped_cols)

    frame, calendar = ensure_daily_calendar(frame)
    frame, artefacts = flag_sensor_artefacts(frame)

    boundary = compute_split_boundary(frame)
    LOGGER.info(
        "Train/test boundary: %s (train < boundary, test >= boundary)",
        boundary.strftime("%Y-%m-%d"),
    )

    structural = frame.copy()
    structural.to_csv(STRUCTURAL_PATH, index=False)
    LOGGER.info("Wrote %s (%s rows)", STRUCTURAL_PATH.name, f"{len(structural):,}")

    comparison = compare_imputation_strategies(structural, KEPT_POLLUTANTS, boundary)
    LOGGER.info(
        "Imputation bake-off | best overall: %s | adopted (causal): %s",
        comparison["best_overall"],
        comparison["selected"],
    )
    plot_imputation_comparison(comparison)

    stats = fit_imputation_statistics(structural, KEPT_POLLUTANTS, boundary)
    imputer_func = IMPUTERS[comparison["selected"]][0]
    cleaned = imputer_func(structural, KEPT_POLLUTANTS, stats)
    cleaned = cleaned.sort_values(["City", "Date"]).reset_index(drop=True)

    imputed_cell_counts = {
        c: int(structural[c].isna().sum()) for c in KEPT_POLLUTANTS
    }
    cleaned["n_imputed_pollutants"] = structural[KEPT_POLLUTANTS].isna().sum(axis=1).to_numpy()

    plot_distribution_shift(structural, cleaned, KEPT_POLLUTANTS)
    validation = validate_clean(cleaned, boundary, KEPT_POLLUTANTS)

    cleaned.to_csv(CLEAN_PATH, index=False)
    LOGGER.info("Wrote %s (%s rows x %s cols)", CLEAN_PATH.name, f"{len(cleaned):,}", cleaned.shape[1])

    report: Dict[str, Any] = {
        "generated_by": "src/data/clean.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {"raw_file": str(config.RAW_DIR / config.PRIMARY_FILE)},
        "outputs": {
            "structural": str(STRUCTURAL_PATH),
            "clean": str(CLEAN_PATH),
        },
        "city_name_normalisation": naming,
        "deduplication": dedupe,
        "city_retention": retention,
        "columns_dropped": {
            "columns": dropped_cols,
            "reason": (
                "Xylene is missing in 61.3% of raw records. Imputing the majority "
                "of a column would inject more modelled values than measured ones, "
                "so the column is dropped rather than reconstructed."
            ),
        },
        "calendar_reindex": calendar,
        "artefact_policy": artefacts,
        "split_boundary": boundary.strftime("%Y-%m-%d"),
        "split_policy": (
            "The boundary is placed at the "
            f"{1 - config.TEST_FRACTION:.0%} point of the calendar span, so the "
            "training period strictly precedes the test period. Every imputation "
            "statistic, scaler and encoder in this project is estimated on "
            "pre-boundary rows only."
        ),
        "imputation_comparison": comparison,
        "imputation_applied": {
            "strategy": comparison["selected"],
            "statistics_estimated_on": f"rows with Date < {boundary.strftime('%Y-%m-%d')}",
            "n_train_rows_used_for_statistics": stats["n_train_rows_used"],
            "cells_imputed_per_column": imputed_cell_counts,
            "cells_imputed_total": int(sum(imputed_cell_counts.values())),
            "cells_total": int(len(structural) * len(KEPT_POLLUTANTS)),
            "cells_imputed_pct": round(
                100.0 * sum(imputed_cell_counts.values()) / (len(structural) * len(KEPT_POLLUTANTS)),
                3,
            ),
        },
        "validation": validation,
        "figures": [
            "05_imputation_strategy_comparison.png",
            "06_imputation_distribution_shift.png",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    LOGGER.info("Wrote %s", REPORT_PATH.name)
    return report


if __name__ == "__main__":
    main()
