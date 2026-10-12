"""The station universe and the rule that picks the study sample from it.

The sample is chosen from catalogue facts alone - provider, declared sensors,
last-seen date, station count per city - before any pollutant value is read, so
no station can be in or out of the study because of how well it forecasts.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from src import config

CATALOGUE = config.PROJECT_ROOT / 'data/research/catalogue/openaq_locations_IN.json'
SELECTION = config.PROJECT_ROOT / 'results/research/data_manifests/station_selection.json'

REQUIRED = ('pm25', 'pm10', 'o3')
ACTIVE_SINCE = '2026-09-01'
NAME = re.compile(r'^(?P<site>.*),\s*(?P<city>[^,]+?)\s*-\s*(?P<agency>[A-Za-z ]+)$')

# Monitoring agency to state. Agencies that operate in several states (CPCB,
# IITM, IMD) and industrial operators are resolved by city or by coordinates.
AGENCY_STATE = {
    'MPCB': 'Maharashtra', 'BMC': 'Maharashtra', 'UPPCB': 'Uttar Pradesh', 'RSPCB': 'Rajasthan',
    'KSPCB': 'Karnataka', 'BSPCB': 'Bihar', 'HSPCB': 'Haryana', 'DPCC': 'Delhi',
    'WBPCB': 'West Bengal', 'OSPCB': 'Odisha', 'MPPCB': 'Madhya Pradesh', 'IMC': 'Madhya Pradesh',
    'TSPCB': 'Telangana', 'CECB': 'Chhattisgarh', 'APPCB': 'Andhra Pradesh', 'TNPCB': 'Tamil Nadu',
    'PCBA': 'Assam', 'PPCB': 'Punjab', 'Kerala PCB': 'Kerala', 'GPCB': 'Gujarat',
    'CPCC': 'Chandigarh', 'UKPCB': 'Uttarakhand', 'Meghalaya PCB': 'Meghalaya',
    'NPCB': 'Nagaland', 'Mizoram PCB': 'Mizoram', 'PPCC': 'Puducherry', 'JKSPCB': 'Jammu and Kashmir',
    'APSPCB': 'Arunachal Pradesh', 'APCB': 'Arunachal Pradesh', 'HPPCB': 'Himachal Pradesh',
    'Tripura SPCB': 'Tripura', 'SSPCB': 'Sikkim', 'JSPCB': 'Jharkhand', 'JMC': 'Jharkhand',
    'Bhilai Steel Plant': 'Chhattisgarh',
}
CITY_STATE = {
    'Delhi': 'Delhi', 'New Delhi': 'Delhi', 'Mumbai': 'Maharashtra', 'Navi Mumbai': 'Maharashtra',
    'Pune': 'Maharashtra', 'Ahmedabad': 'Gujarat', 'Chennai': 'Tamil Nadu', 'Kolkata': 'West Bengal',
    'Bengaluru': 'Karnataka', 'Hyderabad': 'Telangana', 'Lucknow': 'Uttar Pradesh',
    'Noida': 'Uttar Pradesh', 'Gurugram': 'Haryana', 'Faridabad': 'Haryana', 'Jaipur': 'Rajasthan',
    'Patna': 'Bihar', 'Chandigarh': 'Chandigarh', 'Bhopal': 'Madhya Pradesh',
}
STATE_REGION = {
    'Delhi': 'North', 'Haryana': 'North', 'Punjab': 'North', 'Chandigarh': 'North',
    'Uttar Pradesh': 'North', 'Uttarakhand': 'North', 'Himachal Pradesh': 'North',
    'Jammu and Kashmir': 'North', 'Rajasthan': 'North', 'Bihar': 'East', 'Jharkhand': 'East',
    'West Bengal': 'East', 'Odisha': 'East', 'Chhattisgarh': 'Central', 'Madhya Pradesh': 'Central',
    'Maharashtra': 'West', 'Gujarat': 'West', 'Karnataka': 'South', 'Telangana': 'South',
    'Andhra Pradesh': 'South', 'Tamil Nadu': 'South', 'Kerala': 'South', 'Puducherry': 'South',
    'Assam': 'Northeast', 'Meghalaya': 'Northeast', 'Nagaland': 'Northeast', 'Mizoram': 'Northeast',
    'Arunachal Pradesh': 'Northeast', 'Tripura': 'Northeast', 'Sikkim': 'Northeast',
}


def region_from_coordinates(latitude, longitude):
    """Coarse fallback for stations whose operator does not identify a state."""
    if longitude >= 89.5:
        return 'Northeast'
    if latitude < 19.5 and longitude >= 74.0:
        return 'South'
    if latitude >= 24.5:
        return 'North' if longitude < 83.5 else 'East'
    if longitude < 76.5:
        return 'West'
    if longitude >= 83.0:
        return 'East'
    return 'Central'


def parse_name(name):
    match = NAME.match(name or '')
    if match:
        site, city, agency = (match.group(k).strip() for k in ('site','city','agency'))
        # Some provider names explicitly append a state after the city.
        # Treating that state token as a city separates Noida stations incorrectly.
        if city in ('UP','Uttar Pradesh') and ',' in site:
            site, city = (part.strip() for part in site.rsplit(',',1))
        return site, city, agency
    body, separator, agency = (name or '').rpartition(' - ')
    if separator and agency in AGENCY_STATE and ' - ' in body:
        site, city = body.rsplit(' - ',1)
        return site.strip(), city.strip(), agency.strip()
    if body == 'Haldia' and agency == 'WBSPCB':
        return body, body, agency
    return None, None, None


def mass_sensor(location, parameter):
    """True when the location lists this pollutant in a mass-concentration unit."""
    for sensor in location.get('sensors') or []:
        info = sensor.get('parameter') or {}
        if info.get('name') == parameter and 'g/m' in (info.get('units') or ''):
            return True
    return False


def eligible(location):
    last = ((location.get('datetimeLast') or {}).get('utc') or '')
    return ((location.get('provider') or {}).get('name') == 'CPCB'
            and last >= ACTIVE_SINCE
            and all(mass_sensor(location, parameter) for parameter in REQUIRED)
            and (location.get('coordinates') or {}).get('latitude') is not None)


def describe(location):
    site, city, agency = parse_name(location.get('name'))
    coordinates = location['coordinates']
    state = AGENCY_STATE.get(agency) or CITY_STATE.get(city)
    region = STATE_REGION.get(state) or region_from_coordinates(coordinates['latitude'], coordinates['longitude'])
    return {
        'location_id': location['id'], 'name': location.get('name'), 'site': site,
        'city': city or (location.get('name') or f"location-{location['id']}"),
        'agency': agency, 'state': state, 'region': region,
        'latitude': coordinates['latitude'], 'longitude': coordinates['longitude'],
        'provider': (location.get('provider') or {}).get('name'),
        'owner': (location.get('owner') or {}).get('name'),
        'first_seen_utc': (location.get('datetimeFirst') or {}).get('utc'),
        'last_seen_utc': (location.get('datetimeLast') or {}).get('utc'),
    }


def select(locations, large_city_cap=3, mid_city_cap=2, single_city_stride=5):
    """Deterministic stratified sample.

    Cities with five or more eligible stations contribute `large_city_cap`,
    cities with two to four contribute `mid_city_cap`, and every
    `single_city_stride`-th single-station city (in alphabetical order)
    contributes its one station. Within a city, stations are taken in ascending
    OpenAQ location id. The point of the strata is to keep both things the
    spatial experiments need: many distinct cities, and several cities with
    more than one station so an unseen station in a seen city can be tested.
    """
    stations = [describe(location) for location in locations if eligible(location)]
    by_city = defaultdict(list)
    for station in stations:
        by_city[station['city']].append(station)
    for members in by_city.values():
        members.sort(key=lambda s: s['location_id'])

    chosen, singles = [], []
    for city in sorted(by_city):
        members = by_city[city]
        if len(members) >= 5:
            chosen += [dict(s, stratum='large_city') for s in members[:large_city_cap]]
        elif len(members) >= 2:
            chosen += [dict(s, stratum='mid_city') for s in members[:mid_city_cap]]
        else:
            singles.append(members[0])
    chosen += [dict(s, stratum='single_station_city') for s in singles[::single_city_stride]]
    chosen.sort(key=lambda s: s['location_id'])
    return {
        'rule': {'large_city_cap': large_city_cap, 'mid_city_cap': mid_city_cap,
                 'single_city_stride': single_city_stride, 'required_parameters': list(REQUIRED),
                 'provider': 'CPCB', 'active_since': ACTIVE_SINCE,
                 'order_within_city': 'ascending OpenAQ location id',
                 'basis': 'catalogue metadata only; no pollutant value was read before selection'},
        'universe': {'eligible_stations': len(stations), 'eligible_cities': len(by_city),
                     'stations_per_city': dict(sorted(Counter(len(m) for m in by_city.values()).items()))},
        'selected': {'stations': len(chosen), 'cities': len({s['city'] for s in chosen}),
                     'by_stratum': dict(Counter(s['stratum'] for s in chosen)),
                     'by_region': dict(Counter(s['region'] for s in chosen)),
                     'by_state': dict(Counter(s['state'] or 'unresolved' for s in chosen))},
        'stations': chosen,
    }


def build(catalogue_path=None, out_path=None):
    path = Path(catalogue_path or CATALOGUE)
    raw = path.read_bytes()
    payload = json.loads(raw.decode('utf-8'))
    selection = select(payload['results'])
    selection['catalogue'] = {
        'endpoint': payload.get('endpoint'), 'retrieved_at': payload.get('retrieved_at'),
        'locations': len(payload['results']), 'sha256': hashlib.sha256(raw).hexdigest(),
        'path': config.portable(path),
    }
    out = Path(out_path or SELECTION)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(selection, indent=1), encoding='utf-8')
    return selection


if __name__ == '__main__':
    result = build()
    print(json.dumps({k: result[k] for k in ('rule', 'universe', 'selected', 'catalogue')}, indent=1))
