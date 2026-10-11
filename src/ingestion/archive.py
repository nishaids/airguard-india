"""Historical hourly backfill from the OpenAQ v3 archive.

WP1 wants station history from 2019 onwards. The licensed CPCB CCR export is the
first-choice source and is not held, so this fills what the second choice can
actually reach: `/sensors/{id}/hours` over a past window, for sensors already
discovered on registered Indian stations.

Three things this deliberately does not do. It does not require a station to be
reporting now, because an archive is about the past. It does not relabel an
OpenAQ upstream as CPCB. And it writes records under the same `record_key`
scheme as the live path, so a backfilled hour and a live hour are the same row
and neither can double-count the other.

The ceiling here is upstream coverage, not effort: for much of India OpenAQ
carries US-embassy AirNow and low-cost sensors rather than CAAQMS reference
instruments, so a thin result is a finding about the source, and is reported as
one rather than smoothed over.
"""
from __future__ import annotations

import gzip
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import config

from src.ingestion.settings import get_settings, secret
from src.nationwide.aqi import normalize, parse_time
from src.nationwide.providers import Providers
from src.nationwide.store import digest, BudgetExceeded

OPENAQ_URL = 'https://api.openaq.org/v3'
METHOD = 'openaq-archive-hours-v1'
POLLUTANTS = {'pm25': 'PM2.5', 'pm10': 'PM10', 'no2': 'NO2', 'so2': 'SO2',
              'co': 'CO', 'o3': 'O3', 'nh3': 'NH3', 'pb': 'Pb'}
PAGE_LIMIT = 1000
# One request covers at most this many hours, so a page cannot silently truncate
# a window: 1000 hourly bins is about 41 days.
WINDOW_HOURS = 24 * 30


#: Returned when a sensor itself reports that it holds no observations.
EMPTY_SENSOR = object()


def sensor_coverage(providers, sensor, headers, pace=0.0):
    """The sensor's declared first and last observation, or EMPTY_SENSOR.

    Returns None when the sensor does not say, in which case the caller must
    assume coverage rather than skip: an unanswered question is not a no.
    """
    try:
        if pace:
            time.sleep(pace)
        payload = providers.get_json(
            'openaq', f"{OPENAQ_URL}/sensors/{int(sensor['id'])}", None, headers)
    except BudgetExceeded:
        raise
    except Exception:  # noqa: BLE001 - unknown coverage must not skip the sensor
        return None
    results = payload.get('results') or []
    if not results:
        return None
    record = results[0]
    first = ((record.get('datetimeFirst') or {}) or {}).get('utc')
    last = ((record.get('datetimeLast') or {}) or {}).get('utc')
    if not first and not last:
        # An explicit null on both ends, with a zero observation count, is the
        # sensor saying it holds nothing.
        if (record.get('coverage') or {}).get('observedCount') in (0, None) and record.get('datetimeLast') is None:
            return EMPTY_SENSOR
        return None
    try:
        return (parse_time(first) if first else None, parse_time(last) if last else None)
    except (TypeError, ValueError):
        return None


def clip(spans, coverage):
    """Keep only the windows that can contain data, given declared coverage."""
    if not coverage:
        return list(spans)
    first, last = coverage
    kept = []
    for start, end in spans:
        if last is not None and start > last:
            continue
        if first is not None and end <= first:
            continue
        kept.append((start, end))
    return kept


class ArchiveProviders(Providers):
    """Provider access with the backfill's own request pool.

    A multi-hour operator job must not spend the live product's upstream
    allowance: if the archive walk exhausts `provider-hour:openaq`, the public
    site stops being able to show measured data. Same politeness, separate pool.
    The default hourly cap matches the product's, because raising it is a claim
    about what OpenAQ permits for this key and that needs confirming first
    (HUMAN_ACTIONS.md).
    """

    def request_budget(self, provider):
        self.store.budget('archive-hour:' + provider, _int_env('AIRGUARD_ARCHIVE_HOURLY', 200))
        self.store.budget('archive-day:' + provider, _int_env('AIRGUARD_ARCHIVE_DAILY', 4000), 86400)
        self.store.budget('archive-minute:' + provider, _int_env('AIRGUARD_ARCHIVE_PER_MINUTE', 40), 60)


def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def station_rows(store, limit=None, offset=0):
    """Registered Indian OpenAQ stations, newest metadata first."""
    with store.cursor() as cursor:
        cursor.execute("""select station_pk,source_station_id,name,latitude,longitude,metadata
            from airguard.stations where source_id='OpenAQ' and country='IN'
            order by last_seen_at desc nulls last,station_pk""")
        rows = [dict(r) for r in cursor.fetchall()]
    rows = rows[offset:]
    return rows[:limit] if limit else rows


def declared_sensors(metadata):
    """Normalise the two sensor shapes the station table carries.

    The live provider stores OpenAQ's own sensor objects as a list; the ingestion
    path stores a mapping of sensor id to `{parameter, units}`. Both describe the
    same thing, so neither shape should decide whether a station is reachable.
    """
    sensors = (metadata or {}).get('sensors')
    if isinstance(sensors, list):
        return [s for s in sensors if isinstance(s, dict)]
    if isinstance(sensors, dict):
        out = []
        for sensor_id, value in sensors.items():
            if not isinstance(value, dict):
                continue
            try:
                identifier = int(sensor_id)
            except (TypeError, ValueError):
                continue
            out.append({'id': identifier,
                        'parameter': {'name': str(value.get('parameter') or '').lower(),
                                      'units': value.get('units', '')}})
        return out
    return []


def sensors_of(station):
    """One sensor per pollutant, from the station metadata already stored."""
    metadata = station.get('metadata') or {}
    chosen = {}
    for sensor in declared_sensors(metadata):
        name = ((sensor.get('parameter') or {}).get('name') or '').lower()
        pollutant = POLLUTANTS.get(name)
        if not pollutant or pollutant in chosen:
            continue
        units = (sensor.get('parameter') or {}).get('units', '')
        # A sensor whose unit cannot be converted to mass concentration is not
        # usable for a CPCB-style target; ppb needs temperature and pressure.
        if normalize(pollutant, 1, units) is None:
            continue
        chosen[pollutant] = sensor
    return chosen


def hourly_records(station, sensor, pollutant, results, fetched_at, window):
    """Convert one page of hourly bins into records, with per-reason rejections."""
    start, end = window
    records, rejected = [], {}

    def reject(reason):
        rejected[reason] = rejected.get(reason, 0) + 1

    for item in results:
        parameter = item.get('parameter') or {}
        if (parameter.get('name') or '').lower() != ((sensor.get('parameter') or {}).get('name') or '').lower():
            reject('pollutant_identity_mismatch')
            continue
        unit = parameter.get('units', '')
        value = normalize(pollutant, item.get('value'), unit)
        if value is None:
            reject('unconvertible_unit_or_value')
            continue
        if (item.get('flagInfo') or {}).get('hasFlags'):
            reject('upstream_flagged')
            continue
        try:
            at = parse_time(item['period']['datetimeFrom']['utc'])
            until = parse_time(item['period']['datetimeTo']['utc'])
        except (KeyError, TypeError, ValueError):
            reject('unparseable_period')
            continue
        if until - at != timedelta(hours=1):
            reject('not_an_hourly_bin')
            continue
        if not start <= at < end:
            reject('outside_requested_window')
            continue
        coverage = (item.get('coverage') or {}).get('percentCoverage')
        if coverage is not None and coverage < 75:
            reject('under_75_percent_coverage')
            continue
        records.append({
            'record_key': digest(['openaq', sensor['id'], at.isoformat(), pollutant]),
            'provider': 'openaq', 'source_type': 'measured', 'station_pk': station['station_pk'],
            'sensor_id': str(sensor['id']), 'latitude': station['latitude'], 'longitude': station['longitude'],
            'pollutant': pollutant, 'raw_value': item.get('value'), 'raw_unit': unit,
            'normalized_value': value, 'normalized_unit': 'mg/m3' if pollutant == 'CO' else 'ug/m3',
            'valid_at': at.isoformat(), 'issued_at': None, 'fetched_at': fetched_at.isoformat(),
            'quality_state': 'VALID', 'methodology_version': METHOD,
            # Provenance is deliberately slim here. The live path embeds the whole
            # station and sensor payload per row, which is affordable for a handful
            # of current readings and ruinous across years of hourly history: the
            # station and sensor rows already hold that metadata, so this keeps the
            # identifiers needed to rejoin them plus the facts specific to this hour.
            'provenance': {
                'endpoint': f"{OPENAQ_URL}/sensors/{int(sensor['id'])}/hours",
                'retrieval': 'archive_backfill', 'station_pk': station['station_pk'],
                'source_station_id': station['source_station_id'], 'sensor_id': sensor['id'],
                'period_to': until.isoformat(), 'coverage_percent': coverage,
                'upstream_provider': ((station.get('metadata') or {}).get('provider') or {}).get('name'),
                'note': 'OpenAQ upstream; not a CPCB CAAQMS export. Station and sensor metadata '
                        'live in airguard.stations and airguard.sensors.',
            },
        })
    return records, rejected


def windows(days, now=None):
    """Past windows, most recent first, each small enough for one page."""
    end = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    spans = []
    cursor = end
    while cursor > start:
        previous = max(start, cursor - timedelta(hours=WINDOW_HOURS))
        spans.append((previous, cursor))
        cursor = previous
    return spans


def fetch_window(providers, sensor, window, headers, pace, attempts=2):
    """One page, with its own rate-limit patience.

    The archive is a long walk over a shared free endpoint. Being throttled is
    expected rather than exceptional, so a throttled window waits and tries
    again instead of being abandoned and silently missing from the record.
    """
    start, end = window
    params = {'datetime_from': start.isoformat(), 'datetime_to': end.isoformat(), 'limit': PAGE_LIMIT}
    url = f"{OPENAQ_URL}/sensors/{int(sensor['id'])}/hours"
    last = None
    for attempt in range(attempts):
        if pace:
            time.sleep(pace)
        try:
            return providers.get_json('openaq', url, params, headers), None
        except BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - the kind is recorded by the caller
            last = exc
            if getattr(exc, 'kind', None) != 'rate_limited':
                break
            time.sleep(pace * 4 + 2 * (attempt + 1))
    return None, last


class FileSink:
    """Write archive rows to gzipped NDJSON under data/archive instead of the database.

    Years of hourly rows for a hundred stations do not belong in the production
    database: that store exists to serve the live product on a fixed storage
    budget, and research reads the archive in bulk rather than by key. Files cost
    nothing, stay out of Git by .gitignore, and keep one file per station and
    pollutant so a partial run is still usable. Each row keeps the same
    `record_key` as the database path, so the two can be reconciled later.
    """

    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.files = {}
        self.written = 0

    def sensor(self, station_pk, sensor):  # interface parity with the database store
        return None

    def records(self, rows):
        for row in rows:
            name = f"station_{row['station_pk']}_{row['pollutant'].replace('.', '').lower()}.ndjson.gz"
            path = self.directory / name
            handle = self.files.get(name)
            if handle is None:
                handle = self.files[name] = gzip.open(path, 'at', encoding='utf-8')
            handle.write(json.dumps(row, default=str) + '\n')
            self.written += 1
        return len(rows)

    def close(self):
        for handle in self.files.values():
            handle.close()
        self.files.clear()


def backfill(store, providers, days=30, station_limit=None, pollutant_limit=None, now=None, pace=1.0,
             sink=None, catalogue=None, station_offset=0):
    """Fetch and store the reachable archive. Returns a summary, never a claim."""
    key = secret('OPENAQ_API_KEY')
    if not key:
        return {'status': 'CREDENTIAL_MISSING', 'stored': 0,
                'reason': 'OPENAQ_API_KEY is absent; see HUMAN_ACTIONS.md.'}
    headers = {'X-API-Key': key}
    started = datetime.now(timezone.utc)
    spans = windows(days, now=now)
    stations = station_rows(store, station_limit, station_offset)
    writer = sink or store
    if catalogue:
        stations = [s for s in stations if str(s['source_station_id']) in {str(c) for c in catalogue}]
    summary = {
        'status': 'COMPLETE', 'generated_at': started.isoformat(), 'source': 'OpenAQ v3 /sensors/{id}/hours',
        'requested_days': days, 'windows': len(spans), 'stations_considered': len(stations),
        'stations_with_usable_sensors': 0, 'requests': 0, 'stored': 0, 'retrieved': 0,
        'per_pollutant': {}, 'per_station': [], 'rejected': {}, 'errors': {}, 'skipped': {},
        'earliest_valid_at': None, 'latest_valid_at': None,
        'notice': 'Upstream coverage bounds this, not effort. OpenAQ provenance is preserved and is not CPCB.',
        'radius_note': 'Only stations already registered from India are queried; no new discovery happens here.',
    }

    def note(bucket, reason):
        summary[bucket][reason] = summary[bucket].get(reason, 0) + 1

    for station in stations:
        sensors = sensors_of(station)
        if not sensors:
            continue
        summary['stations_with_usable_sensors'] += 1
        chosen = list(sensors.items())[:pollutant_limit] if pollutant_limit else list(sensors.items())
        station_total, station_first, station_last = 0, None, None
        for pollutant, sensor in chosen:
            # One request for the sensor's own declared coverage saves up to
            # thirteen window requests against a sensor that holds nothing. The
            # station record can say data exists while the sensor the station
            # lists has none, and at 200 requests an hour that difference is
            # hours of wall time.
            try:
                coverage_window = sensor_coverage(providers, sensor, headers, pace)
            except BudgetExceeded:
                # Running out of allowance is an expected end to a long walk, not
                # a crash: stop, record why, and keep the summary and the rows
                # already written.
                summary['status'] = 'STOPPED_REQUEST_BUDGET'
                note('errors', 'request_budget_exhausted')
                break
            if coverage_window is EMPTY_SENSOR:
                note('skipped', 'sensor_declares_no_data')
                continue
            sensor_spans = clip(spans, coverage_window)
            if not sensor_spans:
                note('skipped', 'sensor_coverage_outside_requested_window')
                continue
            for start, end in sensor_spans:
                try:
                    payload, failure = fetch_window(providers, sensor, (start, end), headers, pace)
                except BudgetExceeded:
                    summary['status'] = 'STOPPED_REQUEST_BUDGET'
                    note('errors', 'request_budget_exhausted')
                    break
                if payload is None:
                    note('errors', getattr(failure, 'kind', None) or type(failure).__name__)
                    summary['windows_lost'] = summary.get('windows_lost', 0) + 1
                    continue
                summary['requests'] += 1
                results = payload.get('results')
                if not isinstance(results, list):
                    note('errors', 'unexpected_payload_shape')
                    continue
                summary['retrieved'] += len(results)
                records, rejected = hourly_records(
                    station, sensor, pollutant, results, datetime.now(timezone.utc).replace(microsecond=0),
                    (start, end))
                for reason, count in rejected.items():
                    summary['rejected'][reason] = summary['rejected'].get(reason, 0) + count
                if not records:
                    continue
                writer.sensor(station['station_pk'], sensor)
                writer.records(records)
                summary['stored'] += len(records)
                summary['per_pollutant'][pollutant] = summary['per_pollutant'].get(pollutant, 0) + len(records)
                station_total += len(records)
                times = [r['valid_at'] for r in records]
                station_first = min([station_first, *times]) if station_first else min(times)
                station_last = max([station_last, *times]) if station_last else max(times)
            if summary['status'] == 'STOPPED_REQUEST_BUDGET':
                break
        if station_total:
            summary['per_station'].append({
                'station_pk': station['station_pk'], 'name': station['name'],
                'source_station_id': station['source_station_id'], 'rows': station_total,
                'pollutants': sorted({p for p, _s in chosen}), 'first': station_first, 'last': station_last})
            summary['earliest_valid_at'] = min(filter(None, [summary['earliest_valid_at'], station_first]))
            summary['latest_valid_at'] = max(filter(None, [summary['latest_valid_at'], station_last]))
        if summary['status'] == 'STOPPED_REQUEST_BUDGET':
            break
    summary['completed_at'] = datetime.now(timezone.utc).isoformat()
    summary['seconds'] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    summary['settings'] = {'search_radius_m': get_settings().openaq_search_radius_m}
    summary['sink'] = 'files' if sink is not None else 'database'
    if sink is not None:
        summary['sink_directory'] = config.portable(sink.directory)
        sink.close()
    return summary
