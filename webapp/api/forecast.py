"""POST /api/forecast -- next-day AQI forecast with a cohort health advisory.

Body: {"city": str, "date": "YYYY-MM-DD", "cohort": str, "adjustments": {pollutant: fraction}}
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

import _repo  # noqa: F401  (adds the repo root to sys.path as a side effect)

from src.deploy.serverless_inference import forecast


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
            result = forecast(
                city=payload.get("city", ""),
                requested=payload.get("date", ""),
                cohort=payload.get("cohort", "healthy_adult"),
                adjustments=payload.get("adjustments") or {},
            )
            self._send_json(200 if result.get("ok") else 400, result)
        except Exception as exc:  # noqa: BLE001 -- the API must never return a bare 500 with no body
            self._send_json(500, {"ok": False, "messages": [f"Internal error: {exc}"]})
