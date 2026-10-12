import copy
import json
import pytest
from src.research.calibration.catalogue import parse_name
from src.research.calibration.metadata import apply, FIELDS
from src.research.calibration.checkpoint import canonical_hash


@pytest.mark.parametrize('name,expected',[
    ('Sector - 62, Noida, UP - IMD',('Sector - 62','Noida','IMD')),
    ('Sector - 125, Noida, UP - UPPCB',('Sector - 125','Noida','UPPCB')),
    ('Sector-1, Noida - UPPCB',('Sector-1','Noida','UPPCB')),
    ('Tata Stadium - Jorapokhar - JSPCB',('Tata Stadium','Jorapokhar','JSPCB')),
    ('Haldia - WBSPCB',('Haldia','Haldia','WBSPCB')),
    ('Unknown format',(None,None,None)),
])
def test_provider_city_boundaries(name,expected):
    assert parse_name(name)==expected


def fixtures():
    station={'location_id':5616,'name':'Sector - 62, Noida, UP - IMD','site':'Sector - 62, Noida',
        'city':'UP','agency':'IMD','state':None,'region':'North','latitude':28.6,'longitude':77.3,'stratum':'mid_city'}
    selection={'catalogue':{'sha256':'catalogue'},'stations':[station],
        'universe':{'eligible_stations':1,'eligible_cities':1},'selected':{'stations':1,'cities':1}}
    before={k:station.get(k) for k in FIELDS}
    after={**before,'site':'Sector - 62','city':'Noida','state':'Uttar Pradesh'}
    correction={'version':'test-metadata-v1','base_selection_sha256':canonical_hash(selection),
        'catalogue_sha256':'catalogue','corrected_universe':selection['universe'],
        'corrections':[{'location_id':5616,'source_name':station['name'],'before':before,'after':after}]}
    correction['sha256']=canonical_hash(correction)
    return selection,correction


def test_metadata_overlay_is_versioned_and_preserves_membership():
    selection,correction=fixtures()
    original=copy.deepcopy(selection)
    corrected=apply(selection,json.loads(json.dumps(correction)))
    assert selection==original
    assert corrected['stations'][0]['city']=='Noida'
    assert corrected['stations'][0]['stratum']=='mid_city'
    assert corrected['stations'][0]['latitude']==28.6
    assert corrected['selected']['stations']==1
    assert corrected['metadata_revision']['sha256']==correction['sha256']


@pytest.mark.parametrize('change',[
    lambda c:c.update(base_selection_sha256='wrong'),
    lambda c:c.update(catalogue_sha256='wrong'),
    lambda c:c['corrections'][0].update(location_id=999),
    lambda c:c['corrections'][0]['before'].update(city='wrong'),
    lambda c:c['corrections'][0]['after'].update(latitude=50),
    lambda c:c['corrections'][0].update(source_name='wrong station'),
])
def test_metadata_overlay_refuses_unbound_changes(change):
    selection,correction=fixtures()
    change(correction)
    correction['sha256']=canonical_hash({k:v for k,v in correction.items() if k!='sha256'})
    with pytest.raises(ValueError):apply(selection,correction)
