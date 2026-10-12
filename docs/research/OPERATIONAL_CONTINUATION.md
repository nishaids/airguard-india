# Operational continuation checkpoint

The locked v3.1 protocol and measured dataset are preserved. This continuation
uses the existing ADS IDs and versioned acquisition plan. No new probe is needed.
The plan contains development dates only. Keep 2026-07-10 through 2026-10-07 sealed.

## Resume without duplicate requests

First check for a running `src.research.calibration.cams_acquisition` process.
The Windows launcher and its child are one worker, not two independent workers.
Do not launch a second worker. The existing OS file lease also prevents overlap.

```powershell
python -m src.research.calibration.cams_acquisition --poll-only
# Only when no worker is running:
python -m src.research.calibration.cams_acquisition --worker-hours 24
```

New requests are sequential. Previously concurrent requests are allowed to
finish under their original IDs. Any unresolved failure blocks new submission;
an ambiguous submission is never automatically repeated. A terminal ADS failure
needs review before the user's permitted one replacement attempt. A download
failure should recover the existing remote ID, not create a replacement request.
Never print credentials, transport diagnostics, or the contents of `.cdsapirc`.

## Derive available paired months

```powershell
python -m src.research.calibration.cams_baseline
python -m src.research.calibration.primary_dataset
python -m scripts.audit_development_readiness
```

The first step verifies checksums and the complete parameter/date/lead cube.
Each month needs both its surface and model-level chunks. It generates raw
three-species and six-species CPCB-style indices and diurnal descriptors.
The second step uses Arrow date filtering before materialising measured outcomes.
Rejected targets remain in the join. Exact-history lags exclude censored labels;
censored-history flags remain available. Neighbour donors obey the measurement
cutoff and can be restricted explicitly for spatial holdouts.

The actual ADS global grid is **0.4 degrees**, also specified by the
[official dataset](https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts).
No 0.1-degree information is manufactured. Units, hybrid coefficients, producing
run, leads and valid times are checked against each downloaded GRIB.

## What remains before primary fitting

- Complete paired archive coverage and enough protocol-eligible training history.
- Finish the cutoff-aligned CAMS rolling-bias descriptor. The frozen cube starts
  at lead 11h (surface) / 9h (model level). A rolling window ending at 17:00 IST
  on D-1, reconstructed from the D-2 run with seven preceding gas-support bins,
  starts at lead 4.5h. This needs an audited minimal supplementary-lead plan;
  do not extrapolate the current cube or silently substitute a daily CAMS index.
  No supplementary request was submitted in this continuation.
- Integrate the primary train-only tuning, temporal/spatial runner and its donor
  masking, ablations, calibration, advisories and statistical comparisons.
- Treat missing historical FIRMS publication evidence explicitly; acquisition
  timestamps alone do not establish pre-issue availability.
- Bind all completed experiment outputs to a genuine model-selection lock and
  implement/audit the one-shot final executor. The current readiness script is
  deliberately fail-closed and is not a final-test execution path.

The first 90-day training fold cannot meet 120 valid days per station. Preserve
that insufficient fold rather than lowering the threshold or selecting stations
using later outcomes. Current partial pairs cannot support any eligible fold.
The old YAML proxy disclosure remains historical text under its original hash;
the separately frozen ADS manifest supplies the actual operational provenance.
Nominal forecast publication and assumed healthy-feed latency are limitations,
not empirical delivery logs. Do not claim absolute proof of historical access
absence from process artifacts alone.

## Paper and release boundary

The journal draft uses `paper/journal/main.tex`, IEEEtran journal mode, seven
section files, and `paper/references.bib`. The already-open standalone source
remains editable in place. Generation uses:

```powershell
python -m scripts.build_manuscript_package
python -m scripts.journal_evidence_figures
python -m scripts.prepare_journal_draft
```

Compile `main.tex` from `paper/journal` with the recorded Tectonic toolchain.
Figures explicitly distinguish NON_CAMS_PRELIMINARY results from planned primary
experiments. Missing primary predictions cannot produce error-distribution plots.
The six-page development draft is not submission-ready or a selected-model paper.

The existing production deployment is independently verified. Research modules,
raw data, credentials and manuscript artifacts are excluded from its upload.
No learned correction or unvalidated interval has been promoted.
