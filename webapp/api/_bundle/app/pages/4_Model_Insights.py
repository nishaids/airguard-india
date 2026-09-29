"""Model insights: comparison tables, confusion matrices, SHAP, cards and limitations."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from app.utils import inference  # noqa: E402

st.set_page_config(page_title="Model Insights · AirGuard India", page_icon="🔍", layout="wide")

DARK = {
    "template": "plotly_dark",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
}

METRIC_GLOSSARY = {
    "MAE": "Mean absolute error. The average size of the miss, in AQI points. An MAE of 15 means the forecast is typically 15 AQI points away from what happened.",
    "RMSE": "Root mean squared error. Like MAE, but large misses count disproportionately, so it is sensitive to a handful of extreme days.",
    "R-squared": "The share of the variation in next-day AQI that the model accounts for. 1.0 is perfect; 0 is no better than always predicting the average.",
    "MAPE": "Mean absolute percentage error. The typical miss expressed as a percentage of the true value.",
    "Accuracy": "The share of days whose band was predicted exactly right. Misleading on its own here, because the bands are unevenly common.",
    "Macro F1": "The average F1 score across all six bands, giving each band equal weight no matter how rare. This is the primary metric, chosen so a model cannot score well by ignoring the rare Severe band.",
    "Weighted F1": "The same average, but weighted by how common each band is. Closer to accuracy in behaviour.",
    "Balanced accuracy": "The average recall across bands. Another way of refusing to let common bands dominate the score.",
    "Cohen's kappa": "Agreement corrected for the agreement that chance alone would produce. 0 is chance-level; 1 is perfect.",
    "ROC-AUC (OvR)": "For each band in turn, the probability that a randomly chosen day of that band is scored higher than a randomly chosen day that is not. 0.5 is random.",
    "Silhouette": "How well each city sits inside its own cluster compared with the nearest other cluster. Runs from -1 to 1; higher is better.",
    "Davies-Bouldin": "Average similarity between each cluster and the one most like it. Lower is better.",
    "Calinski-Harabasz": "Ratio of between-cluster to within-cluster dispersion. Higher is better.",
    "Persistence baseline": "The naive forecast that tomorrow equals today. Any model that cannot beat it has added nothing.",
    "Ordinal error": "How many severity bands away a wrong prediction landed. An error of one band is far less serious than an error of three.",
}


def load_table(name: str) -> pd.DataFrame:
    """Load a master comparison CSV, returning an empty frame if absent."""
    path = config.RESULTS_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def show_figure(name: str, caption: str = "") -> None:
    """Display a pipeline-generated figure if it exists."""
    path = config.FIGURES_DIR / name
    if path.exists():
        st.image(str(path), use_container_width=True)
        if caption:
            st.caption(caption)
    else:
        st.info(f"Figure {name} not found. Run `python run_all.py`.")


def main() -> None:
    """Render the model insights page."""
    st.title("Model Insights")

    regression = inference.load_results("evaluation_regression.json")
    classification = inference.load_results("evaluation_classification.json")
    clustering = inference.load_results("evaluation_clustering.json")
    tuning = inference.load_results("tuning_report.json")
    explain = inference.load_results("explainability.json")
    errors = inference.load_results("error_analysis.json")

    if not regression or not classification:
        st.error("Model results not found. Run `python run_all.py` first.")
        st.stop()

    tabs = st.tabs(
        [
            "Comparison",
            "Confusion and errors",
            "Explainability",
            "Tuning",
            "Leakage controls",
            "Metric glossary",
            "Data and model cards",
        ]
    )

    # ------------------------------------------------------------------ #
    with tabs[0]:
        st.subheader("Regression: next-day AQI value")
        st.caption(regression["primary_metric_justification"])
        table = load_table("master_comparison_regression.csv")
        if not table.empty:
            st.dataframe(
                table.style.highlight_min(subset=["Test MAE", "Test RMSE"], color="#1B4D3E")
                .highlight_max(subset=["Test R2"], color="#1B4D3E"),
                hide_index=True, use_container_width=True,
            )
        show_figure("27_regression_comparison.png")

        st.subheader("Classification: next-day AQI band")
        st.caption(classification["primary_metric_justification"])
        table = load_table("master_comparison_classification.csv")
        if not table.empty:
            st.dataframe(
                table.style.highlight_max(
                    subset=["Test macro F1", "Test accuracy", "F1 Severe"], color="#1B4D3E"
                ),
                hide_index=True, use_container_width=True,
            )
        show_figure("28_classification_comparison.png")

        st.subheader("Clustering: city archetypes")
        table = load_table("master_comparison_clustering.csv")
        if not table.empty:
            st.dataframe(table, hide_index=True, use_container_width=True)
        show_figure("24_clustering_selection.png")
        show_figure("25_cluster_profiles.png")

        st.subheader("Generalisation and learning behaviour")
        columns = st.columns(2)
        with columns[0]:
            show_figure("34_train_test_gap.png")
        with columns[1]:
            show_figure("32_learning_curves.png")

    # ------------------------------------------------------------------ #
    with tabs[1]:
        st.subheader("Confusion matrices")
        show_figure("29_confusion_matrices.png")

        st.subheader("Discrimination by class")
        show_figure("30_roc_curves.png")

        st.subheader("Residual diagnostics")
        show_figure("31_residual_analysis.png")
        st.markdown(f"**Interpretation.** {regression['residual_analysis']['interpretation']}")

        st.subheader("Error analysis")
        show_figure("35_error_analysis.png")
        if errors:
            columns = st.columns(4)
            columns[0].metric("Test predictions", f"{errors['n_test']:,}")
            columns[1].metric("Wrong", f"{errors['n_wrong']:,}", f"{errors['error_rate_pct']}%")
            columns[2].metric(
                "Wrong by 2+ bands",
                f"{errors['n_wrong_by_two_or_more_bands']:,}",
                f"{errors['pct_wrong_by_two_or_more_bands']}%",
            )
            columns[3].metric(
                "Understating severity by 2+ bands",
                f"{errors['n_understating_severity_by_two_or_more']:,}",
                f"{errors['pct_understating_severity_by_two_or_more']}%",
                help="The health-critical failure mode: told the air is better than it is.",
            )
            st.markdown(f"**Interpretation.** {errors['interpretation']}")
            st.markdown("**Most frequent misclassification transitions**")
            st.dataframe(
                pd.DataFrame(errors["most_frequent_transitions"]),
                hide_index=True, use_container_width=True,
            )

        st.subheader("Error by city")
        show_figure("33_per_city_error.png")

    # ------------------------------------------------------------------ #
    with tabs[2]:
        st.subheader("Why the model predicts what it predicts")
        if explain:
            st.markdown(f"**Method.** {explain['method']}")
            show_figure("36_shap_global.png")
            st.markdown(f"**Interpretation.** {explain['interpretation']}")

            st.subheader("A single day, decomposed")
            show_figure("37_shap_local_waterfall.png")
            local = explain["local_example"]
            st.markdown(
                f"On **{local['date']}** in **{local['city']}**, the model forecast "
                f"**{local['prediction']:.0f}** against an actual "
                f"**{local['actual']:.0f}**, starting from a base value of "
                f"{local['base_value']:.0f}."
            )
            st.dataframe(
                pd.DataFrame(local["top_contributions"]),
                hide_index=True, use_container_width=True,
            )
        else:
            st.info("Explainability results not found. Run `python -m src.models.explain`.")

    # ------------------------------------------------------------------ #
    with tabs[3]:
        st.subheader("Hyperparameter optimisation")
        if tuning:
            st.markdown(f"**Strategy.** {tuning['strategy']}")
            show_figure("26_tuning_before_after.png")

            columns = st.columns(2)
            with columns[0]:
                entry = tuning["regression"]
                st.markdown(f"**Regression: {entry['model']}**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"Setting": "Default", **entry["untuned_test"]},
                            {"Setting": "Tuned", **entry["tuned_test"]},
                        ]
                    )[["Setting", "MAE", "RMSE", "R2", "MAPE_pct"]],
                    hide_index=True, use_container_width=True,
                )
                st.json(entry["best_params"], expanded=False)
            with columns[1]:
                entry = tuning["classification"]
                st.markdown(f"**Classification: {entry['model']}**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"Setting": "Default", **entry["untuned_test"]},
                            {"Setting": "Tuned", **entry["tuned_test"]},
                        ]
                    ),
                    hide_index=True, use_container_width=True,
                )
                st.json(entry["best_params"], expanded=False)

            st.markdown("**Cost against gain**")
            st.info(tuning["cost_vs_gain"]["assessment"], icon="⏱")

            with st.expander("Search spaces and why each parameter was included"):
                for name, reason in tuning["search_space_rationale"].items():
                    st.markdown(f"- **{name}** — {reason}")
                st.markdown("**Exhaustive grid over the Ridge penalty**")
                st.dataframe(
                    pd.DataFrame(tuning["ridge_exhaustive"]["cv_curve"]),
                    hide_index=True, use_container_width=True,
                )
                st.caption(tuning["ridge_exhaustive"]["note"])
        else:
            st.info("Tuning results not found. Run `python -m src.models.tune`.")

    # ------------------------------------------------------------------ #
    with tabs[4]:
        st.subheader("Leakage: demonstrated, not merely asserted")
        leak = classification.get("leakage_demonstration", {})
        if leak:
            st.markdown(f"**Experiment.** {leak['experiment']}")
            rows = []
            for key in (
                "same_day_nowcast_with_aqi",
                "same_day_nowcast_without_aqi",
                "next_day_forecast_this_project",
            ):
                entry = leak[key]
                rows.append(
                    {
                        "Setup": key.replace("_", " "),
                        "Macro F1": entry["macro_f1"],
                        "Accuracy": entry["accuracy"],
                        "Features": entry["n_features"],
                        "Description": entry["description"],
                    }
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.error(leak["conclusion"], icon="🚨")

        features_report = inference.load_results("feature_engineering_report.json")
        if features_report:
            st.subheader("Every leakage control applied in this project")
            for name, description in features_report["leakage_controls"].items():
                st.markdown(f"**{name.capitalize()}.** {description}")

        cleaning = inference.load_results("cleaning_report.json")
        if cleaning:
            st.subheader("Imputation chosen by measurement")
            comparison = cleaning["imputation_comparison"]
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Strategy": r["strategy"],
                            "Causal": r["causal"],
                            "MAE / IQR": r["mean_mae_over_iqr"],
                            "KS statistic": r["mean_ks_statistic"],
                            "Mean |std shift| (%)": r["mean_abs_std_shift_pct"],
                        }
                        for r in comparison["results"]
                    ]
                ),
                hide_index=True, use_container_width=True,
            )
            st.markdown(f"**Selection.** {comparison['selection_rationale']}")

    # ------------------------------------------------------------------ #
    with tabs[5]:
        st.subheader("What each metric means, in plain language")
        for name, description in METRIC_GLOSSARY.items():
            st.markdown(f"**{name}.** {description}")

    # ------------------------------------------------------------------ #
    with tabs[6]:
        columns = st.columns(2)
        for column, name in zip(columns, ("data_card.md", "model_card.md")):
            path = config.REPORTS_DIR / name
            with column:
                if path.exists():
                    st.markdown(path.read_text(encoding="utf-8"))
                else:
                    st.info(f"{name} not found. Run `python run_all.py`.")


main()
