"""One bounded ADS smoke request; credentials and provider messages never logged.

Run with the ADS-enabled environment: .venv-live/Scripts/python -m
src.research.calibration.ads_probe. The official client alone consumes its
private credential configuration. This module never reads that file.
"""
import contextlib
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
DATASET = 'cams-global-atmospheric-composition-forecasts'
REQUEST = {
    'variable': ['particulate_matter_2.5um'],
    'date': '2025-02-18', 'time': ['00:00'],
    'leadtime_hour': ['24'], 'type': ['forecast'],
    'data_format': 'grib', 'area': [29.2, 76.8, 28.4, 77.6],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def request_hash():
    return hashlib.sha256(json.dumps({'dataset': DATASET, 'request': REQUEST},
                                   sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def safe_error(error):
    # Inspect only to classify; NEVER persist repr, traceback, response or URL.
    response = getattr(error, 'response', None)
    status = getattr(response, 'status_code', None)
    message = str(error).lower()
    category = 'CLIENT_OR_SERVICE_ERROR'
    if status == 401:
        category = 'AUTHENTICATION_REJECTED'
    elif status == 403:
        category = 'ACCESS_OR_TERMS_REJECTED'
    elif status == 400:
        category = 'REQUEST_REJECTED'
    elif status == 429:
        category = 'SERVICE_RATE_LIMIT'
    elif status is not None and status >= 500:
        category = 'SERVICE_UNAVAILABLE'
    return {'category': category, 'http_status': status,
            'terms_mentioned': any(word in message for word in ('licence', 'license', 'terms'))}


def status():
    """Read the existing remote job; never submit or print provider responses."""
    import cdsapi
    record = json.loads((ROOT / 'results/research/cams_ads_probe.json').read_text(encoding='utf-8'))
    result = {'local_status': record['status']}
    logging.disable(sys.maxsize)
    with open(os.devnull, 'w') as silent, contextlib.redirect_stdout(silent), contextlib.redirect_stderr(silent):
        try:
            client = cdsapi.Client(url='https://ads.atmosphere.copernicus.eu/api',
                                  quiet=True, debug=False, progress=False, retry_max=1, timeout=30)
            state = client.client.get_remote(record['request_id']).status
            result['remote_status'] = state if state in (
                'accepted', 'running', 'successful', 'failed', 'rejected', 'dismissed', 'deleted') else 'UNKNOWN'
        except Exception as error:
            result['error'] = safe_error(error)
    result['checked_at_utc'] = now()
    write(ROOT / 'results/research/cams_ads_probe_status.json', result)
    print(json.dumps(result))
    return 0


def verify_fields(fields):
    """Fail closed on analysis, changed run/lead/valid time, units or parameter."""
    if len(fields) != 1:
        raise ValueError('Expected exactly one operational forecast field')
    field = fields[0]
    from datetime import timedelta
    reference = datetime.strptime(str(field['dataDate']) + f"{field['dataTime']:04d}", '%Y%m%d%H%M').replace(tzinfo=timezone.utc)
    valid = datetime.strptime(str(field['validityDate']) + f"{field['validityTime']:04d}", '%Y%m%d%H%M').replace(tzinfo=timezone.utc)
    if (field['dataType'] != 'fc' or field['paramId'] != 210073 or field['stepUnits'] != 1
            or float(field['step']) != 24 or reference.isoformat() != '2025-02-18T00:00:00+00:00'
            or valid != reference + timedelta(hours=24) or field['units'] != 'kg m**-3'):
        raise ValueError('Decoded field does not match the expected operational forecast')
    return reference, valid


def validate_grib_container(path):
    """Require complete, contiguous GRIB messages; reject text and trailing junk."""
    size = Path(path).stat().st_size
    messages, editions, offset = 0, set(), 0
    with Path(path).open('rb') as handle:
        while offset < size:
            header = handle.read(8)
            if len(header) != 8 or header[:4] != b'GRIB':
                raise ValueError('Not a contiguous GRIB container')
            edition = header[7]
            if edition == 1:
                length = int.from_bytes(header[4:7], 'big')
                minimum = 12
            elif edition == 2:
                extra = handle.read(8)
                if len(extra) != 8:
                    raise ValueError('Truncated GRIB2 header')
                length = int.from_bytes(extra, 'big')
                minimum = 20
            else:
                raise ValueError('Unsupported GRIB edition')
            if length < minimum or offset + length > size:
                raise ValueError('Truncated or invalid GRIB message length')
            handle.seek(offset + length - 4)
            if handle.read(4) != b'7777':
                raise ValueError('Missing GRIB message terminator')
            offset += length
            handle.seek(offset)
            messages += 1
            editions.add(edition)
    if not messages:
        raise ValueError('Empty GRIB container')
    return {'bytes': size, 'messages': messages, 'editions': sorted(editions),
            'complete_message_framing': True}


def audit():
    """Verify the downloaded GRIB against the tiny request, never target labels."""
    import eccodes as ec
    evidence = ROOT / 'results/research/cams_ads_probe.json'
    record = json.loads(evidence.read_text(encoding='utf-8'))
    if record['request_sha256'] != request_hash() or record['request'] != REQUEST or record['dataset'] != DATASET:
        raise ValueError('Probe request metadata differs')
    if record['status'] not in ('DOWNLOADED_PENDING_GRIB_AUDIT', 'VERIFIED_OPERATIONAL_FORECAST'):
        raise ValueError('A downloaded probe is required before audit')
    path = ROOT / record['file']
    if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
        raise ValueError('Probe file checksum differs')
    container = validate_grib_container(path)
    fields = []
    with path.open('rb') as handle:
        while (gid := ec.codes_grib_new_from_file(handle)) is not None:
            try:
                keys = ('dataDate', 'dataTime', 'step', 'stepUnits', 'validityDate',
                        'validityTime', 'dataType', 'shortName', 'paramId', 'units',
                        'typeOfLevel', 'level', 'numberOfDataPoints', 'edition',
                        'latitudeOfFirstGridPointInDegrees', 'longitudeOfFirstGridPointInDegrees',
                        'latitudeOfLastGridPointInDegrees', 'longitudeOfLastGridPointInDegrees',
                        'Ni', 'Nj', 'numberOfMissing', 'iDirectionIncrementInDegrees',
                        'jDirectionIncrementInDegrees', 'centre', 'marsClass', 'marsStream',
                        'marsType', 'packingType', 'bitsPerValue', 'totalLength')
                field = {key: ec.codes_get(gid, key) for key in keys}
                if (field['centre'],field['marsClass'],field['marsStream'],field['marsType']) != ('ecmf','mc','oper','fc'):
                    raise ValueError('Probe does not identify the ECMWF CAMS operational forecast product')
                values = ec.codes_get_values(gid)
                import math
                if field['numberOfMissing'] or not all(math.isfinite(v) and v >= 0 for v in values):
                    raise ValueError('Probe contains missing/invalid concentration values')
                if field['Ni'] != 3 or field['Nj'] != 3 or field['numberOfDataPoints'] != 9 or field['typeOfLevel'] != 'surface':
                    raise ValueError('Probe is not the requested 3 by 3 surface subset')
                expected = {'latitudeOfFirstGridPointInDegrees':29.2,'longitudeOfFirstGridPointInDegrees':76.8,
                    'latitudeOfLastGridPointInDegrees':28.4,'longitudeOfLastGridPointInDegrees':77.6,
                    'iDirectionIncrementInDegrees':.4,'jDirectionIncrementInDegrees':.4}
                if any(abs(field[key]-value)>1e-6 for key,value in expected.items()):
                    raise ValueError('Decoded probe area/grid differs from request')
                field['minimum_kg_m3'],field['maximum_kg_m3'] = float(min(values)),float(max(values))
                field['values_kg_m3_row_major'] = values.tolist()
                fields.append(field)
            finally:
                ec.codes_release(gid)
    reference, valid = verify_fields(fields)
    if container['messages'] != len(fields):
        raise ValueError('Probe container and decoder message counts differ')
    record.update(status='VERIFIED_OPERATIONAL_FORECAST', decoded_fields=fields,
                  container_validation=container,
                  reference_time_utc=reference.isoformat(), lead_hours=24,
                  valid_time_utc=valid.isoformat(), audited_at_utc=now(),
                  decoder={'name': 'eccodes', 'python_version': importlib.metadata.version('eccodes'),
                           'library_version': ec.codes_get_api_version()},
                  full_acquisition_authorized_by_probe=True,
                  verification_scope='One surface PM2.5 forecast only; gas conversion and archive completeness not established')
    write(evidence, record)
    write(path.parent / 'retrieval.json', record)
    print(json.dumps({'status': record['status'], 'reference_time_utc': reference.isoformat(),
                      'lead_hours': 24, 'valid_time_utc': valid.isoformat(), 'bytes': record['bytes']}))
    return 0


def run():
    import cdsapi
    identity = request_hash()
    folder = ROOT / 'data/research/cams_operational/smoke-v1' / identity
    evidence = ROOT / 'results/research/cams_ads_probe.json'
    ledger = folder / 'retrieval.json'
    folder.mkdir(parents=True, exist_ok=True)
    record = {'dataset': DATASET, 'request': REQUEST, 'request_sha256': identity,
              'cdsapi_version': importlib.metadata.version('cdsapi'),
              'credential_file_exists': (Path.home() / '.cdsapirc').is_file(),
              'started_at_utc': now(), 'status': 'PREPARED',
              'full_acquisition_authorized_by_probe': False,
              'locked_final_test_accessed': False}
    if ledger.exists():
        record = json.loads(ledger.read_text(encoding='utf-8'))
        if record['request_sha256'] != identity:
            raise ValueError('Probe request identity changed')
        # Never resubmit a failed or interrupted request without an explicit audit.
        if record['status'] in ('DOWNLOADED_PENDING_GRIB_AUDIT', 'VERIFIED_OPERATIONAL_FORECAST'):
            target = ROOT / record['file']
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != record['sha256']:
                raise ValueError('Existing probe file checksum differs; refusing another request')
            print(json.dumps({'status': record['status'], 'reused_existing_attempt': True}))
            return 0
        if record['status'] != 'SUBMITTED':
            print(json.dumps({'status': record['status'], 'reused_existing_attempt': True}))
            return 1
    def save():
        write(ledger, record)
        write(evidence, record)
    logging.disable(sys.maxsize)
    with open(os.devnull, 'w') as silent, contextlib.redirect_stdout(silent), contextlib.redirect_stderr(silent):
        try:
            client = cdsapi.Client(url='https://ads.atmosphere.copernicus.eu/api',
                quiet=True, debug=False, progress=False, retry_max=1, timeout=60,
                wait_until_complete=False, delete=False,
                info_callback=lambda *a: None, warning_callback=lambda *a: None,
                error_callback=lambda *a: None, debug_callback=lambda *a: None)
            if record['status'] == 'SUBMITTED':
                remote = client.client.get_remote(record['request_id'])
            else:
                record['status'] = 'SUBMITTING'
                save()
                remote = client.retrieve(DATASET, REQUEST)
                record.update(status='SUBMITTED', request_id=remote.request_id,
                              submitted_at_utc=now())
                save()
            target = folder / 'sample.grib'
            remote.download(str(target))
            record.update(status='DOWNLOADED_PENDING_GRIB_AUDIT', retrieved_at_utc=now(),
                          file=target.relative_to(ROOT).as_posix(), bytes=target.stat().st_size,
                          sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        except Exception as error:
            record.update(status='FAILED', failed_at_utc=now(), error=safe_error(error))
        save()
    print(json.dumps({'status': record['status'], 'error': record.get('error'),
                      'bytes': record.get('bytes'), 'evidence': evidence.relative_to(ROOT).as_posix()}))
    return 0 if record['status'] == 'DOWNLOADED_PENDING_GRIB_AUDIT' else 1


if __name__ == '__main__':
    sys.exit(status() if '--status' in sys.argv else audit() if '--audit' in sys.argv else run())
