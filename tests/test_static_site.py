from src.features.static_site import CAMS_RESOLUTION, PENDING, cams_cell, elevations, site_features

CHENNAI = (13.0878, 80.2785)
AVADI = (13.1147, 80.1098)


def test_cells_are_centred_on_grid_points_and_contain_their_coordinate():
    cell = cams_cell(*CHENNAI)
    assert cell['resolution_degrees'] == CAMS_RESOLUTION
    assert abs(cell['centre_latitude'] - CHENNAI[0]) <= CAMS_RESOLUTION / 2 + 1e-9
    assert abs(cell['centre_longitude'] - CHENNAI[1]) <= CAMS_RESOLUTION / 2 + 1e-9
    # Centres are multiples of the resolution, as measured against the provider.
    assert cell['centre_latitude'] == 13.2 and cell['centre_longitude'] == 80.4


def test_measured_cell_boundaries_are_reproduced():
    # The provider's value changed between these pairs of coordinates and stayed
    # constant within them (scan recorded in docs/research/DATA_SOURCES_RESEARCH.md).
    same = [((13.02, 80.05), (13.38, 80.05)), ((13.25, 79.82), (13.25, 80.18))]
    different = [((12.98, 80.05), (13.02, 80.05)), ((13.38, 80.05), (13.42, 80.05)),
                 ((13.25, 80.18), (13.25, 80.22)), ((13.25, 79.78), (13.25, 79.82))]
    for a, b in same:
        assert cams_cell(*a)['cell_id'] == cams_cell(*b)['cell_id']
    for a, b in different:
        assert cams_cell(*a)['cell_id'] != cams_cell(*b)['cell_id']


def test_avadi_and_central_chennai_are_adjacent_cells_not_one():
    # An earlier, floor-based grid put these in a single cell. They are split
    # at 80.2 degrees east, so the claim that one value covers both was wrong.
    assert cams_cell(*CHENNAI)['cell_id'] != cams_cell(*AVADI)['cell_id']
    assert cams_cell(*CHENNAI)['row'] == cams_cell(*AVADI)['row']
    assert cams_cell(*CHENNAI)['column'] - cams_cell(*AVADI)['column'] == 1


def test_impossible_or_missing_coordinates_return_nothing():
    assert cams_cell(None, 80.0) is None
    assert cams_cell(13.0, None) is None
    assert cams_cell(95.0, 80.0) is None


def test_longitude_is_wrapped_and_reported_back_in_signed_degrees():
    assert cams_cell(13.0, -70.0)['cell_id'] == cams_cell(13.0, 290.0)['cell_id']
    assert cams_cell(13.0, -70.0)['centre_longitude'] < 0


def test_elevations_are_batched_and_missing_values_stay_none():
    calls = []

    def fetch(url, params):
        calls.append(params)
        count = len(params['latitude'].split(','))
        return {'elevation': [12.0] * count}

    values = elevations([CHENNAI] * 150, fetch)
    assert len(values) == 150 and set(values) == {12.0}
    assert len(calls) == 2  # 100 per request

    def broken(url, params):
        return {'elevation': 'not a list'}

    assert elevations([CHENNAI, AVADI], broken) == [None, None]


def test_unobtainable_features_are_pending_with_the_dataset_they_need():
    stations = [{'station_pk': 1, 'name': 'A', 'source_station_id': '1', 'latitude': CHENNAI[0], 'longitude': CHENNAI[1]},
                {'station_pk': 2, 'name': 'B', 'source_station_id': '2', 'latitude': AVADI[0], 'longitude': AVADI[1]}]
    stations.append({'station_pk': 3, 'name': 'C', 'source_station_id': '3', 'latitude': 13.30, 'longitude': 80.30})
    table = site_features(stations)
    assert table['stations'] == 3
    # A and C share the cell centred on 13.2N 80.4E; B sits in the next cell west.
    assert table['stations_sharing_a_cell'] == 2
    assert table['with_elevation'] == 0
    for key, reason in PENDING.items():
        assert table['sites'][0][key] == reason
        assert 'PENDING' in reason and 'needs' in reason
