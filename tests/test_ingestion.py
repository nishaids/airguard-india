"""Tests for live ingestion.

No test here touches a real provider: every HTTP exchange goes through a fake
transport. The one test that needs PostgreSQL is skipped unless a real
``DATABASE_URL`` is configured.

Run with::

    python -m pytest tests/test_ingestion.py -q
"""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from src.ingestion import cpcb, db, firms, matching, openaq, run, units, validation, weather
from src.ingestion import settings as settings_mod
from src.ingestion.base import Batch, CredentialMissing
from src.ingestion.http import HttpClient, HttpError, Response
from src.ingestion.schemas import (
    AirQualityObservation,
    Freshness,
    IngestionRun,
    QualityState,
    RunStatus,
    SourceType,
    Station,
    ValueKind,
    ensure_utc,
    utc_now,
)

ROOT = Path(__file__).resolve().parents[1]
FAKE = {
    "DATA_GOV_API_KEY": "FAKEDATAGOVKEY0123456789",
    "OPENAQ_API_KEY": "FAKEOPENAQKEY0123456789",
    "NASA_FIRMS_MAP_KEY": "0123456789abcdef0123456789abcdef",
    "DATABASE_URL": "postgresql://postgres.fakeref:FAKEDBPASSWORD@fake.pooler.example.com:5432/postgres",
}
SETTINGS = settings_mod.Settings(http_max_retries=2, http_backoff_seconds=1.5)
NOW = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)


def ok(payload, headers=None, status=200):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return Response(status, headers or {}, text)


class Scripted:
    """A transport that replays queued replies and records what it was asked."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, url, params, headers, timeout):
        self.calls.append({"url": url, "params": dict(params or {}), "headers": dict(headers or {})})
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply(url, params) if callable(reply) else reply


def client(*replies):
    sleeps = []
    transport = Scripted(*replies)
    http = HttpClient(SETTINGS, transport=transport, sleep=sleeps.append)
    return http, transport, sleeps


def observation(**overrides):
    base = dict(
        source="OpenAQ", source_type=SourceType.MEASURED, source_station_id="42", pollutant="PM2.5",
        raw_pollutant="pm25", observed_at=NOW - timedelta(minutes=30), retrieved_at=NOW, raw_value=55.0,
        raw_unit="µg/m³", value_kind=ValueKind.CONCENTRATION, averaging_period="native",
        latitude=28.6, longitude=77.2, station_name="Test", city="Delhi",
    )
    base.update(overrides)
    return AirQualityObservation(**base)


CPCB_PAYLOAD = {
    "title": "Real time Air Quality Index from various locations",
    "org": ["Ministry of Environment, Forest and Climate Change", "Central Pollution Control Board"],
    "updated_date": "2026-10-08T05:35:00Z",
    "total": 3,
    "field": [{"id": f} for f in ("country", "state", "city", "station", "last_update", "latitude", "longitude", "pollutant_id", "pollutant_min", "pollutant_max", "pollutant_avg")],
    "records": [
        {"country": "India", "state": "Delhi", "city": "Delhi", "station": "ITO, Delhi - DPCC", "last_update": "08-10-2026 11:00:00",
         "latitude": "28.6316", "longitude": "77.2494", "pollutant_id": "PM2.5", "pollutant_min": "41", "pollutant_max": "163", "pollutant_avg": "97"},
        {"country": "India", "state": "Delhi", "city": "Delhi", "station": "ITO, Delhi - DPCC", "last_update": "08-10-2026 11:00:00",
         "latitude": "28.6316", "longitude": "77.2494", "pollutant_id": "OZONE", "pollutant_min": "NA", "pollutant_max": "NA", "pollutant_avg": "NA"},
        {"country": "India", "state": "Delhi", "city": "Delhi", "station": "ITO, Delhi - DPCC", "last_update": "08-10-2026 11:00:00",
         "latitude": "28.6316", "longitude": "77.2494", "pollutant_id": "CO", "pollutant_min": "1", "pollutant_max": "9", "pollutant_avg": "-4"},
    ],
}

OPENAQ_LOCATION = {
    "id": 8118, "name": "ITO, Delhi - CPCB", "locality": "Delhi", "timezone": "Asia/Kolkata",
    "country": {"id": 9, "code": "IN", "name": "India"}, "owner": {"id": 4, "name": "Unknown Governmental Organization"},
    "provider": {"id": 168, "name": "CPCB"}, "isMonitor": True, "isMobile": False,
    "coordinates": {"latitude": 28.6317, "longitude": 77.2495},
    "sensors": [
        {"id": 23534, "name": "pm25 µg/m³", "parameter": {"id": 2, "name": "pm25", "units": "µg/m³", "displayName": "PM2.5"}},
        {"id": 23535, "name": "co µg/m³", "parameter": {"id": 4, "name": "co", "units": "µg/m³", "displayName": "CO"}},
        {"id": 23536, "name": "relativehumidity %", "parameter": {"id": 98, "name": "relativehumidity", "units": "%", "displayName": "RH"}},
    ],
    "datetimeLast": {"utc": "2026-10-08T05:30:00Z", "local": "2026-10-08T11:00:00+05:30"},
}
OPENAQ_LATEST = {
    "meta": {"page": 1, "limit": 100, "found": 3},
    "results": [
        {"datetime": {"utc": "2026-10-08T05:30:00Z", "local": "2026-10-08T11:00:00+05:30"}, "value": 88.0,
         "coordinates": {"latitude": 28.6317, "longitude": 77.2495}, "sensorsId": 23534, "locationsId": 8118},
        {"datetime": {"utc": "2026-10-08T05:30:00Z", "local": "2026-10-08T11:00:00+05:30"}, "value": 1400.0,
         "coordinates": {"latitude": 28.6317, "longitude": 77.2495}, "sensorsId": 23535, "locationsId": 8118},
        {"datetime": {"utc": "2026-10-08T05:30:00Z", "local": "2026-10-08T11:00:00+05:30"}, "value": 61.0,
         "coordinates": {"latitude": 28.6317, "longitude": 77.2495}, "sensorsId": 23536, "locationsId": 8118},
    ],
}

FIRMS_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    "30.51234,75.81234,334.5,0.39,0.36,2026-10-08,730,N20,VIIRS,n,2.0NRT,295.1,6.42,D\n"
    "30.60000,75.90000,341.0,0.40,0.37,2026-10-08,731,N20,VIIRS,h,2.0NRT,296.0,12.9,D\n"
    ",75.9,341.0,0.40,0.37,2026-10-08,731,N20,VIIRS,h,2.0NRT,296.0,12.9,D\n"
)


# --------------------------------------------------------------------------- #
class UnitTests(unittest.TestCase):
    def test_identity_through_unit_aliases(self):
        self.assertEqual(units.normalise("PM2.5", 55.0, "µg/m³"), (55.0, "ug/m3", None))
        self.assertEqual(units.normalise("PM10", 55.0, "ug/m3")[0], 55.0)

    def test_carbon_monoxide_micrograms_become_milligrams(self):
        value, unit, note = units.normalise("CO", 1400.0, "µg/m³")
        self.assertAlmostEqual(value, 1.4)
        self.assertEqual((unit, note), ("mg/m3", None))

    def test_ppb_and_ppm_use_molar_mass_and_say_so(self):
        value, unit, note = units.normalise("NO2", 10.0, "ppb")
        self.assertAlmostEqual(value, 10.0 * 46.0055 / 24.45, places=6)
        self.assertEqual(unit, "ug/m3")
        self.assertIn("25 C", note)
        value, unit, _ = units.normalise("CO", 1.0, "ppm")
        self.assertAlmostEqual(value, 28.010 / 24.45, places=6)
        self.assertEqual(unit, "mg/m3")

    def test_refuses_to_guess(self):
        with self.assertRaises(units.UnsupportedUnit):
            units.normalise("PM2.5", 12.0, "ppb")  # particles have no molar mass
        with self.assertRaises(units.UnsupportedUnit):
            units.normalise("NO2", 12.0, "furlongs")
        with self.assertRaises(units.UnsupportedUnit):
            units.normalise("NO2", 12.0, None)

    def test_pollutant_names(self):
        self.assertEqual(units.canonical_pollutant("OZONE"), "O3")
        self.assertEqual(units.canonical_pollutant("pm25"), "PM2.5")
        self.assertIsNone(units.canonical_pollutant("relativehumidity"))


class TimestampTests(unittest.TestCase):
    def test_cpcb_local_time_is_converted_to_utc(self):
        self.assertEqual(cpcb.parse_timestamp("08-10-2026 11:00:00"), datetime(2026, 10, 8, 5, 30, tzinfo=timezone.utc))
        self.assertIsNone(cpcb.parse_timestamp("not a time"))

    def test_openaq_utc(self):
        parsed = openaq.parse_utc("2026-10-08T05:30:00Z")
        self.assertEqual(parsed, datetime(2026, 10, 8, 5, 30, tzinfo=timezone.utc))
        self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_firms_time_without_leading_zero(self):
        self.assertEqual(firms.parse_acquired("2026-10-08", "730"), datetime(2026, 10, 8, 7, 30, tzinfo=timezone.utc))
        self.assertEqual(firms.parse_acquired("2026-10-08", "5"), datetime(2026, 10, 8, 0, 5, tzinfo=timezone.utc))
        self.assertIsNone(firms.parse_acquired("", "730"))

    def test_naive_datetime_is_refused(self):
        with self.assertRaises(ValueError):
            ensure_utc(datetime(2026, 10, 8, 5, 30))


class CpcbTests(unittest.TestCase):
    def collect(self, *replies, limit=None):
        http, transport, _ = client(*replies)
        with mock.patch.dict(os.environ, FAKE):
            return cpcb.collect(http, SETTINGS, limit=limit), transport

    def test_records_are_labelled_measured_and_kept_raw(self):
        batch, _ = self.collect(ok(CPCB_PAYLOAD))
        self.assertEqual(len(batch.records), 3)
        first = batch.records[0]
        self.assertEqual((first.source, first.source_type), ("CPCB/data.gov.in", SourceType.MEASURED))
        self.assertEqual((first.pollutant, first.raw_value, first.raw_min, first.raw_max), ("PM2.5", "97", "41", "163"))
        self.assertEqual(first.observed_at, datetime(2026, 10, 8, 5, 30, tzinfo=timezone.utc))
        self.assertEqual(first.value_kind, ValueKind.UNKNOWN)
        self.assertEqual(len(batch.stations), 1)
        self.assertAlmostEqual(batch.stations[0].latitude, 28.6316)

    def test_value_without_a_unit_is_not_normalised(self):
        batch, _ = self.collect(ok(CPCB_PAYLOAD))
        pm = validation.validate_observation(batch.records[0], NOW, SETTINGS)
        self.assertEqual(pm.quality_state, QualityState.FLAGGED)
        self.assertIn("UNIT_UNSPECIFIED", {f.code for f in pm.quality_flags})
        self.assertIsNone(pm.normalized_value)

    def test_unusable_records_are_rejected_with_a_reason(self):
        batch, _ = self.collect(ok(CPCB_PAYLOAD))
        ozone = validation.validate_observation(batch.records[1], NOW, SETTINGS)
        carbon = validation.validate_observation(batch.records[2], NOW, SETTINGS)
        self.assertEqual(ozone.quality_state, QualityState.REJECTED)
        self.assertEqual(validation.rejection_of(ozone).code, "UNPARSABLE_VALUE")
        self.assertEqual(validation.rejection_of(carbon).code, "NEGATIVE_VALUE")

    def test_a_resource_that_is_not_air_quality_is_refused(self):
        wrong = dict(CPCB_PAYLOAD, title="District-wise rainfall statistics")
        http, _, _ = client(ok(wrong))
        with mock.patch.dict(os.environ, FAKE), self.assertRaises(Exception) as caught:
            cpcb.collect(http, SETTINGS)
        self.assertIn("Official measured source unavailable", str(caught.exception))

    def test_pagination_follows_offsets(self):
        def page(url, params):
            start = int(params["offset"])
            return ok(dict(CPCB_PAYLOAD, records=CPCB_PAYLOAD["records"][start:start + 2]))

        with mock.patch.object(cpcb, "PAGE_SIZE", 2):
            batch, transport = self.collect(page)
        self.assertEqual([c["params"]["offset"] for c in transport.calls], [0, 2])
        self.assertEqual(len(batch.records), 3)

    def test_missing_key_is_reported_by_name_only(self):
        http, _, _ = client(ok(CPCB_PAYLOAD))
        with mock.patch.dict(os.environ, {"DATA_GOV_API_KEY": ""}), self.assertRaises(CredentialMissing):
            cpcb.collect(http, SETTINGS)


class OpenAqTests(unittest.TestCase):
    cities = {"Delhi": (28.6139, 77.2090)}

    def collect(self, *replies):
        http, transport, sleeps = client(*replies)
        with mock.patch.dict(os.environ, FAKE), mock.patch.object(openaq, "utc_now", return_value=NOW):
            return openaq.collect(http, SETTINGS, cities=self.cities), transport, sleeps

    def test_latest_values_are_mapped_through_their_sensors(self):
        batch, transport, _ = self.collect(ok({"results": [OPENAQ_LOCATION]}), ok(OPENAQ_LATEST))
        self.assertEqual(transport.calls[0]["headers"]["X-API-Key"], FAKE["OPENAQ_API_KEY"])
        self.assertEqual([o.pollutant for o in batch.records], ["PM2.5", "CO"])  # humidity sensor is out of scope
        pm, co = batch.records
        self.assertEqual((pm.source, pm.source_station_id, pm.sensor_id), ("OpenAQ", "8118", "23534"))
        self.assertEqual(pm.provenance["upstream_provider"], "CPCB")
        validation.validate_observation(co, NOW, SETTINGS)
        self.assertAlmostEqual(co.normalized_value, 1.4)
        self.assertEqual(co.normalized_unit, "mg/m3")
        self.assertEqual((co.raw_value, co.raw_unit), (1400.0, "µg/m³"))  # raw is preserved

    def test_discovery_paginates(self):
        second = dict(OPENAQ_LOCATION, id=8119, name="Second")
        third = dict(OPENAQ_LOCATION, id=8120, name="Third")
        with mock.patch.object(openaq, "PAGE_LIMIT", 2):
            batch, transport, _ = self.collect(
                ok({"results": [OPENAQ_LOCATION, second]}), ok({"results": [third]}), ok({"results": []})
            )
        pages = [c["params"].get("page") for c in transport.calls if c["url"].endswith("/locations")]
        self.assertEqual(pages, [1, 2])
        self.assertEqual(len(batch.stations), 3)

    def test_pauses_when_the_rate_limit_window_is_spent(self):
        spent = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "12"}
        _, _, sleeps = self.collect(ok({"results": [OPENAQ_LOCATION]}, headers=spent), ok(OPENAQ_LATEST))
        self.assertEqual(sleeps, [13.0])

    def test_a_rejected_key_fails_the_run(self):
        http, _, _ = client(ok({"detail": "Unauthorized"}, status=401))
        with mock.patch.dict(os.environ, FAKE):
            result, _ = run.run_source("openaq", dry_run=True, settings=SETTINGS, client=http)
        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertIn("401", result.error)
        self.assertNotIn(FAKE["OPENAQ_API_KEY"], result.error)

    def test_inactive_locations_are_not_polled(self):
        dormant = dict(OPENAQ_LOCATION, datetimeLast={"utc": "2021-01-01T00:00:00Z"})
        batch, transport, _ = self.collect(ok({"results": [dormant]}))
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(batch.records, [])

    def test_a_locality_that_only_names_the_country_gives_way_to_the_target_city(self):
        embassy = dict(OPENAQ_LOCATION, name="New Delhi", locality="India")
        batch, _, _ = self.collect(ok({"results": [embassy]}), ok(OPENAQ_LATEST))
        self.assertEqual(batch.stations[0].city, "Delhi")
        self.assertEqual(batch.stations[0].metadata["provider_locality"], "India")  # what the provider said is kept
        self.assertEqual(batch.records[0].city, "Delhi")

    def test_a_station_inside_two_search_circles_belongs_to_the_nearer_city(self):
        cities = {"Delhi": (28.6139, 77.2090), "Gurugram": (28.4595, 77.0266)}
        near_gurugram = dict(OPENAQ_LOCATION, locality=None, coordinates={"latitude": 28.47, "longitude": 77.03})
        http, _, _ = client(ok({"results": [near_gurugram]}))
        with mock.patch.dict(os.environ, FAKE):
            locations, partial = openaq.discover_locations(http, FAKE["OPENAQ_API_KEY"], SETTINGS, cities)
        self.assertEqual((len(locations), partial), (1, False))
        self.assertEqual(locations[0]["_search_city"], "Gurugram")  # found first from Delhi, but Gurugram is closer

    def test_each_location_is_stamped_when_its_own_response_arrived(self):
        ticks = iter(NOW + timedelta(hours=n) for n in range(100))  # a clock that jumps, as it does when a laptop sleeps mid-run
        second = dict(OPENAQ_LOCATION, id=8119, name="Somewhere else")
        http, _, _ = client(ok({"results": [OPENAQ_LOCATION, second]}), ok(OPENAQ_LATEST))
        with mock.patch.dict(os.environ, FAKE), mock.patch.object(openaq, "utc_now", side_effect=lambda: next(ticks)):
            batch = openaq.collect(http, SETTINGS, cities=self.cities)
        stamps = {r.source_station_id: r.retrieved_at for r in batch.records}
        self.assertEqual(set(stamps), {"8118", "8119"})
        self.assertGreater(stamps["8119"], stamps["8118"])

    def test_values_from_sensors_that_are_not_pollutants_are_counted_in_a_note(self):
        batch, _, _ = self.collect(ok({"results": [OPENAQ_LOCATION]}), ok(OPENAQ_LATEST))
        self.assertEqual((batch.retrieved, len(batch.records)), (3, 2))
        self.assertTrue(any(note.startswith("1 latest values were from sensors that are not pollutants") for note in batch.notes))


class FirmsTests(unittest.TestCase):
    def test_detections_are_parsed_and_labelled(self):
        detections = firms.parse_csv(FIRMS_CSV, "VIIRS_NOAA20_NRT", NOW)
        self.assertEqual(len(detections), 3)
        first = detections[0]
        self.assertEqual(first.source_type, SourceType.SATELLITE_FIRE_DETECTION)
        self.assertEqual((first.satellite, first.confidence, first.frp_mw), ("N20", "nominal", 6.42))
        self.assertEqual(first.acquired_at, datetime(2026, 10, 8, 7, 30, tzinfo=timezone.utc))
        self.assertNotEqual(first.source_record_id, detections[1].source_record_id)

    def test_detection_without_position_is_rejected(self):
        detections = firms.parse_csv(FIRMS_CSV, "VIIRS_NOAA20_NRT", NOW)
        checked = [validation.validate_fire(d, NOW + timedelta(hours=3), SETTINGS) for d in detections]
        self.assertEqual([d.quality_state for d in checked], [QualityState.OK, QualityState.OK, QualityState.REJECTED])

    def test_provider_error_text_is_a_failure_and_hides_the_key(self):
        http, transport, _ = client(ok("Invalid MAP_KEY."))
        with mock.patch.dict(os.environ, FAKE), self.assertRaises(HttpError) as caught:
            firms.collect(http, SETTINGS)
        self.assertIn(FAKE["NASA_FIRMS_MAP_KEY"], transport.calls[0]["url"])  # the key is in the path ...
        self.assertNotIn(FAKE["NASA_FIRMS_MAP_KEY"], str(caught.exception))  # ... and never in the message

    def test_only_supported_viirs_feeds_are_requested(self):
        http, transport, _ = client(ok(FIRMS_CSV))
        with mock.patch.dict(os.environ, FAKE):
            firms.collect(http, SETTINGS)
        products = [c["url"].split("/")[-3] for c in transport.calls]
        self.assertEqual(products, ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"])


class WeatherTests(unittest.TestCase):
    locations = {"Delhi": (28.6139, 77.2090), "Chennai": (13.0827, 80.2707)}

    def payload(self):
        hours = [int((NOW + timedelta(hours=h)).timestamp()) for h in (-1, 0, 1, 24)]
        block = {
            "latitude": 28.625, "longitude": 77.25, "elevation": 216.0,
            "hourly_units": {"time": "unixtime", "temperature_2m": "°C", "wind_speed_10m": "m/s", "boundary_layer_height": "m"},
            "hourly": {
                "time": hours, "temperature_2m": [30.0, 31.0, 32.0, 29.0], "relative_humidity_2m": [40, 38, 36, 45],
                "precipitation": [0, 0, 0, 0], "wind_speed_10m": [2.0, 2.1, 2.2, 1.0], "wind_direction_10m": [280, 281, 282, 100],
                "surface_pressure": [988, 988, 987, 989], "boundary_layer_height": [900, 1200, 1500, None],
            },
        }
        return [block, block]

    RUN = datetime(2026, 10, 7, 18, 0, tzinfo=timezone.utc)

    def parse(self, retrieved=NOW, issued=RUN):
        return weather.parse_forecast(self.payload(), self.locations, "gfs_seamless", retrieved, issued, {})

    def test_only_future_hours_are_kept_with_lead_times(self):
        batch = self.parse()
        delhi = [f for f in batch.records if f.location_label == "Delhi"]
        self.assertEqual([f.lead_time_hours for f in delhi], [0.0, 1.0, 24.0])
        self.assertEqual(delhi[2].valid_at, NOW + timedelta(hours=24))
        self.assertEqual(delhi[0].issued_at, datetime(2026, 10, 7, 18, 0, tzinfo=timezone.utc))
        self.assertTrue(any("past hours" in note for note in batch.notes))

    def test_a_missing_variable_is_flagged_not_dropped(self):
        tomorrow = self.parse().records[2]
        validation.validate_weather(tomorrow)
        self.assertEqual(tomorrow.quality_state, QualityState.FLAGGED)
        self.assertIsNone(tomorrow.variables["boundary_layer_height"])

    def test_a_later_model_run_is_a_new_record_never_an_overwrite(self):
        earlier = self.parse(NOW).records[2]
        later = self.parse(NOW + timedelta(hours=6), self.RUN + timedelta(hours=6)).records[-1]
        self.assertEqual(earlier.valid_at, later.valid_at)
        self.assertNotEqual(earlier.unique_key, later.unique_key)
        store = db.MemoryStore()
        store.insert_forecasts([earlier], IngestionRun("Open-Meteo", NOW))
        store.insert_forecasts([later], IngestionRun("Open-Meteo", NOW))
        self.assertEqual(len(store.forecasts), 2)

    def tomorrow(self, retrieved, issued=RUN):
        """Delhi's forecast for the same valid hour, whenever it was fetched."""
        return next(f for f in self.parse(retrieved, issued).records if f.location_label == "Delhi" and f.valid_at == NOW + timedelta(hours=24))

    def test_fetching_the_same_model_run_again_adds_nothing_and_keeps_the_first_copy(self):
        first = self.tomorrow(NOW)
        again = self.tomorrow(NOW + timedelta(minutes=20))
        self.assertEqual(first.unique_key, again.unique_key)
        store = db.MemoryStore()
        self.assertEqual(store.insert_forecasts([first], IngestionRun("Open-Meteo", NOW)), 1)
        self.assertEqual(store.insert_forecasts([again], IngestionRun("Open-Meteo", NOW)), 0)
        self.assertEqual(next(iter(store.forecasts.values())).retrieved_at, NOW)

    def test_an_unknown_model_run_falls_back_to_the_retrieval_hour(self):
        first = self.tomorrow(NOW + timedelta(minutes=5), None)
        same_hour = self.tomorrow(NOW + timedelta(minutes=40), None)
        next_hour = self.tomorrow(NOW + timedelta(minutes=65), None)
        self.assertIsNone(first.issued_at)
        self.assertEqual(first.vintage_at, NOW)  # NOW is on the hour
        self.assertEqual(first.unique_key, same_hour.unique_key)
        self.assertNotEqual(first.unique_key, next_hour.unique_key)

    def test_run_time_comes_from_model_metadata(self):
        http, _, _ = client(ok({"last_run_initialisation_time": 1791396000, "last_run_availability_time": 1791416057}))
        issued, provenance = weather.model_run_time(http, "gfs_seamless")
        self.assertEqual(issued, datetime(2026, 10, 7, 18, 0, tzinfo=timezone.utc))
        self.assertIn("ncep_gfs013", provenance["issued_at_basis"])
        self.assertIsNone(weather.model_run_time(http, "some_other_model")[0])


class ValidationTests(unittest.TestCase):
    def test_staleness_thresholds_are_configuration(self):
        strict = settings_mod.Settings(fresh_minutes=60, stale_minutes=180, unavailable_hours=24)
        ages = {30: Freshness.FRESH, 120: Freshness.DELAYED, 600: Freshness.STALE, 3000: Freshness.UNAVAILABLE}
        for minutes, expected in ages.items():
            self.assertEqual(validation.classify_freshness(NOW - timedelta(minutes=minutes), NOW, strict), expected)
        lenient = settings_mod.Settings(fresh_minutes=60, stale_minutes=720, unavailable_hours=24)
        self.assertEqual(validation.classify_freshness(NOW - timedelta(minutes=600), NOW, lenient), Freshness.DELAYED)
        self.assertEqual(validation.classify_freshness(None, NOW, strict), Freshness.UNAVAILABLE)

    def test_freshness_is_judged_at_retrieval_not_at_validation(self):
        reading = observation(observed_at=NOW - timedelta(minutes=30), retrieved_at=NOW)
        validation.validate_observation(reading, NOW + timedelta(hours=9), SETTINGS)  # validated long after it was fetched
        self.assertEqual((reading.freshness, reading.quality_state), (Freshness.FRESH, QualityState.OK))

    def test_a_reading_timed_after_its_own_retrieval_is_rejected(self):
        reading = observation(observed_at=NOW + timedelta(hours=2), retrieved_at=NOW)
        validation.validate_observation(reading, NOW + timedelta(hours=9), SETTINGS)
        self.assertIn("FUTURE_TIMESTAMP", [f.code for f in reading.quality_flags])

    def test_a_unit_label_that_cannot_be_true_is_not_converted(self):
        # Seen live: OpenAQ labels Indian government monitors' carbon monoxide "ppb" while the numbers are in mg/m3.
        mislabelled = validation.validate_observation(observation(pollutant="CO", raw_pollutant="co", raw_value=0.96, raw_unit="ppb"), NOW, SETTINGS)
        self.assertIn("UNIT_SUSPECT", [f.code for f in mislabelled.quality_flags])
        self.assertNotIn("UNIT_CONVERTED", [f.code for f in mislabelled.quality_flags])
        self.assertEqual((mislabelled.normalized_value, mislabelled.normalized_unit), (None, None))
        self.assertEqual((mislabelled.raw_value, mislabelled.raw_unit), (0.96, "ppb"))  # kept exactly as received
        self.assertEqual(mislabelled.quality_state, QualityState.FLAGGED)

    def test_believable_carbon_monoxide_is_still_converted(self):
        for raw, unit, expected in ((800.0, "ppb", 0.9166), (1400.0, "µg/m³", 1.4), (1.2, "mg/m³", 1.2)):
            checked = validation.validate_observation(observation(pollutant="CO", raw_pollutant="co", raw_value=raw, raw_unit=unit), NOW, SETTINGS)
            self.assertNotIn("UNIT_SUSPECT", [f.code for f in checked.quality_flags])
            self.assertAlmostEqual(checked.normalized_value, expected, places=3)
        zero = validation.validate_observation(observation(pollutant="CO", raw_pollutant="co", raw_value=0.0, raw_unit="ppb"), NOW, SETTINGS)
        self.assertNotIn("UNIT_SUSPECT", [f.code for f in zero.quality_flags])  # a zero says nothing about its unit

    def test_stale_reading_is_kept_and_flagged(self):
        checked = validation.validate_observation(observation(observed_at=NOW - timedelta(hours=5)), NOW, SETTINGS)
        self.assertEqual(checked.quality_state, QualityState.FLAGGED)
        self.assertEqual(checked.freshness, Freshness.STALE)
        self.assertEqual(checked.normalized_value, 55.0)

    def test_future_timestamp_is_rejected(self):
        checked = validation.validate_observation(observation(observed_at=NOW + timedelta(hours=4)), NOW, SETTINGS)
        self.assertEqual(validation.rejection_of(checked).code, "FUTURE_TIMESTAMP")

    def test_missing_station_and_time(self):
        self.assertEqual(validation.rejection_of(validation.validate_observation(observation(source_station_id=None), NOW, SETTINGS)).code, "MISSING_STATION_ID")
        self.assertEqual(validation.rejection_of(validation.validate_observation(observation(observed_at=None), NOW, SETTINGS)).code, "MISSING_TIMESTAMP")

    def test_implausible_value_is_flagged_not_deleted(self):
        checked = validation.validate_observation(observation(raw_value=5000.0), NOW, SETTINGS)
        self.assertEqual(checked.quality_state, QualityState.FLAGGED)
        self.assertIn("IMPLAUSIBLE_VALUE", {f.code for f in checked.quality_flags})
        self.assertEqual(checked.normalized_value, 5000.0)

    def test_coordinate_problems(self):
        codes = lambda **kw: {f.code for f in validation.validate_observation(observation(**kw), NOW, SETTINGS).quality_flags}
        self.assertIn("COORDINATES_MISSING", codes(latitude=None))
        self.assertIn("COORDINATES_INVALID", codes(latitude=95.0))
        self.assertIn("COORDINATES_INVALID", codes(latitude=0.0, longitude=0.0))
        self.assertIn("COORDINATES_OUTSIDE_INDIA", codes(latitude=51.5, longitude=-0.1))

    def test_unsupported_unit_keeps_the_raw_value(self):
        checked = validation.validate_observation(observation(raw_unit="particles/cm3"), NOW, SETTINGS)
        self.assertIn("UNSUPPORTED_UNIT", {f.code for f in checked.quality_flags})
        self.assertIsNone(checked.normalized_value)
        self.assertEqual(checked.raw_value, 55.0)

    def test_duplicates_within_a_batch(self):
        seen = set()
        first = validation.validate_observation(observation(), NOW, SETTINGS, seen)
        again = validation.validate_observation(observation(), NOW, SETTINGS, seen)
        self.assertEqual(first.quality_state, QualityState.OK)
        self.assertEqual(validation.rejection_of(again).code, "DUPLICATE_IN_BATCH")


class HttpTests(unittest.TestCase):
    def test_retries_a_server_error_with_backoff(self):
        http, transport, sleeps = client(ok("", status=503), ok("", status=503), ok({"fine": True}))
        self.assertEqual(http.get("https://example.org/x").json(), {"fine": True})
        self.assertEqual(len(transport.calls), 3)
        self.assertEqual(sleeps, [1.5, 3.0])

    def test_honours_retry_after_on_429(self):
        http, _, sleeps = client(ok("", status=429, headers={"retry-after": "7"}), ok({"fine": True}))
        http.get("https://example.org/x")
        self.assertEqual(sleeps, [7.0])

    def test_gives_up_after_the_bound(self):
        http, transport, _ = client(TimeoutError("slow"))
        with self.assertRaises(HttpError) as caught:
            http.get("https://example.org/x")
        self.assertEqual(caught.exception.kind, "timeout")
        self.assertEqual(len(transport.calls), SETTINGS.http_max_retries + 1)

    def test_client_error_is_not_retried(self):
        http, transport, sleeps = client(ok("nope", status=404))
        with self.assertRaises(HttpError) as caught:
            http.get("https://example.org/x")
        self.assertEqual((caught.exception.status, len(transport.calls), sleeps), (404, 1, []))

    def test_malformed_json(self):
        http, _, _ = client(ok("<html>gateway error</html>"))
        with self.assertRaises(HttpError) as caught:
            http.get("https://example.org/x").json()
        self.assertEqual(caught.exception.kind, "malformed")


class SecretTests(unittest.TestCase):
    def test_redaction(self):
        with mock.patch.dict(os.environ, FAKE):
            text = settings_mod.redact(
                f"GET https://api.data.gov.in/resource/x?api-key={FAKE['DATA_GOV_API_KEY']}&format=json failed; "
                f"firms https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FAKE['NASA_FIRMS_MAP_KEY']}/VIIRS/1 ; dsn {FAKE['DATABASE_URL']}"
            )
        for value in list(FAKE.values()) + ["FAKEDBPASSWORD"]:
            self.assertNotIn(value, text)

    def test_unknown_key_shaped_values_are_masked_too(self):
        text = settings_mod.redact("https://x.test/api/area/csv/abcdef0123456789abcdef0123456789/V/1?token=zzz999&api_key=qqq111")
        for value in ("abcdef0123456789abcdef0123456789", "zzz999", "qqq111"):
            self.assertNotIn(value, text)

    def test_nothing_secret_reaches_logs_or_the_report(self):
        captured = io.StringIO()
        handler = logging.StreamHandler(captured)
        loggers = [logging.getLogger(name) for name in ("src.ingestion.http", "src.ingestion.run", "src.ingestion.cpcb", "src.ingestion.firms")]
        for logger in loggers:
            logger.addHandler(handler)
        try:
            with mock.patch.dict(os.environ, FAKE):
                run.install_log_redaction()
                leaky = ConnectionError(f"HTTPSConnectionPool: Max retries exceeded with url: /resource/x?api-key={FAKE['DATA_GOV_API_KEY']}")
                results = []
                for name in ("cpcb", "firms"):
                    http, _, _ = client(leaky)
                    results.append((name, *run.run_source(name, dry_run=True, settings=SETTINGS, client=http)))
                lines = []
                run.print_report(results, True, out=lines.append)
        finally:
            for logger in loggers:
                logger.removeHandler(handler)
        everything = captured.getvalue() + "\n".join(lines)
        self.assertIn("FAILED", everything)
        self.assertIn("Official measured source unavailable", everything)
        for value in FAKE.values():
            self.assertNotIn(value, everything)

    def test_placeholder_connection_string_counts_as_unconfigured(self):
        with mock.patch.dict(os.environ, {"DATABASE_URL": "postgresql://postgres.PROJECT_REF:pw@POOLER_HOST:5432/postgres"}):
            self.assertIsNone(settings_mod.secret("DATABASE_URL"))
            self.assertEqual(settings_mod.secret_status()["DATABASE_URL"], "placeholder")

    def test_env_files_are_ignored_by_git(self):
        for name in (".env", ".env.local", "webapp/.env"):
            ignored = subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT).returncode == 0
            self.assertTrue(ignored, f"{name} is not ignored by Git")
        tracked = subprocess.run(["git", "check-ignore", "-q", ".env.example"], cwd=ROOT).returncode == 0
        self.assertFalse(tracked, ".env.example must stay tracked")

    def test_env_example_holds_names_only(self):
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                name, _, value = line.partition("=")
                self.assertEqual(value.strip(), "", f"{name} has a value in .env.example")

    def test_no_configured_secret_is_in_a_tracked_file(self):
        settings_mod.load_env()
        secrets = [os.environ.get(n, "") for n in settings_mod.SECRET_NAMES]
        secrets = [s for s in secrets if len(s) >= 12 and settings_mod.secret_status()]
        if not secrets:
            self.skipTest("no credentials configured on this machine")
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
        for name in filter(None, files):
            path = ROOT / name
            if path.suffix.lower() in {".png", ".pdf", ".docx", ".joblib", ".gz", ".csv", ".ipynb"} or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for value in secrets:
                self.assertNotIn(value, text, f"a credential appears in tracked file {name}")

    def test_frontend_never_references_server_secrets(self):
        offenders = []
        for path in (ROOT / "webapp").rglob("*"):
            if any(part in {"node_modules", ".next", "_bundle", ".vercel"} for part in path.parts) or not path.is_file():
                continue
            if path.suffix not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".json", ".css"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "NEXT_PUBLIC_" in text or any(name in text for name in settings_mod.SECRET_NAMES):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


class MatchingTests(unittest.TestCase):
    def stations(self):
        official = Station("CPCB/data.gov.in", "delhi|delhi|ito-delhi-dpcc", name="ITO, Delhi - DPCC", city="Delhi", latitude=28.6316, longitude=77.2494)
        near = Station("OpenAQ", "8118", name="ITO, Delhi - CPCB", city="Delhi", latitude=28.6317, longitude=77.2495, upstream_provider="CPCB")
        far = Station("OpenAQ", "9000", name="Anand Vihar, Delhi", city="Delhi", latitude=28.6469, longitude=77.3152)
        return official, near, far

    def test_same_city_is_not_enough_to_link(self):
        official, near, far = self.stations()
        self.assertEqual(matching.link_stations([official], [near, far], 300), 1)
        self.assertEqual((near.same_as, near.match_method), (official.key, "distance"))
        self.assertLess(near.match_distance_m, 30)
        self.assertIsNone(far.same_as)

    def pair(self, **official_fields):
        official, near, _ = self.stations()
        matching.link_stations([official], [near], 300)
        when = NOW - timedelta(minutes=30)
        first = observation(source="CPCB/data.gov.in", source_station_id=official.source_station_id, observed_at=when, **official_fields)
        second = observation(source="OpenAQ", source_station_id="8118", observed_at=when)
        for item in (first, second):
            validation.validate_observation(item, NOW, SETTINGS)
        return first, second, near

    def test_the_official_copy_wins_when_both_can_be_modelled(self):
        first, second, near = self.pair()
        self.assertEqual(matching.resolve_modelling_preference([first], [second], [near]), 1)
        self.assertFalse(second.use_for_modelling)
        self.assertEqual(second.provenance["superseded_by"]["source"], "CPCB/data.gov.in")
        self.assertIn("SAME_MONITOR_OTHER_SOURCE", [f.code for f in second.quality_flags])
        self.assertEqual(second.source, "OpenAQ")  # never relabelled

    def test_an_official_copy_that_cannot_be_modelled_does_not_displace_one_that_can(self):
        first, second, near = self.pair(raw_value="97", raw_unit=None, value_kind=ValueKind.UNKNOWN)
        self.assertIsNone(first.normalized_value)
        self.assertEqual(matching.resolve_modelling_preference([first], [second], [near]), 0)
        self.assertTrue(second.use_for_modelling)
        self.assertEqual(second.provenance["also_held_from"]["source"], "CPCB/data.gov.in")

    def test_the_stored_official_copy_is_never_changed_after_the_fact(self):
        for fields in ({}, {"raw_value": "97", "raw_unit": None, "value_kind": ValueKind.UNKNOWN}):
            first, second, near = self.pair(**fields)
            before = (first.use_for_modelling, dict(first.provenance), [f.code for f in first.quality_flags])
            matching.resolve_modelling_preference([first], [second], [near])
            self.assertEqual(before, (first.use_for_modelling, dict(first.provenance), [f.code for f in first.quality_flags]))

    def test_a_rejected_official_reading_counts_for_nothing(self):
        first, second, near = self.pair(raw_value="-4")
        self.assertEqual(first.quality_state, QualityState.REJECTED)
        self.assertEqual(matching.resolve_modelling_preference([first], [second], [near]), 0)
        self.assertTrue(second.use_for_modelling)
        self.assertNotIn("also_held_from", second.provenance)


class StoreAndOrchestratorTests(unittest.TestCase):
    def test_inserting_twice_writes_once(self):
        store, the_run = db.MemoryStore(), IngestionRun("OpenAQ", NOW)
        batch = [validation.validate_observation(observation(), NOW, SETTINGS)]
        self.assertEqual(store.insert_observations(batch, the_run), 1)
        self.assertEqual(store.insert_observations(batch, the_run), 0)
        fires = [validation.validate_fire(f, NOW + timedelta(hours=3), SETTINGS) for f in firms.parse_csv(FIRMS_CSV, "VIIRS_NOAA20_NRT", NOW)][:2]
        self.assertEqual(store.insert_fires(fires, the_run), 2)
        self.assertEqual(store.insert_fires(fires, the_run), 0)
        self.assertEqual((len(store.observations), len(store.fires)), (1, 2))

    def test_end_to_end_into_the_store_is_idempotent(self):
        store = db.MemoryStore()
        with mock.patch.dict(os.environ, FAKE), mock.patch.object(run, "utc_now", return_value=NOW), mock.patch.object(cpcb, "utc_now", return_value=NOW):
            for _ in range(2):
                http, _, _ = client(ok(CPCB_PAYLOAD))
                result, samples = run.run_source("cpcb", store, dry_run=False, settings=SETTINGS, client=http)
        self.assertEqual((result.status, result.retrieved, result.accepted, result.rejected), (RunStatus.SUCCESS, 3, 1, 2))
        self.assertEqual(result.written, 0)  # the second pass found nothing new
        self.assertEqual(len(store.observations), 1)
        self.assertEqual(len(store.rejections), 2)
        self.assertEqual(samples[0].source, "CPCB/data.gov.in")

    def test_dry_run_writes_nothing(self):
        store = db.MemoryStore()
        http, _, _ = client(ok(CPCB_PAYLOAD))
        with mock.patch.dict(os.environ, FAKE), mock.patch.object(run, "utc_now", return_value=NOW):
            result, _ = run.run_source("cpcb", store, dry_run=True, settings=SETTINGS, client=http)
        self.assertEqual((result.accepted, result.written, len(store.observations), len(store.runs)), (1, 0, 0, 0))

    def test_one_failing_source_does_not_stop_the_others(self):
        class Broken:
            SOURCE = "Broken"

            @staticmethod
            def collect(**_):
                raise RuntimeError("boom")

        class Fine:
            SOURCE = "Fine"

            @staticmethod
            def collect(**_):
                return Batch(source="Fine", kind="air_quality", records=[observation()], retrieved=1)

        with mock.patch.dict(run.CONNECTORS, {"cpcb": Broken, "openaq": Fine}), mock.patch.object(run, "utc_now", return_value=NOW):
            broken, _ = run.run_source("cpcb", dry_run=True, settings=SETTINGS)
            fine, _ = run.run_source("openaq", dry_run=True, settings=SETTINGS)
        self.assertEqual((broken.status, fine.status, fine.accepted), (RunStatus.FAILED, RunStatus.SUCCESS, 1))
        self.assertIn("boom", broken.error)


@unittest.skipUnless(
    (settings_mod.load_env() or True) and settings_mod.secret("DATABASE_URL"),
    "DATABASE_URL is not configured; PostgreSQL idempotency is verified by the acceptance run instead",
)
class PostgresIntegrationTests(unittest.TestCase):
    def test_postgres_enforces_idempotency(self):
        db.migrate()
        store = db.PostgresStore()
        marker = f"test-station-{int(utc_now().timestamp())}"
        try:
            the_run = IngestionRun("OpenAQ", utc_now())
            store.start_run(the_run)
            station = Station("OpenAQ", marker, name="Integration test", city="Test", latitude=28.6, longitude=77.2)
            reading = validation.validate_observation(observation(source_station_id=marker, observed_at=utc_now() - timedelta(minutes=10), retrieved_at=utc_now()), utc_now(), SETTINGS)
            store.upsert_stations([station])
            self.assertEqual(store.insert_observations([reading], the_run), 1)
            self.assertEqual(store.insert_observations([reading], the_run), 0)
            rows = store.query("select source_id, source_type, raw_unit, normalized_unit, observed_at from airguard.air_quality_observations where source_station_id=%s", (marker,))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][:4], ("OpenAQ", "measured", "µg/m³", "ug/m3"))
            self.assertEqual(rows[0][4].astimezone(timezone.utc), reading.observed_at)
        finally:
            with store.connection, store.connection.cursor() as cursor:
                cursor.execute("delete from airguard.air_quality_observations where source_station_id=%s", (marker,))
                cursor.execute("delete from airguard.stations where source_station_id=%s", (marker,))
            store.close()


if __name__ == "__main__":
    unittest.main()
