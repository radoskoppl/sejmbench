# Machine-checked seed-rule spec (Lean 4)

This package formalizes the frozen definitions of `CODEBOOK.md` (§1 data
model, §2 metric v0.2, §3 seed rule, §4 invariants) and proves — with the
Lean 4 kernel, machine-checked, no prose trusted — the properties the
CODEBOOK states about them:

| Theorem (in `Sejmbench/SeedRule.lean`) | CODEBOOK claim |
|---|---|
| `winner_yes_iff` / `winner_no_iff` | §3: the winner is exactly the majority comparison over seed tracks |
| `tieFlag_iff` | §3: `seed_rule.tie` is `true` iff `YES == NO`, including 0:0 |
| `tie_never_passed` | §3: a tie keeps the scorer-convention winner and is labelled `tie_seed_order`; never "the motion passed" |
| `method_majority_iff_not_tie` | §3: `method = "majority"` exactly when the comparison was decisive |
| `margin_pos_of_yes_gt` / `margin_neg_of_no_gt` / `margin_zero_of_tie` | §3: `margin` is `YES - NO` and its sign agrees with the winner |
| `abstain_never_decides` | §3: `ABSTAIN` counts toward `n_active` but never decides (for a club already a track — an abstain record can *promote* a club into a track; that frozen behavior is visible in the hypothesis) |
| `absent_never_decides` | §1/§3: ABSENT is non-active; it changes neither winner, tie flag, nor `n_active` |
| `seedYes_le_countYes` | §0.2: seed totals see only track clubs (`inni` never decides) |
| `abs_le_n`, `abs_lt_n_when_abstain`, `polarization_nonneg`, `polarization_le_one` | §2 + §4 item 5: the integer core of `polarization = 1 - \|YES-NO\|/n ∈ [0,1]`; abstention dilutes the yes/no disparity and never sharpens it |

## Scope — read before citing

* This is a spec artifact: it proves properties of the **specification**.
  Equivalence of the reference implementation `seed_rule.py` to this spec is
  enforced by the pytest suite (`tests/`), not here. The vote-filter
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
