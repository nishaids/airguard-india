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


def verify_sensor_metadata(stations, catalogue_sha256):
    identities=[]
    for key, entry in stations.items():
        recovery=entry.get('metadata_recovery')
        if not recovery:
            continue
        if recovery.get('catalogue_sha256')!=catalogue_sha256 or recovery.get('source')!='OpenAQ v3 /sensors/{sensor_id}':
            raise ValueError('Recovered sensor metadata provenance differs')
        for record in recovery['individual_responses']:
            path=(config.PROJECT_ROOT/record['file']).resolve()
            if not path.is_relative_to(data.ROOT.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
                raise ValueError('Recovered sensor metadata file checksum differs')
            response=read_json(path)
            if response['request_path']!=f"/sensors/{record['sensor_id']}" or response['payload_sha256']!=record['payload_sha256'] or canonical_hash(response['payload'])!=record['payload_sha256']:
                raise ValueError('Recovered sensor metadata payload checksum differs')
            identities.append((key,record['sensor_id'],record['payload_sha256']))
    return sorted(identities)


def capture(snapshot_path=None):
    protocol = load()
    inherited = None
    if snapshot_path is not None:
        source = Path(snapshot_path).resolve()
        if not source.is_relative_to(data.DERIVED.resolve()) or source.name!='inputs.json':
            raise ValueError('Frozen inputs must be a versioned research snapshot')
        inherited = read_json(source)
        if inherited['protocol_sha256']!=protocol['_sha256']:
            raise ValueError('Frozen input protocol differs')
        if inherited['data_version']!=canonical_hash(inherited['identity']) or source.parent.name!=inherited['data_version']:
            raise ValueError('Frozen input identity differs')
        if inherited['identity']['selection_semantic_sha256']!=canonical_hash(inherited['selection']):
            raise ValueError('Frozen selection identity differs')
        expected = sorted((k,p,s['sha256']) for k,e in inherited['stations'].items()
                          for p,s in e.get('sensors',{}).items() if s.get('file'))
        if expected!=[tuple(item) for item in inherited['identity']['sensors']]:
            raise ValueError('Frozen sensor identity differs')
        for kind in ('weather','firms'):
            expected=sorted((k,r['sha256']) for k,r in inherited['manifests'].get(kind,{}).get('files',{}).items())
            if expected!=[tuple(item) for item in inherited['identity'][kind]]:
                raise ValueError('Frozen supporting manifest identity differs')
    selection = copy.deepcopy(inherited['selection']) if inherited else read_json(data.MANIFESTS / 'station_selection.json')
    from src.research.calibration import metadata
    metadata_correction = read_json(metadata.PATH) if metadata.PATH.exists() else None
    if metadata_correction:
        if selection.get('metadata_revision'):
            if selection['metadata_revision']['sha256']!=metadata_correction['sha256']:
                raise ValueError('Frozen metadata correction differs')
        else:
            selection = metadata.apply(selection, metadata_correction)
    stations = copy.deepcopy(inherited['stations']) if inherited else {}
    paths = [data.MANIFESTS / 'openaq_hours_manifest.json',
             *sorted(data.MANIFESTS.glob('openaq_hours_manifest.shard*.json'))]
    for path in ([] if inherited else paths):
        if path.exists():
            for key, entry in read_json(path).get('stations', {}).items():
                if entry.get('complete'):
                    stations[key] = entry
    repairs_path = data.MANIFESTS / 'openaq_repairs.json'
    repairs = read_json(repairs_path) if repairs_path.exists() else {}
    # A deliberately frozen earlier cohort is usable only if every known
    # page-cap concern in that cohort has a verified terminal repair record.
    if inherited:
        for key, entry in stations.items():
            for pollutant, sensor in entry.get('sensors',{}).items():
                if any(r.get('warning')=='page_limit_reached' for r in sensor.get('requests',[])):
                    if repairs.get('stations',{}).get(key,{}).get(pollutant,{}).get('status') not in ('repaired','no_missing_rows'):
                        raise ValueError('Frozen cohort contains unresolved pagination')
    stations, repair_originals, repairs_applied = apply_repairs(stations, repairs)
    manifests = copy.deepcopy(inherited['manifests']) if inherited else {name: read_json(data.MANIFESTS / f'{name}_archive_manifest.json')
                 for name in ('weather', 'firms', 'cams')
                 if (data.MANIFESTS / f'{name}_archive_manifest.json').exists()}
    records = [s for e in stations.values() for s in e.get('sensors', {}).values() if s.get('file')]
    records += [r for m in manifests.values() for r in m.get('files', {}).values()]
    size = sum(verify(record) for record in records + repair_originals)
    metadata_identities=verify_sensor_metadata(stations,selection['catalogue']['sha256'])
    identity = {'selection_semantic_sha256': canonical_hash(selection),
                'sensors': sorted((k, p, s['sha256']) for k, e in stations.items()
                                  for p, s in e.get('sensors', {}).items() if s.get('file')),
                'weather': sorted((k, v['sha256']) for k, v in manifests.get('weather', {}).get('files', {}).items()),
                'firms': sorted((k, v['sha256']) for k, v in manifests.get('firms', {}).get('files', {}).items()),
                'recovered_sensor_metadata':metadata_identities}
    version = canonical_hash(identity)
    snapshot = {'data_version': version, 'protocol_sha256': protocol['_sha256'],
                'selection': selection, 'stations': stations, 'manifests': manifests, 'identity': identity,
                'repairs_applied': repairs_applied,
                'metadata_correction': metadata_correction,
                'selection_file_sha256':hashlib.sha256((data.MANIFESTS/'station_selection.json').read_bytes()).hexdigest()}
    if inherited:
        snapshot['inherited_snapshot_data_version']=inherited['data_version']
        snapshot['cohort_basis']='Earlier acquisition snapshot with verified pagination; no outcome-dependent resampling'
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
              'recovered_sensor_metadata_files_verified':len(metadata_identities),
              'uncompressed_bytes_verified': size, 'checksum_audit': 'PASS',
              'repairs_applied': repairs_applied,'original_repair_bases_verified':len(repair_originals),
              'metadata_revision': selection.get('metadata_revision'),
              'snapshot': config.portable(path), 'no_api_requests': True}
    if inherited:
        report['inherited_snapshot_data_version']=inherited['data_version']
        report['cohort_basis']=snapshot['cohort_basis']
        write_json(data.DERIVED/version/'frozen_checkpoint_report.json',report)
    else:
        write_json(OUT / 'recovery_checkpoint.json', report)
    return snapshot, report


if __name__ == '__main__':
    _, report = capture()
    print(json.dumps(report, indent=2))
