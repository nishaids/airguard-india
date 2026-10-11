"""Provision server-only Vercel envs and Vault from local .env, never stdout."""
import os
import secrets
import subprocess
from pathlib import Path
from src.ingestion.settings import load_env, secret, redact
from src.ingestion.db import connect

root=Path(__file__).resolve().parents[1]
load_env()
if not secret("CRON_SECRET"):
    token=secrets.token_urlsafe(32)
    with (root/".env").open("a",encoding="utf-8") as file:
        file.write("\nCRON_SECRET="+token+"\n")
    os.environ["CRON_SECRET"]=token
    print("CRON_SECRET generated securely in the existing ignored .env")
connection=connect()
try:
    with connection,connection.cursor() as cursor:
        cursor.execute("select id from vault.secrets where name=%s",("airguard_cron_secret",))
        row=cursor.fetchone()
        if row:
            cursor.execute("select vault.update_secret(%s,%s)",(row[0],secret("CRON_SECRET")))
        else:
            cursor.execute("select vault.create_secret(%s,%s,%s)",(secret("CRON_SECRET"),"airguard_cron_secret","Bearer authorization for AirGuard scheduled cache refresh"))
    print("Supabase Vault scheduler secret provisioned")
finally:
    connection.close()
for name,targets in (("DATABASE_URL",("preview",)),("OPENAQ_API_KEY",("production","preview")),("CRON_SECRET",("production","preview"))):
    for target in targets:
        result=subprocess.run(["npx.cmd","--yes","vercel@63.1.2","env","add",name,target,"--sensitive"],cwd=root/"webapp",input=secret(name)+"\n",text=True,capture_output=True,timeout=120)
        output=redact(result.stdout+result.stderr)
        if result.returncode and "already exists" not in output:
            print(name,target,"FAILED",output[:800])
            raise SystemExit(1)
        print(name,target,"configured (value hidden)")
