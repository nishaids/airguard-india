"""Popular-location warming and issue-time-valid, station-only verification."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from psycopg2.extras import Json
from src.nationwide.aqi import aggregate, parse_time
from src.nationwide.providers import utcnow


def verify(service, limit=1):
    with service.store.cursor() as cur:
        cur.execute("""select f.* from airguard.forecast_runs f where f.target_end<now()-interval '6 hours'
            and f.target_end>now()-interval '7 days' and f.qualifier='EXACT' and not exists
            (select 1 from airguard.forecast_verifications v where v.forecast_run_id=f.id)
            and not exists(select 1 from airguard.cache_metadata c where c.cache_key='verify:'||f.id::text and c.expires_at>now())
            order by f.target_end,f.id limit %s""",(limit,))
        due=[dict(r) for r in cur.fetchall()]
    results=[]
    for run in due:
        key="verify:"+str(run["id"])
        def check():
            measured=service.providers.measured(run["latitude"],run["longitude"],run["target_start"]-timedelta(hours=7),run["target_end"])
            outcome={"fetched_at":utcnow().isoformat(),"forecast_run_id":run["id"],"status":"INSUFFICIENT_MEASURED_DATA","pairs":0}
            for station in measured["stations"]:
                calc=aggregate(station["rows"],run["target_start"],run["target_end"])
                if calc["status"]!="VALID":
                    continue
                # Same target period and method; no imputed/modelled truth.
                error=run["predicted_aqi"]-calc["aqi"]
                with service.store.cursor() as cur:
                    cur.execute("""insert into airguard.forecast_verifications(forecast_run_id,station_pk,measured_aqi,measured_category,category_index,
                        predicted_category_index,error,lead_hours,evidence) values(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict do nothing""",
                        (run["id"],station["station_pk"],calc["aqi"],calc["category"]["label"],calc["category"]["index"],run["artifact"]["forecast"]["category"]["index"],
                        error,(run["target_start"]-run["issued_at"]).total_seconds()/3600,Json({"calculation":calc,"station":station,"provider":"openaq","target_start":run["target_start"].isoformat(),"target_end":run["target_end"].isoformat()})))
                    outcome["pairs"]+=cur.rowcount
                    outcome["status"]="VERIFIED"
            return outcome
        data,status=service.cached(key,"verification",check,6*3600)
        results.append(data or status)
    return results


def refresh(service):
    # Distributed lease prevents overlapping scheduler requests.
    token=service.store.claim("job:refresh","scheduler")
    if not token:
        return {"ok":True,"status":"SKIPPED_OVERLAP"}
    started=utcnow()
    try:
        from src.research.storage import ResearchStore
        from src.nationwide.aqi import IST
        research=ResearchStore(service.store)
        issue_results=[]
        local=started.astimezone(IST)
        try:
            research.register_protocol()
            if local.hour==20 and local.minute<10:
                for location in service.store.popular(12):
                    issue_results.append(research.capture(location,local.date()))
                accepted=sum(x.get('status') in ('ISSUED','ALREADY_ISSUED') for x in issue_results)
                service.store.event('research','scheduled_issue','SUCCESS' if accepted==len(issue_results) and accepted else 'PARTIAL',
                    int((utcnow()-started).total_seconds()*1000),accepted,
                    detail=str({x.get('status'):sum(r.get('status')==x.get('status') for r in issue_results) for x in issue_results}))
        except Exception:
            issue_results.append({'status':'RESEARCH_UNAVAILABLE'})
            service.store.event('research','scheduled_issue','FAILED',0,error_class='ResearchIssuanceFailure')
        # The daily prefetch must prepare every research location before the
        # fixed cutoff. Ordinary hourly warming stays small and uses its cache.
        prefetch=local.hour==19 and local.minute>=50
        locations=service.store.popular(12 if prefetch else 2)
        def warm(location):
            data=service.summary(location["lat"],location["lon"],location["name"],location.get("region"),force=prefetch)
            return {"location_key":location["key"],"ok":data["ok"],"forecast_run_id":data["tomorrow"].get("forecast_run_id"),"providers":data["provider_status"]}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(warm,locations))
        verification=verify(service)
        try:research_verification=research.verify(service)
        except Exception:
            research_verification=[{'status':'RESEARCH_UNAVAILABLE'}]
            service.store.event('research','scheduled_verify','FAILED',0,error_class='ResearchVerificationFailure')
        status="SUCCESS" if all(r["ok"] for r in results) else "PARTIAL"
        optional_ingestion=[]
        # Protect the fixed issue window and its dedicated prefetch from
        # unrelated network calls. Ordinary refresh also collects fire context
        # and tests the official feed, independently and at most hourly.
        if not prefetch and not (local.hour==20 and local.minute<10):
            try:
                from src.nationwide.optional_ingestion import ingest_optional
                optional_ingestion=ingest_optional(service)
            except Exception:
                optional_ingestion=[{'status':'UNAVAILABLE'}]
                service.store.event('optional_ingestion','scheduled_ingestion','FAILED',0,error_class='OptionalIngestionFailure')
        service.store.event("scheduler","refresh",status,int((utcnow()-started).total_seconds()*1000),len(results))
        with service.store.cursor() as cur:
            cur.execute("""insert into airguard.ingestion_runs(source_id,started_at,finished_at,status,retrieved,accepted,notes)
                values('CAMS/Open-Meteo',%s,now(),%s,%s,%s,%s)""",(started,status,len(results),sum(r["ok"] for r in results),Json(["Nationwide cache warming and verification",*results,*verification])))
        return {"ok":True,"status":status,"locations":results,"verification":verification,"optional_ingestion":optional_ingestion,"research_issuance":issue_results,"research_verification":research_verification,"finished_at":utcnow().isoformat()}
    finally:
        service.store.release("job:refresh",token)
