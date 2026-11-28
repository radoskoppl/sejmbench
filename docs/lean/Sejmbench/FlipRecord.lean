import Sejmbench.SeedRule

/-!
# Record-level flip transformation (issue #24, L1)

Takes formal responsibility for the record-level flip used by `cf_build.py`:
converting exactly `k` selected positions' records to the losing kind.

**Proved here (core Lean, compiles clean, axioms [propext, Classical.choice,
Quot.sound] only):** `recordCount_flipFrom` (generalized over the offset —
the key structural move), `recordCount_flip`, `flipFrom_length`,
`isTrack_flip`,
`isTrack_flipFrom`, `recordCount_cons`, **`filterLen_flipFrom`** (issue #2:
the `List.filter Q` invariance for any flip-preserved predicate `Q`; the
club-only corollary `filterLen_club_flipFrom` is hypothesis-free, and
`recordCount_flipFrom_of_fixed` re-derives `recordCount_flipFrom` as its
`fun s => s == c` instance), **`EligibleFlip`** (direction-generic,
parameterized by the original division's track predicate `P` and source kind
`srcKind`; the `sel` branch carries `hp : P r.club` and `hsrc : srcKind
r.kind` — the two conditions the seed shifts need), and
**`nActive_of_seed_shifts`** (algebraic lemma over the explicit shifts).

**Status:** the shift lemmas `winner_no_of_shift` / `winner_yes_of_shift`
composition and the index-mask bridge (`MaskBridge.lean`) are proven in
`Counterfactual.lean` / `MaskBridge.lean`. **The seed shifts are derived**
(P0 of the round-4/5 P-list): the workhorses `tally_flipFrom_shift` /
`tally_flipFrom_gain` pin the track predicate to the original division and
move each seed tally by exactly the `selCount` of selected tracked records
(`seedYes_flipFrom_shift`, `seedNo_flipFrom_shift`,
`seedAbstain_flipFrom_shift`); the certificate layer converts the `selCount`
amounts into `selFrom S off d.length` under `EligibleFlip (isTrack d) S
isYesKind VoteKind.no d off` (`selCount_{yes,no,all,abstain}_of_cert`),
giving **`seed_shifts_of_cert`** (the exact hypothesis shape
`nActive_of_seed_shifts` consumes) and **`nActive_flipFrom_of_cert`**.
Still open (tracked in #24): the `flipped_record_indices ↔ S` bridge and the
NO→YES specialization (the direction-generic `EligibleFlip` makes the latter
a specialization of the same workhorses with `lose := .yes`).

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
/-! ## Fixed-predicate counting (issue #2) -/

/-- Cons step of the fixed-predicate filter length. -/
theorem filterLen_cons (Q : Record → Bool) (a : Record) (l : Division) :
    (List.filter Q (a :: l)).length = (List.filter Q l).length + (if Q a then 1 else 0) := by
  by_cases h : Q a
  · simp [h]
  · simp [h]

/-- **Fixed-predicate counting lemma** (issue #2). For any predicate `Q`
preserved by the flip (`Q (flipAt lose r) = Q r` — the established scope:
kind-based predicates are NOT preserved, they shift; that is issues #3/#4),
the number of matching records is invariant under `flipFrom` at any offset.
Induction on the list with the offset generalized: the tail IH is needed at
`off + 1` before the cons lemma applies — the key structural move. -/
theorem filterLen_flipFrom (Q : Record → Bool) (S : Nat → Bool) (lose : VoteKind)
    (hQ : ∀ r, Q (flipAt lose r) = Q r) :
    ∀ (d : Division) (off : Nat),
      (List.filter Q (flipFrom d S lose off)).length = (List.filter Q d).length := by
  intro d
  induction d with
  | nil => intro _; simp [flipFrom]
  | cons r rest ih =>
    intro off
    show (List.filter Q ((if S off = true then flipAt lose r else r) :: flipFrom rest S lose (off + 1))).length
       = (List.filter Q (r :: rest)).length
    rw [filterLen_cons Q, filterLen_cons Q, ih (off + 1)]
    by_cases hsel : S off
    · simp [hsel, hQ]
    · simp [hsel]

/-- **Club-predicate specialization** (no hypotheses): the flip never
touches clubs, so every club-only predicate `fun x => P x.club` is
preserved. This is the shape `recordCount` and `isTrack` live in. -/
theorem filterLen_club_flipFrom (P : String → Bool) (S : Nat → Bool) (lose : VoteKind)
    (d : Division) (off : Nat) :
    (List.filter (fun x => P x.club) (flipFrom d S lose off)).length
      = (List.filter (fun x => P x.club) d).length :=
  filterLen_flipFrom (fun x => P x.club) S lose (fun _r => rfl) d off

/-- `recordCount_flipFrom` is the `P := fun s => s == c` instance of the
general fixed-predicate lemma. -/
theorem recordCount_flipFrom_of_fixed (d : Division) (S : Nat → Bool) (lose : VoteKind)
    (off : Nat) (c : String) :
    recordCount (flipFrom d S lose off) c = recordCount d c :=
  filterLen_flipFrom (fun r => r.club == c) S lose (fun _r => rfl) d off

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

/-! ## Seed shifts derived from the certificate (P0 of the round-4/5 P-list)

The seed filter's track predicate is evaluated in the *whole current
division*, so the workhorse theorems pin the track predicate to a fixed
division `d0` (the original) and count the shift on raw counters — the same
Σ-style discipline as the L4 aggregation. `selCount S d0 p d off` counts the
selected positions whose record is a track of `d0` with `p`-kind; the flip
moves each such contribution exactly per the kind of the loss record. -/

/-- Selected positions of `d` (from offset `off`) whose record is a track of
`d0` and whose kind satisfies `p`. -/
def selCount (S : Nat → Bool) (d0 : Division) (p : VoteKind → Bool) :
    Division → Nat → Nat
  | [], _ => 0
  | r :: rest, off =>
      (if S off && isTrack d0 r.club && p r.kind then 1 else 0)
        + selCount S d0 p rest (off + 1)

/-- **Loss-side tally shift** (workhorse). If the loss kind does not satisfy
`p`, flipping moves the `p`-tally of the pinned track predicate `d0` down by
exactly the number of selected tracked `p`-records. -/
theorem tally_flipFrom_shift (d0 : Division) :
    ∀ (d : Division) (S : Nat → Bool) (lose : VoteKind) (p : VoteKind → Bool) (off : Nat),
      p lose = false →
      ((flipFrom d S lose off).filter (fun x => isTrack d0 x.club && p x.kind)).length
          + selCount S d0 p d off
        = (d.filter (fun x => isTrack d0 x.club && p x.kind)).length := by
  intro d
  induction d with
  | nil => intro S lose p off _; simp [flipFrom, selCount]
  | cons r rest ih =>
    intro S lose p off hplose
    have htail := ih S lose p (off + 1) hplose
    have hsplit : flipFrom (r :: rest) S lose off
        = (if S off then flipAt lose r else r) :: flipFrom rest S lose (off + 1) := rfl
    rw [hsplit, filterLen_cons, filterLen_cons]
    simp only [selCount]
    by_cases hsel : S off <;> by_cases ht : isTrack d0 r.club = true <;>
      by_cases hpk : p r.kind = true <;>
      simp [hsel, ht, hpk, flipAt, hplose] <;> omega

/-- **Gain-side tally shift** (workhorse). If the loss kind satisfies `p`
itself, every selected tracked record lands in the `p`-tally after the flip,
so the tally grows by the selected tracked records minus the selected tracked
`p`-records. -/
theorem tally_flipFrom_gain (d0 : Division) :
    ∀ (d : Division) (S : Nat → Bool) (lose : VoteKind) (p : VoteKind → Bool) (off : Nat),
      p lose = true →
      ((flipFrom d S lose off).filter (fun x => isTrack d0 x.club && p x.kind)).length
          + selCount S d0 p d off
        = (d.filter (fun x => isTrack d0 x.club && p x.kind)).length
            + selCount S d0 (fun _ => true) d off := by
  intro d
  induction d with
  | nil => intro S lose p off _; simp [flipFrom, selCount]
  | cons r rest ih =>
    intro S lose p off hplose
    have htail := ih S lose p (off + 1) hplose
    have hsplit : flipFrom (r :: rest) S lose off
        = (if S off then flipAt lose r else r) :: flipFrom rest S lose (off + 1) := rfl
    rw [hsplit, filterLen_cons, filterLen_cons]
    simp only [selCount]
    by_cases hsel : S off <;> by_cases ht : isTrack d0 r.club = true <;>
      by_cases hpk : p r.kind = true <;>
      simp [hsel, ht, hpk, flipAt, hplose] <;> omega

/-- The flipped division's seed filter sees the ORIGINAL division's track
membership: `isTrack (flipFrom …) = isTrack d` pointwise. -/
theorem seedFilter_congr_flipFrom (d : Division) (S : Nat → Bool) (lose : VoteKind)
    (off : Nat) (p : VoteKind → Bool) :
    (flipFrom d S lose off).filter (fun x => isTrack (flipFrom d S lose off) x.club && p x.kind)
      = (flipFrom d S lose off).filter (fun x => isTrack d x.club && p x.kind) :=
  List.filter_congr (p := fun x => isTrack (flipFrom d S lose off) x.club && p x.kind)
    (q := fun x => isTrack d x.club && p x.kind) (l := flipFrom d S lose off)
    (fun x _ => by rw [isTrack_flipFrom])

/-- **seedYes shift**: flipping records to `no` moves the YES seed total down
by exactly the number of selected tracked YES records. -/
theorem seedYes_flipFrom_shift (d : Division) (S : Nat → Bool) (off : Nat) :
    seedYes (flipFrom d S VoteKind.no off) + selCount S d isYesKind d off = seedYes d := by
  unfold seedYes
  rw [seedFilter_congr_flipFrom]
  exact tally_flipFrom_shift d d S VoteKind.no isYesKind off rfl

/-- **seedAbstain shift**: the ABSTAIN total loses exactly the selected
tracked ABSTAIN records (none, under the YES→NO certificate). -/
theorem seedAbstain_flipFrom_shift (d : Division) (S : Nat → Bool) (off : Nat) :
    seedAbstain (flipFrom d S VoteKind.no off) + selCount S d isAbstainKind d off
      = seedAbstain d := by
  unfold seedAbstain
  rw [seedFilter_congr_flipFrom]
  exact tally_flipFrom_shift d d S VoteKind.no isAbstainKind off rfl

/-- **seedNo shift**: flipping to `no` moves the NO seed total up by the
selected tracked records minus the selected tracked NO records. -/
theorem seedNo_flipFrom_shift (d : Division) (S : Nat → Bool) (off : Nat) :
    seedNo (flipFrom d S VoteKind.no off) + selCount S d isNoKind d off
      = seedNo d + selCount S d (fun _ => true) d off := by
  unfold seedNo
  rw [seedFilter_congr_flipFrom]
  exact tally_flipFrom_gain d d S VoteKind.no isNoKind off rfl

/-! ### Certificate layer: the shift amounts from `EligibleFlip`

The certificate theorems are stated over a general index division `n` so the
induction can generalize the index while the track predicate stays pinned to
the original division `d` (a parameter). -/

theorem isNoKind_false_of_isYesKind {k : VoteKind} (h : isYesKind k = true) :
    isNoKind k = false := by
  cases k with
  | yes => rfl
  | no => simp [isYesKind] at h
  | abstain => rfl
  | absent => rfl
  | noVote => rfl

theorem isAbstainKind_false_of_isYesKind {k : VoteKind} (h : isYesKind k = true) :
    isAbstainKind k = false := by
  cases k with
  | yes => rfl
  | no => rfl
  | abstain => simp [isYesKind] at h
  | absent => rfl
  | noVote => rfl

/-- Under the YES→NO certificate, the selected tracked YES records are
exactly the selected positions. -/
theorem selCount_yes_of_cert (d : Division) (S : Nat → Bool) (n : Division) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isYesKind VoteKind.no n off) :
    selCount S d isYesKind n off = selFrom S off (List.length n) := by
  induction hcert with
  | nil off => simp [selCount, selFrom]
  | keep r rest off hs hrest ih => simp [selCount, selFrom, hs, ih]
  | sel r rest off hs hp hsrc hrest ih =>
      simp [selCount, selFrom, hs, hp, hsrc, ih]

/-- Under the YES→NO certificate, no selected record is a NO record. -/
theorem selCount_no_of_cert (d : Division) (S : Nat → Bool) (n : Division) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isYesKind VoteKind.no n off) :
    selCount S d isNoKind n off = 0 := by
  induction hcert with
  | nil off => simp [selCount]
  | keep r rest off hs hrest ih => simp [selCount, hs, ih]
  | sel r rest off hs hp hsrc hrest ih =>
      have hnk : isNoKind r.kind = false := isNoKind_false_of_isYesKind hsrc
      simp [selCount, hs, hp, hnk, ih]

/-- Under the YES→NO certificate, every selected record is a track of the
original division — the selected tracked count is the plain selected count. -/
theorem selCount_all_of_cert (d : Division) (S : Nat → Bool) (n : Division) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isYesKind VoteKind.no n off) :
    selCount S d (fun _ => true) n off = selFrom S off (List.length n) := by
  induction hcert with
  | nil off => simp [selCount, selFrom]
  | keep r rest off hs hrest ih => simp [selCount, selFrom, hs, ih]
  | sel r rest off hs hp hsrc hrest ih =>
      simp [selCount, selFrom, hs, hp, ih]

/-- Under the YES→NO certificate, no selected record is an ABSTAIN record. -/
theorem selCount_abstain_of_cert (d : Division) (S : Nat → Bool) (n : Division) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isYesKind VoteKind.no n off) :
    selCount S d isAbstainKind n off = 0 := by
  induction hcert with
  | nil off => simp [selCount]
  | keep r rest off hs hrest ih => simp [selCount, hs, ih]
  | sel r rest off hs hp hsrc hrest ih =>
      have hnk : isAbstainKind r.kind = false := isAbstainKind_false_of_isYesKind hsrc
      simp [selCount, hs, hp, hnk, ih]

/-- **P0 capstone — the seed shifts from the certificate**: converting
exactly the selected positions (each a track of `d` voting YES) to NO moves
the seed totals by `k = selFrom S off d.length`:
`seedYes d' + k = seedYes d`, `seedNo d' = seedNo d + k`,
`seedAbstain d' = seedAbstain d`. Exactly the hypothesis shape
`nActive_of_seed_shifts` consumes. -/
theorem seed_shifts_of_cert (d : Division) (S : Nat → Bool) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isYesKind VoteKind.no d off) :
    seedYes (flipFrom d S VoteKind.no off) + selFrom S off (List.length d) = seedYes d
      ∧ seedNo (flipFrom d S VoteKind.no off) = seedNo d + selFrom S off (List.length d)
      ∧ seedAbstain (flipFrom d S VoteKind.no off) = seedAbstain d := by
  have h1 := seedYes_flipFrom_shift d S off
  have h2 := seedNo_flipFrom_shift d S off
  have h3 := seedAbstain_flipFrom_shift d S off
  have hy := selCount_yes_of_cert d S d off hcert
  have hn0 := selCount_no_of_cert d S d off hcert
  have hall := selCount_all_of_cert d S d off hcert
  have hab0 := selCount_abstain_of_cert d S d off hcert
  exact ⟨by omega, by omega, by omega⟩

/-- **nActive is invariant** under the certified YES→NO flip
(`nActive_of_seed_shifts` instantiated by the derived shifts). -/
theorem nActive_flipFrom_of_cert (d : Division) (S : Nat → Bool) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isYesKind VoteKind.no d off) :
    nActive (flipFrom d S VoteKind.no off) = nActive d :=
  nActive_of_seed_shifts S d off (seed_shifts_of_cert d S off hcert).1
    (seed_shifts_of_cert d S off hcert).2.1 (seed_shifts_of_cert d S off hcert).2.2

/-! ### The opposite direction: NO→YES (`lose := VoteKind.yes`)

The same workhorses specialize: the loss kind `yes` fails `isNoKind`/
`isAbstainKind` (down-shifts) and satisfies `isYesKind` (up-shift). -/

theorem isYesKind_false_of_isNoKind {k : VoteKind} (h : isNoKind k = true) :
    isYesKind k = false := by
  cases k with
  | yes => simp [isNoKind] at h
  | no => rfl
  | abstain => rfl
  | absent => rfl
  | noVote => rfl

theorem isAbstainKind_false_of_isNoKind {k : VoteKind} (h : isNoKind k = true) :
    isAbstainKind k = false := by
  cases k with
  | yes => rfl
  | no => rfl
  | abstain => simp [isNoKind] at h
  | absent => rfl
  | noVote => rfl

/-- **seedNo shift (NO→YES)**: flipping records to `yes` moves the NO seed
total down by exactly the selected tracked NO records. -/
theorem seedNo_flipToYes_shift (d : Division) (S : Nat → Bool) (off : Nat) :
    seedNo (flipFrom d S VoteKind.yes off) + selCount S d isNoKind d off = seedNo d := by
  unfold seedNo
  rw [seedFilter_congr_flipFrom]
  exact tally_flipFrom_shift d d S VoteKind.yes isNoKind off rfl

/-- **seedAbstain shift (NO→YES)**: the ABSTAIN total loses exactly the
selected tracked ABSTAIN records (none, under the NO→YES certificate). -/
theorem seedAbstain_flipToYes_shift (d : Division) (S : Nat → Bool) (off : Nat) :
    seedAbstain (flipFrom d S VoteKind.yes off) + selCount S d isAbstainKind d off
      = seedAbstain d := by
  unfold seedAbstain
  rw [seedFilter_congr_flipFrom]
  exact tally_flipFrom_shift d d S VoteKind.yes isAbstainKind off rfl

/-- **seedYes shift (NO→YES)**: flipping to `yes` moves the YES seed total up
by the selected tracked records minus the selected tracked YES records. -/
theorem seedYes_flipToYes_gain (d : Division) (S : Nat → Bool) (off : Nat) :
    seedYes (flipFrom d S VoteKind.yes off) + selCount S d isYesKind d off
      = seedYes d + selCount S d (fun _ => true) d off := by
  unfold seedYes
  rw [seedFilter_congr_flipFrom]
  exact tally_flipFrom_gain d d S VoteKind.yes isYesKind off rfl

/-- Under the NO→YES certificate, the selected tracked NO records are exactly
the selected positions. -/
theorem selCount_no_of_cert_no2yes (d : Division) (S : Nat → Bool) (n : Division) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isNoKind VoteKind.yes n off) :
    selCount S d isNoKind n off = selFrom S off (List.length n) := by
  induction hcert with
  | nil off => simp [selCount, selFrom]
  | keep r rest off hs hrest ih => simp [selCount, selFrom, hs, ih]
  | sel r rest off hs hp hsrc hrest ih =>
      simp [selCount, selFrom, hs, hp, hsrc, ih]

/-- Under the NO→YES certificate, every selected record is a track of the
original division — the selected tracked count is the plain selected count. -/
theorem selCount_all_of_cert_no2yes (d : Division) (S : Nat → Bool) (n : Division) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isNoKind VoteKind.yes n off) :
    selCount S d (fun _ => true) n off = selFrom S off (List.length n) := by
  induction hcert with
  | nil off => simp [selCount, selFrom]
  | keep r rest off hs hrest ih => simp [selCount, selFrom, hs, ih]
  | sel r rest off hs hp hsrc hrest ih =>
      simp [selCount, selFrom, hs, hp, ih]

/-- Under the NO→YES certificate, no selected record is a YES record. -/
theorem selCount_yes_of_cert_no2yes (d : Division) (S : Nat → Bool) (n : Division) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isNoKind VoteKind.yes n off) :
    selCount S d isYesKind n off = 0 := by
  induction hcert with
  | nil off => simp [selCount]
  | keep r rest off hs hrest ih => simp [selCount, hs, ih]
  | sel r rest off hs hp hsrc hrest ih =>
      have hyk : isYesKind r.kind = false := isYesKind_false_of_isNoKind hsrc
      simp [selCount, hs, hp, hyk, ih]

/-- Under the NO→YES certificate, no selected record is an ABSTAIN record. -/
theorem selCount_abstain_of_cert_no2yes (d : Division) (S : Nat → Bool) (n : Division)
    (off : Nat) (hcert : EligibleFlip (isTrack d) S isNoKind VoteKind.yes n off) :
    selCount S d isAbstainKind n off = 0 := by
  induction hcert with
  | nil off => simp [selCount]
  | keep r rest off hs hrest ih => simp [selCount, hs, ih]
  | sel r rest off hs hp hsrc hrest ih =>
      have hyk : isAbstainKind r.kind = false := isAbstainKind_false_of_isNoKind hsrc
      simp [selCount, hs, hp, hyk, ih]

/-- The NO→YES seed-shift shape: mirrored hypothesis contract that the
certificate must discharge for `nActive` to be invariant. -/
theorem nActive_of_seed_shifts_no2yes (S : Nat → Bool) (d : Division) (off : Nat)
    (hshiftNo : seedNo (flipFrom d S VoteKind.yes off) + selFrom S off (List.length d)
        = seedNo d)
    (hshiftYes : seedYes (flipFrom d S VoteKind.yes off)
        = seedYes d + selFrom S off (List.length d))
    (hab : seedAbstain (flipFrom d S VoteKind.yes off) = seedAbstain d) :
    nActive (flipFrom d S VoteKind.yes off) = nActive d := by
  unfold nActive
  omega

/-- **P0 capstone (NO→YES)**: converting exactly the selected positions (each
a track of `d` voting NO) to YES moves the seed totals by
`k = selFrom S off d.length`: `seedNo d' + k = seedNo d`,
`seedYes d' = seedYes d + k`, `seedAbstain d' = seedAbstain d`. Exactly the
hypothesis shape `nActive_of_seed_shifts_no2yes` consumes. -/
theorem seed_shifts_of_cert_no2yes (d : Division) (S : Nat → Bool) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isNoKind VoteKind.yes d off) :
    seedNo (flipFrom d S VoteKind.yes off) + selFrom S off (List.length d) = seedNo d
      ∧ seedYes (flipFrom d S VoteKind.yes off)
          = seedYes d + selFrom S off (List.length d)
      ∧ seedAbstain (flipFrom d S VoteKind.yes off) = seedAbstain d := by
  have h1 := seedNo_flipToYes_shift d S off
  have h2 := seedYes_flipToYes_gain d S off
  have h3 := seedAbstain_flipToYes_shift d S off
  have hn := selCount_no_of_cert_no2yes d S d off hcert
  have hy0 := selCount_yes_of_cert_no2yes d S d off hcert
  have hall := selCount_all_of_cert_no2yes d S d off hcert
  have hab0 := selCount_abstain_of_cert_no2yes d S d off hcert
  exact ⟨by omega, by omega, by omega⟩

/-- **nActive is invariant** under the certified NO→YES flip
(`nActive_of_seed_shifts_no2yes` instantiated by the derived shifts). -/
theorem nActive_flipFrom_of_cert_no2yes (d : Division) (S : Nat → Bool) (off : Nat)
    (hcert : EligibleFlip (isTrack d) S isNoKind VoteKind.yes d off) :
    nActive (flipFrom d S VoteKind.yes off) = nActive d :=
  nActive_of_seed_shifts_no2yes S d off (seed_shifts_of_cert_no2yes d S off hcert).1
    (seed_shifts_of_cert_no2yes d S off hcert).2.1 (seed_shifts_of_cert_no2yes d S off hcert).2.2

end Sejmbench
