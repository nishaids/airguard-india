"""Measure sentence overlap between the Medium article and the manuscript.

Publishing an article that reuses the paper's sentences would put the paper's
own text into a venue's similarity check against a public page. The article is
therefore written fresh, and this measures whether that held: it compares
word sequences after stripping LaTeX and Markdown, and reports every shared
run of eight or more words.

    python -m scripts.check_article_originality

Exits non-zero if any shared run is found, or if the article is outside the
1,200-1,800 word range the brief asks for.
"""
import json
import re
import sys
from datetime import datetime, timezone

from src import config

WINDOW = 8
ARTICLE = config.PROJECT_ROOT / 'article/medium.md'
SOURCES = ('paper/main.tex',)
WORD_RANGE = (1200, 1800)
# Shared technical names are not borrowed prose; a phrase made only of these is
# ignored so the check flags copied writing rather than unavoidable vocabulary.
VOCABULARY = {
    'the', 'a', 'an', 'of', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'is', 'are', 'was', 'were',
    'be', 'been', 'it', 'its', 'that', 'this', 'with', 'from', 'by', 'as', 'not', 'no',
    'cpcb', 'aqi', 'cams', 'openaq', 'pm2', 'pm10', 'no2', 'so2', 'o3', 'co', 'nh3', 'india',
    'indian', 'air', 'quality', 'index', 'station', 'stations', 'forecast', 'forecasts', 'model',
    'modelled', 'measured', 'data', 'ist', 'open', 'meteo', 'cohort', 'pollutant', 'pollutants',
}


def words(text, latex=False):
    if latex:
        text = re.sub(r'%.*', ' ', text)
        text = re.sub(r'\\(?:cite|ref|input|includegraphics|label|bibliographystyle|bibliography)'
                      r'(?:\[[^\]]*\])?\{[^}]*\}', ' ', text)
        text = re.sub(r'\\begin\{[^}]*\}|\\end\{[^}]*\}', ' ', text)
        text = re.sub(r'\\[a-zA-Z]+\*?', ' ', text)
        text = text.replace('$', ' ').replace('&', ' ').replace('~', ' ')
    else:
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
        text = re.sub(r'[*_`#>|-]+', ' ', text)
    return re.findall(r'[a-z0-9]+', text.lower())


def runs(sequence, window=WINDOW):
    return {tuple(sequence[i:i + window]) for i in range(max(0, len(sequence) - window + 1))}


def main():
    if not ARTICLE.exists():
        print('article/medium.md is missing.')
        return 1
    article = words(ARTICLE.read_text(encoding='utf-8'))
    shared = []
    for relative in SOURCES:
        path = config.PROJECT_ROOT / relative
        if not path.exists():
            continue
        source = runs(words(path.read_text(encoding='utf-8'), latex=True))
        for phrase in sorted(runs(article) & source):
            if set(phrase) <= VOCABULARY:
                continue
            shared.append({'source': relative, 'phrase': ' '.join(phrase)})

    count = len(article)
    in_range = WORD_RANGE[0] <= count <= WORD_RANGE[1]
    summary = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'article': config.portable(ARTICLE), 'words': count,
        'word_range': list(WORD_RANGE), 'within_word_range': in_range,
        'window': WINDOW, 'shared_phrases': shared, 'shared_phrase_count': len(shared),
        'compared_against': list(SOURCES),
        'notice': 'This compares wording only. It is not a substitute for the venue\'s similarity '
                  'check, and it says nothing about whether the article overclaims.',
    }
    (config.PROJECT_ROOT / 'results/article_originality.json').write_text(
        json.dumps(summary, indent=1), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in (
        'words', 'within_word_range', 'shared_phrase_count')}, indent=1))
    for entry in shared[:20]:
        print(f"SHARED with {entry['source']}: {entry['phrase']}")
    return 0 if in_range and not shared else 1


if __name__ == '__main__':
    sys.exit(main())
