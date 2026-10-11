"""One finite continuation of the observed acquisition; never a scheduler.

Prepare an immutable worker manifest before launching the helper::

    python -m src.research.calibration.continuation prepare-worker-manifest
    python -m src.research.calibration.continuation run

The helper waits for the exact inherited processes, resumes missing caches only,
and records collection and experiment completion separately. It performs no
Git mutations, production issuance, deployment, or cron scheduling; result
generators may read the current Git SHA. Exception messages and process
command lines are deliberately absent from status files and console output.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import platform
from importlib.metadata import version
import time
import urllib.error
import uuid
from typing import Callable

from src import config
from src.research.calibration.checkpoint import canonical_hash

OUT = config.PROJECT_ROOT / 'results/research'
VERSION = 'airguard-finite-continuation-v1'
EXPECTED_WEATHER_POINTS = 151
DEFAULT_PREFIXES = {
    33748: ('-m', 'src.research.calibration.openaq_archive'),
    12384: ('-m', 'src.research.calibration.openaq_archive'),
    36128: ('-m', 'src.research.calibration.model_archives', 'weather'),
}
# Read-only psutil observations of the inherited workers, not merely PID numbers.
OBSERVED_BIRTHS = {33748: 1791742572.870804, 12384: 1791742572.8708603,
                   36128: 1791743869.5686169}


class ContinuationError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class DuplicateHelper(ContinuationError):
    pass


class WorkerIdentityChanged(ContinuationError):
    pass


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    create_time: float
    # Never include argv in representations, status, or exception messages.
    argv: tuple[str, ...] = field(repr=False)
    executable: str = field(default='',repr=False)


@dataclass(frozen=True)
class Worker:
    pid: int
    create_time: float | None
    command_prefix: tuple[str, ...]
    executable_sha256: str = ''

    def matches(self, process):
        return (self.create_time is not None and process.pid == self.pid and abs(process.create_time-self.create_time) < .00001
                and process.argv[1:1+len(self.command_prefix)] == self.command_prefix
                and (not self.executable_sha256 or executable_hash(process.executable) == self.executable_sha256))

    def public(self):
        return {'pid': self.pid, 'create_time': self.create_time,
                'command_prefix': list(self.command_prefix), 'executable_sha256': self.executable_sha256,
                'prepared_state':'ALREADY_EXITED' if self.create_time is None else 'OBSERVED_ALIVE'}


def executable_hash(executable):
    return hashlib.sha256(os.path.normcase(os.path.normpath(executable)).replace('\\','/').encode()).hexdigest()


def probe_process(pid):
    import psutil
    try:
        process = psutil.Process(pid)
        birth = process.create_time()
        argv, executable = tuple(process.cmdline()), process.exe()
        if birth != process.create_time():
            raise WorkerIdentityChanged('PROCESS_CHANGED_DURING_PROBE')
        return ProcessRecord(pid, birth, argv, executable)
    except psutil.NoSuchProcess:
        return None
    except psutil.AccessDenied as error:
        raise ContinuationError('PROCESS_IDENTITY_UNREADABLE') from error


def discover_archive_workers():
    import psutil
    modules = {'src.research.calibration.openaq_archive',
               'src.research.calibration.model_archives', 'src.research.calibration.repair_archive'}
    records = []
    for process in psutil.process_iter(['pid', 'name']):
        if 'python' not in (process.info['name'] or '').lower():
            continue
        record = probe_process(process.pid)
        if record is None:
            continue
        if any(token in modules or Path(token).name in {'openaq_archive.py', 'model_archives.py', 'repair_archive.py'}
               for token in record.argv[1:]):
            records.append(record)
    return records


def scientific_fingerprint():
    from src.research.calibration.protocol import load
    protocol = load()
    paths = list((config.PROJECT_ROOT/'src/research/calibration').glob('*.py'))
    paths += [config.PROJECT_ROOT/'src/nationwide/aqi.py', config.PROJECT_ROOT/'requirements.txt',
              config.PROJECT_ROOT/'requirements-research.txt']
    files = {path.relative_to(config.PROJECT_ROOT).as_posix():
             hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for path in sorted(paths)}
    selection = config.PROJECT_ROOT/'results/research/data_manifests/station_selection.json'
    branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    if branch!='research/station-calibration':
        raise ContinuationError('RESEARCH_BRANCH_REQUIRED')
    return {'protocol_sha256': protocol['_sha256'], 'source_sha256': canonical_hash(files),'branch':branch,
            'runtime':{'python':platform.python_version(),'packages':{p:version(p) for p in
                ('numpy','pandas','scipy','scikit-learn','pyarrow','matplotlib','lightgbm','xgboost','PyYAML','psutil')}},
            'selection_sha256': canonical_hash(json.loads(selection.read_text(encoding='utf-8'))), 'files': files}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
    try:
        with temporary.open('x', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _now():
    return datetime.now(timezone.utc).isoformat()


def prepare_worker_manifest(path=None, *, probe=probe_process, fingerprint=scientific_fingerprint):
    """Capture only the authorized three identities; refuse reused or changed PIDs."""
    path = Path(path or OUT/'continuation_workers.json')
    if path.exists():
        raise ContinuationError('WORKER_MANIFEST_ALREADY_EXISTS_USE_A_NEW_VERSIONED_PATH')
    workers = []
    for pid, prefix in DEFAULT_PREFIXES.items():
        process = probe(pid)
        expected = Worker(pid, OBSERVED_BIRTHS[pid], prefix)
        if process is not None and not expected.matches(process):
            raise WorkerIdentityChanged('OBSERVED_WORKER_IDENTITY_CHANGED')
        workers.append(Worker(pid, process.create_time if process else None, prefix,
                              executable_hash(process.executable) if process else '').public())
    value = {'version': VERSION, 'prepared_at': _now(), 'workers': workers, 'fingerprint': fingerprint()}
    value['sha256'] = canonical_hash(value)
    # Exclusive creation prevents two preparations from silently replacing evidence.
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ContinuationError('WORKER_MANIFEST_ALREADY_EXISTS_USE_A_NEW_VERSIONED_PATH') from error
    return value


def read_worker_manifest(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if value.get('version') != VERSION or value.get('sha256') != canonical_hash({k:v for k,v in value.items() if k!='sha256'}):
        raise ContinuationError('WORKER_MANIFEST_IDENTITY_INVALID')
    workers = [Worker(w['pid'], w['create_time'], tuple(w['command_prefix']), w.get('executable_sha256', ''))
               for w in value['workers']]
    if len(workers) != 3 or {w.pid for w in workers} != set(DEFAULT_PREFIXES):
        raise ContinuationError('WORKER_MANIFEST_DOES_NOT_MATCH_AUTHORIZED_WORKERS')
    for worker in workers:
        if worker.command_prefix != DEFAULT_PREFIXES[worker.pid] or worker.create_time not in (None,OBSERVED_BIRTHS[worker.pid]):
            raise ContinuationError('WORKER_MANIFEST_DOES_NOT_MATCH_OBSERVED_IDENTITY')
    if any(w['create_time'] is None and w.get('prepared_state') != 'ALREADY_EXITED' for w in value['workers']):
        raise ContinuationError('EXITED_WORKER_EVIDENCE_MISSING')
    return value, workers


class ExclusiveLock:
    """OS mutex plus a PID/birth lease; stale takeover requires proof of death.

    The persistent one-byte guard prevents simultaneous stale-lease recovery.
    Releasing the JSON lease does not unlink the OS mutex inode/file.
    """
    def __init__(self, path, *, probe=probe_process, pid=None):
        self.path, self.probe, self.pid = Path(path), probe, pid or os.getpid()
        self.token, self.handle, self.lease = uuid.uuid4().hex, None, None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.with_name(self.path.name+'.guard').open('a+b')
        self.handle.seek(0, 2)
        if not self.handle.tell():
            self.handle.write(b'0')
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.handle.close()
            self.handle = None
            raise DuplicateHelper('ANOTHER_CONTINUATION_HELPER_HOLDS_THE_LOCK') from error
        try:
            if self.path.exists():
                existing = json.loads(self.path.read_text(encoding='utf-8'))
                owner = self.probe(existing['pid'])
                if owner is not None and abs(owner.create_time-existing['create_time']) < .00001:
                    raise DuplicateHelper('EXISTING_HELPER_LEASE_IS_STILL_ALIVE')
                if not isinstance(existing.get('create_time'), (int, float)) or not existing.get('token'):
                    raise ContinuationError('LOCK_DEATH_EVIDENCE_INVALID')
            current = self.probe(self.pid)
            if current is None:
                raise ContinuationError('HELPER_BIRTH_TIME_UNAVAILABLE')
            self.lease = {'pid': self.pid, 'create_time': current.create_time,
                          'token': self.token, 'created_at': _now()}
            atomic_json(self.path, self.lease)
            return self
        except BaseException:
            self._unlock()
            raise

    def _unlock(self):
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle, fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None

    def __exit__(self, *_):
        try:
            if self.lease is not None and self.path.exists():
                existing = json.loads(self.path.read_text(encoding='utf-8'))
                if existing.get('token') == self.token:
                    self.path.unlink()
        finally:
            self._unlock()


def audit_collections():
    """Inspect complete and partially saved files without requests or mutations."""
    from src.research.calibration import checkpoint, data, repair_archive
    selection = checkpoint.read_json(data.MANIFESTS/'station_selection.json')
    expected_stations = {str(s['location_id']) for s in selection['stations']}
    expected_weather = {f"{round(s['latitude'],1):+06.1f}_{round(s['longitude'],1):+07.1f}" for s in selection['stations']}
    if len(expected_weather) != EXPECTED_WEATHER_POINTS:
        raise ContinuationError('FROZEN_WEATHER_POINT_COUNT_CHANGED')
    stations, sources, checked = {}, {}, set()
    paths = [data.MANIFESTS/'openaq_hours_manifest.json', *sorted(data.MANIFESTS.glob('openaq_hours_manifest.shard*.json'))]
    for path in paths:
        if not path.exists():
            continue
        for key, entry in checkpoint.read_json(path).get('stations', {}).items():
            if entry.get('complete') or key not in stations:
                stations[key] = entry
            for pollutant, record in entry.get('sensors', {}).items():
                if record.get('file'):
                    sources[(key,pollutant)] = record
                    identity = (record['file'],record['sha256'])
                    if identity not in checked:
                        checkpoint.verify(record)
                        checked.add(identity)
    weather_path = data.MANIFESTS/'weather_archive_manifest.json'
    weather = checkpoint.read_json(weather_path) if weather_path.exists() else {}
    if weather and (weather.get('source') != 'OPEN_METEO_PREVIOUS_RUNS' or weather.get('lead') != 'previous_day2'
                    or weather.get('model') != 'gfs_seamless'):
        raise ContinuationError('WEATHER_ARCHIVE_PROVENANCE_CHANGED')
    for record in weather.get('files', {}).values():
        checkpoint.verify(record)
        checked.add((record['file'],record['sha256']))
    repair_path = data.MANIFESTS/'openaq_repairs.json'
    repairs = checkpoint.read_json(repair_path) if repair_path.exists() else {}
    pending = []
    for (station,pollutant), record in sources.items():
        if not any(request.get('warning') == 'page_limit_reached' for request in record.get('requests', [])):
            continue
        overlay = repairs.get('stations', {}).get(station, {}).get(pollutant, {})
        if overlay.get('status') in repair_archive.TERMINAL:
            if overlay.get('base_record_sha256') != canonical_hash(record):
                raise ContinuationError('REPAIR_BASE_IDENTITY_CHANGED')
            if overlay.get('override_sha256') != canonical_hash({k:v for k,v in overlay.items() if k!='override_sha256'}):
                raise ContinuationError('REPAIR_OVERRIDE_IDENTITY_INVALID')
            if overlay.get('replacement'):
                checkpoint.verify(overlay['replacement'])
        else:
            pending.append({'station_id': station, 'pollutant': pollutant,
                            'status': overlay.get('status','pending'),
                            'failed_check': overlay.get('last_failed_check')})
    complete = {k for k,v in stations.items() if v.get('complete')}
    return {'missing_openaq': sorted(expected_stations-complete, key=int),
            'missing_weather': sorted(expected_weather-set(weather.get('files', {}))),
            'pagination_pending': pending, 'expected_openaq_stations':len(expected_stations),
            'expected_weather_points':len(expected_weather), 'checksummed_files':len(checked), 'checksum_audit':'PASS'}


@dataclass
class Stages:
    audit: Callable
    merge: Callable
    openaq: Callable
    weather: Callable
    repair: Callable
    checkpoint: Callable
    measured: Callable
    preliminary: Callable
    reproduction: Callable
    prospective: Callable
    readiness: Callable
    paper: Callable
    figures: Callable | None = None
    report: Callable | None = None


def default_stages():
    from src.research.calibration import (openaq_archive, model_archives, repair_archive, checkpoint,
        measured, preliminary, reproducibility, prospective_audit, readiness, paper, figures, report)
    start = datetime(2025,2,1,tzinfo=timezone.utc)
    end = datetime(2026,10,8,tzinfo=timezone.utc)
    return Stages(audit_collections, openaq_archive.merge,
                  lambda: openaq_archive.run(start,end,per_minute=24),
                  model_archives.weather, lambda: repair_archive.run(per_minute=18),
                  checkpoint.capture, measured.build, preliminary.run,
                  reproducibility.audit, prospective_audit.audit, readiness.generate, paper.generate, figures.generate, report.generate)


def _transient(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in (408,429,500,502,503,504)
    return isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError))


def run(manifest_path=None, *, stages=None, probe=probe_process, discover=discover_archive_workers,
        fingerprint=scientific_fingerprint, sleeper=time.sleep, monotonic=time.monotonic,
        status_path=None, lock_path=None, max_download_rounds=3, poll_seconds=30,
        max_wait_seconds=48*3600, pid=None):
    """Execute once. Functions/probes are injected by tests; defaults touch real caches."""
    if not 1 <= max_download_rounds <= 5 or not 0 < poll_seconds <= 60 or max_wait_seconds <= 0:
        raise ContinuationError('INVALID_FINITE_RUN_BOUNDS')
    manifest_path = Path(manifest_path or OUT/'continuation_workers.json')
    status_path = Path(status_path or OUT/'continuation_status.json')
    lock_path = Path(lock_path or OUT/'continuation.lock')
    manifest, workers = read_worker_manifest(manifest_path)
    actions = stages
    state = {'version':VERSION,'started_at':_now(),'updated_at':_now(),'state':'STARTING',
             'worker_manifest_sha256':manifest['sha256'], 'fingerprint':manifest['fingerprint'],
             'worker_pids':[w.pid for w in workers], 'collection_finished':False,
             'measured_completed':False,'experiment_completed':False,
             'primary_experiment_completed':False,'CAMS_ARCHIVE_STATUS':'PENDING_MANUAL_ADS_CREDENTIAL',
             'stages':{},'failures':[]}

    def save():
        state['updated_at'] = _now()
        atomic_json(status_path,state)

    def frozen():
        if fingerprint() != manifest['fingerprint']:
            raise ContinuationError('FROZEN_PROTOCOL_OR_SCIENTIFIC_SOURCE_CHANGED')

    def no_new_workers():
        allowed = {w.pid:w for w in workers}
        unexpected = [p.pid for p in discover() if p.pid not in allowed or not allowed[p.pid].matches(p)]
        if unexpected:
            state['unexpected_archive_worker_pids'] = sorted(unexpected)
            raise ContinuationError('ADDITIONAL_ARCHIVE_WORKER_BLOCKS_RESUME')

    def step(name, action, attempts=1):
        stage = state['stages'][name] = {'state':'RUNNING','started_at':_now(),'attempts':0}
        save()
        for attempt in range(1,attempts+1):
            stage['attempts'] = attempt
            try:
                frozen()
                value = action()
                frozen()
                stage.update(state='COMPLETE',finished_at=_now())
                save()
                return True,value
            except (Exception,SystemExit) as error:
                failure = {'stage':name,'attempt':attempt,'at':_now(),'error_type':type(error).__name__}
                if isinstance(error,ContinuationError):
                    failure['code'] = error.code
                state['failures'].append(failure)
                stage.update(state='FAILED',finished_at=_now(),error_type=type(error).__name__,retryable=_transient(error))
                save()
                if isinstance(error,ContinuationError):
                    raise
                if attempt == attempts or not _transient(error):
                    return False,None
                stage['state'] = 'RETRYING'
                save()
                sleeper(min(60,10*attempt))
        return False,None

    with ExclusiveLock(lock_path,probe=probe,pid=pid):
        save()
        try:
            frozen()
            state['state'] = 'WAITING_INHERITED_WORKERS'
            save()
            began = monotonic()
            while True:
                alive = []
                for worker in workers:
                    if worker.create_time is None:
                        continue  # no birth time is synthesized for a process already absent at preparation
                    process = probe(worker.pid)
                    if process is not None:
                        if not worker.matches(process):
                            raise WorkerIdentityChanged('OBSERVED_WORKER_PID_REUSED_OR_COMMAND_CHANGED')
                        alive.append(worker.pid)
                state['inherited_worker_pids_still_alive'] = alive
                save()
                if not alive:
                    break
                if monotonic()-began >= max_wait_seconds:
                    raise ContinuationError('INHERITED_WORKER_WAIT_TIMEOUT')
                sleeper(poll_seconds)
            no_new_workers()
            state['state'] = 'COLLECTING'
            save()
            ok, audit = step('initial_checksum_audit',stages.audit if stages else audit_collections)
            if not ok:
                raise ContinuationError('INITIAL_CACHE_AUDIT_FAILED')
            actions = stages or default_stages()
            disabled_downloads = set()
            for round_number in range(1,max_download_rounds+1):
                no_new_workers()
                step(f'merge_before_resume_{round_number}',actions.merge)
                ok,audit = step(f'collection_audit_{round_number}',actions.audit)
                if not ok:
                    raise ContinuationError('COLLECTION_CACHE_AUDIT_FAILED')
                state['collection'] = audit
                save()
                if not audit['missing_openaq'] and not audit['missing_weather']:
                    break
                if audit['missing_openaq'] and 'openaq' not in disabled_downloads:
                    no_new_workers()
                    name = f'openaq_resume_{round_number}'
                    resumed,_ = step(name,actions.openaq,max_download_rounds)
                    if not resumed and not state['stages'][name].get('retryable'):
                        disabled_downloads.add('openaq')
                if audit['missing_weather'] and 'weather' not in disabled_downloads:
                    no_new_workers()
                    name = f'weather_resume_{round_number}'
                    resumed,_ = step(name,actions.weather,max_download_rounds)
                    if not resumed and not state['stages'][name].get('retryable'):
                        disabled_downloads.add('weather')
            no_new_workers()
            step('merge_completed_manifests',actions.merge)
            ok,audit = step('audit_before_pagination_repair',actions.audit)
            if not ok:
                raise ContinuationError('COLLECTION_CACHE_AUDIT_FAILED')
            for round_number in range(1,max_download_rounds+1):
                if not audit['pagination_pending']:
                    break
                no_new_workers()
                name = f'pagination_repair_{round_number}'
                repaired,_ = step(name,actions.repair,max_download_rounds)
                ok,audit = step(f'audit_pagination_repair_{round_number}',actions.audit)
                if not ok:
                    raise ContinuationError('PAGINATION_CACHE_AUDIT_FAILED')
                if any(item.get('failed_check') not in (None,'extra_page_request') for item in audit['pagination_pending']):
                    break  # metadata conflicts are not transient network failures
                if not repaired and not state['stages'][name].get('retryable'):
                    break
            state['collection'] = audit
            state['collection_finished'] = (audit['checksum_audit']=='PASS' and not any(
                audit[key] for key in ('missing_openaq','missing_weather','pagination_pending')))
            if not state['collection_finished']:
                state['failures'].append({'stage':'collection','at':_now(),'code':'COLLECTION_INCOMPLETE_AFTER_BOUNDED_RESUME'})
            no_new_workers()
            state['state'] = 'PROCESSING'
            save()
            ok,_ = step('checkpoint',actions.checkpoint)
            # Missing stations/points yield a labelled partial study. Unrepaired
            # truncation is a known target defect and cannot enter another fit.
            measured_ok, quality = step('measured_dataset',actions.measured) if ok and not audit['pagination_pending'] else (False,None)
            if measured_ok:
                quality = quality[1] if isinstance(quality,tuple) else quality
                state['measured_completed'] = bool(quality.get('dataset_hash'))
                state['dataset_hash'] = quality.get('dataset_hash')
                experiment_ok,result = step('preliminary_experiment',actions.preliminary)
                if experiment_ok:
                    if result.get('final_test_scored') is not False:
                        raise ContinuationError('PRELIMINARY_FINAL_TEST_ISOLATION_NOT_ESTABLISHED')
                    if result.get('dataset_hash') != quality.get('dataset_hash'):
                        raise ContinuationError('EXPERIMENT_DATASET_DOES_NOT_MATCH_MEASURED_DATASET')
                    state['experiment_completed'] = bool(result.get('run_id') and any(f.get('strict') for f in result.get('folds',[])))
                    state['preliminary_run_id'] = result.get('run_id')
                step('local_reproduction',actions.reproduction)
            else:
                experiment_ok = False
                state['stages']['measured_dataset'] = state['stages'].get('measured_dataset',
                    {'state':'SKIPPED','reason':'CHECKPOINT_FAILED_OR_PAGINATION_UNRESOLVED'})
            prospect_ok,_ = step('readonly_prospective_audit',actions.prospective,max_download_rounds)
            step('research_readiness',actions.readiness)
            if measured_ok and experiment_ok and prospect_ok:
                step('paper_skeleton',actions.paper)
            else:
                state['stages']['paper_skeleton'] = {'state':'SKIPPED','reason':'REQUIRED_ARTIFACT_STAGE_FAILED'}
            if experiment_ok and actions.figures is not None:
                step('preliminary_figures',actions.figures)
            failed = any(stage['state']=='FAILED' for stage in state['stages'].values())
            state['state'] = ('FINISHED' if state['collection_finished'] and state['measured_completed']
                              and state['experiment_completed'] and not failed else 'FINISHED_WITH_FAILURES')
        except (Exception,SystemExit) as error:
            failure = {'stage':'orchestration','at':_now(),'error_type':type(error).__name__}
            if isinstance(error,ContinuationError):
                failure['code'] = error.code
                state['state'] = 'BLOCKED'
            else:
                state['state'] = 'FAILED'
            state['failures'].append(failure)
        state['finished_at'] = _now()
        save()
        # Generate the checkpoint once from the saved terminal outcome. A report
        # failure is retained, but never triggers recursive report generation.
        if actions is not None and actions.report is not None:
            try:
                frozen()
                actions.report()
                state['stages']['checkpoint_report'] = {'state':'COMPLETE','finished_at':_now()}
            except (Exception,SystemExit) as error:
                failure = {'stage':'checkpoint_report','at':_now(),'error_type':type(error).__name__}
                if isinstance(error,ContinuationError):
                    failure['code'] = error.code
                state['failures'].append(failure)
                state['stages']['checkpoint_report'] = {'state':'FAILED','error_type':type(error).__name__}
                if state['state']=='FINISHED':
                    state['state']='FINISHED_WITH_FAILURES'
            save()
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare-worker-manifest','run'))
    parser.add_argument('--worker-manifest',type=Path,default=OUT/'continuation_workers.json')
    parser.add_argument('--max-download-rounds',type=int,default=3)
    parser.add_argument('--max-wait-hours',type=float,default=48)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare-worker-manifest':
            value = prepare_worker_manifest(args.worker_manifest)
            print(json.dumps({'state':'PREPARED','worker_pids':[w['pid'] for w in value['workers']],
                              'manifest_sha256':value['sha256']}))
            return 0
        value = run(args.worker_manifest,max_download_rounds=args.max_download_rounds,
                    max_wait_seconds=args.max_wait_hours*3600)
        print(json.dumps({k:value[k] for k in ('state','collection_finished','measured_completed','experiment_completed')}))
        return 0 if value['state']=='FINISHED' else 1
    except (Exception,SystemExit) as error:
        print(json.dumps({'state':'REFUSED','error_type':type(error).__name__,
                          'code':error.code if isinstance(error,ContinuationError) else 'CONTINUATION_START_FAILED'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
