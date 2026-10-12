"""Versioned metadata corrections with frozen acquisition/sample membership.

No pollutant, target, prediction or model result is read by this module.
Original selection and download manifests remain byte-for-byte unchanged.
"""
import copy
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from src import config
from src.research.calibration import catalogue

FIELDS = ('site','city','agency','state','region')
PATH = config.PROJECT_ROOT/'results/research/data_manifests/station_metadata_corrections.v2.json'


def apply(selection, correction):
    from src.research.calibration.checkpoint import canonical_hash
    if correction.get('base_selection_sha256') != canonical_hash(selection):
        raise ValueError('Metadata correction does not match the frozen selection')
    if correction.get('sha256') != canonical_hash({k:v for k,v in correction.items() if k!='sha256'}):
        raise ValueError('Metadata correction checksum differs')
    if correction.get('catalogue_sha256') != selection['catalogue']['sha256']:
        raise ValueError('Metadata correction catalogue identity differs')
    output=copy.deepcopy(selection)
    by_id={s['location_id']:s for s in output['stations']}
    seen=set()
    for entry in correction['corrections']:
        key=entry['location_id']
        if key in seen or key not in by_id:
            raise ValueError('Metadata correction changes sample membership')
        seen.add(key)
        station=by_id[key]
        if {k:station.get(k) for k in FIELDS} != entry['before']:
            raise ValueError('Metadata correction base attributes differ')
        if set(entry['after']) != set(FIELDS):
            raise ValueError('Metadata correction changes nonmetadata attributes')
        if entry['source_name'] != station['name']:
            raise ValueError('Metadata correction station identity differs')
        station.update(entry['after'])
    output['universe']=correction['corrected_universe']
    output['selected']['cities']=len({s['city'] for s in output['stations']})
    output['selected']['by_region']=dict(Counter(s['region'] for s in output['stations']))
    output['selected']['by_state']=dict(Counter(s['state'] or 'unresolved' for s in output['stations']))
    output['metadata_revision']={'version':correction['version'],'sha256':correction['sha256'],
        'membership_and_strata':'frozen original sample; never resampled after correction'}
    assert [s['location_id'] for s in output['stations']]==[s['location_id'] for s in selection['stations']]
    return output


def create():
    from src.research.calibration.checkpoint import canonical_hash, write_json
    if PATH.exists():
        value=json.loads(PATH.read_text(encoding='utf-8'))
        apply(json.loads(catalogue.SELECTION.read_text(encoding='utf-8')),value)
        return value
    selection=json.loads(catalogue.SELECTION.read_text(encoding='utf-8'))
    raw=catalogue.CATALOGUE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=selection['catalogue']['sha256']:
        raise ValueError('Original provider catalogue checksum differs')
    locations=json.loads(raw)['results']
    descriptions={s['id']:catalogue.describe(s) for s in locations if catalogue.eligible(s)}
    corrections=[]
    for station in selection['stations']:
        after={k:descriptions[station['location_id']].get(k) for k in FIELDS}
        before={k:station.get(k) for k in FIELDS}
        if before!=after:
            corrections.append({'location_id':station['location_id'],'source_name':station['name'],
                'latitude':station['latitude'],'longitude':station['longitude'],'before':before,'after':after})
    cities=Counter(s['city'] for s in descriptions.values())
    previous=PATH.with_name('station_metadata_corrections.v1.json')
    value={'version':'station-metadata-v2','created_at':datetime.now(timezone.utc).isoformat(),
        'previous_metadata_sha256':json.loads(previous.read_text(encoding='utf-8'))['sha256'] if previous.exists() else None,
        'state_disambiguation_source':'https://gmc.assam.gov.in/',
        'base_selection_sha256':canonical_hash(selection),'catalogue_sha256':selection['catalogue']['sha256'],
        'basis':'Provider-name parsing only; no outcomes or model results determine a correction',
        'membership_changed':False,'strata_changed':False,'qc_or_protocol_changed':False,
        'corrected_universe':{'eligible_stations':len(descriptions),'eligible_cities':len(cities),
            'stations_per_city':{str(k):v for k,v in sorted(Counter(cities.values()).items())}},'corrections':corrections}
    value['sha256']=canonical_hash(value)
    apply(selection,value)
    write_json(PATH,value)
    return value


if __name__=='__main__':
    value=create()
    print(json.dumps({'version':value['version'],'corrected_ids':[e['location_id'] for e in value['corrections']],
        'sha256':value['sha256'],'membership_changed':False}))
