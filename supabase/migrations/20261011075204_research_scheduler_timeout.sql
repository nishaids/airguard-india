-- The 19:50 IST prefetch prepares twelve locations under the existing 300s
-- function limit. Keep the authenticated Supabase transport alive for that
-- bounded work; the token remains exclusively in Vault.
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
