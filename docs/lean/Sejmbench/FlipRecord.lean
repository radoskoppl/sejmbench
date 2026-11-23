import Sejmbench.SeedRule
open Sejmbench
namespace Sejmbench
def flipAt (lose : VoteKind) (r : Record) : Record := { club := r.club, kind := lose }
def flipFrom : Division → (Nat → Bool) → VoteKind → Nat → Division
  | [], _, _, _ => []
  | r :: rest, S, lose, off => (if S off then flipAt lose r else r) :: flipFrom rest S lose (off + 1)
def flip (d : Division) (S : Nat → Bool) (lose : VoteKind) : Division := flipFrom d S lose 0
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

/-- **Eligibility** for a flip toward `lose`: parameterized by the ORIGINAL
division's track predicate `P` and the source kind. A position `off` is
eligible when `S off = false` (kept), or the record at `off` has club with
`P c0 = true` and `isYesKind` kind. The certificate indexes the actual
division; `P` is instantiated with `isTrack d` at use time. -/
inductive EligibleFlip (P : String → Bool) (S : Nat → Bool) (lose : VoteKind) : Division → Nat → Prop
  | nil (d : Division) (off : Nat) : EligibleFlip P S lose d off
  | keep (r : Record) (rest : Division) (off : Nat)
      (hs : ¬ S off) (hrest : EligibleFlip P S lose rest (off + 1)) :
      EligibleFlip P S lose (r :: rest) off
  | sel (r : Record) (rest : Division) (off : Nat)
      (hs : S off) (hp : P r.club) (hsrc : isYesKind r.kind)
      (hrest : EligibleFlip P S lose rest (off + 1)) :
      EligibleFlip P S lose (r :: rest) off

/-- **Algebraic lemma** over the explicit seed shifts: the decisive kinds
trade `−k/+k` and abstains are untouched, so `n_active` is preserved.
The hypotheses are what `seedYes/seedNo/seedAbstain_flip_of_eligible`
must derive from `EligibleFlip`. -/
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
