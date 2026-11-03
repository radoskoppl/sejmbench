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


# ---- issue #12: model identity, retry policy, prompt variants ----

def _model_card(with_identity=True, with_retry=True, variant="reference"):
    fixtures = {"a.json": {"votes": [{"club": "A", "vote": "YES"}] * 6,
                           "term": 10, "sitting": 1, "votingNumber": 2,
                           "title": "t"}}
    items = {"a.json": {"model": "m", "date": "2026-11-03", "temperature": 0,
                        "prompt_hash": scoring.reference_prompt_hash(),
                        "declared_cutoff": "unknown",
                        "raw_output": {"winner": "yes",
                                       "tracks": [{"club": "A", "yes_share": 1.0,
                                                   "polarization": 0.0}]},
                        "fixture": "a.json", "_path": "<test>",
                        "input_tokens": 1234, "context_overflow": False,
                        "inference_attempts": 1}}
    model = {"id": "m", "provider": "p", "revision": None,
             "identity_mutable_alias": True, "call_date": "2026-11-03",
             "decoding": {"temperature": 0}}
    if with_identity:
        model["identity"] = {"weights_sha256": "abc", "tokenizer": "tok-1",
                             "quantization": "bf16", "runtime": "basal-serve",
                             "runtime_version": "2.5.2", "context_length": 262144}
    meta = {"benchmark_version": scoring.BENCHMARK_VERSION,
            "metric_version": scoring.METRIC_VERSION, "harness_version": "t",
            "set": "public", "set_hash": "0" * 64,
            "fixture_entries": {"a.json": {"file": "a.json", "sha256": "x",
                                           "layers": {"0.1": True, "0.2": True}}},
            "model": model,
            "submission": {"kind": "model", "files": []},
            "evaluation_date": "2026-11-03",
            "contamination": {"declared_cutoff": "unknown",
                              "temporal_holdout_applied": False},
            "token_usage": None, "cost_estimate": None}
    if with_retry:
        meta["operational"] = {"retry_policy": "single attempt per item"}
    if variant != "reference":
        meta["prompt_variant"] = variant
    return scoring.build_scorecard(fixtures, items, [], meta)


def test_model_card_requires_identity_and_retry():
    errs = scoring.validate_scorecard(_model_card())
    assert errs == [], errs
    errs = scoring.validate_scorecard(_model_card(with_identity=False))
    assert any("identity" in e for e in errs)
    errs = scoring.validate_scorecard(_model_card(with_retry=False))
    assert any("retry_policy" in e for e in errs)
    bad = _model_card()
    bad["model"]["identity"].pop("quantization")
    assert any("quantization" in e for e in scoring.validate_scorecard(bad))


def test_model_items_carry_operational_fields():
    card = _model_card()
    assert scoring.validate_scorecard(card) == []
    it = card["items"][0]
    assert it["input_tokens"] == 1234
    assert it["context_overflow"] is False
    assert it["inference_attempts"] == 1


def test_corpus_prompt_variant_validates_and_tamper_fails():
    card = _model_card(variant="corpus")
    assert scoring.validate_scorecard(card) == []
    assert card["prompt"]["hash"] == scoring.corpus_reference_prompt_hash()
    tampered = _model_card(variant="corpus")
    tampered["prompt"]["template"] += "\nbe creative\n"
    assert any("pinned hash" in e for e in scoring.validate_scorecard(tampered))


def test_partial_abstention_winner_scores_tracks_coverage_zero():
    fixtures = {"a.json": {"votes": [{"club": "A", "vote": "YES"}] * 6,
                           "term": 10, "sitting": 1, "votingNumber": 2,
                           "title": "t"}}
    items = {"a.json": {"model": "m", "date": "2026-11-03", "temperature": 0,
                        "prompt_hash": scoring.reference_prompt_hash(),
                        "declared_cutoff": "unknown",
                        "raw_output": {"winner": "yes",
                                       "tracks_abstained": "typed API"},
                        "fixture": "a.json", "_path": "<test>"}}
    meta = {"benchmark_version": scoring.BENCHMARK_VERSION,
            "metric_version": scoring.METRIC_VERSION, "harness_version": "t",
            "set": "public", "set_hash": "0" * 64,
            "fixture_entries": {"a.json": {"file": "a.json", "sha256": "x",
                                           "layers": {"0.1": True, "0.2": True}}},
            "model": {"id": "m", "provider": "p", "revision": None,
                      "identity_mutable_alias": True, "call_date": "2026-11-03",
                      "decoding": {"temperature": 0},
                      "identity": {"weights_sha256": "abc", "tokenizer": "tok",
                                   "quantization": "bf16", "runtime": "r",
                                   "runtime_version": "1", "context_length": 1}},
            "submission": {"kind": "model", "files": []},
            "operational": {"retry_policy": "single attempt"},
            "evaluation_date": "2026-11-03",
            "contamination": {"declared_cutoff": "unknown",
                              "temporal_holdout_applied": False},
            "token_usage": None, "cost_estimate": None}
    card = scoring.build_scorecard(fixtures, items, [], meta)
    assert scoring.validate_scorecard(card) == []
    it = card["items"][0]
    assert it["status"] == "scored"
    assert it["layer0_1"]["correct"] == 1          # winner answered -> scored
    assert it["layer0_2"]["tracks_abstained"] is True
    assert it["layer0_2"]["mae_yes_share"] is None  # never a penalized MAE
    l2 = card["layers"]["0.2"]
    assert l2["n_tracks_answered"] == 0
    assert l2["n_tracks_abstained"] == 1
    assert l2["tracks_answer_coverage"] == 0.0
    assert l2["mae_yes_share"] is None
