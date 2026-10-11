"""Modelled and satellite inputs for the retrospective study, cached immutably.

Three archives, and they are not equally trustworthy as issue-time inputs. That
difference is the most important fact about this study, so it is recorded on
every file:

CAMS  Open-Meteo serves CAMS global fields for past dates, but not the run that
      produced them, and it does not serve earlier runs for a given hour (its
      `_previous_dayN` variables return nulls for air quality; verified). The
      archived value for an hour therefore comes from a model run initialised
      close to that hour - after a 20:00 IST issue time for most or all of the
      target day. It is a SHORT-LEAD PROXY, not the forecast available at issue
      time. Genuine archived runs need Copernicus ADS access, which is not held.

Weather  Open-Meteo's Previous Runs API does serve earlier forecasts. `_day2`
      values come from a run initialised at least 48 hours before the valid
      hour, which is before the issue time for every hour of the target day.
      Conservative, and strictly issue-time valid.

FIRMS VIIRS NOAA-21 near-real-time detections carry acquisition times, so the
      issue-time cutoff is applied to each detection downstream.

    python -m src.research.calibration.model_archives cams|weather|firms
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src import config
from src.features.static_site import cams_cell
from src.ingestion.settings import load_env, secret
from src.research.calibration.catalogue import SELECTION

ROOT = config.PROJECT_ROOT / 'data/research'
MANIFESTS = config.PROJECT_ROOT / 'results/research/data_manifests'
START, END = '2025-02-01', '2026-10-08'

CAMS_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'
CAMS_VARIABLES = ('pm2_5', 'pm10', 'nitrogen_dioxide', 'sulphur_dioxide', 'carbon_monoxide', 'ozone')
CAMS_SOURCE = 'CAMS_GLOBAL_VIA_OPEN_METEO_SHORT_LEAD_ARCHIVE'

WEATHER_URL = 'https://previous-runs-api.open-meteo.com/v1/forecast'
WEATHER_MODEL = 'gfs_seamless'
WEATHER_LEAD = 'previous_day2'
WEATHER_VARIABLES = ('temperature_2m', 'relative_humidity_2m', 'wind_speed_10m', 'wind_direction_10m',
                     'precipitation', 'surface_pressure', 'shortwave_radiation', 'cloud_cover')

FIRMS_SOURCE = 'VIIRS_NOAA21_NRT'
INDIA_BOX = '67,5,99,38'  # west,south,east,north


def fetch(url, params=None, attempts=5, pause=0.0, text=False):
    full = url + (('?' + urllib.parse.urlencode(params)) if params else '')
    for attempt in range(attempts):
        if pause:
            time.sleep(pause)
        try:
            request = urllib.request.Request(full, headers={'User-Agent': 'airguard-india-research/1.0'})
            with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310 - fixed hosts
                raw = response.read()
            return raw.decode('utf-8') if text else json.loads(raw.decode('utf-8')), raw
        except urllib.error.HTTPError as error:
            if error.code == 429 or error.code >= 500:
                time.sleep(20 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(10 * (attempt + 1))
    # FIRMS credentials appear in the URL path. Never include it in an error.
    raise RuntimeError('Archive request kept failing after bounded retries')


def store(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as handle, gzip.GzipFile(fileobj=handle, mode='wb', mtime=0) as archive:
        archive.write(raw)
    return {'file': config.portable(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'content_sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def stations():
    return json.loads(SELECTION.read_text(encoding='utf-8'))['stations']


def load_manifest(name, header):
    path = MANIFESTS / name
    if path.exists():
        return path, json.loads(path.read_text(encoding='utf-8'))
    return path, dict(header, files={})


def save_manifest(path, manifest):
    manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    from src.research.calibration.checkpoint import write_json
    write_json(path, manifest)


def cams(pause=4.0):
    """One request per CAMS cell, at the cell centre."""
    cells = {}
    for station in stations():
        cell = cams_cell(station['latitude'], station['longitude'])
        cells.setdefault(cell['cell_id'], dict(cell, stations=[]))['stations'].append(station['location_id'])
    path, manifest = load_manifest('cams_archive_manifest.json', {
        'source': CAMS_SOURCE, 'endpoint': CAMS_URL, 'variables': list(CAMS_VARIABLES),
        'window': [START, END], 'units': 'ug/m3 for every variable, as served',
        'issue_time_valid': False,
        'why_not': 'The provider archives fields for past hours without the run that produced them and '
                   'does not serve earlier runs for air quality. Values for a target day come from runs '
                   'initialised at or after the 20:00 IST issue time. This is a short-lead proxy for the '
                   'forecast that would have been available, and it must never be described as that forecast.',
        'archive_status': 'CAMS_ARCHIVE_STATUS=PENDING_MANUAL_CREDENTIAL_OR_TERMS (Copernicus ADS)',
    })
    for cell_id, cell in sorted(cells.items()):
        if cell_id in manifest['files']:
            continue
        params = {'latitude': cell['centre_latitude'], 'longitude': cell['centre_longitude'],
                  'hourly': ','.join(CAMS_VARIABLES), 'start_date': START, 'end_date': END,
                  'domains': 'cams_global', 'timezone': 'UTC'}
        payload, raw = fetch(CAMS_URL, params, pause=pause)
        hours = len((payload.get('hourly') or {}).get('time') or [])
        record = store(ROOT / 'cams' / f'{cell_id}.json.gz', raw)
        manifest['files'][cell_id] = dict(record, cell=cell, hours=hours, request=params,
                                          retrieved_at=datetime.now(timezone.utc).isoformat())
        save_manifest(path, manifest)
        print(f"cams {cell_id} hours={hours} stations={len(cell['stations'])} "
              f"[{len(manifest['files'])}/{len(cells)}]", flush=True)
    manifest['cells'] = len(cells)
    manifest['stations_sharing_a_cell'] = sum(len(c['stations']) for c in cells.values() if len(c['stations']) > 1)
    save_manifest(path, manifest)
    return manifest


def weather(pause=22.0):
    """Archived forecasts at a strictly issue-time-valid lead, one per ~11 km point."""
    points = {}
    for station in stations():
        key = f"{round(station['latitude'], 1):+06.1f}_{round(station['longitude'], 1):+07.1f}"
        points.setdefault(key, {'latitude': round(station['latitude'], 1),
                                'longitude': round(station['longitude'], 1), 'stations': []})
        points[key]['stations'].append(station['location_id'])
    path, manifest = load_manifest('weather_archive_manifest.json', {
        'source': 'OPEN_METEO_PREVIOUS_RUNS', 'endpoint': WEATHER_URL, 'model': WEATHER_MODEL,
        'lead': WEATHER_LEAD, 'variables': list(WEATHER_VARIABLES), 'window': [START, END],
        'issue_time_valid': True,
        'why': 'Each value was forecast by a run initialised at least 48 hours before its valid hour. '
               'Every hour of a target day therefore comes from a run initialised before the 20:00 IST '
               'issue time of the previous day. This is older than the forecast an operator would have '
               'had, so it handicaps the weather features rather than flattering them.',
        'not_available': 'boundary_layer_height is not archived at any previous-run lead (verified: all null).',
    })
    for key, point in sorted(points.items()):
        if key in manifest['files']:
            continue
        params = {'latitude': point['latitude'], 'longitude': point['longitude'],
                  'hourly': ','.join(f'{v}_{WEATHER_LEAD}' for v in WEATHER_VARIABLES),
                  'start_date': START, 'end_date': END, 'models': WEATHER_MODEL, 'timezone': 'UTC'}
        payload, raw = fetch(WEATHER_URL, params, pause=pause)
        hours = len((payload.get('hourly') or {}).get('time') or [])
        record = store(ROOT / 'weather' / f'{key}.json.gz', raw)
        manifest['files'][key] = dict(record, point=point, hours=hours, request=params,
                                      grid=[payload.get('latitude'), payload.get('longitude')],
                                      retrieved_at=datetime.now(timezone.utc).isoformat())
        save_manifest(path, manifest)
        print(f"weather {key} hours={hours} [{len(manifest['files'])}/{len(points)}]", flush=True)
    manifest['points'] = len(points)
    save_manifest(path, manifest)
    return manifest


def firms(pause=2.0, span=5):
    """VIIRS NOAA-21 NRT detections over India, in five-day requests."""
    load_env()
    key = secret('NASA_FIRMS_MAP_KEY')
    if not key:
        raise SystemExit('NASA_FIRMS_MAP_KEY is not configured.')
    path, manifest = load_manifest('firms_archive_manifest.json', {
        'source': FIRMS_SOURCE, 'endpoint': 'https://firms.modaps.eosdis.nasa.gov/api/area/csv',
        'area': INDIA_BOX, 'window': [START, END], 'issue_time_valid': True,
        'why': 'Near-real-time detections carry acquisition date and time. The issue-time cutoff, with a '
               'three-hour processing allowance, is applied to each detection when features are built.',
    })
    cursor, last = date.fromisoformat(START), date.fromisoformat(END)
    while cursor <= last:
        name = cursor.isoformat()
        if name not in manifest['files']:
            # The key sits in the URL path, so the URL is never logged or stored.
            url = (f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{FIRMS_SOURCE}/'
                   f'{INDIA_BOX}/{span}/{name}')
            text, raw = fetch(url, pause=pause, text=True)
            if not text.startswith('latitude') and 'latitude' not in text[:200]:
                raise RuntimeError(f'FIRMS returned an unexpected body for {name}')
            record = store(ROOT / 'firms' / f'{name}.csv.gz', raw)
            manifest['files'][name] = dict(record, days=span, detections=max(0, text.count('\n') - 1),
                                           retrieved_at=datetime.now(timezone.utc).isoformat())
            save_manifest(path, manifest)
            print(f"firms {name} detections={manifest['files'][name]['detections']}", flush=True)
        cursor += timedelta(days=span)
    save_manifest(path, manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', choices=('cams', 'weather', 'firms'))
    args = parser.parse_args()
    result = {'cams': cams, 'weather': weather, 'firms': firms}[args.archive]()
    print(json.dumps({'archive': args.archive, 'files': len(result['files'])}), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
