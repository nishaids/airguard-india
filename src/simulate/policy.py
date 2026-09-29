"""Counterfactual policy simulator: emission reductions re-scored on the record.

What the simulator does
-----------------------
Given a proportional reduction in one or more pollutants, the historical record
is re-scored from first principles: reduced concentrations produce new CPCB
sub-indices, a new AQI, a new AQI bucket, and new cohort Health Advisory Index
values and bands. The simulator then reports how many city-days move to a safer
band and, more usefully, how many **cohort advisory-days are averted**, meaning
days on which a specific vulnerable group would no longer be told to restrict
outdoor activity.

Why this is a defensible counterfactual, and what it is not
------------------------------------------------------------
The mapping from concentration to index is a published deterministic function,
so re-scoring under reduced concentrations involves no model and no extrapolation
and carries no statistical uncertainty. That part is arithmetic.

What the simulator does **not** claim is that any particular policy would produce
the assumed reduction. The reduction is the user's input, not an output. The
tool answers "if concentrations fell by this much, what would the health advisory
burden become", which is the question a planner needs when comparing targets; it
does not answer "will this intervention deliver that reduction".

Two further limitations are stated because they bound the interpretation:

* **Atmospheric chemistry is not simulated.** Ozone in particular is a secondary
  pollutant formed from nitrogen oxides and volatile organic compounds, and under
  some urban conditions reducing NOx *raises* local ozone. The simulator applies
  the requested reduction to each pollutant independently and does not model that
  coupling. Ozone-led scenarios should therefore be read with more caution than
  particulate-led ones.
* **The 2020 lockdown provides an empirical anchor.** That episode delivered an
  abrupt, large, economy-wide emission reduction, and the measured effect on the
  AQI is reported in ``results/eda_statistics.json``. It is the closest thing in
  this record to a real-world validation of a reduction scenario, and the
  simulator's output for a comparable reduction can be checked against it.

Outputs
-------
``results/policy_simulation.json``
``reports/figures/38_policy_simulation.png``

Run with::

    python -m src.simulate.policy
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src import config
from src.data.clean import CLEAN_PATH
from src.features import hai as hai_mod

LOGGER = config.get_logger(__name__)

RESULTS_PATH = config.RESULTS_DIR / "policy_simulation.json"

#: Bands at which a cohort is advised to restrict outdoor activity.
RESTRICTIVE_BANDS: List[str] = ["High", "Very High", "Extreme"]

#: Buckets treated as unsafe for the band-migration count.
UNSAFE_BUCKETS: List[str] = ["Poor", "Very Poor", "Severe"]

#: Scenarios evaluated for the report. The application exposes arbitrary sliders.
SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "PM2.5 reduced by 10%",
        "reductions": {"PM2.5": 0.10},
        "context": "A modest fine-particulate reduction, of the order achievable by fuel-quality and fleet measures over a few years.",
    },
    {
        "name": "PM2.5 reduced by 20%",
        "reductions": {"PM2.5": 0.20},
        "context": "The scale of reduction targeted by the National Clean Air Programme for participating cities.",
    },
    {
        "name": "PM2.5 and PM10 reduced by 20%",
        "reductions": {"PM2.5": 0.20, "PM10": 0.20},
        "context": "Combined combustion and dust control, addressing both particulate fractions together.",
    },
    {
        "name": "PM2.5 and PM10 reduced by 30%",
        "reductions": {"PM2.5": 0.30, "PM10": 0.30},
        "context": "An ambitious particulate programme sustained over a decade.",
    },
    {
        "name": "NO2 reduced by 30%",
        "reductions": {"NO2": 0.30},
        "context": "Traffic demand management and tightened in-use vehicle emission testing.",
    },
    {
        "name": "All pollutants reduced by 20%",
        "reductions": {p: 0.20 for p in config.HAI_POLLUTANTS},
        "context": "A broad economy-wide reduction, comparable in breadth to the 2020 lockdown though far smaller in depth.",
    },
    {
        "name": "All pollutants reduced by 40%",
        "reductions": {p: 0.40 for p in config.HAI_POLLUTANTS},
        "context": "Approximately the depth of reduction observed during the 2020 national lockdown, applied to the whole record.",
    },
]


def rescore(frame: pd.DataFrame, reductions: Dict[str, float]) -> pd.DataFrame:
    """Apply proportional reductions and recompute every index from first principles.

    Parameters
    ----------
    frame:
        Cleaned daily table carrying raw pollutant concentrations.
    reductions:
        Mapping of pollutant name to the proportion removed, so ``0.2`` means a
        20 per cent reduction.

    Returns
    -------
    pandas.DataFrame
        A copy with reduced concentrations, recomputed sub-indices, a recomputed
        AQI and bucket, and recomputed cohort HAI values and bands.
    """
    out = frame.copy()
    for pollutant, fraction in reductions.items():
        if pollutant in out.columns:
            out[pollutant] = out[pollutant] * (1.0 - float(fraction))

    out = hai_mod.compute_sub_indices(out)
    out["AQI_sim"] = hai_mod.recompute_aqi(out)
    out["AQI_Bucket_sim"] = hai_mod.bucket_from_aqi(out["AQI_sim"].to_numpy())
    for cohort in config.COHORTS:
        values = hai_mod.compute_hai(out, cohort)
        out[f"HAI_{cohort}_sim"] = values
        out[f"HAI_{cohort}_band_sim"] = hai_mod.band_of(values.to_numpy())
    return out


def simulate(
    frame: pd.DataFrame, baseline: pd.DataFrame, reductions: Dict[str, float]
) -> Dict[str, Any]:
    """Evaluate one scenario against the baseline re-scoring.

    The baseline is itself produced by :func:`rescore` with no reduction applied,
    so both sides of the comparison are computed by identical code. Comparing a
    simulated series against the dataset's own supplied AQI would confound the
    scenario effect with the reconstruction gap documented in
    ``src/features/build.py``.
    """
    simulated = rescore(frame, reductions)
    valid = baseline["AQI_sim"].notna() & simulated["AQI_sim"].notna()
    n = int(valid.sum())

    base_aqi = baseline.loc[valid, "AQI_sim"]
    sim_aqi = simulated.loc[valid, "AQI_sim"]

    base_bucket = baseline.loc[valid, "AQI_Bucket_sim"]
    sim_bucket = simulated.loc[valid, "AQI_Bucket_sim"]
    ordinal = config.AQI_BUCKET_ORDINAL
    base_ordinal = base_bucket.map(ordinal)
    sim_ordinal = sim_bucket.map(ordinal)

    improved = int((sim_ordinal < base_ordinal).sum())
    unchanged = int((sim_ordinal == base_ordinal).sum())
    worsened = int((sim_ordinal > base_ordinal).sum())

    unsafe_before = int(base_bucket.isin(UNSAFE_BUCKETS).sum())
    unsafe_after = int(sim_bucket.isin(UNSAFE_BUCKETS).sum())

    cohort_effects: List[Dict[str, Any]] = []
    total_averted = 0
    for cohort in config.COHORTS:
        before = baseline.loc[valid, f"HAI_{cohort}_band_sim"].isin(RESTRICTIVE_BANDS)
        after = simulated.loc[valid, f"HAI_{cohort}_band_sim"].isin(RESTRICTIVE_BANDS)
        averted = int((before & ~after).sum())
        created = int((~before & after).sum())
        total_averted += averted
        cohort_effects.append(
            {
                "cohort": cohort,
                "cohort_label": config.COHORT_LABELS[cohort],
                "restrictive_days_before": int(before.sum()),
                "restrictive_days_after": int(after.sum()),
                "advisory_days_averted": averted,
                "advisory_days_created": created,
                "net_averted": averted - created,
                "reduction_pct": round(
                    100.0 * (int(before.sum()) - int(after.sum())) / max(int(before.sum()), 1), 2
                ),
                "mean_hai_before": round(float(baseline.loc[valid, f"HAI_{cohort}_sim"].mean()), 3),
                "mean_hai_after": round(float(simulated.loc[valid, f"HAI_{cohort}_sim"].mean()), 3),
            }
        )

    per_city: List[Dict[str, Any]] = []
    for city in sorted(frame["City"].unique()):
        mask = valid & (frame["City"] == city)
        if int(mask.sum()) < 30:
            continue
        city_base = baseline.loc[mask, "AQI_Bucket_sim"].map(ordinal)
        city_sim = simulated.loc[mask, "AQI_Bucket_sim"].map(ordinal)
        per_city.append(
            {
                "city": city,
                "n_days": int(mask.sum()),
                "mean_aqi_before": round(float(baseline.loc[mask, "AQI_sim"].mean()), 2),
                "mean_aqi_after": round(float(simulated.loc[mask, "AQI_sim"].mean()), 2),
                "days_improved_band": int((city_sim < city_base).sum()),
                "pct_days_improved_band": round(
                    100.0 * float((city_sim < city_base).mean()), 2
                ),
            }
        )

    return {
        "reductions": reductions,
        "n_city_days": n,
        "aqi": {
            "mean_before": round(float(base_aqi.mean()), 2),
            "mean_after": round(float(sim_aqi.mean()), 2),
            "mean_change": round(float(sim_aqi.mean() - base_aqi.mean()), 2),
            "mean_change_pct": round(
                100.0 * float(sim_aqi.mean() - base_aqi.mean()) / float(base_aqi.mean()), 2
            ),
            "median_before": round(float(base_aqi.median()), 2),
            "median_after": round(float(sim_aqi.median()), 2),
        },
        "band_migration": {
            "days_improved": improved,
            "days_unchanged": unchanged,
            "days_worsened": worsened,
            "pct_improved": round(100.0 * improved / n, 2),
        },
        "unsafe_days": {
            "definition": f"AQI bucket in {UNSAFE_BUCKETS}",
            "before": unsafe_before,
            "after": unsafe_after,
            "removed": unsafe_before - unsafe_after,
            "reduction_pct": round(
                100.0 * (unsafe_before - unsafe_after) / max(unsafe_before, 1), 2
            ),
        },
        "cohort_advisory_days": {
            "definition": f"HAI band in {RESTRICTIVE_BANDS}",
            "total_averted_across_cohorts": total_averted,
            "per_cohort": cohort_effects,
        },
        "per_city": per_city,
    }


def plot_simulation(payload: Dict[str, Any]) -> str:
    """Render the scenario comparison and the distribution shift of the headline case."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    scenarios = payload["scenarios"]
    names = [s["name"] for s in scenarios]
    unsafe_removed = [s["result"]["unsafe_days"]["reduction_pct"] for s in scenarios]
    averted = [
        s["result"]["cohort_advisory_days"]["total_averted_across_cohorts"] for s in scenarios
    ]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6.2))

    y = np.arange(len(names))
    bars = axes[0].barh(y, unsafe_removed, color=config.PALETTE[2])
    axes[0].bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8.5)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(names, fontsize=8)
    axes[0].set_xlabel("Reduction in unsafe city-days (%)")
    axes[0].set_xlim(0, max(unsafe_removed) * 1.28 if max(unsafe_removed) else 1)
    axes[0].spines[["top", "right"]].set_visible(False)
    axes[0].set_title(
        f"Unsafe days removed\n(bucket in {', '.join(UNSAFE_BUCKETS)})",
        fontsize=10.5, loc="left",
    )

    bars = axes[1].barh(y, averted, color=config.PALETTE[0])
    axes[1].bar_label(bars, fmt="%,.0f", padding=3, fontsize=8.5)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([])
    axes[1].set_xlabel("Cohort advisory-days averted (summed over seven cohorts)")
    axes[1].set_xlim(0, max(averted) * 1.3 if max(averted) else 1)
    axes[1].spines[["top", "right"]].set_visible(False)
    axes[1].set_title(
        "Health benefit in advisory-days\n"
        "One advisory-day is one cohort, in one city, on one day, no longer told to "
        "restrict activity.",
        fontsize=10.5, loc="left",
    )

    headline = payload["headline_scenario"]
    cohorts = headline["result"]["cohort_advisory_days"]["per_cohort"]
    labels = [c["cohort_label"] for c in cohorts]
    before = [c["restrictive_days_before"] for c in cohorts]
    after = [c["restrictive_days_after"] for c in cohorts]
    y2 = np.arange(len(labels))
    height = 0.38
    b1 = axes[2].barh(y2 - height / 2, before, height, label="Before", color=config.PALETTE[1])
    b2 = axes[2].barh(y2 + height / 2, after, height, label="After", color=config.PALETTE[2])
    axes[2].bar_label(b1, fmt="%,.0f", padding=2, fontsize=7.5)
    axes[2].bar_label(b2, fmt="%,.0f", padding=2, fontsize=7.5)
    axes[2].set_yticks(y2)
    axes[2].set_yticklabels(labels, fontsize=8)
    axes[2].set_xlabel("City-days in a restrictive advisory band")
    axes[2].set_xlim(0, max(before) * 1.3)
    axes[2].legend(frameon=False, fontsize=9, loc="lower right")
    axes[2].spines[["top", "right"]].set_visible(False)
    axes[2].set_title(
        f"Headline scenario by cohort:\n{headline['name']}",
        fontsize=10.5, loc="left",
    )

    anchor = payload.get("lockdown_anchor", {})
    anchor_text = (
        f" For reference, the 2020 national lockdown produced a measured "
        f"{abs(anchor.get('measured_aqi_change_pct', 0)):.0f}% fall in mean AQI."
        if anchor
        else ""
    )
    fig.suptitle(
        "Figure 38. Counterfactual emission-reduction scenarios, re-scored across "
        f"{scenarios[0]['result']['n_city_days']:,} city-days.\n"
        "The reduction is an input, not a prediction: the simulator states what the "
        "advisory burden would be at a given concentration, not whether any policy "
        f"would achieve it.{anchor_text}",
        fontsize=11.5, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    path = config.FIGURES_DIR / "38_policy_simulation.png"
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", path.name)
    return path.name


def main() -> Dict[str, Any]:
    """Run every declared scenario and write the simulation report."""
    config.set_global_seed()
    config.ensure_dirs()

    frame = pd.read_csv(CLEAN_PATH, parse_dates=["Date"])
    baseline = rescore(frame, {})
    LOGGER.info("Baseline re-scored: %s city-days", f"{int(baseline['AQI_sim'].notna().sum()):,}")

    scenarios: List[Dict[str, Any]] = []
    for scenario in SCENARIOS:
        result = simulate(frame, baseline, scenario["reductions"])
        scenarios.append({**scenario, "result": result})
        LOGGER.info(
            "%-38s | mean AQI %6.1f -> %6.1f (%+.1f%%) | unsafe days -%5.1f%% | "
            "advisory-days averted %s",
            scenario["name"],
            result["aqi"]["mean_before"],
            result["aqi"]["mean_after"],
            result["aqi"]["mean_change_pct"],
            result["unsafe_days"]["reduction_pct"],
            f"{result['cohort_advisory_days']['total_averted_across_cohorts']:,}",
        )

    headline = next(s for s in scenarios if s["name"] == "PM2.5 and PM10 reduced by 20%")

    anchor: Dict[str, Any] = {}
    eda_path = config.RESULTS_DIR / "eda_statistics.json"
    if eda_path.exists():
        eda = json.loads(eda_path.read_text(encoding="utf-8"))
        anchor = {
            "event": "2020 national lockdown, phases 1 to 4",
            "measured_aqi_change_pct": eda["covid"]["national_change_pct"],
            "measured_mean_before": eda["covid"]["national_mean_before"],
            "measured_mean_during": eda["covid"]["national_mean_during"],
            "cities_with_significant_decline": eda["covid"]["n_cities_significant_decline"],
            "use": (
                "The lockdown is the only episode in this record that delivered an "
                "abrupt, broad emission reduction, so it is the closest available "
                "empirical check on a whole-economy scenario. The simulator's "
                "'all pollutants reduced by 40%' case is the nearest comparator."
            ),
        }

    payload: Dict[str, Any] = {
        "generated_by": "src/simulate/policy.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": (
            "Each scenario applies a proportional reduction to the historical "
            "concentrations and recomputes the CPCB sub-indices, the AQI, the AQI "
            "bucket and every cohort HAI value and band from first principles. The "
            "baseline is produced by the same code path with a zero reduction, so "
            "both sides of every comparison are computed identically."
        ),
        "what_this_is_not": (
            "The reduction is an input supplied by the user, not a prediction. The "
            "simulator states what the advisory burden would be at a given "
            "concentration; it does not claim that any particular intervention "
            "would achieve that concentration. Atmospheric chemistry is not "
            "simulated: each pollutant is reduced independently, so ozone-led "
            "scenarios in particular should be read with caution, because reducing "
            "nitrogen oxides can raise local ozone under some urban conditions."
        ),
        "restrictive_bands": RESTRICTIVE_BANDS,
        "unsafe_buckets": UNSAFE_BUCKETS,
        "advisory_day_definition": (
            "One advisory-day is one cohort, in one city, on one day, moved out of "
            "a restrictive HAI band. Summing across the seven cohorts gives the "
            "total advisory-day burden averted."
        ),
        "scenarios": scenarios,
        "headline_scenario": headline,
        "lockdown_anchor": anchor,
    }

    plot_simulation(payload)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    LOGGER.info("Wrote %s", RESULTS_PATH.name)
    return payload


if __name__ == "__main__":
    main()
