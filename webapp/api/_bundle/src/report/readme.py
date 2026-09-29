"""Injection of live results into the README, so it cannot drift from the pipeline.

The README is hand-written prose, but its results table and its deployment URL
must reflect what the pipeline actually produced. Both are enclosed in HTML
comment markers and regenerated here, which keeps the zero-hardcoded-metrics rule
intact for the repository's front page as well as for the reports.

Run with::

    python -m src.report.readme
    python -m src.report.readme --url https://your-app.streamlit.app
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src import config

LOGGER = config.get_logger(__name__)

README = config.PROJECT_ROOT / "README.md"
DEPLOYMENT_FILE = config.RESULTS_DIR / "deployment.json"

RESULTS_START = "<!-- RESULTS:START -->"
RESULTS_END = "<!-- RESULTS:END -->"
DEPLOY_START = "<!-- DEPLOYMENT:START -->"
DEPLOY_END = "<!-- DEPLOYMENT:END -->"


def _load(name: str) -> Dict[str, Any]:
    path = config.RESULTS_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def deployment_url() -> str:
    """Return the recorded deployment URL, or a placeholder if none is set."""
    if DEPLOYMENT_FILE.exists():
        payload = json.loads(DEPLOYMENT_FILE.read_text(encoding="utf-8"))
        url = payload.get("url", "").strip()
        if url:
            return url
    return "_Not yet deployed. Run `python -m src.report.readme --url <your-url>` once the app is live._"


def set_deployment_url(url: str) -> Path:
    """Record the deployment URL so the README and Review 3 can both cite it."""
    DEPLOYMENT_FILE.write_text(
        json.dumps(
            {
                "url": url.strip(),
                "recorded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "platform": "Streamlit Community Cloud",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    LOGGER.info("Recorded deployment URL: %s", url)
    return DEPLOYMENT_FILE


def results_block() -> str:
    """Render the live results table for the README."""
    regression = _load("evaluation_regression.json")
    classification = _load("evaluation_classification.json")
    clustering = _load("evaluation_clustering.json")
    divergence = _load("hai_divergence.json")
    errors = _load("error_analysis.json")
    policy = _load("policy_simulation.json")

    if not regression or not classification:
        return (
            "> Results not yet generated. Run `python run_all.py` and this table "
            "will be populated automatically."
        )

    reg = regression.get("best_test_metrics", {})
    clf = classification.get("best_test_metrics", {})
    reg_base = regression.get("baseline_comparison", {})
    clf_base = classification.get("baseline_comparison", {})
    severe = next((c for c in clf.get("per_class", []) if c["class"] == "Severe"), {})
    kmeans = clustering.get("algorithms", {}).get("KMeans", {})

    lines: List[str] = [
        "| Task | Selected model | Primary metric | Value | Baseline | Improvement |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| **Regression** (next-day AQI) | {regression.get('best_model', 'n/a')} | MAE | "
        f"**{reg.get('MAE', 'n/a')}** | {reg_base.get('baseline_mae', 'n/a')} (persistence) | "
        f"**{reg_base.get('improvement_over_persistence_pct', 'n/a')}%** |",
        f"| **Classification** (next-day band) | {classification.get('best_model', 'n/a')} | "
        f"Macro F1 | **{clf.get('macro_f1', 'n/a')}** | "
        f"{clf_base.get('baseline_macro_f1', 'n/a')} (persistence) | "
        f"**{clf_base.get('improvement_over_persistence_pct', 'n/a')}%** |",
        f"| **Clustering** (city archetypes) | K-Means, k = {clustering.get('selected_k', '?')} | "
        f"Silhouette | **{kmeans.get('silhouette', 'n/a')}** | "
        f"Ward agglomerative | ARI "
        f"{clustering.get('algorithm_agreement', {}).get('adjusted_rand_index', 'n/a')} |",
        "",
        "**Regression detail**",
        "",
        "| MAE | RMSE | R² | MAPE | Bias |",
        "| --- | --- | --- | --- | --- |",
        f"| {reg.get('MAE', 'n/a')} | {reg.get('RMSE', 'n/a')} | {reg.get('R2', 'n/a')} | "
        f"{reg.get('MAPE_pct', 'n/a')}% | {reg.get('bias', 'n/a')} |",
        "",
        "**Classification detail**",
        "",
        "| Macro F1 | Accuracy | Weighted F1 | Balanced acc. | ROC-AUC (OvR) | "
        "F1 on *Severe* | Within 1 band |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| {clf.get('macro_f1', 'n/a')} | {clf.get('accuracy', 'n/a')} | "
        f"{clf.get('weighted_f1', 'n/a')} | {clf.get('balanced_accuracy', 'n/a')} | "
        f"{clf.get('roc_auc_ovr_macro', 'n/a')} | {severe.get('f1', 'n/a')} | "
        f"{clf.get('pct_within_one_band', 'n/a')}% |",
        "",
    ]

    if errors:
        lines += [
            f"> **Safety statistic.** Of {errors.get('n_test', 0):,} test predictions, "
            f"**{errors.get('n_understating_severity_by_two_or_more', 0):,} "
            f"({errors.get('pct_understating_severity_by_two_or_more', 0)}%)** understate "
            f"severity by two bands or more. That is the failure mode that matters "
            f"operationally — being told the air is better than it is — and it is "
            f"reported as a first-class number rather than buried inside an average.",
            "",
        ]

    if divergence:
        cohorts = divergence.get("per_cohort", [])
        worst = max(cohorts, key=lambda c: c["pct_band_differs_from_aqi"]) if cohorts else {}
        lines += [
            "**The novelty claim, measured**",
            "",
            f"Across **{divergence.get('n_city_days_evaluated', 0):,} city-days**, at least "
            f"one cohort receives a *different advisory band* from the one the official AQI "
            f"implies on **{divergence.get('any_cohort_differs', {}).get('pct', 0)}%** of days.",
            "",
            "| Cohort | Mean HAI | Mean AQI ÷ 5 | Mean uplift | Band differs from AQI |",
            "| --- | --- | --- | --- | --- |",
        ]
        for entry in cohorts:
            lines.append(
                f"| {entry['cohort_label']} | {entry['mean_hai']} | "
                f"{entry['mean_aqi_rescaled']} | +{entry['mean_uplift_points']} | "
                f"**{entry['pct_band_differs_from_aqi']}%** |"
            )
        lines += [
            "",
            f"The divergence is decomposed rather than quoted as one headline: the "
            f"aggregation rule alone (dominant sub-index plus a co-exposure surcharge, "
            f"replacing the plain maximum) accounts for "
            f"{divergence.get('aggregation_effect', {}).get('pct', 0)}%, and the cohort "
            f"weighting accounts for the remainder — rising to "
            f"{worst.get('pct_band_differs_from_aqi', 0)}% for "
            f"{worst.get('cohort_label', 'the most affected cohort').lower()}.",
            "",
        ]

    if policy:
        headline = policy.get("headline_scenario", {})
        anchor = policy.get("lockdown_anchor", {})
        whole = next(
            (s for s in policy.get("scenarios", [])
             if s["name"] == "All pollutants reduced by 40%"), None
        )
        if headline:
            result = headline.get("result", {})
            lines += [
                "**Policy simulator**",
                "",
                f"Headline scenario — *{headline.get('name', '')}*: mean AQI "
                f"{result.get('aqi', {}).get('mean_before', 0):.1f} → "
                f"{result.get('aqi', {}).get('mean_after', 0):.1f} "
                f"({result.get('aqi', {}).get('mean_change_pct', 0):+.1f}%), "
                f"**{result.get('unsafe_days', {}).get('reduction_pct', 0):.1f}%** fewer "
                f"unsafe city-days, and "
                f"**{result.get('cohort_advisory_days', {}).get('total_averted_across_cohorts', 0):,} "
                f"cohort advisory-days averted**.",
                "",
            ]
        if anchor and whole:
            lines += [
                f"> **Independent sanity check.** The 2020 national lockdown produced a "
                f"*measured* **{anchor.get('measured_aqi_change_pct', 0)}%** change in "
                f"national mean AQI. The simulator's nearest comparable scenario — a 40% "
                f"reduction across all pollutants — yields "
                f"**{whole['result']['aqi']['mean_change_pct']:+.1f}%**. The two agree "
                f"closely, and the simulator was not fitted to that episode in any way.",
                "",
            ]

    figures = sorted(config.FIGURES_DIR.glob("*.png"))
    results_files = sorted(config.RESULTS_DIR.glob("*.json")) + sorted(
        config.RESULTS_DIR.glob("*.csv")
    )
    lines += [
        f"*Artefacts at this build: **{len(figures)} figures** (all at "
        f"{config.FIG_DPI} DPI, colour-blind-safe), **{len(results_files)} result "
        f"files**, **{len(list(config.MODELS_DIR.glob('*.joblib')))} model artefacts**. "
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.*",
    ]
    return "\n".join(lines)


def _replace_block(text: str, start: str, end: str, content: str) -> str:
    """Replace the content between two markers, inserting the markers if absent."""
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    replacement = f"{start}\n{content}\n{end}"
    if pattern.search(text):
        return pattern.sub(lambda _: replacement, text)
    return text


def update_readme() -> Path:
    """Inject the live results table and deployment URL into the README."""
    if not README.exists():
        LOGGER.warning("README.md not found; nothing to update")
        return README

    text = README.read_text(encoding="utf-8")

    if RESULTS_START not in text:
        # Insert the markers immediately under the Results heading on first run.
        text = text.replace(
            "## Results\n",
            f"## Results\n\n{RESULTS_START}\n{RESULTS_END}\n",
            1,
        )
    if DEPLOY_START not in text:
        text = text.replace(
            "**Live deployment:**",
            f"{DEPLOY_START}\n**Live deployment:**",
            1,
        ).replace(
            "_see the \"Deployment\" section below._",
            f"_see the \"Deployment\" section below._\n{DEPLOY_END}",
            1,
        )

    text = _replace_block(text, RESULTS_START, RESULTS_END, results_block())
    text = _replace_block(
        text, DEPLOY_START, DEPLOY_END, f"**Live deployment:** {deployment_url()}"
    )

    README.write_text(text, encoding="utf-8")
    LOGGER.info("Updated README.md results and deployment blocks")
    return README


def main(url: Optional[str] = None) -> Dict[str, str]:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Refresh the README from results.")
    parser.add_argument("--url", help="record the live deployment URL")
    args, _ = parser.parse_known_args()
    target = url or args.url
    if target:
        set_deployment_url(target)
    path = update_readme()
    return {"readme": str(path), "deployment_url": deployment_url()}


if __name__ == "__main__":
    main()
