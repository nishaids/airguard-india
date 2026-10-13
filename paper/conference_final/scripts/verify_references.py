"""Verify candidate references against the Crossref REST API.

Each DOI is resolved through https://api.crossref.org/works/<doi>; the returned
title, authors, venue, year, volume, issue and pages are stored verbatim in
evidence/crossref_verification.json. Nothing is inferred when a lookup fails:
the entry is marked UNRESOLVED and must not be cited on Crossref evidence.

Usage: python paper/conference_final/scripts/verify_references.py
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'evidence' / 'crossref_verification.json'

CANDIDATES = {
    # CAMS, MOS and statistical post-processing
    'bertrand2023': '10.5194/acp-23-5317-2023',
    'petetin2022': '10.5194/acp-22-11603-2022',
    'riccio2024': '10.5194/acp-24-1673-2024',
    'colette2025': '10.5194/gmd-18-6835-2025',
    'peuch2022': '10.1175/BAMS-D-21-0314.1',
    'casciaro2022': '10.1016/j.atmosenv.2022.119259',
    'glahn1972': '10.1175/1520-0450(1972)011<1203:TUOMOS>2.0.CO;2',
    'djalalova2015': '10.1016/j.atmosenv.2015.02.021',
    'dellemonache2006': '10.1029/2005JD006311',
    'vannitsem2021': '10.1175/BAMS-D-19-0308.1',
    'zhang2012': '10.1016/j.atmosenv.2012.06.031',
    'bai2018': '10.3390/ijerph15040780',
    'sokhi2022': '10.5194/acp-22-4615-2022',
    # India
    'jena2021': '10.1038/s41598-021-83467-8',
    'govardhan2024': '10.5194/gmd-17-2617-2024',
    'ghude2020': '10.18520/cs/v118/i11/1803-1815',
    'kumar2020': '10.1029/2020JD033019',
    'natarajan2024': '10.1038/s41598-024-54807-1',
    'lawrence2026': '10.1186/s42834-026-00296-y',
    'singh2026': '10.1038/s41598-026-37934-9',
    'pande2024': '10.1016/j.envpol.2024.124040',
    'pant2019': '10.1007/s11869-018-0629-6',
    'brauer2019': '10.1016/j.atmosenv.2019.116940',
    'ganguly2020': '10.1016/j.aeaoa.2020.100096',
    'balakrishnan2019': '10.1016/S2542-5196(18)30261-4',
    'debont2024': '10.1016/S2542-5196(24)00114-1',
    'kumargoyal2011': '10.1016/j.scitotenv.2011.08.069',
    'agarwal2020': '10.1016/j.scitotenv.2020.139454',
    # Spatial and temporal validation, leakage
    'roberts2017': '10.1111/ecog.02881',
    'meyer2018': '10.1016/j.envsoft.2017.12.001',
    'meyer2021': '10.1111/2041-210X.13650',
    'ploton2020': '10.1038/s41467-020-18321-y',
    'just2020': '10.1016/j.atmosenv.2020.117649',
    'wadoux2021': '10.1016/j.ecolmodel.2021.109692',
    'bergmeir2012': '10.1016/j.ins.2011.12.028',
    'tashman2000': '10.1016/S0169-2070(00)00065-0',
    'cerqueira2020': '10.1007/s10994-020-05910-7',
    'kapoor2023': '10.1016/j.patter.2023.100804',
    'croushore2001': '10.1016/S0304-4076(01)00072-0',
    # Conformal and quantile methods
    'vovk2005': '10.1007/b106715',
    'lei2018': '10.1080/01621459.2017.1307116',
    'barber2023': '10.1214/23-AOS2276',
    'foygelbarber2021': '10.1093/imaiai/iaaa017',
    'angelopoulos2023': '10.1561/2200000101',
    'koenker1978': '10.2307/1913643',
    # Forecast evaluation, decisions, extremes
    'gneiting2011': '10.1198/jasa.2011.r10138',
    'gneitingraftery2007': '10.1198/016214506000001437',
    'diebold1995': '10.1080/07350015.1995.10524599',
    'murphy1977': '10.1175/1520-0493(1977)105<0803:TVOCCA>2.0.CO;2',
    'richardson2000': '10.1002/qj.49712656313',
    'stephenson2008': '10.1002/met.53',
    'lerch2017': '10.1214/16-STS588',
    'aznarte2017': '10.1016/j.envpol.2017.05.079',
    'kunsch1989': '10.1214/aos/1176347265',
    'neweywest1987': '10.2307/1913610',
    'hoerl1970': '10.1080/00401706.1970.10488634',
    'eder2006': '10.1016/j.atmosenv.2005.12.062',
    'kang2005': '10.1080/10473289.2005.10464775',
    'tobin1958': '10.2307/1907382',
    # Alerts and behaviour
    'chen2018': '10.1016/S2542-5196(17)30185-7',
    'saberian2017': '10.1016/j.reseneeco.2017.05.004',
    'neidell2009': '10.3368/jhr.44.2.450',
    # Tail under-prediction in learned forecasts
    'npj2023': '10.1038/s41612-023-00397-0',
    # Data services
    'openmeteo2023': '10.5281/zenodo.7970649',
}


def lookup(doi):
    url = 'https://api.crossref.org/works/' + urllib.parse.quote(doi, safe='')
    request = urllib.request.Request(url, headers={'User-Agent': 'AirGuardReferenceAudit/1.0 (mailto:nishanth.r.2024.aids@rajalakshmi.edu.in)'})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            message = json.load(response)['message']
    except urllib.error.HTTPError as error:
        return {'status': 'UNRESOLVED', 'http': error.code}
    except Exception as error:  # network failure is recorded, never papered over
        return {'status': 'UNRESOLVED', 'error': type(error).__name__}
    authors = [' '.join(filter(None, [a.get('given'), a.get('family')])) or a.get('name', '') for a in message.get('author', [])]
    issued = (message.get('issued', {}).get('date-parts') or [[None]])[0]
    return {'status': 'RESOLVED', 'doi': message.get('DOI'), 'type': message.get('type'),
            'title': (message.get('title') or [''])[0], 'authors': authors, 'n_authors': len(authors),
            'container': (message.get('container-title') or [''])[0],
            'short_container': (message.get('short-container-title') or [''])[0],
            'year': issued[0], 'volume': message.get('volume'), 'issue': message.get('issue'),
            'page': message.get('page'), 'article_number': message.get('article-number'),
            'publisher': message.get('publisher')}


def main():
    existing = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    for key, doi in CANDIDATES.items():
        if existing.get(key, {}).get('status') == 'RESOLVED' and existing[key].get('requested_doi') == doi:
            continue
        record = lookup(doi)
        record['requested_doi'] = doi
        existing[key] = record
        print(key, record['status'], record.get('year'), (record.get('title') or '')[:70])
        time.sleep(0.15)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(existing, indent=1, ensure_ascii=False), encoding='utf-8')
    print(sum(r['status'] == 'RESOLVED' for r in existing.values()), 'of', len(existing), 'resolved')


if __name__ == '__main__':
    main()
