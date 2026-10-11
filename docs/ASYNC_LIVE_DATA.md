# Live data on uncached locations

The public summary/current/tomorrow/context endpoints return HTTP 202 on a
cache miss, with `QUEUED` or `IN_PROGRESS`, a five-second retry suggestion and
no AQI values. HTTP 202 responses are never cached at the CDN. The frontend
keeps its existing loading placeholders and polls at most 24 times. A failed
background fetch returns an honest HTTP 503 rather than historical data.

Supabase `airguard.enqueue_summary` atomically leases a job in the private
cache table for 360 seconds. Concurrent misses enqueue one request. `pg_net`
sends the request after commit to the fixed production internal endpoint.
The bearer secret is read only inside PostgreSQL from Vault; it is never
returned to the browser or placed in job bodies. A per-job UUID and bounded
coordinates are checked by the authenticated worker. Expired or unowned jobs
cannot fetch providers. The worker uses the same validated ingestion,
provenance, freshness, quota and immutable forecast logic as scheduled jobs.

Each request and provider thread reuses its own SSL connection for its bounded
scope. Every SQL operation remains a separate transaction; errors roll back.
The connection closes at scope exit, including exceptional exits. Connections
are never shared across threads and no application connection pool persists.

The hourly/fixed-time research schedules still use their existing empty
authenticated job body. Public `view` selectors cannot invoke private jobs.
The additive migration is mirrored under `db/migrations` and
`supabase/migrations`. Queue dispatch functions are unavailable to `anon` and
`authenticated`, and cache tables remain under default-deny RLS.

Supabase advisors report the intentional absence of public RLS policies and
unused indexes on new research tables. `pg_net` is non-relocatable in this
project; its extension metadata remains in `public`, with networking functions
in `net`. No destructive extension move or index removal was performed.
