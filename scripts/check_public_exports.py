"""CI gate for machine paths and configured secrets in public JSON/Markdown."""
import json
from pathlib import Path
from src.deploy.public_exports import LOCAL_PATH
from src.ingestion.settings import load_env, secret, SECRET_NAMES

ROOT=Path(__file__).resolve().parents[1]


def check():
    load_env();secrets=[secret(n) for n in SECRET_NAMES if secret(n) and len(secret(n))>=8]
    hits=[];paths=list((ROOT/'webapp/public/data').glob('*'))
    for p in paths:
        if not p.is_file() or p.suffix not in ('.json','.md'):continue
        text=p.read_text(encoding='utf-8')
        if LOCAL_PATH.search(text) or any(s in text for s in secrets):hits.append(p.name)
    out={'files_checked':len(paths),'unsafe_public_artifacts':hits,'status':'PASS' if not hits else 'FAIL'}
    print(json.dumps(out))
    return not hits


if __name__=='__main__':raise SystemExit(0 if check() else 1)
