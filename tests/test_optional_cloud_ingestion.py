from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from src.nationwide.optional_ingestion import ingest_optional


def test_failed_official_source_does_not_stop_fire_and_each_connection_closes():
    closed=[]; events=[]; fetched=[]
    class Store:
        def close(self):closed.append(True)
    class ServiceStore:
        def event(self, *args, **kwargs):events.append(args)
    class Service:
        store=ServiceStore()
        def cached(self, key, provider, collect, seconds):
            assert seconds==3600
            fetched.append(key)
            return collect(), {'status':'SUCCESS'}
    def run(name, **kwargs):
        result={'source':name,'status':'FAILED' if name=='cpcb' else 'SUCCESS'}
        return SimpleNamespace(source=name,started_at=datetime.now(timezone.utc),written=0,
                               error='network refused' if name=='cpcb' else None,
                               to_public_dict=lambda:result), []
    with patch('src.nationwide.optional_ingestion.PostgresStore',Store), patch('src.nationwide.optional_ingestion.run_source',run):
        results=ingest_optional(Service())
    assert [r['run']['status'] for r in results]==['FAILED','SUCCESS']
    assert len(closed)==2 and len(fetched)==2 and len(events)==2
