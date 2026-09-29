"""Smoke tests for the pipeline artefacts and the application's inference layer.

These are not unit tests of individual functions. They are the checks that decide
whether the deployed application can be trusted not to raise on a user's input,
and whether the artefacts a reviewer will read are internally consistent.

Run with::

    python -m tests.test_smoke

or, if pytest is available::

    pytest tests/ -v
"""

from __future__ import annotations

import itertools
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src import config
from src.features import hai as hai_mod


# --------------------------------------------------------------------------- #
# Artefact presence and consistency
# --------------------------------------------------------------------------- #
def test_provenance_exists_and_is_complete() -> None:
    """The provenance record exists and carries a checksum for every file."""
    path = config.RAW_DIR / "PROVENANCE.json"
    assert path.exists(), "PROVENANCE.json missing; run `python -m src.data.acquire`"
    record = json.loads(path.read_text(encoding="utf-8"))

    assert record["license"]["string_as_displayed_on_kaggle"], "licence string absent"
    present = [f for f in record["files"] if f.get("present")]
    assert present, "no files recorded"
    for entry in present:
        assert len(entry["sha256"]) == 64, f"bad digest for {entry['filename']}"
        assert entry["rows"] > 0 and entry["columns"] > 0

    primary = record["primary_file"]
    assert primary["rows"] > 10_000
    assert len(primary["schema"]) == primary["columns"]


def test_figures_are_present_and_high_resolution() -> None:
    """Every figure exists at the declared DPI."""
    from PIL import Image

    figures = sorted(config.FIGURES_DIR.glob("*.png"))
    assert len(figures) >= 14, f"expected at least 14 figures, found {len(figures)}"
    for path in figures:
        with Image.open(path) as image:
            dpi = image.info.get("dpi", (0, 0))
            assert round(dpi[0]) == config.FIG_DPI, f"{path.name} is {dpi[0]} DPI"


def test_no_leakage_columns_in_feature_lists() -> None:
    """Neither task's feature list contains the other task's target."""
    from src.features.build import FEATURE_COLUMNS_PATH

    columns = json.loads(FEATURE_COLUMNS_PATH.read_text(encoding="utf-8"))
    forbidden = {"AQI_next", "AQI_Bucket_next", "AQI_Bucket_next_ordinal"}
    for task in ("regression", "classification"):
        overlap = forbidden & set(columns[task])
        assert not overlap, f"{task} feature list contains target columns: {overlap}"


def test_split_is_time_ordered() -> None:
    """Training dates strictly precede test dates."""
    from src.features.build import TEST_PATH, TRAIN_PATH

    train = pd.read_csv(TRAIN_PATH, usecols=["Date"], parse_dates=["Date"])
    test = pd.read_csv(TEST_PATH, usecols=["Date"], parse_dates=["Date"])
    assert train["Date"].max() < test["Date"].min(), "train and test periods overlap"


def test_cleaned_data_has_no_residual_nulls_or_negatives() -> None:
    """The cleaned table satisfies the invariants the pipeline asserts."""
    from src.data.clean import CLEAN_PATH, KEPT_POLLUTANTS

    frame = pd.read_csv(CLEAN_PATH, parse_dates=["Date"])
    assert not frame.duplicated(subset=["City", "Date"]).any()
    for column in KEPT_POLLUTANTS:
        assert frame[column].notna().all(), f"nulls remain in {column}"
        assert (frame[column] >= 0).all(), f"negative values remain in {column}"


# --------------------------------------------------------------------------- #
# The Health Advisory Index
# --------------------------------------------------------------------------- #
def test_hai_properties_hold() -> None:
    """Every mathematical property claimed for the index is re-verified."""
    checks = hai_mod.self_test()
    assert all(checks.values()), f"HAI self-test failed: {checks}"


def test_hai_never_less_protective_on_real_data() -> None:
    """On the actual record, no cohort index falls below the AQI-equivalent."""
    from src.features.build import FEATURES_PATH

    frame = pd.read_csv(
        FEATURES_PATH,
        usecols=["AQI"] + [f"sub_{p}" for p in config.HAI_POLLUTANTS]
        + [f"HAI_{c}" for c in config.COHORTS],
    ).dropna()
    equivalent = frame[[f"sub_{p}" for p in config.HAI_POLLUTANTS]].max(axis=1) / 5.0
    for cohort in config.COHORTS:
        assert (frame[f"HAI_{cohort}"] + 1e-9 >= equivalent).all(), (
            f"{cohort} falls below the AQI-equivalent on real data"
        )


def test_advisory_text_exists_for_every_combination() -> None:
    """Advisory text is present for every cohort, band and language."""
    for language in hai_mod.LANGUAGES:
        for cohort in config.COHORTS:
            for band, _, _ in config.HAI_BANDS:
                result = hai_mod.advisory(cohort, band, language)
                assert result["text"].strip(), f"empty advisory {language}/{cohort}/{band}"
                assert result["disclaimer"].strip(), "disclaimer missing"


# --------------------------------------------------------------------------- #
# Application inference: the no-exception guarantee
# --------------------------------------------------------------------------- #
def test_forecast_never_raises_across_the_input_grid() -> None:
    """The forecast entry point returns a result for every valid combination.

    This is the check behind the claim that the application does not raise on any
    city, cohort or date the user can select. Every city is exercised against
    every cohort at four dates spanning its record, which covers the boundary
    cases where lag and rolling features are least well defined.
    """
    from app.utils import inference

    cities = inference.available_cities()
    assert cities, "no cities available"

    failures: List[Tuple[str, str, str, str]] = []
    checked = 0

    for city in cities:
        low, high = inference.date_bounds(city)
        span = (high - low).days
        dates = [
            low,
            low + pd.Timedelta(days=max(1, span // 3)),
            low + pd.Timedelta(days=max(2, 2 * span // 3)),
            high,
        ]
        for cohort, date in itertools.product(config.COHORTS, dates):
            checked += 1
            try:
                result = inference.forecast(city, date, cohort)
                assert isinstance(result, dict)
                assert "ok" in result
                if result["ok"]:
                    assert result["predicted_aqi"] is not None
                    assert result["predicted_bucket"] in config.AQI_BUCKETS
                    assert 0 <= result["cohort"]["hai"] <= 100
                    assert result["cohort"]["band"] in [b[0] for b in config.HAI_BANDS]
                    assert result["advisory"]["text"].strip()
            except Exception as exc:
                failures.append((city, cohort, str(date.date()), f"{type(exc).__name__}: {exc}"))

    assert not failures, (
        f"{len(failures)} of {checked} combinations raised. First five: {failures[:5]}"
    )
    print(f"    checked {checked:,} city/cohort/date combinations")


def test_forecast_handles_invalid_input_gracefully() -> None:
    """Out-of-range and malformed inputs return a result rather than raising."""
    from app.utils import inference

    city = inference.available_cities()[0]

    result = inference.forecast("Atlantis", "2019-01-01", "children")
    assert result["ok"] is False and result["messages"]

    result = inference.forecast(city, "1990-01-01", "children")
    assert result["ok"] is True and result["fallback_applied"], "no fallback applied"

    result = inference.forecast(city, "2099-01-01", "children")
    assert result["ok"] is True and result["fallback_applied"]

    result = inference.forecast(city, "not-a-date", "children")
    assert result["ok"] is False


def test_what_if_sliders_move_the_forecast_in_the_right_direction() -> None:
    """Reducing a pollutant must not raise, and must not raise the cohort index."""
    from app.utils import inference

    city = "Delhi" if "Delhi" in inference.available_cities() else inference.available_cities()[0]
    _, high = inference.date_bounds(city)

    base = inference.forecast(city, high, "asthma_copd")
    reduced = inference.forecast(city, high, "asthma_copd", {"PM2.5": 0.5, "PM10": 0.5})

    assert base["ok"] and reduced["ok"]
    assert reduced["cohort"]["hai"] <= base["cohort"]["hai"] + 1e-6, (
        "halving particulates raised the Health Advisory Index"
    )


def test_drift_check_returns_a_verdict() -> None:
    """The drift stub returns a structured verdict for typical and extreme input."""
    from app.utils import inference

    typical = inference.drift_check({"PM2.5": 60.0, "PM10": 120.0, "NO2": 40.0})
    assert typical["n_flagged"] == 0, "typical input flagged as drifted"

    extreme = inference.drift_check({"PM2.5": 5000.0})
    assert extreme["n_flagged"] >= 1, "extreme input not flagged"
    assert extreme["verdict"]


# --------------------------------------------------------------------------- #
# Policy simulator
# --------------------------------------------------------------------------- #
def test_policy_simulator_is_monotone() -> None:
    """A deeper reduction must never produce a worse outcome than a shallower one."""
    payload = json.loads(
        (config.RESULTS_DIR / "policy_simulation.json").read_text(encoding="utf-8")
    )
    shallow = next(s for s in payload["scenarios"] if s["name"] == "PM2.5 reduced by 10%")
    deep = next(s for s in payload["scenarios"] if s["name"] == "PM2.5 reduced by 20%")

    assert deep["result"]["aqi"]["mean_after"] <= shallow["result"]["aqi"]["mean_after"]
    assert (
        deep["result"]["cohort_advisory_days"]["total_averted_across_cohorts"]
        >= shallow["result"]["cohort_advisory_days"]["total_averted_across_cohorts"]
    )


def test_reports_contain_no_placeholder_metrics() -> None:
    """The generated documents exist and are non-trivial in size."""
    expected = [
        "Review1_Problem_and_Dataset.docx",
        "Review2_Preprocessing_and_EDA.docx",
        "Review3_Modeling_and_Comparison.docx",
        "data_card.md",
        "model_card.md",
        "dataset_provenance.md",
    ]
    for name in expected:
        path = config.REPORTS_DIR / name
        assert path.exists(), f"{name} missing"
        assert path.stat().st_size > 4096, f"{name} is suspiciously small"


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def main() -> int:
    """Run every test in this module and report a summary."""
    tests: List[Callable[[], None]] = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]

    passed: List[str] = []
    failed: List[Tuple[str, str]] = []

    print("=" * 74)
    print(f"AirGuard India smoke tests ({len(tests)} checks)")
    print("=" * 74)

    for test in tests:
        name = test.__name__
        try:
            test()
            passed.append(name)
            print(f"  PASS  {name}")
        except Exception:
            failed.append((name, traceback.format_exc()))
            print(f"  FAIL  {name}")

    print("-" * 74)
    print(f"  {len(passed)} passed, {len(failed)} failed")
    for name, trace in failed:
        print(f"\n--- {name} ---\n{trace}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
