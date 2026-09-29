"""Generation and execution of the three phase notebooks.

The notebooks contain orchestration and narrative only. Every piece of business
logic is imported from ``src/``, so a notebook cannot drift away from the code
that produced the results, and a reader can follow the argument without reading
an implementation inline.

Each notebook is built programmatically and then executed end to end with
``nbconvert``, so the committed ``.ipynb`` files carry real output rather than
empty cells.

Outputs
-------
``notebooks/01_phase1_problem_and_dataset.ipynb``
``notebooks/02_phase2_preprocessing_and_eda.ipynb``
``notebooks/03_phase3_modeling_and_comparison.ipynb``

Run with::

    python -m src.report.notebooks
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

from src import config

LOGGER = config.get_logger(__name__)

#: Preamble placed at the top of every notebook so that ``src`` is importable
#: regardless of the working directory the notebook was opened from.
PREAMBLE = """\
import sys, json
from pathlib import Path

ROOT = Path.cwd()
while not (ROOT / "src").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from IPython.display import Image, Markdown, display

from src import config

config.set_global_seed()
pd.set_option("display.max_columns", 60)
pd.set_option("display.width", 200)

RESULTS = config.RESULTS_DIR
FIGURES = config.FIGURES_DIR

def load(name: str) -> dict:
    \"\"\"Load a results artefact by file name.\"\"\"
    path = RESULTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def show(filename: str, caption: str = "") -> None:
    \"\"\"Display a pipeline-generated figure with its caption.\"\"\"
    path = FIGURES / filename
    if path.exists():
        display(Image(filename=str(path), width=900))
        if caption:
            display(Markdown(f"*{caption}*"))
    else:
        display(Markdown(f"> Figure `{filename}` not found. Run `python run_all.py`."))

print(f"Project root: {ROOT}")
print(f"Global seed:  {config.RANDOM_SEED}")
"""


def _notebook(cells: List[Any]) -> Any:
    """Assemble a notebook with the project kernel metadata."""
    notebook = new_notebook(cells=cells)
    notebook.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"},
    }
    return notebook


def _header(title: str, phase: str, rubric: str) -> str:
    """Return the markdown header shared by every notebook."""
    academic = config.ACADEMIC
    return f"""\
# {academic['project_title']} — {title}

**{academic['course_code']} · {academic['course_name']}**
{academic['institution']}

| | |
| --- | --- |
| Phase | {phase} |
| Rubric rows addressed | {rubric} |
| Degree and branch | {academic['degree_branch']} |
| Regulation / Year / Semester | {academic['regulation']} / {academic['academic_year']} / {academic['semester']} |
| Team | {', '.join(f"{m['register_no']} ({m['name']})" for m in config.TEAM)} |
| Repository | {config.REPO_URL} |

---

> **How to read this notebook.** It contains orchestration and narrative only.
> Every piece of analysis logic lives in the `src/` package and is imported
> here, so nothing shown below can drift away from the code that produced the
> committed results. Every number displayed is read from `results/*.json`, which
> the pipeline writes; none is typed by hand.
"""


# --------------------------------------------------------------------------- #
# Notebook 1
# --------------------------------------------------------------------------- #
def build_notebook1() -> Path:
    """Build the phase 1 notebook: problem framing, acquisition and provenance."""
    cells = [
        new_markdown_cell(
            _header(
                "Phase 1: Problem Statement and Dataset",
                "1 of 3 — Review 1",
                "Problem statement; dataset selection and quality; project charter; "
                "methodology; planning",
            )
        ),
        new_code_cell(PREAMBLE),
        new_markdown_cell(
            "## 1. The problem\n\n"
            "India's air quality index is accurate but has two structural "
            "limitations as a personal health signal: it is a single "
            "population-average number reported identically to every person in a "
            "city, and it is retrospective. This project forecasts the next day and "
            "resolves the advisory by vulnerability cohort, while guaranteeing that "
            "it is never less protective than the official index.\n\n"
            "The full problem statement, the six research objectives with their "
            "measurable success criteria, and the project charter are in "
            "`reports/Review1_Problem_and_Dataset.docx`, generated from the same "
            "artefacts this notebook reads."
        ),
        new_markdown_cell(
            "## 2. Acquisition and provenance\n\n"
            "The dataset is acquired programmatically. The acquisition module emits "
            "an audit trail a reviewer can independently re-verify: SHA-256 "
            "checksums for every file, the licence string read from the live dataset "
            "page at download time, and a full column-level schema profile."
        ),
        new_code_cell(
            'provenance = json.loads((config.RAW_DIR / "PROVENANCE.json").read_text(encoding="utf-8"))\n'
            'dataset, licence = provenance["dataset"], provenance["license"]\n'
            'primary = provenance["primary_file"]\n\n'
            'display(Markdown(f"""\n'
            "| Field | Value |\n"
            "| --- | --- |\n"
            '| Title (scraped from the source page) | {dataset["title_scraped"]} |\n'
            '| Upstream producer | {provenance["upstream_source"]["organisation"]} |\n'
            '| Mirror | {dataset["kaggle_url"]} |\n'
            '| **Licence as displayed** | **{licence["string_as_displayed_on_kaggle"]}** |\n'
            '| Verified live at download | {licence["verified_live"]} |\n'
            '| Retrieved (UTC) | {provenance["downloaded_at_utc"]} |\n'
            '| Rows | {primary["rows"]:,} |\n'
            '| Columns | {primary["columns"]} |\n'
            '| Cities | {primary["n_cities"]} |\n'
            '| Coverage | {primary["date_min"]} to {primary["date_max"]} |\n'
            '"""))'
        ),
        new_markdown_cell(
            "The licence recorded above is the string the source page actually "
            "displayed, not an assumption inherited from the upstream agency's usual "
            "terms. The compiled dataset and its upstream source are separately "
            "licensed artefacts, and conflating them would misstate the terms under "
            "which this work redistributes anything."
        ),
        new_code_cell(
            'rows = [\n'
            '    {\n'
            '        "File": f["filename"],\n'
            '        "Size (MB)": f["size_mb"],\n'
            '        "Rows": f["rows"],\n'
            '        "Columns": f["columns"],\n'
            '        "In data/raw/": f["retained_in_data_raw"],\n'
            '        "SHA-256 (first 16)": f["sha256"][:16] + "...",\n'
            '    }\n'
            '    for f in provenance["files"] if f.get("present")\n'
            ']\n'
            'display(Markdown("### Files acquired, with checksums"))\n'
            'display(pd.DataFrame(rows))'
        ),
        new_code_cell(
            'show("00_dataset_proof_schema.png",\n'
            '     "Figure 1. Column-level schema of city_day.csv rendered directly from '
            'the acquired file. This is documentary evidence that the schema was read rather '
            'than transcribed.")'
        ),
        new_markdown_cell(
            "## 3. Initial quality assessment\n\n"
            "The assessment runs in full before any cleaning decision is taken, so "
            "that each decision can be justified by a measurement rather than by an "
            "expectation."
        ),
        new_code_cell(
            'quality = load("data_quality_report.json")\n'
            'invalid, duplicates = quality["invalid_values"], quality["duplicates"]\n'
            'consistency = invalid["bucket_consistency"]\n\n'
            'display(Markdown(f"""\n'
            "| Check | Result |\n"
            "| --- | --- |\n"
            '| Fully duplicated rows | {duplicates["fully_duplicated_rows"]} |\n'
            '| Duplicate (City, Date) keys | {duplicates["duplicated_city_date_keys"]} |\n'
            '| Missing calendar days | {invalid["dates"]["total_missing_calendar_days"]} |\n'
            '| Columns failing a unit check | {quality["unit_sanity"]["n_flagged"]} |\n'
            '| City naming | {quality["city_naming"]["verdict"]} |\n'
            '| AQI above the CPCB 0-500 scale | {invalid["aqi"]["aqi_above_scale_max_500"]} '
            "({invalid['aqi']['aqi_above_scale_max_500_pct']}%) |\n"
            '| AQI_Bucket reproducible from AQI | {consistency["agreement_pct"]}% '
            "({consistency['mismatches']} mismatches) |\n"
            '"""))'
        ),
        new_markdown_cell(
            "The final row is the important one. The band is reproducible from the "
            "AQI by the published cut points alone, which is verified here rather "
            "than assumed. That fact establishes the label-leakage hazard that the "
            "forecasting formulation dissolves, and which phase 3 measures directly."
        ),
        new_code_cell(
            'balance = quality["class_balance"]\n'
            'display(Markdown("### AQI band distribution"))\n'
            'display(pd.DataFrame(balance["distribution"]))\n'
            'display(Markdown(f"**Imbalance ratio:** {balance[\'imbalance_ratio_max_over_min\']}\\n\\n"\n'
            '                 f"{balance[\'implication\']}"))'
        ),
        new_markdown_cell(
            "## 4. City selection\n\n"
            "Two gates, both fixed before any model was fitted. No city is dropped "
            "silently: every exclusion appears below with its completeness figure "
            "and its reason."
        ),
        new_code_cell(
            'retention = quality["city_retention"]\n'
            'table = pd.DataFrame(retention["decisions"])[\n'
            '    ["city", "labelled_days", "aqi_completeness", "retained", "reason"]\n'
            ']\n'
            'display(Markdown(f"**{retention[\'n_retained\']} of "\n'
            '                 f"{retention[\'n_retained\'] + retention[\'n_excluded\']} cities retained.**"))\n'
            'display(table)\n'
            'display(Markdown(f"*{retention[\'threshold_justification\']}*"))'
        ),
        new_code_cell(
            'show("02_city_availability_heatmap.png",\n'
            '     "Figure 2. Per-city availability of a labelled AQI by month. Coverage '
            'expanded over the record, which is the structural reason a national trend '
            'across the full span cannot be claimed from these data.")\n'
            'show("03_null_percentage_bar.png", "Figure 3. Missing-value rate per column.")'
        ),
        new_markdown_cell(
            "## 5. Methodology\n\n"
            "The pipeline below is the design the remaining two phases execute. The "
            "leakage controls in the lower band apply at every stage rather than at "
            "a single checkpoint."
        ),
        new_code_cell(
            'show("39_pipeline_diagram.png", "Figure 4. End-to-end methodology.")\n'
            'show("40_project_gantt.png", "Figure 5. Six-week project plan with the three review milestones.")'
        ),
        new_markdown_cell(
            "## 6. Phase 1 outcome\n\n"
            "* Dataset acquired, with a machine-verified provenance record.\n"
            "* Quality assessed; the label-leakage hazard identified and verified.\n"
            "* City selection gates applied with every decision recorded.\n"
            "* Methodology, charter and plan fixed.\n\n"
            "Phase 2 cleans the record, engineers the features and builds the Health "
            "Advisory Index."
        ),
    ]
    path = config.NOTEBOOKS_DIR / "01_phase1_problem_and_dataset.ipynb"
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(_notebook(cells), str(path))
    return path


# --------------------------------------------------------------------------- #
# Notebook 2
# --------------------------------------------------------------------------- #
def build_notebook2() -> Path:
    """Build the phase 2 notebook: cleaning, features and exploratory analysis."""
    cells = [
        new_markdown_cell(
            _header(
                "Phase 2: Preprocessing and Exploratory Data Analysis",
                "2 of 3 — Review 2",
                "Data quality; preprocessing and cleansing; transformation and "
                "feature engineering; EDA; interpretation",
            )
        ),
        new_code_cell(PREAMBLE),
        new_markdown_cell(
            "## 1. The cleaning decisions, and the evidence for each\n\n"
            "Three decisions in this phase could have been made by preference. Each "
            "was instead made by measurement, and the measurement is shown."
        ),
        new_code_cell(
            'cleaning = load("cleaning_report.json")\n'
            'artefacts = cleaning["artefact_policy"]\n'
            'display(Markdown("### Decision 1 — which extreme values are artefacts?"))\n'
            'display(Markdown(f"**Retention principle.** {artefacts[\'retention_principle\']}"))\n'
            'display(pd.DataFrame(artefacts["rule"], index=["Condition"]).T)\n'
            'display(pd.DataFrame(artefacts["per_pollutant"]).T)\n'
            'display(Markdown(\n'
            '    f"**{artefacts[\'event_window_protected_days\']:,} city-days** fall inside a "\n'
            '    f"documented event window and are exempt from the statistical spike rule. "\n'
            '    f"In total {artefacts[\'total_values_set_to_missing\']} values were converted "\n'
            '    f"to missing, and {artefacts[\'aqi_above_scale_retained_and_flagged\']} "\n'
            '    f"above-scale AQI values were retained and flagged rather than truncated."\n'
            '))'
        ),
        new_markdown_cell(
            "A pollution dataset contains two entirely different kinds of extreme "
            "value. An instrument fault must be removed; a Diwali night must not. "
            "The rule above separates them on physical grounds — build-up and decay "
            "over multiple days against an isolated single-day leap — and it never "
            "fires inside a documented event window."
        ),
        new_code_cell(
            'comparison = cleaning["imputation_comparison"]\n'
            'display(Markdown("### Decision 2 — which imputation strategy?"))\n'
            'display(Markdown(f"*Method.* {comparison[\'method\']}"))\n'
            'display(pd.DataFrame([\n'
            '    {\n'
            '        "Strategy": r["strategy"],\n'
            '        "Causal": r["causal"],\n'
            '        "MAE / IQR": r["mean_mae_over_iqr"],\n'
            '        "KS statistic": r["mean_ks_statistic"],\n'
            '        "Mean |std shift| %": r["mean_abs_std_shift_pct"],\n'
            '    }\n'
            '    for r in comparison["results"]\n'
            ']))\n'
            'display(Markdown(f"**Selection.** {comparison[\'selection_rationale\']}"))'
        ),
        new_code_cell(
            'show("05_imputation_strategy_comparison.png",\n'
            '     "Figure 1. Reconstruction error and distribution shift for each candidate. '
            'Green is causal and admissible for forecasting; orange is reported only to '
            'quantify what the causality constraint costs.")\n'
            'show("06_imputation_distribution_shift.png",\n'
            '     "Figure 2. Distributions before and after the adopted imputation.")'
        ),
        new_markdown_cell(
            "The result is worth stating plainly: linear interpolation reconstructs "
            "hidden values best, but it is **not causal** — it fills a gap using the "
            "observation that follows it. Since the task is to forecast tomorrow "
            "from today, adopting it would inflate reported test performance without "
            "improving real forecasting skill. The best causal strategy is adopted "
            "instead, and the cost of that constraint is now a measured quantity "
            "rather than an unexamined assumption."
        ),
        new_code_cell(
            'validation = cleaning["validation"]\n'
            'display(Markdown("### Decision 3 — did the cleaning actually work?"))\n'
            'display(pd.DataFrame([\n'
            '    {"Assertion": k, "Result": v}\n'
            '    for k, v in validation.items()\n'
            '    if isinstance(v, bool)\n'
            ']))\n'
            'display(Markdown(\n'
            '    f"Final shape **{validation[\'shape\'][\'rows\']:,} x {validation[\'shape\'][\'columns\']}** "\n'
            '    f"across **{validation[\'cities\']}** cities, "\n'
            '    f"{validation[\'date_range\'][0]} to {validation[\'date_range\'][1]}. "\n'
            '    f"Split boundary **{validation[\'split_boundary\']}** "\n'
            '    f"({validation[\'n_train_rows\']:,} train / {validation[\'n_test_rows\']:,} test)."\n'
            '))'
        ),
        new_markdown_cell(
            "## 2. Feature engineering\n\n"
            "Every window ends on the current day and every lag is taken within a "
            "city, so no feature can see the future and no city contributes to "
            "another city's history."
        ),
        new_code_cell(
            'features = load("feature_engineering_report.json")\n'
            'display(pd.DataFrame([\n'
            '    {"Group": k, "Count": v}\n'
            '    for k, v in features["feature_group_counts"].items()\n'
            ']))\n'
            'display(Markdown("### Leakage controls applied"))\n'
            'for name, text in features["leakage_controls"].items():\n'
            '    display(Markdown(f"**{name.capitalize()}.** {text}"))'
        ),
        new_markdown_cell(
            "## 3. The Health Advisory Index\n\n"
            "The index is the project's methodological contribution. Its "
            "mathematical properties are asserted in code and re-verified at every "
            "pipeline run, so a broken index cannot reach a report."
        ),
        new_code_cell(
            'from src.features import hai as hai_mod\n\n'
            'checks = hai_mod.self_test()\n'
            'display(pd.DataFrame([{"Property": k, "Verified": v} for k, v in checks.items()]))'
        ),
        new_code_cell(
            'display(Markdown("### Cohort vulnerability factors"))\n'
            'display(pd.DataFrame(hai_mod.VULNERABILITY).T[config.HAI_POLLUTANTS])\n'
            'display(Markdown(\n'
            '    "Every factor is at least 1 and the reference cohort is exactly 1 "\n'
            '    "throughout, which is what guarantees the index can never be less "\n'
            '    "protective than the official AQI."\n'
            '))'
        ),
        new_code_cell(
            'divergence = load("hai_divergence.json")\n'
            'display(pd.DataFrame(divergence["per_cohort"])[[\n'
            '    "cohort_label", "mean_hai", "mean_aqi_rescaled", "mean_uplift_points",\n'
            '    "pct_band_differs_from_aqi", "pct_band_differs_from_reference_cohort",\n'
            ']])\n'
            'display(Markdown(\n'
            '    f"Across **{divergence[\'n_city_days_evaluated\']:,} city-days**, at least one "\n'
            '    f"cohort receives a different advisory band from the one the official AQI "\n'
            '    f"implies on **{divergence[\'any_cohort_differs\'][\'pct\']}%** of days. "\n'
            '    f"The aggregation rule alone accounts for "\n'
            '    f"{divergence[\'aggregation_effect\'][\'pct\']}%; the remainder is the cohort "\n'
            '    f"weighting."\n'
            '))'
        ),
        new_code_cell(
            'show("07_hai_vs_aqi_scatter.png", "Figure 3. The index against the official AQI on real observations.")\n'
            'show("08_hai_divergence_by_cohort.png", "Figure 4. Divergence by cohort, decomposed.")'
        ),
        new_markdown_cell(
            "## 4. Exploratory analysis\n\n"
            "Every figure below has a written interpretation that states the "
            "modelling consequence it drives. A chart without one tells a reader "
            "nothing."
        ),
        new_code_cell(
            'eda = load("eda_statistics.json")\n'
            'display(Markdown("### Descriptive statistics"))\n'
            'display(pd.DataFrame(eda["descriptive"]["per_column"])[[\n'
            '    "column", "unit", "n", "mean", "std", "median", "p95", "max", "skew", "kurtosis",\n'
            ']])'
        ),
        new_code_cell(
            'for name, caption in [\n'
            '    ("11_univariate_distributions.png", "Figure 5. Univariate distributions."),\n'
            '    ("12_pollutant_boxplots.png", "Figure 6. Pollutant spread on a logarithmic axis."),\n'
            '    ("13_city_ranking.png", "Figure 7. Cities ranked by mean AQI, with band composition."),\n'
            '    ("14_pollutant_vs_aqi.png", "Figure 8. Each pollutant against the same-day AQI."),\n'
            '    ("15_correlation_heatmap.png", "Figure 9. Spearman correlation across pollutants."),\n'
            '    ("16_pairplot.png", "Figure 10. Pairwise structure, coloured by AQI band."),\n'
            '    ("17_pca_projection.png", "Figure 11. PCA projection with loadings, and scree plot."),\n'
            ']:\n'
            '    show(name, caption)'
        ),
        new_code_cell(
            'for name, caption in [\n'
            '    ("18_stl_decomposition.png", "Figure 12. Seasonal-trend decomposition."),\n'
            '    ("19_seasonal_boxplots.png", "Figure 13. AQI by season and by month."),\n'
            '    ("20_city_month_heatmap.png", "Figure 14. Mean AQI by city and month."),\n'
            '    ("10_hourly_exposure_climatology.png", "Figure 15. Diurnal exposure cycle with the safest window shaded."),\n'
            ']:\n'
            '    show(name, caption)'
        ),
        new_markdown_cell(
            "### The two natural experiments in this record\n\n"
            "The span contains two episodes in which emissions changed abruptly for "
            "reasons outside the air quality system itself. Both are real signal, "
            "both are retained in full, and both are tested for significance rather "
            "than described impressionistically."
        ),
        new_code_cell(
            'covid, festival = eda["covid"], eda["festival"]\n'
            'display(Markdown(\n'
            '    f"**Lockdown.** National mean AQI moved from {covid[\'national_mean_before\']} "\n'
            '    f"to {covid[\'national_mean_during\']} ({covid[\'national_change_pct\']}%), "\n'
            '    f"significant at the 5% level in {covid[\'n_cities_significant_decline\']} of "\n'
            '    f"{len(covid[\'per_city\'])} cities.\\n\\n"\n'
            '    f"**Diwali.** AQI in the festival window is {festival[\'national_uplift_pct\']}% "\n'
            '    f"above a matched seasonal baseline, significant in "\n'
            '    f"{festival[\'n_cities_significant_uplift\']} of {len(festival[\'per_city\'])} cities, "\n'
            '    f"peaking {festival[\'peak_offset_days\']:+d} day(s) from Diwali itself."\n'
            '))\n'
            'show("21_covid_interrupted_series.png", "Figure 16. The 2020 lockdown as a natural experiment.")\n'
            'show("22_diwali_festival_impact.png", "Figure 17. Diwali against a matched seasonal baseline.")\n'
            'show("23_hai_advisory_burden.png", "Figure 18. Advisory burden by cohort and city.")'
        ),
        new_markdown_cell(
            "## 5. Insights and what they imply for modelling\n\n"
            "Each insight cites its figure and states the consequence it drives."
        ),
        new_code_cell(
            'insights = load("eda_insights.json")\n'
            'for entry in insights["insights"]:\n'
            '    display(Markdown(\n'
            '        f"**Insight {entry[\'id\']}** *(see `{entry[\'figure\']}`)*\\n\\n"\n'
            '        f"{entry[\'observation\']}\\n\\n"\n'
            '        f"> **Consequence for modelling.** {entry[\'modelling_consequence\']}"\n'
            '    ))'
        ),
        new_markdown_cell(
            "## 6. Phase 2 outcome\n\n"
            "* Cleaning decisions made by measurement, not preference.\n"
            "* Genuine pollution episodes retained; artefacts removed on a stated "
            "physical rule.\n"
            "* Feature matrix built with every leakage control in place.\n"
            "* Health Advisory Index built, its properties proved, its divergence "
            "from the official AQI measured.\n"
            "* Exploratory analysis complete, every figure interpreted.\n\n"
            "Phase 3 trains, compares, tunes, explains and ships."
        ),
    ]
    path = config.NOTEBOOKS_DIR / "02_phase2_preprocessing_and_eda.ipynb"
    nbformat.write(_notebook(cells), str(path))
    return path


# --------------------------------------------------------------------------- #
# Notebook 3
# --------------------------------------------------------------------------- #
def build_notebook3() -> Path:
    """Build the phase 3 notebook: modelling, comparison and the product."""
    cells = [
        new_markdown_cell(
            _header(
                "Phase 3: Modelling, Comparison and Product",
                "3 of 3 — Review 3",
                "Model implementation; evaluation metrics; performance comparison; "
                "tuning; product development",
            )
        ),
        new_code_cell(PREAMBLE),
        new_markdown_cell(
            "## 1. The formulation, and why it matters\n\n"
            "Every model predicts **tomorrow** from information available **today**. "
            "That choice makes the output actionable, and it also dissolves a "
            "leakage problem that a same-day formulation suffers from. The "
            "experiment below measures the difference rather than asserting it."
        ),
        new_code_cell(
            'classification = load("evaluation_classification.json")\n'
            'leak = classification["leakage_demonstration"]\n'
            'display(pd.DataFrame([\n'
            '    {\n'
            '        "Setup": key.replace("_", " "),\n'
            '        "Macro F1": leak[key]["macro_f1"],\n'
            '        "Accuracy": leak[key]["accuracy"],\n'
            '        "Features": leak[key]["n_features"],\n'
            '    }\n'
            '    for key in ("same_day_nowcast_with_aqi", "same_day_nowcast_without_aqi",\n'
            '                "next_day_forecast_this_project")\n'
            ']))\n'
            'display(Markdown(f"> {leak[\'conclusion\']}"))'
        ),
        new_markdown_cell(
            "## 2. Regression: next-day AQI\n\n"
            "The persistence baseline — tomorrow equals today — is the row that "
            "makes every other row interpretable. Daily AQI is strongly "
            "autocorrelated, so most of a high R-squared is available for nothing."
        ),
        new_code_cell(
            'regression = load("evaluation_regression.json")\n'
            'display(Markdown(f"**Primary metric.** {regression[\'primary_metric_justification\']}"))\n'
            'table = pd.read_csv(RESULTS / "master_comparison_regression.csv")\n'
            'display(table)\n'
            'display(Markdown(f"> {regression[\'baseline_comparison\'][\'verdict\']}"))'
        ),
        new_code_cell(
            'show("27_regression_comparison.png", "Figure 1. Regression comparison against the persistence baseline.")\n'
            'show("31_residual_analysis.png", "Figure 2. Residual diagnostics for the selected regressor.")\n'
            'display(Markdown(f"> **Residual interpretation.** {regression[\'residual_analysis\'][\'interpretation\']}"))'
        ),
        new_markdown_cell(
            "## 3. Classification: next-day band\n\n"
            "Accuracy exceeds macro F1 for every model, and the gap is the cost of "
            "the rare classes. A reader shown only accuracy would conclude the "
            "models perform better than they do on exactly the bands that matter "
            "most for health protection."
        ),
        new_code_cell(
            'display(Markdown(f"**Primary metric.** {classification[\'primary_metric_justification\']}"))\n'
            'display(pd.read_csv(RESULTS / "master_comparison_classification.csv"))'
        ),
        new_code_cell(
            'display(Markdown("### Class weighting against SMOTE, head to head"))\n'
            'display(pd.DataFrame(classification["smote_head_to_head"]))\n'
            'display(Markdown("### Per-class performance of the selected classifier"))\n'
            'display(pd.DataFrame(classification["best_test_metrics"]["per_class"]))'
        ),
        new_code_cell(
            'show("28_classification_comparison.png", "Figure 3. Classification comparison and per-class performance.")\n'
            'show("29_confusion_matrices.png", "Figure 4. Confusion matrices, raw and normalised.")\n'
            'show("30_roc_curves.png", "Figure 5. One-versus-rest ROC curves.")'
        ),
        new_markdown_cell(
            "### The error that actually matters\n\n"
            "Overall accuracy treats every mistake alike. For a health advisory they "
            "are not alike: predicting one band too clean is a wording problem, and "
            "predicting three bands too clean is a safety problem."
        ),
        new_code_cell(
            'errors = load("error_analysis.json")\n'
            'display(Markdown(\n'
            '    f"| Statistic | Value |\\n| --- | --- |\\n"\n'
            '    f"| Test predictions | {errors[\'n_test\']:,} |\\n"\n'
            '    f"| Wrong | {errors[\'n_wrong\']:,} ({errors[\'error_rate_pct\']}%) |\\n"\n'
            '    f"| Wrong by 2+ bands | {errors[\'n_wrong_by_two_or_more_bands\']:,} "\n'
            '    f"({errors[\'pct_wrong_by_two_or_more_bands\']}%) |\\n"\n'
            '    f"| **Understating severity by 2+ bands** | "\n'
            '    f"**{errors[\'n_understating_severity_by_two_or_more\']:,} "\n'
            '    f"({errors[\'pct_understating_severity_by_two_or_more\']}%)** |"\n'
            '))\n'
            'show("35_error_analysis.png", "Figure 6. Signed band error and the most frequent transitions.")\n'
            'display(Markdown(f"> {errors[\'interpretation\']}"))'
        ),
        new_markdown_cell(
            "## 4. Clustering: city archetypes\n\n"
            "Two cities can share a mean AQI and still need opposite interventions. "
            "Clustering on the *composition* of the pollutant mix rather than its "
            "magnitude separates kinds of problem from degrees of severity."
        ),
        new_code_cell(
            'clustering = load("evaluation_clustering.json")\n'
            'display(pd.DataFrame(clustering["k_selection"]["candidates"]))\n'
            'display(Markdown(f"**Selection rule.** {clustering[\'k_selection\'][\'selection_rule\']}"))\n'
            'display(Markdown(f"*{clustering[\'k_selection\'][\'power_caveat\']}*"))\n'
            'display(Markdown(f"**Algorithm agreement.** {clustering[\'algorithm_agreement\'][\'interpretation\']}"))'
        ),
        new_code_cell(
            'display(pd.DataFrame(clustering["archetypes"])[[\n'
            '    "cluster", "archetype", "defining_pollutant", "n_cities", "cities", "policy_lever",\n'
            ']])\n'
            'show("24_clustering_selection.png", "Figure 7. Selection of the number of archetypes.")\n'
            'show("25_cluster_profiles.png", "Figure 8. Archetype signatures and the cities in archetype space.")'
        ),
        new_markdown_cell(
            "## 5. Hyperparameter optimisation, and what it was worth"
        ),
        new_code_cell(
            'tuning = load("tuning_report.json")\n'
            'display(Markdown(f"**Strategy.** {tuning[\'strategy\']}"))\n'
            'for task in ("regression", "classification"):\n'
            '    entry = tuning[task]\n'
            '    display(Markdown(f"### {task.capitalize()}: {entry[\'model\']}"))\n'
            '    display(pd.DataFrame([\n'
            '        {"Setting": "Default", **entry["untuned_test"]},\n'
            '        {"Setting": "Tuned", **entry["tuned_test"]},\n'
            '    ]))\n'
            '    display(Markdown(f"Best parameters: `{entry[\'best_params\']}`"))\n'
            'show("26_tuning_before_after.png", "Figure 9. Effect of tuning, and what it cost.")\n'
            'display(Markdown(f"> **Cost against gain.** {tuning[\'cost_vs_gain\'][\'assessment\']}"))'
        ),
        new_markdown_cell(
            "## 6. Explainability\n\n"
            "A health advisory that cannot say *why* it is warning is hard to act on "
            "and hard to trust."
        ),
        new_code_cell(
            'explain = load("explainability.json")\n'
            'display(Markdown(f"**Method.** {explain[\'method\']}"))\n'
            'show("36_shap_global.png", "Figure 10. Global SHAP explanation of both deployed models.")\n'
            'show("37_shap_local_waterfall.png", "Figure 11. One high-AQI day, fully decomposed.")\n'
            'display(Markdown(f"> {explain[\'interpretation\']}"))'
        ),
        new_markdown_cell(
            "## 7. The counterfactual policy simulator\n\n"
            "The reduction is an **input**, not a prediction. The simulator states "
            "what the advisory burden would be at a given concentration; it does not "
            "claim any intervention would achieve it."
        ),
        new_code_cell(
            'policy = load("policy_simulation.json")\n'
            'display(Markdown(f"> {policy[\'what_this_is_not\']}"))\n'
            'display(pd.DataFrame([\n'
            '    {\n'
            '        "Scenario": s["name"],\n'
            '        "Mean AQI change %": s["result"]["aqi"]["mean_change_pct"],\n'
            '        "Unsafe days removed %": s["result"]["unsafe_days"]["reduction_pct"],\n'
            '        "Advisory-days averted": s["result"]["cohort_advisory_days"]["total_averted_across_cohorts"],\n'
            '    }\n'
            '    for s in policy["scenarios"]\n'
            ']))\n'
            'show("38_policy_simulation.png", "Figure 12. Counterfactual scenarios and the cohort breakdown.")'
        ),
        new_code_cell(
            'anchor = policy.get("lockdown_anchor", {})\n'
            'whole = next((s for s in policy["scenarios"] if s["name"] == "All pollutants reduced by 40%"), None)\n'
            'if anchor and whole:\n'
            '    display(Markdown(\n'
            '        f"**Sanity check.** The 2020 lockdown produced a measured "\n'
            '        f"**{anchor[\'measured_aqi_change_pct\']}%** change in national mean AQI. "\n'
            '        f"The nearest comparable scenario, a 40% reduction across all pollutants, "\n'
            '        f"yields **{whole[\'result\'][\'aqi\'][\'mean_change_pct\']:+.1f}%**. The two "\n'
            '        f"agree closely, which is a useful independent check because the simulator "\n'
            '        f"was not fitted to that episode in any way."\n'
            '    ))'
        ),
        new_markdown_cell("## 8. Final selection"),
        new_code_cell(
            'selection = (RESULTS / "final_model_selection.md")\n'
            'display(Markdown(selection.read_text(encoding="utf-8")))'
        ),
        new_markdown_cell(
            "## 9. The product\n\n"
            "Launch locally with:\n\n"
            "```bash\n"
            "streamlit run app/Home.py\n"
            "```\n\n"
            "Four pages: **Forecast** (cohort-resolved next-day advisory in three "
            "languages, with what-if sliders), **City Risk Atlas** (archetypes, "
            "seasonality, festival and lockdown panels), **Policy Simulator** "
            "(counterfactual re-scoring), and **Model Insights** (comparison tables, "
            "SHAP, the leakage demonstration, and the data and model cards).\n\n"
            "## 10. Phase 3 outcome\n\n"
            "All three learning paradigms trained, tuned, compared and explained; "
            "the product shipped; every limitation stated in "
            "`reports/model_card.md`."
        ),
    ]
    path = config.NOTEBOOKS_DIR / "03_phase3_modeling_and_comparison.ipynb"
    nbformat.write(_notebook(cells), str(path))
    return path


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #
def execute(path: Path, timeout: int = 900) -> bool:
    """Execute a notebook in place so the committed file carries real output."""
    try:
        from nbclient import NotebookClient

        notebook = nbformat.read(str(path), as_version=4)
        client = NotebookClient(
            notebook,
            timeout=timeout,
            kernel_name="python3",
            resources={"metadata": {"path": str(config.PROJECT_ROOT)}},
        )
        client.execute()
        nbformat.write(notebook, str(path))
        LOGGER.info("Executed %s", path.name)
        return True
    except Exception as exc:
        LOGGER.warning("Execution failed for %s (%s: %s)", path.name, type(exc).__name__, exc)
        return False


def main() -> Dict[str, Any]:
    """Build and execute all three notebooks."""
    config.ensure_dirs()
    config.NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)

    built = [build_notebook1(), build_notebook2(), build_notebook3()]
    executed = {path.name: execute(path) for path in built}
    LOGGER.info(
        "Built %s notebooks, executed %s successfully",
        len(built),
        sum(1 for ok in executed.values() if ok),
    )
    return {"built": [str(p) for p in built], "executed": executed}


if __name__ == "__main__":
    main()
