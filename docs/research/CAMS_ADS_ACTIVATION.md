# ADS activation checkpoint — 12 October 2026

Continuation begins at `4212d05` on `research/station-calibration`. The user
reported completing the ADS manual setup. The official `cdsapi==0.7.7` imports
in `.venv-live`; the default system interpreter does not have this client.
Only the existence of the private credential file was checked. Its contents
were not inspected or displayed. The official client consumes credentials
internally with all provider/client output suppressed.

One request was submitted at 2026-10-12T06:33:00.939830Z to
`cams-global-atmospheric-composition-forecasts`: PM2.5, forecast, initialised
2025-02-18 00:00 UTC, lead 24 hours, GRIB, bounding box north/west/south/east
29.2/76.8/28.4/77.6. This is a small region with one parameter and one step,
entirely before the locked final test. ADS accepted the request and assigned a
job ID. Acceptance establishes successful submission, **not** retrieval or
verified operational metadata. The exact non-secret request, request ID and
timestamps are in `results/research/cams_ads_probe.json`.

Current archive state: **ADS_PROBE_SUBMITTED — provider queue pending**.
No full acquisition or primary fitting has started. No `MODEL_SELECTION_LOCK`
has been created. The measured dataset and locked protocol are unchanged;
no target table was read by the smoke request or its decoder checks.

The retrieval process resumes an existing submitted job by ID. It refuses to
resubmit failed or ambiguous attempts and checks the SHA256 before accepting
an existing file. Client logs, response bodies, download URLs, exception
messages and tracebacks are not written to evidence. Error records contain
only a fixed category, HTTP status and a terms-mentioned flag.

`eccodes==2.44.0` was installed in `.venv-live` and its native decoder self-check
passed. Dependencies are pinned separately in `requirements-ads.txt`.
No application rebuild or production deployment occurred.

Commands (do not run another download process while the original is active):

```powershell
.\.venv-live\Scripts\python.exe -m src.research.calibration.ads_probe --status
# After the active process finishes downloading:
.\.venv-live\Scripts\python.exe -m src.research.calibration.ads_probe --audit
# Only if the original process has exited before download completion:
.\.venv-live\Scripts\python.exe -m src.research.calibration.ads_probe
```

The audit checks actual GRIB forecast type, parameter, units, initialisation,
lead and valid time. Only a downloaded and audited file can release the smoke
gate. A complete archive still needs its own per-file/unit/availability audit.
Final-test dates 2026-07-10 through 2026-10-07 remain sealed. The next stage is
to derive and acquire the minimum development archive, complete development
evaluations and commit `MODEL_SELECTION_LOCK`; final evaluation requires the
user's separate explicit approval after that lock exists.

Validation: 592 passed, 5 skipped, 4 database cases excluded in the offline
suite. The new tests cover safe error handling, duplicate prevention, resume,
checksum corruption, analysis rejection and inconsistent time/unit metadata.

Official references: [ADS client setup](https://ads.atmosphere.copernicus.eu/how-to-api),
[forecast dataset](https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts),
[ECMWF ecCodes](https://github.com/ecmwf/eccodes-python).
