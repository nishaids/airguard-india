"""Read artifact metadata only; never load targets or execute final evaluation.

A BLOCKED report is not a model-selection lock. All required experiment
artifacts must exist and be hash-bound before human final-test authorization.
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from src.research.calibration.protocol import load
from src.research.calibration.checkpoint import write_json
from src.research.calibration.cams_acquisition import sha, validate_file

ROOT=Path(__file__).resolve().parents[1]
REQUIRED=('baselines','rolling_origin','spatial_validation','severity','ablation',
          'uncertainty','advisory','statistical_comparison','reproducibility')


def read(relative):
    path=ROOT/relative
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def audit():
    protocol=load()
    state=read('results/research/cams_development_acquisition.json')
    plan=read('results/research/cams_development_acquisition_plan.v2.json')
    alignment=read('results/research/cams_development_alignment.json')
    measured=read('results/research/measured_dataset.json')
    raw=[]
    for job in plan['jobs']:
        entry=state['jobs'].get(job['id'],{})
        if entry.get('status')!='VERIFIED_GRIB': continue
        path=ROOT/entry['file']
        if sha(path)!=entry['sha256']: raise ValueError('Acquired CAMS checksum mismatch')
        decoded=validate_file(path,job)
        raw.append({'job_sha256':job['id'],'file':entry['file'],'sha256':entry['sha256'],
                    'bytes':path.stat().st_size,'messages':decoded['messages'],
                    'grid_degrees':decoded['grid']['iDirectionIncrementInDegrees']})
    if state['plan_sha256']!=plan['sha256']: raise ValueError('Acquisition plan mismatch')
    if alignment and sha(ROOT/alignment['table'])!=alignment['sha256']:
        raise ValueError('Alignment checksum mismatch')
    blockers=[]
    if len(raw)!=len(plan['jobs']): blockers.append(f'Operational archive incomplete: {len(raw)}/{len(plan["jobs"])} verified chunks')
    if not alignment.get('complete_primary_feature_dataset'): blockers.append('Primary feature integration remains incomplete')
    eligible=[f for f in alignment.get('fold_coverage',[]) if f['eligible_training_stations'] and f['archive_dates_in_test_window']]
    if not eligible: blockers.append('No protocol-eligible rolling fold with acquired validation dates')
    results=read('results/research/primary_development_results.json')
    for name in REQUIRED:
        record=results.get('experiments',{}).get(name,{})
        if record.get('status')!='COMPLETE':
            blockers.append('Primary experiment pending: '+name)
    lock=ROOT/'paper/journal/MODEL_SELECTION_LOCK.md'
    committed=False
    if lock.exists():
        committed=subprocess.run(['git','ls-files','--error-unmatch',str(lock.relative_to(ROOT))],cwd=ROOT,capture_output=True).returncode==0
        committed=committed and subprocess.run(['git','diff','--quiet','HEAD','--',str(lock.relative_to(ROOT))],cwd=ROOT).returncode==0
    if not committed: blockers.append('MODEL_SELECTION_LOCK is absent or uncommitted')
    # Completion booleans cannot authorize a final run. Until a dedicated
    # experiment/lock binding validator exists, fail closed even on forged flags.
    blockers.append('Final executor and complete experiment-to-lock hash binding audit not yet implemented')
    report={'status':'BLOCKED','generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'protocol_sha256':protocol['_sha256'],'protocol_version':protocol['protocol_version'],
        'measured_semantic_sha256':measured['dataset_hash'],
        'measured_file_sha256':sha(ROOT/measured['table']),
        'cams_plan_sha256':plan['sha256'],'verified_chunks':len(raw),'required_chunks':len(plan['jobs']),
        'verified_files':raw,'alignment_sha256':alignment.get('sha256'),
        'alignment_rows':alignment.get('rows'),'development_dates':alignment.get('dates'),
        'fold_coverage':alignment.get('fold_coverage',[]),'blockers':blockers,
        'final_test_interval':['2026-07-10','2026-10-07'],'final_test_accessed_by_this_audit':False,
        'target_files_materialised_by_this_audit':False,'historical_access_claim':'Current reader and test evidence; not a forensic proof of every prior process',
        'approval_required':'Fresh explicit user authorization only after committed selection lock and READY report',
        'locked_protocol_changed':False,'model_selection_complete':False}
    write_json(ROOT/'results/research/final_test_readiness.json',report)
    text='# Final-test readiness: BLOCKED\n\nGenerated '+report['generated_at_utc']+'\n\n'
    text+='\n'.join('- '+b for b in blockers)+'\n\n'
    text+='Final interval: **2026-07-10 through 2026-10-07**. This audit reads metadata and hashes file bytes; it does not materialise or score target rows. '
    text+='The development reader filters dates before materialisation. Historical absence of access is not independently provable from artifacts alone.\n\n'
    text+='No selection lock is fabricated. Fresh explicit approval is required after a real committed lock and a READY report. '
    text+='No approval to score is requested at this blocked checkpoint.\n\n'
    text+='Protocol SHA256: `'+report['protocol_sha256']+'`\n\nMeasured semantic SHA256: `'+report['measured_semantic_sha256']+'`\n'
    (ROOT/'FINAL_TEST_READINESS_REPORT.md').write_text(text,encoding='utf-8')
    print(json.dumps({'status':report['status'],'verified_chunks':len(raw),'development_dates':report['development_dates'],'blockers':len(blockers)}))
    return report


if __name__=='__main__': audit()
