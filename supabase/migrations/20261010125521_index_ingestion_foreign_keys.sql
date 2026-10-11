-- Additive FK indexes identified by Supabase performance audit.
create index if not exists air_quality_observations_ingestion_run on airguard.air_quality_observations(ingestion_run_id);
create index if not exists data_quality_flags_ingestion_run on airguard.data_quality_flags(ingestion_run_id);
create index if not exists fire_detections_ingestion_run on airguard.fire_detections(ingestion_run_id);
create index if not exists weather_forecasts_ingestion_run on airguard.weather_forecasts(ingestion_run_id);
create index if not exists environmental_records_station on airguard.environmental_records(station_pk);
-- Supabase hosted Postgres supports these extensions. No public credentials.
create extension if not exists pg_cron;
create extension if not exists pg_net;
create or replace function airguard.enqueue_refresh() returns bigint
language plpgsql set search_path='' as $$
declare token text; request_id bigint;
begin
 select decrypted_secret into token from vault.decrypted_secrets where name='airguard_cron_secret';
 if token is null then raise exception 'Scheduler secret not provisioned'; end if;
 select net.http_post(
   url:='https://webapp-phi-taupe.vercel.app/api/internal/refresh',
   headers:=jsonb_build_object('Content-Type','application/json','Authorization','Bearer '||token),
   body:='{}'::jsonb,timeout_milliseconds:=300000
 ) into request_id;
 return request_id;
end $$;
revoke all on function airguard.enqueue_refresh() from public,anon,authenticated;
