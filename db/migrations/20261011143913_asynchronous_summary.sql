-- Private server-only job dispatch. Leases collapse simultaneous cache misses;
-- pg_net sends the request only after this transaction commits. No public role
-- can read Vault, execute this function, or write cache/job state.
create or replace function airguard.enqueue_summary(summary_key text, lat double precision, lon double precision)
returns text language plpgsql set search_path='' as $$
declare token text; job_token text := pg_catalog.gen_random_uuid()::text; claimed text; old_payload jsonb;
begin
 if lat is null or lon is null or not (lat between 6 and 38 and lon between 68 and 98)
    or summary_key is null or length(summary_key)>220 or summary_key not like 'summary:%' then
   raise exception 'Invalid summary job';
 end if;
 insert into airguard.cache_metadata(cache_key,provider,lease_until,lease_token,payload)
 values('queue:'||summary_key,'summary_queue',now()+interval '360 seconds',job_token,null)
 on conflict(cache_key) do update set lease_until=excluded.lease_until,lease_token=excluded.lease_token,payload=null
 where airguard.cache_metadata.lease_until is null or airguard.cache_metadata.lease_until<now()
 returning cache_key into claimed;
 if claimed is null then
   select payload into old_payload from airguard.cache_metadata where cache_key='queue:'||summary_key;
   return case when old_payload->>'status'='FAILED' then 'FAILED' else 'IN_PROGRESS' end;
 end if;
 select decrypted_secret into token from vault.decrypted_secrets where name='airguard_cron_secret';
 if token is null then raise exception 'Scheduler secret not provisioned'; end if;
 perform net.http_post(
   url:='https://webapp-phi-taupe.vercel.app/api/internal/refresh',
   headers:=jsonb_build_object('Content-Type','application/json','Authorization','Bearer '||token),
   body:=jsonb_build_object('task','summary','lat',lat::text,'lon',lon::text,'job_token',job_token),
   timeout_milliseconds:=300000
 );
 return 'QUEUED';
end $$;
revoke all on function airguard.enqueue_summary(text,double precision,double precision) from public,anon,authenticated;
