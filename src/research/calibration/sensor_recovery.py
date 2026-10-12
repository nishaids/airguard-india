"""Recover official sensor metadata when location/sensors returns server errors.

Sensor IDs come from the exact locked provider catalogue. Individual sensor
responses supply real dates/coverage/units; location dates are never substituted.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from src import config
from src.research.calibration import catalogue
from src.research.calibration.checkpoint import canonical_hash, write_json
from src.nationwide.aqi import normalize


def fetch(client,station,*,selection=None,cache_dir=None):
    from src.research.calibration.openaq_archive import POLLUTANTS
    selection=selection or json.loads(catalogue.SELECTION.read_text(encoding='utf-8'))
    source=config.PROJECT_ROOT/selection['catalogue']['path']
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=selection['catalogue']['sha256']:
        raise ValueError('Locked location catalogue checksum differs')
    matches=[s for s in json.loads(raw)['results'] if s['id']==station['location_id']]
    if len(matches)!=1 or matches[0]['name']!=station['name'] or matches[0]['provider']['name']!='CPCB':
        raise ValueError('Sensor recovery location identity differs')
    location=matches[0]
    if any(location['coordinates'][k]!=station[k] for k in ('latitude','longitude')):
        raise ValueError('Sensor recovery coordinates differ')
    root=Path(cache_dir or config.PROJECT_ROOT/'data/research/catalogue/sensors/recovery_v1')
    results,records=[],[]
    for sensor in location.get('sensors',[]):
        parameter=sensor['parameter']; pollutant=POLLUTANTS.get(parameter['name'])
        if pollutant is None or normalize(pollutant,1,parameter['units']) is None:
            continue
        key=sensor['id']; endpoint=f'/sensors/{key}'; path=root/f'{key}.json'
        if path.exists():
            record=json.loads(path.read_text(encoding='utf-8'))
            if record['request_path']!=endpoint or record['payload_sha256']!=canonical_hash(record['payload']):
                raise ValueError('Individual sensor metadata checksum differs')
        else:
            payload=client.get(endpoint,attempts=2)
            record={'request_path':endpoint,'retrieved_at':datetime.now(timezone.utc).isoformat(),
                'payload':payload,'payload_sha256':canonical_hash(payload)}
            write_json(path,record)
        returned=record['payload'].get('results',[])
        if len(returned)!=1 or returned[0]['id']!=key or returned[0]['parameter']['name']!=parameter['name']:
            raise ValueError('Individual sensor response identity differs')
        # No ranking by ID: choose_sensors will use actual returned dates/counts.
        results.append(returned[0])
        records.append({'sensor_id':key,'file':config.portable(path),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'payload_sha256':record['payload_sha256'],
            'retrieved_at':record['retrieved_at'],'request_path':endpoint})
    if not results:
        raise ValueError('No supported sensor metadata in the locked catalogue')
    return {'results':results,'_provenance':{'source':'OpenAQ v3 /sensors/{sensor_id}',
        'reason':'location sensor metadata endpoint server error',
        'station_sensor_association':'exact locked location catalogue',
        'catalogue_sha256':selection['catalogue']['sha256'],'individual_responses':records}}
