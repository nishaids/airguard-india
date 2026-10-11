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
   body:='{}'::jsonb,timeout_milliseconds:=60000
 ) into request_id;
 return request_id;
end $$;
revoke all on function airguard.enqueue_refresh() from public,anon,authenticated;
-- Register the real schedule, disabled until the new endpoint has been
-- deployed and smoke-tested with explicit production deployment approval.
select cron.schedule('airguard-nationwide-refresh','17 * * * *','select airguard.enqueue_refresh();');
select cron.alter_job((select jobid from cron.job where jobname='airguard-nationwide-refresh'),active:=false);
