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
from functools import lru_cache
from http.server import BaseHTTPRequestHandler

import _repo  # noqa: F401

import pandas as pd

from src.data.clean import CLEAN_PATH
from src.simulate.policy import rescore, simulate


@lru_cache(maxsize=1)
def _clean_frame() -> pd.DataFrame:
    return pd.read_csv(CLEAN_PATH, parse_dates=["Date"])


@lru_cache(maxsize=1)
def _baseline() -> pd.DataFrame:
    return rescore(_clean_frame(), {})


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
            reductions = {k: float(v) for k, v in (payload.get("reductions") or {}).items() if float(v) > 0}
            if not reductions:
                self._send_json(400, {"ok": False, "messages": ["Set at least one reduction above zero."]})
                return
            result = simulate(_clean_frame(), _baseline(), reductions)
            self._send_json(200, {"ok": True, "result": result})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "messages": [f"Internal error: {exc}"]})
