# Research continuation runbook

Run commands from the existing repository root on `research/station-calibration`.
Use the audited research interpreter, `.\.venv-live\Scripts\python.exe`.
This workflow does not switch
branches, reset Git, rebuild the application, deploy a correction model or
create a recurring scheduler.

## Environment and frozen evidence

`requirements-research.txt` includes the pinned application requirements plus
`PyYAML==6.0.3` and `psutil==7.2.2`. For a separately prepared research environment,
install with `python -m pip install -r requirements-research.txt`. Do not change
packages while a prepared continuation is running. The current audited
environment is reused; this runbook performs no installation.

The inherited v3.1 protocol is `docs/research/research_protocol.yaml`; its hash
and version history are in `results/research/protocol_lock.json`. The loader
refuses a mismatched protocol. Do not relock or edit it to make a run pass.
The finite helper also freezes normalized scientific source hashes, canonical
station-selection metadata, the research branch, and Python/package versions
at preparation. It rechecks this fingerprint before and after stages, including
before fitting. Generated readiness/report JSON changes do not change this
source fingerprint. A genuine pre-fitting defect needs a documented versioned
amendment, preserving previous hashes and results.

## One finite acquisition continuation

Prepare only after scientific source and the environment are stable, then run:

```powershell
.\.venv-live\Scripts\python.exe -m src.research.calibration.continuation prepare-worker-manifest
.\.venv-live\Scripts\python.exe -m src.research.calibration.continuation run
```

Preparation writes an immutable `results/research/continuation_workers.json`.
It captures the exact observed OpenAQ PIDs 33748/12384 and weather PID 36128,
their birth timestamps, permitted module prefixes and executable identity
hashes. An already absent worker is recorded as exited without inventing a
birth identity. A changed or reused PID is refused. The helper waits for those
exact workers; additional archive workers block resumption. Do not launch
parallel archive jobs alongside it. The PID/birth lease and OS lock prevent
two helpers from duplicating work; recovery requires evidence the owner died.

Defaults are one finite run, at most three bounded download rounds and a
48-hour inherited-worker wait. Optional flags are `--max-download-rounds`,
`--max-wait-hours` and `--worker-manifest`. An existing preparation is never
overwritten; after an intentional reviewed source change, use a new versioned
manifest path for both commands rather than bypassing its fingerprint.

The helper verifies manifests and checksums, merges inherited manifests,
resumes only incomplete selected OpenAQ stations/missing weather points,
and repairs only flagged pagination truncations. It then builds measured
data, evaluates the non-CAMS preliminary study, reconstructs sampled stations
from raw caches, audits prospective logging, and generates readiness, paper,
figures and the final checkpoint. Unresolved pagination defects prevent a new
fit. Other incomplete acquisition can yield an explicitly partial study.
Failures are retained; `collection_finished`, `measured_completed` and
`experiment_completed` are separate fields in the atomic
`results/research/continuation_status.json`. The primary CAMS completion flag
remains false. Process command lines and exception text are not logged.

## Research-only local commands

These commands regenerate local evidence; none issues production forecasts.
Use them only after relevant acquisition/repair stages are safe to inspect.

| Module after `.\.venv-live\Scripts\python.exe -m` | Purpose / principal artifact |
| --- | --- |
| `src.research.calibration.protocol show` | Inspect the existing locked protocol identity |
| `src.research.calibration.checkpoint` | Verify caches; `results/research/recovery_checkpoint.json` |
| `src.research.calibration.measured` | Measured targets, rejection ledger and issue-time features; `results/research/measured_dataset.json` |
| `src.research.calibration.preliminary` | Frozen `NON_CAMS_PRELIMINARY` study; `results/research/preliminary/<run_id>/results.json` and latest pointer |
| `src.research.calibration.reproducibility` | Local raw-cache reconstruction; `results/research/dataset_reproducibility.json` |
| `src.research.calibration.prospective_audit` | Read-only database audit; local `results/research/prospective_audit.json` and immutable audit copies |
| `src.research.calibration.validation --snapshot` | Offline tests and source-bound evidence; `results/research/test_validation.json`, snapshots and `logs/research_validation_*` |
| `src.research.calibration.readiness` | Evidence-derived `results/research/research_readiness.json` |
| `src.research.calibration.paper` | Exact-result paper skeleton; `paper/station_calibration_skeleton.tex` and `results/research/paper_skeleton.json` |
| `src.research.calibration.figures` | Diagnostics and file hashes under the immutable experiment directory |
| `src.research.calibration.report` | `results/research/continuation_checkpoint.json` and `docs/research/CONTINUATION_CHECKPOINT.md` |

Raw/partial caches live under `data/research/`; source manifests are under
`results/research/data_manifests/`. Derived versioned tables, inputs and quality
reports are under `data/research/derived/`. Never replace rejected targets with
silent deletions. Preserve v3.1 zero/stuck-sensor exclusions, retained spike and
PM2.5>PM10 flags, and censored Severe diagnostics; do not fit or score exact
regression error against a fabricated Severe value.

## Scientific boundaries

The final 90 days, **2026-07-10 through 2026-10-07**, are sealed for model
selection and excluded from preliminary fitting/evaluation. Descriptive QC
counts can include those dates; they cannot drive station selection, feature,
hyperparameter or advisory choices. Training-window eligibility is separate
from descriptive full-window eligibility. Current acquisition counts may grow
after an experiment; always cite its immutable result artifact, dataset hash,
data/feature/protocol versions and plan hash, not the latest acquisition totals.

Stream A is genuine prospective operational issuance. Preserve each issued
forecast and issue-time snapshot unchanged, including model/feature/protocol
versions and recorded Git SHA. Pair only real matching station/date outcomes;
do not backdate forecasts or reconstruct absent issuance metadata. The audit
reads production records and writes local evidence only. Thirty real elapsed
days and thirty actual verified target days are both required for that gate.

Stream B is historical measured research. Strict preliminary predictors are
weather with the documented previous-runs availability bound, calendar and
coordinates. Measured-history/persistence sensitivities assume feed latency;
historical publication timestamps are unavailable. Fire predictors are
withheld. These results are not archived raw-CAMS comparisons and do not
complete primary research gates. See [CONTINUATION_CONTRACT.md](CONTINUATION_CONTRACT.md).

## Genuine CAMS archive integration

`CAMS_ARCHIVE_STATUS=PENDING_MANUAL_ADS_CREDENTIAL`. Follow
[ADS_MANUAL_SETUP.md](ADS_MANUAL_SETUP.md): accept dataset terms and configure
the private ADS token outside the repository. No token is needed in chat.
Preserve the inherited CAMS proxy cache with its label; reanalysis or current
historical fields cannot substitute for operational forecast runs.

Credentials alone do not release the experiment. A future importer must supply
versioned raw forecast files with checksums, exact ADS request provenance,
decoded initialization/leads/valid times/variables, and documented availability
by 20:00 IST. The unit audit must bind decoded units and verified conversion
descriptions to those exact file hashes, with same-run pressure/temperature
where needed. `primary.require_operational_archive` checks this evidence;
`guard_primary_row` additionally checks row availability and pre-issue frozen
pollutant support. The guard is infrastructure, not an implemented ADS importer.
Resolve the support-policy difference transparently before primary fitting,
then compare Raw CAMS, Direct ML and residual models on identical windows.
Do not alter the sealed final dates or inspect final scores during integration.
