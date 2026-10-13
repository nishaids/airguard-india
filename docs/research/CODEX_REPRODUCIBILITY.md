# Continuation reproducibility

Checkpoint: 2026-10-13T20:05:39.026617+00:00. Research branch; code checkpoint `106c33eafac531a04dae99f19ec0005ae808ff6a`. Final test remains sealed.

Use the existing `.venv-live` runtime. Immutable extension metadata records Python 3.10.6, NumPy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2, LightGBM 4.7.0, PyArrow 23.0.1 and SciPy 1.15.3. Seeds are 42; full primary runtime/search grids are in each plan.json.

```powershell
python -m src.research.calibration.validation --snapshot
python -m src.research.calibration.prospective_audit
python -m scripts.audit_database_release
python -m scripts.audit_secret_history
python -m src.research.calibration.readiness
python -m src.research.calibration.cams_baseline
python -m src.research.calibration.primary_dataset
python -m src.research.calibration.primary_experiments --run-development
python -m scripts.audit_development_readiness
python -m scripts.finish_codex_handoff
```

The CAMS baseline and join are idempotent and development-filtered. Do not rerun measured-data acquisition or target construction during continuation. Use its existing semantic hash and sealed table. The primary runner filters dates before materialisation and reports insufficient folds instead of fitting shortened windows. Spatial, ablation, uncertainty, warning and statistics stages share its configuration when coverage is sufficient.

Existing extension v1 outputs are reused with their audited exclusion; do not execute the recovered v1 source as an approved method. The v2 extension code excludes censored fitting but is not rerun here. Full future v2 analyses remain exploratory; neither version can replace the primary model-selection protocol. The historical paper analysis/reproduction sources and exact hashes are preserved in `paper/conference_final/evidence/`. Do not regenerate the submission snapshot.

Raw CAMS/measured caches and extension prediction tables remain local unless packaged as explicit paper evidence. Missing data require the manifested acquisition, never undocumented edits. Source-bound tests and checksums do not constitute a complete clean-clone primary experiment reproduction.
