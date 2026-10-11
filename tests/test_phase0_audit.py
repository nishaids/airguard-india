import json
from pathlib import Path
from scripts import confirm_phase0 as audit


def test_part_b_yields_every_limitation_with_severity():
    rows = audit.part_b()
    assert sorted(rows) == list(range(1, 53))
    assert all(sev in 'CHML' and claim and fix for sev, claim, fix in rows.values())


def test_every_limitation_has_a_known_verdict_and_resolvable_anchors():
    rows = audit.part_b()
    found = audit.verdicts(audit.evidence())
    assert sorted(found) == sorted(rows)
    for number, (status, finding, anchors) in found.items():
        assert status in audit.STATUSES, number
        assert finding.strip() and anchors, number
        for spec in anchors:
            citation = audit.anchor(spec)
            path, _, line = citation.strip('`').partition(':')
            assert (audit.ROOT / path).exists(), spec
            if line:
                assert int(line) >= 1


def test_anchor_rejects_text_that_is_not_there():
    for spec in ('does/not/exist.py', 'README.md::a string that is not in the readme'):
        try:
            audit.anchor(spec)
        except SystemExit:
            continue
        raise AssertionError(f'anchor should have failed: {spec}')


def test_path_leak_scan_sees_a_planted_path(tmp_path, monkeypatch):
    planted = audit.ROOT / 'results' / '_leak_probe.json'
    planted.write_text(json.dumps({'source': 'D:\\PODS Project\\airguard-india\\data\\raw\\x.csv'}), encoding='utf-8')
    try:
        assert 'results/_leak_probe.json' in audit.path_leaks()
    finally:
        planted.unlink()
    assert 'results/_leak_probe.json' not in audit.path_leaks()


def test_published_exports_carry_no_local_path():
    published = Path(audit.ROOT / 'webapp/public')
    assert published.exists()
    assert not [p for p in audit.path_leaks() if p.startswith('webapp/public')]
