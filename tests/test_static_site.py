from src.features.static_site import CAMS_RESOLUTION, PENDING, cams_cell, elevations, site_features

CHENNAI = (13.0878, 80.2785)
AVADI = (13.1147, 80.1098)


def test_cells_are_identified_and_their_centres_are_inside_the_cell():
    cell = cams_cell(*CHENNAI)
    assert cell['resolution_degrees'] == CAMS_RESOLUTION
    assert abs(cell['centre_latitude'] - CHENNAI[0]) <= CAMS_RESOLUTION
    assert abs(cell['centre_longitude'] - CHENNAI[1]) <= CAMS_RESOLUTION


def test_two_places_45_km_apart_can_share_one_modelled_input():
    # This is the resolution limitation as a fact about two real places rather
    # than a sentence: Avadi and central Chennai receive the same grid value.
    assert cams_cell(*CHENNAI)['cell_id'] == cams_cell(*AVADI)['cell_id']


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
    table = site_features(stations)
    assert table['stations'] == 2
    assert table['stations_sharing_a_cell'] == 2
    assert table['with_elevation'] == 0
    for key, reason in PENDING.items():
        assert table['sites'][0][key] == reason
        assert 'PENDING' in reason and 'needs' in reason
