#!/usr/bin/env python3
"""Tier-1 conformance suite (#23): Python seed_rule.py vs Lean-derived golden vectors.

The vectors in docs/lean/test-vectors/tier1.json carry expected values derived
from the Lean definitions (SeedRule.lean @ spec_revision) — never from
seed_rule.py, so the comparison is a real differential test, not a tautology.

Tier 1 fields: winner, tie, method, margin, seed totals (YES/NO/ABSTAIN),
n_active, and per-club track membership (isTrack counts all five kinds).
"""
import json
import os
import sys
from collections import Counter

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import seed_rule  # noqa: E402

KINDMAP = {"yes": "YES", "no": "NO", "abstain": "ABSTAIN",
           "absent": "ABSENT", "noVote": "NO_VOTE"}

VECTORS_PATH = os.path.join(ROOT, "docs", "lean", "test-vectors", "tier1.json")


def load_vectors():
    with open(VECTORS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["spec_revision"], "vectors must carry a spec_revision"
    assert data["codebook_version"], "vectors must carry a codebook_version"
    return data["vectors"]


def to_division(records):
    votes = [{"MP": r["mp"], "club": r["club"], "vote": KINDMAP[r["kind"]]}
             for r in records]
    tally = Counter(v["vote"] for v in votes)
    yes, no, ab = tally.get("YES", 0), tally.get("NO", 0), tally.get("ABSTAIN", 0)
    return {"term": 10, "sitting": 1, "votingNumber": 1,
            "date": "2025-01-01T12:00:00", "title": "conformance", "topic": None,
            "description": None, "kind": "ELECTRONIC", "yes": yes, "no": no,
            "abstain": ab, "notParticipating": 0, "present": 0,
            "totalVoted": yes + no + ab, "sittingDay": 1, "votes": votes}


def vector_id(v):
    return v["vector_id"]


def test_vectors_exist_and_cover_edge_cases():
    vectors = load_vectors()
    ids = {v["vector_id"] for v in vectors}
    # the edge-case minimum set from #23, both club thresholds included
    for required in ("T02-boundary-5-records", "T03-below-5-records",
                     "T04-6-records-4-active", "T05-7rec-3no-4novote",
                     "T07-zero-zero", "T08-tie-5-5", "T09-equal-size-clubs",
                     "T10-boundary-2k-eq-margin", "T11-novote-era",
                     "T12-niez-small"):
        assert required in ids, f"missing required edge-case vector {required}"


@pytest.mark.parametrize("v", load_vectors(), ids=vector_id)
def test_tier1_conformance(v):
    """Python must agree with the Lean-derived expected values on every Tier-1 field."""
    metric = seed_rule.compute_metric(to_division(v["input"]))
    sr = metric["seed_rule"]
    exp = v["expected"]

    # winner/tie/method/margin — the §3 core (Lean: winner_yes_iff, tieFlag_iff,
    # method_majority_iff_not_tie, margin_pos_of_yes_gt / margin_neg_of_no_gt)
    if exp["tie"]:
        assert sr["tie"] is True
        assert sr["method"] == "tie_seed_order"
        assert sr["margin"] == 0
        # on ties there is no decisive winner (winner stays the legacy field;
        # vectors record null and do not constrain seed_rule.winner)
    else:
        assert sr["tie"] is False
        assert sr["method"] == "majority"
        assert sr["winner"] == exp["winner"]
        assert sr["margin"] == exp["margin"]

    # seed totals see only track clubs (Lean: seed_cons_of_track, seedYes_le_countYes)
    st = metric["seed_totals"]
    assert st["YES"] == exp["seedYes"]
    assert st["NO"] == exp["seedNo"]
    assert st["ABSTAIN"] == exp["seedAbstain"]

    # n_active = seedYes + seedNo + seedAbstain (Lean: abstain_increments_nActive)
    assert exp["n_active"] == exp["seedYes"] + exp["seedNo"] + exp["seedAbstain"]
    assert metric["n_active"] == exp["n_active"]

    # track membership: recordCount counts ALL five kinds (Lean: isTrack/docstring)
    counts = Counter(r["club"] for r in v["input"])
    for club, want in exp["track_membership"].items():
        assert (counts[club] >= seed_rule.MIN_TRACK_RECORDS) is want, \
            f"isTrack({club!r}) diverges from the Lean definition"


def test_vector_integrity():
    """sha256 of canonical input+expected must match (tamper detection)."""
    import hashlib
    with open(VECTORS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    for v in data["vectors"]:
        canon = json.dumps({"input": v["input"], "expected": v["expected"]},
                           sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        assert hashlib.sha256(canon.encode("utf-8")).hexdigest() == v["sha256"], \
            f"vector {v['vector_id']} failed integrity"


def test_cf_build_gt_path_agrees_with_vectors():
    """The counterfactual GT recomputation (cf_build uses seed_rule.compute_metric)
    must land on the same GT as the vectors — the perturbation pipeline shares the bridge."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    vectors = load_vectors()
    basic = next(v for v in vectors if v["vector_id"] == "T01-basic-majority")
    metric = seed_rule.compute_metric(to_division(basic["input"]))
    # cf_build reads exactly these fields for gt_original / gt_perturbed
    assert metric["seed_rule"]["winner"] == basic["expected"]["winner"]
    assert metric["seed_rule"]["tie"] == basic["expected"]["tie"]
    assert metric["seed_rule"]["method"] == basic["expected"]["method"]
