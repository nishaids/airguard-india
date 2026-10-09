"""GET /api/live_forecast -- tomorrow's AQI for the twelve cities, from current conditions.

Optional query: ``?city=Delhi``.

The inputs are fetched at request time from the CAMS atmospheric model via
Open-Meteo, so this function holds no credential and needs no database. The
response is cached at the edge for half an hour: the underlying model updates
far less often than that, and the provider's free tier is shared.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Vercel imports this file by path, without its own directory on sys.path, so a
# sibling helper module cannot be imported here -- the bootstrap is inline.
# Locally the real repository sits two levels up and is used directly; on
# Vercel only webapp/ is uploaded, so api/_bundle/ is used instead (see
# src/deploy/vendor_for_vercel.py).
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1] if (_HERE.parents[1] / "src" / "config.py").exists() else _HERE / "_bundle"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.live.forecast import live_forecast  # noqa: E402

CACHE_OK = "public, s-maxage=1800, stale-while-revalidate=3600"


def handle(payload: dict) -> tuple[int, dict]:
    """Request handling, independent of the transport (shared with dev_api_server.py)."""
    city = (payload.get("city") or "").strip()
    result = live_forecast([city] if city else None)
    return (200 if result.get("ok") else 503), result


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", CACHE_OK if status == 200 else "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        try:
            query = parse_qs(urlparse(self.path).query)
            status, result = handle({"city": (query.get("city") or [""])[0]})
            self._send_json(status, result)
        except Exception as exc:  # noqa: BLE001 -- the API must never return a bare 500 with no body
            self._send_json(500, {"ok": False, "message": f"Internal error: {exc.__class__.__name__}"})
