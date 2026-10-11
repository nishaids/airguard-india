"""Resume only inherited OpenAQ windows marked ``page_limit_reached``.

Original sensor files and download manifests are never modified. Successful
extra pages have immutable checkpoints, and repaired sensors are new versioned
files exposed through ``openaq_repairs.json``. This module does not apply QC.
"""
from __future__ import annotations

import argparse
import copy
import csv
import gzip
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from src import config
from src.nationwide.aqi import normalize
from src.research.calibration.checkpoint import canonical_hash, read_json, verify, write_json
from src.research.calibration.openaq_archive import Client, FIELDS, PAGE, POLLUTANTS, rows_of, write_rows

VERSION = 'openaq-pagination-repair-v1'
TERMINAL = {'repaired', 'no_missing_rows'}


class RepairCheckFailed(ValueError):
    """A safe check name, never an upstream exception or credential-bearing URL."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _checked(code, action, *args):
    try:
        return action(*args)
    except Exception as error:
        raise RepairCheckFailed(code) from error


def _now():
    return datetime.now(timezone.utc).isoformat()


def _utc(value):
    timestamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('Repair timestamp has no timezone')
    return timestamp.astimezone(timezone.utc)


def _cache_path(value):
    path = (config.PROJECT_ROOT / value).resolve()
    if not path.is_relative_to((config.PROJECT_ROOT / 'data/research').resolve()):
        raise ValueError('Repair cache leaves data/research')
    return path


def validate_sensor_metadata(record, pollutant):
    """Validate identity and raw CSV shape without excluding low-quality bins."""
    if int(record['sensor_id']) <= 0 or POLLUTANTS.get(record['parameter'].lower()) != pollutant:
        raise ValueError('Repair sensor identity or parameter mismatch')
    if record.get('pollutant', pollutant) != pollutant:
        raise ValueError('Repair pollutant metadata mismatch')
    if normalize(pollutant, 1, record['units']) is None:
        raise ValueError('Repair sensor unit is not a supported mass concentration')
    _utc(record['first_utc'])
    _utc(record['last_utc'])
    with gzip.open(_cache_path(record['file']), 'rt', encoding='utf-8', newline='') as handle:
        reader = csv.reader(handle)
        if tuple(next(reader, ())) != FIELDS:
            raise ValueError('Repair base CSV schema mismatch')
        rows = list(reader)
    if len(rows) != record['rows']:
        raise ValueError('Repair base CSV row count mismatch')
    seen = set()
    for row in rows:
        if len(row) != len(FIELDS) or row[5] not in ('0', '1'):
            raise ValueError('Repair base CSV row shape mismatch')
        begin, end = _utc(row[0]), _utc(row[1])
        if end <= begin or begin in seen:
            raise ValueError('Repair base CSV period or duplicate mismatch')
        seen.add(begin)
    if rows and (rows[0][0] != record['first_row'] or rows[-1][0] != record['last_row']):
        raise ValueError('Repair base CSV boundary metadata mismatch')
    return rows


def validate_repair_payload(payload, sensor, pollutant, page):
    """Prove requested pagination and pollutant identity before accepting rows."""
    if not isinstance(payload, dict) or not isinstance(payload.get('results'), list):
        raise ValueError('OpenAQ repair response schema mismatch')
    meta = payload.get('meta')
    if not isinstance(meta, dict) or meta.get('page') != page or meta.get('limit') != PAGE:
        raise ValueError('OpenAQ repair pagination metadata mismatch')
    if len(payload['results']) > PAGE:
        raise ValueError('OpenAQ repair exceeds requested page size')
    for item in payload['results']:
        if not isinstance(item, dict) or 'value' not in item:
            raise ValueError('OpenAQ repair hourly row schema mismatch')
        parameter = item.get('parameter')
        if not isinstance(parameter, dict) or POLLUTANTS.get(str(parameter.get('name', '')).lower()) != pollutant:
            raise ValueError('OpenAQ repair pollutant metadata mismatch')
        if parameter.get('units') != sensor['units']:
            raise ValueError('OpenAQ repair unit metadata mismatch')
        period = item.get('period') or {}
        begin = _utc(period['datetimeFrom']['utc'])
        end = _utc(period['datetimeTo']['utc'])
        if end <= begin:
            raise ValueError('OpenAQ repair period metadata mismatch')
        for field in ('coverage', 'flagInfo'):
            if item.get(field) is not None and not isinstance(item[field], dict):
                raise ValueError('OpenAQ repair ancillary metadata mismatch')
    return payload['results']


def _immutable_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('Immutable repair page checkpoint collision')
    else:
        with path.open('xb') as handle:
            handle.write(raw)
    return {'file': config.portable(path), 'sha256': hashlib.sha256(raw).hexdigest()}


def _page_payload(page_record, request):
    raw = _cache_path(page_record['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != page_record['sha256']:
        raise ValueError('Repair page checkpoint checksum mismatch')
    stored = json.loads(raw)
    if stored.get('request') != request or canonical_hash(stored['payload']) != stored['payload_sha256']:
        raise ValueError('Repair page checkpoint payload or request mismatch')
    return stored['payload']


def _equivalent(first, second):
    """Keep original representations when a page repeats an existing bin."""
    for index, (left, right) in enumerate(zip(first, second)):
        if str(left) == str(right):
            continue
        if index in (2, 4):
            try:
                if float(left) == float(right):
                    continue
            except (TypeError, ValueError):
                pass
        return False
    return True


def _repair_sensor(sensor, pollutant, entry, manifest, output, client_factory, max_pages):
    # Both compressed and decompressed hashes are checked before any API call.
    _checked('base_checksum_validation', verify, sensor)
    base_rows = _checked('base_schema_metadata_validation', validate_sensor_metadata, sensor, pollutant)
    if entry['status'] in TERMINAL:
        expected = entry['override_sha256']
        if canonical_hash({k: v for k, v in entry.items() if k != 'override_sha256'}) != expected:
            raise ValueError('Immutable repair override metadata checksum mismatch')
        if entry.get('replacement'):
            _checked('replacement_checksum_validation', verify, entry['replacement'])
            _checked('replacement_schema_metadata_validation', validate_sensor_metadata, entry['replacement'], pollutant)
        return
    extra = []
    for original in sensor['requests']:
        if original.get('warning') != 'page_limit_reached':
            continue
        begin, end = _utc(original['from']), _utc(original['to'])
        if end <= begin:
            raise ValueError('Repair window boundary mismatch')
        identity = canonical_hash([sensor['sensor_id'], original['from'], original['to']])
        window = entry['windows'].setdefault(identity, {
            'from': original['from'], 'to': original['to'], 'pages': {}, 'status': 'pending'})
        page = 2
        while True:
            if page > max_pages:
                raise ValueError('Repair pagination exceeded safety bound')
            params = {'datetime_from': original['from'], 'datetime_to': original['to'],
                      'limit': PAGE, 'page': page}
            endpoint = f"/sensors/{int(sensor['sensor_id'])}/hours"
            request = {'path': endpoint, 'params': params}
            checkpoint = _cache_path(sensor['file']).parent / 'repair_pages' / sensor['sha256'] / identity / f'page{page}.json'
            page_record = window['pages'].get(str(page))
            if page_record:
                payload = _checked('page_checkpoint_validation', _page_payload, page_record, request)
            elif checkpoint.exists():
                # A crash after writing the page but before updating the manifest
                # must not cause a duplicate request.
                raw = checkpoint.read_bytes()
                page_record = {'file': config.portable(checkpoint), 'sha256': hashlib.sha256(raw).hexdigest()}
                payload = _checked('orphan_page_checkpoint_validation', _page_payload, page_record, request)
                entry['repair_request_log'].append({
                    **request, 'at': _now(), 'status': 'recovered_checkpoint',
                    'returned': len(payload['results']), 'payload_sha256': canonical_hash(payload)})
            else:
                try:
                    payload = _checked('extra_page_request', client_factory().get, endpoint, params)
                    _checked('page_schema_metadata_validation', validate_repair_payload, payload, sensor, pollutant, page)
                    stored = {'request': request, 'payload': payload, 'payload_sha256': canonical_hash(payload),
                              'retrieved_at': _now()}
                    page_record = _checked('page_checkpoint_write', _immutable_json, checkpoint, stored)
                except Exception as error:
                    entry['repair_request_log'].append({
                        'path': endpoint, 'params': params, 'at': _now(),
                        'status': 'failed', 'error_type': type(error).__name__,
                        'check': getattr(error, 'code', 'extra_page_request')})
                    window.update(status='failed', failed_page=page)
                    write_json(output, manifest)
                    raise
                entry['repair_request_log'].append({
                    'path': endpoint, 'params': params, 'at': _now(), 'status': 'success',
                    'returned': len(payload['results']), 'payload_sha256': canonical_hash(payload)})
            results = _checked('page_schema_metadata_validation', validate_repair_payload, payload, sensor, pollutant, page)
            accepted = rows_of(results, begin, end)
            page_record.update(returned=len(results), rows_in_window=len(accepted))
            window['pages'][str(page)] = page_record
            extra.extend(accepted)
            if len(results) < PAGE:
                window.update(status='complete', final_page=page)
                window.pop('failed_page', None)
                write_json(output, manifest)
                break
            write_json(output, manifest)
            page += 1
    merged = {_utc(row[0]): row for row in base_rows}
    for row in extra:
        key = _utc(row[0])
        if key in merged and not _equivalent(merged[key], row):
            raise RepairCheckFailed('immutable_hourly_bin_conflict')
        merged.setdefault(key, row)
    rows = [merged[key] for key in sorted(merged)]
    entry['added_rows'] = len(rows) - len(base_rows)
    entry['checked_at'] = _now()
    entry.pop('last_error_type', None)
    entry.pop('last_failed_check', None)
    if not entry['added_rows']:
        entry['status'] = 'no_missing_rows'
    else:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator='\n')
        writer.writerow(FIELDS)
        writer.writerows(rows)
        content_hash = hashlib.sha256(buffer.getvalue().encode()).hexdigest()
        old_path = _cache_path(sensor['file'])
        name = old_path.name.removesuffix('.csv.gz')
        path = old_path.with_name(f'{name}.repair-v1-{content_hash[:16]}.csv.gz')
        replacement = copy.deepcopy(sensor)
        replacement.update(file=config.portable(path), rows=len(rows), content_sha256=content_hash,
                           first_row=rows[0][0], last_row=rows[-1][0], repair_version=VERSION,
                           base_sha256=sensor['sha256'])
        if path.exists():
            replacement['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            replacement['sha256'], _ = write_rows(path, rows)
        _checked('replacement_checksum_validation', verify, replacement)
        _checked('replacement_schema_metadata_validation', validate_sensor_metadata, replacement, pollutant)
        entry.update(status='repaired', replacement=replacement)
    entry['override_sha256'] = canonical_hash(entry)
    write_json(output, manifest)


def run(*, source_paths=None, repairs_path=None, client=None, per_minute=18, limit=None, max_pages=100):
    """Repair flagged spans only; a failed page resumes without repeating successes."""
    if not 0 < per_minute <= 24:
        raise ValueError('Repair pace must be at most 24 requests per minute')
    if max_pages < 2:
        raise ValueError('Repair page bound must include page 2')
    root = config.PROJECT_ROOT / 'results/research/data_manifests'
    source_paths = source_paths if source_paths is not None else [
        root / 'openaq_hours_manifest.json', *sorted(root.glob('openaq_hours_manifest.shard*.json'))]
    output = Path(repairs_path) if repairs_path is not None else root / 'openaq_repairs.json'
    sources = {}
    for path in source_paths:
        if Path(path).exists():
            for station, record in read_json(path).get('stations', {}).items():
                # A station can be unfinished while one immutable sensor file
                # is already complete; those flagged files also need recovery.
                for pollutant, sensor in record.get('sensors', {}).items():
                    if sensor.get('file'):
                        sources[(str(station), pollutant)] = sensor
    manifest = read_json(output) if output.exists() else {'repair_version': VERSION, 'stations': {}}
    if manifest.get('repair_version') != VERSION:
        raise ValueError('Repair manifest version mismatch')
    active_client = client

    def get_client():
        nonlocal active_client
        if active_client is None:
            active_client = Client(per_minute=per_minute)
        return active_client

    processed = 0
    for (station, pollutant), sensor in sorted(sources.items()):
        if not any(r.get('warning') == 'page_limit_reached' for r in sensor.get('requests', [])):
            continue
        if limit is not None and processed >= limit:
            break
        processed += 1
        sensors = manifest['stations'].setdefault(station, {})
        entry = sensors.setdefault(pollutant, {
            'reason': 'page_limit_reached', 'old_path': sensor['file'],
            'base_sha256': sensor['sha256'], 'base_content_sha256': sensor['content_sha256'],
            'base_sensor_id': sensor['sensor_id'], 'base_record_sha256': canonical_hash(sensor),
            'status': 'pending', 'windows': {}, 'repair_request_log': [], 'failures': []})
        if entry['base_record_sha256'] != canonical_hash(sensor):
            raise ValueError('Inherited sensor changed since repair checkpoint')
        try:
            _repair_sensor(sensor, pollutant, entry, manifest, output, get_client, max_pages)
        except Exception as error:
            # Never persist exception text: it can contain a credential-bearing URL.
            if entry['status'] in TERMINAL:
                raise  # completed overrides remain immutable, including on audit failure
            check = getattr(error, 'code', 'repair_metadata_or_pagination_validation')
            entry.update(status='failed', last_error_type=type(error).__name__, last_failed_check=check)
            entry['failures'].append({'at': _now(), 'error_type': type(error).__name__, 'check': check})
            write_json(output, manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--per-minute', type=int, default=18)
    parser.add_argument('--limit', type=int, help='maximum flagged sensors, not all stations')
    args = parser.parse_args()
    manifest = run(per_minute=args.per_minute, limit=args.limit)
    states = [entry['status'] for sensors in manifest['stations'].values() for entry in sensors.values()]
    print(json.dumps({'repaired': states.count('repaired'), 'no_missing_rows': states.count('no_missing_rows'),
                      'failed': states.count('failed')}))
    return int('failed' in states)


if __name__ == '__main__':
    raise SystemExit(main())
