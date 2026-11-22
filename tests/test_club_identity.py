"""Club-identity registry (issue #1): table consistency, CI gate, curated picks."""
import gzip
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import club_overlap_report  # noqa: E402
import select_fixtures  # noqa: E402

MEMBERSHIP = os.path.join(ROOT, "docs", "club-identity-membership.json.gz")
IDENTITY = os.path.join(ROOT, "docs", "club-identity.json")


def _load():
    return club_overlap_report.load_membership(MEMBERSHIP)


def _table():
    return json.load(open(IDENTITY, encoding="utf-8"))


def test_identity_table_verifies_against_snapshot():
    _, by_term = _load()
    problems, checked = club_overlap_report.verify(by_term)
    assert problems == []
    assert checked > 50  # every curated relation is recomputed


def test_every_corpus_label_has_an_entry():
    _, by_term = _load()
    table = _table()
    for term, labels in by_term.items():
        assert str(term) in table["terms"], f"term {term} missing from the registry"
        registered = set(table["terms"][str(term)]["labels"])
        assert registered == set(labels), f"term {term}: registry/snapshot label mismatch"


def test_canonical_targets_resolve():
    table = _table()
    for term_s, entry in table["terms"].items():
        labels = entry["labels"]
        for name, rec in labels.items():
            assert rec["canonical"] in labels, f"term {term_s}: {name} canonical target missing"
            assert rec["kind"] in ("canonical", "relay", "alias", "coalition")


def test_known_chains():
    table = _table()
    t10 = table["terms"]["10"]["labels"]
    assert t10["Nowa_Lewica"]["canonical"] == "Lewica"
    assert t10["PSL"]["canonical"] == "PSL-TD"
    assert t10["Polska2050-TD"]["canonical"] == "Polska2050"  # alias, terminal label
    t9 = table["terms"]["9"]["labels"]
    assert t9["SLD"]["canonical"] == "Lewica"
    assert t9["PSL-Kukiz15"]["canonical"] == "KP"
    t3 = table["terms"]["3"]["labels"]
    assert t3["KPN-Ojcz"]["canonical"] == "KdP"


def test_club_split_curated_picks():
    """The two hardcoded picks are the earliest split co-presence divisions."""
    raw, by_term = _load()
    table = _table()
    divs = {}
    for key, e in raw["clubs"].items():
        term, label = key.split("|", 1)
        divs[(int(term), label)] = set(map(tuple, e["divisions"]))
    cands = []
    for term_s, entry in table["terms"].items():
        term = int(term_s)
        for label, rec in entry["labels"].items():
            for edge in rec.get("relations", []):
                if edge["kind"] != "split-from":
                    continue
                both = divs[(term, label)] & divs[(term, edge["with"])]
                if both:
                    s, v = min(both)
                    cands.append((term, s, v, label, edge["with"]))
    cands.sort()
    picks = sorted((e["term"], e["sitting"], e["votingNumber"])
                   for e in select_fixtures.CLUB_SPLIT_CURATED)
    assert [(t, s, v) for t, s, v, _, _ in cands[:2]] == picks


def test_identity_gate_passes_on_repo_fixtures():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "club_identity_check.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "pairs covered" in r.stdout


def test_identity_gate_fails_on_unmapped(tmp_path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    fx = {"term": 10, "sitting": 1, "votingNumber": 2,
          "votes": [{"club": "LEWA_2023_TYPO", "MP": 1, "vote": "YES"}]}
    (fixtures_dir / "fake-fixture.json").write_text(json.dumps(fx), encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "club_identity_check.py"),
                        "--fixtures", str(fixtures_dir)],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "unmapped club id" in r.stderr
