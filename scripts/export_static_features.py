"""Build the static per-site feature table for registered stations.

Elevation comes from the Open-Meteo elevation endpoint, which needs no
credential. The CAMS cell id is arithmetic, and it is the interesting column:
it shows how many stations share one modelled input, which is the 45 km grid
limitation expressed per station rather than as a sentence on the methods page.

Coastal distance, urban fraction and population density stay PENDING with the
dataset each would need. Approximating them would produce numbers that look
like features and would end up in a model.

    python -m scripts.export_static_features
"""
import json
import sys
from datetime import datetime, timezone

from src import config
from src.features.static_site import site_features
from src.ingestion.archive import station_rows
from src.ingestion.settings import load_env
from src.nationwide.providers import Providers
from src.nationwide.store import Store


def main():
    load_env()
    store = Store()
    stations = station_rows(store)
    if not stations:
        print('No registered stations.')
        return 1
    providers = Providers(store)

    def fetch(url, params):
        try:
            return providers.get_json('open_meteo', url, params)
        except Exception as exc:  # noqa: BLE001 - elevation is optional, the table is not
            print(f'elevation lookup failed ({type(exc).__name__}); continuing without it')
            return None

    table = site_features(stations, fetch=fetch)
    table['generated_at'] = datetime.now(timezone.utc).isoformat()
    out = config.PROJECT_ROOT / 'results/static_features.json'
    out.write_text(json.dumps(table, indent=1, default=str), encoding='utf-8')
    print(json.dumps({
        'stations': table['stations'], 'with_elevation': table['with_elevation'],
        'distinct_cams_cells': table['distinct_cams_cells'],
        'stations_sharing_a_cell': table['stations_sharing_a_cell'],
        'pending_features': sorted(table['pending_features']),
    }, indent=1))
    print(f'artefact: {config.portable(out)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
