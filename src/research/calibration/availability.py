"""When each input would have existed, and a guard that refuses anything later.

Every feature in the study answers one question before it is allowed in: when
would this value have become available in real life? The answers live in
FEATURE_AVAILABILITY, one entry per feature group, and the cutoffs they imply
are computed in one place (`Cutoffs`) so the dataset builder, the tests and the
audit trail cannot disagree about what "before issue time" means.

`guard_*` functions are called by the builder on the timestamps it is about to
use. They raise LeakageError rather than filter: a filter would hide a
programming mistake, and a leak that is silently dropped in one place tends to
reappear in another.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo('Asia/Kolkata')
ISSUE_LOCAL = time(20, 0)
MEASUREMENT_LATENCY = timedelta(hours=3)
FIRE_LATENCY = timedelta(hours=3)
WEATHER_MINIMUM_LEAD = timedelta(hours=48)
FEATURE_VERSION = 'station-calibration-features-v1'


class LeakageError(ValueError):
    """An input that would not have existed at issue time was about to be used."""


@dataclass(frozen=True)
class Cutoffs:
    """Every time boundary for one target day, in UTC."""
    target_date: date
    issue: datetime
    target_start: datetime
    target_end: datetime
    measurement: datetime
    fire: datetime
    weather_latest_run: datetime

    @classmethod
    def for_target(cls, target_date):
        if isinstance(target_date, datetime):
            target_date = target_date.date()
        start = datetime.combine(target_date, time(0, 0), tzinfo=IST).astimezone(timezone.utc)
        issue = datetime.combine(target_date - timedelta(days=1), ISSUE_LOCAL, tzinfo=IST).astimezone(timezone.utc)
        end = start + timedelta(days=1)
        return cls(target_date=target_date, issue=issue, target_start=start, target_end=end,
                   measurement=issue - MEASUREMENT_LATENCY, fire=issue - FIRE_LATENCY,
                   # The latest run that may contribute is the one feeding the last
                   # target hour, initialised at least the minimum lead before it.
                   weather_latest_run=end - WEATHER_MINIMUM_LEAD)


FEATURE_AVAILABILITY = {
    'A_cams': {
        'source': 'CAMS global via Open-Meteo, archived fields',
        'value_time': 'each hour of the target day D and of D-1',
        'provider_issue_time': 'not exposed by the provider',
        'latest_permissible_use': 'issue time, 20:00 IST on D-1',
        'issue_time_valid': False,
        'operationally_reconstructable': False,
        'reason': 'The archive holds fields from runs initialised at or after the issue time for the '
                  'target day. It is a short-lead proxy for the forecast that was available. Genuine '
                  'archived runs need Copernicus ADS access.',
    },
    'B_measured_history': {
        'source': 'OpenAQ hourly bins, provider CPCB',
        'value_time': 'hourly bins ending at or before the measurement cutoff; daily indices for D-2 and earlier',
        'provider_issue_time': 'ingestion time is not exposed; a three-hour latency is assumed',
        'latest_permissible_use': 'measurement cutoff, 17:00 IST on D-1',
        'issue_time_valid': True,
        'operationally_reconstructable': True,
        'reason': 'Only bins that had ended three hours before issue are read. The assumption of a '
                  'healthy feed is tested by the stale-feed sensitivity analysis.',
    },
    'C_weather_forecast': {
        'source': 'Open-Meteo Previous Runs API, gfs_seamless, previous_day2',
        'value_time': 'each hour of the target day D',
        'provider_issue_time': 'a run initialised at least 48 hours before the valid hour',
        'latest_permissible_use': 'issue time',
        'issue_time_valid': True,
        'operationally_reconstructable': True,
        'reason': 'The latest contributing run was initialised at least 20 hours before issue.',
    },
    'D_temporal': {
        'source': 'calendar', 'value_time': 'the target day', 'provider_issue_time': 'n/a',
        'latest_permissible_use': 'always known', 'issue_time_valid': True,
        'operationally_reconstructable': True, 'reason': 'Known in advance.',
    },
    'E_spatial': {
        'source': 'station coordinates, elevation, CAMS grid, neighbouring stations',
        'value_time': 'static, or neighbours\' bins ending at or before the measurement cutoff',
        'provider_issue_time': 'as for measured history',
        'latest_permissible_use': 'measurement cutoff',
        'issue_time_valid': True, 'operationally_reconstructable': True,
        'reason': 'Neighbour summaries obey the same cutoff as a station\'s own history.',
    },
    'F_fire': {
        'source': 'NASA FIRMS VIIRS NOAA-21 near real time',
        'value_time': 'detections acquired in the 24 and 72 hours before the fire cutoff',
        'provider_issue_time': 'near-real-time product, within about three hours of overpass',
        'latest_permissible_use': 'fire cutoff, 17:00 IST on D-1',
        'issue_time_valid': True, 'operationally_reconstructable': True,
        'reason': 'Each detection carries its acquisition time and is filtered against the cutoff.',
    },
}


def _utc(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise LeakageError('A timestamp without a timezone cannot be checked against a cutoff.')
        return value.astimezone(timezone.utc)
    if hasattr(value, 'to_pydatetime'):
        return _utc(value.to_pydatetime())
    raise LeakageError(f'Unrecognised timestamp: {value!r}')


def guard_measurement(bin_end, cutoffs, what='measured bin'):
    """A measured hourly bin may be used only if it had ended by the cutoff."""
    if bin_end is None:
        return
    if _utc(bin_end) > cutoffs.measurement:
        raise LeakageError(
            f'{what} ends {_utc(bin_end).isoformat()}, after the measurement cutoff '
            f'{cutoffs.measurement.isoformat()} for target day {cutoffs.target_date}.')


def guard_daily_lag(lag_date, cutoffs, what='daily index'):
    """A complete measured day may be used only if it ended by the cutoff: D-2 or earlier."""
    if lag_date is None:
        return
    end = datetime.combine(lag_date, time(0, 0), tzinfo=IST).astimezone(timezone.utc) + timedelta(days=1)
    if end > cutoffs.measurement:
        raise LeakageError(
            f'{what} for {lag_date} completes after the measurement cutoff for target day {cutoffs.target_date}.')


def guard_fire(acquired, cutoffs):
    if acquired is None:
        return
    if _utc(acquired) > cutoffs.fire:
        raise LeakageError(
            f'fire detection acquired {_utc(acquired).isoformat()} is after the fire cutoff '
            f'{cutoffs.fire.isoformat()} for target day {cutoffs.target_date}.')


def guard_weather_run(run_initialised, cutoffs):
    if run_initialised is None:
        return
    if _utc(run_initialised) > cutoffs.issue:
        raise LeakageError(
            f'weather run initialised {_utc(run_initialised).isoformat()} is after the issue time '
            f'{cutoffs.issue.isoformat()} for target day {cutoffs.target_date}.')


def guard_snapshot(row, require_issue_time_valid_cams=False):
    """Re-check a stored feature snapshot. This is what a reviewer's audit runs.

    `row` is one record of the feature-snapshot table. Returns the cutoffs it
    was checked against. With `require_issue_time_valid_cams` the short-lead
    CAMS proxy is itself refused, which is how the readiness gate asks whether
    the dataset is issue-time valid end to end.
    """
    cutoffs = Cutoffs.for_target(row['target_date'])
    guard_measurement(row.get('latest_measured_bin_end_utc'), cutoffs)
    guard_measurement(row.get('latest_neighbour_bin_end_utc'), cutoffs, what='neighbour bin')
    guard_daily_lag(row.get('latest_daily_lag_date'), cutoffs)
    guard_fire(row.get('latest_fire_acquired_utc'), cutoffs)
    guard_weather_run(row.get('weather_latest_run_bound_utc'), cutoffs)
    if require_issue_time_valid_cams and not row.get('cams_issue_time_valid', False):
        raise LeakageError(
            f"CAMS input for target day {cutoffs.target_date} is {row.get('cams_source')}, a short-lead "
            'proxy and not the forecast available at issue time.')
    return cutoffs
