# Thirty practical scenarios

| Scenario | Expected AirGuard behaviour |
| --- | --- |
| Parent planning outdoor exercise | Select place and tomorrow; show category/provenance; no medical clearance |
| School sports planning | Compare periods and prepare an indoor option under applicable policy |
| Outdoor shift preparation | Show regional forecast and feasible timing context, not employer guarantees |
| Morning versus evening commute | Compare complete relative exposure windows, not street-route safety |
| Traveller entering another city | Search coordinates; raw-grid fallback works without local calibration claim |
| High pollution forecast tomorrow | Display category and explicit source; disclose uncertainty validation status |
| City without monitor | Display modelled fallback and absent measured evidence |
| Unreliable monitoring station | Freshness/QC prevents stale station being presented as fresh truth |
| CAMS available, station absent | Keep a modelled estimate; no station correction claim |
| Station available, CAMS absent | Measured current context can remain; tomorrow may be withheld |
| All sources down | Show unavailable state, not an invented clean-air value |
| Location permission denied | Manual search/coordinates remain available |
| Coordinates outside service region | Reject input before provider call |
| PIN code unmatched | Show honest empty search; do not guess a city |
| Share forecast with another person | URL carries selected location; warn that it reveals place of interest |
| Sensitive cohort selected | Guidance changes locally; no clinical risk probability |
| Hourly pollutant missing | Keep gaps; do not fill zero and call it clean air |
| Two-hour period lacks common pollutants | Do not rank an incomplete relative exposure window |
| Prospective score not yet available | Show no eligible pairs; historical scores are separate |
| Severe observation recorded | Retain >=401 censoring and report under-warning |
| Policy slider used | Recalculate assumed concentrations; label non-causal scenario |
| Weather outage | AQ forecast may display while weather context is unavailable |
| Satellite fire context missing | Core AQ display remains, no source attribution inferred |
| Stale cache during provider failure | Show age-qualified stale state only within allowed boundary |
| IST midnight crossed | Invalidate day cache/in-flight result; recompute target date |
| Previously unseen station | Use only a validated support rule; fall back to raw grid |
| Very wide research interval | Disclose width and conditional calibration limits; no guarantee of safety |
| Malformed provider payload | Reject at adapter/browser boundary with retry state |
| Researcher reproduces target table | Use checked raw caches and locked code/protocol; no new targets invented |
| Investor asks national scaling | Discuss caches/licences/load testing; no million-user benchmark claimed |


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
