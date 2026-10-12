# Demo backup and controlled failures

A provider outage should change the demonstration, not the truth of the numbers. Label all recorded screenshots/research artifacts as historical. Do not rewrite frontend live values or load synthetic fault fixtures as if they are current observations.

| What to click | What appears | What to say | Technical concept | Likely question | Answer |
| --- | --- | --- | --- | --- | --- |
| Deny geolocation | Manual search remains | Permission denial does not block place search. | Graceful location fallback | Do you track me automatically? | Geolocation starts only after a user action. |
| Enter invalid coordinates via search | Validation error | Invalid inputs do not become forced nearest-city predictions. | Input boundary | What if NaN? | Rejected before provider use. |
| DevTools offline, then refresh in a controlled local demo | Unavailable/retry state | No substitute clean-air number is shown. | Network failure | Does caching hide outage? | Source/age bounds still apply. |
| Open ONE_PAGE_RESULTS.md or stored screenshot | Clearly historical checkpoint | This is a recorded research artifact, not live conditions. | Backup provenance | Why not fake a successful live result? | That would mislead users and invalidate evidence. |
| Open JURY_QA.md and FAILURE_MATRIX.md | Failure/recovery explanations | We distinguish upstream failure from forecast error. | Operational honesty | What remains blocked? | Read the current acquisition manifest and checkpoint report. |


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
