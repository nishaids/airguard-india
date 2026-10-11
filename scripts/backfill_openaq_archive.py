"""Backfill reachable hourly history from the OpenAQ archive and report the ceiling.

    python -m scripts.backfill_openaq_archive --days 30 --stations 20

Writes `results/openaq_archive_backfill.json`. A thin result is a finding about
upstream coverage, not a failure to report: the summary records what was asked
for, what came back and why rows were rejected.
"""
import argparse
import json
import sys

from src import config
from src.ingestion.archive import FileSink, backfill
from src.ingestion.settings import load_env
from src.nationwide.providers import Providers
from src.nationwide.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=30, help='how far back to ask for (default 30)')
    parser.add_argument('--stations', type=int, default=None, help='cap the number of stations queried')
    parser.add_argument('--pollutants', type=int, default=None, help='cap sensors per station')
    parser.add_argument('--pace', type=float, default=1.0, help='seconds to wait before each request')
    parser.add_argument('--sink', choices=('database', 'files'), default='database',
                        help='where rows go; use files for bulk history, which stays out of the '
                             'production storage budget (default database)')
    args = parser.parse_args()
    load_env()
    store = Store()
    sink = FileSink(config.PROJECT_ROOT / 'data/archive') if args.sink == 'files' else None
    summary = backfill(store, Providers(store), days=args.days, station_limit=args.stations,
                       pollutant_limit=args.pollutants, pace=args.pace, sink=sink)
    out = config.PROJECT_ROOT / 'results/openaq_archive_backfill.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in (
        'status', 'requested_days', 'stations_considered', 'stations_with_usable_sensors',
        'requests', 'retrieved', 'stored', 'per_pollutant', 'earliest_valid_at', 'latest_valid_at',
        'rejected', 'errors', 'seconds', 'sink', 'sink_directory', 'windows_lost') if k in summary}, indent=1, default=str))
    print(f'artefact: {config.portable(out)}')
    return 0 if summary.get('status') in ('COMPLETE', 'STOPPED_REQUEST_BUDGET') else 1


if __name__ == '__main__':
    sys.exit(main())
