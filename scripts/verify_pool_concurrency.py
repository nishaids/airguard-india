"""Read-only check of thirty overlapping transaction-pool clients."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from threading import Barrier
import json
from src.ingestion.db import connect
from src.ingestion.settings import load_env


def main():
    load_env()
    gate=Barrier(30,timeout=20)
    def probe(_):
        connection=None
        try:
            connection=connect(transaction_pool=True)
            with connection,connection.cursor() as cur:
                cur.execute('select 1');assert cur.fetchone()[0]==1
            # Transaction committed; keep the client open to reproduce overlap
            # without holding a backend slot or any data locks.
            gate.wait()
            return 'PASS'
        except Exception as exc:return type(exc).__name__
        finally:
            if connection is not None:connection.close()
    with ThreadPoolExecutor(max_workers=30) as pool:states=list(pool.map(probe,range(30)))
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'read_only':True,
            'concurrent_clients':30,'passed':states.count('PASS'),'errors':sorted(set(states)-{'PASS'})}
    Path('results/release/pool_concurrency.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    assert report['passed']==30


if __name__=='__main__':main()
