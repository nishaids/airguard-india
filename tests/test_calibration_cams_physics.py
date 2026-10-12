import numpy as np
import pytest
from src.research.calibration import cams_physics as p


def test_interpolation_uses_native_same_run_brackets_not_future_runs():
    actual=p.interpolate([9,12,15],[[1,10],[4,40],[7,70]],[11.5,14.5])
    assert np.allclose(actual,[[3.5,35],[6.5,65]])
    with pytest.raises(ValueError,match='extrapolation'):p.interpolate([12,15],[[4],[7]],[11.5])


def test_lowest_level_hybrid_pressure_and_units():
    pv=np.zeros(276);pv[138+136]=.98;pv[138+137]=1
    pressure=p.lowest_level_pressure(np.array([100000]),pv)
    assert pressure[0]==99000
    gas=p.mass_concentration([1e-7],[300],[0],pressure)
    assert gas[0]==pytest.approx(114.96,rel=.001)
    assert p.mass_concentration([1e-7],[300],[0],pressure,co=True)[0]==pytest.approx(gas[0]/1000)
    assert p.mass_concentration([1e-7],[300],[.02],pressure)[0]<gas[0]


@pytest.mark.parametrize('r,t,q,pres',[(-1,300,0,100000),(1,0,0,100000),(1,300,1,100000),(1,300,0,0),(float('nan'),300,0,100000)])
def test_invalid_conversion_cannot_produce_a_forecast(r,t,q,pres):
    with pytest.raises(ValueError):p.mass_concentration([r],[t],[q],[pres])


def test_missing_coefficients_cannot_be_replaced_by_assumed_surface_pressure():
    with pytest.raises(ValueError):p.lowest_level_pressure([100000],[])
