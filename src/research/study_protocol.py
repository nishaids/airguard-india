"""Expanded preregistration; live collection v1 remains immutable and active."""
import copy
from src.research.protocol import PROTOCOL as COLLECTION_PROTOCOL
from src.nationwide.store import digest

STUDY=copy.deepcopy(COLLECTION_PROTOCOL)
STUDY.update(protocol_version='airguard-national-study-20ist-v2',
    status='PREREGISTERED_PENDING_MATCHED_DATA', collection_protocol_version=COLLECTION_PROTOCOL['protocol_version'],
    minimum_stations=100, archive_requirement='Genuine archived issue-time forecast initialization and availability; no reanalysis/past-fields substitute')
STUDY['eligibility'].update(minimum_training_days=365,minimum_test_days=90,minimum_stations_for_spatial_validation=100)
STUDY['splits'].update(training_days=365,final_test_days=90,final_test='Latest 90 global target dates locked before model selection; evaluate once, reproducible rerun only at same data/protocol/source hash')
STUDY['advisory']['underwarning_targets']['outdoor_workers']=.05
STUDY['hypotheses']={
    'H1':'Station correction lowers held-out MAE vs raw CAMS and persistence; paired date-blocked comparison, Holm correction.',
    'H2':'Raw CAMS O3/PM2.5 bias varies by region/season; directions are hypotheses, not precomputed findings.',
    'H3':'80/90% interval coverage within 3 percentage points across seasons/severity; joint pollutant support required for AQI bounds.',
    'H4':'Empirical under-warning at most 5% vulnerable/10% general; report over-warning, support and uncertainty.'}
STUDY['not_implemented_or_validated']=['EnbPI comparison','pollutant-level MOS/CQR training','region/coastal holdouts',
    'calibrated band probabilities','HAI v2 evidence coefficients','deweathered event causal design','clinical benefit']
STUDY_HASH=digest(STUDY)


def register(store):
    from src.research.storage import Json
    with store.cursor() as c:
        c.execute('insert into airguard.research_protocols(protocol_version,definition,definition_hash) values(%s,%s,%s) on conflict do nothing',
                  (STUDY['protocol_version'],Json(STUDY),STUDY_HASH))
        c.execute('select definition_hash from airguard.research_protocols where protocol_version=%s',(STUDY['protocol_version'],))
        if c.fetchone()['definition_hash']!=STUDY_HASH:raise ValueError('Registered study definition is immutable; create a new version')
