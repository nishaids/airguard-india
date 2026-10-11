"""Private research storage and a deliberately limited public ledger projection."""
from __future__ import annotations
from datetime import timedelta, datetime, timezone
from pathlib import Path
import json
import os
import re
from psycopg2.extras import Json as PgJson
from src.nationwide.store import Store, digest
from src.research.protocol import PROTOCOL, VERSION, aware, cutoff_for, period, build_features, daily_target


def Json(value):
    return PgJson(value,dumps=lambda x:json.dumps(x,default=str,allow_nan=False))


def issuance_identity():
    """Use deployment-supplied identity only; never infer an old issuance SHA."""
    sha = os.environ.get('AIRGUARD_GIT_SHA') or os.environ.get('VERCEL_GIT_COMMIT_SHA')
    sha = sha if sha and re.fullmatch(r'[0-9a-fA-F]{40}', sha) else None
    return {'git_sha': sha, 'feature_version': PROTOCOL['feature_version'],
            'protocol_version': VERSION, 'model_version': 'RAW_CAMS_UPSTREAM_VERSION_NOT_EXPOSED',
            'correction_status': 'NOT_VALIDATED', 'interval': None}


class ResearchStore:
    def __init__(self, store=None): self.store=store or Store()

    def register_protocol(self):
        with self.store.cursor() as c:
            c.execute('insert into airguard.research_protocols(protocol_version,definition,definition_hash) values(%s,%s,%s) on conflict do nothing',
                (VERSION,Json(PROTOCOL),digest(PROTOCOL)))
            c.execute('select definition_hash from airguard.research_protocols where protocol_version=%s',(VERSION,))
            if c.fetchone()['definition_hash']!=digest(PROTOCOL):raise ValueError('Protocol changed without new version')
            c.execute('insert into airguard.advisory_policy_versions(policy_version,protocol_version,definition,status) values(%s,%s,%s,%s) on conflict do nothing',
                (PROTOCOL['advisory']['version'],VERSION,Json(PROTOCOL['advisory']),'EXPERIMENTAL_NOT_DEPLOYED'))

    def snapshot(self,payload,lat,lon,station_pk=None):
        fetched=aware(payload['fetched_at']);key=digest([payload,lat,lon,station_pk])
        with self.store.cursor() as c:
            c.execute('''insert into airguard.provider_snapshots(snapshot_hash,provider,source_type,model,latitude,longitude,station_pk,
                retrieved_at,available_at,reference_time,payload,provenance) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing''',
                (key,payload.get('provider','openaq'),payload['source_type'],payload.get('model'),lat,lon,station_pk,fetched,fetched,payload.get('provider_issued_at'),
                 Json(payload),Json({'available_time_basis':'first actual AirGuard retrieval; upstream release time unknown','raw_reference':payload.get('raw_reference'),
                                    'archive_backfill':False,'methodology_version':PROTOCOL['methodology_version']})))
        return key

    def latest_snapshot(self,kind,lat,lon,cutoff):
        with self.store.cursor() as c:
            c.execute('''select * from airguard.provider_snapshots where source_type=%s and latitude=%s and longitude=%s
                and available_at<=%s order by available_at desc limit 1''',(kind,lat,lon,cutoff))
            r=c.fetchone()
        if not r:return None
        payload=dict(r['payload']);payload.update(available_at=r['available_at'].isoformat(),retrieved_at=r['retrieved_at'].isoformat(),reference_time=r['reference_time'].isoformat() if r['reference_time'] else None)
        return payload

    def measured_rows(self,station_pk,start,end,cutoff=None):
        with self.store.cursor() as c:
            c.execute('''select * from airguard.environmental_records where source_type='measured' and station_pk=%s
                and valid_at>=%s and valid_at<%s and (%s::timestamptz is null or fetched_at<=%s) order by valid_at,fetched_at''',
                (station_pk,start,end,cutoff,cutoff))
            rows=[dict(x) for x in c.fetchall()]
        for r in rows:
            r.update(available_at=r['fetched_at'].isoformat(),retrieved_at=r['fetched_at'].isoformat(),valid_end=(r['valid_at']+timedelta(hours=1)).isoformat())
        return rows

    def capture(self,location,issue_day,now=None):
        from src.nationwide.providers import grid,distance
        now=aware(now or datetime.now(timezone.utc));cutoff=cutoff_for(issue_day)
        if not cutoff<=now<=cutoff+timedelta(minutes=PROTOCOL['issuance_grace_minutes']):
            return {'status':'OUTSIDE_FIXED_ISSUANCE_WINDOW','location':location['key']}
        lat,lon=location['lat'],location['lon'];gx,gy=grid(lat,lon)
        cams=self.latest_snapshot('modelled_forecast',gx,gy,cutoff)
        weather=self.latest_snapshot('weather_forecast',gx,gy,cutoff)
        if not cams:return {'status':'NO_ISSUE_TIME_CAMS_SNAPSHOT','location':location['key']}
        # Only metadata and measurements actually retrieved before cutoff can bind the outcome station.
        with self.store.cursor() as c:
            c.execute('''select station_pk,payload from airguard.provider_snapshots where source_type='measured'
                and available_at<=%s and available_at>%s-interval '3 hours' order by available_at desc limit 100''',(cutoff,cutoff))
            candidates=[dict(r) for r in c.fetchall()]
        usable=[]
        for r in candidates:
            st=r['payload'];km=distance(lat,lon,st['coordinates'])
            if km<=25 and len({x['pollutant'] for x in st.get('latest',[])})>=3:
                usable.append((km,r['station_pk']))
        station_pk=min(usable)[1] if usable else None
        rows=self.measured_rows(station_pk,cutoff-timedelta(hours=49),cutoff,cutoff) if station_pk else []
        try:features=build_features(cams,weather,rows,issue_day,lat,lon,station_pk)
        except ValueError as exc:return {'status':'INPUTS_REJECTED','reason':str(exc),'location':location['key']}
        self.store.location(location)
        key=digest([location['key'],features['snapshot_hash']]);features['snapshot_hash']=key
        latest=max(aware(x['available_at']) for x in features['input_availability'])
        with self.store.cursor() as c:
            c.execute('''insert into airguard.feature_snapshots(snapshot_hash,protocol_version,feature_version,location_key,station_pk,
                issue_time,feature_cutoff,latest_input_available_at,target_date,target_start,target_end,features,provenance)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing''',
                (key,VERSION,PROTOCOL['feature_version'],location['key'],station_pk,now,cutoff,latest,features['target_date'],features['target_start'],features['target_end'],
                 Json(features['features']),Json(features)))
            c.execute('''insert into airguard.research_forecast_runs(protocol_version,location_key,station_pk,feature_snapshot_hash,forecast_mode,
                issued_at,feature_cutoff,target_date,target_start,target_end,cams_aqi,predicted_aqi,methodology_version,git_sha,artifact)
                values(%s,%s,%s,%s,'CAMS_BASED_NATIONWIDE',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing returning id''',
                (VERSION,location['key'],station_pk,key,now,cutoff,features['target_date'],features['target_start'],features['target_end'],features['cams_aqi'],features['cams_aqi'],
                 PROTOCOL['methodology_version'],issuance_identity()['git_sha'],Json({'location':location,'features':features,**issuance_identity()})))
            r=c.fetchone()
        return {'status':'ISSUED' if r else 'ALREADY_ISSUED','forecast_run_id':r['id'] if r else None,'location':location['key']}

    def verify(self,service,limit=2):
        with self.store.cursor() as c:
            c.execute('''select f.* from airguard.research_forecast_runs f where target_end<now()-interval '6 hours'
                and target_end>now()-interval '7 days' and station_pk is not null and not exists
                (select 1 from airguard.research_forecast_verifications v where v.forecast_run_id=f.id)
                order by f.target_end limit %s''',(limit,))
            runs=[dict(x) for x in c.fetchall()]
        results=[]
        for f in runs:
            location=f['artifact']['location']
            # Existing bounded provider fetch; after-outcome retrieval is allowed for targets, never predictors.
            service.providers.measured(location['lat'],location['lon'],f['target_start']-timedelta(hours=7),f['target_end'])
            rows=self.measured_rows(f['station_pk'],f['target_start']-timedelta(hours=7),f['target_end'])
            target=daily_target(rows,f['target_date'],f['station_pk'],datetime.now(timezone.utc))
            calc=target['calculation']
            if calc['aqi'] is None:results.append({'id':f['id'],'status':'INSUFFICIENT_MEASURED_DATA'});continue
            exact=calc['qualifier']=='EXACT'
            with self.store.cursor() as c:
                c.execute('''insert into airguard.station_daily_targets(station_pk,target_date,available_at,methodology_version,target_aqi,qualifier,category,quality_state,evidence)
                    values(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing''',(f['station_pk'],f['target_date'],target['available_at'],PROTOCOL['methodology_version'],calc['aqi'],calc['qualifier'],calc['category']['label'],calc['status'],Json(target)))
                c.execute('select target_id,target_aqi,qualifier,category,evidence from airguard.station_daily_targets where station_pk=%s and target_date=%s and methodology_version=%s',
                    (f['station_pk'],f['target_date'],PROTOCOL['methodology_version']))
                saved=c.fetchone();observed=saved['target_aqi'];exact=saved['qualifier']=='EXACT'
                c.execute('''insert into airguard.research_forecast_verifications(forecast_run_id,target_id,observed_aqi,qualifier,observed_category,cams_error,airguard_error,interval_covered,evidence)
                    values(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing''',(f['id'],saved['target_id'],observed,saved['qualifier'],saved['category'],
                    f['cams_aqi']-observed if exact else None,f['corrected_aqi']-observed if exact and f['corrected_aqi'] is not None else None,
                    f['interval']['lower']<=observed<=f['interval']['upper'] if exact and f['interval'] else None,Json(saved['evidence'])))
            results.append({'id':f['id'],'status':'VERIFIED' if exact else 'CENSORED_CATEGORY_ONLY'})
        return results

    def public(self):
        path=Path(__file__).with_name('readiness.json')
        readiness=json.loads(path.read_text(encoding='utf8')) if path.exists() else {'status':'COLLECTING','checks':{}}
        with self.store.cursor() as c:
            c.execute('''select f.id,f.protocol_version,f.forecast_mode,f.issued_at,f.target_date,f.cams_aqi,f.corrected_aqi,f.predicted_aqi,f.interval,
                f.model_version,f.station_pk,l.name location,v.observed_aqi,v.qualifier,v.observed_category,v.cams_error,v.airguard_error,v.verified_at
                from airguard.research_forecast_runs f join airguard.locations l using(location_key)
                left join airguard.research_forecast_verifications v on v.forecast_run_id=f.id order by f.issued_at desc limit 100''')
            ledger=[dict(r) for r in c.fetchall()]
            c.execute('select count(*) forecasts,min(issued_at) started_at from airguard.research_forecast_runs');summary=dict(c.fetchone())
            c.execute('select count(*) outcomes,count(distinct f.target_date) valid_days from airguard.research_forecast_verifications v join airguard.research_forecast_runs f on f.id=v.forecast_run_id where v.qualifier=\'EXACT\'')
            summary.update(dict(c.fetchone()))
            c.execute('''select id,issued_at,target_start,predicted_aqi,location_key from airguard.forecast_runs order by issued_at desc limit 20''')
            on_demand=[dict(r) for r in c.fetchall()]
            c.execute("select jobname,schedule,active from cron.job where jobname like 'airguard-research-%'");schedules=[dict(r) for r in c.fetchall()]
        for window in (7,30,90):summary[f'{window}_day_status']='COLLECTING' if summary['valid_days']<window else 'ENOUGH_DAYS_CHECK_WINDOW_COVERAGE'
        # An active schedule is not an issued forecast: that conflation is exactly what
        # L38 reported. Report the schedule and the immutable ledger as separate facts.
        summary['fixed_issuance_schedule_active']=any(x['active'] and x['jobname']=='airguard-research-issue' for x in schedules)
        summary['fixed_issuance_logging_active']=bool(summary['forecasts']) and summary['fixed_issuance_schedule_active']
        summary['last_issued_at']=max((r['issued_at'] for r in ledger),default=None)
        return {'ok':True,'protocol':PROTOCOL,'readiness':readiness,'prospective':summary,'ledger':ledger,'schedules':schedules,
            'on_demand_forecasts':on_demand,'on_demand_notice':'Immutable nationwide forecasts issued before target; variable issuance times, excluded from fixed 20:00 protocol experiments.',
            'archive_experiment':'PENDING — ADS credential/terms required','correction_status':'NOT_VALIDATED','last_updated':datetime.now(timezone.utc).isoformat()}
