"""Hourly worker, usable by Windows Task Scheduler or any external scheduler.

Each provider has its own DB connection and runs concurrently. A PostgreSQL
session advisory lock prevents overlapping scheduled cycles. Failed providers
are recorded and leave the others running. Exit 1 means at least one failed.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging.handlers import RotatingFileHandler

from src import config
from src.ingestion.db import PostgresStore
from src.ingestion.run import ORDER, _RedactingFilter, install_log_redaction, run_source
from src.ingestion.settings import Settings, load_env, redact

LOCK_NAME = 'airguard:scheduled-ingestion:v1'


def ingest_cycle(settings=None):
    load_env()
    install_log_redaction()
    settings = settings or Settings(http_timeout_seconds=12, http_max_retries=1)
    coordinator = PostgresStore()
    try:
        if not coordinator.query('select pg_try_advisory_lock(hashtext(%s))', (LOCK_NAME,))[0][0]:
            return {'ok': True, 'skipped': True, 'reason': 'Another scheduled cycle is running', 'runs': []}

        def worker(name):
            store = PostgresStore()
            try:
                result, _ = run_source(name, store=store, dry_run=False, settings=settings)
                return result.to_public_dict()
            finally:
                store.close()

        results = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(worker, name): name for name in ORDER}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {'source': name, 'status': 'FAILED', 'error': redact(exc)}
                results.append(result)
                logging.getLogger(__name__).info('%s', redact(json.dumps(result)))
        return {'ok': all(r['status'] == 'SUCCESS' for r in results), 'skipped': False, 'runs': results}
    finally:
        # Session locks are released on disconnect, including after an interrupted cycle.
        coordinator.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-file', default=str(config.PROJECT_ROOT / 'results/ingestion.log'))
    args = parser.parse_args()
    load_env()
    handler = RotatingFileHandler(args.log_file, maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    handler.addFilter(_RedactingFilter())
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    install_log_redaction()
    try:
        result = ingest_cycle()
    except Exception as exc:
        logging.getLogger(__name__).error('Scheduled ingestion failed: %s', redact(exc))
        return 1
    print(redact(json.dumps(result)))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
