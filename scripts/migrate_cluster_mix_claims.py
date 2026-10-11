"""Replace the clustering artefacts' policy-lever claims with mix descriptions.

An unsupervised partition of six pollutant shares cannot attribute a mix to a
source, so it cannot recommend an intervention either (limitation L30). The
wording in `src/models/train_clustering.py` has been rewritten accordingly, but
regenerating the artefacts needs the legacy raw archive. The description is a
deterministic function of the cluster's defining pollutant, so this recomputes
it from the new rules rather than inventing or retyping anything, and records
that attribution is not established.

Idempotent: run it again and it reports nothing to do.
"""
import json
import sys

from src import config
from src.models.train_clustering import label_archetypes  # noqa: F401 - import proves the rules load

TARGETS = ('results/evaluation_clustering.json', 'webapp/public/data/evaluation_clustering.json')
ATTRIBUTION = 'NOT_ESTABLISHED — association only; no source apportionment is cited'


def rules():
    """The composition rules as the current module defines them."""
    from src.models import train_clustering
    import inspect
    source = inspect.getsource(train_clustering.label_archetypes)
    namespace = {}
    start = source.index('composition_rules = {')
    end = source.index('}', source.index('"CO": ('))
    exec(source[start:end + 1].replace('    composition_rules', 'composition_rules'), namespace)  # noqa: S102
    return namespace['composition_rules']


def migrate(payload, mapping):
    changed = 0
    for entry in payload.get('archetypes') or []:
        rule_for = (mapping.get(entry.get('defining_pollutant')) or (None, None))[0]
        expected_name = f"{entry.get('burden_level')}, {rule_for}" if entry.get('burden_level') else None
        if ('policy_lever' not in entry and entry.get('composition') == rule_for
                and (expected_name is None or entry.get('archetype') == expected_name)):
            continue
        pollutant = entry.get('defining_pollutant')
        rule = mapping.get(pollutant)
        if not rule:
            continue
        entry.pop('policy_lever', None)
        entry['mix_interpretation'] = rule[1]
        entry['composition'] = rule[0]
        if entry.get('burden_level'):
            # The archetype name embeds the composition string, so it carries the
            # same claim and has to be rebuilt from the new wording.
            entry['archetype'] = f"{entry['burden_level']}, {rule[0]}"
        entry['attribution'] = ATTRIBUTION
        changed += 1
    if changed:
        payload['attribution_notice'] = (
            'Archetypes are exploratory and describe pollutant-mix shape only. No source '
            'apportionment is cited, so no city-specific intervention is implied.')
    return changed


def main():
    mapping = rules()
    total = 0
    for relative in TARGETS:
        path = config.PROJECT_ROOT / relative
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding='utf-8'))
        changed = migrate(payload, mapping)
        if changed:
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'{relative}: {changed} archetype(s) rewritten')
        total += changed
    if not total:
        print('Nothing to do; artefacts already carry mix descriptions.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
