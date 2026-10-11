"""GET /api/live -- validated Supabase records, labelled by their actual source."""
from __future__ import annotations

import json
import logging
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1] if (_HERE.parents[1] / 'src/config.py').exists() else _HERE / '_bundle'
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.ingestion.live import snapshot
from src.ingestion.settings import load_env


def handle(payload):
    load_env()
    try:
        return 200, snapshot((payload.get('city') or '').strip() or None)
    except ValueError:
        return 400, {'ok': False, 'message': 'Unknown city. Choose a supported AirGuard city.'}
    except Exception as exc:
        logging.getLogger(__name__).error('Live storage unavailable (%s)', type(exc).__name__)
        return 503, {'ok': False, 'message': 'Live storage is unavailable. Please try again later.'}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        status, result = handle({'city': (query.get('city') or [''])[0]})
        body = json.dumps(result, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
