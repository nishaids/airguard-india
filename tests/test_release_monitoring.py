from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import copy
from src.nationwide.api import cache_headers
from src.nationwide.monitoring import classify
from src.nationwide.service import Service
from src.nationwide.store import digest
from src.nationwide.aqi import IST, METHOD
from src.features.exposure import VERSION as EXPOSURE_VERSION
from tests.test_nationwide import FakeStore, NOW


def test_cache_never_crosses_ist_midnight_and_errors_not_shared():
    at=datetime(2026,10,11,18,29,50,tzinfo=timezone.utc)
    headers=cache_headers('summary',200,{},at)
    assert headers['Vercel-CDN-Cache-Control']=='public, s-maxage=9, stale-while-revalidate=0'
    assert cache_headers('summary',503,{},at)=={'Cache-Control':'no-store'}
    assert cache_headers('refresh',200,{},at)=={'Cache-Control':'no-store'}
    assert cache_headers('research',200,{},at)=={'Cache-Control':'no-store'}


def test_first_cutoff_not_due_is_not_scheduler_failure():
    now=datetime(2026,10,11,12,tzinfo=timezone.utc)
    registered=datetime(2026,10,10,17,tzinfo=timezone.utc)
    schedules=[{'jobname':'airguard-research-issue','active':True}]
    assert classify(now,registered,schedules,None,None)['state']=='AWAITING_FIRST_CUTOFF'
    late=now.replace(hour=14,minute=45)
    assert classify(late,registered,schedules,None,None)['state']=='MISSED_ISSUANCE'
    event={'created_at':late.replace(minute=32)}
    assert classify(late,registered,schedules,None,event)['state']=='ATTEMPTED_NO_ELIGIBLE_FORECASTS'
    assert classify(late,registered,schedules,late.replace(minute=31),event)['state']=='ISSUED'


def test_summary_hit_avoids_provider_work_and_retains_provenance():
    store=FakeStore();s=Service(store,object())
    hour=NOW.astimezone(IST).replace(minute=0,second=0,microsecond=0)
    key='summary:'+METHOD+':'+EXPOSURE_VERSION+':'+digest([13.11,80.11,hour.isoformat()])
    value={'ok':True,'location':{'name':'Original','region':'TN'},'tomorrow':{'date':'2026-10-11','forecast_run_id':7},'refreshed_at':NOW.isoformat(),'provenance':{'source':'CAMS'}}
    store.cache[key]={'payload':copy.deepcopy(value),'expires_at':NOW+timedelta(minutes=5),'fetched_at':NOW}
    with patch('src.nationwide.service.utcnow',return_value=NOW): result=s.summary(13.11,80.11,'Requested')
    assert result['response_cache']['status']=='HIT' and result['tomorrow']['forecast_run_id']==7
    assert result['location']['name']=='Requested' and store.cache[key]['payload']['location']['name']=='Original'
    assert result['provenance']==value['provenance']


def test_cached_wrong_target_date_rejected_before_issuance():
    store=FakeStore();s=Service(store,object())
    hour=NOW.astimezone(IST).replace(minute=0,second=0,microsecond=0)
    key='summary:'+METHOD+':'+EXPOSURE_VERSION+':'+digest([13.11,80.11,hour.isoformat()])
    store.cache[key]={'payload':{'tomorrow':{'date':'2020-07-01'}},'expires_at':NOW+timedelta(minutes=5)}
    with patch('src.nationwide.service.utcnow',return_value=NOW), patch.object(s,'_build_summary',return_value={'ok':False}) as build:
        assert s.summary(13.11,80.11)=={'ok':False}
        build.assert_called_once()


def test_cdn_does_not_keep_fresh_label_after_source_expiry():
    at=datetime(2026,10,11,12,0,tzinfo=timezone.utc)
    payload={'tomorrow':{'freshness':'FRESH','issued_at':(at-timedelta(minutes=59,seconds=50)).isoformat()}}
    assert cache_headers('forecast',200,payload,at)['Vercel-CDN-Cache-Control']=='public, s-maxage=9, stale-while-revalidate=0'
    payload['tomorrow']['issued_at']=(at-timedelta(hours=1)).isoformat()
    assert cache_headers('forecast',200,payload,at)=={'Cache-Control':'no-store'}
