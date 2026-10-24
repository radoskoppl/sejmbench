"""Unit tests: hand-computed synthetic divisions (no network)."""

import os

import pytest

from seed_rule import compute_metric

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")


def division(votes, **meta):
    d = {"term": 10, "sitting": 0, "votingNumber": 0, "title": "test", "date": "2024-01-01"}
    d.update(meta)
    d["votes"] = [{"MP": i, "club": c, "vote": vo} for i, (c, vo) in enumerate(votes)]
    return d


def test_unanimous_track_zero_polarization():
    votes = [("A", "YES")] * 6 + [("B", "YES")] * 6
    r = compute_metric(division(votes))
    assert r["tracks"]["A"]["polarization"] == 0.0
    assert r["tracks"]["A"]["yes_share"] == 1.0
    assert r["seed_rule"]["winner"] == "yes"
    assert r["seed_rule"]["margin"] == 12


def test_split_track_half_polarization():
    votes = [("A", "YES")] * 3 + [("A", "NO")] * 3
    r = compute_metric(division(votes))
    assert r["tracks"]["A"]["polarization"] == 1.0
    assert r["tracks"]["A"]["yes_share"] == 0.5


def test_abstain_counts_in_denominator():
    votes = [("A", "YES")] * 4 + [("A", "ABSTAIN")] * 6
    r = compute_metric(division(votes))
    assert r["tracks"]["A"]["yes_share"] == pytest.approx(0.4)
    # ABSTAIN dilutes the split: gap |YES-NO| = 4 over n = 10 -> 1 - 0.4
    assert r["tracks"]["A"]["polarization"] == pytest.approx(0.6)


def test_small_club_is_inni():
    votes = [("A", "YES")] * 6 + [("solo", "NO")]
    r = compute_metric(division(votes))
    assert "solo" in r["inni_clubs"]
    assert "solo" not in r["tracks"]


def test_tie_resolves_by_seed_order():
    votes = [("A", "YES")] * 5 + [("B", "NO")] * 5
    r = compute_metric(division(votes))
    assert r["seed_rule"]["winner"] == "yes"
    assert r["seed_rule"]["method"] == "tie_seed_order"
    assert r["seed_rule"]["margin"] == 0


def test_no_majority_when_no_smaller():
    votes = [("A", "NO")] * 7 + [("B", "YES")] * 4
    r = compute_metric(division(votes))
    assert r["seed_rule"]["winner"] == "no"
    # seed margin counts only scored tracks (B has 4 records -> inni)
    assert r["seed_rule"]["margin"] == -7
    # margin_all counts every record, including inni
    assert r["margin_all"] == -3


def test_real_fixture_self_consistency():
    """Tallies recomputed from vote records must equal the API headline counts."""
    path = os.path.join(FIXTURES, "term10-s6-v14-tight.json")
    if not os.path.exists(path):  # fixtures fetched separately; skip if absent
        pytest.skip("fixture not fetched")
    import json

    d = json.load(open(path, encoding="utf-8"))
    r = compute_metric(d)
    # seed + inni must reconstruct the API headline counts exactly
    assert r["seed_totals"]["YES"] + r["inni_totals"]["YES"] == d["yes"]
    assert r["seed_totals"]["NO"] + r["inni_totals"]["NO"] == d["no"]
    assert r["seed_totals"]["ABSTAIN"] + r["inni_totals"]["ABSTAIN"] == d["abstain"]
    assert r["n_active"] + (r["inni_totals"]["YES"] + r["inni_totals"]["NO"]
                            + r["inni_totals"]["ABSTAIN"]) == d["totalVoted"]
    assert 0.0 <= r["overall_polarization"] <= 1.0
