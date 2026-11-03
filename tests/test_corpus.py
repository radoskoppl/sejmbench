"""Corpus-backed evaluation sets (issue #11): loader, population binding, schema 1.2."""

import gzip
import hashlib
import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import scoring  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "sejmbench_cli", os.path.join(ROOT, "scripts", "sejmbench.py"))
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


def _metric(winner="yes", tracks=None):
    return {"seed_rule": {"winner": winner, "method": "majority", "margin": 10,
                          "tie": False},
            "seed_totals": {"YES": 30, "NO": 20, "ABSTAIN": 1},
            "tracks": tracks or {"A": {"n": 20, "yes": 20, "no": 0, "abstain": 0,
                                       "yes_share": 1.0, "polarization": 0.0}}}


def _write_population(tmp_path, ids, gt_rows):
    pop = tmp_path / "docs" / "population"
    pop.mkdir(parents=True)
    (pop / "ids-full-corpus.txt").write_text("".join(i + "\n" for i in ids))
    with gzip.open(pop / "gt-full.jsonl.gz", "wt", encoding="utf-8") as fh:
        for row in gt_rows:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return str(tmp_path)


def test_corpus_loader_roundtrip(tmp_path):
    ids = ["3:1:1", "3:1:2"]
    rows = [{"id": "term3-s1-v1", "metric": _metric()},
            {"id": "term3-s1-v2", "metric": _metric("no")}]
    repo = _write_population(tmp_path, ids, rows)
    fixtures, pop = cli._corpus_for_set(repo, "full")
    assert sorted(fixtures) == ["term3-s1-v1.json", "term3-s1-v2.json"]
    assert pop["n"] == 2
    assert len(pop["ids_sha256"]) == 64 and len(pop["gt_sha256"]) == 64


def test_corpus_loader_detects_drift(tmp_path):
    repo = _write_population(tmp_path, ["3:1:1", "3:1:9"],
                             [{"id": "term3-s1-v1", "metric": _metric()}])
    with pytest.raises(SystemExit, match="population drift"):
        cli._corpus_for_set(repo, "full")


def test_score_item_uses_precomputed_gt():
    division = {"__gt__": _metric()}
    item = {"raw_output": {"winner": "yes",
                           "tracks": [{"club": "A", "yes_share": 1.0,
                                       "polarization": 0.0}]},
            "_path": "<test>"}
    entry = scoring.score_item(item, division, "x.json")
    assert entry["layer0_1"]["correct"] == 1
    assert entry["layer0_2"]["mae_yes_share"] == 0.0


def _corpus_card(tmp_path, with_population=True):
    repo = _write_population(tmp_path, ["3:1:1"], [{"id": "term3-s1-v1",
                                                    "metric": _metric()}])
    fixtures, pop = cli._corpus_for_set(repo, "full")
    items = scoring.baseline_items("majority-class", fixtures, {"fixtures": []})
    meta = scoring.baseline_meta("majority-class", "full", {"fixtures": []}, "test")
    meta.update({"set_hash": pop["gt_sha256"],
                 "fixture_entries": {name: {"file": name, "sha256": pop["gt_sha256"],
                                            "layers": {"0.1": True, "0.2": True}}
                                     for name in fixtures}})
    if with_population:
        meta["population"] = pop
    return scoring.build_scorecard(fixtures, items, [], meta)


def test_corpus_scorecard_validates_with_population(tmp_path):
    card = _corpus_card(tmp_path)
    assert scoring.validate_scorecard(card) == []
    assert card["population"]["n"] == 1


def test_corpus_scorecard_missing_population_is_invalid(tmp_path):
    card = _corpus_card(tmp_path, with_population=False)
    errs = scoring.validate_scorecard(card)
    assert any("population" in e for e in errs)
