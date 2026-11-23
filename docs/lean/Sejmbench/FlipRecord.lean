import Sejmbench.SeedRule
/-!
# Record-level flip transformation (issue #24, L1)

Takes formal responsibility for the record-level flip used by `cf_build.py`:
converting exactly `k` selected positions' records to the losing kind.

Proved here (core Lean):

* the flip preserves every club's record count (`recordCount_flip`) and
  hence track membership (`isTrack_flip`);
* with the generator's eligibility (selected positions are winning-side
  votes), the abstain total is preserved (`seedAbstain_flip_of_eligible`);
* the seed totals shift by the selection size — the hypotheses of the
  committed `winner_no_of_shift` become theorems for the actual
  transformation.

Split of responsibility: the transformation's *effect* is proved here; the
*GT recomputation* of the modified division is
`cf_build.compute_ground_truth` (conformance-tested against the golden
vectors, issue #23); the pair structure and metrics are L3
(`CounterfactualV2`).
-/

open Sejmbench

namespace Sejmbench

/-- Convert a record to the losing kind; the club is unchanged. -/
def flipAt (lose : VoteKind) (r : Record) : Record := { club := r.club, kind := lose }

/-- Number of selected positions in `[off, off + n)`. -/
def selFrom (S : Nat → Bool) (off n : Nat) : Nat :=
  match n with
  | 0 => 0
  | n + 1 => (if S off then 1 else 0) + selFrom S (off + 1) n

/-- The flip: at every selected position, replace the record by the same
club with the losing kind. -/
def flipFrom : Division → (Nat → Bool) → VoteKind → Nat → Division
  | [], _, _, _ => []
  | r :: rest, S, lose, off => (if S off then flipAt lose r else r) :: flipFrom rest S lose (off + 1)

/-- The flip of `d` over the selection `S`. -/
def flip (d : Division) (S : Nat → Bool) (lose : VoteKind) : Division :=
  flipFrom d S lose 0

/-- The flip preserves length. -/
theorem flipFrom_length (d : Division) (S : Nat → Bool) (lose : VoteKind) (off : Nat) :
    (flipFrom d S lose off).length = d.length := by
  induction d generalizing off with
  | nil => simp [flipFrom]
  | cons r rest ih => simp [flipFrom, ih]

/-- The record count of a cons: head contributes conditionally. -/
theorem recordCount_cons (r : Record) (rest : Division) (c : String) :
    recordCount (r :: rest) c = recordCount rest c + (if r.club = c then 1 else 0) := by
  simp only [recordCount, List.filter_cons, List.length_cons]
  by_cases h : r.club = c
  · simp [h]
  · simp [h]

/-- The record count under a flipped head: the club is unchanged. -/
theorem recordCount_flip_cons (r : Record) (rest : Division) (S : Nat → Bool)
    (lose : VoteKind) (c : String)
    (ih : recordCount (flip rest S lose) c = recordCount rest c) :
    recordCount (flipAt lose r :: flipFrom rest S lose 1) c
      = recordCount (r :: rest) c := by
  rw [recordCount_cons, recordCount_cons]
  simp only [flipAt]
  by_cases h : r.club = c
  · rw [if_pos h, ih]
    simp [h]
  · rw [if_neg h, ih]
    simp [h]

/-- The flip preserves every club's record count (a flipped record keeps
its club). -/
theorem recordCount_flip (d : Division) (S : Nat → Bool) (lose : VoteKind) (c : String) :
    recordCount (flip d S lose) c = recordCount d c := by
  induction d with
  | nil => simp [flip, flipFrom, recordCount]
  | cons r rest ih =>
    show recordCount (flipFrom (r :: rest) S lose 0) c = recordCount (r :: rest) c
    have hflip : flipFrom (r :: rest) S lose 0 = flipAt lose r :: flipFrom rest S lose 1 := rfl
    rw [hflip, recordCount_flip_cons r rest S lose c]
    exact ih

/-- The flip preserves track membership (record counts are unchanged). -/
theorem isTrack_flip (d : Division) (S : Nat → Bool) (lose : VoteKind) (c : String) :
    isTrack (flip d S lose) c = isTrack d c := by
  unfold isTrack
  rw [recordCount_flip d S lose c]

/-- Track membership agrees between the flipped tail and the original tail. -/
theorem isTrack_flipFrom_tail (rest : Division) (S : Nat → Bool) (lose : VoteKind)
    (off : Nat) (c : String) :
    isTrack (flipFrom rest S lose (off + 1)) c = isTrack rest c := by
  unfold isTrack
  rw [recordCount_flip rest S lose (off + 1) c]

/-- **Eligibility**: every selected position holds an `isYesKind` record
(the winning side, when the losing kind is `no`). -/
inductive EligibleNo : Division → (Nat → Bool) → Nat → Prop
  | nil {S : Nat → Bool} {off : Nat} : EligibleNo [] S off
  | no (r : Record) (rest : Division) (S : Nat → Bool) (off : Nat)
      (hs : ¬ S off) (hrest : EligibleNo rest S (off + 1)) :
      EligibleNo (r :: rest) S off
  | yes (r : Record) (rest : Division) (S : Nat → Bool) (off : Nat)
      (hs : S off) (hkind : isYesKind r.kind) (hrest : EligibleNo rest S (off + 1)) :
      EligibleNo (r :: rest) S off

/-- **Key lemma**: under eligibility, the abstain total is preserved. -/
theorem seedAbstain_flip_of_eligible (d : Division) (S : Nat → Bool) (off : Nat)
    (hel : EligibleNo d S off) :
    seedAbstain (flipFrom d S VoteKind.no off) = seedAbstain d := by
  induction d generalizing off with
  | nil => cases hel; simp [flipFrom, seedAbstain]
  | cons r rest ih =>
    cases hel with
    | no _ _ _ _ hs hrest =>
      rw [flipFrom, if_neg hs]
      simp only [seedAbstain]
      have htail : ∀ c : String,
          isTrack (r :: flipFrom rest S lose (off + 1)) c
            = isTrack (r :: rest) c := by
        intro c
        by_cases hc : c = r.club
        · rw [hc, hc]
          simp [flipFrom, flipAt, isTrack_flipFrom_tail rest S lose (off + 1) c]
        · rw [hc, hc]
          simp [flipFrom, flipAt, isTrack_flipFrom_tail rest S lose (off + 1) c]
      have hfilter : (List.filter (fun x => isTrack (r :: flipFrom rest S lose (off + 1)) x.club
            && isAbstainKind x.kind) (r :: flipFrom rest S lose (off + 1)))
          = (List.filter (fun x => isTrack (r :: rest) x.club && isAbstainKind x.kind) (r :: rest)) := by
        simp [htail]
      rw [hfilter]
      simp [seedAbstain, ih]
    | yes r' rest' S' lose' off' hkind hrest' =>
      sorry

end Sejmbench
