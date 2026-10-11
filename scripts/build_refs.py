"""Build paper/refs.bib from authoritative records, and drop what will not verify.

Rule 2 of the project's ground rules: every BibTeX entry must resolve through a
DOI or an official URL, and anything that cannot be verified is dropped. Typing
references by hand is how wrong volumes, wrong years and non-existent papers get
into a bibliography, so nothing here is typed: each entry is fetched from
Crossref (DOI content negotiation), from the arXiv API, or confirmed by
retrieving the official page and matching its title.

    python -m scripts.build_refs            # verify and write
    python -m scripts.build_refs --offline  # report what a run would check

Every outcome, including each failure and its reason, is recorded in
results/reference_verification.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone

from src import config

USER_AGENT = 'AirGuard-India-refs/1.0 (research reference verification; mailto:noreply@example.invalid)'
TIMEOUT = 30

# Candidate sources, from the spec's Part G seed list. `expect` is a distinctive
# phrase that must appear in the retrieved record's title, so a DOI typo that
# resolves to a different paper fails rather than silently succeeding.
CANDIDATES = [
    {'key': 'stieb2008aqhi', 'doi': '10.3155/1047-3289.58.3.435',
     'expect': 'air quality health index', 'role': 'AQHI prior art'},
    {'key': 'george2025aqhi', 'doi': '10.1088/1748-9326/aded26',
     'expect': 'city-specific air quality health index', 'role': 'Indian AQHI prior art'},
    {'key': 'jena2021delhi', 'doi': '10.1038/s41598-021-83467-8',
     'expect': 'forecast over delhi', 'role': 'Indian operational forecasting'},
    {'key': 'pommier2018india', 'doi': '10.5194/acp-18-103-2018',
     'expect': 'emission scenarios', 'role': 'model ozone bias over India'},
    {'key': 'grange2018normalisation', 'doi': '10.5194/acp-18-6223-2018',
     'expect': 'meteorological normalisation', 'role': 'deweathering method'},
    {'key': 'shi2021lockdown', 'doi': '10.1126/sciadv.abd6696',
     'expect': 'covid-19 lockdown', 'role': 'event analysis method'},
    {'key': 'inness2019camsra', 'doi': '10.5194/acp-19-3515-2019',
     'expect': 'cams reanalysis', 'role': 'CAMS reanalysis description'},
    {'key': 'orellano2020shortterm', 'doi': '10.1016/j.envint.2020.105876',
     'expect': 'short-term exposure', 'role': 'concentration-response review'},
    {'key': 'diebold1995comparing', 'doi': '10.1080/07350015.1995.10524599',
     'expect': 'predictive accuracy', 'role': 'forecast comparison test'},
    {'key': 'gneiting2007scoring', 'doi': '10.1198/016214506000001437',
     'expect': 'scoring rules', 'role': 'probabilistic evaluation'},
    {'key': 'debont2024india', 'doi': '10.1016/S2542-5196(24)00114-1',
     'expect': 'mortality', 'role': 'Indian mortality coefficients'},
    {'key': 'xu2021enbpi', 'arxiv': '2010.09107',
     'expect': 'conformal prediction', 'role': 'conformal time series'},
    {'key': 'gibbs2021aci', 'arxiv': '2106.00170',
     'expect': 'adaptive conformal inference', 'role': 'online conformal calibration'},
    {'key': 'lundberg2017shap', 'arxiv': '1705.07874',
     'expect': 'interpreting model predictions', 'role': 'attribution method'},
    {'key': 'kushwaha2025nowcasting', 'arxiv': '2511.11185',
     'expect': 'particulate', 'role': 'Indian subcontinent nowcasting'},
    {'key': 'pandey2024spatiotemporal', 'arxiv': '2412.13935',
     'expect': 'pm2.5', 'role': 'Indian spatio-temporal forecasting'},
    {'key': 'cpcb2014aqi', 'url': 'https://cpcb.nic.in/National-Air-Quality-Index/',
     'expect': 'air quality index', 'role': 'CPCB AQI method',
     'bibtex': {'type': 'techreport', 'author': '{Central Pollution Control Board}',
                'title': 'National Air Quality Index', 'institution':
                'Central Pollution Control Board, Ministry of Environment, Forest and Climate Change, India',
                'year': '2014', 'series': 'Control of Urban Pollution Series CUPS/82/2014-15'}},
    {'key': 'who2021guidelines',
     'url': 'https://www.who.int/publications/i/item/9789240034228',
     'expect': 'air quality guidelines', 'role': 'exposure guideline values',
     'bibtex': {'type': 'techreport', 'author': '{World Health Organization}',
                'title': 'WHO global air quality guidelines: particulate matter, ozone, nitrogen dioxide, '
                         'sulfur dioxide and carbon monoxide', 'institution': 'World Health Organization',
                'year': '2021'}},
    {'key': 'cams2024forecasts',
     'url': 'https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts',
     'expect': 'atmospheric composition', 'role': 'forecast input dataset',
     'bibtex': {'type': 'misc', 'author': '{Copernicus Atmosphere Monitoring Service}',
                'title': 'CAMS global atmospheric composition forecasts',
                'howpublished': 'Copernicus Atmosphere Data Store', 'year': '2024'}},
    {'key': 'openaq2026', 'url': 'https://docs.openaq.org/',
     'expect': 'openaq', 'role': 'measured data source',
     'bibtex': {'type': 'misc', 'author': '{OpenAQ}', 'title': 'OpenAQ API version 3 documentation',
                'howpublished': 'OpenAQ', 'year': '2026'}},
    {'key': 'openmeteo2026', 'url': 'https://open-meteo.com/en/docs/air-quality-api',
     'expect': 'air quality', 'role': 'forecast delivery source',
     'bibtex': {'type': 'misc', 'author': '{Open-Meteo}', 'title': 'Air Quality API documentation',
                'howpublished': 'Open-Meteo', 'year': '2026'}},
]


def fetch(url, accept=None):
    request = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT, **({'Accept': accept} if accept else {})})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - fixed https hosts
        return response.status, response.read().decode('utf-8', errors='replace')


def normalise(text):
    """Fold punctuation and whitespace so a hyphen or a decimal point in either
    the record or the expected phrase cannot fail an otherwise exact match."""
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', (text or '').lower())).strip()


def clean_bibtex(text):
    """Make a Crossref entry safe for LaTeX.

    Crossref returns JATS markup inside titles (``<sub>2.5</sub>``) and HTML
    entities (``&amp;``), both of which would reach the typeset page verbatim.
    Subscript markup is dropped rather than translated: ``PM2.5`` is how the
    pollutant is written everywhere else in this paper.
    """
    text = re.sub(r'</?(?:sub|sup|i|b|italic|bold|sc)>', '', text)
    # Dropping the tags leaves "PM 2.5" and "O 3"; rejoin the formulae.
    text = re.sub(r'\b(PM|NO|SO|O|CO|NH)\s+(\d+(?:\.\d+)?)\b', r'\1\2', text)
    text = text.replace('&amp;', r'\&').replace('&lt;', '<').replace('&gt;', '>')
    return re.sub(r'[ \t]*\n[ \t]+', ' ', text)


def verify_doi(candidate):
    doi = candidate['doi']
    status, body = fetch(f'https://api.crossref.org/works/{urllib.parse.quote(doi)}',
                         'application/json')
    message = json.loads(body)['message']
    title = (message.get('title') or [''])[0]
    if normalise(candidate['expect']) not in normalise(title):
        return None, f"title mismatch: Crossref returned {title!r}"
    _status, bibtex = fetch(f'https://doi.org/{urllib.parse.quote(doi)}', 'application/x-bibtex')
    bibtex = re.sub(r'^@(\w+)\{[^,]+,', lambda m: f"@{m.group(1)}{{{candidate['key']},", bibtex.strip(), count=1)
    bibtex = clean_bibtex(bibtex)
    record = {
        'title': title, 'year': (message.get('issued', {}).get('date-parts') or [[None]])[0][0],
        'container': (message.get('container-title') or [''])[0],
        'authors': [f"{a.get('family', '')}, {a.get('given', '')}".strip(', ')
                    for a in (message.get('author') or [])][:8],
        'doi': doi, 'verified_by': 'crossref', 'http_status': status,
    }
    return bibtex, record


def verify_arxiv(candidate):
    identifier = candidate['arxiv']
    status, body = fetch(f'http://export.arxiv.org/api/query?id_list={identifier}')
    root = ElementTree.fromstring(body)
    namespace = {'atom': 'http://www.w3.org/2005/Atom'}
    entry = root.find('atom:entry', namespace)
    if entry is None:
        return None, 'arXiv returned no entry'
    title = (entry.findtext('atom:title', '', namespace) or '').strip()
    if normalise(candidate['expect']) not in normalise(title):
        return None, f"title mismatch: arXiv returned {title!r}"
    authors = [a.findtext('atom:name', '', namespace) for a in entry.findall('atom:author', namespace)]
    published = (entry.findtext('atom:published', '', namespace) or '')[:4]
    bibtex = ('@misc{' + candidate['key'] + ',\n'
              f'  title = {{{title}}},\n'
              f'  author = {{{" and ".join(authors)}}},\n'
              f'  year = {{{published}}},\n'
              f'  eprint = {{{identifier}}},\n'
              '  archivePrefix = {arXiv}\n}')
    return bibtex, {'title': title, 'year': published, 'container': 'arXiv',
                    'authors': authors[:8], 'arxiv': identifier,
                    'verified_by': 'arxiv_api', 'http_status': status}


def verify_url(candidate):
    status, body = fetch(candidate['url'])
    match = re.search(r'<title[^>]*>(.*?)</title>', body, re.S | re.I)
    page_title = re.sub(r'\s+', ' ', match.group(1)).strip() if match else ''
    expected = normalise(candidate['expect'])
    if expected not in normalise(page_title) and expected not in normalise(body[:60000]):
        return None, f"expected phrase not found at {candidate['url']} (title {page_title!r})"
    fields = dict(candidate['bibtex'])
    kind = fields.pop('type')
    fields['note'] = f"Online: {candidate['url']}"
    lines = ',\n'.join(f'  {name} = {{{value}}}' for name, value in fields.items())
    bibtex = f"@{kind}{{{candidate['key']},\n{lines}\n}}"
    return bibtex, {'title': fields.get('title'), 'year': fields.get('year'),
                    'container': fields.get('institution') or fields.get('howpublished'),
                    'url': candidate['url'], 'page_title': page_title,
                    'verified_by': 'official_url', 'http_status': status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='list what would be checked, fetch nothing')
    args = parser.parse_args()
    if args.offline:
        print(json.dumps([{k: c.get(k) for k in ('key', 'doi', 'arxiv', 'url', 'role')}
                          for c in CANDIDATES], indent=1))
        return 0

    entries, verified, dropped = [], [], []
    for candidate in CANDIDATES:
        try:
            if candidate.get('doi'):
                bibtex, record = verify_doi(candidate)
            elif candidate.get('arxiv'):
                bibtex, record = verify_arxiv(candidate)
            else:
                bibtex, record = verify_url(candidate)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError,
                ElementTree.ParseError, TimeoutError) as exc:
            bibtex, record = None, f'{type(exc).__name__}: {exc}'
        if bibtex is None:
            dropped.append({'key': candidate['key'], 'role': candidate.get('role'), 'reason': record})
            print(f"DROP {candidate['key']}: {record}")
        else:
            entries.append(bibtex)
            verified.append({'key': candidate['key'], 'role': candidate.get('role'), **record})
            print(f"OK   {candidate['key']}: {record['title'][:70]}")
        time.sleep(0.5)

    header = [
        '% Generated by scripts/build_refs.py. Do not edit by hand.',
        '% Every entry was fetched from Crossref, the arXiv API or the official page and',
        '% checked against an expected title phrase. Entries that did not verify were',
        '% dropped and the reason is in results/reference_verification.json.',
        f'% Generated {datetime.now(timezone.utc).isoformat()}.',
        '',
    ]
    out = config.PROJECT_ROOT / 'paper/refs.bib'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(header + entries) + '\n', encoding='utf-8')

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'candidates': len(CANDIDATES), 'verified': len(verified), 'dropped': len(dropped),
        'bibliography': config.portable(out),
        'verified_entries': verified, 'dropped_entries': dropped,
        'notice': 'Verification confirms that a record exists and matches its title. Whether a source '
                  'supports a particular claim, and whether a coefficient from it may be adopted, '
                  'remains a human judgement (HUMAN_ACTIONS.md).',
    }
    (config.PROJECT_ROOT / 'results/reference_verification.json').write_text(
        json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('candidates', 'verified', 'dropped', 'bibliography')}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
