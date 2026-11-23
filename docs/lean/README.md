# Machine-checked seed-rule spec (Lean 4)

This package formalizes selected seed-rule definitions and mathematical
invariants from the frozen `CODEBOOK.md` (§1 data model, §2 metric v0.2,
§3 seed rule, §4 invariants) and proves — with the Lean 4 kernel,
machine-checked, no prose trusted — the properties listed below.

| Theorem (in `Sejmbench/SeedRule.lean`) | CODEBOOK claim |
|---|---|
| `winner_yes_iff` / `winner_no_iff` | §3: the winner is exactly the majority comparison over seed tracks |
| `tieFlag_iff` | §3: `seed_rule.tie` is `true` iff `YES == NO`, including 0:0 |
| `tie_is_explicit` | §3: a tie is represented explicitly by `tie = true` and `method = tie_seed_order`; it is not classified as a decisive majority outcome (whether a consumer reports it as "passed" is outside the model) |
| `method_majority_iff_not_tie` | §3: `method = "majority"` exactly when the comparison was decisive |
| `margin_pos_of_yes_gt` / `margin_neg_of_no_gt` / `margin_zero_of_tie` | §3: `margin` is `YES - NO` and its sign agrees with the winner |
| `abstain_never_decides` | §3: for a club already a track, an ABSTAIN record changes neither winner nor tie flag (an abstain record can *promote* a club into a track; that frozen behavior is visible in the hypothesis) |
| `abstain_increments_nActive` | §2/§3: the same record *does* increment `n_active` by one — ABSTAIN counts toward activity, it merely never decides |
| `absent_never_decides` | §1/§3: ABSENT is non-active; it changes neither winner, tie flag, nor `n_active` |
| `noVote_never_decides` | §1: NO_VOTE (term-3-era non-active value) behaves like ABSENT for an already-tracked club |
| `seedYes_le_countYes` | §0.2: seed totals see only track clubs (`inni` never decides) |
| `abs_le_n`, `abs_lt_n_when_abstain`, `polarization_nonneg`, `polarization_le_one` | §2 + §4 item 5: the integer core of `polarization = 1 - \|YES-NO\|/n ∈ [0,1]`; abstention dilutes the yes/no disparity and never sharpens it |

## Lean–Python conformance bridge (#23)

`docs/lean/test-vectors/tier1.json` carries **Tier-1 golden vectors whose
expected values are derived from the Lean definitions in `Sejmbench/SeedRule.lean`**
(winner/tie/method/margin per §3, seed totals per §0.2, `isTrack` counting all
five record kinds) — never from `seed_rule.py`, so
`tests/test_conformance.py` is a real differential test: Python must agree
with the machine-checked spec on every Tier-1 field, for 12 edge-case vectors
(both club thresholds, ABSENT/NO_VOTE qualification, 0:0 and genuine ties,
equal-size clubs, the inclusive `2k == margin` mirror boundary, NO_VOTE-era
records, `niez.`). Vector integrity is sha256-checked; a deliberate divergence
was demonstrated to fail the suite. The vectors also pin
`cf_build.py`'s GT-recomputation path (`gt_perturbed` shares the bridge).

## Counterfactual spike (issue #15) — `Sejmbench.Counterfactual`

The counterfactual input-reliance spike perturbs divisions and re-checks
whether the model's answer follows the *perturbed* tally. The perturbation
types and their ground-truth effect are machine-checked:

| Theorem (in `Sejmbench/Counterfactual.lean`) | Claim |
|---|---|
| `gt_unchanged_by_reorder` | **reorder** (P2): permuting vote records leaves winner, tie flag, method, margin and `n_active` unchanged — the ground truth is a function of the record multiset |
| `recordCount_relabel` / `isTrack_relabel` | **pseudonymize** (P3): the relabeled division's club partition is the original's transported through the bijection — track membership corresponds label-for-label, so the seed totals computed from the relabeled records are the original's (the composite folding is the pipeline's per-item assertion) |
| `flip_shift_cons` | **flip** (P1): converting a winning-side YES record of a tracked club to NO moves the totals by exactly `(−1, +1)` — kind changes never move track membership (`isTrack_flip_kind`) |
| `winner_no_of_shift` | after such a shift by `k`, the winner is `no` exactly when `2·k > seedYes − seedNo` (original winner `yes`) |
| `winner_yes_of_shift` | mirror: the winner flips to `yes` exactly when `2·k ≥ seedNo − seedYes` — the boundary is inclusive because the exact-boundary case is a TIE and the frozen tie convention resolves it to the `YES` seed |
| `flip_quota_sufficient` | the spike's quota `k = ⌊margin/2⌋ + 1` meets the strict inequality |

Scope note: as with `SeedRule`, these are properties of the
*specification*; the Python pipeline (`scripts/cf_build.py`) realizes the
constructions on concrete records and validates each item's ground truth
with `seed_rule.compute_metric`. There is no machine-checked equivalence
between the two.

## Scope — read before citing

* This is a spec artifact: it proves properties of the **specification**.
  The Lean–Python conformance bridge (above) now provides shared **Tier-1
  golden vectors** and automated **differential testing** for the seed-rule
  fields listed above. This is fixed-sample regression testing, **not** a
  machine-checked proof of semantic equivalence between the implementations.
  Extended metrics (`polarization`, `yes_share`, `margin_all`, per-track
  statistics, `inni` breakdowns) remain outside Tier 1 until corresponding
  Lean definitions and proofs are available. The counterfactual
  transformation itself is not verified by testing
  `cf_build.compute_ground_truth()` alone: its record-level correctness is
  the responsibility of the formal development in issue #24 (L1).
* The Lean specification and the Python implementation are
  *independently* validated; the pytest suite checks `seed_rule.py` against
  the golden vectors and invariants. The vote-filter
  definitions are pointwise equal to the per-club dict aggregation (each
  record belongs to exactly one club); the README of the formalization
  states this as a comment, and the threshold is pinned (`MIN_TRACK_RECORDS
  = 5`, records of *all five* kinds counting towards membership — including
  ABSENT/NO_VOTE, which is what `sum(t.values()) >= 5` does).
* Monotonicity of `|YES-NO|/n` in the abstain count is nonlinear and stays
  in the prose (noted in `abs_lt_n_when_abstain`).
* For `n = 0` the implementation conventionally reports polarization `0.0`
  (`polarization_le_one` requires `n > 0`) — a special case, not the
  formula.

## Building

Requires [elan](https://github.com/leanprover/lean4) (the Lean version
manager); the toolchain is pinned in `lean-toolchain` (currently
`leanprover/lean4:v4.36.0`). Core Lean only — no Mathlib, no external
dependencies:

```sh
elan init          # or: curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y
lake build         # inside docs/lean/
```

CI runs the same build in the `lean-spec` job of `.github/workflows/ci.yml`,
so a proof that no longer compiles fails the build loudly instead of
silently drifting from the CODEBOOK.
