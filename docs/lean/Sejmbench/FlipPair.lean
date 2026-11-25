import Sejmbench.SeedCount
import Sejmbench.MaskBridge

/-!
# FlipPair (issue #24, L3 — CounterfactualV2, first component)

The experiment unit for CounterfactualV2. Design decision (review of the
mask bridge, 2026-11-25): the two ground truths are **derived from the
specification**, never given independently — the original GT is `winner
original` and the perturbed GT is `winner` of the division produced by the
verified transformation. The `hperturbed` field ties the stored perturbed
division to `flipFrom original (maskOf idxs) lose 0`, so a `FlipPair`
cannot exist with a declared perturbed GT that disagrees with the actual
transformation of its records.

Both flip directions get their own structure, mirroring the two
certificate types of `FlipRecord`/`SeedCount` (YES→NO over `isYesKind`,
NO→YES over `isNoKind`). The reversal theorems reuse the iff-wrappers of
`SeedCount` plus the index contract of `MaskBridge`: under the experiment
quota (`2k > margin`, strict for YES→NO; `2k ≥ margin`, inclusive for
NO→YES) the two GTs provably differ — the pair is a *genuine* reversal
pair by construction.
-/

namespace Sejmbench

/-! ## YES → NO (the original winner is YES) -/

/-- A YES→NO flip experiment: original division, a unique in-range index
list of eligible (tracked, winning-side) records, and the perturbed
division tied to the verified transformation. -/
structure FlipPair where
  /-- The original division. -/
  original : Division
  /-- Indices of the records flipped from YES to NO (unique, in range,
  eligible by `helig`). -/
  idxs : List Nat
  /-- The perturbed division — tied to the formal transformation. -/
  perturbed : Division
  /-- The perturbed division IS the certified flip of the original. -/
  hperturbed : perturbed = flipFrom original (maskOf idxs) VoteKind.no 0
  /-- Indices are unique (`random.sample` / `Nodup`). -/
  hnodup : idxs.Nodup
  /-- Indices are in range (`enumerate`). -/
  hrange : ∀ i ∈ idxs, i < original.length
  /-- Each pointed record is a tracked club's winning-side vote. -/
  helig : ∀ i ∈ idxs,
    isTrack original original[i]!.club ∧ isYesKind original[i]!.kind
  /-- The original comparison was decisive (experiment contract #24: the
  generator skips `tie`/non-majority items). A tie would be resolved to
  YES by convention, so `seedNo original < seedYes original` is the
  majority condition for the YES→NO direction. -/
  horiginalMajority : seedNo original < seedYes original

/-- The original ground truth — derived, not stored. -/
def FlipPair.originalGT (p : FlipPair) : Winner := winner p.original

/-- Formal bridge to the experiment contract: the original method is
`majority` (`method_majority_iff_not_tie` + the strict field). -/
theorem FlipPair.method_majority (p : FlipPair) :
    method p.original = Method.majority := by
  have hne : seedYes p.original ≠ seedNo p.original :=
    Nat.ne_of_gt p.horiginalMajority
  exact (method_majority_iff_not_tie p.original).mpr hne

/-- The perturbed ground truth — derived through the verified
transformation, never an independent value. -/
def FlipPair.perturbedGT (p : FlipPair) : Winner := winner p.perturbed

/-- **Reversal (YES→NO).** Under the experiment quota
`2k > seedYes − seedNo` (with `k = |idxs|`), the two derived ground
truths provably differ: the pair is a genuine reversal pair by
construction. The original majority is a field of the structure, not a
hypothesis (review of 2992e77: a tie would satisfy the old `≤` form
vacuously; the experiment contract excludes it). -/
theorem FlipPair.reversal (p : FlipPair)
    (hquota : 2 * p.idxs.length > seedYes p.original - seedNo p.original) :
    p.originalGT ≠ p.perturbedGT := by
  have hcert : EligibleFlip (isTrack p.original) (maskOf p.idxs) isYesKind
      VoteKind.no p.original 0 :=
    eligibleFlip_of_indices (isTrack p.original) isYesKind VoteKind.no
      p.original p.idxs p.hrange p.helig
  have hk : selFrom (maskOf p.idxs) 0 p.original.length = p.idxs.length :=
    selFrom_maskOf_eq_length p.idxs p.original.length p.hnodup p.hrange
  have hw : winner (flipFrom p.original (maskOf p.idxs) VoteKind.no 0)
      = Winner.no := by
    have hle : seedNo p.original ≤ seedYes p.original :=
      Nat.le_of_lt p.horiginalMajority
    rw [winner_no_of_eligible_flip_iff (maskOf p.idxs) p.original 0 hcert
      hle, hk]
    exact hquota
  show winner p.original ≠ winner p.perturbed
  have horigGT : winner p.original = Winner.yes :=
    winner_yes_of_ge p.original (Nat.le_of_lt p.horiginalMajority)
  rw [p.hperturbed, hw, horigGT]
  simp

/-! ## NO → YES (the original winner is NO) -/

/-- A NO→YES flip experiment: original division, a unique in-range index
list of eligible (tracked, losing-side) records, and the perturbed
division tied to the verified transformation. -/
structure FlipPairRev where
  /-- The original division. -/
  original : Division
  /-- Indices of the records flipped from NO to YES. -/
  idxs : List Nat
  /-- The perturbed division — tied to the formal transformation. -/
  perturbed : Division
  /-- The perturbed division IS the certified flip of the original. -/
  hperturbed : perturbed = flipFrom original (maskOf idxs) VoteKind.yes 0
  /-- Indices are unique. -/
  hnodup : idxs.Nodup
  /-- Indices are in range. -/
  hrange : ∀ i ∈ idxs, i < original.length
  /-- Each pointed record is a tracked club's losing-side vote. -/
  helig : ∀ i ∈ idxs,
    isTrack original original[i]!.club ∧ isNoKind original[i]!.kind
  /-- The original comparison was decisive — a strict NO majority
  (experiment contract #24; mirrors `horiginalMajority` of `FlipPair`). -/
  horiginalMajority : seedYes original < seedNo original

/-- Formal bridge to the experiment contract: the original method is
`majority`. -/
theorem FlipPairRev.method_majority (p : FlipPairRev) :
    method p.original = Method.majority := by
  have hne : seedNo p.original ≠ seedYes p.original :=
    Nat.ne_of_gt p.horiginalMajority
  have hne2 : seedYes p.original ≠ seedNo p.original := fun h => hne h.symm
  exact (method_majority_iff_not_tie p.original).mpr hne2

/-- The original ground truth — derived, not stored. -/
def FlipPairRev.originalGT (p : FlipPairRev) : Winner := winner p.original

/-- The perturbed ground truth — derived through the verified
transformation. -/
def FlipPairRev.perturbedGT (p : FlipPairRev) : Winner := winner p.perturbed

/-- **Reversal (NO→YES).** Under the experiment quota
`2k ≥ seedNo − seedYes` (INCLUSIVE boundary — the frozen tie convention
resolves the exact-boundary case to YES), the two derived ground truths
provably differ. The original majority is a field of the structure. -/
theorem FlipPairRev.reversal (p : FlipPairRev)
    (hquota : 2 * p.idxs.length ≥ seedNo p.original - seedYes p.original) :
    p.originalGT ≠ p.perturbedGT := by
  have hcert : EligibleFlip (isTrack p.original) (maskOf p.idxs) isNoKind
      VoteKind.yes p.original 0 :=
    eligibleFlip_of_indices (isTrack p.original) isNoKind VoteKind.yes
      p.original p.idxs p.hrange p.helig
  have hk : selFrom (maskOf p.idxs) 0 p.original.length = p.idxs.length :=
    selFrom_maskOf_eq_length p.idxs p.original.length p.hnodup p.hrange
  have hw : winner (flipFrom p.original (maskOf p.idxs) VoteKind.yes 0)
      = Winner.yes := by
    rw [winner_yes_of_eligible_flip_iff (maskOf p.idxs) p.original 0 hcert
      p.horiginalMajority, hk]
    exact hquota
  show winner p.original ≠ winner p.perturbed
  have horigGT : winner p.original = Winner.no :=
    winner_no_of_gt p.original p.horiginalMajority
  rw [p.hperturbed, hw, horigGT]
  simp

/-! ## ModelResponsePair (L3 — next component, per review of 2992e77)

The model's typed answer about a division. Five values: the two decisive
answers, an explicit abstain, a refusal, and "unresolvable" (the input
does not determine an answer). The ordering matters for the metrics: a
refusal/unresolvable is NOT a wrong decisive answer — coverage counts
decisive responses; responsiveness distinguishes them via `decisive`. -/

/-- The typed model response. -/
inductive ModelAnswer where
  /-- The model says the motion passes. -/
  | yes
  /-- The model says the motion fails. -/
  | no
  /-- The model abstains (explicit, typed). -/
  | abstain
  /-- The model refuses to answer. -/
  | refusal
  /-- The input does not determine an answer. -/
  | unresolvable

/-- A `ModelAnswer` is decisive iff it commits to yes or no. -/
def ModelAnswer.decisive : ModelAnswer → Bool
  | .yes => true
  | .no => true
  | _ => false

/-- The response pair: the model's answer about the original and the
perturbed division of a flip experiment. Answers are free (the model is
the object under test); the GTs remain derived from the pair. -/
structure ModelResponsePair where
  /-- The flip experiment (either direction). -/
  pair : Sum FlipPair FlipPairRev
  /-- The model's answer about the original division. -/
  originalAnswer : ModelAnswer
  /-- The model's answer about the perturbed division. -/
  perturbedAnswer : ModelAnswer

/-- The original GT of the pair (through the derived projections). -/
def ModelResponsePair.originalGT (r : ModelResponsePair) : Winner :=
  match r.pair with
  | .inl p => p.originalGT
  | .inr p => p.originalGT

/-- The perturbed GT of the pair (through the derived projections). -/
def ModelResponsePair.perturbedGT (r : ModelResponsePair) : Winner :=
  match r.pair with
  | .inl p => p.perturbedGT
  | .inr p => p.perturbedGT

/-- Is the model's answer about the original division correct? -/
def ModelResponsePair.originalCorrect (r : ModelResponsePair) : Bool :=
  match r.originalAnswer, r.originalGT with
  | .yes, .yes => true
  | .no, .no => true
  | _, _ => false

/-- Is the model's answer about the perturbed division correct? -/
def ModelResponsePair.perturbedCorrect (r : ModelResponsePair) : Bool :=
  match r.perturbedAnswer, r.perturbedGT with
  | .yes, .yes => true
  | .no, .no => true
  | _, _ => false

/-- **Strict flip responsiveness:** the model was correct on the original
AND adapts to the perturbed GT (stays decisive-correct, or — per the
metric's intent — at least does not keep the stale wrong answer). This
definition is deliberately strict: correct before, correct after. -/
def ModelResponsePair.strictlyResponsive (r : ModelResponsePair) : Bool :=
  r.originalCorrect && r.perturbedCorrect

/-- **Incidental correctness:** the model was wrong on the original but
happens to be correct on the perturbed division. Reported separately —
it must never be merged into responsiveness. -/
def ModelResponsePair.incidentallyCorrect (r : ModelResponsePair) : Bool :=
  !r.originalCorrect && r.perturbedCorrect

end Sejmbench
