"""AirGuard India - application entry point.

Run from the repository root with::

    streamlit run app/Home.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# The application imports from src/, so the repository root must be importable
# regardless of the directory Streamlit was launched from.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from app.utils import inference  # noqa: E402
from app.utils.i18n import DISCLAIMER, LANGUAGES  # noqa: E402

st.set_page_config(
    page_title="AirGuard India",
    page_icon="🌬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def sidebar_language() -> str:
    """Render the language selector and return the chosen language code."""
    codes = list(LANGUAGES)
    choice = st.sidebar.selectbox(
        "Language / மொழி / भाषा",
        codes,
        format_func=lambda code: LANGUAGES[code],
        key="language",
    )
    return choice


def main() -> None:
    """Render the landing page."""
    language = sidebar_language()

    st.title("AirGuard India")
    st.caption(config.ACADEMIC["project_subtitle"])

    st.markdown(
        """
Air quality indices in India report a single number for an entire city, and the
same number for every person in it. A child with developing airways, a person
with COPD, a cardiac patient and a healthy adult receive identical advice,
although the documented exposure-response relationships differ substantially
between them. The index also describes the air that has already been breathed
rather than the air that is coming.

**AirGuard India addresses both gaps.** It forecasts the next day rather than
summarising today, and it reports a **vulnerability-weighted Health Advisory
Index** for seven population cohorts alongside the official AQI.
"""
    )

    regression = inference.load_results("evaluation_regression.json")
    classification = inference.load_results("evaluation_classification.json")
    divergence = inference.load_results("hai_divergence.json")
    clustering = inference.load_results("evaluation_clustering.json")

    if not regression or not classification:
        st.error(
            "Model results are not available. Run `python run_all.py` from the "
            "repository root to build the pipeline, then reload this page."
        )
        st.stop()

    st.subheader("Headline results")
    columns = st.columns(4)
    columns[0].metric(
        "Next-day AQI error (MAE)",
        f"{regression['best_test_metrics']['MAE']:.1f}",
        delta=f"{regression['baseline_comparison']['improvement_over_persistence_pct']:+.1f}% vs persistence",
        delta_color="inverse",
        help=(
            f"Mean absolute error of {regression['best_model']} on the held-out "
            f"test period. The comparison is against the naive forecast that "
            f"tomorrow equals today."
        ),
    )
    columns[1].metric(
        "Band classification (macro F1)",
        f"{classification['best_test_metrics']['macro_f1']:.3f}",
        delta=f"{classification['baseline_comparison']['improvement_over_persistence_pct']:+.1f}% vs persistence",
        help=(
            "Macro-averaged F1 across the six CPCB bands, chosen as the primary "
            "metric so that the rare Severe class cannot be ignored."
        ),
    )
    columns[2].metric(
        "Days where a cohort differs from AQI",
        f"{divergence.get('any_cohort_differs', {}).get('pct', 0):.1f}%",
        help=(
            "Share of city-days on which at least one cohort would receive a "
            "different advisory band from the one the official AQI implies."
        ),
    )
    columns[3].metric(
        "Cities covered",
        f"{len(inference.available_cities())}",
        help="Cities passing the completeness and volume gates described in the data card.",
    )

    st.divider()

    left, right = st.columns([1.4, 1])
    with left:
        st.subheader("What each page does")
        st.markdown(
            """
**Forecast** - pick a city, a date and a cohort. Returns tomorrow's predicted
AQI, the predicted band with the model's confidence, the cohort's Health
Advisory Index and band, the dominant pollutant, the cleanest outdoor window,
and plain-language advice in English, Tamil or Hindi. Includes what-if sliders.

**City Risk Atlas** - the pollution archetypes discovered without supervision,
the ranked risk table, the seasonal heatmap, and the festival and lockdown
panels.

**Policy Simulator** - reduce pollutants by a chosen proportion and see how many
city-days move to a safer band and how many cohort advisory-days are averted.

**Model Insights** - the full comparison tables, confusion matrices, SHAP
explanations, the leakage demonstration, and the data and model cards.
"""
        )

        if clustering:
            st.subheader("City archetypes")
            for entry in clustering["archetypes"]:
                st.markdown(
                    f"**{entry['archetype']}** ({entry['n_cities']} cities: "
                    f"{', '.join(entry['cities'])}) — {entry['policy_lever']}"
                )

    with right:
        st.subheader("Dataset and licence")
        provenance = {}
        provenance_path = config.RAW_DIR / "PROVENANCE.json"
        if provenance_path.exists():
            import json

            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

        if provenance:
            dataset = provenance["dataset"]
            licence = provenance["license"]
            primary = provenance["primary_file"]
            st.markdown(
                f"""
**{dataset['title_scraped']}**

| | |
| --- | --- |
| Source | {provenance['upstream_source']['organisation']} |
| Mirror | [Kaggle]({dataset['kaggle_url']}), uploader `{dataset['kaggle_uploader_handle']}` |
| Licence | **{licence['string_as_displayed_on_kaggle']}** |
| Verified live | {licence['verified_live']} |
| Records | {primary['rows']:,} city-days |
| Coverage | {primary['date_min']} to {primary['date_max']} |
| Cities in source | {primary['n_cities']} |

The licence string above was read directly from the dataset page at download
time and recorded in `data/raw/PROVENANCE.json` together with a SHA-256 checksum
for every file. Code in this repository is MIT licensed.
"""
            )
        else:
            st.info("Provenance record not found. Run `python -m src.data.acquire`.")

        models = inference.deployed_model_names()
        st.subheader("Models in use")
        st.markdown(
            f"- Regression: **{models['regression']}**\n"
            f"- Classification: **{models['classification']}**\n"
            f"- Clustering: **K-Means, k={clustering.get('selected_k', '?')}**"
        )

    st.divider()
    st.warning(f"**Important.** {DISCLAIMER[language]}", icon="⚠")

    st.caption(
        f"{config.ACADEMIC['course_code']} {config.ACADEMIC['course_name']} · "
        f"{config.ACADEMIC['institution']} · Repository: {config.REPO_URL}"
    )


main()
