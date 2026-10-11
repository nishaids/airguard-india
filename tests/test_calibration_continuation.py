"""Finite orchestration tests: no real processes waited on, downloads, or DB calls."""
import copy
from dataclasses import replace
import json
import urllib.error
import pytest
from src.research.calibration import continuation as c


class Harness:
    def __init__(self, tmp_path, *, alive=True, incomplete=False):
        self.root, self.pid = tmp_path, 990001
        self.processes = {self.pid:c.ProcessRecord(self.pid,100.,('python','helper'),r'C:\private\python.exe')}
        if alive:
            self.processes.update({pid:c.ProcessRecord(pid,birth,('python',*c.DEFAULT_PREFIXES[pid]),r'C:\private\python.exe')
                                   for pid,birth in c.OBSERVED_BIRTHS.items()})
        self.fingerprint = {'protocol_sha256':'protocol','source_sha256':'science','selection_sha256':'selection'}
        self.calls, self.sleeps = {}, []
        self.audit = {'missing_openaq':['12'] if incomplete else [],
                      'missing_weather':['point'] if incomplete else [],
                      'pagination_pending':[{'station_id':'12','pollutant':'O3','status':'pending','failed_check':None}] if incomplete else [],
                      'checksum_audit':'PASS','expected_weather_points':151,'expected_openaq_stations':181}
        self.manifest = tmp_path/'workers.json'
        self.status, self.lock = tmp_path/'status.json', tmp_path/'continuation.lock'

        def counted(name, value=None, clear=None):
            def action():
                self.calls[name] = self.calls.get(name,0)+1
                if clear:
                    self.audit[clear] = []
                return copy.deepcopy(value)
            return action

        def audit():
            self.calls['audit'] = self.calls.get('audit',0)+1
            return copy.deepcopy(self.audit)

        self.stages = c.Stages(audit, counted('merge'), counted('openaq',clear='missing_openaq'),
            counted('weather',clear='missing_weather'), counted('repair',clear='pagination_pending'),
            counted('checkpoint'), counted('measured',{'dataset_hash':'dataset'}),
            counted('preliminary',{'dataset_hash':'dataset','run_id':'run','final_test_scored':False,'folds':[{'strict':{'ridge_strict':{}}}]}),
            counted('reproduction',{'status':'PASS'}), counted('prospective',{'read_only':True}),
            counted('readiness',{'status':'COLLECTING_NOT_RESEARCH_READY'}), counted('paper'),counted('figures'))

    def prepare(self):
        return c.prepare_worker_manifest(self.manifest,probe=self.processes.get,
                                         fingerprint=lambda:copy.deepcopy(self.fingerprint))

    def discover(self):
        return [p for pid,p in self.processes.items() if pid!=self.pid]

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        for pid in c.DEFAULT_PREFIXES:
            self.processes.pop(pid,None)

    def run(self, **kwargs):
        return c.run(self.manifest,stages=self.stages,probe=self.processes.get,discover=self.discover,
                     fingerprint=lambda:copy.deepcopy(self.fingerprint),sleeper=self.sleep,
                     status_path=self.status,lock_path=self.lock,pid=self.pid,**kwargs)


def test_waits_for_exact_inherited_workers_before_resuming_missing_data(tmp_path):
    h = Harness(tmp_path,incomplete=True)
    manifest = h.prepare()
    result = h.run()
    assert h.sleeps == [30]
    assert result['state']=='FINISHED'
    assert all(result[key] for key in ('collection_finished','measured_completed','experiment_completed'))
    assert not result['primary_experiment_completed']
    assert h.calls['openaq']==h.calls['weather']==h.calls['repair']==1
    assert h.calls['preliminary']==h.calls['prospective']==h.calls['figures']==1
    assert 'C:\\private' not in json.dumps(manifest)
    assert 'C:\\private' not in h.status.read_text()
    assert all(w['executable_sha256'] for w in manifest['workers'])
    assert not h.lock.exists()


def test_complete_caches_trigger_no_download_or_pagination_calls(tmp_path):
    h = Harness(tmp_path,alive=False)
    manifest = h.prepare()
    assert all(w['prepared_state']=='ALREADY_EXITED' and w['create_time'] is None for w in manifest['workers'])
    result = h.run()
    assert result['state']=='FINISHED'
    assert not any(h.calls.get(name) for name in ('openaq','weather','repair'))
    assert not h.sleeps


@pytest.mark.parametrize('change',['birth','prefix','executable'])
def test_worker_identity_changes_block_all_resume_and_fits(tmp_path,change):
    h = Harness(tmp_path,incomplete=True)
    h.prepare()
    original = h.processes[33748]
    h.processes[33748] = replace(original,**({'create_time':original.create_time+1} if change=='birth' else
        {'argv':('python','-m','unexpected.module')} if change=='prefix' else {'executable':'different-python'}))
    result = h.run()
    assert result['state']=='BLOCKED'
    assert result['failures'][-1]['code']=='OBSERVED_WORKER_PID_REUSED_OR_COMMAND_CHANGED'
    assert not h.calls


def test_preparation_refuses_reused_observed_pid(tmp_path):
    h = Harness(tmp_path)
    h.processes[12384] = replace(h.processes[12384],create_time=999.)
    with pytest.raises(c.WorkerIdentityChanged):
        h.prepare()
    assert not h.manifest.exists()


def test_additional_archive_worker_after_preparation_blocks_resume(tmp_path):
    h = Harness(tmp_path,alive=False,incomplete=True)
    h.prepare()
    h.processes[999] = c.ProcessRecord(999,12.,('python','-m','src.research.calibration.openaq_archive'))
    result = h.run()
    assert result['state']=='BLOCKED' and result['unexpected_archive_worker_pids']==[999]
    assert result['failures'][-1]['code']=='ADDITIONAL_ARCHIVE_WORKER_BLOCKS_RESUME'
    assert not h.calls


def test_second_helper_cannot_overwrite_running_status(tmp_path):
    h = Harness(tmp_path,alive=False)
    h.prepare()
    h.status.write_text('{"owned_by_first":true}')
    with c.ExclusiveLock(h.lock,probe=h.processes.get,pid=h.pid):
        with pytest.raises(c.DuplicateHelper):
            h.run()
        assert json.loads(h.status.read_text())=={'owned_by_first':True}
    assert not h.lock.exists()


@pytest.mark.parametrize('owner_birth,current_birth',[(5.,None),(5.,6.)])
def test_demonstrably_dead_lock_can_be_recovered(tmp_path,owner_birth,current_birth):
    h = Harness(tmp_path,alive=False)
    h.lock.write_text(json.dumps({'pid':111,'create_time':owner_birth,'token':'dead-owner'}))
    if current_birth is not None:
        h.processes[111] = c.ProcessRecord(111,current_birth,('unrelated-program',))
    with c.ExclusiveLock(h.lock,probe=h.processes.get,pid=h.pid):
        assert json.loads(h.lock.read_text())['pid']==h.pid
    assert not h.lock.exists()


def test_alive_lock_owner_cannot_be_recovered_without_proof_of_death(tmp_path):
    h = Harness(tmp_path,alive=False)
    h.lock.write_text(json.dumps({'pid':h.pid,'create_time':100.,'token':'still-alive'}))
    with pytest.raises(c.DuplicateHelper):
        with c.ExclusiveLock(h.lock,probe=h.processes.get,pid=h.pid):
            pass
    assert json.loads(h.lock.read_text())['token']=='still-alive'


def test_source_change_before_fits_blocks_experiment(tmp_path):
    h = Harness(tmp_path,alive=False)
    h.prepare()
    original = h.stages.measured
    def changed():
        result = original()
        h.fingerprint['source_sha256']='changed-science'
        return result
    h.stages.measured = changed
    result = h.run()
    assert result['state']=='BLOCKED'
    assert result['failures'][-1]['code']=='FROZEN_PROTOCOL_OR_SCIENTIFIC_SOURCE_CHANGED'
    assert not h.calls.get('preliminary')


def test_transient_failure_is_bounded_retained_and_secret_free(tmp_path):
    h = Harness(tmp_path,alive=False,incomplete=True)
    h.prepare()
    original = h.stages.weather
    attempts = []
    def transient():
        attempts.append(1)
        if len(attempts)==1:
            raise urllib.error.URLError('https://private.example/SECRET_TOKEN')
        return original()
    h.stages.weather = transient
    result = h.run(max_download_rounds=2)
    assert len(attempts)==2 and result['state']=='FINISHED'
    assert any(f.get('error_type')=='URLError' for f in result['failures'])
    assert 'SECRET_TOKEN' not in h.status.read_text()


def test_permanent_network_failure_is_not_retried_and_partial_status_is_explicit(tmp_path):
    h = Harness(tmp_path,alive=False,incomplete=True)
    h.prepare()
    attempts = []
    def forbidden():
        attempts.append(1)
        raise urllib.error.HTTPError('https://private/SECRET',403,'not authorized',{},None)
    h.stages.weather = forbidden
    result = h.run(max_download_rounds=3)
    assert len(attempts)==1
    assert result['state']=='FINISHED_WITH_FAILURES' and not result['collection_finished']
    assert result['measured_completed'] and result['experiment_completed']
    assert 'SECRET' not in h.status.read_text()


def test_unrepaired_pagination_never_enters_another_fit(tmp_path):
    h = Harness(tmp_path,alive=False)
    h.audit['pagination_pending']=[{'station_id':'12','pollutant':'O3','failed_check':'immutable_hourly_bin_conflict'}]
    h.prepare()
    h.stages.repair = lambda:None
    result = h.run()
    assert result['state']=='FINISHED_WITH_FAILURES'
    assert not result['collection_finished'] and not result['experiment_completed']
    assert not h.calls.get('measured') and not h.calls.get('preliminary')
    assert h.calls['prospective']==h.calls['readiness']==1


def test_final_test_scoring_status_is_checked_before_claiming_completion(tmp_path):
    h = Harness(tmp_path,alive=False)
    h.prepare()
    h.stages.preliminary = lambda:{'run_id':'bad','dataset_hash':'dataset','final_test_scored':True}
    result = h.run()
    assert result['state']=='BLOCKED' and not result['experiment_completed']
    assert result['failures'][-1]['code']=='PRELIMINARY_FINAL_TEST_ISOLATION_NOT_ESTABLISHED'


def test_final_checkpoint_report_reads_saved_terminal_status_once(tmp_path):
    h = Harness(tmp_path,alive=False)
    h.prepare()
    snapshots = []
    def report():
        snapshots.append(json.loads(h.status.read_text()))
    h.stages.report = report
    result = h.run()
    assert len(snapshots)==1 and snapshots[0]['state']=='FINISHED'
    assert snapshots[0]['collection_finished'] and snapshots[0]['experiment_completed']
    assert snapshots[0]['finished_at']
    assert result['stages']['checkpoint_report']['state']=='COMPLETE'


def test_report_failure_is_retained_without_recursive_report_calls(tmp_path):
    h = Harness(tmp_path,alive=False)
    h.prepare()
    attempts = []
    def report():
        attempts.append(1)
        raise RuntimeError('sensitive message is not persisted')
    h.stages.report = report
    result = h.run()
    assert len(attempts)==1 and result['state']=='FINISHED_WITH_FAILURES'
    assert result['failures'][-1]['stage']=='checkpoint_report'
    assert 'sensitive message' not in h.status.read_text()
