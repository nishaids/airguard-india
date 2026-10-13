# CAMS operational archive status

Checkpoint: 2026-10-13T19:16:03.423817+00:00. Research branch; code checkpoint `9ac8b5a607246ced7150bfa47591c3398d72b5d8`. Final test remains sealed.

Current manifest: **7/36 verified**, statuses `{'VERIFIED_GRIB': 7, 'running': 1}`. The existing sequential worker retains original request IDs; no duplicate probe or archive request was submitted by this handoff. Frozen plan SHA-256: `952325f75dfc11e773dda90cbfe4ec4e883cda045a30d03c17578980ababeb6a`.

The readiness audit independently rehashed and decoded each verified GRIB. Forecast type, reference time, leads, valid times, fields, mass units, hybrid coefficients and the 0.4-degree grid are checked. Only paired surface/model-level months enter station extraction. Reanalysis and missing-month substitution are prohibited.

Current join: 12,960 retained station-days, 180 stations, 100 cities, 72 dates, 8,484 exact targets and 3 censored Severe targets; 4,473 rejected targets remain visible. Availability violations: 0.

Evidence: `results/research/final_test_readiness.json`, `cams_station_join_manifest.json`, and the existing acquisition/alignment manifests. Existing worker status must be inspected before any future launch; only resume when no worker owns the lease. Transport-only re-poll recovery preserves the existing remote ID.
