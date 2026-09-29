"""POST /api/forecast -- next-day AQI forecast with a cohort health advisory.

Body: {"city": str, "date": "YYYY-MM-DD", "cohort": str, "adjustments": {pollutant: fraction}}
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Vercel imports this file by path, without its own directory on sys.path, so a
# sibling helper module cannot be imported here -- the bootstrap is inline.
# Locally the real repository sits two levels up and is used directly, so the
# development server always runs the current working tree. On Vercel only
# webapp/ is uploaded, so api/_bundle/ is used instead: a generated mirror of
# the paths these functions need (see src/deploy/vendor_for_vercel.py).
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1] if (_HERE.parents[1] / "src" / "config.py").exists() else _HERE / "_bundle"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.deploy.serverless_inference import forecast  # noqa: E402


def handle(payload: dict) -> tuple[int, dict]:
    """Request handling, independent of the transport.

    ``handler`` below is what Vercel invokes; ``webapp/dev_api_server.py``
    calls this same function so the local development server and the deployed
    function cannot drift apart.
    """
    result = forecast(
        city=payload.get("city", ""),
        requested=payload.get("date", ""),
        cohort=payload.get("cohort", "healthy_adult"),
        adjustments=payload.get("adjustments") or {},
    )
    return (200 if result.get("ok") else 400), result


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
        except Exception as exc:  # noqa: BLE001 -- the API must never return a bare 500 with no body
            self._send_json(500, {"ok": False, "messages": [f"Internal error: {exc}"]})
