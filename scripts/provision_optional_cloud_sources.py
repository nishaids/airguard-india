"""Provision existing local optional-source keys as server-only production secrets."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from src.ingestion.settings import load_env, secret

ROOT=Path(__file__).resolve().parents[1]


def main():
    load_env()
    cli=next(p.parent/'dist/vc.js' for p in (Path(os.environ['LOCALAPPDATA'])/'npm-cache/_npx').glob('*/node_modules/vercel/package.json') if json.loads(p.read_text())['version']=='63.1.2')
    for name in ('NASA_FIRMS_MAP_KEY','DATA_GOV_API_KEY'):
        value=secret(name)
        if not value:
            print(json.dumps({'name':name,'configured':False,'reason':'Local credential absent; optional source remains unavailable'}))
            continue
        result=subprocess.run([shutil.which('node'),str(cli),'env','add',name,'production','--sensitive','--scope','nishanth-s-projects-e335f110'],
                              cwd=ROOT/'webapp',input=value+'\n',text=True,capture_output=True,timeout=120)
        if result.returncode and 'already exists' not in result.stdout+result.stderr:
            raise RuntimeError('Optional production variable provisioning failed; credential output suppressed')
        print(json.dumps({'name':name,'configured':True,'value':'hidden','target':'production'}))


if __name__=='__main__':main()
