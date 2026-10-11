-- Reinforce immutable ledger joins and time semantics without changing existing records.
create or replace function airguard.guard_research_issue() returns trigger language plpgsql set search_path='' as $$
declare s airguard.feature_snapshots;
begin
 select * into s from airguard.feature_snapshots where snapshot_hash=new.feature_snapshot_hash;
 if s.snapshot_hash is null or new.issued_at<now()-interval '10 minutes' or new.issued_at>now()+interval '1 minute'
 or (new.issued_at at time zone 'Asia/Kolkata')::time not between '20:00:00'::time and '20:10:00'::time
 or (new.feature_cutoff at time zone 'Asia/Kolkata')::time<>'20:00:00'::time
 or s.protocol_version<>new.protocol_version or s.location_key<>new.location_key
 or s.station_pk is distinct from new.station_pk or s.target_date<>new.target_date
 or s.feature_cutoff<>new.feature_cutoff or s.target_start<>new.target_start or s.target_end<>new.target_end
 or new.target_date<>(new.feature_cutoff at time zone 'Asia/Kolkata')::date+1
 or new.target_start<>(new.target_date::timestamp at time zone 'Asia/Kolkata') or new.target_end<>new.target_start+interval '24 hours'
 or new.cams_aqi<>(s.features->>'A_cams_aqi')::double precision
 then raise exception 'Invalid prospective issue-time protocol or feature binding'; end if;
 if new.forecast_mode='CAMS_BASED_NATIONWIDE' and new.predicted_aqi<>new.cams_aqi then raise exception 'Uncorrected mode must equal raw CAMS'; end if;
 if new.forecast_mode='STATION_CALIBRATED_AIRGUARD' and not exists
 (select 1 from airguard.model_versions where model_version=new.model_version and deployment_status='VALIDATED')
 then raise exception 'Correction model has not passed validation'; end if;
 return new;
end $$;
create or replace function airguard.guard_research_verification() returns trigger language plpgsql set search_path='' as $$
declare f airguard.research_forecast_runs; t airguard.station_daily_targets;
begin
 select * into f from airguard.research_forecast_runs where id=new.forecast_run_id;
 select * into t from airguard.station_daily_targets where target_id=new.target_id;
 if f.id is null or t.target_id is null or f.station_pk is distinct from t.station_pk or f.target_date<>t.target_date
 or f.methodology_version<>t.methodology_version or now()<f.target_end or t.available_at<f.target_end
 or new.observed_aqi is distinct from t.target_aqi or new.qualifier is distinct from t.qualifier or new.observed_category is distinct from t.category
 then raise exception 'Outcome does not match the pre-bound station and target'; end if;
 if new.qualifier='EXACT' and new.cams_error is distinct from (f.cams_aqi-t.target_aqi)
 then raise exception 'Incorrect CAMS error'; end if;
 if new.qualifier<>'EXACT' and (new.cams_error is not null or new.airguard_error is not null or new.interval_covered is not null)
 then raise exception 'Censored outcomes cannot have exact error or interval coverage'; end if;
 if new.airguard_error is distinct from (case when new.qualifier='EXACT' and f.corrected_aqi is not null then f.corrected_aqi-t.target_aqi else null end)
 then raise exception 'Incorrect corrected forecast error'; end if;
 return new;
end $$;
revoke all on function airguard.guard_research_issue(),airguard.guard_research_verification() from public,anon,authenticated;
