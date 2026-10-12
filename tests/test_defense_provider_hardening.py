from datetime import datetime, timezone
import pytest
from src.nationwide import providers
from src.ingestion.http import HttpError


class Store:
    def records(self,rows): self.rows=rows


def test_boolean_timestamp_rejected_before_persistence():
    p=providers.Providers(Store())
    with pytest.raises(HttpError,match='timestamp'):
        p.parse_series({'hourly':{'time':[True],'pm2_5':[2]},'hourly_units':{'pm2_5':'ug/m3'}},
            13,80,{'pm2_5':'PM2.5'},'open_meteo','cams_global','modelled_forecast','test')


@pytest.mark.parametrize('bad',[None,[],{'country_code':'IN','latitude':13,'longitude':80,'name':['invalid']}])
def test_malformed_geocoding_records_fail_cleanly(bad):
    p=providers.Providers(Store())
    p.get_json=lambda *args,**kwargs:{'results':[bad]}
    with pytest.raises(HttpError,match='geocoding'):
        p.search('Avadi')


def test_boolean_weather_is_not_a_numeric_measurement():
    p=providers.Providers(Store())
    result=p.parse_series({'hourly':{'time':[datetime(2026,10,12,tzinfo=timezone.utc).timestamp()],
        'temperature_2m':[True]},'hourly_units':{'temperature_2m':'°C'}},13,80,
        {'temperature_2m':'temperature_2m'},'weather','gfs_seamless','weather_forecast','test')
    assert 'temperature_2m' not in result['rows'][0]
