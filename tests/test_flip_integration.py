#!/usr/bin/env python3
"""Integration test: the real Python flip vs the formal MaskBridge model.

Lean (Sejmbench/MaskBridge.lean @ 9dbcee7) proves:
  flipAtIndices d idxs lose = flipFrom d (maskOf idxs) lose 0
  (flipAtIndices_eq_flipFrom), where flipAtIndices is
  List.mapIdx (fun i r => if i ∈ idxs then flipAt lose r else r) d,
and, for unique in-range idxs (selFrom_maskOf_eq_length):
  selFrom (maskOf idxs) 0 n = idxs.length.

These tests check the REAL Python updater (cf_build.apply_flip) against the
same position-wise specification, projected to the (club, vote) fields the
Lean Record models, plus the count agreement on synthetic divisions — the
third level of the mask-bridge trust chain (review of 7b5b496, §4):
  index list → Lean mask      proved
  Lean mask → formal flip     proved
  real Python → formal flip   THIS FILE
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)
import cf_build  # noqa: E402


def _project(votes):
    """The (club, vote) projection the Lean Record models."""
    return [(v["club"], v["vote"]) for v in votes]


def _model_flip(votes, indices, lose_vote):
    """Literal mirror of the Lean flipAtIndices: position i is flipped iff
    i ∈ idxs (maskOf), all other records pass through unchanged."""
    idxs = set(indices)
    return [(v["club"], lose_vote if i in idxs else v["vote"])
            for i, v in enumerate(votes)]


VOTES = [{"club": "A", "vote": "YES"}, {"club": "B", "vote": "NO"},
         {"club": "C", "vote": "ABSTAIN"}, {"club": "A", "vote": "YES"}]


def test_apply_flip_matches_formal_model():
    for idxs in ([], [0], [3], [0, 3], [1, 2]):
        out = cf_build.apply_flip(VOTES, idxs, "NO")
        assert _project(out) == _model_flip(VOTES, idxs, "NO")


def test_apply_flip_is_pure():
    out = cf_build.apply_flip(VOTES, [0], "NO")
    assert VOTES[0]["vote"] == "YES"           # original untouched
    assert out is not VOTES and out[0] is not VOTES[0]


def test_apply_flip_range_and_uniqueness():
    with pytest.raises(ValueError):
        cf_build.apply_flip(VOTES, [4], "NO")      # out of range
    with pytest.raises(ValueError):
        cf_build.apply_flip(VOTES, [0, 0], "NO")   # duplicate


def test_apply_flip_negative_index_rejected():
    with pytest.raises(ValueError):
        cf_build.apply_flip(VOTES, [-1], "NO")


def test_count_agreement_mirror():
    # selFrom (maskOf idxs) 0 n == len(idxs) for unique in-range idxs
    votes = [{"club": f"C{i}", "vote": "YES"} for i in range(10)]
    for idxs in ([], [0], [9], [1, 4, 7], [0, 2, 4, 6, 8]):
        assert cf_build.mask_hits(votes, idxs) == len(idxs)


def test_bool_index_rejected():
    # isinstance(True, int) is True in Python — a bare bool must not pass
    # as an index (hardening suggestion from the review of 9dbcee7/5e49124).
    with pytest.raises(ValueError):
        cf_build.apply_flip(VOTES, [True], "NO")
    with pytest.raises(ValueError):
        cf_build.apply_flip(VOTES, [False], "NO")


def _all_subsets(n):
    for mask in range(1 << n):
        yield [i for i in range(n) if (mask >> i) & 1]


@pytest.mark.parametrize("lose", ["NO", "YES"])
@pytest.mark.parametrize("n", range(9))
def test_exhaustive_subsets(n, lose):
    # Every subset of indices for divisions of length 0..8, in both flip
    # directions — the real updater vs the position-wise model (review of
    # 9dbcee7/5e49124, hardening B).
    votes = [{"club": "A" if i % 2 else "B", "vote": "YES" if lose == "NO" else "NO"}
             for i in range(n)]
    for idxs in _all_subsets(n):
        out = cf_build.apply_flip(votes, idxs, lose)
        assert _project(out) == _model_flip(votes, idxs, lose)
        assert cf_build.mask_hits(out, idxs) == len(idxs)
