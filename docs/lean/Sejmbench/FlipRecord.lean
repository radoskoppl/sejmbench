import Sejmbench.SeedRule

/-!
# Record-level flip transformation (issue #24, L1)

Takes formal responsibility for the record-level flip used by `cf_build.py`:
converting exactly `k` selected positions' records to the losing kind.

**Proved here (core Lean, compiles clean, axioms [propext, Classical.choice,
Quot.sound] only):** `recordCount_flipFrom` (generalized over the offset —
the key structural move), `recordCount_flip`, `isTrack_flip`,
**`isTrack_flipFrom`** (any offset — the shape the abstain proof needs,
replacing `isTrack_flipFrom_tail` per review §4), `recordCount_cons`,
**`EligibleNo`** (division-indexed, track-qualified per review §2: `sel`
carries `hkind : isYesKind r.kind` and `htrack : isTrack original r.club`,
both evaluated against the ORIGINAL division), and
**`nActive_of_seed_shifts`** (renamed from nActive_flip_of_eligible per
review §1 — an algebraic lemma over explicit shifts, not a derivation from
eligibility).

**Open (tracked):** seedYes/seedNo shift lemmas (derive from `EligibleNo`
+ `isTrack_flipFrom`), `seedAbstain_flip_of_eligible` (via
`List.filter_congr` after `abstainCount_flipFrom`), composition with
`winner_no_of_shift`/`winner_yes_of_shift`, `flipFrom_length`, and the
`selectedIndices ↔ S` bridge.

Split of responsibility: the transformation's *effect* is proved here; the
*GT recomputation* of the modified division is
`cf_build.compute_ground_truth` (conformance-tested against the golden
vectors, issue #23); the pair structure and metrics are L3
(`CounterfactualV2`).
-/
open Sejmbench
namespace Sejmbench
def flipAt (lose : VoteKind) (r : Record) : Record := { club := r.club, kind := lose }
def flipFrom : Division → (Nat → Bool) → VoteKind → Nat → Division
  | [], _, _, _ => []
  | r :: rest, S, lose, off => (if S off then flipAt lose r else r) :: flipFrom rest S lose (off + 1)
def flip (d : Division) (S : Nat → Bool) (lose : VoteKind) : Division := flipFrom d S lose 0
theorem recordCount_cons (r : Record) (rest : Division) (c : String) :
    recordCount (r :: rest) c = recordCount rest c + (if r.club = c then 1 else 0) := by
  simp only [recordCount, List.filter_cons, List.length_cons]
  by_cases h : r.club = c
  · simp [h]
  · simp [h]
theorem recordCount_flipFrom (d : Division) (S : Nat → Bool) (lose : VoteKind)
    (off : Nat) (c : String) :
    recordCount (flipFrom d S lose off) c = recordCount d c := by
  induction d generalizing off with
  | nil => simp [flipFrom, recordCount]
  | cons r rest ih =>
    show recordCount ((if S off = true then flipAt lose r else r) :: flipFrom rest S lose (off + 1)) c
       = recordCount (r :: rest) c
    rw [recordCount_cons, recordCount_cons, ih (off + 1)]
    by_cases hsel : S off
    · simp [hsel, flipAt]
    · simp [hsel, recordCount]
theorem recordCount_flip (d : Division) (S : Nat → Bool) (lose : VoteKind) (c : String) :
    recordCount (flip d S lose) c = recordCount d c :=
  recordCount_flipFrom d S lose 0 c
theorem isTrack_flip (d : Division) (S : Nat → Bool) (lose : VoteKind) (c : String) :
    isTrack (flip d S lose) c = isTrack d c := by
  unfold isTrack
  rw [recordCount_flip d S lose c]
theorem isTrack_flipFrom (d : Division) (S : Nat → Bool) (lose : VoteKind)
    (off : Nat) (c : String) :
    isTrack (flipFrom d S lose off) c = isTrack d c := by
  unfold isTrack
  rw [recordCount_flipFrom d S lose off c]
inductive EligibleNo (original : Division) (S : Nat → Bool) : Division → Nat → Prop
  | nil (off : Nat) : EligibleNo original S [] off
  | keep (r : Record) (rest : Division) (off : Nat)
      (hs : ¬ S off) (hrest : EligibleNo original S rest (off + 1)) :
      EligibleNo original S (r :: rest) off
  | sel (r : Record) (rest : Division) (off : Nat)
      (hs : S off) (hkind : isYesKind r.kind) (htrack : isTrack original r.club)
      (hrest : EligibleNo original S rest (off + 1)) :
      EligibleNo original S (r :: rest) off

/-- Number of selected positions in `[off, off + n)`. -/
def selFrom (S : Nat → Bool) (off n : Nat) : Nat :=
  match n with
  | 0 => 0
  | n + 1 => (if S off then 1 else 0) + selFrom S (off + 1) n

/-- **Algebraic lemma** over the explicit seed shifts: the decisive kinds
trade `−k/+k` and abstains are untouched, so `n_active` is preserved.
Renamed from `nActive_flip_of_eligible` per review §1 — the hypotheses
(`hshiftYes`, `hshiftNo`, `hab`) are exactly what the future
`seed_totals_flip_of_eligible` must derive from the eligibility model. -/

theorem nActive_of_seed_shifts (S : Nat → Bool) (d : Division) (off : Nat)
    (hshiftYes : seedYes (flipFrom d S VoteKind.no off) + selFrom S off (List.length d)
        = seedYes d)
    (hshiftNo : seedNo (flipFrom d S VoteKind.no off)
        = seedNo d + selFrom S off (List.length d))
    (hab : seedAbstain (flipFrom d S VoteKind.no off) = seedAbstain d) :
    nActive (flipFrom d S VoteKind.no off) = nActive d := by
  unfold nActive
  omega


/-- The flip preserves length. -/
theorem flipFrom_length (d : Division) (S : Nat → Bool) (lose : VoteKind) (off : Nat) :
    (flipFrom d S lose off).length = d.length := by
  induction d generalizing off with
  | nil => simp [flipFrom]
  | cons r rest ih => simp [flipFrom, ih]

-- TODO (next step, #24 L1): `seedAbstain_flip_of_eligible` and the seedYes/seedNo
-- shift lemmas. The tail IH alone is insufficient — the abstain filter depends on
-- tracks of the whole division. Route: `abstainCount_flipFrom` (fixed predicate P
-- by induction, mirroring seedP_perm in Counterfactual.lean), then `seedAbstain`
-- via `List.filter_congr` with `P := isTrack d` and `isTrack_flipFrom`. The
-- `EligibleNo.sel` branch needs `hp : isTrack d r.club` (P0 from review §2),
-- which the division-indexed inductive now carries.

end Sejmbench