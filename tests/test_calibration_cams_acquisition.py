import copy
import json
import logging
import sys
from types import SimpleNamespace
from datetime import date
import pytest
from src.research.calibration import cams_acquisition as archive
from src.research.calibration.protocol import load


def selection():
    return {'stations':[{'latitude':8.51,'longitude':70.91}, {'latitude':30.75,'longitude':94.09}]}


def test_plan_uses_only_development_runs_and_frozen_coordinates():
    plan=archive.make_plan(load(),selection())
    assert plan['run_range']==['2025-02-17','2026-07-08']
    assert plan['run_count']==507
    assert plan['target_range']==['2025-02-19','2026-07-09']
    assert not plan['final_test_acquisition']
    assert plan['area']==[30.8,70.8,8.4,94.0]
    for group in ('surface','lowest_model_level'):
        jobs=[j for j in plan['jobs'] if j['group']==group]
        dates=[d for j in jobs for d in j['request']['date']]
        assert len(dates)==len(set(dates))==507
        assert max(dates)<'2026-07-09'
        assert all(j['request']['type']==['forecast'] and j['request']['time']==['00:00'] for j in jobs)
    assert len(plan['jobs'])==36
    assert all('total_column' not in v for j in plan['jobs'] for v in j['request']['variable'])


def test_plan_is_deterministic_without_reading_targets():
    p=load(); s=selection()
    assert archive.make_plan(p,s)==archive.make_plan(copy.deepcopy(p),copy.deepcopy(s))
    assert archive.make_plan(p,s)==json.loads(json.dumps(archive.make_plan(p,s)))
    assert [int(x) for x in archive.make_plan(p,s)['jobs'][1]['request']['leadtime_hour']]==list(range(9,43,3))


def test_pending_and_failed_jobs_never_resubmitted(tmp_path,monkeypatch):
    plan=archive.make_plan(load(),selection())
    plan['jobs']=plan['jobs'][:2]
    monkeypatch.setattr(archive,'ROOT',tmp_path)
    monkeypatch.setattr(archive,'STATE',tmp_path/'state.json')
    monkeypatch.setattr(archive,'freeze',lambda:plan)
    calls=[]
    class Remote:
        status='accepted'
        request_id='EXISTING_ID'
    class Client:
        def __init__(self,**kw): self.client=self
        def retrieve(self,*args): calls.append('submit'); return Remote()
        def get_remote(self,id): calls.append('poll'); return Remote()
    monkeypatch.setitem(sys.modules,'cdsapi',SimpleNamespace(Client=Client))
    old=logging.root.manager.disable
    try:
        first=archive.step(); archive.step()
        assert calls.count('submit')==2
        assert first['counts']=={'accepted':2}
        state=json.loads(archive.STATE.read_text())
        for entry in state['jobs'].values(): entry['status']='SUBMISSION_FAILED'
        archive.STATE.write_text(json.dumps(state))
        archive.step()
        assert calls.count('submit')==2
    finally: logging.disable(old)
