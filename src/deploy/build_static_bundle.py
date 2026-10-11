"""Assemble every static asset the Vercel frontend needs.

The Next.js pages recreate the Streamlit application's read-only views
(everything except the forecast and the policy simulator, which need live
computation and are served by the two Python functions in ``webapp/api``).
Those views only ever display artefacts the pipeline has already produced, so
there is nothing to compute here: this script copies ``results/*.json``, the
figures each page references, the two master comparison tables, the data and
model cards, and computes the two small aggregate tables the City Risk Atlas
page derives from the feature matrix (the ranked risk table and the seasonal
heatmap), exactly as ``app/pages/2_City_Risk_Atlas.py`` does, so the static
site and the Streamlit application show the same numbers from the same code
path's output.

Run with::

    python -m src.deploy.build_static_bundle
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from src import config

PUBLIC_DIR = config.PROJECT_ROOT / "webapp" / "public"
DATA_OUT = PUBLIC_DIR / "data"
FIGURES_OUT = PUBLIC_DIR / "figures"

RESULT_FILES = [
    "evaluation_regression.json",
    "evaluation_classification.json",
    "evaluation_clustering.json",
    "tuning_report.json",
    "explainability.json",
    "error_analysis.json",
    "hai_divergence.json",
    "eda_statistics.json",
    "eda_insights.json",
    "safe_windows.json",
    "policy_simulation.json",
    "feature_engineering_report.json",
    "cleaning_report.json",
    "deployment_classifier.json",
    "definition_of_done.json",
]

FIGURE_FILES = [
    "24_clustering_selection.png",
    "25_cluster_profiles.png",
    "26_tuning_before_after.png",
    "27_regression_comparison.png",
    "28_classification_comparison.png",
    "29_confusion_matrices.png",
    "30_roc_curves.png",
    "31_residual_analysis.png",
    "32_learning_curves.png",
    "33_per_city_error.png",
    "34_train_test_gap.png",
    "35_error_analysis.png",
    "36_shap_global.png",
    "37_shap_local_waterfall.png",
]


def _copy_results() -> list[str]:
    written = []
    for name in RESULT_FILES:
        source = config.RESULTS_DIR / name
        if source.exists():
            shutil.copy2(source, DATA_OUT / name)
            written.append(name)
    return written


def _copy_figures() -> list[str]:
    written = []
    for name in FIGURE_FILES:
        source = config.FIGURES_DIR / name
        if source.exists():
            shutil.copy2(source, FIGURES_OUT / name)
            written.append(name)
    return written


def _copy_master_tables() -> list[str]:
    written = []
    for name in (
        "master_comparison_regression.csv",
        "master_comparison_classification.csv",
        "master_comparison_clustering.csv",
    ):
        source = config.RESULTS_DIR / name
        if not source.exists():
            continue
        frame = pd.read_csv(source)
        out_name = name.replace(".csv", ".json")
        (DATA_OUT / out_name).write_text(frame.to_json(orient="records"), encoding="utf-8")
        written.append(out_name)
    return written


def _copy_cards() -> list[str]:
    written = []
    for name in ("data_card.md", "model_card.md"):
        source = config.REPORTS_DIR / name
        if source.exists():
            (DATA_OUT / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(name)
    return written


def _copy_provenance() -> None:
    source = config.RAW_DIR / "PROVENANCE.json"
    if source.exists():
        shutil.copy2(source, DATA_OUT / "PROVENANCE.json")


def _build_ranked_risk_table() -> None:
    """Reproduce the ranked risk table from ``2_City_Risk_Atlas.py`` tab 2."""
    clustering_path = config.RESULTS_DIR / "evaluation_clustering.json"
    features_path = config.PROJECT_ROOT / "data" / "processed" / "features_full.csv"
    if not clustering_path.exists() or not features_path.exists():
        return

    clustering = json.loads(clustering_path.read_text(encoding="utf-8"))
    cluster_of = clustering["city_to_cluster"]
    archetype_of = {entry["cluster"]: entry["archetype"] for entry in clustering["archetypes"]}
    restrictive = ["High", "Very High", "Extreme"]

    features = pd.read_csv(features_path, parse_dates=["Date"])
    rows = []
    for city, group in features.dropna(subset=["AQI"]).groupby("City"):
        entry = {
            "City": city,
            "Archetype": archetype_of.get(cluster_of.get(city, -1), "n/a"),
            "Mean AQI": round(float(group["AQI"].mean()), 1),
            "Median AQI": round(float(group["AQI"].median()), 1),
            "Worst AQI": round(float(group["AQI"].max()), 1),
            "Days Poor or worse (%)": round(
                100.0 * float(group["AQI_Bucket"].isin(["Poor", "Very Poor", "Severe"]).mean()), 1
            ),
            "Days Severe (%)": round(100.0 * float((group["AQI_Bucket"] == "Severe").mean()), 1),
        }
        for cohort in ("healthy_adult", "children", "elderly_60plus", "cardiac"):
            entry[f"{config.COHORT_LABELS[cohort]} restricted (%)"] = round(
                100.0 * float(group[f"HAI_{cohort}_band"].isin(restrictive).mean()), 1
            )
        rows.append(entry)

    table = pd.DataFrame(rows).sort_values("Mean AQI", ascending=False).reset_index(drop=True)
    (DATA_OUT / "ranked_risk_table.json").write_text(table.to_json(orient="records"), encoding="utf-8")


def _build_seasonal_heatmap() -> None:
    """Reproduce the city x month AQI heatmap from tab 3."""
    clean_path = config.PROJECT_ROOT / "data" / "processed" / "city_day_clean.csv"
    if not clean_path.exists():
        return
    clean = pd.read_csv(clean_path, parse_dates=["Date"])
    work = clean.dropna(subset=["AQI"]).copy()
    work["month"] = work["Date"].dt.month
    pivot = work.pivot_table(index="City", columns="month", values="AQI", aggfunc="mean")
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

    payload = {
        "cities": pivot.index.tolist(),
        "months": [pd.Timestamp(2020, m, 1).strftime("%b") for m in pivot.columns],
        "values": [[None if pd.isna(v) else round(float(v), 1) for v in row] for row in pivot.to_numpy()],
    }
    (DATA_OUT / "seasonal_heatmap.json").write_text(json.dumps(payload), encoding="utf-8")


def _build_meta() -> None:
    """Export the config constants and per-city date coverage the frontend needs."""
    features_path = config.PROJECT_ROOT / "data" / "processed" / "features_full.csv"
    features = pd.read_csv(features_path, parse_dates=["Date"])
    cities = sorted(features["City"].unique().tolist())
    date_bounds = {
        city: {
            "min": features.loc[features["City"] == city, "Date"].min().strftime("%Y-%m-%d"),
            "max": features.loc[features["City"] == city, "Date"].max().strftime("%Y-%m-%d"),
        }
        for city in cities
    }

    payload = {
        "cities": cities,
        "date_bounds": date_bounds,
        "cohorts": config.COHORTS,
        "cohort_labels": config.COHORT_LABELS,
        "hai_pollutants": config.HAI_POLLUTANTS,
        "pollutant_units": config.POLLUTANT_UNITS,
        "aqi_buckets": config.AQI_BUCKETS,
        "aqi_bucket_bounds": [[b[0], b[1], (None if b[2] == float("inf") else b[2])] for b in config.AQI_BUCKET_BOUNDS],
        "season_order": config.SEASON_ORDER,
        "palette": config.PALETTE,
        "academic": config.ACADEMIC,
        "team": config.TEAM,
        "repo_url": config.REPO_URL,
    }
    (DATA_OUT / "meta.json").write_text(json.dumps(payload), encoding="utf-8")


def main() -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    FIGURES_OUT.mkdir(parents=True, exist_ok=True)

    results = _copy_results()
    figures = _copy_figures()
    tables = _copy_master_tables()
    cards = _copy_cards()
    _copy_provenance()
    _build_ranked_risk_table()
    _build_seasonal_heatmap()
    _build_meta()
    from src.deploy.public_exports import sanitize_directory
    sanitize_directory(DATA_OUT)

    print(f"results copied: {len(results)}")
    print(f"figures copied: {len(figures)}")
    print(f"master tables converted: {len(tables)}")
    print(f"cards copied: {len(cards)}")
    print(f"total public/data size: {sum(f.stat().st_size for f in DATA_OUT.glob('*')) / 1e6:.1f} MB")
    print(f"total public/figures size: {sum(f.stat().st_size for f in FIGURES_OUT.glob('*')) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
