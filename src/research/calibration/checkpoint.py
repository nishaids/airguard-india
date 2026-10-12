"""Audit the inherited caches without API requests or production mutations."""
from __future__ import annotations
import gzip
import copy
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


def apply_repairs(stations, repairs):
    """Overlay versioned repairs only when their exact inherited base is proven."""
    stations = copy.deepcopy(stations)
    originals, applied = [], []
    for station, sensors in repairs.get('stations', {}).items():
        if station not in stations:
            continue
        for pollutant, entry in sensors.items():
            if entry.get('status') not in ('repaired', 'no_missing_rows'):
                continue
            base = stations[station]['sensors'][pollutant]
            if entry['base_record_sha256'] != canonical_hash(base):
                raise ValueError('Repair overlay does not match frozen inherited sensor')
            if entry['override_sha256'] != canonical_hash({k:v for k,v in entry.items() if k!='override_sha256'}):
                raise ValueError('Repair overlay metadata checksum mismatch')
            originals.append(base)
            if entry['status']=='repaired':
                replacement=entry['replacement']
                if replacement['sensor_id']!=base['sensor_id'] or replacement.get('base_sha256')!=base['sha256']:
                    raise ValueError('Repair overlay changes sensor identity')
                verify(replacement)
                stations[station]['sensors'][pollutant]=replacement
                applied.append({'station_id':station,'pollutant':pollutant,'added_rows':entry['added_rows']})
    return stations, originals, applied


def capture():
    protocol = load()
    selection = read_json(data.MANIFESTS / 'station_selection.json')
    from src.research.calibration import metadata
    metadata_correction = read_json(metadata.PATH) if metadata.PATH.exists() else None
    if metadata_correction:
        selection = metadata.apply(selection, metadata_correction)
    stations = {}
    paths = [data.MANIFESTS / 'openaq_hours_manifest.json',
             *sorted(data.MANIFESTS.glob('openaq_hours_manifest.shard*.json'))]
    for path in paths:
        if path.exists():
            for key, entry in read_json(path).get('stations', {}).items():
                if entry.get('complete'):
                    stations[key] = entry
    repairs_path = data.MANIFESTS / 'openaq_repairs.json'
    repairs = read_json(repairs_path) if repairs_path.exists() else {}
    stations, repair_originals, repairs_applied = apply_repairs(stations, repairs)
    manifests = {name: read_json(data.MANIFESTS / f'{name}_archive_manifest.json')
                 for name in ('weather', 'firms', 'cams')
                 if (data.MANIFESTS / f'{name}_archive_manifest.json').exists()}
    records = [s for e in stations.values() for s in e.get('sensors', {}).values() if s.get('file')]
    records += [r for m in manifests.values() for r in m.get('files', {}).values()]
    size = sum(verify(record) for record in records + repair_originals)
    identity = {'selection_semantic_sha256': canonical_hash(selection),
                'sensors': sorted((k, p, s['sha256']) for k, e in stations.items()
                                  for p, s in e.get('sensors', {}).items() if s.get('file')),
                'weather': sorted((k, v['sha256']) for k, v in manifests.get('weather', {}).get('files', {}).items()),
                'firms': sorted((k, v['sha256']) for k, v in manifests.get('firms', {}).get('files', {}).items())}
    version = canonical_hash(identity)
    snapshot = {'data_version': version, 'protocol_sha256': protocol['_sha256'],
                'selection': selection, 'stations': stations, 'manifests': manifests, 'identity': identity,
                'repairs_applied': repairs_applied,
                'metadata_correction': metadata_correction,
                'selection_file_sha256':hashlib.sha256((data.MANIFESTS/'station_selection.json').read_bytes()).hexdigest()}
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
              'repairs_applied': repairs_applied,'original_repair_bases_verified':len(repair_originals),
              'metadata_revision': selection.get('metadata_revision'),
              'snapshot': config.portable(path), 'no_api_requests': True}
    write_json(OUT / 'recovery_checkpoint.json', report)
    return snapshot, report


if __name__ == '__main__':
    _, report = capture()
    print(json.dumps(report, indent=2))
