"""Final mechanical checks on the manuscript source and PDF.

1. Forbidden generation artifacts in main.tex, tables, bibliography and PDF text.
2. Every number macro used in main.tex exists; every cited key is in references.bib.
3. PDF facts: page count, page size, embedded fonts, abstract length, last-page fill.
4. SHA-256 manifest of deliverables.

Run inside paper/conference_final:  python scripts/final_checks.py
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import fitz

BASE = Path(__file__).resolve().parents[1]
ARTIFACTS = ['TODO', 'RESULT PENDING', 'INSERT', 'PLACEHOLDER', 'SYSTEM', 'PROMPT', 'FIXME', 'XXX', 'lorem', 'As an AI',
             'citeturn', 'oaicite', 'contentReference', '```', '**', '??', '[?]', 'tbd', 'TBD', 'draft', 'DRAFT', 'undefined']


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    tex = (BASE / 'main.tex').read_text(encoding='utf-8')
    tables = ''.join(p.read_text(encoding='utf-8') for p in sorted((BASE / 'tables').glob('table*.tex')))
    bib = (BASE / 'references.bib').read_text(encoding='utf-8')
    doc = fitz.open(BASE / 'main.pdf')
    pdf_text = ''.join(page.get_text() for page in doc)
    report = {'artifact_hits': {}}
    for name, text in (('main.tex', tex), ('tables', tables), ('pdf_text', pdf_text)):
        hits = {}
        for token in ARTIFACTS:
            pattern = re.escape(token) if not token.isalpha() else r'(?<![A-Za-z])' + re.escape(token) + r'(?![A-Za-z])'
            found = re.findall(pattern, text)
            if found:
                hits[token] = len(found)
        report['artifact_hits'][name] = hits
    macros = json.loads((BASE / 'evidence' / 'number_macros.json').read_text())
    standard = {'documentclass', 'IEEEoverridecommandlockouts', 'usepackage', 'def', 'UrlFont', 'rmfamily', 'input', 'newcommand', 'begin', 'end',
                'title', 'author', 'IEEEauthorblockN', 'IEEEauthorblockA', 'textit', 'maketitle', 'section', 'subsection', 'cite', 'textbf',
                'ref', 'label', 'centering', 'includegraphics', 'textwidth', 'caption', 'mu', 'frac', 'quad', 'max', 'ge', 'le', 'dots',
                'mathcal', 'bigl', 'bigr', 'hat', 'lceil', 'rceil', 'alpha', 'tau', 'ell', 'lambda', 'footnote', 'raggedright', 'url', 'texttt',
                'bibliographystyle', 'bibliography', 'pmtwo', 'pmten', 'ozone', 'equation', 'IEEEkeywords', 'abstract', 'figure', 'document'}
    used = set(re.findall(r'\\([A-Za-z]+)', tex))
    report['unknown_commands'] = sorted(used - standard - set(macros))
    report['macros_used'] = len(used & set(macros))
    report['macros_defined_unused'] = sorted(set(macros) - used)
    cited = set(k.strip() for group in re.findall(r'\\cite\{([^}]*)\}', tex) for k in group.split(','))
    keys = set(re.findall(r'@\w+\{([^,]+),', bib))
    report['cited'] = len(cited)
    report['cited_missing_from_bib'] = sorted(cited - keys)
    report['bib_entries_not_cited'] = sorted(keys - cited)
    figures = re.findall(r'\\ref\{(fig:[a-z]+)\}', tex)
    order = []
    for key in figures:
        if key not in order:
            order.append(key)
    report['figure_first_citation_order'] = order
    report['tables_cited'] = sorted(set(re.findall(r'\\ref\{(tab:[a-z]+)\}', tex)))
    start, end = pdf_text.find('Abstract'), pdf_text.find('Index Terms')
    abstract = pdf_text[start:end].replace('Abstract—', '').replace('-\n', '').replace('\n', ' ').replace('\ufb01', 'fi').replace('\ufb02', 'fl').strip()
    (BASE / 'ABSTRACT_FINAL.txt').write_text(abstract + '\n', encoding='utf-8', newline='\n')
    last = doc[-1]
    blocks = [b for b in last.get_text('blocks') if b[4].strip()]
    mid = last.rect.width / 2
    right_bottom = max(b[3] for b in blocks if b[0] >= mid - 5)
    body_top, body_bottom = 54.0, 718.9
    fonts = sorted({f[3] for page in doc for f in page.get_fonts()})
    report['pdf'] = {'pages': len(doc), 'page_size_pt': [round(doc[0].rect.width, 1), round(doc[0].rect.height, 1)],
                     'is_a4': abs(doc[0].rect.width - 595.28) < 1 and abs(doc[0].rect.height - 841.89) < 1,
                     'fonts': fonts, 'all_fonts_embedded_subsets': all('+' in f for f in fonts),
                     'abstract_words': len(abstract.split()),
                     'last_page_right_column_bottom_pt': round(right_bottom, 1),
                     'last_page_right_column_fill': round((right_bottom - body_top) / (body_bottom - body_top), 3),
                     'references_in_pdf': len(re.findall(r'^\[\d+\]', pdf_text, flags=re.M)),
                     'displayed_equations': len(re.findall(r'\\begin\{equation\}', tex)),
                     'figures': len(re.findall(r'\\begin\{figure\*?\}', tex)), 'tables': len(re.findall(r'\\input\{tables/table', tex))}
    log = (BASE / 'main.log').read_text(encoding='utf-8', errors='ignore') if (BASE / 'main.log').exists() else ''
    report['latex_log'] = {'overfull_hbox': len(re.findall(r'Overfull \\hbox', log)), 'undefined_references': len(re.findall(r'undefined', log, flags=re.I)),
                           'multiply_defined': len(re.findall(r'multiply defined', log))}
    deliverables = ['main.tex', 'references.bib', 'main.pdf', 'ABSTRACT_FINAL.txt'] + \
        [str(p.relative_to(BASE)).replace('\\', '/') for folder in ('figures', 'tables', 'scripts', 'evidence') for p in sorted((BASE / folder).glob('*'))
         if p.is_file() and p.name != 'deliverable_hashes.json']
    report['sha256'] = {name: sha256(BASE / name) for name in deliverables}
    (BASE / 'evidence' / 'final_checks.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'sha256'}, indent=1))


if __name__ == '__main__':
    main()
