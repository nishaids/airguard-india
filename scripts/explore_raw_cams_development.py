"""Exploratory diagnostic: raw archived CAMS against measured station targets on development dates.

    python -m scripts.explore_raw_cams_development

This is NOT the primary experiment and selects nothing. It fits no model and
tunes nothing: it scores two fixed baselines that the locked protocol already
defines (B2 raw CAMS, matched and six-pollutant, and B1 persistence) on the
same station-days of the guarded development join, which ends before the
sealed final test by construction. It exists because the live product shows a
raw CAMS-based AQI to the public, and how far that number sits from measured
values is worth knowing now.

Censored Severe targets are lower bounds: they enter only the Severe counts,
never an error average. Output: results/research/extensions/raw_cams_development_diagnostic.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/research/extensions/raw_cams_development_diagnostic.json"
BANDS = [0, 50, 100, 200, 300, 400, np.inf]
POOR = 201
RNG_SEED = 20261020
BLOCK_DAYS = 7
REPLICATES = 2000


def band(values):
    return np.digitize(np.asarray(values, dtype=float), BANDS[1:-1], right=True)


def scores(pred, truth):
    error = pred - truth
    b_pred, b_true = band(pred), band(truth)
    polluted = truth >= POOR
    return {"n": int(len(truth)), "mae": round(float(np.abs(error).mean()), 2), "bias": round(float(error.mean()), 2),
            "rmse": round(float(np.sqrt((error ** 2).mean())), 2),
            "category_agreement": round(float((b_pred == b_true).mean()), 4),
            "within_one_category": round(float((np.abs(b_pred - b_true) <= 1).mean()), 4),
            "poor_or_worse_days": int(polluted.sum()),
            "poor_or_worse_under_warning": round(float((pred[polluted] < POOR).mean()), 4) if polluted.any() else None,
            "over_warning_on_cleaner_days": round(float((pred[~polluted] >= POOR).mean()), 4) if (~polluted).any() else None}


def block_bootstrap(frame, a, b):
    """Paired MAE difference (a minus b) with a seven-day moving-block bootstrap over dates."""
    daily = frame.assign(d=(frame[a] - frame.y_aqi).abs() - (frame[b] - frame.y_aqi).abs()).groupby("target_date").d.agg(["sum", "count"])
    sums, counts = daily["sum"].to_numpy(), daily["count"].to_numpy()
    n = len(daily)
    rng = np.random.default_rng(RNG_SEED)
    starts = np.arange(n - BLOCK_DAYS + 1)
    draws = []
    for _ in range(REPLICATES):
        picked = np.concatenate([np.arange(s, s + BLOCK_DAYS) for s in rng.choice(starts, size=int(np.ceil(n / BLOCK_DAYS)))])[:n]
        draws.append(sums[picked].sum() / counts[picked].sum())
    return {"mae_difference": round(float(sums.sum() / counts.sum()), 2),
            "interval_95": [round(float(np.percentile(draws, 2.5)), 2), round(float(np.percentile(draws, 97.5)), 2)],
            "dates": int(n), "block_days": BLOCK_DAYS, "replicates": REPLICATES, "seed": RNG_SEED}


def main():
    alignment = json.loads((ROOT / "results/research/cams_development_alignment.json").read_text(encoding="utf-8"))
    from src.research.calibration.primary_dataset import final_start
    from src.research.calibration.protocol import load
    frame = pd.read_parquet(ROOT / alignment["table"])
    assert pd.to_datetime(frame.target_date).max() < pd.Timestamp(final_start(load())), "sealed dates must not be present"

    exact = frame[frame.target_valid & ~frame.censored & frame.y_aqi.notna()]
    paired = exact.dropna(subset=["cams_aqi_frozen", "cams_six", "obs24_aqi"]).copy()
    paired["target_date"] = pd.to_datetime(paired.target_date)
    censored = frame[frame.target_valid & frame.censored]

    result = {
        "status": "EXPLORATORY_DEVELOPMENT_DIAGNOSTIC_NOT_PRIMARY",
        "generated_by": "scripts/explore_raw_cams_development.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "join_sha256": alignment["sha256"], "dates": [str(paired.target_date.min().date()), str(paired.target_date.max().date())],
        "model_fitting_performed": False, "selection_performed": False, "final_test_accessed": False,
        "population": "exact (uncensored) valid targets where matched CAMS, six-pollutant CAMS and persistence all exist",
        "overall": {
            "raw_cams_matched": scores(paired.cams_aqi_frozen.to_numpy(), paired.y_aqi.to_numpy()),
            "raw_cams_six_pollutant_as_displayed": scores(paired.cams_six.to_numpy(), paired.y_aqi.to_numpy()),
            "persistence_measured_24h": scores(paired.obs24_aqi.to_numpy(), paired.y_aqi.to_numpy()),
        },
        "paired_differences": {
            "matched_cams_minus_persistence": block_bootstrap(paired, "cams_aqi_frozen", "obs24_aqi"),
            "six_pollutant_minus_matched": block_bootstrap(paired, "cams_six", "cams_aqi_frozen"),
        },
        "by_region": {r: scores(g.cams_aqi_frozen.to_numpy(), g.y_aqi.to_numpy()) for r, g in paired.groupby("region") if len(g) >= 200},
        "by_month": {str(m): scores(g.cams_aqi_frozen.to_numpy(), g.y_aqi.to_numpy()) for m, g in paired.groupby(paired.target_date.dt.to_period("M"))},
        "mechanism": {
            "dominant_share_cams": {k: round(float(v), 4) for k, v in paired.cams_dominant_static_three.value_counts(normalize=True).items()},
            "dominant_share_measured": {k: round(float(v), 4) for k, v in paired.y_dominant.value_counts(normalize=True).items()},
            "mean_daily_concentration_ugm3": {p: {"cams": round(float(paired[f"cams_conc_{p}"].mean()), 1), "measured": round(float(paired[f"y_conc_{p}"].mean()), 1),
                                                  "ratio": round(float(paired[f"cams_conc_{p}"].mean() / paired[f"y_conc_{p}"].mean()), 2)}
                                              for p in ("PM2.5", "PM10", "O3")},
            "matched_equals_six_pollutant_share": round(float(np.isclose(paired.cams_six, paired.cams_aqi_frozen).mean()), 4),
        },
        "censored_severe": {"days": int(len(censored)),
                            "matched_cams_below_401": int((censored.cams_aqi_frozen < 401).sum()),
                            "persistence_below_401": int((censored.obs24_aqi < 401).sum())},
        "caveats": ["February to early June only: no winter, few Poor-or-worse days",
                    "persistence uses the measured index at the issue cutoff and assumes a healthy feed (3 h latency)",
                    "this is a baseline diagnostic; the primary comparison on locked folds is still required"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    # The public site cites a few of these numbers; it reads them from this generated file only.
    o, m = result["overall"], result["mechanism"]
    public = {"source": "results/research/extensions/raw_cams_development_diagnostic.json", "status": result["status"],
              "period": result["dates"], "station_days": o["raw_cams_matched"]["n"],
              "raw_cams_mae": o["raw_cams_matched"]["mae"], "raw_cams_bias": o["raw_cams_matched"]["bias"],
              "persistence_mae": o["persistence_measured_24h"]["mae"],
              "ozone_ratio": m["mean_daily_concentration_ugm3"]["O3"]["ratio"],
              "ozone_dominant_share_cams": m["dominant_share_cams"].get("O3"), "ozone_dominant_share_measured": m["dominant_share_measured"].get("O3")}
    (ROOT / "webapp/app/lib/cams-diagnostic.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    o = result["overall"]
    print(json.dumps({k: {m: o[k][m] for m in ("n", "mae", "bias", "category_agreement", "poor_or_worse_days", "poor_or_worse_under_warning")} for k in o}))
    print(json.dumps(result["paired_differences"]))
    print(json.dumps(result["censored_severe"]))


if __name__ == "__main__":
    main()
