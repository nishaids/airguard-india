from datetime import datetime, timedelta, timezone

from src.nationwide.alerts import record, render
from src.nationwide.monitoring import classify

CUTOFF = datetime(2026, 10, 11, 14, 30, tzinfo=timezone.utc)
ACTIVE = [{'jobname': 'airguard-research-issue', 'schedule': '30 14 * * *', 'active': True}]
REGISTERED = CUTOFF - timedelta(days=3)


class FakeStore:
    def __init__(self):
        self.events = []

    def event(self, provider, operation, status, latency, count=0, http_status=None, error_class=None, detail=None):
        self.events.append({'provider': provider, 'operation': operation, 'status': status,
                            'count': count, 'detail': detail})


def health(state_now, latest_issue=None, schedules=ACTIVE, latest_event=None, forecasts=0):
    issuance = classify(state_now, REGISTERED, schedules, latest_issue, latest_event)
    return {'issuance': issuance, 'forecasts': forecasts, 'last_issue': latest_issue}


def test_served_cutoff_raises_no_alert_and_records_ok():
    store = FakeStore()
    verdict = record(store, health(CUTOFF + timedelta(hours=2), latest_issue=CUTOFF + timedelta(minutes=2), forecasts=12))
    assert verdict['alert'] is None
    assert verdict['status'] == 'OK'
    assert store.events[0]['operation'] == 'issuance_heartbeat'


def test_missed_cutoff_renders_a_critical_alert_that_is_not_sent():
    store = FakeStore()
    verdict = record(store, health(CUTOFF + timedelta(hours=5)))
    alert = verdict['alert']
    assert verdict['issuance']['state'] == 'MISSED_ISSUANCE'
    assert alert['severity'] == 'CRITICAL'
    assert alert['delivery'].startswith('NOT_SENT')
    assert 'cannot be recovered' in alert['reason']
    assert store.events[0]['status'] == 'ALERT_SUPPRESSED_NO_CHANNEL'


def test_inactive_schedule_is_critical_and_an_empty_attempt_is_a_warning():
    inactive = [{'jobname': 'airguard-research-issue', 'schedule': '30 14 * * *', 'active': False}]
    assert render(health(CUTOFF + timedelta(hours=5), schedules=inactive))['severity'] == 'CRITICAL'
    attempted = render(health(CUTOFF + timedelta(hours=5),
                              latest_event={'created_at': CUTOFF + timedelta(minutes=1)}))
    assert attempted['state'] == 'ATTEMPTED_NO_ELIGIBLE_FORECASTS'
    assert attempted['severity'] == 'WARNING'


def test_open_window_is_not_an_alert_so_a_pending_cutoff_is_never_cried_wolf():
    assert render(health(CUTOFF + timedelta(minutes=5))) is None
