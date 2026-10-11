"""Audit the inherited caches without API requests or production mutations."""
from __future__ import annotations
import gzip
import hashlib
import json
import time
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from src import config
from src.research.calibration import data
from src.research.calibration.protocol import load

OUT = config.PROJECT_ROOT / 'results/research'
CAMS_ARCHIVE_STATUS = 'PENDING_MANUAL_ADS_CREDENTIAL'


def read_json(path):
    for attempt in range(4):
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            if attempt == 3:
                raise
            time.sleep(.1)  # inherited writers can still be running


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def verify(record):
    path = (config.PROJECT_ROOT / record['file']).resolve()
    if not path.is_relative_to(data.ROOT.resolve()):
        raise ValueError('Research cache path leaves data/research')
    if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
        raise ValueError(f'Checksum mismatch: {record["file"]}')
    with gzip.open(path, 'rb') as handle:
        content = handle.read()
    if hashlib.sha256(content).hexdigest() != record['content_sha256']:
        raise ValueError(f'Content checksum mismatch: {record["file"]}')
    return len(content)


def capture():
    protocol = load()
    selection = read_json(data.MANIFESTS / 'station_selection.json')
    stations = {}
    paths = [data.MANIFESTS / 'openaq_hours_manifest.json',
             *sorted(data.MANIFESTS.glob('openaq_hours_manifest.shard*.json'))]
    for path in paths:
        if path.exists():
            for key, entry in read_json(path).get('stations', {}).items():
                if entry.get('complete'):
                    stations[key] = entry
    manifests = {name: read_json(data.MANIFESTS / f'{name}_archive_manifest.json')
                 for name in ('weather', 'firms', 'cams')
                 if (data.MANIFESTS / f'{name}_archive_manifest.json').exists()}
    records = [s for e in stations.values() for s in e.get('sensors', {}).values() if s.get('file')]
    records += [r for m in manifests.values() for r in m.get('files', {}).values()]
    size = sum(verify(record) for record in records)
    identity = {'selection_sha256': hashlib.sha256((data.MANIFESTS / 'station_selection.json').read_bytes()).hexdigest(),
                'sensors': sorted((k, p, s['sha256']) for k, e in stations.items()
                                  for p, s in e.get('sensors', {}).items() if s.get('file')),
                'weather': sorted((k, v['sha256']) for k, v in manifests.get('weather', {}).get('files', {}).items()),
                'firms': sorted((k, v['sha256']) for k, v in manifests.get('firms', {}).get('files', {}).items())}
    version = canonical_hash(identity)
    snapshot = {'data_version': version, 'protocol_sha256': protocol['_sha256'],
                'selection': selection, 'stations': stations, 'manifests': manifests, 'identity': identity}
    path = data.DERIVED / version / 'inputs.json'
    if not path.exists():
        write_json(path, snapshot)
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'data_version': version,
              'CAMS_ARCHIVE_STATUS': CAMS_ARCHIVE_STATUS,
              'protocol_version': protocol['protocol_version'], 'protocol_sha256': protocol['_sha256'],
              'openaq_complete': len(stations), 'openaq_selected': len(selection['stations']),
              'openaq_rows': sum(s.get('rows', 0) for e in stations.values() for s in e.get('sensors', {}).values()),
              'weather_points_complete': len(manifests.get('weather', {}).get('files', {})),
              'weather_points_expected': len({f"{round(s['latitude'], 1):+06.1f}_{round(s['longitude'], 1):+07.1f}" for s in selection['stations']}),
              'firms_windows_complete': len(manifests.get('firms', {}).get('files', {})),
              'firms_windows_expected': len(list(range(0, (date(2026,10,8)-date(2025,2,1)).days+1, 5))),
              'proxy_cams_files_preserved': len(manifests.get('cams', {}).get('files', {})),
              'proxy_cams_used_for_research': False, 'checksummed_files': len(records),
              'uncompressed_bytes_verified': size, 'checksum_audit': 'PASS',
              'snapshot': config.portable(path), 'no_api_requests': True}
    write_json(OUT / 'recovery_checkpoint.json', report)
    return snapshot, report


if __name__ == '__main__':
    _, report = capture()
    print(json.dumps(report, indent=2))
