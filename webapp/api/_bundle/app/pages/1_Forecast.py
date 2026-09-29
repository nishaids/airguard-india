"""Next-day forecast with a cohort-specific health advisory."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.features import hai as hai_mod  # noqa: E402
from app.utils import inference  # noqa: E402
from app.utils.i18n import LANGUAGES, cohort_label, translate  # noqa: E402

st.set_page_config(page_title="Forecast · AirGuard India", page_icon="🌬", layout="wide")

#: Band colours, colour-blind safe and checked for contrast against the dark theme.
BAND_COLOUR = {
    "Low": "#009E73",
    "Moderate": "#F0E442",
    "High": "#E69F00",
    "Very High": "#D55E00",
    "Extreme": "#CC79A7",
}


def main() -> None:
    """Render the forecast page."""
    st.title("Next-day forecast")

    cities = inference.available_cities()
    if not cities:
        st.error("No data available. Run `python run_all.py` first.")
        st.stop()

    language = st.sidebar.selectbox(
        "Language / மொழி / भाषा", list(LANGUAGES), format_func=lambda c: LANGUAGES[c]
    )

    controls = st.columns([1, 1, 1.2, 1])
    city = controls[0].selectbox(translate("city", language), cities, index=cities.index("Delhi") if "Delhi" in cities else 0)
    cohort = controls[1].selectbox(
        translate("cohort", language),
        config.COHORTS,
        format_func=lambda c: cohort_label(c, language),
    )

    low, high = inference.date_bounds(city)
    chosen = controls[2].date_input(
        translate("date", language),
        value=high.date(),
        min_value=low.date(),
        max_value=high.date(),
    )
    controls[3].metric("Records available", f"{(high - low).days + 1:,} days")

    with st.expander(translate("what_if", language)):
        st.caption(
            "Reduce today's measured concentrations and watch the forecast and the "
            "advisory respond. Lag and rolling features are left untouched, because "
            "a what-if about today does not rewrite the preceding week."
        )
        slider_columns = st.columns(len(config.HAI_POLLUTANTS))
        adjustments = {
            pollutant: slider_columns[idx].slider(
                f"{pollutant} reduction", 0, 80, 0, step=5, format="%d%%"
            )
            / 100.0
            for idx, pollutant in enumerate(config.HAI_POLLUTANTS)
        }

    result = inference.forecast(city, chosen, cohort, adjustments)
    if not result["ok"]:
        for message in result["messages"]:
            st.warning(message)
        st.stop()

    for message in result["messages"]:
        st.info(message)

    applied = {k: v for k, v in result["what_if_applied"].items() if v}
    if applied:
        st.success(
            "What-if applied: "
            + ", ".join(f"{k} reduced {v:.0%}" for k, v in applied.items())
            + ". Figures below are counterfactual."
        )

    band = result["cohort"]["band"]
    colour = BAND_COLOUR.get(band, "#56B4E9")

    st.subheader(
        f"{translate('forecast_heading', language)} · {city} · "
        f"{result['forecast_date'].strftime('%d %B %Y')}"
    )

    metrics = st.columns(5)
    metrics[0].metric(translate("predicted_aqi", language), f"{result['predicted_aqi']:.0f}")
    metrics[1].metric(translate("predicted_band", language), result["predicted_bucket"])
    metrics[2].metric(
        translate("confidence", language),
        f"{result['confidence']:.0%}" if result["confidence"] is not None else "n/a",
    )
    metrics[3].metric(
        f"{translate('hai', language)} ({cohort_label(cohort, language)})",
        f"{result['cohort']['hai']:.0f}",
        help=result["cohort"]["rationale"],
    )
    metrics[4].metric(translate("dominant", language), result["cohort"]["dominant_pollutant"] or "n/a")

    st.markdown(
        f"""
<div style="background:{colour};color:#11151C;padding:16px 20px;border-radius:10px;
            font-size:1.05rem;line-height:1.55;margin:6px 0 14px 0;">
<strong style="font-size:1.2rem;">
{hai_mod.BAND_LABELS[language][band]} — {cohort_label(cohort, language)}
</strong><br>
{result['advisory']['text']}
</div>
""",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.5, 1])

    with left:
        st.markdown(f"**{translate('history', language)}**")
        frame = inference.history(city, result["date"], days=30)
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=frame["Date"], y=frame["AQI"], mode="lines+markers",
                name="Observed AQI", line={"color": "#56B4E9", "width": 2},
                marker={"size": 5},
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[result["forecast_date"]], y=[result["predicted_aqi"]], mode="markers",
                name="Forecast", marker={"size": 15, "color": "#D55E00", "symbol": "diamond"},
            )
        )
        if result["actual_next_aqi"] is not None:
            figure.add_trace(
                go.Scatter(
                    x=[result["forecast_date"]], y=[result["actual_next_aqi"]], mode="markers",
                    name="Actual (historical)",
                    marker={"size": 13, "color": "#009E73", "symbol": "circle-open",
                            "line": {"width": 3}},
                )
            )
        for name, low_edge, high_edge in config.AQI_BUCKET_BOUNDS[:-1]:
            figure.add_hline(
                y=high_edge, line_dash="dot", line_color="rgba(255,255,255,0.22)",
                annotation_text=name, annotation_position="right",
                annotation_font_size=9,
            )
        figure.update_layout(
            template="plotly_dark", height=380, margin={"l": 10, "r": 10, "t": 30, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend={"orientation": "h", "y": 1.12},
            yaxis_title="AQI", xaxis_title=None,
        )
        st.plotly_chart(figure, use_container_width=True)

        if result["bucket_distribution"]:
            st.markdown("**Predicted band probability**")
            ordered = [
                (b, result["bucket_distribution"].get(b, 0.0)) for b in config.AQI_BUCKETS
            ]
            bar = go.Figure(
                go.Bar(
                    x=[p for _, p in ordered], y=[b for b, _ in ordered], orientation="h",
                    marker_color=["#009E73", "#A8DDB5", "#F0E442", "#E69F00", "#D55E00", "#8B0000"],
                    text=[f"{p:.0%}" for _, p in ordered], textposition="outside",
                )
            )
            bar.update_layout(
                template="plotly_dark", height=260,
                margin={"l": 10, "r": 40, "t": 10, "b": 10},
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis={"range": [0, 1.12], "tickformat": ".0%"},
                yaxis={"categoryorder": "array", "categoryarray": config.AQI_BUCKETS[::-1]},
            )
            st.plotly_chart(bar, use_container_width=True)

    with right:
        st.markdown(f"**{translate('observed_today', language)}** ({result['date'].date()})")
        observed = pd.DataFrame(
            [
                {
                    "Pollutant": pollutant,
                    "Value": value,
                    "Unit": config.POLLUTANT_UNITS[pollutant],
                }
                for pollutant, value in result["observed_today"].items()
            ]
        )
        st.dataframe(observed, hide_index=True, use_container_width=True)

        if result["safe_window"]:
            st.info(
                f"**{translate('safe_window', language)}:** {result['safe_window']} "
                f"({result['season']})",
                icon="🕒",
            )

        st.markdown("**Health Advisory Index across all cohorts**")
        row = inference._row_for(result["city"], result["date"])
        adjusted, _ = inference.apply_what_if(row, adjustments)
        cohort_rows = []
        for candidate in config.COHORTS:
            snapshot = inference.cohort_snapshot(adjusted, candidate)
            cohort_rows.append(
                {
                    "Cohort": cohort_label(candidate, language),
                    "HAI": snapshot["hai"],
                    "Band": hai_mod.BAND_LABELS[language][snapshot["band"]],
                }
            )
        st.dataframe(
            pd.DataFrame(cohort_rows).sort_values("HAI", ascending=False),
            hide_index=True, use_container_width=True,
        )
        st.caption(
            "The spread across this table is the information a single "
            "population-average AQI discards."
        )

        drift = inference.drift_check(result["observed_today"])
        if drift["n_flagged"]:
            st.warning(
                f"**Input drift check.** {drift['verdict']} Flagged: "
                + ", ".join(
                    f"{f['pollutant']} (z = {f['z_score']})" for f in drift["flagged"]
                ),
                icon="📉",
            )

        if result["actual_next_aqi"] is not None:
            error = result["predicted_aqi"] - result["actual_next_aqi"]
            st.markdown(f"**{translate('actual', language)}**")
            st.markdown(
                f"Actual next-day AQI **{result['actual_next_aqi']:.0f}** "
                f"({result['actual_next_bucket']}). Forecast error "
                f"**{error:+.0f}** AQI points."
            )

    st.divider()
    st.caption(
        f"Regression: {result['models']['regression']} · "
        f"Classification: {result['models']['classification']}"
    )
    st.warning(f"**{translate('disclaimer', language)}.** {hai_mod.DISCLAIMER[language]}", icon="⚠")


main()
