"""Inspect Git blobs and built browser assets without displaying credentials."""
import json
import os
from datetime import datetime, timezone
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, unquote
from src.ingestion.settings import load_env, SECRET_NAMES

load_env()
needles = {os.environ[n].encode() for n in SECRET_NAMES if len(os.environ.get(n, "")) >= 8}
password = urlsplit(os.environ.get("DATABASE_URL", "")).password
if password and len(password) >= 8:
    needles.add(unquote(password).encode())
root = Path(__file__).resolve().parents[1]
history = subprocess.run(["git", "rev-list", "--objects", "--all"], cwd=root, capture_output=True, check=True).stdout.splitlines()
objects = {line.split(b" ", 1)[0] for line in history}
hits = []
process = subprocess.Popen(["git", "cat-file", "--batch"], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
for oid in objects:
    process.stdin.write(oid + b"\n")
    process.stdin.flush()
    header = process.stdout.readline().split()
    size = int(header[2])
    content = process.stdout.read(size)
    process.stdout.read(1)
    if header[1] == b"blob" and any(n in content for n in needles):
        hits.append(oid.decode())
process.stdin.close()
process.wait()
assets = list((root / "webapp/.next/static").rglob("*"))
asset_hits = sum(1 for p in assets if p.is_file() and any(n in p.read_bytes() for n in needles))
current=subprocess.run(["git","ls-files","--cached","--others","--exclude-standard","-z"],cwd=root,capture_output=True,check=True).stdout.split(b"\x00")
current_hits=0
for raw in current:
    if not raw:continue
    path=root/os.fsdecode(raw)
    if path.is_file() and any(n in path.read_bytes() for n in needles):current_hits+=1
summary={"generated_at":datetime.now(timezone.utc).isoformat(),"git_objects_checked": len(objects),
    "history_secret_hits": len(hits), "current_worktree_secret_hits":current_hits,"browser_asset_secret_hits": asset_hits,
    "browser_assets_checked":sum(1 for p in assets if p.is_file()),
    "notice":"Counts only. No credential value, path or object id of a hit is recorded here."}
out=root/"results/release/secret_audit.json";out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(summary,indent=1),encoding="utf-8")
print(json.dumps(summary))
raise SystemExit(1 if hits or asset_hits or current_hits else 0)
