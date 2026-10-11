"""Check that the 20:00 IST cutoff was actually served, and record the verdict.

Exit codes: 0 when issuance is healthy or the window is still open, 2 when an
alert condition exists. A missed cutoff is permanent, so this is meant to run
after every cutoff (locally, or from the scheduler once a channel is authorised).
Nothing is sent to anyone; see src/nationwide/alerts.py.
"""
import json
import sys

from src import config
from src.ingestion.settings import load_env
from src.nationwide.alerts import record
from src.nationwide.monitoring import scheduler_health
from src.nationwide.store import Store


def main():
    load_env()
    store = Store()
    health = scheduler_health(store)
    verdict = record(store, health)
    out = config.PROJECT_ROOT / 'results/release/issuance_heartbeat.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**verdict, 'schedules': health['schedules'],
                               'protocol_version': health['protocol_version']}, indent=1, default=str),
                   encoding='utf-8')
    print(json.dumps({'state': verdict['issuance']['state'], 'forecasts': verdict['forecasts'],
                      'status': verdict['status'], 'artefact': config.portable(out)}, default=str))
    return 2 if verdict['alert'] else 0


if __name__ == '__main__':
    sys.exit(main())
