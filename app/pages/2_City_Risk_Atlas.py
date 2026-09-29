"""City risk atlas: archetypes, ranked risk, seasonality and event panels."""

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

st.set_page_config(page_title="City Risk Atlas · AirGuard India", page_icon="🗺", layout="wide")

DARK = {
    "template": "plotly_dark",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
}


def main() -> None:
    """Render the atlas page."""
    st.title("City Risk Atlas")

    clustering = inference.load_results("evaluation_clustering.json")
    eda = inference.load_results("eda_statistics.json")
    divergence = inference.load_results("hai_divergence.json")
    clean = inference.load_clean()
    features = inference.load_features()

    if not clustering:
        st.error("Clustering results not found. Run `python run_all.py` first.")
        st.stop()

    tabs = st.tabs(
        ["Archetypes", "Ranked risk", "Seasonality", "Festival impact", "COVID-19 lockdown"]
    )

    # ------------------------------------------------------------------ #
    with tabs[0]:
        st.subheader("Pollution archetypes discovered without supervision")
        st.caption(
            "Cities are clustered on the *shape* of their pollutant mix rather than "
            "its magnitude, so the partition separates kinds of problem from degrees "
            "of severity. Each archetype maps to a different policy lever. The bars "
            "below show composition with each cluster's overall level removed, so a "
            "cluster that is simply cleaner across the board is not mislabelled as "
            "being led by any one species; the level is reported separately."
        )

        for index, entry in enumerate(clustering["archetypes"]):
            with st.container(border=True):
                left, right = st.columns([1, 2])
                left.markdown(
                    f"### {entry['archetype']}\n\n"
                    f"**Leading pollutant in the mix:** {entry['defining_pollutant']} "
                    f"(+{entry['defining_pollutant_shape_score']} against this "
                    f"cluster's own mean)\n\n"
                    f"**Overall burden level:** {entry['burden_level']} "
                    f"(z = {entry['mean_level_z']:+.2f} across cities)\n\n"
                    f"**Mean AQI:** {entry['mean_aqi']}\n\n"
                    f"**Cities ({entry['n_cities']}):** {', '.join(entry['cities'])}"
                )
                right.markdown(f"**Policy lever.** {entry['policy_lever']}")
                profile = pd.DataFrame(
                    [
                        {"Pollutant": p, "z-score": v}
                        for p, v in entry["composition_profile"].items()
                    ]
                )
                figure = go.Figure(
                    go.Bar(
                        x=profile["Pollutant"], y=profile["z-score"],
                        marker_color=config.PALETTE[index % len(config.PALETTE)],
                        text=[f"{v:+.2f}" for v in profile["z-score"]],
                        textposition="outside",
                    )
                )
                figure.update_layout(
                    **DARK, height=240, margin={"l": 10, "r": 10, "t": 10, "b": 10},
                    yaxis_title="Composition (z minus cluster mean)", showlegend=False,
                )
                right.plotly_chart(figure, use_container_width=True)

        with st.expander("How the number of archetypes was chosen"):
            st.markdown(clustering["k_selection"]["selection_rule"])
            st.markdown(f"_{clustering['k_selection']['power_caveat']}_")
            st.dataframe(
                pd.DataFrame(clustering["k_selection"]["candidates"]),
                hide_index=True, use_container_width=True,
            )
            st.markdown(
                f"**Agreement between algorithms.** "
                f"{clustering['algorithm_agreement']['interpretation']}"
            )
            st.markdown("**Alternative partitions considered**")
            for partition in clustering.get("alternative_partitions", []):
                marker = " — selected" if partition["selected"] else ""
                st.markdown(
                    f"*k = {partition['k']}{marker}* (silhouette {partition['silhouette']}): "
                    + "; ".join(
                        f"**{a['archetype']}** ({', '.join(a['cities'])})"
                        for a in partition["archetypes"]
                    )
                )

    # ------------------------------------------------------------------ #
    with tabs[1]:
        st.subheader("Ranked risk table")
        cluster_of = clustering["city_to_cluster"]
        archetype_of = {
            entry["cluster"]: entry["archetype"] for entry in clustering["archetypes"]
        }
        restrictive = ["High", "Very High", "Extreme"]

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
                "Days Severe (%)": round(
                    100.0 * float((group["AQI_Bucket"] == "Severe").mean()), 1
                ),
            }
            for cohort in ("healthy_adult", "children", "elderly_60plus", "cardiac"):
                entry[f"{config.COHORT_LABELS[cohort]} restricted (%)"] = round(
                    100.0 * float(group[f"HAI_{cohort}_band"].isin(restrictive).mean()), 1
                )
            rows.append(entry)

        table = pd.DataFrame(rows).sort_values("Mean AQI", ascending=False).reset_index(drop=True)
        st.dataframe(
            table.style.background_gradient(
                subset=["Mean AQI", "Days Poor or worse (%)", "Days Severe (%)"], cmap="YlOrRd"
            ),
            hide_index=True, use_container_width=True,
        )
        st.caption(
            "The last four columns show how the advisory burden differs by cohort "
            "within the same city. The gap between the healthy-adult column and the "
            "cardiac column is what a single population-average index hides."
        )

        if divergence:
            st.markdown("**Cohort divergence from the official AQI**")
            cohort_table = pd.DataFrame(
                [
                    {
                        "Cohort": entry["cohort_label"],
                        "Mean HAI": entry["mean_hai"],
                        "Mean AQI / 5": entry["mean_aqi_rescaled"],
                        "Mean uplift": entry["mean_uplift_points"],
                        "Band differs from AQI (%)": entry["pct_band_differs_from_aqi"],
                        "Stricter than AQI (%)": entry["pct_band_stricter_than_aqi"],
                    }
                    for entry in divergence["per_cohort"]
                ]
            )
            st.dataframe(cohort_table, hide_index=True, use_container_width=True)

    # ------------------------------------------------------------------ #
    with tabs[2]:
        st.subheader("Seasonality")
        work = clean.dropna(subset=["AQI"]).copy()
        work["month"] = work["Date"].dt.month
        pivot = work.pivot_table(index="City", columns="month", values="AQI", aggfunc="mean")
        pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]
        pivot.columns = [pd.Timestamp(2020, m, 1).strftime("%b") for m in pivot.columns]

        figure = px.imshow(
            pivot, color_continuous_scale="Viridis", aspect="auto",
            labels={"color": "Mean AQI"}, text_auto=".0f",
        )
        figure.update_layout(**DARK, height=460, margin={"l": 10, "r": 10, "t": 20, "b": 10})
        st.plotly_chart(figure, use_container_width=True)

        if eda:
            seasonal = eda["seasonal"]
            columns = st.columns(4)
            for index, season in enumerate(config.SEASON_ORDER):
                columns[index].metric(
                    season, f"{seasonal['seasonal_mean_aqi'].get(season, float('nan')):.0f}"
                )
            st.caption(
                f"Worst season: **{seasonal['worst_season']}**; cleanest: "
                f"**{seasonal['best_season']}**; a {seasonal['seasonal_ratio']}-fold swing "
                f"within the same cities. Northern cities show an extreme winter "
                f"maximum while southern coastal cities stay comparatively flat, which "
                f"is why the models carry a city interaction."
            )

        st.markdown("**Cleanest outdoor window by city and season**")
        windows = inference.load_results("safe_windows.json")
        if windows and not windows.get("degraded"):
            window_rows = []
            for city, entry in sorted(windows["per_city"].items()):
                row = {"City": city, "All year": entry["all_year"]["label"]}
                for season in config.SEASON_ORDER:
                    season_entry = entry.get("by_season", {}).get(season, {})
                    row[season] = season_entry.get("label", "n/a")
                row["Exposure cut (%)"] = entry["all_year"]["reduction_vs_day_mean_pct"]
                window_rows.append(row)
            st.dataframe(pd.DataFrame(window_rows), hide_index=True, use_container_width=True)
            st.caption(windows["why_not_the_supplied_hourly_aqi"]["explanation"])
        elif windows:
            st.warning(windows.get("reason", "Hourly data unavailable."))

    # ------------------------------------------------------------------ #
    with tabs[3]:
        st.subheader("Festival impact: the Diwali window")
        if not eda:
            st.info("Exploratory statistics not found.")
        else:
            festival = eda["festival"]
            columns = st.columns(3)
            columns[0].metric("National uplift", f"{festival['national_uplift_pct']:+.1f}%")
            columns[1].metric(
                "Cities with a significant uplift",
                f"{festival['n_cities_significant_uplift']} of {len(festival['per_city'])}",
            )
            columns[2].metric("Peak", f"{festival['peak_offset_days']:+d} days from Diwali")

            table = pd.DataFrame(festival["per_city"]).sort_values("uplift_pct", ascending=False)
            figure = go.Figure(
                go.Bar(
                    x=table["uplift_pct"], y=table["city"], orientation="h",
                    marker_color=[
                        "#D55E00" if s else "#56B4E9" for s in table["significant_at_0_05"]
                    ],
                    text=[f"{v:+.0f}%" for v in table["uplift_pct"]], textposition="outside",
                )
            )
            figure.update_layout(
                **DARK, height=440, margin={"l": 10, "r": 40, "t": 10, "b": 10},
                xaxis_title="Change against a matched seasonal baseline (%)",
                yaxis={"categoryorder": "total ascending"},
            )
            st.plotly_chart(figure, use_container_width=True)
            st.caption(
                f"Baseline: {festival['baseline_definition']}. Orange bars are "
                f"significant at the 5% level under a one-sided Mann-Whitney U test. "
                f"These spikes are real signal and are never removed as outliers; the "
                f"cleaning rule explicitly exempts documented event windows."
            )

            profile = pd.DataFrame(
                [{"Offset": int(k), "Mean AQI": v} for k, v in festival["profile"].items()]
            ).sort_values("Offset")
            line = go.Figure(
                go.Scatter(
                    x=profile["Offset"], y=profile["Mean AQI"], mode="lines+markers",
                    line={"color": "#56B4E9", "width": 2.5},
                )
            )
            line.add_vline(x=0, line_color="#D55E00", line_width=2, annotation_text="Diwali")
            line.update_layout(
                **DARK, height=320, margin={"l": 10, "r": 10, "t": 20, "b": 10},
                xaxis_title="Days from Diwali", yaxis_title="Mean AQI across cities and years",
            )
            st.plotly_chart(line, use_container_width=True)

    # ------------------------------------------------------------------ #
    with tabs[4]:
        st.subheader("The 2020 lockdown as a natural experiment")
        if not eda:
            st.info("Exploratory statistics not found.")
        else:
            covid = eda["covid"]
            columns = st.columns(4)
            columns[0].metric("National mean AQI before", f"{covid['national_mean_before']:.0f}")
            columns[1].metric("During lockdown", f"{covid['national_mean_during']:.0f}")
            columns[2].metric("Change", f"{covid['national_change_pct']:+.1f}%")
            columns[3].metric(
                "Cities with a significant decline",
                f"{covid['n_cities_significant_decline']} of {len(covid['per_city'])}",
            )

            table = pd.DataFrame(covid["per_city"]).sort_values("change_pct")
            figure = go.Figure(
                go.Bar(
                    x=table["change_pct"], y=table["city"], orientation="h",
                    marker_color=["#009E73" if v < 0 else "#D55E00" for v in table["change_pct"]],
                    text=[f"{v:+.0f}%" for v in table["change_pct"]], textposition="outside",
                )
            )
            figure.update_layout(
                **DARK, height=440, margin={"l": 10, "r": 40, "t": 10, "b": 10},
                xaxis_title="Change in mean AQI against the preceding 60 days (%)",
                yaxis={"categoryorder": "total descending"},
            )
            st.plotly_chart(figure, use_container_width=True)
            st.caption(
                f"{covid['test']} This episode is the only abrupt, broad emission "
                f"reduction in the record, and it is the empirical anchor against "
                f"which the Policy Simulator's whole-economy scenarios can be checked."
            )

            st.markdown(
                "**How this is handled in modelling.** 2020 is a genuine regime change "
                "rather than noise, so it is modelled with an explicit lockdown flag "
                "rather than deleted, and test-set error is reported separately for "
                "the lockdown period as a stress test. Both choices are recorded in "
                "`results/feature_engineering_report.json`."
            )


main()
