"""Static per-site features that need no licensed dataset.

WP1 asks for elevation, coastal distance, urban fraction, population density and
the CAMS cell id. Two of those are obtainable here and three are not, so this
module computes what it can and states what it cannot:

- CAMS cell id is arithmetic on the provider's 0.4 degree grid, and it matters
  because several stations inside one cell receive an identical modelled input;
  that is the resolution limitation (L14) made explicit per station.
- Elevation comes from the Open-Meteo elevation endpoint, which is free and
  needs no credential.
- Coastal distance needs a coastline geometry, and urban fraction and population
  density need a licensed gridded product. Those stay PENDING with the reason
  attached rather than being approximated into a number someone might cite.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

CAMS_RESOLUTION = 0.4
ELEVATION_URL = 'https://api.open-meteo.com/v1/elevation'
ELEVATION_BATCH = 100
PENDING = {
    'coastal_distance_km': 'PENDING — needs a coastline geometry (for example Natural Earth or OSM '
                           'coastlines) with its licence recorded.',
    'urban_fraction': 'PENDING — needs a licensed gridded urban product (GHS-SMOD or similar).',
    'population_density': 'PENDING — needs a licensed gridded population product (WorldPop or GHS-POP) '
                          'with vintage and reuse terms; see HUMAN_ACTIONS.md.',
}


def cams_cell(latitude, longitude, resolution=CAMS_RESOLUTION):
    """Identify the provider grid cell a coordinate falls in, and its centre.

    The grid was measured, not assumed: scanning the provider across a cell
    boundary showed the value changing at 13.0 and 13.4 degrees north and at
    79.8, 80.2 and 80.6 degrees east. Cells are therefore centred on multiples
    of the resolution and a coordinate belongs to its nearest grid point. An
    earlier version floored instead of rounding, which shifted every cell by
    half its width and put Avadi and central Chennai in one cell; they are in
    adjacent cells, split at 80.2 degrees east.

    Stations sharing a cell share one modelled input, which is why the id is
    stored: it makes an apparently per-station modelled value traceable to the
    ~45 km cell it actually came from.
    """
    if latitude is None or longitude is None:
        return None
    latitude, longitude = float(latitude), float(longitude)
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 360):
        return None
    signed = longitude - 360 if longitude > 180 else longitude
    # floor(x + 0.5) rather than round(): Python rounds exact halves to even.
    row = int(math.floor(latitude / resolution + 0.5))
    column = int(math.floor(signed / resolution + 0.5))
    return {
        'cell_id': f'{resolution:g}deg-{row:+04d}-{column:+05d}',
        'row': row, 'column': column, 'resolution_degrees': resolution,
        'centre_latitude': round(row * resolution, 4),
        'centre_longitude': round(column * resolution, 4),
    }


def elevations(coordinates, fetch):
    """Metres above sea level for each coordinate, or None where unavailable.

    `fetch(url, params)` is injected so this stays testable and so the caller
    keeps its own request budget and event logging.
    """
    out = [None] * len(coordinates)
    for offset in range(0, len(coordinates), ELEVATION_BATCH):
        chunk = coordinates[offset:offset + ELEVATION_BATCH]
        payload = fetch(ELEVATION_URL, {
            'latitude': ','.join(f'{lat:.5f}' for lat, _lon in chunk),
            'longitude': ','.join(f'{lon:.5f}' for _lat, lon in chunk),
        }) or {}
        values = payload.get('elevation')
        if not isinstance(values, list) or len(values) != len(chunk):
            continue
        for index, value in enumerate(values):
            out[offset + index] = None if value is None else float(value)
    return out


def site_features(stations, fetch=None):
    """Build the static feature table for a list of station rows."""
    coordinates = [(float(s['latitude']), float(s['longitude'])) for s in stations
                   if s.get('latitude') is not None and s.get('longitude') is not None]
    heights = elevations(coordinates, fetch) if (fetch and coordinates) else [None] * len(coordinates)
    heights_by_coordinate = dict(zip(coordinates, heights))

    sites, cells = [], {}
    for station in stations:
        latitude, longitude = station.get('latitude'), station.get('longitude')
        cell = cams_cell(latitude, longitude)
        key = (float(latitude), float(longitude)) if latitude is not None and longitude is not None else None
        site = {
            'station_pk': station.get('station_pk'), 'name': station.get('name'),
            'source_station_id': station.get('source_station_id'),
            'latitude': latitude, 'longitude': longitude,
            'cams_cell': cell, 'elevation_m': heights_by_coordinate.get(key),
            **PENDING,
        }
        sites.append(site)
        if cell:
            cells.setdefault(cell['cell_id'], []).append(station.get('station_pk'))

    shared = {cell: members for cell, members in cells.items() if len(members) > 1}
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'resolution_degrees': CAMS_RESOLUTION,
        'stations': len(sites),
        'with_elevation': sum(1 for s in sites if s['elevation_m'] is not None),
        'distinct_cams_cells': len(cells),
        'cells_with_multiple_stations': shared,
        'stations_sharing_a_cell': sum(len(members) for members in shared.values()),
        'pending_features': PENDING,
        'sites': sites,
        'notice': 'Stations inside one CAMS cell receive an identical modelled input. A per-station '
                  'modelled value is therefore a cell value, not a site measurement.',
    }
