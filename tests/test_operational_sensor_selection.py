"""Operational acquisition must not let retired sensors hide live successors."""
from datetime import datetime, timedelta, timezone
import json
import threading

import pytest

from src.ingestion.http import HttpClient, Response
from src.ingestion.settings import Settings
from src.nationwide import providers
from src.nationwide.store import BudgetExceeded
from src.research.protocol import check_inputs


NOW = datetime(2026, 10, 11, 14, 20, tzinfo=timezone.utc)
START = NOW - timedelta(hours=32)


def sensor(sensor_id, name="pm25", first="2025-02-18T00:00:00Z", last=None, unit="ug/m3", count=100):
    return {"id": sensor_id, "parameter": {"name": name, "units": unit},
            "datetimeFirst": {"utc": first}, "datetimeLast": {"utc": last or NOW.isoformat()},
            "coverage": {"observedCount": count}}


def test_retired_sensor_cannot_hide_successor_in_either_order():
    retired = sensor(1, first="2018-01-01T00:00:00Z", last="2022-01-01T00:00:00Z")
    live = sensor(11)
    for metadata in ([retired, live], [live, retired]):
        assert providers.select_measured_sensors(metadata, START, NOW) == [(live, "PM2.5")]


def test_newest_convertible_overlapping_sensor_wins_without_reading_values():
    old = sensor(1, last=(NOW-timedelta(hours=4)).isoformat(), count=100000)
    live = sensor(11, count=1)
    ppb = sensor(21, last=(NOW+timedelta(minutes=1)).isoformat(), unit="ppb")
    future = sensor(31, first=(NOW+timedelta(hours=1)).isoformat(), last=(NOW+timedelta(hours=2)).isoformat())
    assert providers.select_measured_sensors([old, ppb, future, live], START, NOW) == [(live, "PM2.5")]


@pytest.mark.parametrize("malformed", [
    {"id": 1, "parameter": {"name": "pm25", "units": "ug/m3"}},
    sensor(1, first="2026-10-11T00:00:00"),
    sensor(1, first="bad timestamp"),
    sensor(1, first="2026-10-12T00:00:00Z", last="2026-10-11T00:00:00Z"),
    sensor(True),
    None,
])
def test_unevidenced_or_invalid_sensor_metadata_is_not_used(malformed):
    assert not providers.select_measured_sensors([malformed], START, NOW)


def test_equal_sensor_timestamps_have_deterministic_tie_break():
    lower = sensor(11)
    higher = sensor(21)
    for metadata in ([higher, lower], [lower, higher]):
        assert providers.select_measured_sensors(metadata, START, NOW) == [(lower, "PM2.5")]


class Store:
    def __init__(self):
        self.saved = []
        self.sensors = []
        self.budgets = []
        self.snapshots = []

    def budget(self, *args):
        self.budgets.append(args)

    def event(self, *args, **kwargs):
        pass

    def station(self, metadata):
        assert metadata["id"] == 50
        return 700

    def sensor(self, station_pk, metadata):
        self.sensors.append((station_pk, metadata["id"]))

    def records(self, rows):
        self.saved.extend(rows)

    def research_snapshot(self, payload, lat, lon, station_pk):
        self.snapshots.append((payload, lat, lon, station_pk))


def acquisition(monkeypatch, metadata_status=200, deny_metadata_budget=False):
    store = Store()
    calls = []
    chosen = [sensor(11), sensor(21, "pm10"), sensor(31, "o3")]
    retired = [sensor(i, name, first="2018-01-01T00:00:00Z", last="2022-01-01T00:00:00Z")
               for i, name in ((1, "pm25"), (2, "pm10"), (3, "o3"))]
    location = {"id": 50, "name": "Test station", "country": {"code": "IN"},
                "coordinates": {"latitude": 13.0, "longitude": 80.0},
                "datetimeLast": {"utc": NOW.isoformat()},
                # Discovery has no sensor dates, as in actual OpenAQ responses.
                "sensors": [{"id": s["id"], "parameter": s["parameter"]} for s in retired + chosen]}

    def transport(url, params, headers, timeout):
        calls.append((url, params))
        assert headers["X-API-Key"] == "test-key"
        if url == providers.OPENAQ_URL + "/locations":
            return Response(200, {}, json.dumps({"results": [location]}))
        if url == providers.OPENAQ_URL + "/locations/50/sensors":
            return Response(metadata_status, {}, json.dumps({"results": retired + chosen}))
        requested = next(s for s in chosen if url.endswith(f"/sensors/{s['id']}/hours"))
        rows = []
        for i in range(24):
            begin = NOW-timedelta(hours=24-i)
            rows.append({"parameter": requested["parameter"], "value": 40,
                         "period": {"datetimeFrom": {"utc": begin.isoformat()},
                                    "datetimeTo": {"utc": (begin+timedelta(hours=1)).isoformat()}},
                         "coverage": {"percentCoverage": 100}, "flagInfo": {"hasFlags": False}})
        return Response(200, {}, json.dumps({"results": rows}))

    if deny_metadata_budget:
        def budget(*args):
            store.budgets.append(args)
            # Every API call starts with the provider-hour budget.
            if args[0] == "provider-hour:openaq" and len(calls) >= 1:
                raise BudgetExceeded("test budget")
        store.budget = budget
    client = HttpClient(Settings(http_max_retries=0), transport=transport, sleep=lambda _: None)
    provider = providers.Providers(store, client)
    monkeypatch.setattr(providers, "secret", lambda _: "test-key")
    monkeypatch.setattr(providers, "utcnow", lambda: NOW)
    return provider, store, calls


def test_operational_request_fetches_dated_metadata_and_only_live_sensor_hours(monkeypatch):
    provider, store, calls = acquisition(monkeypatch)
    result = provider.measured(13, 80, START, NOW)
    assert result["status"] == "SUCCESS"
    assert len(result["stations"]) == 1
    assert result["stations"][0]["station_pk"] == 700
    assert result["stations"][0]["calculation"]["status"] == "VALID"
    assert {sid for _, sid in store.sensors} == {11, 21, 31}
    assert len(store.saved) == 72
    assert all(r["station_pk"] == 700 and r["provenance"]["station"]["id"] == 50 for r in store.saved)
    assert len(calls) == 5  # discovery, one metadata call, three selected pollutants
    assert sum(b[0] == "provider-minute:openaq" for b in store.budgets) == 5
    assert len(store.snapshots) == 1 and store.snapshots[0][3] == 700


@pytest.mark.parametrize("mode", ["http", "budget"])
def test_metadata_failure_is_partial_and_never_falls_back_to_retired_list_order(monkeypatch, mode):
    provider, store, calls = acquisition(monkeypatch, metadata_status=503 if mode == "http" else 200,
                                         deny_metadata_budget=mode == "budget")
    result = provider.measured(13, 80, START, NOW)
    assert result["status"] == "PARTIAL" and result["errors"]
    assert not result["stations"] and not store.saved
    assert not any(url.endswith("/hours") for url, _ in calls)


def test_response_receipt_crossing_20ist_is_rejected_as_an_issue_time_input(monkeypatch):
    provider, store, calls = acquisition(monkeypatch)
    cutoff = datetime(2026, 10, 11, 14, 30, tzinfo=timezone.utc)
    began = cutoff-timedelta(seconds=3)
    discovery = cutoff-timedelta(seconds=2)
    metadata = cutoff-timedelta(seconds=1.5)
    receipts = {11: cutoff-timedelta(seconds=1), 21: cutoff+timedelta(seconds=1),
                31: cutoff+timedelta(seconds=2)}
    clock = threading.local()
    main_time = [began]
    monkeypatch.setattr(providers, "utcnow", lambda: getattr(clock, "received", main_time[0]))
    original_get = provider.get_json

    def timed_get(name, url, *args):
        payload = original_get(name, url, *args)
        if url.endswith("/locations"):
            main_time[0] = discovery
        elif url.endswith("/locations/50/sensors"):
            main_time[0] = metadata
        else:
            clock.received = receipts[int(url.split("/")[-2])]
        return payload

    monkeypatch.setattr(provider, "get_json", timed_get)
    result = provider.measured(13, 80, START, NOW)
    for row in store.saved:
        received = receipts[int(row["sensor_id"])]
        assert datetime.fromisoformat(row["fetched_at"]) == received
        assert row["provenance"]["response_received_at"] == received.isoformat()
        assert row["valid_at"] == row["provenance"]["hourly_record"]["period"]["datetimeFrom"]["utc"]
        envelope = {**row, "available_at": row["fetched_at"], "retrieved_at": row["fetched_at"],
                    "valid_end": row["provenance"]["hourly_record"]["period"]["datetimeTo"]["utc"]}
        if received <= cutoff:
            assert check_inputs([envelope], cutoff)
        else:
            with pytest.raises(ValueError, match="not available at issuance cutoff"):
                check_inputs([envelope], cutoff)
    snapshot = store.snapshots[0][0]
    assert datetime.fromisoformat(snapshot["fetched_at"]) >= max(receipts.values()) > cutoff
    assert datetime.fromisoformat(result["fetched_at"]) >= datetime.fromisoformat(snapshot["fetched_at"])
    assert snapshot["sensor_metadata_received_at"] == metadata.isoformat()
    assert len(calls) == 5
    assert sum(b[0] == "provider-minute:openaq" for b in store.budgets) == 5


def test_delayed_sensor_metadata_does_not_backdate_the_completed_station(monkeypatch):
    provider, store, _ = acquisition(monkeypatch)
    cutoff = datetime(2026, 10, 11, 14, 30, tzinfo=timezone.utc)
    clock = threading.local()
    main_time = [cutoff-timedelta(seconds=2)]
    metadata_received = cutoff+timedelta(seconds=3)
    hours_received = metadata_received+timedelta(seconds=1)
    monkeypatch.setattr(providers, "utcnow", lambda: getattr(clock, "received", main_time[0]))
    original_get = provider.get_json

    def timed_get(name, url, *args):
        payload = original_get(name, url, *args)
        if url.endswith("/locations/50/sensors"):
            main_time[0] = metadata_received
        elif url.endswith("/hours"):
            clock.received = hours_received
        return payload

    monkeypatch.setattr(provider, "get_json", timed_get)
    provider.measured(13, 80, START, NOW)
    assert all(datetime.fromisoformat(r["fetched_at"]) >= hours_received for r in store.saved)
    snapshot = store.snapshots[0][0]
    assert snapshot["sensor_metadata_received_at"] == metadata_received.isoformat()
    assert datetime.fromisoformat(snapshot["fetched_at"]) >= hours_received > cutoff
