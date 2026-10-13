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
        assert calls.count('submit')==1
        assert first['counts']=={'accepted':1}
        state=json.loads(archive.STATE.read_text())
        for entry in state['jobs'].values(): entry['status']='SUBMISSION_FAILED'
        archive.STATE.write_text(json.dumps(state))
        archive.step()
        assert calls.count('submit')==1
        archive.STATE.unlink()
        empty=archive.step(poll_only=True)
        assert empty['counts']=={}
        assert calls.count('submit')==1
    finally: logging.disable(old)


def test_transport_failure_reopens_existing_id_without_submitting(tmp_path,monkeypatch):
    plan=archive.make_plan(load(),selection())
    plan['jobs']=plan['jobs'][:2]
    monkeypatch.setattr(archive,'ROOT',tmp_path)
    monkeypatch.setattr(archive,'STATE',tmp_path/'state.json')
    monkeypatch.setattr(archive,'freeze',lambda:plan)
    first,second=(job['id'] for job in plan['jobs'])
    transport={'category':'CLIENT_OR_SERVICE_ERROR','http_status':None,'terms_mentioned':False}
    def write(entries):
        archive.STATE.write_text(json.dumps({'plan_sha256':plan['sha256'],'dataset':'d','jobs':entries,'final_test_accessed':False}))
    base={'status':'RETRIEVAL_OR_VALIDATION_FAILED','request_id':'EXISTING_ID','error':transport}
    write({first:dict(base)})
    result=archive.reopen_transport_failure(first[:12],'network interruption during polling')
    entry=json.loads(archive.STATE.read_text())['jobs'][first]
    assert result=={'reopened':first[:12],'counts':{'running':1},'new_request_submitted':False}
    assert entry['status']=='running' and entry['request_id']=='EXISTING_ID' and 'error' not in entry
    assert entry['recovery_history'][0]['previous_error']==transport
    assert entry['recovery_history'][0]['new_request_submitted'] is False
    refused=[
        {first:{**base,'error':{**transport,'http_status':400,'category':'REQUEST_REJECTED'}}},  # provider rejection
        {first:{**base,'request_id':None}},                                                   # ambiguous submission
        {first:{**base,'file':'data/x.grib'}},                                                # validation failure
        {first:{**base,'status':'SUBMISSION_FAILED'}},
        {first:dict(base),second:dict(base)},                                                 # ambiguous identifier
    ]
    for index,entries in enumerate(refused):
        write(entries)
        with pytest.raises(ValueError):
            archive.reopen_transport_failure(first[:12] if index<4 else '', 'note')
        assert json.loads(archive.STATE.read_text())['jobs']==entries
    # A reopened job is polled, never resubmitted.
    write({first:dict(base)})
    archive.reopen_transport_failure(first[:12],'note')
    calls=[]
    class Remote:
        status='running'
    class Client:
        def __init__(self,**kw): self.client=self
        def retrieve(self,*args): calls.append('submit')
        def get_remote(self,id): calls.append(('poll',id)); return Remote()
    monkeypatch.setitem(sys.modules,'cdsapi',SimpleNamespace(Client=Client))
    old=logging.root.manager.disable
    try:
        assert archive.step(poll_only=True)['counts']=={'running':1}
        assert archive.step()['counts']=={'running':1}
    finally: logging.disable(old)
    assert calls==[('poll','EXISTING_ID'),('poll','EXISTING_ID')]


def test_author_pause_blocks_default_submission_and_preserves_ids(tmp_path,monkeypatch):
    plan=archive.make_plan(load(),selection())
    plan['jobs']=plan['jobs'][:2]
    monkeypatch.setattr(archive,'ROOT',tmp_path)
    monkeypatch.setattr(archive,'STATE',tmp_path/'state.json')
    monkeypatch.setattr(archive,'freeze',lambda:plan)
    archive.STATE.write_text(json.dumps({'plan_sha256':plan['sha256'],'jobs':{}}))
    archive.pause_new_requests()
    class Client:
        def __init__(self,**kw): self.client=self
        def retrieve(self,*args): pytest.fail('Author pause must block submissions')
        def get_remote(self,*args): pytest.fail('There are no existing request IDs')
    monkeypatch.setitem(sys.modules,'cdsapi',SimpleNamespace(Client=Client))
    old=logging.root.manager.disable
    try:
        assert archive.step()['counts']=={}
    finally: logging.disable(old)
    state=json.loads(archive.STATE.read_text())
    assert state['submission_control']['new_requests_authorized'] is False
    assert state['jobs']=={}


def test_reconciliation_polls_only_explicit_existing_scope_and_redacts_replies(tmp_path,monkeypatch,capsys):
    plan=archive.make_plan(load(),selection())
    plan['jobs']=plan['jobs'][:2]
    monkeypatch.setattr(archive,'ROOT',tmp_path)
    monkeypatch.setattr(archive,'STATE',tmp_path/'state.json')
    monkeypatch.setattr(archive,'freeze',lambda:plan)
    result=tmp_path/'results/research';result.mkdir(parents=True)
    (result/'cams_ads_probe.json').write_text(json.dumps({'request_id':'PROBE','status':'SUBMITTED'}))
    entries={j['id']:{'request_id':f'ARCHIVE{i}','status':'running'} for i,j in enumerate(plan['jobs'])}
    archive.STATE.write_text(json.dumps({'plan_sha256':plan['sha256'],'jobs':entries}))
    archive.pause_new_requests()
    calls=[]
    secret='TEST_SECRET_NEVER_PERSIST_PROVIDER_REPLY'
    class Client:
        def __init__(self,**kw): self.client=self;print(secret)
        def retrieve(self,*args): pytest.fail('Reconciliation must never submit')
        def get_remote(self,request_id):
            calls.append(request_id)
            return SimpleNamespace(json={'processID':archive.ads_probe.DATASET,'status':'running',
                                         'metadata':{'credentials':secret},'download_url':secret})
    monkeypatch.setitem(sys.modules,'cdsapi',SimpleNamespace(Client=Client))
    counts=archive.reconcile_existing(['ARCHIVE0','PROBE'])
    assert calls==['ARCHIVE0','PROBE']
    assert counts['ads_requests_in_reported_scope']==2 and counts['content_valid']==0
    report=json.loads((result/'cams_archive_status.json').read_text())
    assert report['additional_preexisting_requests'][0]['request_id']=='ARCHIVE1'
    assert report['new_requests_submitted']==0
    assert secret not in capsys.readouterr().out
    assert all(secret not in p.read_text() for p in tmp_path.rglob('*.json'))
    with pytest.raises(ValueError,match='Unknown request'):
        archive.reconcile_existing(['UNKNOWN'])
    assert calls==['ARCHIVE0','PROBE']
