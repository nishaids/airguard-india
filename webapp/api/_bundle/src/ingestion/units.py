"""Pollutant names and unit normalisation.

Providers disagree about units. One reports carbon monoxide in milligrams per
cubic metre, another in micrograms, a third in parts per million; a value of
``1.2`` means three different things. This module converts whatever arrives
into the unit the rest of AirGuard already uses (``config.POLLUTANT_UNITS``),
and refuses to guess when it cannot.

Conversions
-----------
Mass to mass is exact: ``1 mg/m3 = 1000 ug/m3``.

Volume mixing ratio to mass concentration depends on temperature and pressure:

    ug/m3 = ppb x M / V        mg/m3 = ppm x M / V

with ``M`` the molar mass in g/mol and ``V`` the molar volume of an ideal gas.
``V = 24.45 L/mol`` is used, which is 25 degrees C and 1 atmosphere, a common
regulatory reference condition for this conversion. Real ambient
temperature moves the result by a few per cent. Every converted record says in
its provenance that this assumption was applied, so that a later analysis can
identify and, if it matters, redo it.

Particulate matter has no molar mass; a PM value in ppb or ppm is an error and
is reported as an unsupported unit rather than converted.
"""

from __future__ import annotations

from typing import Optional, Tuple

from src import config

MOLAR_VOLUME_L = 24.45  # 25 degrees C, 1 atm

MOLAR_MASS = {
    "NO2": 46.0055,
    "NO": 30.006,
    "SO2": 64.066,
    "O3": 47.998,
    "CO": 28.010,
    "NH3": 17.031,
}

POLLUTANT_ALIASES = {
    "pm25": "PM2.5", "pm2.5": "PM2.5", "pm2_5": "PM2.5",
    "pm10": "PM10",
    "no2": "NO2", "no": "NO", "nox": "NOx",
    "so2": "SO2",
    "o3": "O3", "ozone": "O3",
    "co": "CO",
    "nh3": "NH3",
    "benzene": "Benzene", "toluene": "Toluene", "xylene": "Xylene",
}

UNIT_ALIASES = {
    "ug/m3": "ug/m3", "µg/m³": "ug/m3", "μg/m³": "ug/m3", "µg/m3": "ug/m3", "μg/m3": "ug/m3",
    "ug/m³": "ug/m3", "ugm3": "ug/m3", "ug/m^3": "ug/m3", "microgram/m3": "ug/m3",
    "mg/m3": "mg/m3", "mg/m³": "mg/m3", "mg/m^3": "mg/m3",
    "ppb": "ppb", "ppm": "ppm",
}


class UnsupportedUnit(ValueError):
    """The unit is missing, unknown, or meaningless for this pollutant."""


def canonical_pollutant(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return POLLUTANT_ALIASES.get(str(name).strip().lower().replace(" ", ""))


def canonical_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    return UNIT_ALIASES.get(str(unit).strip().lower().replace(" ", ""))


def target_unit(pollutant: str) -> Optional[str]:
    return config.POLLUTANT_UNITS.get(pollutant)


def normalise(pollutant: str, value: float, raw_unit: Optional[str]) -> Tuple[float, str, Optional[str]]:
    """Convert ``value`` to AirGuard's unit for ``pollutant``.

    Returns ``(value, unit, note)``. ``note`` is ``None`` when no assumption was
    needed and otherwise names the assumption, for the record's provenance.
    """
    target = target_unit(pollutant)
    if target is None:
        raise UnsupportedUnit(f"no canonical unit is defined for {pollutant}")
    unit = canonical_unit(raw_unit)
    if unit is None:
        raise UnsupportedUnit(f"unit {raw_unit!r} is not recognised")
    if unit == target:
        return float(value), target, None

    mass = {"ug/m3": 1.0, "mg/m3": 1000.0}  # in micrograms per cubic metre
    if unit in mass and target in mass:
        return float(value) * mass[unit] / mass[target], target, None

    molar_mass = MOLAR_MASS.get(pollutant)
    note = f"converted assuming 25 C and 1 atm (molar volume {MOLAR_VOLUME_L} L/mol)"

    if unit in ("ppb", "ppm") and target in mass:
        if molar_mass is None:
            raise UnsupportedUnit(f"{pollutant} cannot be expressed in {unit}")
        ppb = float(value) * (1000.0 if unit == "ppm" else 1.0)
        micrograms = ppb * molar_mass / MOLAR_VOLUME_L
        return micrograms / mass[target], target, note

    if unit in mass and target in ("ppb", "ppm"):
        if molar_mass is None:
            raise UnsupportedUnit(f"{pollutant} in {unit} cannot be converted to {target} without a molar mass")
        ppb = float(value) * mass[unit] * MOLAR_VOLUME_L / molar_mass
        return (ppb / 1000.0 if target == "ppm" else ppb), target, note

    if unit in ("ppb", "ppm") and target in ("ppb", "ppm"):
        return float(value) * (1000.0 if unit == "ppm" else 0.001), target, None

    raise UnsupportedUnit(f"cannot convert {pollutant} from {unit} to {target}")
