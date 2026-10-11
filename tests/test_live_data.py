"""Live data transport, expiry, storage idempotency and scheduled overlap checks."""
from datetime import timedelta
from unittest import mock

from src.ingestion import db, live, scheduled, validation
from src.ingestion.schemas import Freshness, IngestionRun, utc_now
from src.ingestion.settings import Settings, load_env
from tests.test_ingestion import NOW, SETTINGS, client, ok, CPCB_PAYLOAD, FAKE
from src.ingestion import run, cpcb


def test_future_timestamp_cannot_look_fresh():
    assert validation.classify_freshness(NOW + timedelta(hours=2), NOW, SETTINGS) == Freshness.UNAVAILABLE


def test_exception_tracebacks_are_redacted():
    import io
    import logging
    import os
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(run._RedactingFilter())
    logger = logging.Logger('redaction-test')
    logger.addHandler(handler)
    with mock.patch.dict(os.environ, FAKE):
        try:
            raise RuntimeError(FAKE['OPENAQ_API_KEY'])
        except RuntimeError:
            logger.exception('Provider failed')
    assert FAKE['OPENAQ_API_KEY'] not in stream.getvalue()
    assert '<OPENAQ_API_KEY>' in stream.getvalue()


def test_freshness_boundary_expiry():
    for minutes, expected in [(90, 'fresh'), (91, 'delayed'), (180, 'delayed'), (181, 'stale'), (1440, 'stale'), (1441, 'unavailable')]:
        assert validation.classify_freshness(NOW - timedelta(minutes=minutes), NOW, SETTINGS).value == expected


def test_database_conflicts_are_reported_as_duplicates():
    import os
    store = db.MemoryStore()
    with mock.patch.dict(os.environ, FAKE), mock.patch.object(run, 'utc_now', return_value=NOW), mock.patch.object(cpcb, 'utc_now', return_value=NOW):
        first, _ = run.run_source('cpcb', store, False, settings=SETTINGS, client=client(ok(CPCB_PAYLOAD))[0])
        second, _ = run.run_source('cpcb', store, False, settings=SETTINGS, client=client(ok(CPCB_PAYLOAD))[0])
    assert first.written == 1
    assert second.written == 0 and second.duplicates == 1


def test_scheduler_skips_overlapping_cycle():
    coordinator = mock.MagicMock()
    coordinator.query.return_value = [(False,)]
    with mock.patch.object(scheduled, 'PostgresStore', return_value=coordinator), mock.patch.object(scheduled, 'run_source') as worker:
        result = scheduled.ingest_cycle()
    assert result['skipped'] is True
    worker.assert_not_called()
    coordinator.close.assert_called_once()


def test_scheduler_continues_after_provider_failure():
    coordinator = mock.MagicMock()
    coordinator.query.return_value = [(True,)]
    def result(name, **kwargs):
        record = IngestionRun(name, NOW)
        from src.ingestion.schemas import RunStatus
        record.status = RunStatus.FAILED if name == 'cpcb' else RunStatus.SUCCESS
        return record, []
    with mock.patch.object(scheduled, 'PostgresStore', return_value=coordinator), mock.patch.object(scheduled, 'run_source', side_effect=result):
        outcome = scheduled.ingest_cycle()
    assert outcome['ok'] is False
    assert len(outcome['runs']) == 4
    assert sum(r['status'] == 'SUCCESS' for r in outcome['runs']) == 3


def test_api_errors_hide_connection_details_and_validate_city():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('live_api_test', Path(__file__).resolve().parents[1] / 'webapp/api/live.py')
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    assert api.handle({'city': 'not-a-city'})[0] == 400
    with mock.patch.object(api, 'snapshot', side_effect=RuntimeError('private connection detail')):
        status, body = api.handle({})
    assert status == 503
    assert 'private' not in str(body)


def test_real_supabase_snapshot_and_expiry():
    import pytest
    from src.ingestion.settings import secret
    load_env()
    if not secret('DATABASE_URL'):
        pytest.skip('DATABASE_URL not configured')
    now = utc_now()
    current = live.snapshot(now=now)
    assert current['ok'] and len(current['sources']) == 4
    assert all(row['source_id'] == 'OpenAQ' for row in current['measurements'] if row['source_id'] != 'CPCB/data.gov.in')
    expired = live.snapshot(now=now + timedelta(days=10))
    assert not any(row['usable_now'] for row in expired['measurements'])
    assert expired['weather'] == []
    assert expired['fires']['count_last_24h'] == 0
    delhi = live.snapshot('Delhi')
    assert all(row['location_label'] == 'Delhi' for row in delhi['weather'])


def test_real_db_all_record_types_repeat_without_duplicate_flags():
    import pytest
    from src.ingestion.settings import secret
    load_env()
    if not secret('DATABASE_URL'):
        pytest.skip('DATABASE_URL not configured')
    # Replay validated provider samples already in the DB into a rollback-only
    # transaction. No synthetic samples or test ingestion logs are committed.
    connection = db.connect()
    try:
        with connection.cursor() as cursor:
            for table, id_column in [('air_quality_observations', 'observation_id'), ('weather_forecasts', 'forecast_id'), ('fire_detections', 'detection_id')]:
                cursor.execute(f'select count(*) from airguard.{table}')
                before = cursor.fetchone()[0]
                cursor.execute(f'insert into airguard.{table} select * from airguard.{table} order by {id_column} desc limit 5 on conflict do nothing')
                assert cursor.rowcount == 0
                cursor.execute(f'select count(*) from airguard.{table}')
                assert cursor.fetchone()[0] == before
    finally:
        connection.rollback()
        connection.close()
