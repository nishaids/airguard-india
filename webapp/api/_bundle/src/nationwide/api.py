"""Shared API contract, authentication, validation and safe JSON transport."""
from __future__ import annotations
from contextlib import nullcontext

import hashlib
import hmac
import json
import uuid
from http.server import BaseHTTPRequestHandler
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from src.ingestion.settings import load_env, secret
from src.nationwide.providers import coordinates, utcnow
from src.nationwide.service import Service
from src.nationwide.store import BudgetExceeded

MAX_QUERY_BYTES = 2048


def cache_headers(operation, status, payload, now=None):
    """Shared CDN data is never personalized and never spans IST midnight."""
    if status != 200 or operation not in ('summary','current','forecast'):
        return {'Cache-Control':'no-store'}
    from src.nationwide.cache_policy import remaining_seconds
    from src.nationwide.service import ttl
    remaining = remaining_seconds(payload, now or utcnow(), ttl('AIRGUARD_AIR_TTL',3600), ttl('AIRGUARD_WEATHER_TTL',7200))
    ttl = min(600,remaining)
    if ttl < 1: return {'Cache-Control':'no-store'}
    swr = min(3600,remaining-ttl)
    return {'Cache-Control':'public, max-age=0, must-revalidate',
            'Vercel-CDN-Cache-Control':f'public, s-maxage={ttl}, stale-while-revalidate={swr}'}


def dispatch(operation, payload, authorization="", client="anonymous", service=None):
    load_env()
    service = service or Service()
    with service.store.session() if hasattr(service.store,'session') else nullcontext():
        return _dispatch(operation,payload,authorization,client,service)


def _dispatch(operation, payload, authorization="", client="anonymous", service=None):
    load_env()
    service = service or Service()
    try:
        if not isinstance(payload, dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in payload.items()):
            raise ValueError("Invalid query parameters.")
        # Vercel Hobby: the public research URL shares this read-only function.
        # A fixed selector cannot invoke refresh or any internal mutation.
        if operation=='status' and payload.get('view') in ('research','scheduler'):
            operation=payload['view']
            payload={k:v for k,v in payload.items() if k!='view'}
        if operation=='summary' and payload.get('view') in ('tomorrow','context'):
            operation='forecast' if payload['view']=='tomorrow' else 'context'
            payload={k:v for k,v in payload.items() if k!='view'}
        allowed = {"search":{"q"},"current":{"lat","lon","name","region"},"forecast":{"lat","lon","name","region"},"summary":{"lat","lon","name","region"},"context":{"lat","lon","name","region"},"status":set(),"health":set(),"refresh":{"task","lat","lon","job_token"},"metrics":set(),"research":set(),"scheduler":set()}
        if operation not in allowed: raise ValueError('Unknown operation.')
        if set(payload)-allowed[operation]:
            raise ValueError("Unexpected query parameters.")
        if sum(len(k)+len(v) for k,v in payload.items()) > MAX_QUERY_BYTES:
            raise ValueError("Query exceeds the 2KB limit.")
        if operation == "refresh":
            cron_secret = secret("CRON_SECRET")
            if not cron_secret or not hmac.compare_digest(authorization,"Bearer " + cron_secret):
                return 401,{"ok":False,"error":"UNAUTHORIZED"}
            if payload:
                if set(payload)!={'task','lat','lon','job_token'} or payload['task']!='summary':
                    raise ValueError('Invalid private job.')
                lat,lon = coordinates(payload['lat'],payload['lon'])
                uuid.UUID(payload['job_token'])
                return 200,service.run_summary_job(lat,lon,payload['job_token'])
            from src.nationwide.jobs import refresh
            return 200, refresh(service)
        # Shared across invocations. Salted hashes only, not browser health cohorts.
        token = hashlib.sha256(((secret("CRON_SECRET") or "airguard") + client).encode()).hexdigest()
        service.store.budget("request:"+token,60,60)
        service.store.budget("requests-all",120,60)
        if operation=='research':
            from src.research.storage import ResearchStore
            return 200,ResearchStore(service.store).public()
        if operation=='scheduler':
            from src.nationwide.monitoring import scheduler_health
            return 200,scheduler_health(service.store)
        if operation == "health":
            with service.store.cursor() as cur:
                cur.execute("select 1")
            return 200,{"ok":True,"database":"CONNECTED","timestamp":utcnow().isoformat(),"schema_version":"1.0"}
        if operation == "status":
            return 200,{"ok":True,"providers":service.store.status(),"timestamp":utcnow().isoformat()}
        if operation == "metrics":
            return 200,{"ok":True,"track_record":service.store.metrics()}
        if operation == "search":
            result = service.search(payload.get("q"))
        else:
            lat,lon = coordinates(payload.get("lat"),payload.get("lon"))
            result = service.summary(lat,lon,payload.get("name"),payload.get("region"),defer=True)
            if result.get('state') in ('QUEUED','IN_PROGRESS','FAILED'):
                return (503 if result['state']=='FAILED' else 202),result
            if operation in ("current","forecast"):
                key = "current" if operation == "current" else "tomorrow"
                result = {"ok":result[key]["aqi"] is not None,"location":result["location"],key:result[key],"provenance":result["provenance"],"provider_status":result["provider_status"],**({"hourly_forecast":result["hourly_forecast"]} if key=="tomorrow" else {})}
            elif operation=='context':
                result={k:result[k] for k in ('ok','location','measured_context','weather_context','fire_context','provider_status','provenance','refreshed_at','data_quality')}
        return (200 if result.get("ok") else 503),result
    except ValueError as exc:
        return 400,{"ok":False,"error":"INVALID_INPUT","message":str(exc)}
    except BudgetExceeded:
        return 429,{"ok":False,"error":"RATE_LIMITED","message":"Request budget reached. Please retry later."}
    except Exception:
        # DSNs/provider errors can appear in exception chains; never serialize them.
        return 503,{"ok":False,"error":"SERVICE_UNAVAILABLE","message":"Live data is temporarily unavailable. Please retry shortly."}


def make_handler(operation):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self,status,payload):
            body=json.dumps(payload,ensure_ascii=False,allow_nan=False,default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type","application/json; charset=utf-8")
            effective = 'forecast' if operation=='summary' and 'tomorrow' in payload and 'current' not in payload else operation
            for key,value in cache_headers(effective,status,payload).items(): self.send_header(key,value)
            self.send_header("X-Content-Type-Options","nosniff")
            if status == 429:
                self.send_header("Retry-After","60")
            if status == 202:
                self.send_header('Retry-After','5')
            self.send_header("Content-Length",str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if operation == "refresh":
                self.send_json(405,{"ok":False,"error":"METHOD_NOT_ALLOWED"})
                return
            if len(self.path.encode()) > MAX_QUERY_BYTES:
                self.send_json(414,{"ok":False,"error":"QUERY_TOO_LONG"})
                return
            parsed=parse_qs(urlparse(self.path).query,keep_blank_values=True)
            if any(len(values)!=1 for values in parsed.values()):
                self.send_json(400,{"ok":False,"error":"DUPLICATE_PARAMETER"})
                return
            status,payload=dispatch(operation,{k:v[0] for k,v in parsed.items()},self.headers.get("Authorization",""),self.headers.get("x-real-ip") or self.client_address[0])
            self.send_json(status,payload)

        def do_POST(self):
            if operation != "refresh":
                self.send_json(405,{"ok":False,"error":"METHOD_NOT_ALLOWED"})
                return
            try:
                length=int(self.headers.get("Content-Length",0))
                if length<0 or length>512:
                    self.send_json(413,{"ok":False,"error":"BODY_TOO_LARGE"})
                    return
                body=self.rfile.read(length)
                payload=json.loads(body) if body.strip() else {}
            except (ValueError,UnicodeError):
                self.send_json(400,{"ok":False,"error":"INVALID_LENGTH"})
                return
            status,payload=dispatch(operation,payload,self.headers.get("Authorization",""),self.client_address[0])
            self.send_json(status,payload)

        def log_message(self,*args):
            pass  # Query strings/authorization never go to the HTTP log.
    return Handler
