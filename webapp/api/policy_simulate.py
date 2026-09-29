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
import sys
from functools import lru_cache
from http.server import BaseHTTPRequestHandler
from pathlib import Path

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


def handle(payload: dict) -> tuple[int, dict]:
    """Request handling, independent of the transport.

    ``handler`` below is what Vercel invokes; ``webapp/dev_api_server.py``
    calls this same function so the local development server and the deployed
    function cannot drift apart.
    """
    reductions = {k: float(v) for k, v in (payload.get("reductions") or {}).items() if float(v) > 0}
    if not reductions:
        return 400, {"ok": False, "messages": ["Set at least one reduction above zero."]}
    return 200, {"ok": True, "result": simulate(_clean_frame(), _baseline(), reductions)}


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            status, result = handle(payload)
            self._send_json(status, result)
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "messages": [f"Internal error: {exc}"]})
