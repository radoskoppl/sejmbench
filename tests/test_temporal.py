"""Temporal holdout (issue #5, schema 1.3): block build, validation, rescore."""

import argparse
import gzip
import importlib.util
import json
import os
import shutil
import sys
import tarfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import scoring  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "sejmbench_cli", os.path.join(ROOT, "scripts", "sejmbench.py"))
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

CUTOFF = "2026-01-01"


def _metric(winner="yes", date="2025-06-01T12:00:00"):
    return {"fixture": {"date": date, "sitting": 1, "term": 3, "title": "t",
                        "votingNumber": 1},
            "seed_rule": {"winner": winner, "method": "majority", "margin": 10,
                          "tie": False},
            "seed_totals": {"YES": 30, "NO": 20, "ABSTAIN": 1},
            "tracks": {"A": {"n": 20, "yes": 20, "no": 0, "abstain": 0,
                             "yes_share": 1.0, "polarization": 0.0}}}


def _rows():
    return [
        {"_key": "3:1:1", "_id": "term3-s1-v1",
         "metric": _metric(date="2025-06-01T12:00:00")},
        {"_key": "3:1:2", "_id": "term3-s1-v2",
         "metric": _metric(date="2026-06-01T12:00:00")},
    ]


def _write_repo(tmp_path, rows):
    pop = tmp_path / "docs" / "population"
    pop.mkdir(parents=True)
    (pop / "ids-full-corpus.txt").write_text("".join(r["_key"] + "\n" for r in rows))
    with gzip.open(pop / "gt-full.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({"id": r["_id"], "metric": r["metric"]},
                                sort_keys=True, ensure_ascii=False) + "\n")
    post = sorted(r["_key"] for r in rows
                  if r["metric"]["fixture"]["date"][:10] > CUTOFF)
    (pop / ("ids-post-%s.txt" % CUTOFF)).write_text("".join(k + "\n" for k in post))
    return str(tmp_path)


def _temporal_card(repo):
    fixtures, pop = cli._corpus_for_set(repo, "full")
    items = scoring.baseline_items("majority-class", fixtures, {"fixtures": []})
    meta = scoring.baseline_meta("majority-class", "full", {"fixtures": []}, "test")
    meta.update({"set_hash": pop["gt_sha256"],
                 "fixture_entries": {name: {"file": name, "sha256": pop["gt_sha256"],
                                            "layers": {"0.1": True, "0.2": True}}
                                     for name in fixtures},
                 "population": pop,
                 "temporal": scoring.load_post_ids(repo, CUTOFF, "full")})
    meta["contamination"]["temporal_holdout_applied"] = True
    return scoring.build_scorecard(fixtures, items, [], meta)


def test_fixture_key():
    assert scoring._fixture_key("term10-s1-v10.json") == (10, 1, 10)
    assert scoring._fixture_key("term3-s1-v2") == (3, 1, 2)
    assert scoring._fixture_key("a.json") is None


def test_temporal_block_built_and_validates(tmp_path):
    card = _temporal_card(_write_repo(tmp_path, _rows()))
    ts = card["temporal_split"]
    assert ts["cutoff"] == CUTOFF
    assert ts["n_pre"] == 1 and ts["n_post"] == 1
    assert ts["ids_post_file"] == "docs/population/ids-post-2026-01-01.txt"
    assert len(ts["ids_post_sha256"]) == 64
    assert card["contamination"]["temporal_holdout_applied"] is True
    l01 = ts["layers"]["0.1"]
    assert l01["pre"]["n"] == 1 and l01["post"]["n"] == 1
    assert l01["pre"]["accuracy"] == 1.0 and l01["post"]["accuracy"] == 1.0
    assert scoring.validate_scorecard(card) == []


def test_temporal_split_tamper_variants(tmp_path):
    card = _temporal_card(_write_repo(tmp_path, _rows()))
    bad = json.loads(json.dumps(card))
    bad["temporal_split"]["ids_post_sha256"] = "zz"
    assert any("sha256 hex digest" in e for e in scoring.validate_scorecard(bad))
    bad = json.loads(json.dumps(card))
    bad["temporal_split"]["n_pre"] = 5
    assert any("n_pre+n_post" in e for e in scoring.validate_scorecard(bad))
    bad = json.loads(json.dumps(card))
    bad["contamination"]["temporal_holdout_applied"] = False
    assert any("temporal_holdout_applied" in e for e in scoring.validate_scorecard(bad))
    bad = json.loads(json.dumps(card))
    bad["set"] = "public"
    assert any("corpus sets only" in e for e in scoring.validate_scorecard(bad))


def test_rescore_reproduces_temporal_block(tmp_path):
    repo = _write_repo(tmp_path, _rows())
    card = _temporal_card(repo)
    rebuilt = scoring.rescore(card, repo, {"fixtures": []})
    assert scoring.rescore_matches(card, rebuilt) == []


def test_rescore_detects_post_list_drift(tmp_path):
    repo = _write_repo(tmp_path, _rows())
    card = _temporal_card(repo)
    with open(os.path.join(repo, "docs", "population",
                           "ids-post-%s.txt" % CUTOFF), "w", encoding="utf-8") as fh:
        fh.write("")
    with pytest.raises(SystemExit, match="drift"):
        scoring.rescore(card, repo, {"fixtures": []})


def _model_items(repo, n=2):
    """AGENTS.md item files under <repo>/results/basal-x/ for the corpus rows."""
    rows = _rows()[:n]
    item_dir = os.path.join(repo, "results", "basal-x")
    os.makedirs(item_dir, exist_ok=True)
    paths = []
    for r in rows:
        name = r["_id"] + ".json"
        data = {"model": "m", "date": "2026-11-06", "temperature": 0,
                "prompt_hash": scoring.corpus_reference_prompt_hash(),
                "declared_cutoff": "unknown",
                "raw_output": {"winner": "yes",
                               "tracks": [{"club": "A", "yes_share": 1.0,
                                           "polarization": 0.0}]},
                "fixture": name}
        p = os.path.join(item_dir, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True, ensure_ascii=False)
        paths.append(p)
    return paths


def _model_card_with_tar(repo, item_paths):
    fixtures, pop = cli._corpus_for_set(repo, "full")
    items, _ = scoring.load_submission_files(item_paths)
    meta = {"benchmark_version": scoring.BENCHMARK_VERSION,
            "metric_version": scoring.METRIC_VERSION, "harness_version": "t",
            "repo_root": repo,
            "set": "full", "set_hash": pop["gt_sha256"],
            "fixture_entries": {name: {"file": name, "sha256": pop["gt_sha256"],
                                       "layers": {"0.1": True, "0.2": True}}
                                for name in fixtures},
            "model": {"id": "m", "provider": "p", "revision": None,
                      "identity_mutable_alias": True, "call_date": "2026-11-06",
                      "decoding": {"temperature": 0},
                      "identity": {"weights_sha256": "abc", "tokenizer": "tok",
                                   "quantization": "bf16", "runtime": "r",
                                   "runtime_version": "1", "context_length": 1}},
            "submission": {"kind": "model",
                           "files": [{"fixture": os.path.basename(p),
                                      "path": "results/basal-x/" + os.path.basename(p),
                                      "sha256": scoring._sha256_file(p)}
                                     for p in item_paths]},
            "prompt_variant": "corpus",
            "operational": {"retry_policy": "single attempt per item"},
            "evaluation_date": "2026-11-06",
            "contamination": {"declared_cutoff": "unknown",
                              "temporal_holdout_applied": True},
            "token_usage": None, "cost_estimate": None,
            "population": pop,
            "temporal": scoring.load_post_ids(repo, CUTOFF, "full")}
    return scoring.build_scorecard(fixtures, items, [], meta)


def test_rescore_from_tar_reproduces_model_card(tmp_path):
    repo = _write_repo(tmp_path, _rows())
    item_paths = _model_items(repo)
    card = _model_card_with_tar(repo, item_paths)
    assert scoring.validate_scorecard(card) == []
    # archive the per-item files first (tar layout mirrors the real archives:
    # created from inside results/, so the root is <dir>/), then drop the
    # files - the committed tar becomes the rescore source
    tar_path = os.path.join(repo, "results", "basal-x.raw.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tf:
        for p in item_paths:
            tf.add(p, arcname="basal-x/" + os.path.basename(p))
    shutil.rmtree(os.path.join(repo, "results", "basal-x"))
    rebuilt = scoring.rescore(card, repo, {"fixtures": []})
    assert scoring.rescore_matches(card, rebuilt) == []


def test_rescore_tar_missing_is_hard_error(tmp_path):
    repo = _write_repo(tmp_path, _rows())
    item_paths = _model_items(repo)
    card = _model_card_with_tar(repo, item_paths)
    shutil.rmtree(os.path.join(repo, "results", "basal-x"))
    with pytest.raises(SystemExit, match="not found"):
        scoring.rescore(card, repo, {"fixtures": []})


def test_corpus_binding_errors(tmp_path):
    repo = _write_repo(tmp_path, _rows())
    card = _temporal_card(repo)
    assert cli._corpus_binding_errors(card, repo) == []
    bad = json.loads(json.dumps(card))
    bad["population"]["ids_sha256"] = "0" * 64
    errs = cli._corpus_binding_errors(bad, repo)
    assert any("ids_sha256 drift" in e for e in errs)


def test_corpus_model_card_requires_temporal_block(tmp_path):
    repo = _write_repo(tmp_path, _rows())
    card = _model_card_with_tar(repo, _model_items(repo))
    assert scoring.validate_scorecard(card) == []          # carries the block
    stripped = json.loads(json.dumps(card))
    stripped.pop("temporal_split")
    stripped["contamination"]["temporal_holdout_applied"] = False
    errs = scoring.validate_scorecard(stripped)
    assert any("must carry temporal_split" in e for e in errs)


def test_cmd_score_requires_temporal_cutoff():
    # the guard fires after corpus-set resolution, before any submission loading
    args = argparse.Namespace(layers="0.1,0.2", set="full", submission=[],
                              temporal_cutoff=None)
    with pytest.raises(SystemExit, match="required for corpus sets"):
        cli.cmd_score(args)
