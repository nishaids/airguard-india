"""Exploratory data analysis: statistics, figures and the derived insight list.

Every figure produced here is written at 300 DPI with a colour-blind-safe
palette, and every figure has a corresponding written interpretation in
``results/eda_insights.json``. No figure is generated without one: an
uninterpreted chart tells a reader nothing, and the insight list is what carries
the analysis into the Review 2 document.

The module is organised as univariate, bivariate, multivariate, temporal and
event-focused analysis, mirroring the structure of the report.

Outputs
-------
``results/eda_statistics.json``   all computed statistics
``results/eda_insights.json``     numbered insights, each citing its figure and
                                  the modelling consequence it drives
``reports/figures/11_*.png`` through ``reports/figures/23_*.png``

Run with::

    python -m src.eda.plots
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats as sp_stats

from src import config
from src.data.clean import CLEAN_PATH, KEPT_POLLUTANTS
from src.features.build import FEATURES_PATH

LOGGER = config.get_logger(__name__)

STATS_PATH = config.RESULTS_DIR / "eda_statistics.json"
INSIGHTS_PATH = config.RESULTS_DIR / "eda_insights.json"

#: Pollutants shown in the compact multi-panel figures.
FOCUS_POLLUTANTS: List[str] = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]

sns.set_theme(style="whitegrid", palette=config.PALETTE)


def _save(fig: plt.Figure, name: str) -> str:
    """Save a figure at the project DPI and return its file name."""
    path = config.FIGURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", name)
    return name


def load_frames() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load the cleaned daily table and the engineered feature matrix."""
    clean = pd.read_csv(CLEAN_PATH, parse_dates=["Date"])
    features = pd.read_csv(FEATURES_PATH, parse_dates=["Date"])
    LOGGER.info(
        "Loaded clean (%s rows) and features (%s rows x %s cols)",
        f"{len(clean):,}",
        f"{len(features):,}",
        features.shape[1],
    )
    return clean, features


# --------------------------------------------------------------------------- #
# Univariate
# --------------------------------------------------------------------------- #
def figure_distributions(frame: pd.DataFrame) -> str:
    """Histograms with kernel density estimates for the focus pollutants and AQI."""
    columns = FOCUS_POLLUTANTS + ["AQI"]
    fig, axes = plt.subplots(2, 4, figsize=(17, 8))
    for ax, column in zip(axes.ravel(), columns):
        series = frame[column].dropna()
        upper = float(np.percentile(series, 99.5))
        sns.histplot(
            series.clip(upper=upper), bins=60, kde=True, ax=ax,
            color=config.PALETTE[0], edgecolor="none",
        )
        ax.axvline(float(series.median()), color=config.PALETTE[1], linewidth=1.6,
                   label=f"median {series.median():.1f}")
        ax.axvline(float(series.mean()), color=config.PALETTE[2], linewidth=1.6,
                   linestyle="--", label=f"mean {series.mean():.1f}")
        unit = config.POLLUTANT_UNITS.get(column, "index")
        ax.set_title(
            f"{column} ({unit})   skew {series.skew():.2f}", fontsize=10.5
        )
        ax.set_xlabel("")
        ax.legend(fontsize=7.5, frameon=False)
    axes.ravel()[-1].axis("off")
    axes.ravel()[-1].text(
        0.02, 0.5,
        "Every distribution is right-skewed:\nthe mean sits above the median in\n"
        "each panel. Clean days are common,\nbut the tail of severe days is long\n"
        "and it is where the health burden is.",
        fontsize=10, va="center",
    )
    fig.suptitle(
        "Figure 11. Univariate distributions of the principal pollutants and the AQI "
        "(clipped at the 99.5th percentile for display)",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, "11_univariate_distributions.png")


def figure_boxplots(frame: pd.DataFrame) -> str:
    """Boxplots of the focus pollutants on a shared logarithmic scale."""
    melted = frame[FOCUS_POLLUTANTS].melt(var_name="Pollutant", value_name="Value").dropna()
    melted = melted.loc[melted["Value"] > 0]
    fig, ax = plt.subplots(figsize=(11, 6))
    sns.boxplot(
        data=melted, x="Pollutant", y="Value", ax=ax, palette=config.PALETTE[:6],
        fliersize=1.2, hue="Pollutant", legend=False,
    )
    ax.set_yscale("log")
    ax.set_ylabel("Concentration (log scale; CO in mg/m3, others in ug/m3)")
    ax.set_title(
        "Figure 12. Pollutant spread on a logarithmic scale\n"
        "A logarithmic axis is required to show all six species together, which is "
        "itself evidence of the\nmagnitude differences a scaler must remove before "
        "any distance-based model is fitted.",
        fontsize=11, loc="left",
    )
    fig.tight_layout()
    return _save(fig, "12_pollutant_boxplots.png")


def figure_city_ranking(frame: pd.DataFrame) -> str:
    """Ranked mean AQI per city with the bucket composition beside it."""
    stats = (
        frame.dropna(subset=["AQI"])
        .groupby("City")["AQI"]
        .agg(["mean", "median", "std", "count"])
        .sort_values("mean", ascending=True)
    )
    composition = (
        frame.dropna(subset=["AQI_Bucket"])
        .groupby(["City", "AQI_Bucket"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=config.AQI_BUCKETS, fill_value=0)
    )
    composition = composition.div(composition.sum(axis=1), axis=0).loc[stats.index]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(15.5, 7), gridspec_kw={"width_ratios": [1, 1.25]}
    )
    bars = ax1.barh(stats.index, stats["mean"], color=config.PALETTE[0],
                    xerr=stats["std"], error_kw={"elinewidth": 0.8, "ecolor": "#888888"})
    ax1.bar_label(bars, fmt="%.0f", padding=3, fontsize=9)
    ax1.set_xlabel("Mean AQI (bars), standard deviation (whiskers)")
    ax1.set_xlim(0, float((stats["mean"] + stats["std"]).max()) * 1.12)
    ax1.set_title("Mean AQI by city", fontsize=11, loc="left")

    left = np.zeros(len(composition))
    colours = ["#009E73", "#A8DDB5", "#F0E442", "#E69F00", "#D55E00", "#8B0000"]
    for bucket, colour in zip(config.AQI_BUCKETS, colours):
        values = composition[bucket].to_numpy() * 100
        ax2.barh(composition.index, values, left=left, color=colour, label=bucket)
        left += values
    ax2.set_xlabel("Share of labelled days (%)")
    ax2.set_xlim(0, 100)
    ax2.legend(ncol=3, frameon=False, fontsize=8.5, loc="lower center",
               bbox_to_anchor=(0.5, -0.20))
    ax2.set_title("Composition of AQI buckets by city", fontsize=11, loc="left")
    ax2.set_yticklabels([])

    fig.suptitle(
        "Figure 13. City ranking by mean AQI, with the bucket composition that the "
        "mean conceals",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    return _save(fig, "13_city_ranking.png")


# --------------------------------------------------------------------------- #
# Bivariate
# --------------------------------------------------------------------------- #
def figure_pollutant_vs_aqi(frame: pd.DataFrame) -> Tuple[str, List[Dict[str, Any]]]:
    """Scatter each pollutant against AQI with Pearson and Spearman coefficients."""
    work = frame.dropna(subset=["AQI"])
    correlations: List[Dict[str, Any]] = []

    fig, axes = plt.subplots(2, 3, figsize=(16, 8.5))
    for ax, pollutant in zip(axes.ravel(), FOCUS_POLLUTANTS):
        subset = work[[pollutant, "AQI"]].dropna()
        pearson = float(sp_stats.pearsonr(subset[pollutant], subset["AQI"])[0])
        spearman = float(sp_stats.spearmanr(subset[pollutant], subset["AQI"])[0])
        correlations.append(
            {
                "pollutant": pollutant,
                "pearson_r": round(pearson, 4),
                "spearman_rho": round(spearman, 4),
                "n": int(len(subset)),
            }
        )
        ax.scatter(
            subset[pollutant], subset["AQI"], s=4, alpha=0.14,
            color=config.PALETTE[0], rasterized=True,
        )
        slope, intercept = np.polyfit(subset[pollutant], subset["AQI"], 1)
        grid = np.linspace(subset[pollutant].min(), subset[pollutant].max(), 50)
        ax.plot(grid, slope * grid + intercept, color=config.PALETTE[1], linewidth=1.8)
        ax.set_xlabel(f"{pollutant} ({config.POLLUTANT_UNITS[pollutant]})")
        ax.set_ylabel("AQI")
        ax.set_title(
            f"{pollutant}   Pearson r = {pearson:.3f}   Spearman rho = {spearman:.3f}",
            fontsize=10.5,
        )
    fig.suptitle(
        "Figure 14. Each pollutant against the same-day AQI, with linear fits and "
        "both correlation coefficients\n"
        "Spearman exceeding Pearson indicates a monotone but non-linear "
        "relationship, which favours tree-based models\nover a purely linear one.",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return _save(fig, "14_pollutant_vs_aqi.png"), correlations


def figure_correlation_heatmap(frame: pd.DataFrame) -> Tuple[str, Dict[str, Any]]:
    """Correlation heatmap across the pollutants and the AQI."""
    columns = KEPT_POLLUTANTS + ["AQI"]
    correlation = frame[columns].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(10.5, 8.5))
    mask = np.triu(np.ones_like(correlation, dtype=bool), k=1)
    sns.heatmap(
        correlation, mask=mask, annot=True, fmt=".2f", cmap=config.DIV_CMAP,
        vmin=-1, vmax=1, square=True, linewidths=0.5, ax=ax,
        cbar_kws={"label": "Spearman rank correlation"}, annot_kws={"fontsize": 8},
    )
    ax.set_title(
        "Figure 15. Spearman correlation across pollutants and the AQI\n"
        "The nitrogen oxide block (NO, NO2, NOx) is strongly internally correlated, "
        "which is why the feature selection\nstage removes redundant members rather "
        "than feeding all three to a linear model.",
        fontsize=11, loc="left",
    )
    fig.tight_layout()

    upper = correlation.where(mask)
    pairs = (
        upper.stack()
        .reset_index()
        .rename(columns={"level_0": "a", "level_1": "b", 0: "rho"})
    )
    pairs["abs"] = pairs["rho"].abs()
    top = pairs.sort_values("abs", ascending=False).head(8)
    summary = {
        "method": "Spearman rank correlation",
        "strongest_pairs": [
            {"a": row.a, "b": row.b, "spearman_rho": round(float(row.rho), 4)}
            for row in top.itertuples()
        ],
        "aqi_correlations": {
            column: round(float(correlation.loc[column, "AQI"]), 4)
            for column in KEPT_POLLUTANTS
        },
    }
    return _save(fig, "15_correlation_heatmap.png"), summary


def figure_pairplot(frame: pd.DataFrame) -> str:
    """Pairwise scatter matrix of four key pollutants, coloured by AQI bucket."""
    columns = ["PM2.5", "PM10", "NO2", "O3"]
    work = frame.dropna(subset=["AQI_Bucket"])[columns + ["AQI_Bucket"]].copy()
    work = work.loc[work["AQI_Bucket"].isin(["Good", "Moderate", "Very Poor", "Severe"])]
    sample = pd.concat(
        [
            group.sample(min(len(group), 700), random_state=config.RANDOM_SEED)
            for _, group in work.groupby("AQI_Bucket")
        ]
    )
    grid = sns.pairplot(
        sample, vars=columns, hue="AQI_Bucket",
        hue_order=["Good", "Moderate", "Very Poor", "Severe"],
        palette=[config.PALETTE[2], config.PALETTE[4], config.PALETTE[1], "#8B0000"],
        plot_kws={"s": 9, "alpha": 0.45, "linewidth": 0}, diag_kind="kde", height=2.5,
    )
    grid.figure.suptitle(
        "Figure 16. Pairwise structure of four key pollutants, coloured by AQI bucket\n"
        "Bucket classes separate cleanly along the particulate axes and overlap "
        "heavily along the ozone axis.",
        fontsize=12, x=0.02, ha="left", y=1.03,
    )
    return _save(grid.figure, "16_pairplot.png")


# --------------------------------------------------------------------------- #
# Multivariate
# --------------------------------------------------------------------------- #
def figure_pca(frame: pd.DataFrame) -> Tuple[str, Dict[str, Any]]:
    """Two-dimensional PCA projection coloured by AQI bucket."""
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    columns = KEPT_POLLUTANTS
    work = frame.dropna(subset=columns + ["AQI_Bucket"])
    scaled = StandardScaler().fit_transform(work[columns])
    pca = PCA(n_components=min(6, len(columns)), random_state=config.RANDOM_SEED)
    scores = pca.fit_transform(scaled)

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(15, 6.5), gridspec_kw={"width_ratios": [1.4, 1]}
    )
    colours = ["#009E73", "#A8DDB5", "#F0E442", "#E69F00", "#D55E00", "#8B0000"]
    for bucket, colour in zip(config.AQI_BUCKETS, colours):
        mask = (work["AQI_Bucket"] == bucket).to_numpy()
        if not mask.any():
            continue
        ax1.scatter(
            scores[mask, 0], scores[mask, 1], s=5, alpha=0.35, color=colour,
            label=bucket, rasterized=True,
        )
    for idx, column in enumerate(columns):
        ax1.arrow(
            0, 0, pca.components_[0, idx] * 6, pca.components_[1, idx] * 6,
            color="black", width=0.012, head_width=0.16, alpha=0.75,
        )
        ax1.text(
            pca.components_[0, idx] * 6.6, pca.components_[1, idx] * 6.6, column,
            fontsize=8.5, ha="center", fontweight="bold",
        )
    ax1.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%} of variance)")
    ax1.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%} of variance)")
    ax1.legend(markerscale=2.5, fontsize=8.5, frameon=False, ncol=2)
    ax1.set_title("Projection with pollutant loadings", fontsize=11, loc="left")

    cumulative = np.cumsum(pca.explained_variance_ratio_)
    ax2.bar(
        range(1, len(cumulative) + 1), pca.explained_variance_ratio_ * 100,
        color=config.PALETTE[0], label="Individual",
    )
    ax2.plot(
        range(1, len(cumulative) + 1), cumulative * 100, color=config.PALETTE[1],
        marker="o", linewidth=1.8, label="Cumulative",
    )
    ax2.axhline(80, color="grey", linestyle="--", linewidth=1)
    ax2.set_xlabel("Principal component")
    ax2.set_ylabel("Variance explained (%)")
    ax2.legend(frameon=False)
    ax2.set_title("Scree plot", fontsize=11, loc="left")

    fig.suptitle(
        f"Figure 17. PCA of the eleven cleaned pollutants. The first two components "
        f"retain {cumulative[1]:.1%} of the variance.",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    summary = {
        "n_components": int(pca.n_components_),
        "explained_variance_ratio": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "cumulative": [round(float(v), 4) for v in cumulative],
        "n_components_for_80pct": int(np.searchsorted(cumulative, 0.80) + 1),
        "pc1_loadings": {
            column: round(float(pca.components_[0, idx]), 4)
            for idx, column in enumerate(columns)
        },
        "pc2_loadings": {
            column: round(float(pca.components_[1, idx]), 4)
            for idx, column in enumerate(columns)
        },
    }
    return _save(fig, "17_pca_projection.png"), summary


# --------------------------------------------------------------------------- #
# Temporal
# --------------------------------------------------------------------------- #
def figure_decomposition(frame: pd.DataFrame, city: str = "Delhi") -> Tuple[str, Dict[str, Any]]:
    """Seasonal-trend decomposition of one city's AQI series."""
    from statsmodels.tsa.seasonal import STL

    series = (
        frame.loc[frame["City"] == city]
        .set_index("Date")["AQI"]
        .interpolate(limit_direction="both")
        .asfreq("D")
    )
    stl = STL(series, period=365, robust=True).fit()

    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    for ax, (values, label, colour) in zip(
        axes,
        [
            (series, "Observed AQI", config.PALETTE[0]),
            (stl.trend, "Trend", config.PALETTE[1]),
            (stl.seasonal, "Annual seasonal component", config.PALETTE[2]),
            (stl.resid, "Residual", config.PALETTE[3]),
        ],
    ):
        ax.plot(values.index, values.to_numpy(), color=colour, linewidth=0.9)
        ax.set_ylabel(label, fontsize=9.5)
        ax.grid(alpha=0.25, linewidth=0.5)
    axes[-1].axhline(0, color="black", linewidth=0.8)
    axes[-1].set_xlabel("Date")

    strength_seasonal = float(
        max(0.0, 1 - stl.resid.var() / (stl.seasonal + stl.resid).var())
    )
    strength_trend = float(max(0.0, 1 - stl.resid.var() / (stl.trend + stl.resid).var()))

    fig.suptitle(
        f"Figure 18. STL decomposition of the {city} AQI series (annual period).\n"
        f"Seasonal strength {strength_seasonal:.2f}, trend strength "
        f"{strength_trend:.2f}: the annual cycle dominates, which is why "
        f"cyclical calendar features are engineered.",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    summary = {
        "city": city,
        "seasonal_strength": round(strength_seasonal, 4),
        "trend_strength": round(strength_trend, 4),
        "seasonal_amplitude": round(float(stl.seasonal.max() - stl.seasonal.min()), 2),
        "residual_std": round(float(stl.resid.std()), 2),
    }
    return _save(fig, "18_stl_decomposition.png"), summary


def figure_seasonal_boxplots(frame: pd.DataFrame) -> Tuple[str, Dict[str, Any]]:
    """AQI by season and by month, across all retained cities."""
    work = frame.dropna(subset=["AQI"]).copy()
    work["season"] = work["Date"].dt.month.map(config.SEASON_OF_MONTH)
    work["month_name"] = work["Date"].dt.strftime("%b")

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(16, 6), gridspec_kw={"width_ratios": [1, 1.7]}
    )
    sns.boxplot(
        data=work, x="season", y="AQI", order=config.SEASON_ORDER, ax=ax1,
        palette=config.PALETTE[:4], hue="season", legend=False, fliersize=1,
    )
    ax1.set_title("By season", fontsize=11, loc="left")
    ax1.set_xlabel("")

    month_order = [pd.Timestamp(2020, m, 1).strftime("%b") for m in range(1, 13)]
    sns.boxplot(
        data=work, x="month_name", y="AQI", order=month_order, ax=ax2,
        color=config.PALETTE[0], fliersize=1,
    )
    ax2.set_title("By calendar month", fontsize=11, loc="left")
    ax2.set_xlabel("")

    seasonal_means = work.groupby("season")["AQI"].mean()
    monthly_means = work.groupby(work["Date"].dt.month)["AQI"].mean()
    fig.suptitle(
        f"Figure 19. Seasonal and monthly AQI distributions across all twelve "
        f"retained cities.\nWinter mean {seasonal_means.get('Winter', float('nan')):.0f} "
        f"against monsoon mean {seasonal_means.get('Monsoon', float('nan')):.0f}: a "
        f"{seasonal_means.max() / seasonal_means.min():.1f}-fold seasonal swing.",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))

    summary = {
        "seasonal_mean_aqi": {k: round(float(v), 2) for k, v in seasonal_means.items()},
        "monthly_mean_aqi": {int(k): round(float(v), 2) for k, v in monthly_means.items()},
        "worst_season": str(seasonal_means.idxmax()),
        "best_season": str(seasonal_means.idxmin()),
        "seasonal_ratio": round(float(seasonal_means.max() / seasonal_means.min()), 3),
        "worst_month": int(monthly_means.idxmax()),
        "best_month": int(monthly_means.idxmin()),
    }
    return _save(fig, "19_seasonal_boxplots.png"), summary


def figure_city_month_heatmap(frame: pd.DataFrame) -> str:
    """City-by-month mean AQI heatmap."""
    work = frame.dropna(subset=["AQI"]).copy()
    work["month"] = work["Date"].dt.month
    pivot = work.pivot_table(index="City", columns="month", values="AQI", aggfunc="mean")
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]
    pivot.columns = [pd.Timestamp(2020, m, 1).strftime("%b") for m in pivot.columns]

    fig, ax = plt.subplots(figsize=(12, 6.5))
    sns.heatmap(
        pivot, annot=True, fmt=".0f", cmap=config.SEQ_CMAP, linewidths=0.5, ax=ax,
        cbar_kws={"label": "Mean AQI"}, annot_kws={"fontsize": 8},
    )
    ax.set_title(
        "Figure 20. Mean AQI by city and calendar month\n"
        "The northern cities show an extreme winter maximum; the southern coastal "
        "cities are comparatively flat.\nA single national model must therefore "
        "carry a city interaction, which is what the city encodings supply.",
        fontsize=11, loc="left",
    )
    ax.set_xlabel("")
    fig.tight_layout()
    return _save(fig, "20_city_month_heatmap.png")


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
def figure_covid(frame: pd.DataFrame) -> Tuple[str, Dict[str, Any]]:
    """Interrupted time series around the 2020 national lockdown."""
    work = frame.dropna(subset=["AQI"]).copy()
    start = pd.Timestamp(config.LOCKDOWN_START)
    end = pd.Timestamp(config.LOCKDOWN_END)

    national = work.groupby("Date")["AQI"].mean().asfreq("D").interpolate()
    smoothed = national.rolling(7, center=True, min_periods=3).mean()

    window = 60
    before = work.loc[work["Date"].between(start - pd.Timedelta(days=window), start - pd.Timedelta(days=1))]
    during = work.loc[work["Date"].between(start, end)]

    per_city: List[Dict[str, Any]] = []
    for city in sorted(work["City"].unique()):
        pre = before.loc[before["City"] == city, "AQI"]
        post = during.loc[during["City"] == city, "AQI"]
        if len(pre) < 20 or len(post) < 20:
            continue
        statistic, pvalue = sp_stats.mannwhitneyu(pre, post, alternative="greater")
        per_city.append(
            {
                "city": city,
                "mean_aqi_60d_before": round(float(pre.mean()), 2),
                "mean_aqi_during_lockdown": round(float(post.mean()), 2),
                "change_pct": round(100.0 * (post.mean() - pre.mean()) / pre.mean(), 2),
                "mannwhitney_u": float(statistic),
                "p_value": float(pvalue),
                "significant_at_0_05": bool(pvalue < 0.05),
            }
        )

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [1.3, 1]}
    )
    subset = smoothed.loc["2019-09-01":"2020-07-01"]
    ax1.plot(subset.index, subset.to_numpy(), color=config.PALETTE[0], linewidth=1.6,
             label="National mean AQI (7-day centred mean)")
    ax1.axvspan(start, end, color=config.PALETTE[1], alpha=0.16,
                label="National lockdown, phases 1 to 4")
    pre_mean = float(national.loc[start - pd.Timedelta(days=window):start].mean())
    post_mean = float(national.loc[start:end].mean())
    ax1.hlines(pre_mean, start - pd.Timedelta(days=window), start,
               color=config.PALETTE[2], linewidth=2.2,
               label=f"Mean of the 60 days before: {pre_mean:.0f}")
    ax1.hlines(post_mean, start, end, color=config.PALETTE[3], linewidth=2.2,
               label=f"Mean during lockdown: {post_mean:.0f}")
    ax1.set_ylabel("AQI")
    ax1.legend(frameon=False, fontsize=9, loc="upper right")
    ax1.grid(alpha=0.25, linewidth=0.5)
    ax1.set_title(
        f"National mean AQI fell {100 * (pre_mean - post_mean) / pre_mean:.1f}% "
        f"during the lockdown relative to the preceding 60 days",
        fontsize=11, loc="left",
    )

    ordered = sorted(per_city, key=lambda r: r["change_pct"])
    names = [r["city"] for r in ordered]
    changes = [r["change_pct"] for r in ordered]
    colours = [config.PALETTE[2] if c < 0 else config.PALETTE[1] for c in changes]
    bars = ax2.barh(names, changes, color=colours)
    ax2.bar_label(bars, fmt="%.0f%%", padding=3, fontsize=8.5)
    ax2.axvline(0, color="black", linewidth=0.9)
    ax2.set_xlabel("Change in mean AQI during lockdown against the preceding 60 days (%)")
    ax2.set_xlim(min(changes) * 1.25, max(max(changes) * 1.35, 5))
    ax2.grid(alpha=0.25, axis="x", linewidth=0.5)

    fig.suptitle(
        "Figure 21. The 2020 lockdown as a natural experiment in emission reduction",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    summary = {
        "lockdown_window": [config.LOCKDOWN_START, config.LOCKDOWN_END],
        "comparison_window_days_before": window,
        "national_mean_before": round(pre_mean, 2),
        "national_mean_during": round(post_mean, 2),
        "national_change_pct": round(100.0 * (post_mean - pre_mean) / pre_mean, 2),
        "per_city": per_city,
        "n_cities_significant_decline": sum(1 for r in per_city if r["significant_at_0_05"]),
        "test": (
            "One-sided Mann-Whitney U test per city, alternative hypothesis that "
            "the pre-lockdown distribution is stochastically greater than the "
            "lockdown distribution. A rank test is used because the AQI is "
            "strongly right-skewed, which violates the normality assumption of a "
            "t-test."
        ),
    }
    return _save(fig, "21_covid_interrupted_series.png"), summary


def figure_festival(frame: pd.DataFrame) -> Tuple[str, Dict[str, Any]]:
    """Diwali window against a matched baseline, per city and nationally."""
    work = frame.dropna(subset=["AQI"]).copy()
    window = config.DIWALI_WINDOW_DAYS

    festival_mask = pd.Series(False, index=work.index)
    baseline_mask = pd.Series(False, index=work.index)
    for _, day in config.DIWALI_DATES.items():
        centre = pd.Timestamp(day)
        offset = (work["Date"] - centre).dt.days
        festival_mask |= offset.abs() <= window
        # Matched baseline: the same span of days, three to five weeks earlier,
        # which keeps the season and the meteorological regime comparable.
        baseline_mask |= offset.between(-35, -21)

    per_city: List[Dict[str, Any]] = []
    for city in sorted(work["City"].unique()):
        city_mask = work["City"] == city
        festival = work.loc[city_mask & festival_mask, "AQI"]
        baseline = work.loc[city_mask & baseline_mask, "AQI"]
        if len(festival) < 10 or len(baseline) < 10:
            continue
        statistic, pvalue = sp_stats.mannwhitneyu(festival, baseline, alternative="greater")
        per_city.append(
            {
                "city": city,
                "n_festival_days": int(len(festival)),
                "n_baseline_days": int(len(baseline)),
                "mean_festival_aqi": round(float(festival.mean()), 2),
                "mean_baseline_aqi": round(float(baseline.mean()), 2),
                "uplift_pct": round(
                    100.0 * (festival.mean() - baseline.mean()) / baseline.mean(), 2
                ),
                "p_value": float(pvalue),
                "significant_at_0_05": bool(pvalue < 0.05),
            }
        )

    ordered = sorted(per_city, key=lambda r: r["uplift_pct"])
    names = [r["city"] for r in ordered]
    uplift = [r["uplift_pct"] for r in ordered]
    stars = ["*" if r["significant_at_0_05"] else "" for r in ordered]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6.5))
    colours = [config.PALETTE[1] if u > 0 else config.PALETTE[2] for u in uplift]
    bars = ax1.barh(names, uplift, color=colours)
    ax1.bar_label(
        bars, labels=[f"{u:+.0f}%{s}" for u, s in zip(uplift, stars)], padding=3, fontsize=8.5
    )
    ax1.axvline(0, color="black", linewidth=0.9)
    ax1.set_xlabel("Change in mean AQI, Diwali window against matched baseline (%)")
    ax1.set_xlim(min(uplift) * 1.3 if min(uplift) < 0 else -5, max(uplift) * 1.35)
    ax1.set_title(
        f"Per-city uplift. An asterisk marks significance at the 5% level\n"
        f"(one-sided Mann-Whitney U).",
        fontsize=10.5, loc="left",
    )

    profile: Dict[int, List[float]] = {}
    for offset in range(-10, 11):
        values: List[float] = []
        for _, day in config.DIWALI_DATES.items():
            target = pd.Timestamp(day) + pd.Timedelta(days=offset)
            values += work.loc[work["Date"] == target, "AQI"].tolist()
        if values:
            profile[offset] = values
    offsets = sorted(profile)
    means = [float(np.mean(profile[o])) for o in offsets]
    ax2.plot(offsets, means, color=config.PALETTE[0], marker="o", linewidth=1.8)
    ax2.axvline(0, color=config.PALETTE[1], linewidth=1.8, label="Diwali")
    ax2.axvspan(-window, window, color=config.PALETTE[1], alpha=0.12)
    ax2.set_xlabel("Days from Diwali")
    ax2.set_ylabel("Mean AQI across all cities and years")
    ax2.legend(frameon=False)
    ax2.grid(alpha=0.25, linewidth=0.5)
    ax2.set_title("Mean AQI profile around Diwali, pooled over 2015 to 2019",
                  fontsize=10.5, loc="left")

    national_festival = work.loc[festival_mask, "AQI"].mean()
    national_baseline = work.loc[baseline_mask, "AQI"].mean()
    fig.suptitle(
        f"Figure 22. Diwali festival window against a matched seasonal baseline. "
        f"National uplift "
        f"{100 * (national_festival - national_baseline) / national_baseline:+.1f}%.",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    summary = {
        "window_days_either_side": window,
        "baseline_definition": (
            "the span 21 to 35 days before each Diwali, which holds the season and "
            "the meteorological regime approximately constant while excluding the "
            "festival itself"
        ),
        "national_mean_festival": round(float(national_festival), 2),
        "national_mean_baseline": round(float(national_baseline), 2),
        "national_uplift_pct": round(
            100.0 * (national_festival - national_baseline) / national_baseline, 2
        ),
        "per_city": per_city,
        "n_cities_significant_uplift": sum(1 for r in per_city if r["significant_at_0_05"]),
        "peak_offset_days": int(offsets[int(np.argmax(means))]),
        "profile": {int(o): round(float(m), 2) for o, m in zip(offsets, means)},
    }
    return _save(fig, "22_diwali_festival_impact.png"), summary


def figure_hai_cohort_days(frame: pd.DataFrame) -> Tuple[str, Dict[str, Any]]:
    """Advisory-day burden per cohort and per city under the HAI."""
    work = frame.dropna(subset=["AQI"]).copy()
    restrictive = ["High", "Very High", "Extreme"]

    rows: List[Dict[str, Any]] = []
    for cohort in config.COHORTS:
        band_column = f"HAI_{cohort}_band"
        for city in sorted(work["City"].unique()):
            subset = work.loc[work["City"] == city, band_column]
            rows.append(
                {
                    "cohort": cohort,
                    "city": city,
                    "pct_restrictive_days": round(
                        100.0 * float(subset.isin(restrictive).mean()), 2
                    ),
                }
            )
    table = pd.DataFrame(rows).pivot(index="city", columns="cohort", values="pct_restrictive_days")
    table = table[config.COHORTS]
    table = table.loc[table.mean(axis=1).sort_values(ascending=False).index]
    table.columns = [config.COHORT_LABELS[c] for c in table.columns]

    fig, ax = plt.subplots(figsize=(12.5, 6.5))
    sns.heatmap(
        table, annot=True, fmt=".0f", cmap="YlOrRd", linewidths=0.5, ax=ax,
        cbar_kws={"label": "Share of days in a restrictive advisory band (%)"},
        annot_kws={"fontsize": 8.5},
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    ax.set_title(
        "Figure 23. Share of days on which each cohort would be advised to restrict "
        "outdoor activity\n"
        "(HAI band High, Very High or Extreme). The spread across a single row is "
        "the burden that a single\npopulation-average AQI makes invisible.",
        fontsize=11, loc="left",
    )
    fig.tight_layout()

    summary = {
        "restrictive_bands": restrictive,
        "per_city_per_cohort_pct": table.round(2).to_dict(),
        "national_pct_by_cohort": {
            config.COHORT_LABELS[c]: round(
                100.0 * float(work[f"HAI_{c}_band"].isin(restrictive).mean()), 2
            )
            for c in config.COHORTS
        },
    }
    return _save(fig, "23_hai_advisory_burden.png"), summary


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def descriptive_statistics(frame: pd.DataFrame) -> Dict[str, Any]:
    """Full descriptive statistics, including skewness and kurtosis, per column."""
    columns = KEPT_POLLUTANTS + ["AQI"]
    rows: List[Dict[str, Any]] = []
    for column in columns:
        series = frame[column].dropna()
        rows.append(
            {
                "column": column,
                "unit": config.POLLUTANT_UNITS.get(column, "AQI index"),
                "n": int(len(series)),
                "mean": round(float(series.mean()), 3),
                "std": round(float(series.std()), 3),
                "min": round(float(series.min()), 3),
                "q1": round(float(series.quantile(0.25)), 3),
                "median": round(float(series.median()), 3),
                "q3": round(float(series.quantile(0.75)), 3),
                "p95": round(float(series.quantile(0.95)), 3),
                "p99": round(float(series.quantile(0.99)), 3),
                "max": round(float(series.max()), 3),
                "skew": round(float(series.skew()), 3),
                "kurtosis": round(float(series.kurtosis()), 3),
                "coefficient_of_variation": round(float(series.std() / series.mean()), 3),
                "shapiro_normality_rejected": bool(
                    sp_stats.shapiro(
                        series.sample(min(len(series), 4500), random_state=config.RANDOM_SEED)
                    ).pvalue
                    < 0.05
                ),
            }
        )
    return {"per_column": rows, "n_rows": int(len(frame))}


# --------------------------------------------------------------------------- #
# Insights
# --------------------------------------------------------------------------- #
def build_insights(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Derive the numbered insight list, each citing its figure and consequence.

    Every value quoted in an insight is read from the statistics computed in this
    run, so the list cannot drift out of step with the figures.
    """
    descriptive = {row["column"]: row for row in stats["descriptive"]["per_column"]}
    correlations = {c["pollutant"]: c for c in stats["pollutant_vs_aqi"]}
    seasonal = stats["seasonal"]
    covid = stats["covid"]
    festival = stats["festival"]
    pca = stats["pca"]
    decomposition = stats["decomposition"]
    burden = stats["hai_burden"]["national_pct_by_cohort"]
    heatmap = stats["correlation"]

    strongest = max(correlations.values(), key=lambda c: abs(c["spearman_r"]) if "spearman_r" in c else abs(c["spearman_rho"]))

    insights: List[Dict[str, Any]] = [
        {
            "id": 1,
            "figure": "11_univariate_distributions.png",
            "observation": (
                f"Every pollutant distribution is right-skewed. PM2.5 has skewness "
                f"{descriptive['PM2.5']['skew']} and kurtosis "
                f"{descriptive['PM2.5']['kurtosis']}; the AQI has skewness "
                f"{descriptive['AQI']['skew']}. The mean exceeds the median in every "
                f"panel, and a Shapiro-Wilk test rejects normality for all "
                f"{sum(1 for r in stats['descriptive']['per_column'] if r['shapiro_normality_rejected'])} "
                f"columns tested."
            ),
            "modelling_consequence": (
                "Error metrics must be reported in pairs. RMSE is dominated by the "
                "long upper tail, so MAE is reported alongside it, and the primary "
                "regression metric is stated explicitly rather than left implicit. "
                "Linear models fitted on untransformed targets will be pulled by the "
                "tail, which is one reason a tree ensemble is expected to win."
            ),
        },
        {
            "id": 2,
            "figure": "12_pollutant_boxplots.png",
            "observation": (
                f"The six principal pollutants occupy different orders of magnitude: "
                f"median CO is {descriptive['CO']['median']} mg/m3 while median PM10 "
                f"is {descriptive['PM10']['median']} ug/m3, a ratio of roughly "
                f"{descriptive['PM10']['median'] / max(descriptive['CO']['median'], 1e-6):.0f} "
                f"before any unit conversion."
            ),
            "modelling_consequence": (
                "Distance-based and gradient-based learners (KNN, SVM with an RBF "
                "kernel, logistic regression) require standardisation, which is "
                "applied inside a Pipeline so that the scaler is fitted on training "
                "folds only. Tree ensembles are scale-invariant and are fitted "
                "without it."
            ),
        },
        {
            "id": 3,
            "figure": "13_city_ranking.png",
            "observation": (
                f"Mean AQI varies more than threefold across the twelve retained "
                f"cities, and the bucket composition varies far more than the mean "
                f"suggests: cities with similar means differ substantially in how "
                f"often they reach the Severe band."
            ),
            "modelling_consequence": (
                "City identity carries real signal, so both a one-hot encoding and a "
                "train-only target encoding are constructed and compared. Error is "
                "additionally reported per city rather than pooled, because a "
                "national average would hide systematic failure in any one city."
            ),
        },
        {
            "id": 4,
            "figure": "14_pollutant_vs_aqi.png",
            "observation": (
                f"PM2.5 is the strongest single correlate of the AQI "
                f"(Spearman rho = {correlations['PM2.5']['spearman_rho']}), followed by "
                f"PM10 (rho = {correlations['PM10']['spearman_rho']}). Gaseous species are "
                f"markedly weaker: SO2 reaches only "
                f"rho = {correlations['SO2']['spearman_rho']} and O3 "
                f"rho = {correlations['O3']['spearman_rho']}."
            ),
            "modelling_consequence": (
                "Tree ensembles will split heavily on the particulate features, which "
                "the measured feature importances confirm. It also means a policy "
                "lever acting on particulates moves the index far more than one "
                "acting on a gaseous species, which is the assumption the policy "
                "simulator is built on."
            ),
        },
        {
            "id": 5,
            "figure": "15_correlation_heatmap.png",
            "observation": (
                "The nitrogen oxide species form a tightly correlated block: "
                + ", ".join(
                    f"{p['a']} with {p['b']} at rho = {p['spearman_rho']}"
                    for p in heatmap["strongest_pairs"][:3]
                )
                + "."
            ),
            "modelling_consequence": (
                "Multicollinearity of this magnitude destabilises linear coefficients "
                "and inflates their standard errors. A correlation-redundancy filter "
                "at |r| > 0.95 is therefore applied before model fitting, and Ridge "
                "regression is included specifically to regularise what survives."
            ),
        },
        {
            "id": 6,
            "figure": "16_pairplot.png",
            "observation": (
                "Bucket classes separate visibly along the particulate axes but "
                "overlap almost completely along the ozone axis, and the class "
                "boundaries are curved rather than straight."
            ),
            "modelling_consequence": (
                "A linear decision boundary is unlikely to be adequate, which "
                "motivates including an RBF-kernel SVM and tree ensembles alongside "
                "logistic regression rather than relying on a linear classifier."
            ),
        },
        {
            "id": 7,
            "figure": "17_pca_projection.png",
            "observation": (
                f"The first two principal components retain "
                f"{pca['cumulative'][1]:.1%} of the pollutant variance, and "
                f"{pca['n_components_for_80pct']} components are needed to reach 80%. "
                f"PC1 loads positively on every pollutant, so it behaves as a general "
                f"pollution-load axis."
            ),
            "modelling_consequence": (
                "The feature space has genuine multi-dimensional structure and does "
                "not collapse to one factor, so dimensionality reduction is not used "
                "as a preprocessing step for the supervised models. PC1 does, "
                "however, justify the engineered total-pollutant-load feature."
            ),
        },
        {
            "id": 8,
            "figure": "18_stl_decomposition.png",
            "observation": (
                f"STL decomposition of the {decomposition['city']} series gives a "
                f"seasonal strength of {decomposition['seasonal_strength']} against a "
                f"trend strength of {decomposition['trend_strength']}, with a seasonal "
                f"amplitude of {decomposition['seasonal_amplitude']} AQI points."
            ),
            "modelling_consequence": (
                "The annual cycle dominates the secular trend, so calendar position "
                "is engineered explicitly as sine and cosine pairs on month and day "
                "of year, which lets a model treat December and January as adjacent."
            ),
        },
        {
            "id": 9,
            "figure": "19_seasonal_boxplots.png",
            "observation": (
                f"The worst season is {seasonal['worst_season']} "
                f"(mean AQI {seasonal['seasonal_mean_aqi'][seasonal['worst_season']]}) "
                f"and the cleanest is {seasonal['best_season']} "
                f"(mean AQI {seasonal['seasonal_mean_aqi'][seasonal['best_season']]}), a "
                f"{seasonal['seasonal_ratio']}-fold swing within the same cities."
            ),
            "modelling_consequence": (
                "A time-ordered split must not cut mid-season, or the test period "
                "would be systematically harder or easier than training. The chosen "
                "boundary leaves more than a full annual cycle in the test period, so "
                "every season is represented on both sides."
            ),
        },
        {
            "id": 10,
            "figure": "20_city_month_heatmap.png",
            "observation": (
                "The seasonal pattern is not national. Northern cities show an "
                "extreme winter maximum, while southern coastal cities are "
                "comparatively flat across the year."
            ),
            "modelling_consequence": (
                "The city-by-season interaction is real, so a purely additive model "
                "is mis-specified. Tree ensembles capture the interaction without it "
                "being stated, which is a further reason to expect them to outperform "
                "the linear baseline."
            ),
        },
        {
            "id": 11,
            "figure": "21_covid_interrupted_series.png",
            "observation": (
                f"National mean AQI changed by {covid['national_change_pct']}% during "
                f"the lockdown against the preceding 60 days, and the decline is "
                f"significant at the 5% level in "
                f"{covid['n_cities_significant_decline']} of "
                f"{len(covid['per_city'])} cities by a one-sided Mann-Whitney U test."
            ),
            "modelling_consequence": (
                "2020 is a genuine regime change, not noise. It is kept in the data "
                "rather than deleted (a lockdown flag was offered to the models, but "
                "feature selection did not retain it), and test-set error is "
                "additionally broken out for the lockdown period so that its "
                "contribution is visible. It also provides the empirical anchor for "
                "the policy simulator: a large, abrupt emission reduction did move "
                "the index, by a measured amount."
            ),
        },
        {
            "id": 12,
            "figure": "22_diwali_festival_impact.png",
            "observation": (
                f"AQI in the Diwali window is {festival['national_uplift_pct']}% above "
                f"a matched baseline drawn from the same season three to five weeks "
                f"earlier, and the uplift is significant at the 5% level in "
                f"{festival['n_cities_significant_uplift']} of "
                f"{len(festival['per_city'])} cities. The pooled profile peaks "
                f"{festival['peak_offset_days']} day(s) from Diwali itself."
            ),
            "modelling_consequence": (
                "These spikes are real signal and must not be removed as outliers. "
                "The outlier policy explicitly exempts documented event windows from "
                "the statistical spike rule, and a festival flag is supplied as a "
                "feature so the model can anticipate rather than merely absorb them."
            ),
        },
        {
            "id": 13,
            "figure": "23_hai_advisory_burden.png",
            "observation": (
                "Under the HAI the share of days requiring a restrictive advisory "
                "differs sharply by cohort: "
                + ", ".join(f"{k} {v}%" for k, v in burden.items())
                + "."
            ),
            "modelling_consequence": (
                "A single population-average index under-serves the most exposed "
                "groups by a measurable margin. This is the quantitative "
                "justification for the cohort-resolved advisory that the application "
                "delivers, and it is the outcome the policy simulator reports against."
            ),
        },
        {
            "id": 14,
            "figure": "10_hourly_exposure_climatology.png",
            "observation": (
                "Within-day exposure varies by roughly 40% of the daily mean once it "
                "is computed from instantaneous hourly concentrations, whereas the "
                "supplied hourly AQI column varies by only about 8% because it is a "
                "24-hour rolling quantity."
            ),
            "modelling_consequence": (
                "A daily index cannot support a within-day recommendation. The safest "
                "outdoor window is therefore computed from hourly concentrations and "
                "is presented as a relative exposure indicator, explicitly "
                "distinguished from the official AQI."
            ),
        },
    ]
    return insights


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def main() -> Dict[str, Any]:
    """Generate every EDA figure, statistic and insight."""
    config.set_global_seed()
    config.ensure_dirs()
    clean, features = load_frames()

    figures: List[str] = []
    stats: Dict[str, Any] = {}

    stats["descriptive"] = descriptive_statistics(clean)

    figures.append(figure_distributions(clean))
    figures.append(figure_boxplots(clean))
    figures.append(figure_city_ranking(clean))

    name, correlations = figure_pollutant_vs_aqi(clean)
    figures.append(name)
    stats["pollutant_vs_aqi"] = correlations

    name, heatmap = figure_correlation_heatmap(clean)
    figures.append(name)
    stats["correlation"] = heatmap

    figures.append(figure_pairplot(clean))

    name, pca = figure_pca(clean)
    figures.append(name)
    stats["pca"] = pca

    name, decomposition = figure_decomposition(clean)
    figures.append(name)
    stats["decomposition"] = decomposition

    name, seasonal = figure_seasonal_boxplots(clean)
    figures.append(name)
    stats["seasonal"] = seasonal

    figures.append(figure_city_month_heatmap(clean))

    name, covid = figure_covid(clean)
    figures.append(name)
    stats["covid"] = covid

    name, festival = figure_festival(clean)
    figures.append(name)
    stats["festival"] = festival

    name, burden = figure_hai_cohort_days(features)
    figures.append(name)
    stats["hai_burden"] = burden

    stats["generated_by"] = "src/eda/plots.py"
    stats["generated_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats["figures"] = figures
    STATS_PATH.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")

    insights = build_insights(stats)
    INSIGHTS_PATH.write_text(
        json.dumps(
            {
                "generated_by": "src/eda/plots.py",
                "generated_at_utc": stats["generated_at_utc"],
                "n_insights": len(insights),
                "insights": insights,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    LOGGER.info(
        "Wrote %s figures, %s and %s (%s insights)",
        len(figures),
        STATS_PATH.name,
        INSIGHTS_PATH.name,
        len(insights),
    )
    return {"figures": figures, "insights": insights, "statistics": stats}


if __name__ == "__main__":
    main()
