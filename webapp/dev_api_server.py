"""Local development server for the two Python API functions.

On Vercel, ``webapp/api/forecast.py`` and ``webapp/api/policy_simulate.py`` are
serverless functions the platform invokes directly. A plain ``next dev`` server
does not run them, and ``vercel dev`` cannot start them on a Windows path
containing a space (its Python bootstrap builds an unquoted command). This
server fills that gap so the application is fully functional locally: it calls
the same ``handle()`` functions the deployed handlers call, so the two cannot
drift apart.

``next.config.mjs`` rewrites ``/api/*`` here in development only; in production
the rewrite is absent and Vercel routes to the real functions.

Run with::

    python webapp/dev_api_server.py [--port 8787]
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_DIR = Path(__file__).resolve().parent / "api"
sys.path.insert(0, str(API_DIR))

import forecast as forecast_function  # noqa: E402
import live_forecast as live_function  # noqa: E402
import policy_simulate as policy_function  # noqa: E402

ROUTES = {
    "/api/forecast": forecast_function.handle,
    "/api/policy_simulate": policy_function.handle,
}
GET_ROUTES = {
    "/api/live_forecast": live_function.handle,
}


class DevHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

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
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(self.path)
        handle = GET_ROUTES.get(parsed.path.rstrip("/"))
        if handle is None:
            self._send_json(404, {"ok": False, "messages": [f"No route {parsed.path}"]})
            return
        try:
            status, result = handle({k: v[0] for k, v in parse_qs(parsed.query).items()})
            self._send_json(status, result)
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "message": f"Internal error: {exc}"})

    def do_POST(self) -> None:
        route = self.path.split("?")[0].rstrip("/")
        handle = ROUTES.get(route)
        if handle is None:
            self._send_json(404, {"ok": False, "messages": [f"No route {route}"]})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            status, result = handle(payload)
            self._send_json(status, result)
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "messages": [f"Internal error: {exc}"]})

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"  api  {fmt % args}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    port = parser.parse_args().port

    print(f"Warming caches (loading the feature matrix and the exported boosters)...")
    forecast_function.handle({"city": "Delhi", "date": "2020-01-01", "cohort": "healthy_adult"})

    print(f"AirGuard India dev API listening on http://127.0.0.1:{port}")
    print(f"  POST {'/api/forecast':<24} next-day forecast")
    print(f"  POST {'/api/policy_simulate':<24} counterfactual scenario")
    ThreadingHTTPServer(("127.0.0.1", port), DevHandler).serve_forever()


if __name__ == "__main__":
    main()
