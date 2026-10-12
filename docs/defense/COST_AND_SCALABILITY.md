# Cost and scalability defense

No commercial price or measured million-user capacity is asserted. Separate prototype, research and production budgets.

| Stage | Main resource | Cost/limit issue | Control |
| --- | --- | --- | --- |
| Prototype | Hosting/database + provider free tiers | Free does not mean unlimited, guaranteed or commercially licensed | Cache, quotas, scoped demo and clear attribution |
| Research | Archive downloads, local CPU/RAM/disk | Large dated forecasts and repeated fitting; ADS latency is a time cost | Minimum subset, immutable files, incremental jobs and train-only tuning |
| Production | Paid hosting/database/provider licences | Traffic, cold starts, DB contention, retention, support and egress | Batch by forecast grid, bounded storage, shared cache and monitored SLA |

[Open-Meteo](https://open-meteo.com/en/pricing) states that its free API is non-commercial, has limits and no uptime guarantee; commercial use needs a suitable licence. [OpenAQ](https://docs.openaq.org/using-the-api/rate-limits) currently lists general limits of 60 requests/minute and 2,000/hour per API key; read headers and terms rather than multiplying keys. AirGuard’s runtime budgets are intentionally smaller and shared across requests.

Ten users: shared cache and grid reuse reduce provider calls, subject to actual warm-state tests. Ten thousand users: precompute popular grid/time summaries, isolate provider queues, measure DB contention and use licensed capacities. One million users: no claim that the prototype supports this; require load tests, CDN strategy, partitioned storage, durable queues, capacity budgets and paid service planning.

Station calibration scales with station-day training rows, not individual users. CAMS acquisition scales with date × parameter × lead × grid cells. Per-user provider calls are the wrong national architecture. Outstanding cost risk: monitoring/support and mandatory commercial terms, not just model inference CPU.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
