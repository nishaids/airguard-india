-- AirGuard India: live ingestion schema.
--
-- Everything lives in its own schema, `airguard`. On Supabase the auto-generated
-- REST API exposes only the `public` schema, so these tables are not reachable
-- with the project's anonymous key. Row-level security is enabled on every table
-- as a second barrier, with no policies: only the owning role, which the
-- ingestion job connects as, can read or write.
--
-- No table here holds anything about a person. User or health data is out of
-- scope for this phase by design.
--
-- The script is idempotent: it can be applied to a database that already has it.

create schema if not exists airguard;

-- ------------------------------------------------------------------------- --
-- Who the data comes from, and what kind of thing it is
-- ------------------------------------------------------------------------- --
create table if not exists airguard.source_registry (
    source_id      text primary key,
    display_name   text        not null,
    source_type    text        not null check (source_type in
                     ('measured', 'modelled', 'satellite_fire_detection', 'weather_forecast')),
    is_official    boolean     not null default false,  -- a government publisher's own feed
    requires_key   boolean     not null default false,
    licence        text,
    attribution    text,
    homepage       text,
    notes          text,
    created_at     timestamptz not null default now()
);

insert into airguard.source_registry
    (source_id, display_name, source_type, is_official, requires_key, attribution, homepage, notes)
values
    ('CPCB/data.gov.in', 'CPCB real-time AQI via data.gov.in', 'measured', true, true,
     'Central Pollution Control Board, Government of India, via data.gov.in',
     'https://www.data.gov.in',
     'Official feed. Publishes no unit; values are stored raw and not normalised.'),
    ('OpenAQ', 'OpenAQ v3', 'measured', false, true,
     'OpenAQ, with the upstream provider recorded per station',
     'https://openaq.org',
     'Aggregator. Never labelled as CPCB, even where CPCB is the upstream provider.'),
    ('NASA FIRMS', 'NASA FIRMS VIIRS active fires', 'satellite_fire_detection', false, true,
     'NASA FIRMS (LANCE)', 'https://firms.modaps.eosdis.nasa.gov',
     'Fire detections. Not air quality.'),
    ('Open-Meteo', 'Open-Meteo weather forecast', 'weather_forecast', false, false,
     'Weather data by Open-Meteo.com', 'https://open-meteo.com',
     'Third-party redistribution of national weather models. Free tier is non-commercial.'),
    ('CAMS/Open-Meteo', 'CAMS global atmospheric composition via Open-Meteo', 'modelled', false, false,
     'CAMS, via Open-Meteo.com', 'https://open-meteo.com',
     'Registered so that modelled air quality can only ever be stored as modelled. No connector yet.')
on conflict (source_id) do nothing;

-- ------------------------------------------------------------------------- --
-- Ingestion runs: one row per source per invocation
-- ------------------------------------------------------------------------- --
create table if not exists airguard.ingestion_runs (
    run_id       bigserial   primary key,
    source_id    text        not null references airguard.source_registry,
    started_at   timestamptz not null,
    finished_at  timestamptz,
    status       text        not null check (status in ('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED')),
    retrieved    integer     not null default 0,
    accepted     integer     not null default 0,
    flagged      integer     not null default 0,
    rejected     integer     not null default 0,
    duplicates   integer     not null default 0,
    written      integer     not null default 0,
    error        text,                                  -- redacted before it is stored
    notes        jsonb       not null default '[]'
);
create index if not exists ingestion_runs_source_started on airguard.ingestion_runs (source_id, started_at desc);

-- ------------------------------------------------------------------------- --
-- Stations
-- ------------------------------------------------------------------------- --
create table if not exists airguard.stations (
    station_pk          bigserial   primary key,
    source_id           text        not null references airguard.source_registry,
    source_station_id   text        not null,          -- the provider's own identifier
    name                text,
    city                text,
    state               text,
    country             text,
    latitude            double precision check (latitude between -90 and 90),
    longitude           double precision check (longitude between -180 and 180),
    timezone            text,
    owner               text,
    upstream_provider   text,
    -- Another source's station that is the same physical monitor, and how that was decided.
    same_as_station_pk  bigint references airguard.stations,
    match_method        text,
    match_distance_m    double precision,
    metadata            jsonb       not null default '{}',
    first_seen_at       timestamptz not null default now(),
    last_seen_at        timestamptz not null default now(),
    unique (source_id, source_station_id)
);
create index if not exists stations_city on airguard.stations (city);
create index if not exists stations_same_as on airguard.stations (same_as_station_pk);

-- ------------------------------------------------------------------------- --
-- Air-quality observations
-- ------------------------------------------------------------------------- --
create table if not exists airguard.air_quality_observations (
    observation_id      bigserial   primary key,
    source_id           text        not null references airguard.source_registry,
    source_type         text        not null check (source_type in ('measured', 'modelled')),
    station_pk          bigint      references airguard.stations,
    source_station_id   text        not null,
    source_record_id    text,
    sensor_id           text,
    pollutant           text        not null,
    raw_pollutant       text,
    value_kind          text        not null check (value_kind in ('concentration', 'index', 'unknown')),
    averaging_period    text        not null default 'unspecified',
    raw_value           text,                           -- exactly as the provider sent it
    raw_min             text,
    raw_max             text,
    raw_unit            text,
    normalized_value    double precision,               -- null when it could not be normalised
    normalized_unit     text,
    observed_at         timestamptz not null,           -- UTC
    local_timezone      text,
    retrieved_at        timestamptz not null,
    quality_state       text        not null check (quality_state in ('ok', 'flagged')),
    freshness_at_retrieval text     check (freshness_at_retrieval in ('fresh', 'delayed', 'stale', 'unavailable')),
    use_for_modelling   boolean     not null default true,
    provenance          jsonb       not null default '{}',
    ingestion_run_id    bigint      references airguard.ingestion_runs,
    created_at          timestamptz not null default now(),
    -- The identity that makes ingestion idempotent: re-fetching the same reading inserts nothing.
    unique (source_id, source_station_id, pollutant, averaging_period, observed_at)
);
create index if not exists aqo_station_time on airguard.air_quality_observations (station_pk, observed_at desc);
create index if not exists aqo_pollutant_time on airguard.air_quality_observations (pollutant, observed_at desc);
create index if not exists aqo_observed_at on airguard.air_quality_observations (observed_at desc);

-- ------------------------------------------------------------------------- --
-- Weather forecasts. One row per location, model, valid hour AND retrieval.
-- A later retrieval of the same hour is a new row; rows are never updated.
-- ------------------------------------------------------------------------- --
create table if not exists airguard.weather_forecasts (
    forecast_id            bigserial   primary key,
    source_id              text        not null references airguard.source_registry,
    model                  text        not null,
    location_label         text        not null,
    latitude               double precision not null,
    longitude              double precision not null,
    issued_at              timestamptz,                 -- model run initialisation, when published
    retrieved_at           timestamptz not null,        -- when AirGuard obtained it: the leakage-safe anchor
    valid_at               timestamptz not null,
    lead_time_hours        double precision not null check (lead_time_hours >= 0),
    temperature_2m         double precision,
    relative_humidity_2m   double precision,
    precipitation          double precision,
    wind_speed_10m         double precision,
    wind_direction_10m     double precision,
    surface_pressure       double precision,
    boundary_layer_height  double precision,
    units                  jsonb       not null default '{}',
    quality_state          text        not null check (quality_state in ('ok', 'flagged')),
    provenance             jsonb       not null default '{}',
    ingestion_run_id       bigint      references airguard.ingestion_runs,
    created_at             timestamptz not null default now(),
    unique (source_id, model, latitude, longitude, valid_at, retrieved_at)
);
create index if not exists wf_location_valid on airguard.weather_forecasts (location_label, valid_at);
create index if not exists wf_retrieved on airguard.weather_forecasts (retrieved_at desc);

-- ------------------------------------------------------------------------- --
-- Fire detections. Not air quality.
-- ------------------------------------------------------------------------- --
create table if not exists airguard.fire_detections (
    detection_id      bigserial   primary key,
    source_id         text        not null references airguard.source_registry,
    source_type       text        not null default 'satellite_fire_detection'
                        check (source_type = 'satellite_fire_detection'),
    source_record_id  text        not null,
    product           text,
    satellite         text,
    instrument        text,
    latitude          double precision not null check (latitude between -90 and 90),
    longitude         double precision not null check (longitude between -180 and 180),
    acquired_at       timestamptz not null,
    confidence        text,
    frp_mw            double precision,
    brightness_k      double precision,
    day_night         text,
    version           text,
    retrieved_at      timestamptz not null,
    quality_state     text        not null check (quality_state in ('ok', 'flagged')),
    provenance        jsonb       not null default '{}',
    ingestion_run_id  bigint      references airguard.ingestion_runs,
    created_at        timestamptz not null default now(),
    unique (source_id, source_record_id)
);
create index if not exists fd_acquired on airguard.fire_detections (acquired_at desc);
create index if not exists fd_position on airguard.fire_detections (latitude, longitude);

-- ------------------------------------------------------------------------- --
-- Quality flags, and the reasons for rejected records
-- ------------------------------------------------------------------------- --
create table if not exists airguard.data_quality_flags (
    flag_id           bigserial   primary key,
    record_kind       text        not null check (record_kind in
                        ('air_quality_observation', 'weather_forecast', 'fire_detection', 'rejected_record')),
    observation_id    bigint      references airguard.air_quality_observations on delete cascade,
    forecast_id       bigint      references airguard.weather_forecasts on delete cascade,
    detection_id      bigint      references airguard.fire_detections on delete cascade,
    source_id         text        not null references airguard.source_registry,
    record_hash       text,                             -- identity of a rejected record
    code              text        not null,
    severity          text        not null check (severity in ('info', 'warning', 'reject')),
    message           text        not null,
    field_name        text        not null default '',
    details           jsonb       not null default '{}',
    ingestion_run_id  bigint      references airguard.ingestion_runs,
    created_at        timestamptz not null default now()
);
create unique index if not exists dqf_observation on airguard.data_quality_flags (observation_id, code, field_name) where observation_id is not null;
create unique index if not exists dqf_forecast on airguard.data_quality_flags (forecast_id, code, field_name) where forecast_id is not null;
create unique index if not exists dqf_detection on airguard.data_quality_flags (detection_id, code, field_name) where detection_id is not null;
create unique index if not exists dqf_rejected on airguard.data_quality_flags (source_id, record_hash, code) where record_kind = 'rejected_record';
create index if not exists dqf_code on airguard.data_quality_flags (code);

-- ------------------------------------------------------------------------- --
-- What a model may read: one reading per physical monitor, pollutant and hour.
-- Stations linked as the same monitor share a canonical key; the official
-- source wins a tie. Rows that could not be normalised are excluded.
-- ------------------------------------------------------------------------- --
-- security_invoker: the view checks the caller's own rights, so it cannot be used
-- to read around row-level security. Requires PostgreSQL 15 or later.
create or replace view airguard.observations_for_modelling
with (security_invoker = true) as
select *
from (
    select
        o.*,
        coalesce(s.same_as_station_pk, s.station_pk) as canonical_station_pk,
        row_number() over (
            partition by coalesce(s.same_as_station_pk, s.station_pk), o.pollutant, date_trunc('hour', o.observed_at)
            order by r.is_official desc, o.observed_at desc, o.observation_id
        ) as rank_in_hour
    from airguard.air_quality_observations o
    join airguard.stations s on s.station_pk = o.station_pk
    join airguard.source_registry r on r.source_id = o.source_id
    where o.use_for_modelling
      and o.normalized_value is not null
      and o.source_type = 'measured'
) ranked
where rank_in_hour = 1;

-- ------------------------------------------------------------------------- --
-- Lock everything down
-- ------------------------------------------------------------------------- --
alter table airguard.source_registry          enable row level security;
alter table airguard.ingestion_runs           enable row level security;
alter table airguard.stations                 enable row level security;
alter table airguard.air_quality_observations enable row level security;
alter table airguard.weather_forecasts        enable row level security;
alter table airguard.fire_detections          enable row level security;
alter table airguard.data_quality_flags       enable row level security;
