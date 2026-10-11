from datetime import datetime, timedelta, timezone

from src.ingestion.archive import WINDOW_HOURS, hourly_records, sensors_of, windows

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
STATION = {'station_pk': 7, 'source_station_id': '1234', 'name': 'Probe', 'latitude': 13.0, 'longitude': 80.2,
           'metadata': {'provider': {'name': 'AirNow'}, 'owner': {'name': 'US Embassy'},
                        'sensors': [{'id': 11, 'parameter': {'name': 'pm25', 'units': 'µg/m³'}},
                                    {'id': 12, 'parameter': {'name': 'pm25', 'units': 'µg/m³'}},
                                    {'id': 13, 'parameter': {'name': 'no2', 'units': 'ppb'}},
                                    {'id': 14, 'parameter': {'name': 'o3', 'units': 'µg/m³'}},
                                    {'id': 15, 'parameter': {'name': 'um003', 'units': 'particles/cm³'}}]}}


def bin_at(start, value=42.0, unit='µg/m³', name='pm25', coverage=100, flags=False, hours=1):
    return {'value': value, 'parameter': {'name': name, 'units': unit},
            'coverage': {'percentCoverage': coverage}, 'flagInfo': {'hasFlags': flags},
            'period': {'datetimeFrom': {'utc': start.isoformat()},
                       'datetimeTo': {'utc': (start + timedelta(hours=hours)).isoformat()}}}


def test_windows_cover_the_whole_span_without_overlapping_or_exceeding_one_page():
    spans = windows(90, now=NOW)
    assert spans[0][1] == NOW
    assert spans[-1][0] == NOW - timedelta(days=90)
    for (start, end) in spans:
        assert 0 < (end - start).total_seconds() / 3600 <= WINDOW_HOURS
    for earlier, later in zip(spans[1:], spans):
        assert earlier[1] == later[0]


def test_one_sensor_per_pollutant_and_no_unconvertible_or_non_pollutant_sensor():
    chosen = sensors_of(STATION)
    assert sorted(chosen) == ['O3', 'PM2.5']
    assert chosen['PM2.5']['id'] == 11
    # ppb needs temperature and pressure, so NO2 in ppb is not silently converted.
    assert 'NO2' not in chosen


def test_record_keys_match_the_live_path_so_a_backfilled_hour_cannot_double_count():
    from src.nationwide.store import digest
    at = NOW - timedelta(hours=3)
    records, _rejected = hourly_records(STATION, STATION['metadata']['sensors'][0], 'PM2.5',
                                        [bin_at(at)], NOW, (NOW - timedelta(days=1), NOW))
    assert records[0]['record_key'] == digest(['openaq', 11, at.isoformat(), 'PM2.5'])
    assert records[0]['provenance']['retrieval'] == 'archive_backfill'
    assert 'not a CPCB' in records[0]['provenance']['note']


def test_every_rejection_is_counted_by_reason_and_nothing_is_dropped_silently():
    sensor = STATION['metadata']['sensors'][0]
    at = NOW - timedelta(hours=3)
    page = [
        bin_at(at),
        bin_at(at - timedelta(hours=1), coverage=40),
        bin_at(at - timedelta(hours=2), flags=True),
        bin_at(at - timedelta(hours=3), unit='ppb'),
        bin_at(at - timedelta(hours=4), hours=3),
        bin_at(at - timedelta(hours=5), name='pm10'),
        bin_at(NOW - timedelta(days=9)),
    ]
    records, rejected = hourly_records(STATION, sensor, 'PM2.5', page, NOW, (NOW - timedelta(days=1), NOW))
    assert len(records) == 1
    assert rejected == {'under_75_percent_coverage': 1, 'upstream_flagged': 1,
                        'unconvertible_unit_or_value': 1, 'not_an_hourly_bin': 1,
                        'pollutant_identity_mismatch': 1, 'outside_requested_window': 1}
    assert len(records) + sum(rejected.values()) == len(page)


def test_provenance_stays_small_enough_for_years_of_hourly_rows():
    import json
    sensor = STATION['metadata']['sensors'][0]
    records, _ = hourly_records(STATION, sensor, 'PM2.5', [bin_at(NOW - timedelta(hours=2))], NOW,
                                (NOW - timedelta(days=1), NOW))
    assert len(json.dumps(records[0]['provenance'])) < 500
