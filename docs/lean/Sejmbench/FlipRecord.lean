import Sejmbench.SeedRule

/-!
# Record-level flip transformation (issue #24, L1)

Takes formal responsibility for the record-level flip used by `cf_build.py`:
converting exactly `k` selected positions' records to the losing kind.

**Proved here (core Lean, compiles clean, axioms [propext, Classical.choice,
Quot.sound] only):** `recordCount_flipFrom` (generalized over the offset —
the key structural move), `recordCount_flip`, `flipFrom_length`,
`isTrack_flip`,
`isTrack_flipFrom`, `recordCount_cons`, **`EligibleFlip`** (direction-generic,
parameterized by the original division's track predicate `P` and source kind
`srcKind`; the `sel` branch carries `hp : P r.club` and `hsrc : srcKind
r.kind` — the two conditions the seed shifts need), and
**`nActive_of_seed_shifts`** (algebraic lemma over the explicit shifts).

**Open (next milestone):** `seedYes`/`seedNo` shift lemmas derived from
`EligibleFlip.sel` + `isTrack_flipFrom` (shift amount
`k = selFrom S off d.length`), `seedAbstain_flip_of_eligible`, composition
with `winner_no_of_shift`/`winner_yes_of_shift`, the
`flipped_record_indices ↔ S` bridge, and the NO→YES specialization.

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
/-- The flip touches exactly the records of the division: one entry per
record, selected or kept. -/
theorem flipFrom_length (d : Division)
    (S : Nat → Bool)
    (lose : VoteKind)
    (off : Nat) :
    (flipFrom d S lose off).length = d.length := by
  induction d generalizing off with
  | nil => simp [flipFrom]
  | cons r rest ih => simp [flipFrom, ih]
def selFrom (S : Nat → Bool) (off n : Nat) : Nat :=
  match n with
  | 0 => 0
  | n + 1 => (if S off then 1 else 0) + selFrom S (off + 1) n
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
inductive EligibleFlip (P : String → Bool) (S : Nat → Bool) (srcKind : VoteKind → Bool) (lose : VoteKind) :
    Division → Nat → Prop
  | nil (off : Nat) : EligibleFlip P S srcKind lose [] off
  | keep (r : Record) (rest : Division) (off : Nat)
      (hs : ¬ S off) (hrest : EligibleFlip P S srcKind lose rest (off + 1)) :
      EligibleFlip P S srcKind lose (r :: rest) off
  | sel (r : Record) (rest : Division) (off : Nat)
      (hs : S off) (hp : P r.club) (hsrc : srcKind r.kind)
      (hrest : EligibleFlip P S srcKind lose rest (off + 1)) :
      EligibleFlip P S srcKind lose (r :: rest) off
theorem nActive_of_seed_shifts (S : Nat → Bool) (d : Division) (off : Nat)
    (hshiftYes : seedYes (flipFrom d S VoteKind.no off) + selFrom S off (List.length d)
        = seedYes d)
    (hshiftNo : seedNo (flipFrom d S VoteKind.no off)
        = seedNo d + selFrom S off (List.length d))
    (hab : seedAbstain (flipFrom d S VoteKind.no off) = seedAbstain d) :
    nActive (flipFrom d S VoteKind.no off) = nActive d := by
  unfold nActive
  omega
end Sejmbench
