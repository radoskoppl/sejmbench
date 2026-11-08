"""Margin buckets (issue #14, CODEBOOK §13) — unit tests.

Boundaries, denominator rule, macro definition and the additive
validate_scorecard consistency check.
"""
import pytest

import scoring


def test_bucket_boundaries():
    got = [scoring.margin_bucket(m) for m in (0, 1, 5, 6, 50, 51, 1000)]
    assert got == ["tie", "narrow", "narrow", "close", "close", "wide", "wide"]
    assert scoring.margin_bucket(None) is None


def test_stats_denominator_rule():
    per = [
        {"fixture": "a", "status": "scored", "layer0_1": {"correct": 1}},
        {"fixture": "b", "status": "parse_failure", "layer0_1": {"correct": 0}},
        {"fixture": "c", "status": "excluded", "layer0_1": {"correct": None}},
        {"fixture": "d", "status": "scored", "layer0_1": {"correct": 0}},
    ]
    margins = {"a": 0, "b": 3, "c": 7, "d": 100}
    st = scoring.margin_bucket_stats(per, margins, {k: k for k in margins})
    b = st["buckets"]
    assert b["tie"]["n"] == 1 and b["tie"]["accuracy"] == 1.0
    # parse failure: same rule as the headline accuracy — counts as incorrect
    assert b["narrow"]["n"] == 1 and b["narrow"]["accuracy"] == 0.0
    # excluded leaves the denominator entirely
    assert b["close"]["n"] == 0 and b["close"]["accuracy"] is None
    assert b["wide"]["n"] == 1 and b["wide"]["accuracy"] == 0.0
    # macro = unweighted mean over non-empty buckets only
    assert st["margin_macro"] == pytest.approx((1.0 + 0.0 + 0.0) / 3)


def test_stats_missing_margin_skipped():
    per = [{"fixture": "x", "status": "scored", "layer0_1": {"correct": 1}}]
    st = scoring.margin_bucket_stats(per, {"x": None}, {"x": "s1"})
    assert all(b["n"] == 0 for b in st["buckets"].values())
    assert st["n_no_margin"] == 1
    assert st["margin_macro"] is None


def test_stats_denominator_rule_counts_n_no_margin():
    per = [
        {"fixture": "a", "status": "scored", "layer0_1": {"correct": 1}},
        {"fixture": "b", "status": "scored", "layer0_1": {"correct": 0}},
    ]
    margins = {"a": 2, "b": None}  # partial GT: b has no margin_all
    st = scoring.margin_bucket_stats(per, margins, {k: k for k in margins})
    assert st["buckets"]["narrow"]["n"] == 1 and st["buckets"]["narrow"]["accuracy"] == 1.0
    assert st["n_no_margin"] == 1
    assert st["margin_macro"] == 1.0


def test_validate_margin_buckets_consistency():
    def card(n_per_bucket, n_eligible=None):
        return {"layers": {"0.1": {
            "n_eligible": (sum(n_per_bucket.values()) if n_eligible is None
                           else n_eligible),
            "margin_buckets": {"definition": "x",
                               "buckets": {k: {"n": v} for k, v in n_per_bucket.items()},
                               "margin_macro": 0.5}}}}

    ok = scoring.validate_scorecard(card({"tie": 1, "narrow": 1, "close": 0, "wide": 0}))
    assert not any("margin_buckets" in e for e in ok)
    bad = scoring.validate_scorecard(
        card({"tie": 1, "narrow": 3, "close": 0, "wide": 0}, n_eligible=2))
    assert any("margin_buckets n values" in e for e in bad)
    wrong_keys = scoring.validate_scorecard(card({"tie": 1, "edge": 1, "wide": 0, "close": 0}))
    assert any("must carry exactly" in e for e in wrong_keys)


def test_cluster_bootstrap_per_item_fallback_matches_per_item_bootstrap():
    vals = [1, 0, 1, 1, 0, 1, 1, 0]
    clusters = [f"c{i}" for i in range(len(vals))]
    assert scoring.cluster_bootstrap_ci(vals, clusters) == scoring.bootstrap_ci(vals)


def test_cluster_bootstrap_point_unchanged_and_deterministic():
    vals = [1] * 5 + [0] * 5
    clusters = ["s1"] * 5 + ["s2"] * 5
    acc, lo, hi = scoring.cluster_bootstrap_ci(vals, clusters)
    assert acc == 0.5
    assert (lo, hi) == scoring.cluster_bootstrap_ci(vals, clusters)[1:]


def test_macro_rank_verdict_per_bucket_minimum():
    v = scoring.macro_rank_verdict
    assert v({"tie": 43, "narrow": 461, "close": 13745, "wide": 51855}, True) == \
        {"ranked": True, "provisional": False}
    # 19 + 1 = 20 sum, but no bucket meets the per-bucket minimum → provisional
    assert v({"tie": 19, "wide": 1}, True) == {"ranked": False, "provisional": True}
    assert v({"tie": 43, "narrow": 461}, False) == {"ranked": False, "provisional": False}
    assert v({}, True) == {"ranked": False, "provisional": False}


def test_macro_ci_deterministic_and_covers_point():
    per = ([{"fixture": f"a{i}", "status": "scored", "layer0_1": {"correct": 1}}
            for i in range(5)] +
           [{"fixture": f"b{i}", "status": "scored", "layer0_1": {"correct": 0}}
            for i in range(3)])
    margins = {**{f"a{i}": 100 for i in range(5)}, **{f"b{i}": 0 for i in range(3)}}
    st = scoring.margin_bucket_stats(per, margins, {k: k for k in margins})
    lo, hi = st["margin_macro_ci95"]
    assert lo is not None and lo <= st["margin_macro"] <= hi
    st2 = scoring.margin_bucket_stats(per, margins, {k: k for k in margins})
    assert st2["margin_macro_ci95"] == st["margin_macro_ci95"]  # deterministic (§8.1)
