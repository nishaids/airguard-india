"""Connection lifecycle and asynchronous public/private trust boundary."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import uuid
import pytest

from src.nationwide.store import Store
from src.nationwide.service import Service
from src.nationwide.api import dispatch, cache_headers


def test_connection_reused_nested_scopes_and_closed_after_exception():
    connection = MagicMock(closed=False)
    with patch('src.nationwide.store.connect',return_value=connection) as connect:
        store=Store()
        try:
            with store.session():
                with store.cursor(): pass
                with store.session():
                    with store.cursor(): pass
                connection.close.assert_not_called()
                raise RuntimeError('test rollback')
        except RuntimeError: pass
        connect.assert_called_once()
        connection.close.assert_called_once()


def test_worker_threads_get_separate_connections_and_no_global_pool():
    connections=[]
    def connect():
        c=MagicMock(closed=False);connections.append(c);return c
    store=Store()
    def work(_):
        with store.session():
            with store.cursor(): pass
            with store.cursor(): pass
    with patch('src.nationwide.store.connect',side_effect=connect):
        with ThreadPoolExecutor(max_workers=3) as pool: list(pool.map(work,range(3)))
    assert len(connections)==3
    for c in connections: c.close.assert_called_once()


def test_uncached_public_request_queues_without_calling_providers():
    store=MagicMock();store.get.return_value=None;store.enqueue_summary.return_value='QUEUED'
    service=Service(store=store,providers=MagicMock())
    status,data=dispatch('summary',{'lat':'13.12','lon':'80.11'},service=service)
    assert status==202 and data['state']=='QUEUED' and 'current' not in data
    service.providers.air.assert_not_called()
    assert cache_headers('summary',status,data)=={'Cache-Control':'no-store'}


def test_failed_background_fetch_is_not_presented_as_live_data():
    store=MagicMock();store.get.return_value=None;store.enqueue_summary.return_value='FAILED'
    status,data=dispatch('current',{'lat':'13.12','lon':'80.11'},service=Service(store=store))
    assert status==503 and data['ok'] is False and 'current' not in data


def test_private_job_requires_bearer_authorization_and_valid_owned_token():
    service=MagicMock()
    job={'task':'summary','lat':'13.12','lon':'80.11','job_token':'a30a4814-4f97-4054-a2e5-2b8eb09560cb'}
    with patch('src.nationwide.api.secret',return_value='test-secret'):
        assert dispatch('refresh',job,service=service)[0]==401
        service.run_summary_job.assert_not_called()
        service.run_summary_job.return_value={'ok':True,'state':'COMPLETE'}
        assert dispatch('refresh',job,'Bearer test-secret',service=service)[0]==200
        assert dispatch('refresh',{**job,'job_token':'invalid'},'Bearer test-secret',service=service)[0]==400
        assert dispatch('status',{'view':'refresh'},'Bearer test-secret',service=service)[0]==400


def test_expired_queue_lease_never_fetches_provider_or_reissues_forecast():
    store=MagicMock();store.summary_job_owned.return_value=False
    service=Service(store=store,providers=MagicMock())
    assert service.run_summary_job(13.12,80.11,'expired')['state']=='EXPIRED_JOB'
    store.issue.assert_not_called();service.providers.air.assert_not_called()


def test_real_queue_collapses_duplicates_and_rolls_back_dispatch():
    from src.ingestion.settings import load_env,secret
    from src.ingestion.db import connect
    load_env()
    if not secret('DATABASE_URL'): pytest.skip('DATABASE_URL is not configured')
    connection=connect()
    try:
        with connection.cursor() as cur:
            key='summary:test-rollback:'+str(uuid.uuid4())
            cur.execute('select airguard.enqueue_summary(%s,13.12,80.11)',(key,))
            assert cur.fetchone()[0]=='QUEUED'
            cur.execute('select airguard.enqueue_summary(%s,13.12,80.11)',(key,))
            assert cur.fetchone()[0]=='IN_PROGRESS'
            cur.execute('select count(*) from airguard.cache_metadata where cache_key=%s',('queue:'+key,))
            assert cur.fetchone()[0]==1
            cur.execute("select has_function_privilege('anon','airguard.enqueue_summary(text,double precision,double precision)','execute')")
            assert cur.fetchone()[0] is False
            # pg_net sends only after commit. This test never commits a request.
    finally:
        connection.rollback();connection.close()
