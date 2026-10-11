"""Generated adapter: see scripts/generate_nationwide_routes.py."""
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler
_HERE=Path(__file__).resolve()
_API=next(p for p in _HERE.parents if p.name=="api")
_ROOT=_API.parents[1] if (_API.parents[1]/"src/config.py").exists() else _API/"_bundle"
sys.path.insert(0,str(_ROOT))
from src.nationwide.api import dispatch, make_handler
def handle(payload):
    return dispatch("status",payload)
_Implementation=make_handler("status")
class handler(BaseHTTPRequestHandler):
    # Literal BaseHTTPRequestHandler entrypoint is required by Vercel detection.
    send_json=_Implementation.send_json
    do_GET=_Implementation.do_GET
    do_POST=_Implementation.do_POST
    log_message=_Implementation.log_message
