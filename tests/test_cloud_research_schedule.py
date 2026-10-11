"""Scheduled prefetch prepares all locations; issuance precedes new fetches."""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from src.nationwide import jobs


@pytest.mark.parametrize('hour,minute,warm_count,force,issue_count', [
    (14, 20, 12, True, 0),   # 19:50 IST daily prefetch
    (14, 17, 2, False, 0),   # 19:47 IST ordinary hourly refresh
    (14, 30, 2, False, 12),  # 20:00 IST fixed issuance
])
def test_cloud_schedule_keeps_prefetch_before_issue(hour, minute, warm_count, force, issue_count):
    now = datetime(2026, 10, 11, hour, minute, tzinfo=timezone.utc)
    events = []

    class Cursor:
        def execute(self, *args): pass

    class Store:
        def claim(self, *args): return 'test-lease'
        def release(self, *args): events.append('release')
        def event(self, *args, **kwargs): pass
        def popular(self, limit):
            return [{'key': str(i), 'lat': 13., 'lon': 80., 'name': str(i)} for i in range(limit)]
        @contextmanager
        def cursor(self): yield Cursor()

    class Research:
        def __init__(self, store): pass
        def register_protocol(self): pass
        def capture(self, location, date):
            assert date.isoformat() == '2026-10-11'
            events.append('issue')
            return {'status': 'ISSUED'}
        def verify(self, service): return []

    class Service:
        store = Store()
        def summary(self, *args, **kwargs):
            assert kwargs['force'] is force
            events.append('warm')
            return {'ok': True, 'tomorrow': {}, 'provider_status': {}}

    with patch.object(jobs, 'utcnow', return_value=now), patch.object(jobs, 'verify', return_value=[]), patch('src.research.storage.ResearchStore', Research):
        result = jobs.refresh(Service())
    assert result['status'] == 'SUCCESS'
    assert events.count('warm') == warm_count and events.count('issue') == issue_count
    if issue_count:
        assert events.index('warm') > max(i for i, event in enumerate(events) if event == 'issue')
    assert events[-1] == 'release'
