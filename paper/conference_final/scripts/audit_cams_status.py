"""Read-only audit of the operational CAMS extension.

Re-hashes the GRIB files present on disk and compares them with the committed
acquisition manifest. It never contacts ADS, never submits or polls a request,
and never opens a measured target. Output: evidence/cams_status.json.
"""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'paper' / 'conference_final' / 'evidence' / 'cams_status.json'
RESEARCH = ROOT / 'results' / 'research'


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    manifest = json.loads((RESEARCH / 'cams_development_acquisition.json').read_text())
    plan = json.loads((RESEARCH / 'cams_development_acquisition_plan.json').read_text())
    planned = plan.get('jobs') or plan.get('chunks') or []
    readiness = json.loads((RESEARCH / 'final_test_readiness.json').read_text())
    alignment = json.loads((RESEARCH / 'cams_development_alignment.json').read_text())
    baseline = json.loads((RESEARCH / 'cams_raw_baseline_derivation.json').read_text())
    probe = json.loads((RESEARCH / 'cams_ads_probe.json').read_text())
    files = []
    for key, job in manifest['jobs'].items():
        entry = {'job': key[:12], 'status': job.get('status'), 'request_id_present': bool(job.get('request_id')),
                 'manifest_sha256': job.get('sha256'), 'bytes': job.get('bytes'), 'messages': job.get('messages'),
                 'grid': job.get('grid'), 'lead_hours': [min(job['lead_hours']), max(job['lead_hours'])] if job.get('lead_hours') else None,
                 'reference_dates': [min(job['reference_dates']), max(job['reference_dates'])] if job.get('reference_dates') else None,
                 'variables': (job.get('request') or {}).get('variable'), 'times': (job.get('request') or {}).get('time'),
                 'levels': (job.get('request') or {}).get('model_level') or (job.get('request') or {}).get('pressure_level'),
                 'parameter_units': job.get('parameter_units')}
        path = ROOT / job['file'] if job.get('file') else None
        candidates = [path, Path(str(path) + '.grib')] if path else []
        found = next((p for p in candidates if p and p.exists()), None)
        entry['on_disk'] = bool(found)
        if found:
            entry['disk_sha256'] = sha256(found)
            entry['disk_bytes'] = found.stat().st_size
            entry['hash_matches_manifest'] = entry['disk_sha256'] == job.get('sha256')
        files.append(entry)
    counts = collections.Counter(f['status'] for f in files)
    verified = [f for f in files if f['status'] == 'VERIFIED_GRIB']
    status = {'audit': 'read-only; no ADS contact, no request submitted, no measured target opened',
              'dataset': manifest['dataset'], 'plan_sha256': manifest['plan_sha256'],
              'planned_chunks': readiness['required_chunks'], 'planned_jobs_in_plan_file': len(planned),
              'manifest_checked_at_utc': manifest['checked_at_utc'], 'job_status_counts': dict(counts),
              'verified_chunks': len(verified),
              'verified_chunks_rehashed_and_matching': sum(bool(f.get('hash_matches_manifest')) for f in verified),
              'failed_jobs': counts.get('RETRIEVAL_OR_VALIDATION_FAILED', 0),
              'manifest_complete': manifest['complete'], 'files': files,
              'probe': {k: probe.get(k) for k in ('status', 'reference_time_utc', 'lead_hours', 'valid_time_utc', 'bytes', 'sha256', 'verification_scope')},
              'raw_baseline': {k: baseline.get(k) for k in ('status', 'rows', 'stations', 'dates', 'date_range', 'measured_targets_read', 'evaluation_performed')},
              'alignment': {k: alignment.get(k) for k in ('status', 'rows', 'stations', 'cities', 'dates', 'valid_targets', 'rejected_targets_retained',
                                                         'censored_severe_retained', 'reader_filter', 'model_fitting_performed',
                                                         'complete_primary_feature_dataset', 'remaining_features',
                                                         'per_run_publication_empirically_verified')},
              'eligible_rolling_folds': sum(1 for f in readiness['fold_coverage'] if f.get('eligible_training_stations', 0) > 0
                                            and f.get('archive_dates_in_test_window', 0) > 0),
              'readiness': {'status': readiness['status'], 'blockers': readiness['blockers'],
                            'model_selection_complete': readiness['model_selection_complete'],
                            'final_test_interval': readiness['final_test_interval']},
              'cams_correction_evaluated': False, 'final_test_accessed': False}
    OUT.write_text(json.dumps(status, indent=1), encoding='utf-8')
    print(json.dumps({k: status[k] for k in ('planned_chunks', 'job_status_counts', 'verified_chunks',
                                             'verified_chunks_rehashed_and_matching', 'failed_jobs', 'eligible_rolling_folds')}, indent=1))
    for f in files:
        print(f['job'], f['status'], f['on_disk'], f.get('hash_matches_manifest'), f['reference_dates'], f['lead_hours'], f['grid'], str(f['variables'])[:90])


if __name__ == '__main__':
    main()
