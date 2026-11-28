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
| `recordCount_relabel` / `isTrack_relabel` | **pseudonymize** (P3): the relabeled division's club partition is the original's transported through the bijection — track membership corresponds label-for-label |
| `gt_unchanged_by_pseudonymize` | **pseudonymize, composite** (P3): the relabeled division's seed totals, tie flag, margin, winner, method and `n_active` are *the original's* — the ground truth never depended on the label names |
| `recordCount_flipFrom` / `isTrack_flipFrom` | **flip** (P1): the per-record flip moves club totals exactly by the shift amount `k = selFrom S off d.length` — kind changes never move track membership |
| `selected_must_be_source_kind` / `selected_must_be_track` (in `Sejmbench/FlipRecord.lean`) | **eligibility contract** (round-6/7 P-list): under an `EligibleFlip` certificate, a mask-selected position must carry a tracked source-kind record; the contrapositives `no_cert_of_wrong_kind` / `no_cert_of_off_track` state a bad mask admits no certificate, and `selected_all_*` lift the test to every selected position of the slice |
| `winner_no_of_shift` | after such a shift by `k`, the winner is `no` exactly when `2·k > seedYes − seedNo` (original winner `yes`) |
| `winner_yes_of_shift` | mirror: the winner flips to `yes` exactly when `2·k ≥ seedNo − seedYes` — the boundary is inclusive because the exact-boundary case is a TIE and the frozen tie convention resolves it to the `YES` seed |
| `flip_quota_sufficient` | the spike's quota `k = ⌊margin/2⌋ + 1` meets the strict inequality |

Mask bridge (`Sejmbench/MaskBridge.lean`) — the Python index list
(`cf_build.py`: `flipped_record_indices`, sorted, sampled without
replacement, in-range) and the abstract mask `S : Nat → Bool` are linked
in both directions:

| Theorem (in `Sejmbench/MaskBridge.lean`) | Claim |
|---|---|
| `flipAtIndices_eq_flipFrom` | the in-place Python flip over an index list IS the certified `flipFrom d (maskOf idxs) lose 0` — transformation agreement |
| `eligibleFlip_of_indices` | if every listed index points at an eligible record, the derived mask satisfies the `EligibleFlip` certificate (the Python invariant `flipped_idx ⊆ eligible` enters as a hypothesis) |
| `selFrom_maskOf_eq_length` | for a Nodup in-range index list, the shift amount `k = selFrom (maskOf idxs) 0 n` equals `idxs.length` — the count never drifts from the sampled list |
| `selectedFrom_length` / `selectedFrom_nodup` / `selectedFrom_bound` / `selectedFrom_mem` | the canonical index list of any mask: its length IS `selFrom` (selectedCount = selFrom), it is Nodup, in-window, and its members are exactly the selected positions |
| `maskOf_selectedFrom` | the mask derived back from the canonical index list agrees with `S` at every in-window position — no information lost on the window |
| `flip_eq_flipAtIndices` | the abstract flip over any mask equals the Python-style flip over its canonical index list (both directions closed) |
| `selFrom_maskOf_selectedFrom` | count round-trip: `selFrom` is invariant under the list → mask → list cycle |

Seed shifts land directly from the certificate layer
(`Sejmbench/SeedCount.lean`): `seedYes_dec_of_eligible` /
`seedNo_inc_of_eligible` (YES → NO), `seedNo_dec_of_eligible` /
`seedYes_inc_of_eligible` (NO → YES), the ABSTAIN invariants
`seedAbstain_flip_*_of_eligible`, and the `nActive_flip_*_of_eligible`
capstones — composed with the thresholds by
`winner_no_of_eligible_flip` / `winner_yes_of_eligible_flip` (with iff
wrappers and the inclusive `2k = margin` boundary family).

Scope note: as with `SeedRule`, these are properties of the
*specification*; the Python pipeline (`scripts/cf_build.py`) realizes the
constructions on concrete records and validates each item's ground truth
with `seed_rule.compute_metric`. There is no machine-checked equivalence
between the two.

## Pool & stratification (issue #24) — `Sejmbench.Pool`

The pool layer over `ModelResponsePair`s: each `PoolItem` stores only
`itemId` and the candidate pair — the cell key
`(perturbedGT, direction, originalMarginBand)` is *computed* from the pair,
not stored (design frozen by the round-4 review of `49401d2`). The
aggregation contract is Σnᵢ/Σdᵢ on raw counters; machine-checked:

| Theorem (in `Sejmbench/Pool.lean`) | Claim |
|---|---|
| `cellCount6_sum` / `cellCount_sum` | the 6 cells of `(perturbedGT, direction, band)` partition the pool — total cell occupancy = `pool.length` |
| `cellN_add` / `cellAnswerCount_add` / `cellAnswerCount_eq` | every per-cell counter is additive over any split of the pool; a cell's answer-level denominator is exactly `2·N` |
| `contingency_all_sum` | the full contingency table (2 directions × 5×5 answer pairs = 50 entries) sums to `pool.length` |
| `PoolItem.toResponseSet` + `stickyNum_eq_responseSet` / `originalCorrectNum_eq_responseSet` / `strictNum_eq_responseSet` / `incidentalNum_eq_responseSet` | the pool projection onto the #22 `ResponseSet` contract counts identically — pool-level and response-set-level numbers coincide |
| `accuracy_agg` / `perturbedAccuracy_agg` / `strictUnconditional_agg` / `incidental_agg` / `coverage_agg` / `abstainRate_agg` / `refusalRate_agg` / `unresolvableRate_agg` | pool-level rates are exactly the `ResponseSet` rates computed from *summed per-cell counters* (Σnᵢ/Σdᵢ); aggregation never averages `Option Rate` values |
| `strictConditional_agg` / `balancedPerturbedAccuracy_agg` | the same Σnᵢ/Σdᵢ contract for the weighted rates — denominators `originalCorrectNum` resp. the per-class perturbed-GT band counts |
| `accuracyAgg_stratified` / `strictUnconditionalAgg_stratified` / `perturbedAccuracyAgg_stratified` / `incidentalAgg_stratified` / `coverageAgg_stratified` / `abstainRateAgg_stratified` / `refusalRateAgg_stratified` / `unresolvableRateAgg_stratified` / `strictConditionalAgg_stratified` / `balancedPerturbedAccuracyAgg_stratified` | stratification invariance, all ten Σnᵢ/Σdᵢ aggregates: `aggregate pool` = the two strata `pool.filter Q` / `pool.filter (¬Q)` recombined at the counter level; definedness is inherited from the whole pool (`none` iff the whole pool lacks the denominator), never by coercing a `none` stratum to zero |
| `manifestOf_itemIds` / `itemId_unique` / `conforms_unique` | manifest conformance: every item has a canonically matching `ManifestEntry`, `itemId`s are unique under `poolWellFormed`, and an entry matches at most one item — non-conformance is a defect, never an ambiguity |

Open conditions stay explicit predicates on the pool: `poolWellFormed`
(unique `itemId`s), `poolLeakageGate` (the best constant perturbed-class
predictor stays below 0.55) and `minCellSize` (minimum cell occupancy,
independent of the gate). No unweighted-mean claim is made anywhere.

## Proof audit (L1 closure)

Final sweep over the complete library (`lake build` clean, zero warnings;
grep for `sorry`/`admit` clean):

* **Axiom check:** `#print axioms` executed on **all 427 declarations**
  (`defs`, `theorem`s and structures across `SeedRule`, `Counterfactual`,
  `FlipRecord`, `SeedCount`, `MaskBridge`, `FlipPair`, `EvaluationMetrics`,
  `Pool`). Every declaration's axiom set is a subset of
  `[propext, Classical.choice, Quot.sound]`; zero `sorryAx`; no
  `EligibleFlip.rec` or other new axioms anywhere.
* **Closed properties** (machine-checked, all of the tables above): the
  seed-rule contract (§3 winner/tie/method/margin, abstention semantics,
  activity counting, polarization integer core), the counterfactual
  transformations (reorder/pseudonymize/flip with record- and
  kind-level exactness), the eligibility contract (`selected_must_be_*`,
  `selected_all_*`, contrapositives), the seed shifts from the
  `EligibleFlip` certificate in both directions, the threshold
  compositions (`winner_*_of_shift`, boundary family), and the Python
  indices ↔ mask bridge in both directions with the count round-trip.
* **Still open / deliberately outside the model:** monotonicity of
  `|YES−NO|/n` in the abstain count stays in prose (nonlinear; noted at
  `abs_lt_n_when_abstain`); `n = 0` polarization is an implementation
  convention, not the formula; the Python pipeline realizes the
  constructions on concrete records without a machine-checked semantic
  equivalence to the Lean spec (fixed-sample differential testing only);
  statistical-independence-flavored claims are never formalized — the
  stratification contract is exact per-counter bookkeeping.

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
