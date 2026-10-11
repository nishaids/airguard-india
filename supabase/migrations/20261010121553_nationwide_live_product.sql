-- Additive migration; preserves all legacy ingestion/research data.
create table if not exists airguard.locations (
 location_key text primary key, name text not null, region text, latitude double precision not null check(latitude between 6 and 38),
 longitude double precision not null check(longitude between 68 and 98), metadata jsonb not null default '{}',
 requested_at timestamptz not null default now(), created_at timestamptz not null default now()
);
create index if not exists locations_requested on airguard.locations(requested_at desc);
create table if not exists airguard.sensors (
 sensor_id text primary key, station_pk bigint references airguard.stations, pollutant text not null,
 raw_unit text not null, metadata jsonb not null, fetched_at timestamptz not null
);
create index if not exists sensors_station on airguard.sensors(station_pk);
create table if not exists airguard.cache_metadata (
 cache_key text primary key, provider text not null, payload jsonb, fetched_at timestamptz,
 expires_at timestamptz, lease_until timestamptz, lease_token text
);
create index if not exists cache_expiry on airguard.cache_metadata(expires_at);
create table if not exists airguard.provider_events (
 id bigserial primary key, provider text not null, operation text not null, status text not null,
 latency_ms integer not null, record_count integer not null default 0, http_status integer, error_class text,
 detail text, created_at timestamptz not null default now()
);
create index if not exists provider_events_recent on airguard.provider_events(provider,created_at desc);
create table if not exists airguard.request_budgets (
 bucket text primary key, window_start timestamptz not null, used integer not null check(used>=0)
);
create table if not exists airguard.environmental_records (
 record_key text primary key, provider text not null, source_type text not null check(source_type in('measured','modelled_forecast','weather_forecast')),
 model text, station_pk bigint references airguard.stations, sensor_id text references airguard.sensors,
 latitude double precision not null, longitude double precision not null, pollutant text not null,
 raw_value double precision not null check(raw_value>=0), raw_unit text not null,
 normalized_value double precision not null check(normalized_value>=0), normalized_unit text not null,
 valid_at timestamptz not null, issued_at timestamptz, provider_issued_at timestamptz,
 fetched_at timestamptz not null, quality_state text not null, provenance jsonb not null,
 methodology_version text not null
);
create index if not exists environmental_records_valid on airguard.environmental_records(provider,latitude,longitude,valid_at desc);
create index if not exists environmental_records_sensor on airguard.environmental_records(sensor_id,valid_at desc) where sensor_id is not null;
-- An immutable artifact stores the full input and derived values before tomorrow.
create table if not exists airguard.forecast_runs (
 id bigserial primary key, location_key text not null references airguard.locations,
 latitude double precision not null, longitude double precision not null, region text,
 provider text not null, model text not null, issued_at timestamptz not null,
 provider_issued_at timestamptz, target_start timestamptz not null, target_end timestamptz not null,
 predicted_aqi integer check(predicted_aqi between 0 and 500), predicted_category text, dominant_pollutant text,
 qualifier text, raw_forecast_reference text not null, methodology_version text not null,
 artifact jsonb not null, created_at timestamptz not null default now(),
 check(issued_at < target_start and target_start < target_end),
 unique(location_key,target_start,raw_forecast_reference,methodology_version)
);
create index if not exists forecast_runs_due on airguard.forecast_runs(target_end,id);
create index if not exists forecast_runs_location on airguard.forecast_runs(location_key,issued_at desc);
create table if not exists airguard.forecast_verifications (
 id bigserial primary key, forecast_run_id bigint not null references airguard.forecast_runs,
 station_pk bigint not null references airguard.stations, measured_aqi integer not null check(measured_aqi between 0 and 400),
 measured_category text not null, category_index integer not null, predicted_category_index integer not null,
 error double precision not null, lead_hours double precision not null check(lead_hours>0),
 evidence jsonb not null, verified_at timestamptz not null default now(), unique(forecast_run_id,station_pk)
);
create index if not exists forecast_verifications_station on airguard.forecast_verifications(station_pk);
create or replace function airguard.reject_forecast_mutation() returns trigger
 language plpgsql set search_path='' as $$ begin raise exception 'Issued forecasts and verifications are immutable'; end $$;
revoke all on function airguard.reject_forecast_mutation() from public,anon,authenticated;
create trigger immutable_forecast before update or delete on airguard.forecast_runs
 for each row execute function airguard.reject_forecast_mutation();
create trigger immutable_verification before update or delete on airguard.forecast_verifications
 for each row execute function airguard.reject_forecast_mutation();
alter table airguard.locations enable row level security;
alter table airguard.sensors enable row level security;
alter table airguard.cache_metadata enable row level security;
alter table airguard.provider_events enable row level security;
alter table airguard.request_budgets enable row level security;
alter table airguard.environmental_records enable row level security;
alter table airguard.forecast_runs enable row level security;
alter table airguard.forecast_verifications enable row level security;
revoke all on all tables in schema airguard from anon,authenticated;
update airguard.source_registry set notes='CAMS global 0.4 degree forecasts via Open-Meteo; never station measurements.' where source_id='CAMS/Open-Meteo';
