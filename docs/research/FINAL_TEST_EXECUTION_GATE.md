# Final-test execution gate

The latest attached “ONE MASTER EXECUTION PROMPT” explicitly requires
**fresh user approval after a committed MODEL_SELECTION_LOCK and a READY
FINAL_TEST_READINESS_REPORT.md**, before any final labels are opened or scored.
This supersedes the previous conditional one-evaluation authorization.
Production-safe website deployment and an evidence-backed manuscript draft
are now authorized; experimental correction deployment remains prohibited.

The locked period remains **2026-07-10 through 2026-10-07**. The v3.1 YAML,
its hash, the completed measured table and previous result artifacts are
unchanged. The current CAMS acquisition plan contains development runs only.

Before any final labels are materialised or scored, require:

- Full development CAMS cube, per-file hashes, decoded run/lead/valid times,
  units, gas conversions, spatial matching and availability audit.
- All declared development comparisons/validation/calibration analyses,
  reporting insufficient folds/groups explicitly and retaining failures.
- A selection artifact binding the learner/formulation, exact features,
  preprocessing, parameters, training range, forecast/support policy,
  uncertainty/advisory configuration and dependency versions.
- Measured semantic dataset hash, CAMS manifest hash, protocol hash, source
  Git SHA and result hashes in MODEL_SELECTION_LOCK.
- Git evidence that this exact lock is committed, plus final-isolation tests
  and absence of prior final tuning/evaluation.
- An exclusive one-shot execution reservation that refuses a second run or
  automatic retry after an ambiguous interruption.

After evaluation, preserve the result even if poor. Do not switch learners,
retune, change features, recalibrate thresholds or intervals, or conceal
negative findings. Any future improvement belongs to a new study/version and
fresh held-out evidence. The final test is **not executable at the current
checkpoint**, because the full archive/development selection are incomplete.
