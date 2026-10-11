"""Hourly bounded independent ingestion for optional official/fire sources."""
from concurrent.futures import ThreadPoolExecutor
from src.ingestion.db import PostgresStore
from src.ingestion.run import run_source, install_log_redaction
from src.ingestion.settings import Settings
from src.nationwide.providers import utcnow


def ingest_optional(service):
    install_log_redaction()
    def ingest(name):
        def collect():
            store = PostgresStore()
            try:
                run, _ = run_source(name, store=store, dry_run=False,
                                    limit=1000 if name == 'cpcb' else 5000,
                                    settings=Settings(http_timeout_seconds=12, http_max_retries=1))
                result = run.to_public_dict()
                service.store.event(run.source, 'scheduled_ingestion', result['status'],
                                    int((utcnow()-run.started_at).total_seconds()*1000), run.written,
                                    error_class='SourceUnavailable' if run.error else None,
                                    detail=run.error)
                return {'fetched_at': utcnow().isoformat(), 'run': result}
            finally:
                store.close()
        # A failed source is itself cached for this interval. Other providers
        # still run; retry storms cannot repeatedly hit an unavailable feed.
        data, status = service.cached('optional-ingestion-v1:'+name, 'optional_ingestion', collect, 3600)
        return data or {'source': name, 'status': status}
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(ingest, ('cpcb', 'firms')))
