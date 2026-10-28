"""Tests for the SejmBench harness scorer (issue #4).

Pinned constants (PROMPT_HASH, SET_HASH) are version events: changing the
reference prompt template or the fixture set changes them by design, and the
assertions here make that loud rather than silent.
"""

import argparse
import copy
import importlib.util
import json
import os

import pytest

import scoring
import seed_rule

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROMPT_HASH = "d937dfcbe2e92cef97c292353371cd40017da7c226587f7da31a09682db20dc6"
SET_HASH = "d465a66a92ec27f779f0fb75f6ed2e1a51cc7a66d64cf62eb2bfb469e07a9f02"
LANDSLIDE = "term10-s1-v2-landslide.json"
TIGHT = "term10-s6-v14-tight.json"


@pytest.fixture(scope="module")
def manifest():
    return scoring.load_manifest(ROOT)


@pytest.fixture(scope="module")
def fixtures(manifest):
    return {LANDSLIDE: scoring.load_fixture(ROOT, LANDSLIDE, manifest),
            TIGHT: scoring.load_fixture(ROOT, TIGHT, manifest)}


def item(fixture, raw_output, **extra):
    base = {"model": "test-model", "date": "2026-10-28", "temperature": 0,
            "prompt_hash": PROMPT_HASH, "declared_cutoff": "unknown",
            "raw_output": raw_output, "fixture": fixture, "_path": f"<test:{fixture}>"}
    base.update(extra)
    return base


def meta_for(fixtures_dict, manifest):
    return {
        "benchmark_version": "0.3", "metric_version": "0.3", "harness_version": "test",
        "set": "public", "set_hash": scoring.canonical_set_hash(manifest),
        "fixture_entries": {os.path.basename(e["file"]): e for e in manifest["fixtures"]},
        "model": {"id": "test-model", "provider": "test", "revision": "rev-1",
                  "identity_mutable_alias": False, "call_date": "2026-10-28",
                  "decoding": {"temperature": 0}},
        "submission": {"kind": "model", "files": []},
        "evaluation_date": "2026-10-28",
        "contamination": {"declared_cutoff": "unknown", "temporal_holdout_applied": False},
        "token_usage": None, "cost_estimate": None,
    }


def perfect_answer(division):
    m = seed_rule.compute_metric(division)
    return {"winner": m["seed_rule"]["winner"],
            "tracks": [{"club": c, "yes_share": t["yes_share"], "polarization": t["polarization"]}
                       for c, t in sorted(m["tracks"].items())]}


def synthetic_division(votes):
    return {"term": 99, "sitting": 1, "votingNumber": 1, "title": "synthetic",
            "date": "2026-01-01",
            "yes": sum(1 for v in votes if v["vote"] == "YES"),
            "no": sum(1 for v in votes if v["vote"] == "NO"),
            "abstain": sum(1 for v in votes if v["vote"] == "ABSTAIN"),
            "totalVoted": len(votes), "votes": votes}


# ------------------------------------------------------------------ pins ----

def test_prompt_hash_pinned():
    assert scoring.reference_prompt_hash() == PROMPT_HASH
    assert "głosowanie imienne" in scoring.REFERENCE_PROMPT
    assert "{VOTE_RECORDS}" in scoring.REFERENCE_PROMPT


def test_set_hash_pinned(manifest):
    assert scoring.canonical_set_hash(manifest) == SET_HASH


def test_set_hash_subset_differs(manifest):
    subset = [e for e in manifest["fixtures"] if LANDSLIDE in e["file"]]
    assert scoring.canonical_set_hash(manifest, [e["file"] for e in subset]) != SET_HASH


# ---------------------------------------------------------------- parser ----

def test_parse_scored_variants():
    good = {"winner": "yes", "tracks": []}
    assert scoring.parse_answer(good) == ("scored", {"winner": "yes", "tracks": []})
    assert scoring.parse_answer(json.dumps(good))[0] == "scored"
    status, parsed = scoring.parse_answer('Sure: {"winner": "no", "tracks": []} — done.')
    assert status == "scored" and parsed["winner"] == "no"


def test_parse_refusal():
    for raw in (None, "", "   "):
        assert scoring.parse_answer(raw) == ("refusal", None)


def test_parse_failure():
    for raw in ("no json here", '{"tracks": []}', '{"winner": true, "tracks": []}'):
        assert scoring.parse_answer(raw)[0] == "parse_failure"


def test_parse_abstain():
    assert scoring.parse_answer('{"winner": "maybe", "tracks": []}')[0] == "abstain"
    assert scoring.parse_answer('{"abstain": true}')[0] == "abstain"


def test_parse_normalizes_case():
    status, parsed = scoring.parse_answer('{"winner": "YES", "tracks": []}')
    assert status == "scored" and parsed["winner"] == "yes"


# --------------------------------------------------------------- layer 0.1 ----

def test_gt_winners_real_fixtures(fixtures):
    for name, division in fixtures.items():
        assert seed_rule.compute_metric(division)["seed_rule"]["winner"] == "yes"


def test_winner_exact_match(fixtures):
    hit = scoring.score_item(item(LANDSLIDE, {"winner": "yes", "tracks": []}),
                             fixtures[LANDSLIDE], LANDSLIDE)
    miss = scoring.score_item(item(LANDSLIDE, {"winner": "no", "tracks": []}),
                              fixtures[LANDSLIDE], LANDSLIDE)
    assert hit["layer0_1"]["correct"] == 1 and hit["status"] == "scored"
    assert miss["layer0_1"]["correct"] == 0


def test_tie_convention_synthetic():
    votes = [{"MP": i, "club": "X", "firstName": "A", "lastName": f"L{i}", "secondName": None,
              "vote": v} for i, v in enumerate(["YES"] * 5 + ["NO"] * 5, start=1)]
    division = synthetic_division(votes)
    metric = seed_rule.compute_metric(division)
    assert metric["seed_rule"]["tie"] is True and metric["seed_rule"]["winner"] == "yes"
    yes = scoring.score_item(item("tie.json", {"winner": "yes", "tracks": []}), division, "tie.json")
    no = scoring.score_item(item("tie.json", {"winner": "no", "tracks": []}), division, "tie.json")
    assert yes["layer0_1"]["correct"] == 1 and no["layer0_1"]["correct"] == 0


# --------------------------------------------------------------- layer 0.2 ----

def test_tracks_exact_zero_mae(fixtures):
    ans = perfect_answer(fixtures[TIGHT])
    got = scoring.score_item(item(TIGHT, ans), fixtures[TIGHT], TIGHT)
    l2 = got["layer0_2"]
    assert l2["mae_yes_share"] == 0.0 and l2["mae_polarization"] == 0.0
    assert l2["n_matched"] == l2["n_tracks_gt"] == 6
    assert l2["n_missing"] == 0 and l2["n_extra"] == 0


def test_missing_track_max_deviation(fixtures):
    ans = perfect_answer(fixtures[LANDSLIDE])
    dropped = ans["tracks"][0]["club"]
    ans["tracks"] = ans["tracks"][1:]
    l2 = scoring.score_item(item(LANDSLIDE, ans), fixtures[LANDSLIDE], LANDSLIDE)["layer0_2"]
    assert l2["n_missing"] == 1 and l2["missing_clubs"] == [dropped]
    assert l2["mae_yes_share"] == pytest.approx(1.0 / 6)
    assert l2["mae_polarization"] == pytest.approx(1.0 / 6)


def test_extra_track_recorded_not_penalized(fixtures):
    ans = perfect_answer(fixtures[LANDSLIDE])
    ans["tracks"].append({"club": "GHOST", "yes_share": 0.5, "polarization": 0.5})
    l2 = scoring.score_item(item(LANDSLIDE, ans), fixtures[LANDSLIDE], LANDSLIDE)["layer0_2"]
    assert l2["n_extra"] == 1 and l2["extra_clubs"] == ["GHOST"]
    assert l2["mae_yes_share"] == 0.0


def test_invalid_track_values_treated_missing(fixtures):
    ans = perfect_answer(fixtures[LANDSLIDE])
    ans["tracks"][0]["yes_share"] = 1.5
    l2 = scoring.score_item(item(LANDSLIDE, ans), fixtures[LANDSLIDE], LANDSLIDE)["layer0_2"]
    assert l2["n_invalid_entries"] == 1
    assert l2["n_missing"] == 1 and l2["mae_yes_share"] == pytest.approx(1.0 / 6)


def test_tracks_not_a_list(fixtures):
    ans = {"winner": "yes", "tracks": "broken"}
    entry = scoring.score_item(item(LANDSLIDE, ans), fixtures[LANDSLIDE], LANDSLIDE)
    assert entry["status"] == "scored"
    assert entry["layer0_2"]["n_invalid_entries"] == 1
    assert entry["layer0_2"]["n_missing"] == entry["layer0_2"]["n_tracks_gt"] == 6
    assert entry["layer0_2"]["mae_yes_share"] == 1.0


# ------------------------------------------------------- counts / headline ----

def test_abstain_and_missing_count_as_incorrect(fixtures, manifest):
    items = {LANDSLIDE: item(LANDSLIDE, {"winner": "yes", "tracks": []}),
             TIGHT: item(TIGHT, '{"winner": "cannot say", "tracks": []}')}
    card = scoring.build_scorecard(fixtures, items, [], meta_for(fixtures, manifest))
    l01, l02 = card["layers"]["0.1"], card["layers"]["0.2"]
    assert l01["n_scored"] == 1 and l01["n_abstained"] == 1
    assert l01["accuracy"] == 0.5  # abstain = incorrect (§9.4)
    assert l02["n_scored"] == 1 and l02["answer_coverage"] == 0.5  # §8.6


def test_missing_submission_file(fixtures, manifest):
    items = {LANDSLIDE: item(LANDSLIDE, {"winner": "yes", "tracks": []})}
    card = scoring.build_scorecard(fixtures, items, [], meta_for(fixtures, manifest))
    l01 = card["layers"]["0.1"]
    assert l01["n_missing_files"] == 1 and l01["accuracy"] == 0.5
    missing = next(it for it in card["items"] if it["status"] == "missing")
    assert missing["exclusion_reason"] == "no submission file for fixture"
    assert missing["layer0_1"]["correct"] == 0


def test_submission_contract_violations_recorded(fixtures, manifest):
    items = {LANDSLIDE: item(LANDSLIDE, {"winner": "yes", "tracks": []}, temperature=1,
                             prompt_hash="deadbeef")}
    card = scoring.build_scorecard(fixtures, items, [], meta_for(fixtures, manifest))
    assert any("temperature" in p for p in card["problems"])
    assert any("prompt_hash" in p for p in card["problems"])


# -------------------------------------------------------------- statistics ----

def test_bootstrap_deterministic_and_sane():
    vals = [0.0, 1.0] * 25
    a = scoring.bootstrap_ci(vals)
    b = scoring.bootstrap_ci(vals)
    assert a == b
    mean, lo, hi = a
    assert lo <= mean <= hi
    assert scoring.bootstrap_ci([1.0]) == (1.0, 1.0, 1.0)


def test_paired_bootstrap_semantics():
    same = scoring.paired_bootstrap([0.0] * 20)
    assert same[0] == 0.0 and same[1] == 0.0 and same[2] == 0.0
    decisive = scoring.paired_bootstrap([1.0] * 20)
    assert decisive[0] == 1.0 and decisive[1] > 0  # ranked: CI excludes 0


# --------------------------------------------------------------- scorecard ----

def test_scorecard_validation(manifest, fixtures):
    items = {n: item(n, perfect_answer(d)) for n, d in fixtures.items()}
    card = scoring.build_scorecard(fixtures, items, [], meta_for(fixtures, manifest))
    assert scoring.validate_scorecard(card) == []
    broken = copy.deepcopy(card)
    del broken["set_hash"]
    assert any("set_hash" in e for e in scoring.validate_scorecard(broken))
    broken = copy.deepcopy(card)
    broken["layers"]["0.1"]["n_total"] = 3
    assert any("counts sum" in e for e in scoring.validate_scorecard(broken))


def test_perfect_submission_full_pipeline(fixtures, manifest):
    items = {n: item(n, perfect_answer(d)) for n, d in fixtures.items()}
    card = scoring.build_scorecard(fixtures, items, [], meta_for(fixtures, manifest))
    assert card["layers"]["0.1"]["accuracy"] == 1.0
    assert card["layers"]["0.2"]["mae_yes_share"] == 0.0
    assert card["problems"] == []
    again = scoring.build_scorecard(fixtures, items, [], meta_for(fixtures, manifest))
    assert json.dumps(card, sort_keys=True) == json.dumps(again, sort_keys=True)


# ---------------------------------------------------------------- baselines ----

def test_baseline_majority_class(fixtures, manifest):
    items = scoring.baseline_items("majority-class", fixtures, manifest)
    card = scoring.build_scorecard(fixtures, items, [], scoring.baseline_meta(
        "majority-class", "public", manifest, "test"))
    assert card["layers"]["0.1"]["accuracy"] == 1.0  # both GT winners are "yes"
    landslide = next(i for i in card["items"] if i["fixture"] == LANDSLIDE)
    tight = next(i for i in card["items"] if i["fixture"] == TIGHT)
    assert landslide["layer0_2"]["mae_yes_share"] == 0.0   # unanimous yes
    assert tight["layer0_2"]["mae_yes_share"] > 0.0        # mixed shares penalize the baseline
    assert card["problems"] == []


def test_baseline_random_deterministic(fixtures, manifest):
    a = scoring.baseline_items("random", fixtures, manifest)
    b = scoring.baseline_items("random", fixtures, manifest)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    card = scoring.build_scorecard(fixtures, a, [], scoring.baseline_meta(
        "random", "public", manifest, "test"))
    acc = card["layers"]["0.1"]["accuracy"]
    assert acc in (0.0, 0.5, 1.0) and card["problems"] == []


def test_unknown_baseline_raises(fixtures, manifest):
    with pytest.raises(ValueError):
        scoring.baseline_items("nope", fixtures, manifest)


# ------------------------------------------------------------------ rescore ----

def test_rescore_reproduces_baseline(fixtures, manifest):
    items = scoring.baseline_items("majority-class", fixtures, manifest)
    card = scoring.build_scorecard(fixtures, items, [], scoring.baseline_meta(
        "majority-class", "public", manifest, "test"))
    assert scoring.rescore_matches(card, scoring.rescore(card, ROOT, manifest)) == []


def test_rescore_detects_drift(fixtures, manifest):
    items = scoring.baseline_items("majority-class", fixtures, manifest)
    card = scoring.build_scorecard(fixtures, items, [], scoring.baseline_meta(
        "majority-class", "public", manifest, "test"))
    card["layers"]["0.1"]["accuracy"] = 0.0
    assert scoring.rescore_matches(card, scoring.rescore(card, ROOT, manifest)) != []


def test_cli_rescore_check_and_layer1_refusal(fixtures, manifest, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "sejmbench_cli", os.path.join(ROOT, "scripts", "sejmbench.py"))
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    # layer 1 refuses until the dictionary freezes (CODEBOOK §10)
    with pytest.raises(SystemExit):
        cli.main(["score", "--submission", "x", "--layers", "1"])

    items = scoring.baseline_items("majority-class", fixtures, manifest)
    card = scoring.build_scorecard(fixtures, items, [], scoring.baseline_meta(
        "majority-class", "public", manifest, "test"))
    good = tmp_path / "baseline.scorecard.json"
    good.write_text(json.dumps(card, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    assert cli.cmd_rescore_check(argparse.Namespace(scorecards=[str(good)])) == 0

    drifted = copy.deepcopy(card)
    drifted["layers"]["0.1"]["accuracy"] = 0.0
    bad = tmp_path / "drifted.scorecard.json"
    bad.write_text(json.dumps(drifted, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    assert cli.cmd_rescore_check(argparse.Namespace(scorecards=[str(bad)])) == 1
