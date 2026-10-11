from datetime import datetime,timedelta,timezone
from src.features.exposure import choose_window, forecast_windows
from src.features.safe_window import best_window
import numpy as np


def test_practical_hours_and_common_length_in_live_and_historical():
    values=[5]*6+[100]*18;values[10:12]=[20,20]
    assert choose_window(values)['start_hour']==10
    assert best_window(np.array(values,dtype=float))['start_hour']==10
    assert choose_window(values)['length']==2
    values[10:12]=[None,401]
    assert choose_window(values)['start_hour']!=10


def test_live_window_uses_hourly_exposure_not_rolling_aqi():
    start=datetime(2026,10,11,18,30,tzinfo=timezone.utc)
    rows=[{'time':(start+timedelta(hours=i)).isoformat(),'PM2.5':10 if i in (10,11) else 60,'PM10':20,'NO2':10} for i in range(24)]
    weather=[{'time':r['time'],'boundary_layer_height':10 if i in (10,11) else 500} for i,r in enumerate(rows)]
    window=forecast_windows(rows,start,start+timedelta(days=1),weather)['lower_exposure_window']
    assert window['start']==rows[10]['time'] and window['window_hours']==2
    assert 'shallowest' in window['boundary_layer_caveat'] and 'min_aqi' not in window


def test_missing_dominant_pollutant_not_artificially_clean_hour():
    start=datetime(2026,10,11,18,30,tzinfo=timezone.utc)
    rows=[{'time':(start+timedelta(hours=i)).isoformat(),'PM2.5':20,'NO2':10,'O3':40} for i in range(24)]
    rows[10].pop('O3')
    assert forecast_windows(rows,start,start+timedelta(days=1))['lower_exposure_window'] is None
