"""Missed-issuance alerting that records, and deliberately does not send.

The 30-day prospective record cannot be backdated: a cutoff that passes without
an issued forecast is lost permanently, so a missed run has to be noticed the
same day. What this module will not do is message anyone. No outbound channel,
recipient or opt-in has been authorised, so a would-be alert is rendered,
recorded in `provider_events` and surfaced on /status; delivery stays
unconfigured until a human supplies an authorised channel (see HUMAN_ACTIONS.md).
"""
from datetime import datetime, timezone

STATES = {
    'MISSED_ISSUANCE': 'The 20:00 IST cutoff passed with no issued forecast. That day cannot be recovered.',
    'SCHEDULE_INACTIVE': 'The fixed-time issuance schedule is not active, so no cutoff will be served.',
    'ATTEMPTED_NO_ELIGIBLE_FORECASTS': 'The job ran at the cutoff but stored no forecast; inputs were ineligible.',
}


def render(health):
    """One alert payload, or None when nothing is wrong. No recipient is implied."""
    issuance = health['issuance']
    state = issuance['state']
    if not issuance.get('alert_required'):
        return None
    return {
        'severity': 'CRITICAL' if state in ('MISSED_ISSUANCE', 'SCHEDULE_INACTIVE') else 'WARNING',
        'state': state,
        'reason': STATES.get(state, 'Fixed-time issuance needs attention.'),
        'expected_cutoff': issuance['expected_cutoff'],
        'next_cutoff': issuance['next_cutoff'],
        'forecasts_in_ledger': health.get('forecasts'),
        'last_issue': health.get('last_issue'),
        'subject': f'AirGuard fixed-time issuance: {state}',
        'delivery': 'NOT_SENT — no authorised channel, recipient or opt-in exists',
        'rendered_at': datetime.now(timezone.utc).isoformat(),
    }


def record(store, health):
    """Record the alert decision as an auditable event; never contact anyone."""
    alert = render(health)
    status = 'ALERT_SUPPRESSED_NO_CHANNEL' if alert else 'OK'
    detail = alert or {'state': health['issuance']['state'], 'note': 'No alert condition.'}
    store.event('scheduler', 'issuance_heartbeat', status, 0, count=health.get('forecasts') or 0, detail=detail)
    return {'alert': alert, 'status': status, 'issuance': health['issuance'],
            'forecasts': health.get('forecasts'), 'last_issue': health.get('last_issue'),
            'checked_at': datetime.now(timezone.utc).isoformat()}
