"""Safe-exposure window recommender built from the hourly city record.

Purpose
-------
An advisory that says only "the air is bad today" leaves the reader with no
action. Pollutant concentrations in Indian cities follow a strong and repeatable
diurnal cycle: a shallow nocturnal boundary layer traps emissions and produces an
early-morning particulate peak, mixing deepens through the day, and photochemical
ozone peaks in the afternoon. Knowing *when* within the day exposure is lowest
converts a warning into a plan.

Why the supplied hourly AQI cannot answer this
----------------------------------------------
``city_hour.csv`` carries an ``AQI`` column at hourly resolution, but the CPCB
National AQI is defined on 24-hour averages (and 8-hour averages for CO and
ozone). An hourly AQI is therefore a *rolling* quantity: consecutive hours share
almost all of their input window, so the series is nearly flat within any single
day by construction. Measured on this dataset, the all-year diurnal swing in that
column is under 1 per cent for several cities. It cannot express a diurnal cycle,
and using it for a within-day recommendation would be a category error.

This module therefore computes the climatology twice:

``exposure_index`` (used for the recommendation)
    Hourly concentrations are converted to CPCB sub-indices *instantaneously*,
    without any rolling window, and the maximum across pollutants is taken. The
    result is on the familiar 0-500 scale and is directly comparable in shape to
    the AQI, but it varies within the day because its inputs do. It is labelled
    throughout as a relative within-day exposure indicator, not as the official
    AQI, because the official index is not defined at hourly resolution.

``official_aqi`` (reported for contrast)
    The mean of the supplied hourly ``AQI`` column, retained so that the flatness
    described above is documented by measurement rather than by assertion.

Graceful degradation
--------------------
``city_hour.csv`` is around 66 MB and is streamed in chunks, so the module runs
inside a modest memory budget. If the hourly file is unavailable,
:func:`build_safe_windows` falls back to a monthly seasonal calendar derived from
the daily table, records ``"degraded": True``, and the application and reports
state that the recommendation is seasonal rather than hourly. The fallback is a
documented outcome, not a silent substitution.

Outputs
-------
``results/safe_windows.json``
``reports/figures/10_hourly_exposure_climatology.png``

Run with::

    python -m src.features.safe_window
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src import config
from src.data.clean import CLEAN_PATH
from src.features import hai as hai_mod
from src.features.exposure import choose_window, instantaneous, VERSION as EXPOSURE_VERSION

LOGGER = config.get_logger(__name__)

OUTPUT_PATH = config.RESULTS_DIR / "safe_windows.json"
FIGURE_NAME = "10_hourly_exposure_climatology.png"

#: Length of the recommended outdoor window, in hours.
WINDOW_HOURS: int = 2

#: Chunk size used when streaming the hourly file.
CHUNK_ROWS: int = 200_000

#: Pollutants whose hourly concentrations drive the exposure index.
EXPOSURE_POLLUTANTS: List[str] = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]


def _format_hour(hour: int) -> str:
    """Render an hour of the day as a 12-hour clock label."""
    suffix = "am" if hour % 24 < 12 else "pm"
    display = hour % 12 or 12
    return f"{display} {suffix}"


def format_window(start_hour: int, length: int = WINDOW_HOURS) -> str:
    """Render a window as a human-readable range, e.g. ``"2 pm to 4 pm"``."""
    return f"{_format_hour(start_hour)} to {_format_hour(start_hour + length)}"


# --------------------------------------------------------------------------- #
# Climatology
# --------------------------------------------------------------------------- #
def load_hourly_climatology(cities: List[str]) -> Optional[pd.DataFrame]:
    """Stream ``city_hour.csv`` into a city-by-season-by-hour climatology.

    Parameters
    ----------
    cities:
        Cities to retain; rows for any other city are discarded as they are read,
        which is what keeps the memory footprint small.

    Returns
    -------
    pandas.DataFrame or None
        One row per ``(City, season, hour)`` carrying the mean concentration of
        each exposure pollutant, the mean of the supplied hourly ``AQI`` column,
        and the observation counts behind each. ``None`` if the file is absent.
    """
    path = config.RAW_DIR / config.HOURLY_FILE
    if not path.exists():
        LOGGER.warning("%s not found; hourly climatology unavailable", path.name)
        return None

    keep = set(cities)
    columns = ["City", "Datetime", "AQI"] + EXPOSURE_POLLUTANTS
    sums: Dict[Tuple[str, str, int], Dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    counts: Dict[Tuple[str, str, int], Dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    total_rows = 0

    reader = pd.read_csv(
        path, usecols=columns, parse_dates=["Datetime"], chunksize=CHUNK_ROWS
    )
    for chunk in reader:
        chunk = chunk.loc[chunk["City"].isin(keep)]
        if chunk.empty:
            continue
        total_rows += len(chunk)
        chunk = chunk.assign(
            hour=chunk["Datetime"].dt.hour,
            season=chunk["Datetime"].dt.month.map(config.SEASON_OF_MONTH),
        )
        grouped = chunk.groupby(["City", "season", "hour"], sort=False)
        for measure in EXPOSURE_POLLUTANTS + ["AQI"]:
            aggregated = grouped[measure].agg(["sum", "count"])
            for key, row in aggregated.iterrows():
                sums[key][measure] += float(row["sum"])
                counts[key][measure] += float(row["count"])

    if not sums:
        LOGGER.warning("No usable hourly rows for the retained cities")
        return None

    records: List[Dict[str, Any]] = []
    for key, measures in sums.items():
        city, season, hour = key
        entry: Dict[str, Any] = {"City": city, "season": season, "hour": int(hour)}
        for measure, total in measures.items():
            n = counts[key][measure]
            entry[measure] = total / n if n else np.nan
            entry[f"n_{measure}"] = int(n)
        records.append(entry)

    frame = pd.DataFrame.from_records(records)
    LOGGER.info("Hourly climatology built from %s hourly rows", f"{total_rows:,}")
    return frame


def add_exposure_index(climatology: pd.DataFrame) -> pd.DataFrame:
    """Derive an instantaneous exposure index from the mean hourly concentrations.

    The index is the maximum CPCB sub-index across :data:`EXPOSURE_POLLUTANTS`,
    computed from the hour's mean concentration with no rolling window. It is a
    relative within-day exposure indicator on the 0-500 scale, not the official
    AQI, which is undefined at hourly resolution.
    """
    out = climatology.copy()
    # A city's comparisons use the same pollutant support across seasons.
    # Missing coverage in another city must not change this city's indicator.
    groups = out.groupby('City') if 'City' in out else [(None, out)]
    entries_by_index = {}
    for _, group in groups:
        practical = group.loc[group['hour'].between(6, 20)] if 'hour' in group else group
        common = [p for p in EXPOSURE_POLLUTANTS if p in group and practical[p].notna().all()]
        for index, row in group.iterrows():
            entries_by_index[index] = instantaneous({p:float(row[p]) for p in common})
    entries = [entries_by_index[index] for index in out.index]
    out['exposure_index']=[entry['value'] if entry['qualifier']=='EXACT' else np.nan for entry in entries]
    out['dominant_pollutant']=[entry['dominant'] for entry in entries]
    return out


def best_window(hourly_values: np.ndarray, length: int = WINDOW_HOURS) -> Dict[str, Any]:
    """Return the contiguous window of ``length`` hours with the lowest mean value.

    Shared practical-hours selector: 06:00–21:00 IST, no midnight wrap.
    Windows containing missing or censored hours are skipped.
    """
    window=choose_window(hourly_values.tolist(),length=length)
    if window is None:
        return {"available": False}
    best_start,best_mean=window['start_hour'],window['mean']

    day_mean = float(np.nanmean(hourly_values))
    worst = int(np.nanargmax(hourly_values))
    return {
        "available": True,
        "start_hour": int(best_start),
        "end_hour": int((best_start + length) % 24),
        "label": format_window(int(best_start), length),
        "window_mean": round(best_mean, 2),
        "day_mean": round(day_mean, 2),
        "reduction_vs_day_mean_pct": round(100.0 * (day_mean - best_mean) / day_mean, 2) if day_mean else 0,
        "diurnal_swing_pct": round(
            100.0
            * (float(np.nanmax(hourly_values)) - float(np.nanmin(hourly_values)))
            / (day_mean or 1),
            2,
        ),
        "worst_hour": worst,
        "worst_hour_label": _format_hour(worst),
        "worst_hour_value": round(float(np.nanmax(hourly_values)), 2),
    }


def seasonal_fallback(daily: pd.DataFrame) -> Dict[str, Any]:
    """Build a monthly seasonal calendar when the hourly file is unavailable."""
    work = daily.dropna(subset=["AQI"]).copy()
    work["month"] = work["Date"].dt.month
    table: Dict[str, Any] = {}
    for city, group in work.groupby("City"):
        monthly = group.groupby("month")["AQI"].mean()
        best_month = int(monthly.idxmin())
        table[city] = {
            "monthly_mean_aqi": {int(k): round(float(v), 2) for k, v in monthly.items()},
            "cleanest_month": best_month,
            "cleanest_month_name": pd.Timestamp(2020, best_month, 1).strftime("%B"),
            "cleanest_month_mean_aqi": round(float(monthly.min()), 2),
        }
    return {
        "degraded": True,
        "reason": (
            "city_hour.csv was unavailable, so an hourly recommendation could not "
            "be produced. The recommendation degrades to a monthly seasonal "
            "calendar derived from the daily record. This limitation is stated in "
            "the application and in the reports."
        ),
        "per_city": table,
    }


# --------------------------------------------------------------------------- #
# Figure
# --------------------------------------------------------------------------- #
def plot_hourly_climatology(climatology: pd.DataFrame, payload: Dict[str, Any]) -> Path:
    """Render the diurnal exposure cycle per season for six cities, with contrast."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    counts = climatology.groupby("City")["n_AQI"].sum().sort_values(ascending=False)
    cities = counts.head(6).index.tolist()

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True)
    for ax, city in zip(axes.ravel(), cities):
        subset = climatology.loc[climatology["City"] == city]
        for idx, season in enumerate(config.SEASON_ORDER):
            series = (
                subset.loc[subset["season"] == season]
                .sort_values("hour")
                .set_index("hour")["exposure_index"]
                .reindex(range(24))
            )
            ax.plot(
                series.index, series.to_numpy(), color=config.PALETTE[idx],
                linewidth=1.9, label=season,
            )

        official = (
            subset.groupby("hour")
            .apply(lambda g: np.average(g["AQI"], weights=g["n_AQI"]), include_groups=False)
            .reindex(range(24))
        )
        ax.plot(
            official.index, official.to_numpy(), color="black", linewidth=1.6,
            linestyle=":", label="Supplied hourly AQI (24-h rolling)",
        )

        entry = payload["per_city"].get(city, {}).get("all_year", {})
        if entry.get("available"):
            ax.axvspan(
                entry["start_hour"], entry["start_hour"] + WINDOW_HOURS,
                color=config.PALETTE[2], alpha=0.18,
                label=f"Safest window ({entry['label']})",
            )
        swing = entry.get("diurnal_swing_pct", 0.0)
        ax.set_title(f"{city}   diurnal swing {swing:.0f}% of the daily mean", fontsize=10.5)
        ax.set_xticks(range(0, 24, 3))
        ax.set_xlim(0, 23)
        ax.grid(alpha=0.25, linewidth=0.5)
        ax.spines[["top", "right"]].set_visible(False)

    for ax in axes[1, :]:
        ax.set_xlabel("Hour of day")
    for ax in axes[:, 0]:
        ax.set_ylabel("Exposure index (0-500)")

    handles, labels = axes[0, 0].get_legend_handles_labels()
    seen: Dict[str, Any] = {}
    for handle, label in zip(handles, labels):
        seen.setdefault(label.split(" (")[0], handle)
    fig.legend(
        list(seen.values()), list(seen.keys()), loc="lower center", ncol=6,
        frameon=False, bbox_to_anchor=(0.5, -0.02), fontsize=9,
    )
    fig.suptitle(
        "Figure 10. Diurnal exposure cycle by season, with the recommended two-hour "
        "outdoor window shaded\n"
        "The dotted line is the supplied hourly AQI column: it is nearly flat "
        "because it is a 24-hour rolling quantity, which is\nprecisely why the "
        "recommendation is computed from instantaneous hourly concentrations instead.",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.91))
    path = config.FIGURES_DIR / FIGURE_NAME
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", FIGURE_NAME)
    return path


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def build_safe_windows() -> Dict[str, Any]:
    """Compute per-city and per-season safest outdoor windows."""
    config.set_global_seed()
    config.ensure_dirs()

    daily = pd.read_csv(CLEAN_PATH, parse_dates=["Date"])
    cities = sorted(daily["City"].unique().tolist())

    climatology = load_hourly_climatology(cities)
    if climatology is None:
        result = seasonal_fallback(daily)
        result["generated_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
        LOGGER.warning("Wrote %s in degraded (seasonal) mode", OUTPUT_PATH.name)
        return result

    climatology = add_exposure_index(climatology)

    per_city: Dict[str, Any] = {}
    official_swings: List[float] = []
    exposure_swings: List[float] = []

    for city in cities:
        subset = climatology.loc[climatology["City"] == city]
        if subset.empty:
            continue

        weighted = (
            subset.groupby("hour")
            .apply(
                lambda g: pd.Series(
                    {
                        "exposure_index": np.average(
                            g["exposure_index"], weights=g["n_AQI"].clip(lower=1)
                        ),
                        "official_aqi": np.average(g["AQI"], weights=g["n_AQI"].clip(lower=1)),
                    }
                ),
                include_groups=False,
            )
            .reindex(range(24))
        )
        exposure = weighted["exposure_index"].to_numpy(dtype=float)
        official = weighted["official_aqi"].to_numpy(dtype=float)

        entry: Dict[str, Any] = {"all_year": best_window(exposure)}
        entry["official_aqi_all_year"] = best_window(official)
        entry["hourly_exposure_index"] = [
            None if np.isnan(v) else round(float(v), 2) for v in exposure
        ]
        entry["hourly_official_aqi"] = [
            None if np.isnan(v) else round(float(v), 2) for v in official
        ]

        by_season: Dict[str, Any] = {}
        for season in config.SEASON_ORDER:
            seasonal = (
                subset.loc[subset["season"] == season]
                .sort_values("hour")
                .set_index("hour")["exposure_index"]
                .reindex(range(24))
                .to_numpy(dtype=float)
            )
            if np.isnan(seasonal).all():
                continue
            window = best_window(seasonal)
            window["hourly_exposure_index"] = [
                None if np.isnan(v) else round(float(v), 2) for v in seasonal
            ]
            dominant = (
                subset.loc[subset["season"] == season]
                .sort_values("hour")
                .set_index("hour")["dominant_pollutant"]
                .reindex(range(24))
            )
            if window.get("available"):
                hours = [
                    (window["start_hour"] + offset) % 24 for offset in range(WINDOW_HOURS)
                ]
                values = dominant.loc[hours].dropna()
                window["dominant_pollutant_in_window"] = (
                    values.mode().iloc[0] if not values.empty else None
                )
            by_season[season] = window
        entry["by_season"] = by_season
        entry["n_hourly_observations"] = int(subset["n_AQI"].sum())
        per_city[city] = entry

        if entry["all_year"].get("available"):
            exposure_swings.append(entry["all_year"]["diurnal_swing_pct"])
        if entry["official_aqi_all_year"].get("available"):
            official_swings.append(entry["official_aqi_all_year"]["diurnal_swing_pct"])

    result: Dict[str, Any] = {
        "generated_by": "src/features/safe_window.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "degraded": False,
        "source": str(config.RAW_DIR / config.HOURLY_FILE),
        "window_hours": WINDOW_HOURS,
        "exposure_methodology_version": EXPOSURE_VERSION,
        "practical_hours_ist": [6,21],
        "exposure_pollutants": EXPOSURE_POLLUTANTS,
        "method": (
            "Hourly concentrations are averaged by city, season and hour of day, "
            "converted to CPCB sub-indices instantaneously (no rolling window), "
            "and the maximum across pollutants is taken as an exposure index on "
            "closed index scale, excluding censored Severe hours. The recommended window is the contiguous two-hour "
            "block with the lowest mean within 06:00–21:00 IST, without "
            "midnight wrap. The index is a relative within-day exposure indicator, not "
            "the official AQI, which is defined only on 24-hour (and 8-hour) "
            "averages and is therefore undefined at hourly resolution."
        ),
        "why_not_the_supplied_hourly_aqi": {
            "mean_diurnal_swing_supplied_aqi_pct": round(float(np.mean(official_swings)), 2)
            if official_swings
            else None,
            "mean_diurnal_swing_exposure_index_pct": round(float(np.mean(exposure_swings)), 2)
            if exposure_swings
            else None,
            "explanation": (
                "The supplied hourly AQI is a 24-hour rolling quantity, so "
                "consecutive hours share almost all of their input window and the "
                "series is nearly flat within a day by construction. The measured "
                "diurnal swings above quantify the difference and justify building "
                "the recommendation on instantaneous concentrations instead."
            ),
        },
        "seasons": config.SEASON_ORDER,
        "per_city": per_city,
    }

    plot_hourly_climatology(climatology, result)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    LOGGER.info(
        "Wrote %s for %s cities | mean diurnal swing: exposure index %.1f%% vs "
        "supplied AQI %.1f%%",
        OUTPUT_PATH.name,
        len(per_city),
        float(np.mean(exposure_swings)) if exposure_swings else float("nan"),
        float(np.mean(official_swings)) if official_swings else float("nan"),
    )
    return result


def lookup_window(
    city: str, season: Optional[str] = None, payload: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """Return the formatted safest window for a city, with graceful fallback.

    Resolution order: the season-specific window, then the city's all-year
    window, then the degraded seasonal calendar, then ``None``.
    """
    payload = payload or json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    entry = payload.get("per_city", {}).get(city)
    if entry is None:
        return None
    if payload.get("degraded"):
        return f"cleanest month: {entry.get('cleanest_month_name')}"
    if season and season in entry.get("by_season", {}):
        window = entry["by_season"][season]
        if window.get("available"):
            return window["label"]
    window = entry.get("all_year", {})
    return window["label"] if window.get("available") else None


def main() -> Dict[str, Any]:
    """Entry point."""
    return build_safe_windows()


if __name__ == "__main__":
    main()
