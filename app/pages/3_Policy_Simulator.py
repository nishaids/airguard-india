"""Counterfactual policy simulator with live re-scoring."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.simulate.policy import RESTRICTIVE_BANDS, UNSAFE_BUCKETS, rescore, simulate  # noqa: E402
from app.utils import inference  # noqa: E402

st.set_page_config(page_title="Policy Simulator · AirGuard India", page_icon="⚖", layout="wide")

DARK = {
    "template": "plotly_dark",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
}


@st.cache_data(show_spinner=False)
def baseline_scoring() -> pd.DataFrame:
    """Re-score the record with no reduction, for use as the comparison baseline."""
    return rescore(inference.load_clean(), {})


@st.cache_data(show_spinner="Re-scoring the historical record...")
def run_scenario(reductions_items: tuple) -> dict:
    """Run one scenario. The argument is a tuple so that it is hashable for caching."""
    reductions = dict(reductions_items)
    return simulate(inference.load_clean(), baseline_scoring(), reductions)


def main() -> None:
    """Render the policy simulator page."""
    st.title("Policy Simulator")
    st.caption(
        "Reduce pollutant concentrations and the entire historical record is "
        "re-scored from first principles: new sub-indices, new AQI, new bands, and "
        "new cohort Health Advisory Index values for all seven groups."
    )

    stored = inference.load_results("policy_simulation.json")

    with st.container(border=True):
        st.markdown("**What this tool does and does not claim**")
        st.markdown(
            stored.get(
                "what_this_is_not",
                "The reduction is an input supplied by the user, not a prediction.",
            )
        )

    st.subheader("Set the reduction")
    preset = st.selectbox(
        "Start from a preset",
        ["Custom"] + [s["name"] for s in stored.get("scenarios", [])],
        help="Presets match the scenarios reported in the Review 3 document.",
    )
    preset_values = {}
    if preset != "Custom":
        preset_values = next(
            s["reductions"] for s in stored["scenarios"] if s["name"] == preset
        )
        context = next(s["context"] for s in stored["scenarios"] if s["name"] == preset)
        st.info(context, icon="ℹ")

    slider_columns = st.columns(len(config.HAI_POLLUTANTS))
    reductions = {}
    for index, pollutant in enumerate(config.HAI_POLLUTANTS):
        default = int(round(100 * preset_values.get(pollutant, 0.0)))
        reductions[pollutant] = (
            slider_columns[index].slider(
                f"{pollutant}", 0, 80, default, step=5, format="%d%%",
                key=f"slider_{pollutant}_{preset}",
            )
            / 100.0
        )

    active = {k: v for k, v in reductions.items() if v > 0}
    if not active:
        st.info("Set at least one reduction above to run a scenario.", icon="👆")
        st.stop()

    result = run_scenario(tuple(sorted(active.items())))

    st.subheader("Result")
    metrics = st.columns(4)
    metrics[0].metric(
        "Mean AQI",
        f"{result['aqi']['mean_after']:.1f}",
        delta=f"{result['aqi']['mean_change_pct']:+.1f}%",
        delta_color="inverse",
    )
    metrics[1].metric(
        f"Unsafe days ({', '.join(UNSAFE_BUCKETS)})",
        f"{result['unsafe_days']['after']:,}",
        delta=f"-{result['unsafe_days']['removed']:,} ({result['unsafe_days']['reduction_pct']:.1f}%)",
        delta_color="inverse",
    )
    metrics[2].metric(
        "City-days improving a band",
        f"{result['band_migration']['days_improved']:,}",
        delta=f"{result['band_migration']['pct_improved']:.1f}% of days",
    )
    metrics[3].metric(
        "Cohort advisory-days averted",
        f"{result['cohort_advisory_days']['total_averted_across_cohorts']:,}",
        help=stored.get("advisory_day_definition", ""),
    )

    left, right = st.columns([1, 1])

    with left:
        st.markdown("**Cohort advisory burden, before and after**")
        cohorts = result["cohort_advisory_days"]["per_cohort"]
        labels = [c["cohort_label"] for c in cohorts]
        figure = go.Figure()
        figure.add_trace(
            go.Bar(
                y=labels, x=[c["restrictive_days_before"] for c in cohorts],
                name="Before", orientation="h", marker_color="#D55E00",
            )
        )
        figure.add_trace(
            go.Bar(
                y=labels, x=[c["restrictive_days_after"] for c in cohorts],
                name="After", orientation="h", marker_color="#009E73",
            )
        )
        figure.update_layout(
            **DARK, height=420, barmode="group",
            margin={"l": 10, "r": 20, "t": 30, "b": 10},
            xaxis_title=f"City-days in a restrictive band ({', '.join(RESTRICTIVE_BANDS)})",
            legend={"orientation": "h", "y": 1.1},
        )
        st.plotly_chart(figure, use_container_width=True)

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Cohort": c["cohort_label"],
                        "Before": c["restrictive_days_before"],
                        "After": c["restrictive_days_after"],
                        "Averted": c["advisory_days_averted"],
                        "Reduction (%)": c["reduction_pct"],
                        "Mean HAI before": c["mean_hai_before"],
                        "Mean HAI after": c["mean_hai_after"],
                    }
                    for c in cohorts
                ]
            ),
            hide_index=True, use_container_width=True,
        )

    with right:
        st.markdown("**Band migration**")
        migration = result["band_migration"]
        pie = go.Figure(
            go.Pie(
                labels=["Improved a band", "Unchanged", "Worsened"],
                values=[
                    migration["days_improved"],
                    migration["days_unchanged"],
                    migration["days_worsened"],
                ],
                marker_colors=["#009E73", "#56B4E9", "#D55E00"],
                hole=0.45, textinfo="label+percent",
            )
        )
        pie.update_layout(**DARK, height=330, margin={"l": 10, "r": 10, "t": 20, "b": 10},
                          showlegend=False)
        st.plotly_chart(pie, use_container_width=True)

        st.markdown("**Effect by city**")
        city_table = pd.DataFrame(result["per_city"]).sort_values(
            "pct_days_improved_band", ascending=False
        )
        city_figure = go.Figure(
            go.Bar(
                x=city_table["pct_days_improved_band"], y=city_table["city"],
                orientation="h", marker_color="#56B4E9",
                text=[f"{v:.0f}%" for v in city_table["pct_days_improved_band"]],
                textposition="outside",
            )
        )
        city_figure.update_layout(
            **DARK, height=420, margin={"l": 10, "r": 40, "t": 10, "b": 10},
            xaxis_title="Days improving at least one band (%)",
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(city_figure, use_container_width=True)

    anchor = stored.get("lockdown_anchor", {})
    if anchor:
        st.divider()
        st.subheader("Sanity check against a real emission reduction")
        columns = st.columns(3)
        columns[0].metric(
            "Measured lockdown effect", f"{anchor['measured_aqi_change_pct']:+.1f}%"
        )
        columns[1].metric("This scenario", f"{result['aqi']['mean_change_pct']:+.1f}%")
        columns[2].metric(
            "Cities with a significant measured decline",
            f"{anchor['cities_with_significant_decline']}",
        )
        st.caption(anchor["use"])

    st.divider()
    with st.expander("Scenarios reported in the Review 3 document"):
        if stored.get("scenarios"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Scenario": s["name"],
                            "Mean AQI change (%)": s["result"]["aqi"]["mean_change_pct"],
                            "Unsafe days removed (%)": s["result"]["unsafe_days"]["reduction_pct"],
                            "Advisory-days averted": s["result"]["cohort_advisory_days"][
                                "total_averted_across_cohorts"
                            ],
                        }
                        for s in stored["scenarios"]
                    ]
                ),
                hide_index=True, use_container_width=True,
            )


main()
