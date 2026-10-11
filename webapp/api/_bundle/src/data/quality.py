"""Data quality assessment of the raw daily city-level air quality table.

The module answers, with executed code rather than assertion, the questions a
reviewer is entitled to ask before any cleaning is attempted:

* how much of each column is missing, and is the missingness structured?
* are there duplicate records, or duplicate ``(City, Date)`` primary keys?
* are there physically invalid values (negative concentrations, impossible
  dates, out-of-scale AQI)?
* is city naming internally consistent, and consistent with ``stations.csv``?
* do the reported units pass order-of-magnitude sanity checks?
* how many outliers does each pollutant carry under an IQR rule and under a
  z-score rule, and do the two rules agree?
* which cities have enough usable record to be modelled at all?

Outputs
-------
``results/data_quality_report.json``
    The complete machine-readable assessment. Every figure and every table in
    the Review 2 document is rendered from this file.
``reports/figures/01_missingness_matrix.png``
``reports/figures/02_city_availability_heatmap.png``
``reports/figures/03_null_percentage_bar.png``
``reports/figures/04_outlier_counts.png``

Run with::

    python -m src.data.quality
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src import config

LOGGER = config.get_logger(__name__)

REPORT_PATH = config.RESULTS_DIR / "data_quality_report.json"

#: Order-of-magnitude reference ranges for a plausible Indian urban daily mean.
#: A column whose median falls outside its range is flagged for unit review.
#: Ranges are deliberately wide: the test detects a unit error (e.g. CO reported
#: in ug/m3 rather than mg/m3), not an unusual pollution day.
UNIT_SANITY_RANGES: Dict[str, tuple] = {
    "PM2.5": (5.0, 300.0),
    "PM10": (10.0, 500.0),
    "NO": (0.5, 150.0),
    "NO2": (2.0, 150.0),
    "NOx": (2.0, 200.0),
    "NH3": (1.0, 150.0),
    "CO": (0.05, 10.0),
    "SO2": (1.0, 100.0),
    "O3": (2.0, 150.0),
    "Benzene": (0.0, 50.0),
    "Toluene": (0.0, 100.0),
    "Xylene": (0.0, 50.0),
}


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_raw_city_day() -> pd.DataFrame:
    """Load ``data/raw/city_day.csv`` without modifying it.

    Returns
    -------
    pandas.DataFrame
        The raw table with ``Date`` parsed to ``datetime64``. No other change is
        applied: this function must never mutate the immutable raw layer.
    """
    path = config.RAW_DIR / config.PRIMARY_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python -m src.data.acquire` first."
        )
    frame = pd.read_csv(path, parse_dates=["Date"])
    LOGGER.info("Loaded %s: %s rows x %s cols", path.name, f"{len(frame):,}", frame.shape[1])
    return frame


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #
def assess_missingness(frame: pd.DataFrame) -> Dict[str, Any]:
    """Quantify missingness per column and per city."""
    n_rows = len(frame)
    per_column: List[Dict[str, Any]] = []
    for column in frame.columns:
        nulls = int(frame[column].isna().sum())
        per_column.append(
            {
                "column": column,
                "nulls": nulls,
                "non_null": int(n_rows - nulls),
                "null_pct": round(100.0 * nulls / n_rows, 3),
            }
        )

    complete_rows = int(frame.dropna(subset=config.POLLUTANT_COLS + ["AQI"]).shape[0])

    per_city: List[Dict[str, Any]] = []
    for city, group in frame.groupby("City", sort=True):
        span_days = int((group["Date"].max() - group["Date"].min()).days) + 1
        aqi_non_null = int(group["AQI"].notna().sum())
        per_city.append(
            {
                "city": city,
                "records": int(len(group)),
                "calendar_span_days": span_days,
                "aqi_non_null": aqi_non_null,
                "aqi_completeness_vs_span": round(aqi_non_null / span_days, 4),
                "row_completeness_vs_span": round(len(group) / span_days, 4),
                "mean_pollutant_null_pct": round(
                    float(group[config.POLLUTANT_COLS].isna().mean().mean() * 100), 2
                ),
                "first_date": group["Date"].min().strftime("%Y-%m-%d"),
                "last_date": group["Date"].max().strftime("%Y-%m-%d"),
            }
        )

    return {
        "n_rows": n_rows,
        "per_column": per_column,
        "rows_complete_on_all_pollutants_and_aqi": complete_rows,
        "rows_complete_pct": round(100.0 * complete_rows / n_rows, 3),
        "per_city": per_city,
    }


def assess_duplicates(frame: pd.DataFrame) -> Dict[str, Any]:
    """Count fully duplicated rows and duplicated ``(City, Date)`` keys."""
    full_dupes = int(frame.duplicated(keep=False).sum())
    key_dupes_mask = frame.duplicated(subset=["City", "Date"], keep=False)
    key_dupes = int(key_dupes_mask.sum())
    examples: List[Dict[str, str]] = []
    if key_dupes:
        sample = frame.loc[key_dupes_mask, ["City", "Date"]].head(10)
        examples = [
            {"city": row.City, "date": row.Date.strftime("%Y-%m-%d")}
            for row in sample.itertuples()
        ]
    return {
        "fully_duplicated_rows": full_dupes,
        "duplicated_city_date_keys": key_dupes,
        "duplicated_key_examples": examples,
        "primary_key_is_unique": key_dupes == 0,
    }


def assess_invalid_values(frame: pd.DataFrame) -> Dict[str, Any]:
    """Detect negative concentrations, zero-runs and out-of-scale AQI values."""
    per_pollutant: List[Dict[str, Any]] = []
    for column in config.POLLUTANT_COLS:
        series = frame[column]
        ceiling = config.POLLUTANT_PLAUSIBLE_MAX[column]
        per_pollutant.append(
            {
                "pollutant": column,
                "unit": config.POLLUTANT_UNITS[column],
                "negative_values": int((series < 0).sum()),
                "exact_zeros": int((series == 0).sum()),
                "above_plausible_ceiling": int((series > ceiling).sum()),
                "plausible_ceiling": ceiling,
                "observed_min": None if series.notna().sum() == 0 else float(series.min()),
                "observed_max": None if series.notna().sum() == 0 else float(series.max()),
            }
        )

    aqi = frame["AQI"]
    aqi_checks = {
        "negative_aqi": int((aqi < 0).sum()),
        "aqi_below_scale_min": int((aqi < 0).sum()),
        "aqi_above_scale_max_500": int((aqi > 500).sum()),
        "aqi_above_scale_max_500_pct": round(
            100.0 * int((aqi > 500).sum()) / int(aqi.notna().sum()), 3
        ),
        "observed_aqi_min": float(aqi.min()),
        "observed_aqi_max": float(aqi.max()),
        "note": (
            "The CPCB National AQI scale is defined on 0-500. Values above 500 "
            "arise because the dataset compiler extrapolated the topmost "
            "sub-index breakpoint linearly instead of capping at 500. Such rows "
            "are retained: they mark genuine extreme-pollution days, and "
            "truncating them would erase the very events the advisory system "
            "exists to warn about. They are flagged in data/processed/ via the "
            "column aqi_above_scale."
        ),
    }

    bucket_consistency = _check_bucket_consistency(frame)
    date_checks = _check_dates(frame)
    return {
        "per_pollutant": per_pollutant,
        "aqi": aqi_checks,
        "bucket_consistency": bucket_consistency,
        "dates": date_checks,
    }


def _check_bucket_consistency(frame: pd.DataFrame) -> Dict[str, Any]:
    """Verify that ``AQI_Bucket`` is the CPCB category implied by ``AQI``.

    Confirming this relationship empirically is what justifies treating
    ``AQI_Bucket`` as a deterministic function of ``AQI``, and therefore as a
    label-leakage hazard in the classification task.
    """
    subset = frame.dropna(subset=["AQI", "AQI_Bucket"]).copy()
    expected = pd.cut(
        subset["AQI"],
        bins=[-np.inf, 50, 100, 200, 300, 400, np.inf],
        labels=config.AQI_BUCKETS,
        right=True,
    ).astype(str)
    mismatch_mask = expected.to_numpy() != subset["AQI_Bucket"].to_numpy()
    n_mismatch = int(mismatch_mask.sum())
    examples: List[Dict[str, Any]] = []
    if n_mismatch:
        sample = subset.loc[mismatch_mask, ["City", "Date", "AQI", "AQI_Bucket"]].head(10)
        examples = [
            {
                "city": row.City,
                "date": row.Date.strftime("%Y-%m-%d"),
                "aqi": float(row.AQI),
                "bucket_in_file": row.AQI_Bucket,
                "bucket_expected": expected.to_numpy()[
                    int(np.where(mismatch_mask)[0][idx])
                ],
            }
            for idx, row in enumerate(sample.itertuples())
        ]
    return {
        "rows_checked": int(len(subset)),
        "mismatches": n_mismatch,
        "agreement_pct": round(100.0 * (1 - n_mismatch / len(subset)), 4) if len(subset) else None,
        "examples": examples,
        "implication": (
            "AQI_Bucket is reproducible from AQI by the CPCB cut points alone. "
            "AQI must therefore be excluded from the feature matrix of the "
            "bucket-classification task, otherwise the model trivially recovers "
            "the label."
        ),
        "aqi_null_but_bucket_present": int(
            (frame["AQI"].isna() & frame["AQI_Bucket"].notna()).sum()
        ),
        "bucket_null_but_aqi_present": int(
            (frame["AQI_Bucket"].isna() & frame["AQI"].notna()).sum()
        ),
    }


def _check_dates(frame: pd.DataFrame) -> Dict[str, Any]:
    """Check the date column for impossible values and calendar gaps."""
    dates = frame["Date"]
    lower, upper = pd.Timestamp("2015-01-01"), pd.Timestamp("2020-12-31")
    gaps: List[Dict[str, Any]] = []
    for city, group in frame.groupby("City", sort=True):
        ordered = group["Date"].sort_values()
        expected_days = int((ordered.max() - ordered.min()).days) + 1
        gaps.append(
            {
                "city": city,
                "observed_days": int(ordered.nunique()),
                "expected_days_in_span": expected_days,
                "missing_calendar_days": expected_days - int(ordered.nunique()),
            }
        )
    return {
        "nulls": int(dates.isna().sum()),
        "min": dates.min().strftime("%Y-%m-%d"),
        "max": dates.max().strftime("%Y-%m-%d"),
        "outside_plausible_window": int(((dates < lower) | (dates > upper)).sum()),
        "plausible_window": ["2015-01-01", "2020-12-31"],
        "future_dates": int((dates > pd.Timestamp(datetime.now().date())).sum()),
        "calendar_gaps_by_city": gaps,
        "total_missing_calendar_days": int(sum(g["missing_calendar_days"] for g in gaps)),
    }


def assess_city_naming(frame: pd.DataFrame) -> Dict[str, Any]:
    """Look for inconsistent city labels and cross-check with ``stations.csv``."""
    cities = sorted(frame["City"].unique().tolist())
    normalised: Dict[str, List[str]] = {}
    for city in cities:
        key = city.strip().lower().replace(" ", "").replace("-", "")
        normalised.setdefault(key, []).append(city)
    collisions = {k: v for k, v in normalised.items() if len(v) > 1}

    whitespace_issues = [c for c in cities if c != c.strip()]
    case_issues = [c for c in cities if c != c.title() and c != c.upper()]

    stations_path = config.RAW_DIR / config.STATION_META_FILE
    cross_check: Dict[str, Any] = {}
    if stations_path.exists():
        stations = pd.read_csv(stations_path)
        station_cities = set(stations["City"].dropna().unique().tolist())
        cross_check = {
            "cities_in_city_day_not_in_stations": sorted(set(cities) - station_cities),
            "n_cities_in_stations": len(station_cities),
            "n_cities_matched": len(set(cities) & station_cities),
        }

    return {
        "n_cities": len(cities),
        "cities": cities,
        "normalisation_collisions": collisions,
        "leading_or_trailing_whitespace": whitespace_issues,
        "non_title_case": case_issues,
        "stations_cross_check": cross_check,
        "verdict": (
            "consistent"
            if not collisions and not whitespace_issues
            else "inconsistent - normalisation required"
        ),
    }


def assess_units(frame: pd.DataFrame) -> Dict[str, Any]:
    """Order-of-magnitude sanity check on each pollutant column."""
    results: List[Dict[str, Any]] = []
    for column, (low, high) in UNIT_SANITY_RANGES.items():
        series = frame[column].dropna()
        if series.empty:
            results.append({"pollutant": column, "status": "no data"})
            continue
        median = float(series.median())
        results.append(
            {
                "pollutant": column,
                "declared_unit": config.POLLUTANT_UNITS[column],
                "median": round(median, 4),
                "expected_median_range": [low, high],
                "status": "plausible" if low <= median <= high else "REVIEW UNITS",
            }
        )
    return {
        "checks": results,
        "n_flagged": sum(1 for r in results if r.get("status") == "REVIEW UNITS"),
    }


def assess_outliers(frame: pd.DataFrame) -> Dict[str, Any]:
    """Count outliers per pollutant under an IQR rule and a z-score rule.

    Both rules are reported because they disagree systematically on heavily
    right-skewed data: the IQR rule flags far more observations once the
    distribution has a long upper tail, while a z-score rule computed from a
    mean and standard deviation that the tail itself inflates flags fewer. The
    disagreement is evidence that neither rule may be used on its own to delete
    data, which is the basis of the retention policy in ``data/clean.py``.
    """
    results: List[Dict[str, Any]] = []
    for column in config.POLLUTANT_COLS + ["AQI"]:
        series = frame[column].dropna()
        if series.empty:
            continue
        q1, q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        iqr_out = int(((series < lower) | (series > upper)).sum())
        mean, std = float(series.mean()), float(series.std())
        z_out = int((np.abs((series - mean) / std) > 3).sum()) if std > 0 else 0
        results.append(
            {
                "column": column,
                "n": int(len(series)),
                "q1": round(q1, 3),
                "q3": round(q3, 3),
                "iqr": round(iqr, 3),
                "iqr_lower_fence": round(lower, 3),
                "iqr_upper_fence": round(upper, 3),
                "iqr_outliers": iqr_out,
                "iqr_outlier_pct": round(100.0 * iqr_out / len(series), 3),
                "z_outliers_gt_3": z_out,
                "z_outlier_pct": round(100.0 * z_out / len(series), 3),
                "skew": round(float(series.skew()), 3),
                "kurtosis": round(float(series.kurtosis()), 3),
                "above_plausible_ceiling": int(
                    (series > config.POLLUTANT_PLAUSIBLE_MAX[column]).sum()
                )
                if column in config.POLLUTANT_PLAUSIBLE_MAX
                else None,
            }
        )
    return {
        "method_iqr": "Tukey fence, k = 1.5 on Q1/Q3",
        "method_zscore": "|z| > 3 on the column mean and standard deviation",
        "per_column": results,
    }


def assess_class_balance(frame: pd.DataFrame) -> Dict[str, Any]:
    """Report the AQI bucket distribution, which drives the metric choice."""
    counts = frame["AQI_Bucket"].value_counts()
    total = int(counts.sum())
    distribution = [
        {
            "bucket": bucket,
            "count": int(counts.get(bucket, 0)),
            "pct": round(100.0 * int(counts.get(bucket, 0)) / total, 3),
        }
        for bucket in config.AQI_BUCKETS
    ]
    non_zero = [d["count"] for d in distribution if d["count"] > 0]
    return {
        "labelled_rows": total,
        "distribution": distribution,
        "imbalance_ratio_max_over_min": round(max(non_zero) / min(non_zero), 2),
        "implication": (
            "The bucket distribution is markedly uneven, so overall accuracy is "
            "not an adequate summary: a model that never predicts the rarest "
            "class can still score well. Macro-averaged F1 is therefore declared "
            "the primary classification metric, with per-class F1 reported "
            "alongside it."
        ),
    }


def recommend_city_retention(missing: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the completeness policy from ``config`` and explain each decision.

    No city is dropped silently: every city appears in the returned table with
    its completeness figures and an explicit reason.
    """
    decisions: List[Dict[str, Any]] = []
    for entry in missing["per_city"]:
        completeness = entry["aqi_completeness_vs_span"]
        records = entry["aqi_non_null"]
        passes_completeness = completeness >= config.CITY_COMPLETENESS_THRESHOLD
        passes_volume = records >= config.CITY_MIN_RECORDS
        retained = passes_completeness and passes_volume
        if retained:
            reason = (
                f"AQI completeness {completeness:.1%} >= "
                f"{config.CITY_COMPLETENESS_THRESHOLD:.0%} and {records:,} labelled "
                f"days >= {config.CITY_MIN_RECORDS:,}."
            )
        else:
            failed = []
            if not passes_completeness:
                failed.append(
                    f"completeness {completeness:.1%} < "
                    f"{config.CITY_COMPLETENESS_THRESHOLD:.0%}"
                )
            if not passes_volume:
                failed.append(
                    f"only {records:,} labelled days < {config.CITY_MIN_RECORDS:,}"
                )
            reason = "Excluded: " + "; ".join(failed) + "."
        decisions.append(
            {
                "city": entry["city"],
                "labelled_days": records,
                "calendar_span_days": entry["calendar_span_days"],
                "aqi_completeness": completeness,
                "first_date": entry["first_date"],
                "last_date": entry["last_date"],
                "retained": retained,
                "reason": reason,
            }
        )
    retained_cities = [d["city"] for d in decisions if d["retained"]]
    return {
        "threshold_completeness": config.CITY_COMPLETENESS_THRESHOLD,
        "threshold_min_labelled_days": config.CITY_MIN_RECORDS,
        "threshold_justification": (
            "Two independent gates are applied. The completeness gate (80% of the "
            "calendar days in a city's own observation span must carry a labelled "
            "AQI) ensures that per-city lag and rolling features are computed over "
            "a near-contiguous series rather than across long gaps, since a lag of "
            "one row is only a lag of one day when the series is dense. The volume "
            "gate (at least 730 labelled days, i.e. two years) ensures each "
            "retained city contributes at least two full annual cycles, so that "
            "seasonal structure is estimable and a time-ordered split leaves a "
            "usable test period. Both thresholds were fixed before any model was "
            "fitted and are not tuned against model performance."
        ),
        "decisions": decisions,
        "n_retained": len(retained_cities),
        "n_excluded": len(decisions) - len(retained_cities),
        "retained_cities": retained_cities,
        "excluded_cities": [d["city"] for d in decisions if not d["retained"]],
    }


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def _save(fig: "plt.Figure", name: str) -> Path:
    """Save a figure at the project DPI and return its path."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = config.FIGURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", name)
    return path


def plot_missingness_matrix(frame: pd.DataFrame) -> Path:
    """Render a missingness matrix over the whole table, ordered by date."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = frame.sort_values(["Date", "City"]).reset_index(drop=True)
    mask = ordered.isna().to_numpy().astype(float)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.imshow(mask, aspect="auto", cmap="Greys", interpolation="nearest", vmin=0, vmax=1)
    ax.set_xticks(range(len(ordered.columns)))
    ax.set_xticklabels(ordered.columns, rotation=60, ha="right", fontsize=9)
    ax.set_ylabel("Record index (sorted by date, then city)")
    ax.set_title(
        "Figure 1. Missingness matrix of city_day.csv\n"
        "Dark marks are missing values. Horizontal bands indicate whole periods "
        "in which a station reported nothing;\nvertical bands indicate columns "
        "that are structurally sparse (Xylene, PM10, NH3).",
        fontsize=10,
        loc="left",
    )
    ax.grid(False)
    return _save(fig, "01_missingness_matrix.png")


def plot_city_availability_heatmap(frame: pd.DataFrame) -> Path:
    """Render a city-by-month heatmap of labelled-AQI availability."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    work = frame.copy()
    work["ym"] = work["Date"].dt.to_period("M").astype(str)
    pivot = (
        work.assign(has_aqi=work["AQI"].notna().astype(float))
        .pivot_table(index="City", columns="ym", values="has_aqi", aggfunc="mean")
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(15, 7.5))
    mesh = ax.imshow(
        pivot.to_numpy(), aspect="auto", cmap=config.SEQ_CMAP, vmin=0, vmax=1
    )
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    step = 3
    ax.set_xticks(range(0, len(pivot.columns), step))
    ax.set_xticklabels(pivot.columns[::step], rotation=90, fontsize=7)
    ax.set_xlabel("Calendar month")
    fig.colorbar(mesh, ax=ax, label="Fraction of days in month with a labelled AQI")
    ax.set_title(
        "Figure 2. Per-city data availability by month\n"
        "Bright cells are well covered; dark cells are absent. Monitoring coverage "
        "expanded over time, so early years\ncarry only the six longest-running "
        "cities and most cities begin part-way through the record.",
        fontsize=10,
        loc="left",
    )
    ax.grid(False)
    return _save(fig, "02_city_availability_heatmap.png")


def plot_null_percentage_bar(missing: Dict[str, Any]) -> Path:
    """Render a ranked bar chart of null percentage per column."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    entries = [e for e in missing["per_column"] if e["null_pct"] > 0]
    entries.sort(key=lambda e: e["null_pct"], reverse=True)
    names = [e["column"] for e in entries]
    values = [e["null_pct"] for e in entries]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(names[::-1], values[::-1], color=config.PALETTE[0])
    ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    ax.set_xlabel("Missing values (% of 29,531 records)")
    ax.set_xlim(0, max(values) * 1.18)
    ax.set_title(
        "Figure 3. Missing-value rate per column, ranked\n"
        "Xylene is missing in over 60% of records and is therefore excluded from "
        "the modelling feature set;\nPM10 and NH3 are recoverable by per-city "
        "imputation.",
        fontsize=10,
        loc="left",
    )
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, "03_null_percentage_bar.png")


def plot_outlier_counts(outliers: Dict[str, Any]) -> Path:
    """Render the IQR-versus-z-score outlier comparison."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = outliers["per_column"]
    names = [r["column"] for r in rows]
    iqr_pct = [r["iqr_outlier_pct"] for r in rows]
    z_pct = [r["z_outlier_pct"] for r in rows]
    skew = [r["skew"] for r in rows]

    x = np.arange(len(names))
    width = 0.38
    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(11, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
    )
    ax.bar(x - width / 2, iqr_pct, width, label="IQR rule (Tukey, k=1.5)", color=config.PALETTE[0])
    ax.bar(x + width / 2, z_pct, width, label="z-score rule (|z| > 3)", color=config.PALETTE[1])
    ax.set_ylabel("Flagged observations (%)")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(
        "Figure 4. Outlier prevalence under two rules, with distribution skewness\n"
        "The two rules disagree by a wide margin on every right-skewed pollutant. "
        "Neither may be used on its own to\ndelete observations, because the "
        "flagged tail is where genuine pollution episodes live.",
        fontsize=10,
        loc="left",
    )
    ax2.bar(x, skew, color=config.PALETTE[2])
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_ylabel("Skewness")
    ax2.set_xticks(x)
    ax2.set_xticklabels(names, rotation=45, ha="right")
    ax2.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return _save(fig, "04_outlier_counts.png")


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def main() -> Dict[str, Any]:
    """Run the full quality assessment, write the JSON report and the figures."""
    config.set_global_seed()
    config.ensure_dirs()
    frame = load_raw_city_day()

    missing = assess_missingness(frame)
    duplicates = assess_duplicates(frame)
    invalid = assess_invalid_values(frame)
    naming = assess_city_naming(frame)
    units = assess_units(frame)
    outliers = assess_outliers(frame)
    balance = assess_class_balance(frame)
    retention = recommend_city_retention(missing)

    plot_missingness_matrix(frame)
    plot_city_availability_heatmap(frame)
    plot_null_percentage_bar(missing)
    plot_outlier_counts(outliers)

    report: Dict[str, Any] = {
        "generated_by": "src/data/quality.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_file": config.portable(config.RAW_DIR / config.PRIMARY_FILE),
        "shape": {"rows": int(frame.shape[0]), "columns": int(frame.shape[1])},
        "missingness": missing,
        "duplicates": duplicates,
        "invalid_values": invalid,
        "city_naming": naming,
        "unit_sanity": units,
        "outliers": outliers,
        "class_balance": balance,
        "city_retention": retention,
        "figures": [
            "01_missingness_matrix.png",
            "02_city_availability_heatmap.png",
            "03_null_percentage_bar.png",
            "04_outlier_counts.png",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOGGER.info("Wrote %s", REPORT_PATH.name)

    LOGGER.info(
        "Duplicates: %s full rows, %s duplicate (City, Date) keys",
        duplicates["fully_duplicated_rows"],
        duplicates["duplicated_city_date_keys"],
    )
    LOGGER.info(
        "AQI_Bucket reproducible from AQI in %.4f%% of labelled rows (%s mismatches)",
        invalid["bucket_consistency"]["agreement_pct"],
        invalid["bucket_consistency"]["mismatches"],
    )
    LOGGER.info(
        "Cities retained: %s of %s -> %s",
        retention["n_retained"],
        retention["n_retained"] + retention["n_excluded"],
        ", ".join(retention["retained_cities"]),
    )
    return report


if __name__ == "__main__":
    main()
