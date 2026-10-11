"""Save a credential-free acceptance snapshot of the real stored live feed."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.db import PostgresStore, migrate
from src.ingestion.live import snapshot
from src.ingestion.settings import SECRET_NAMES, load_env, secret, secret_status, redact


def main():
    load_env()
    applied = migrate()
    feed = snapshot()
    store = PostgresStore()
    try:
        storage = {}
        for table, key in [
            ('air_quality_observations', 'source_id, source_station_id, pollutant, averaging_period, observed_at'),
            ('weather_forecasts', 'source_id, model, latitude, longitude, valid_at, vintage_at'),
            ('fire_detections', 'source_id, source_record_id'),
        ]:
            storage[table] = {
                'duplicate_groups': store.query(f'select count(*) from (select {key} from airguard.{table} group by {key} having count(*)>1) d')[0][0],
                'rows_with_provenance': store.query(f"select count(*) from airguard.{table} where provenance <> '{{}}'::jsonb")[0][0],
            }
        report = {'generated_at': feed['generated_at'], 'secret_configuration': secret_status(),
                  'new_migrations_applied': applied, 'table_counts': store.counts(),
                  'storage_checks': storage, 'live_snapshot': feed}
    finally:
        store.close()
    body = json.dumps(report, indent=2, ensure_ascii=False)
    for name in SECRET_NAMES:
        value = secret(name)
        if value and value in body:
            raise RuntimeError('Credential detected in report; refusing to save')
    output = ROOT / 'results/live_integration_acceptance.json'
    output.write_text(body + '\n', encoding='utf-8')
    print('Saved results/live_integration_acceptance.json')
    print(json.dumps({'table_counts':report['table_counts'], 'storage_checks':storage,
        'sources': [{k:s[k] for k in ('source_id','last_run_status','stored','usable_measurements_now','written','duplicates')} for s in feed['sources']]},indent=2))


if __name__ == '__main__':
    main()
