-- Additive research layer. Existing on-demand forecasts and legacy models remain intact.
create table airguard.research_protocols (
 protocol_version text primary key, definition jsonb not null, definition_hash text not null,
 created_at timestamptz not null default now()
);
create table airguard.provider_snapshots (
 snapshot_hash text primary key, provider text not null, source_type text not null,
 model text, latitude double precision, longitude double precision, station_pk bigint references airguard.stations,
 retrieved_at timestamptz not null, available_at timestamptz not null, reference_time timestamptz,
 payload jsonb not null, provenance jsonb not null, created_at timestamptz not null default now(),
 check(available_at<=retrieved_at), check(reference_time is null or reference_time<=retrieved_at)
);
create index provider_snapshots_grid on airguard.provider_snapshots(source_type,latitude,longitude,retrieved_at desc);
create index provider_snapshots_station on airguard.provider_snapshots(station_pk,retrieved_at desc);
create table airguard.station_daily_targets (
 target_id bigserial primary key, station_pk bigint not null references airguard.stations,
 target_date date not null, available_at timestamptz not null, methodology_version text not null,
 target_aqi integer, qualifier text, category text, quality_state text not null, evidence jsonb not null,
 created_at timestamptz not null default now(), unique(station_pk,target_date,methodology_version),
 check(target_aqi is null or target_aqi>=0)
);
create table airguard.dataset_versions (
 data_version text primary key, protocol_version text not null references airguard.research_protocols,
 manifest jsonb not null, created_at timestamptz not null default now()
);
create index dataset_versions_protocol on airguard.dataset_versions(protocol_version);
create table airguard.feature_snapshots (
 snapshot_hash text primary key, protocol_version text not null references airguard.research_protocols,
 feature_version text not null, location_key text not null references airguard.locations,
 station_pk bigint references airguard.stations, issue_time timestamptz not null,
 feature_cutoff timestamptz not null, latest_input_available_at timestamptz not null,
 target_date date not null, target_start timestamptz not null, target_end timestamptz not null,
 features jsonb not null, provenance jsonb not null, created_at timestamptz not null default now(),
 check(latest_input_available_at<=feature_cutoff and feature_cutoff<=issue_time and issue_time<target_start and target_start<target_end)
);
create index feature_snapshots_protocol on airguard.feature_snapshots(protocol_version,target_date);
create index feature_snapshots_station on airguard.feature_snapshots(station_pk,target_date);
create index feature_snapshots_location on airguard.feature_snapshots(location_key,target_date);
create table airguard.experiment_registry (
 experiment_id text primary key, protocol_version text not null references airguard.research_protocols,
 data_version text references airguard.dataset_versions, git_sha text, dirty_tree_hash text,
 seed integer not null, definition jsonb not null, environment jsonb not null,
 status text not null, artifacts jsonb not null, started_at timestamptz not null, completed_at timestamptz
);
create index experiments_protocol on airguard.experiment_registry(protocol_version);
create index experiments_dataset on airguard.experiment_registry(data_version);
create table airguard.model_versions (
 model_version text primary key, experiment_id text references airguard.experiment_registry,
 family text not null, artifact_hash text not null, metadata jsonb not null,
 deployment_status text not null check(deployment_status in ('CANDIDATE','VALIDATED','RETIRED')),
 created_at timestamptz not null default now()
);
create index model_versions_experiment on airguard.model_versions(experiment_id);
create table airguard.training_runs (
 run_id bigserial primary key, experiment_id text not null references airguard.experiment_registry,
 model_version text references airguard.model_versions, metadata jsonb not null, created_at timestamptz not null default now()
);
create index training_runs_experiment on airguard.training_runs(experiment_id);
create index training_runs_model on airguard.training_runs(model_version);
create table airguard.backtest_runs (
 run_id bigserial primary key, experiment_id text not null references airguard.experiment_registry,
 split_definition jsonb not null, metrics jsonb not null, created_at timestamptz not null default now()
);
create index backtest_runs_experiment on airguard.backtest_runs(experiment_id);
create table airguard.backtest_predictions (
 run_id bigint not null references airguard.backtest_runs, station_pk bigint not null references airguard.stations,
 target_date date not null, prediction jsonb not null, primary key(run_id,station_pk,target_date)
);
create index backtest_predictions_station on airguard.backtest_predictions(station_pk);
create table airguard.calibration_runs (
 calibration_id bigserial primary key, experiment_id text not null references airguard.experiment_registry,
 method text not null, calibration_window jsonb not null, evidence jsonb not null, created_at timestamptz not null default now()
);
create index calibration_runs_experiment on airguard.calibration_runs(experiment_id);
create table airguard.advisory_policy_versions (
 policy_version text primary key, protocol_version text not null references airguard.research_protocols,
 definition jsonb not null, status text not null, created_at timestamptz not null default now()
);
create index advisory_policy_protocol on airguard.advisory_policy_versions(protocol_version);
create table airguard.advisory_evaluations (
 evaluation_id bigserial primary key, policy_version text not null references airguard.advisory_policy_versions,
 experiment_id text not null references airguard.experiment_registry, evidence jsonb not null,
 created_at timestamptz not null default now()
);
create index advisory_evaluations_policy on airguard.advisory_evaluations(policy_version);
create index advisory_evaluations_experiment on airguard.advisory_evaluations(experiment_id);
create table airguard.research_forecast_runs (
 id bigserial primary key, protocol_version text not null references airguard.research_protocols,
 location_key text not null references airguard.locations, station_pk bigint references airguard.stations,
 feature_snapshot_hash text not null references airguard.feature_snapshots,
 forecast_mode text not null check(forecast_mode in ('CAMS_BASED_NATIONWIDE','STATION_CALIBRATED_AIRGUARD')),
 issued_at timestamptz not null default now(), feature_cutoff timestamptz not null,
 target_date date not null, target_start timestamptz not null, target_end timestamptz not null,
 cams_aqi double precision not null, corrected_aqi double precision, predicted_aqi double precision not null,
 interval jsonb, model_version text references airguard.model_versions, data_version text,
 methodology_version text not null, git_sha text, artifact jsonb not null,
 unique(protocol_version,location_key,target_date),
 check(feature_cutoff<=issued_at and issued_at<target_start and target_start<target_end),
 check(cams_aqi>=0 and predicted_aqi>=0),
 check((forecast_mode='CAMS_BASED_NATIONWIDE' and corrected_aqi is null and model_version is null and interval is null)
   or (forecast_mode='STATION_CALIBRATED_AIRGUARD' and corrected_aqi is not null and model_version is not null and interval is not null))
);
create index research_forecast_station on airguard.research_forecast_runs(station_pk,target_date);
create index research_forecast_due on airguard.research_forecast_runs(target_end);
create index research_forecast_location on airguard.research_forecast_runs(location_key,issued_at desc);
create index research_forecast_features on airguard.research_forecast_runs(feature_snapshot_hash);
create index research_forecast_model on airguard.research_forecast_runs(model_version);
create table airguard.research_forecast_verifications (
 forecast_run_id bigint primary key references airguard.research_forecast_runs,
 target_id bigint not null references airguard.station_daily_targets,
 observed_aqi integer, qualifier text not null, observed_category text not null,
 cams_error double precision, airguard_error double precision, interval_covered boolean,
 evidence jsonb not null, verified_at timestamptz not null default now()
);
create index research_verification_target on airguard.research_forecast_verifications(target_id);
create or replace function airguard.guard_research_issue() returns trigger language plpgsql set search_path='' as $$
declare s airguard.feature_snapshots; p airguard.research_protocols;
begin
 select * into s from airguard.feature_snapshots where snapshot_hash=new.feature_snapshot_hash;
 select * into p from airguard.research_protocols where protocol_version=new.protocol_version;
 if new.issued_at<now()-interval '10 minutes' or new.issued_at>now()+interval '1 minute'
 or (new.issued_at at time zone 'Asia/Kolkata')::time not between '20:00:00'::time and '20:10:00'::time
 or (new.feature_cutoff at time zone 'Asia/Kolkata')::time<>'20:00:00'::time
 or s.protocol_version<>new.protocol_version or s.location_key<>new.location_key
 or s.station_pk is distinct from new.station_pk or s.target_date<>new.target_date
 or s.feature_cutoff<>new.feature_cutoff or s.target_start<>new.target_start or s.target_end<>new.target_end
 or new.target_date<>(new.feature_cutoff at time zone 'Asia/Kolkata')::date+1
 then raise exception 'Invalid prospective issue-time protocol or feature binding'; end if;
 if new.forecast_mode='STATION_CALIBRATED_AIRGUARD' and not exists
 (select 1 from airguard.model_versions where model_version=new.model_version and deployment_status='VALIDATED')
 then raise exception 'Correction model has not passed validation'; end if;
 return new;
end $$;
create trigger research_issue_guard before insert on airguard.research_forecast_runs for each row execute function airguard.guard_research_issue();
create or replace function airguard.guard_research_verification() returns trigger language plpgsql set search_path='' as $$
declare f airguard.research_forecast_runs; t airguard.station_daily_targets;
begin
 select * into f from airguard.research_forecast_runs where id=new.forecast_run_id;
 select * into t from airguard.station_daily_targets where target_id=new.target_id;
 if f.station_pk is distinct from t.station_pk or f.target_date<>t.target_date or f.methodology_version<>t.methodology_version
 or now()<f.target_end or t.available_at<f.target_end then raise exception 'Outcome does not match the pre-bound station and target'; end if;
 return new;
end $$;
create trigger research_verification_guard before insert on airguard.research_forecast_verifications for each row execute function airguard.guard_research_verification();
revoke all on function airguard.guard_research_issue(),airguard.guard_research_verification() from public,anon,authenticated;
do $$ declare t text; begin
 foreach t in array array['research_protocols','provider_snapshots','station_daily_targets','dataset_versions','feature_snapshots',
 'experiment_registry','model_versions','training_runs','backtest_runs','backtest_predictions','calibration_runs',
 'advisory_policy_versions','advisory_evaluations','research_forecast_runs','research_forecast_verifications'] loop
 execute format('alter table airguard.%I enable row level security',t);
 execute format('revoke all on airguard.%I from anon,authenticated',t);
 execute format('create trigger immutable_research_record before update or delete on airguard.%I for each row execute function airguard.reject_forecast_mutation()',t);
 end loop;
end $$;
-- Future activation remains gated on explicit production deployment approval.
select cron.schedule('airguard-research-issue','30 14 * * *','select airguard.enqueue_refresh();');
select cron.schedule('airguard-research-prefetch','20 14 * * *','select airguard.enqueue_refresh();');
select cron.schedule('airguard-research-verify','30 1 * * *','select airguard.enqueue_refresh();');
select cron.alter_job((select jobid from cron.job where jobname='airguard-research-issue'),active:=false);
select cron.alter_job((select jobid from cron.job where jobname='airguard-research-prefetch'),active:=false);
select cron.alter_job((select jobid from cron.job where jobname='airguard-research-verify'),active:=false);
