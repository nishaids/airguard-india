-- pg_net is non-relocatable on this hosted version. Its extension marker is
-- public, but the callable network functions/tables live in the net schema.
-- Restrict those objects instead of dropping/reinstalling a live extension.
revoke all on schema net from public,anon,authenticated;
revoke all on all functions in schema net from public,anon,authenticated;
revoke all on all tables in schema net from public,anon,authenticated;
grant usage on schema net to postgres;
grant execute on all functions in schema net to postgres;
