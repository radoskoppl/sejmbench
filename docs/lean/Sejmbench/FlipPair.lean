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

/-- The original ground truth — derived, not stored. -/
def FlipPair.originalGT (p : FlipPair) : Winner := winner p.original

/-- The perturbed ground truth — derived through the verified
transformation, never an independent value. -/
def FlipPair.perturbedGT (p : FlipPair) : Winner := winner p.perturbed

/-- **Reversal (YES→NO).** Under the experiment quota
`2k > seedYes − seedNo` (with `k = |idxs|`), the two derived ground
truths provably differ: the pair is a genuine reversal pair by
construction. -/
theorem FlipPair.reversal (p : FlipPair)
    (hmajority : seedNo p.original ≤ seedYes p.original)
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
    rw [winner_no_of_eligible_flip_iff (maskOf p.idxs) p.original 0 hcert
      hmajority, hk]
    exact hquota
  show winner p.original ≠ winner p.perturbed
  rw [p.hperturbed, hw, winner_yes_of_ge p.original (by omega)]
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

/-- The original ground truth — derived, not stored. -/
def FlipPairRev.originalGT (p : FlipPairRev) : Winner := winner p.original

/-- The perturbed ground truth — derived through the verified
transformation. -/
def FlipPairRev.perturbedGT (p : FlipPairRev) : Winner := winner p.perturbed

/-- **Reversal (NO→YES).** Under the experiment quota
`2k ≥ seedNo − seedYes` (INCLUSIVE boundary — the frozen tie convention
resolves the exact-boundary case to YES), the two derived ground truths
provably differ. -/
theorem FlipPairRev.reversal (p : FlipPairRev)
    (hmajority : seedYes p.original < seedNo p.original)
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
      hmajority, hk]
    exact hquota
  show winner p.original ≠ winner p.perturbed
  rw [p.hperturbed, hw]
  have horig : winner p.original = Winner.no := by
    unfold winner
    have h1 : ¬ (seedYes p.original > seedNo p.original) := by omega
    have h2 : seedNo p.original > seedYes p.original := by omega
    simp [h1, h2]
  rw [horig]
  simp

end Sejmbench
