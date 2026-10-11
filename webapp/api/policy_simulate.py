"""POST /api/policy_simulate -- counterfactual pollutant-reduction scenario.

Body: {"reductions": {pollutant: fraction_0_to_1}}

Re-scores the full historical record with the requested proportional pollutant
reduction and returns the same comparison ``app/pages/3_Policy_Simulator.py``
computes, using the identical ``rescore``/``simulate`` functions from
``src/simulate/policy.py`` (numpy and pandas only -- no model is involved, so
this endpoint has no scipy/scikit-learn size concern at all).
"""

from __future__ import annotations

import json
import math
import sys
from functools import lru_cache
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# See the equivalent note in forecast.py: Vercel imports this file without its
# own directory on sys.path, so the bootstrap is inline rather than a sibling
# module. Locally the repository is used directly; on Vercel, api/_bundle/.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1] if (_HERE.parents[1] / "src" / "config.py").exists() else _HERE / "_bundle"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd  # noqa: E402

from src.data.clean import CLEAN_PATH  # noqa: E402
from src.deploy.serverless_inference import read_csv_maybe_gzipped  # noqa: E402
from src.simulate.policy import rescore, simulate  # noqa: E402


@lru_cache(maxsize=1)
def _clean_frame() -> pd.DataFrame:
    return read_csv_maybe_gzipped(CLEAN_PATH, parse_dates=["Date"])


@lru_cache(maxsize=1)
def _baseline() -> pd.DataFrame:
    return rescore(_clean_frame(), {})


def handle(payload: dict, client="anonymous") -> tuple[int, dict]:
    """Request handling, independent of the transport.

    ``handler`` below is what Vercel invokes; ``webapp/dev_api_server.py``
    calls this same function so the local development server and the deployed
    function cannot drift apart.
    """
    if not isinstance(payload,dict):
        return 400,{"ok":False,"message":"Expected a JSON object."}
    if "forecast_run_id" in payload or "location_key" in payload:
        from src.nationwide.scenarios import handle as operational_scenario
        return operational_scenario(payload,client)
    allowed = {"PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3", "Pb"}
    try:
        raw = payload.get("reductions") or {}
        if not isinstance(raw,dict) or len(raw)>8 or set(raw)-allowed or any(isinstance(v,bool) for v in raw.values()):
            raise ValueError
        reductions = {k:float(v) for k,v in raw.items()}
        if any(not math.isfinite(v) or not 0<=v<=1 for v in reductions.values()):
            raise ValueError
        reductions = {k:v for k,v in reductions.items() if v>0}
    except (ValueError,TypeError):
        return 400,{"ok":False,"messages":["Use supported pollutant reductions between 0 and 1."]}
    if not reductions:
        return 400, {"ok": False, "messages": ["Set at least one reduction above zero."]}
    return 200, {"ok": True, "result": simulate(_clean_frame(), _baseline(), reductions)}


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        self._send_json(405,{"ok":False,"message":"Use POST for a counterfactual scenario."})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length<0 or length>16384:
                self._send_json(413,{"ok":False,"messages":["Request body too large."]})
                return
            payload = json.loads(self.rfile.read(length) or b"{}")
            client=self.headers.get("x-real-ip") or self.client_address[0]
            if parse_qs(urlparse(self.path).query).get("view")==["operational"]:
                from src.nationwide.scenarios import handle as operational_scenario
                status,result=operational_scenario(payload,client)
            else:
                status, result = handle(payload,client)
            self._send_json(status, result)
        except (ValueError, json.JSONDecodeError):
            self._send_json(400,{"ok":False,"message":"Invalid JSON request."})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "messages": ["Internal error"]})
