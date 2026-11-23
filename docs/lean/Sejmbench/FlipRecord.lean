import Sejmbench.SeedRule

/-!
# Record-level flip transformation (issue #24, L1)

Takes formal responsibility for the record-level flip used by `cf_build.py`:
converting exactly `k` selected positions' records to the losing kind.

**Proved here (core Lean, compiles clean, axioms [propext, Classical.choice,
Quot.sound] only):** `recordCount_flipFrom` (generalized over the offset —
the key structural move per review), `recordCount_flip`, `isTrack_flip`,
`isTrack_flipFrom_tail`, `recordCount_cons`, `nActive_flip_of_eligible`
(shift hypotheses explicit).

**Open (tracked in the TODO below):** `seedAbstain_flip_of_eligible` and the
seedYes/seedNo shift lemmas — the tail IH is insufficient; the abstain
filter depends on tracks of the whole division.

Split of responsibility: the transformation's *effect* is proved here; the
*GT recomputation* of the modified division is
`cf_build.compute_ground_truth` (conformance-tested against the golden
vectors, issue #23); the pair structure and metrics are L3
(`CounterfactualV2`).
-/
open Sejmbench
namespace Sejmbench
def flipAt (lose : VoteKind) (r : Record) : Record := { club := r.club, kind := lose }
def selFrom (S : Nat → Bool) (off n : Nat) : Nat :=
  match n with
  | 0 => 0
  | n + 1 => (if S off then 1 else 0) + selFrom S (off + 1) n
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
theorem isTrack_flipFrom_tail (rest : Division) (S : Nat → Bool) (lose : VoteKind)
    (off : Nat) (c : String) :
    isTrack (flipFrom rest S lose (off + 1)) c = isTrack rest c := by
  unfold isTrack
  rw [recordCount_flipFrom rest S lose (off + 1) c]
inductive EligibleNo : Division → (Nat → Bool) → Nat → Prop
  | nil {S : Nat → Bool} {off : Nat} : EligibleNo [] S off
  | no (r : Record) (rest : Division) (S : Nat → Bool) (off : Nat)
      (hs : ¬ S off) (hrest : EligibleNo rest S (off + 1)) :
      EligibleNo (r :: rest) S off
  | yes (r : Record) (rest : Division) (S : Nat → Bool) (off : Nat)
      (hs : S off) (hkind : isYesKind r.kind) (hrest : EligibleNo rest S (off + 1)) :
      EligibleNo (r :: rest) S off
theorem nActive_flip_of_eligible (d : Division) (S : Nat → Bool) (off : Nat)
    (hshiftYes : seedYes (flipFrom d S VoteKind.no off) + selFrom S off (List.length d)
        = seedYes d)
    (hshiftNo : seedNo (flipFrom d S VoteKind.no off)
        = seedNo d + selFrom S off (List.length d))
    (hab : seedAbstain (flipFrom d S VoteKind.no off) = seedAbstain d) :
    nActive (flipFrom d S VoteKind.no off) = nActive d := by
  unfold nActive
  omega
end Sejmbench
