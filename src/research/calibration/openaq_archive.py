"""Hourly station history from OpenAQ, cached as immutable checksummed files.

One file per sensor, every returned hourly bin kept as it arrived - including
bins the provider flagged and bins with thin coverage - so the quality rules are
applied downstream by code a reviewer can read, not baked into the cache. A
manifest records what was asked for, when, and the SHA-256 of what came back.

Two lessons from the first attempt are built in. A location lists retired
sensors beside live ones (a 2018-2022 PM2.5 sensor next to its 2025 successor),
so the sensor for each pollutant is chosen by most recent data, not by position
in the list. And the provider's own rate-limit headers are obeyed, with headroom
left for the live product, which shares the key.

    python -m src.research.calibration.openaq_archive --start 2025-02-01 --end 2026-10-08
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import config
from src.ingestion.settings import load_env, secret
from src.nationwide.aqi import normalize
from src.research.calibration.catalogue import SELECTION

BASE = 'https://api.openaq.org/v3'
ROOT = config.PROJECT_ROOT / 'data/research/openaq_hours'
SENSORS = config.PROJECT_ROOT / 'data/research/catalogue/sensors'
MANIFEST = config.PROJECT_ROOT / 'results/research/data_manifests/openaq_hours_manifest.json'
POLLUTANTS = {'pm25': 'PM2.5', 'pm10': 'PM10', 'o3': 'O3', 'no2': 'NO2', 'so2': 'SO2', 'co': 'CO'}
PAGE = 1000
WINDOW_HOURS = 1000
FIELDS = ('valid_from_utc', 'valid_to_utc', 'value', 'unit', 'coverage_pct', 'flagged')


class Client:
    """Paced OpenAQ access that never prints or stores the key."""

    def __init__(self, per_minute=42):
        load_env()
        self.key = secret('OPENAQ_API_KEY')
        if not self.key:
            raise SystemExit('OPENAQ_API_KEY is not configured; see HUMAN_ACTIONS.md.')
        self.interval = 60.0 / per_minute
        self.last = 0.0
        self.requests = 0
        self.throttled = 0

    def get(self, path, params=None, attempts=6):
        url = BASE + path + (('?' + urllib.parse.urlencode(params)) if params else '')
        for attempt in range(attempts):
            wait = self.interval - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            request = urllib.request.Request(url, headers={
                'X-API-Key': self.key, 'User-Agent': 'airguard-india-research/1.0'})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed host
                    self.requests += 1
                    remaining = response.headers.get('x-ratelimit-remaining')
                    reset = response.headers.get('x-ratelimit-reset')
                    body = json.loads(response.read().decode('utf-8'))
                    # Leave the last few calls of every window for the live site.
                    if remaining is not None and reset is not None and int(remaining) <= 6:
                        time.sleep(min(60, int(reset) + 1))
                    return body
            except urllib.error.HTTPError as error:
                if error.code == 429:
                    self.throttled += 1
                    reset = error.headers.get('x-ratelimit-reset') or error.headers.get('retry-after') or '30'
                    time.sleep(min(90, int(float(reset)) + 2))
                    continue
                if error.code in (500, 502, 503, 504) and attempt < attempts - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == attempts - 1:
                    raise
                time.sleep(5 * (attempt + 1))
        raise RuntimeError(f'OpenAQ request kept failing: {path}')


def parse(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def choose_sensors(sensors, start, end):
    """One sensor per pollutant: convertible unit, most recent data in the window."""
    chosen, considered = {}, []
    for sensor in sensors:
        info = sensor.get('parameter') or {}
        pollutant = POLLUTANTS.get((info.get('name') or '').lower())
        first = (sensor.get('datetimeFirst') or {}).get('utc')
        last = (sensor.get('datetimeLast') or {}).get('utc')
        entry = {'sensor_id': sensor.get('id'), 'parameter': info.get('name'), 'units': info.get('units'),
                 'first_utc': first, 'last_utc': last,
                 'observed_count': (sensor.get('coverage') or {}).get('observedCount')}
        if not pollutant:
            continue
        if normalize(pollutant, 1, info.get('units') or '') is None:
            # A gas labelled in ppb cannot become a mass concentration without
            # temperature and pressure, and this provider's ppb labels for Indian
            # gases are not reliable enough to assume them.
            considered.append(dict(entry, decision='rejected_unit_not_mass_concentration'))
            continue
        if not first or not last or parse(last) < start or parse(first) >= end:
            considered.append(dict(entry, decision='rejected_no_data_in_window'))
            continue
        current = chosen.get(pollutant)
        if current is None or (last, entry['observed_count'] or 0) > (current['last_utc'], current['observed_count'] or 0):
            if current is not None:
                considered.append(dict(current, decision='superseded_by_more_recent_sensor'))
            chosen[pollutant] = dict(entry, pollutant=pollutant)
        else:
            considered.append(dict(entry, decision='superseded_by_more_recent_sensor'))
    return chosen, considered


def windows(start, end, hours=WINDOW_HOURS):
    spans, cursor = [], start
    while cursor < end:
        upper = min(end, cursor + timedelta(hours=hours))
        spans.append((cursor, upper))
        cursor = upper
    return spans


def rows_of(results, start, end):
    """Every hourly bin in the window, unfiltered apart from shape."""
    rows = []
    for item in results:
        try:
            begin = parse(item['period']['datetimeFrom']['utc'])
            finish = parse(item['period']['datetimeTo']['utc'])
        except (KeyError, TypeError, ValueError):
            continue
        if not start <= begin < end:
            continue
        rows.append((begin.isoformat(), finish.isoformat(), item.get('value'),
                     (item.get('parameter') or {}).get('units'),
                     (item.get('coverage') or {}).get('percentCoverage'),
                     int(bool((item.get('flagInfo') or {}).get('hasFlags')))))
    return rows


def fetch_sensor(client, sensor, start, end, checkpoint_dir=None):
    from src.research.calibration.checkpoint import write_json
    lower = max(start, parse(sensor['first_utc']).replace(minute=0, second=0, microsecond=0))
    upper = min(end, parse(sensor['last_utc']) + timedelta(hours=1))
    collected, log = {}, []
    for begin, finish in windows(lower, upper):
        params = {'datetime_from': begin.isoformat(), 'datetime_to': finish.isoformat(), 'limit': PAGE}
        cache = None
        if checkpoint_dir is not None:
            identity = hashlib.sha256(json.dumps([sensor['sensor_id'], params],sort_keys=True).encode()).hexdigest()
            cache = Path(checkpoint_dir) / f'{identity}.json'
        if cache is not None and cache.exists():
            stored = json.loads(cache.read_text(encoding='utf-8'))
            raw = json.dumps(stored['payload'],sort_keys=True,separators=(',', ':')).encode()
            if hashlib.sha256(raw).hexdigest() != stored['sha256'] or stored['request']!=params:
                raise ValueError('OpenAQ window cache checksum mismatch')
            payload = stored['payload']
        else:
            payload = client.get(f"/sensors/{int(sensor['sensor_id'])}/hours", params)
            if cache is not None:
                from src.research.calibration.checkpoint import write_json
                raw = json.dumps(payload,sort_keys=True,separators=(',', ':')).encode()
                write_json(cache, {'payload': payload,'sha256':hashlib.sha256(raw).hexdigest(),
                                  'request':params,'retrieved_at':datetime.now(timezone.utc).isoformat()})
        results = payload.get('results') or []
        for row in rows_of(results, begin, finish):
            collected[row[0]] = row
        log.append({'from': begin.isoformat(), 'to': finish.isoformat(), 'returned': len(results)})
        if len(results) >= PAGE:
            # Existing first-page checkpoints remain valid. Request only missing
            # pages, with a separate immutable identity for each request.
            from src.research.calibration.repair_archive import validate_repair_payload
            page = 2
            while len(results) >= PAGE:
                if page > 100:
                    raise ValueError('OpenAQ pagination exceeded safety bound')
                extra_params = dict(params, page=page)
                extra_cache = None
                if checkpoint_dir is not None:
                    identity = hashlib.sha256(json.dumps([sensor['sensor_id'], extra_params],sort_keys=True).encode()).hexdigest()
                    extra_cache = Path(checkpoint_dir)/f'{identity}.json'
                if extra_cache is not None and extra_cache.exists():
                    stored = json.loads(extra_cache.read_text(encoding='utf-8'))
                    raw = json.dumps(stored['payload'],sort_keys=True,separators=(',', ':')).encode()
                    if hashlib.sha256(raw).hexdigest()!=stored['sha256'] or stored['request']!=extra_params:
                        raise ValueError('OpenAQ page cache checksum/request mismatch')
                    extra = stored['payload']
                else:
                    extra = client.get(f"/sensors/{int(sensor['sensor_id'])}/hours", extra_params)
                    validate_repair_payload(extra, sensor, sensor['pollutant'], page)
                    if extra_cache is not None:
                        raw = json.dumps(extra,sort_keys=True,separators=(',', ':')).encode()
                        write_json(extra_cache,{'payload':extra,'sha256':hashlib.sha256(raw).hexdigest(),
                            'request':extra_params,'retrieved_at':datetime.now(timezone.utc).isoformat()})
                results = validate_repair_payload(extra, sensor, sensor['pollutant'], page)
                for row in rows_of(results,begin,finish):
                    if row[0] in collected and collected[row[0]]!=row:
                        raise ValueError('OpenAQ pagination conflicts with an earlier bin')
                    collected[row[0]]=row
                log[-1].setdefault('additional_pages',[]).append({'page':page,'returned':len(results)})
                page += 1
            log[-1]['pagination_complete']=True
    return [collected[key] for key in sorted(collected)], log


def write_rows(path, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(FIELDS)
    writer.writerows(rows)
    data = buffer.getvalue().encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the gzip bytes, and therefore the checksum, reproducible.
    with open(path, 'wb') as handle, gzip.GzipFile(fileobj=handle, mode='wb', mtime=0) as archive:
        archive.write(data)
    return hashlib.sha256(path.read_bytes()).hexdigest(), hashlib.sha256(data).hexdigest()


def shard_path(shard):
    return MANIFEST.with_name(f'openaq_hours_manifest.shard{shard}.json')


def already_done():
    """Stations completed by any earlier run or shard, so nothing is fetched twice."""
    done = {}
    for path in [MANIFEST, *sorted(MANIFEST.parent.glob('openaq_hours_manifest.shard*.json'))]:
        if path.exists():
            for key, entry in json.loads(path.read_text(encoding='utf-8')).get('stations', {}).items():
                if entry.get('complete'):
                    from src.research.calibration.checkpoint import verify
                    for record in entry.get('sensors', {}).values():
                        if record.get('file'):
                            verify(record)
                    done[key] = entry
    return done


def merge():
    """Fold the shard manifests into the single committed manifest."""
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {
        'source': 'OpenAQ v3 /sensors/{id}/hours', 'stations': {}}
    for path in sorted(MANIFEST.parent.glob('openaq_hours_manifest.shard*.json')):
        shard = json.loads(path.read_text(encoding='utf-8'))
        for key, entry in shard.get('stations', {}).items():
            if entry.get('complete') or key not in manifest['stations']:
                manifest['stations'][key] = entry
        for field in ('window', 'selection_sha256', 'note'):
            if field in shard:
                manifest[field] = shard[field]
    manifest['stations'] = dict(sorted(manifest['stations'].items(), key=lambda kv: int(kv[0])))
    manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
    manifest['stations_complete'] = sum(1 for s in manifest['stations'].values() if s.get('complete'))
    manifest['rows'] = sum(s.get('rows') or 0 for e in manifest['stations'].values()
                           for s in (e.get('sensors') or {}).values())
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    return manifest


def run(start, end, limit=None, per_minute=42, shard=None, of=1):
    selection = json.loads(SELECTION.read_text(encoding='utf-8'))
    stations = selection['stations'][:limit] if limit else selection['stations']
    target = MANIFEST if shard is None else shard_path(shard)
    if shard is not None:
        stations = [s for index, s in enumerate(stations) if index % of == shard]
    manifest = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {
        'source': 'OpenAQ v3 /sensors/{id}/hours', 'stations': {}}
    expected_window = [start.isoformat(), end.isoformat()]
    expected_selection = hashlib.sha256(SELECTION.read_bytes()).hexdigest()
    normalized_selection = SELECTION.read_bytes().replace(b'\r\n',b'\n')
    equivalent_selection_hashes={expected_selection,hashlib.sha256(normalized_selection).hexdigest(),
        hashlib.sha256(normalized_selection.replace(b'\n',b'\r\n')).hexdigest()}
    for previous_path in [MANIFEST, *sorted(MANIFEST.parent.glob('openaq_hours_manifest.shard*.json'))]:
        if previous_path.exists():
            from src.research.calibration.checkpoint import read_json
            previous_manifest = read_json(previous_path)
            if previous_manifest.get('window') not in (None, expected_window):
                raise ValueError('Existing OpenAQ manifest has another window; use a versioned cache')
            if previous_manifest.get('selection_sha256') not in equivalent_selection_hashes | {None}:
                raise ValueError('Existing OpenAQ manifest has another station selection')
    finished = already_done()
    manifest.update({'window': [start.isoformat(), end.isoformat()],
                     'selection_sha256': hashlib.sha256(SELECTION.read_bytes()).hexdigest(),
                     'note': 'Raw hourly bins, unfiltered. OpenAQ provider is CPCB for every station; '
                             'values are not an official CPCB export.'})
    client = Client(per_minute=per_minute)
    began = time.monotonic()
    for index, station in enumerate(stations, 1):
        key = str(station['location_id'])
        if manifest['stations'].get(key, {}).get('complete') or key in finished:
            continue
        try:
            payload = client.get(f"/locations/{station['location_id']}/sensors")
        except Exception as error:  # noqa: BLE001 - recorded, the walk continues
            manifest['stations'][key] = {'complete': False, 'error': type(error).__name__}
            continue
        SENSORS.mkdir(parents=True, exist_ok=True)
        (SENSORS / f'{key}.json').write_text(json.dumps(payload), encoding='utf-8')
        chosen, considered = choose_sensors(payload.get('results') or [], start, end)
        entry = {'name': station['name'], 'city': station['city'], 'sensors': {}, 'not_used': considered,
                 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'complete': False}
        previous = manifest['stations'].get(key, {})
        failed = False
        for pollutant, sensor in sorted(chosen.items()):
            old = previous.get('sensors', {}).get(pollutant, {})
            if old.get('file') and old.get('sensor_id') == sensor['sensor_id']:
                from src.research.calibration.checkpoint import verify
                verify(old)
                entry['sensors'][pollutant] = old
                continue
            try:
                rows, log = fetch_sensor(client, sensor, start, end,
                                         checkpoint_dir=ROOT / key / 'windows')
            except Exception as error:  # noqa: BLE001
                entry['sensors'][pollutant] = dict(sensor, error=type(error).__name__)
                failed = True
                continue
            path = ROOT / key / f"{pollutant.replace('.', '').lower()}_{sensor['sensor_id']}.csv.gz"
            file_hash, content_hash = write_rows(path, rows)
            entry['sensors'][pollutant] = dict(
                sensor, file=config.portable(path), rows=len(rows), sha256=file_hash,
                content_sha256=content_hash, requests=log,
                first_row=rows[0][0] if rows else None, last_row=rows[-1][0] if rows else None)
            # Save each completed sensor, not only the station, so interruption
            # cannot trigger a repeat download of completed sensor history.
            from src.research.calibration.checkpoint import write_json
            manifest['stations'][key] = entry
            write_json(target, manifest)
        entry['complete'] = not failed
        manifest['stations'][key] = entry
        manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
        manifest['requests_this_run'] = client.requests
        target.parent.mkdir(parents=True, exist_ok=True)
        from src.research.calibration.checkpoint import write_json
        write_json(target, manifest)
        elapsed = time.monotonic() - began
        print(f"[{index}/{len(stations)}] {station['name'][:44]:44s} "
              f"{ {p: s.get('rows') for p, s in entry['sensors'].items()} } "
              f"requests={client.requests} throttled={client.throttled} elapsed={elapsed / 60:.1f}m",
              flush=True)
    done = sum(1 for s in manifest['stations'].values() if s.get('complete'))
    print(json.dumps({'stations_complete': done, 'stations_selected': len(stations),
                      'requests': client.requests, 'throttled': client.throttled}), flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default='2025-02-01')
    parser.add_argument('--end', default='2026-10-08')
    parser.add_argument('--limit', type=int, default=None, help='only the first N selected stations')
    parser.add_argument('--per-minute', type=int, default=42,
                        help='request pace; the key allows 60 and the live site shares it')
    parser.add_argument('--shard', type=int, default=None, help='walk only stations where index %% of == shard')
    parser.add_argument('--of', type=int, default=1, help='number of shards sharing the rate limit')
    parser.add_argument('--merge', action='store_true', help='fold shard manifests into the main manifest and exit')
    args = parser.parse_args()
    if args.merge:
        merged = merge()
        print(json.dumps({'stations_complete': merged['stations_complete'], 'rows': merged['rows']}))
        return 0
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    run(start, end, limit=args.limit, per_minute=args.per_minute, shard=args.shard, of=args.of)
    return 0


if __name__ == '__main__':
    sys.exit(main())
