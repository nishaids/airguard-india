# Project gap audit

Checkpoint: 20 October 2026 (IST), branch `research/station-calibration`. Supersedes the 13 October text, preserved in git history. Final test remains sealed.

Research readiness: 5/17, `COLLECTING_NOT_RESEARCH_READY`. The six-page paper is preserved and the app has production-safe provenance infrastructure. Scientific completion is not established by software tests or paper formatting.

| Area | Current evidence | Remaining gap |
| --- | --- | --- |
| Paper | Six-page SHA-protected snapshot; assets/citations present. | Author submission decisions. |
| CAMS | 10 verified chunks, 2 running; acquisition re-authorised 2026-10-20. | 26 files; first eligible fold needs 10 more. |
| Primary models | Runner/guards tested; no eligible real fold. | Real development comparisons and lock. |
| Extensions | Original valid independent outputs reused; floor surrogate excluded. | Primary replication; no selected correction. |
| Prospective | 108 fixed-time forecasts, 9 target days, 2 verified days, no violations; live track record gated by sample size. | Real elapsed days and outcomes. |
| Software | 681 Python tests, 44 frontend tests, lint, types and build pass; 20 October release verified (31 staged, 37 public checks). | None for this release. |
| Security | Zero configured-secret hits, all DB tables RLS. | No claim of penetration testing or unknown-secret detection. |
