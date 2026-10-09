"""Tests for the live forecast path. No network: the modelled-data provider is replaced by a fake.

    python -m pytest tests/test_live.py -q
"""

from __future__ import annotations

import math
import re
import unittest
import urllib.parse
from unittest import mock

import pandas as pd

from src.deploy.serverless_inference import _feature_order
from src.ingestion.settings import TARGET_CITIES
from src.live import cams, features, forecast
from src.live import backtest

NOW = pd.Timestamp("2026-10-10 09:30")  # Indian local time
REFERENCE = dict(features.build_reference(), bias={"Delhi": {"PM2.5": 0.5, "PM10": 2.0, "O3": 0.25}}, bias_fitted_until="2026-10-07", bias_note="test correction")


def fake_provider(url: str):
    """Answer like Open-Meteo: one block per requested location, hourly, in local time."""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    locations = len(query["latitude"][0].split(","))
    past, ahead = int(query.get("past_days", ["20"])[0]), int(query.get("forecast_days", ["3"])[0])
    hours = pd.date_range(NOW.normalize() - pd.Timedelta(days=past), NOW.normalize() + pd.Timedelta(days=ahead) - pd.Timedelta(hours=1), freq="h")
    blocks = []
    for index in range(locations):
        wave = [1 + 0.3 * math.sin(i / 24 * 2 * math.pi + index) + 0.01 * (i // 24) for i in range(len(hours))]
        blocks.append(
            {
                "hourly": {
                    "time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours],
                    "pm2_5": [40 * w for w in wave],
                    "pm10": [90 * w for w in wave],
                    "nitrogen_dioxide": [25 * w for w in wave],
                    "sulphur_dioxide": [10 * w for w in wave],
                    "carbon_monoxide": [800 * w for w in wave],  # ug/m3, as the provider reports it
                    "ozone": [60 * w for w in wave],
                }
            }
        )
    return blocks if locations > 1 else blocks[0]


def run(cities=None, now=NOW, reference=REFERENCE, provider=fake_provider):
    with mock.patch.object(forecast, "load_reference", return_value=reference):
        return forecast.live_forecast(cities, now=now, fetcher=provider)


class ModelledDataTests(unittest.TestCase):
    def test_hourly_values_arrive_in_airguard_units(self):
        hourly = cams.fetch_hourly({"Delhi": TARGET_CITIES["Delhi"]}, past_days=2, forecast_days=1, fetcher=fake_provider)
        self.assertEqual(set(cams.POLLUTANTS) - set(hourly.columns), set())
        self.assertLess(hourly["CO"].max(), 5)  # 800 ug/m3 is 0.8 mg/m3, not 800
        self.assertEqual(hourly["City"].unique().tolist(), ["Delhi"])

    def test_a_refusal_from_the_provider_is_an_error_not_an_empty_table(self):
        with self.assertRaises(cams.LiveSourceError):
            cams.fetch_hourly({"Delhi": TARGET_CITIES["Delhi"]}, fetcher=lambda url: {"error": True, "reason": "Too many requests"})

    def test_daily_means_count_the_hours_still_to_come(self):
        hourly = cams.fetch_hourly({"Delhi": TARGET_CITIES["Delhi"]}, past_days=2, forecast_days=2, fetcher=fake_provider)
        daily = cams.daily_means(hourly, NOW).set_index("Date")
        self.assertEqual(daily.loc[NOW.normalize() - pd.Timedelta(days=1), "forecast_hours"], 0)
        self.assertEqual(daily.loc[NOW.normalize(), "forecast_hours"], 14)  # 10:00 to 23:00
        self.assertEqual(daily.loc[NOW.normalize() + pd.Timedelta(days=1), "forecast_hours"], 24)


class FeatureTests(unittest.TestCase):
    def history(self, correct=True):
        hourly = cams.fetch_hourly({"Delhi": TARGET_CITIES["Delhi"]}, past_days=20, forecast_days=2, fetcher=fake_provider)
        return features.prepare_history(cams.daily_means(hourly, NOW), REFERENCE, correct)

    def test_the_correction_scales_only_what_it_was_fitted_for_and_keeps_the_original(self):
        raw, fixed = self.history(False).iloc[-1], self.history(True).iloc[-1]
        self.assertAlmostEqual(fixed["PM2.5"], raw["PM2.5"] * 0.5)
        self.assertAlmostEqual(fixed["PM10"], raw["PM10"] * 2.0)
        self.assertAlmostEqual(fixed["NO2"], raw["NO2"])
        self.assertAlmostEqual(fixed["PM2.5_modelled"], raw["PM2.5"])

    def test_the_aqi_never_rests_on_a_filler_value(self):
        reference = dict(REFERENCE, typical_overall=dict(REFERENCE["typical_overall"], NH3=5000.0), typical_by_city_month={})
        hourly = cams.fetch_hourly({"Delhi": TARGET_CITIES["Delhi"]}, past_days=3, forecast_days=1, fetcher=fake_provider)
        prepared = features.prepare_history(cams.daily_means(hourly, NOW), reference)
        self.assertEqual(prepared["NH3"].iloc[0], 5000.0)  # the filler is absurd on purpose
        self.assertNotIn("sub_NH3", prepared.columns)
        self.assertLess(prepared["AQI"].max(), 400)

    def test_every_feature_the_model_wants_is_built(self):
        frame = features.build_features(self.history(), REFERENCE)
        today = frame.loc[frame["Date"] == NOW.normalize()].iloc[0]
        self.assertEqual(features.missing_features(today, _feature_order()["regression"]), [])
        self.assertEqual(today["days_since_start"], (NOW.normalize() - features.TRAINING_ORIGIN).days)
        self.assertEqual(today["City_target_enc"], REFERENCE["city_target_enc"]["Delhi"])


class ForecastTests(unittest.TestCase):
    def test_every_city_gets_a_labelled_forecast(self):
        result = run()
        self.assertTrue(result["ok"])
        self.assertEqual([c["city"] for c in result["cities"]], list(TARGET_CITIES))
        self.assertTrue(all(c["ok"] for c in result["cities"]))
        self.assertEqual(result["inputs"]["source_type"], "modelled")
        self.assertIn("not measured", result["inputs"]["label"])
        delhi = next(c for c in result["cities"] if c["city"] == "Delhi")
        self.assertEqual(delhi["today"]["date"], "2026-10-10")
        self.assertEqual(delhi["tomorrow"]["date"], "2026-10-11")
        self.assertTrue(0 < delhi["tomorrow"]["aqi"] < 600)
        self.assertEqual(len(delhi["cohorts"]), 7)
        self.assertEqual(delhi["today"]["forecast_hours_in_daily_mean"], 14)

    def test_the_provider_being_down_is_said_plainly_and_nothing_is_invented(self):
        def down(url):
            raise cams.LiveSourceError("Open-Meteo air-quality API unavailable (HTTP 429)")

        result = run(provider=down)
        self.assertFalse(result["ok"])
        self.assertIn("unavailable", result["message"])
        self.assertNotIn("cities", result)

    def test_an_unknown_city_is_refused(self):
        self.assertFalse(run(["Atlantis"])["ok"])

    def test_too_little_history_fails_that_city_without_a_number(self):
        def short(url):
            return fake_provider(re.sub(r"past_days=\d+", "past_days=3", url))

        city = run(["Delhi"], provider=short)["cities"][0]
        self.assertFalse(city["ok"])
        self.assertNotIn("tomorrow", city)

    def test_an_old_correction_is_dropped_and_the_page_is_told(self):
        fresh = run(["Delhi"])
        self.assertTrue(fresh["inputs"]["corrected_against_measurements"])
        self.assertEqual(fresh["inputs"]["correction_age_days"], 3)

        stale = run(["Delhi"], reference=dict(REFERENCE, bias_fitted_until="2026-08-01"))
        self.assertFalse(stale["inputs"]["corrected_against_measurements"])
        self.assertIn("No correction applied", stale["inputs"]["correction_note"])
        used = stale["cities"][0]["today"]
        self.assertEqual(used["concentrations"], used["concentrations_before_correction"])

    def test_the_likely_range_comes_from_tested_errors_and_prefers_the_citys_own(self):
        spread = {"q10": -10.0, "q90": 30.0, "by_city": {"Delhi": {"q10": -50.0, "q90": 100.0, "n": 40}}}
        result = run(["Delhi", "Chennai"], reference=dict(REFERENCE, backtest={"error_quantiles": spread}))
        delhi, chennai = result["cities"]
        self.assertAlmostEqual(delhi["tomorrow"]["likely_range"][1] - delhi["tomorrow"]["aqi"], 50.0, places=0)
        self.assertAlmostEqual(chennai["tomorrow"]["likely_range"][1] - chennai["tomorrow"]["aqi"], 10.0, places=0)
        self.assertIsNone(run(["Delhi"], reference=dict(REFERENCE, backtest=None))["cities"][0]["tomorrow"]["likely_range"])


class BacktestTests(unittest.TestCase):
    def test_a_correction_factor_is_the_ratio_of_medians_and_needs_enough_days(self):
        days = pd.date_range("2026-09-01", periods=20)
        modelled = pd.DataFrame({"City": "Delhi", "Date": days, "PM2.5": 100.0, "PM10": 50.0, "O3": 80.0})
        measured = pd.DataFrame({"City": "Delhi", "Date": days, "PM2.5_measured": 50.0, "PM10_measured": 100.0, "O3_measured": 20.0})
        self.assertEqual(backtest.fit_factors(modelled, measured), {"Delhi": {"PM2.5": 0.5, "PM10": 2.0, "O3": 0.25}})
        self.assertEqual(backtest.fit_factors(modelled.head(5), measured.head(5)), {})

    def test_monitors_are_averaged_into_one_city_value_and_an_aqi(self):
        rows = [
            {"City": "Delhi", "station": s, "pollutant": p, "Date": "2026-10-01", "value": v, "coverage": 100.0}
            for s, values in (("a", {"PM2.5": 40.0, "PM10": 100.0, "O3": 30.0}), ("b", {"PM2.5": 80.0, "PM10": 200.0, "O3": 50.0}))
            for p, v in values.items()
        ]
        city = backtest.measured_city_days(pd.DataFrame(rows)).iloc[0]
        self.assertEqual((city["PM2.5_measured"], city["PM10_measured"], city["monitors"]), (60.0, 150.0, 2))
        self.assertAlmostEqual(city["AQI_measured"], 133.3, places=0)  # PM10 of 150 is the larger sub-index


if __name__ == "__main__":
    unittest.main()
