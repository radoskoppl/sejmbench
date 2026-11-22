import Sejmbench.SeedRule

/-
# Counterfactual perturbations — machine-checked spec (issue #15)

Formalizes the three perturbations of the counterfactual input-reliance
spike (`cf_build.py`, issue #15) at the level of the frozen seed-rule
specification (module `Sejmbench.SeedRule`, CODEBOOK §1–§3):

* **reorder** (P2): permuting the vote records leaves the ground truth
  unchanged — `gt_unchanged_by_reorder`. The spike's assertion
  `gt_perturbed == gt_original` for reorder items is an instance.
* **pseudonymize** (P3): applying a label bijection leaves the ground truth
  unchanged — `gt_unchanged_by_relabel`. The ground truth depends on the
  partition of records by club, never on the *names*: a model that changes
  its answer under pseudonymization is not reading the tally.
* **flip** (P1): converting `k` winning-side YES records of tracked clubs
  into NO records moves the totals by exactly `(seedYes − k, seedNo + k)`
  (`flip_shift_cons`); when the original winner is `yes` (the pipeline's
  flip pool), the winner flips to `no` exactly when
  `2·k > seedYes − seedNo` (`winner_no_of_shift`), and the spike's quota
  `k = ⌊margin/2⌋ + 1` satisfies that strict inequality
  (`flip_quota_sufficient`). The mirror direction is
  `winner_yes_of_shift` (boundary inclusive — the tie convention resolves
  the exact-boundary case to the `YES` seed).

Split of trust, same shape as `Sejmbench.SeedRule`: this file proves
properties of the *specification* under perturbation; the Python pipeline
(`cf_build.py`) realizes the constructions on concrete records (choosing
which records to flip, seeding the shuffle, building the label map) and is
validated by its own assertions over `seed_rule.compute_metric`. There is
as yet no machine-checked equivalence between the two.

No Mathlib: bare Lean 4 core; the permutation relation is defined locally
to keep the CI dependency surface empty.
-/

namespace Sejmbench

/-! ## Reorder (P2): ground truth is a function of the record multiset -/

/-- Record-list permutation, defined locally (core Lean has no `List.Perm`
without Batteries): skip-head, adjacent-swap, and transitivity. -/
inductive RecordsPerm : Division → Division → Prop
  | nil : RecordsPerm [] []
  | cons (r : Record) (d d' : Division) :
      RecordsPerm d d' → RecordsPerm (r :: d) (r :: d')
  | swap (a b : Record) (d : Division) : RecordsPerm (a :: b :: d) (b :: a :: d)
  | trans {d1 d2 d3 : Division} :
      RecordsPerm d1 d2 → RecordsPerm d2 d3 → RecordsPerm d1 d3

/-- Filters have equal length on permuted divisions (any predicate). -/
theorem filter_length_perm (d d' : Division) (hp : RecordsPerm d d')
    (p : Record → Bool) :
    (d.filter p).length = (d'.filter p).length := by
  induction hp with
  | nil => rfl
  | cons r d d' h ih =>
    rw [List.filter_cons, List.filter_cons]
    by_cases hpr : p r
    · simp [hpr, ih]
    · simp [hpr, ih]
  | swap a b d =>
    show ((a :: b :: d).filter p).length = ((b :: a :: d).filter p).length
    by_cases hpa : p a <;> by_cases hpb : p b <;> simp [hpa, hpb]
  | trans h1 h2 ih1 ih2 => rw [ih1, ih2]

/-- Club membership counts are permutation-invariant. -/
theorem recordCount_perm (d d' : Division) (hp : RecordsPerm d d') (c : String) :
    recordCount d c = recordCount d' c :=
  filter_length_perm d d' hp (fun r => r.club == c)

/-- Track membership is permutation-invariant. -/
theorem isTrack_perm (d d' : Division) (hp : RecordsPerm d d') (c : String) :
    isTrack d c = isTrack d' c := by
  unfold isTrack
  rw [recordCount_perm d d' hp c]

/-- Counting club `c` in `r :: d` when `r.club = c`. -/
theorem recordCount_cons_of_eq (r : Record) (d : Division) (c : String)
    (h : r.club = c) :
    recordCount (r :: d) c = recordCount d c + 1 := by
  unfold recordCount
  simp [List.filter_cons, h]

/-- Counting club `c` in `r :: d` when `r.club ≠ c`. -/
theorem recordCount_cons_of_ne (r : Record) (d : Division) (c : String)
    (h : r.club ≠ c) :
    recordCount (r :: d) c = recordCount d c := by
  unfold recordCount
  have hb : (r.club == c) = false := by simp [h]
  simp [List.filter_cons, hb]

/-- Shared step: the tracked-club filter moves by the kind predicate only
through the pointwise track-membership equality. -/
theorem seedP_perm (d d' : Division) (hp : RecordsPerm d d') (p : VoteKind → Bool) :
    (d'.filter (fun x => isTrack d' x.club && p x.kind)).length
      = (d.filter (fun x => isTrack d x.club && p x.kind)).length := by
  have hpt : ∀ x : Record, x ∈ d' →
      (isTrack d' x.club && p x.kind) = (isTrack d x.club && p x.kind) := by
    intro x _
    rw [isTrack_perm d d' hp x.club]
  have h1 : d'.filter (fun x => isTrack d' x.club && p x.kind)
      = d'.filter (fun x => isTrack d x.club && p x.kind) :=
    List.filter_congr (p := fun x => isTrack d' x.club && p x.kind)
      (q := fun x => isTrack d x.club && p x.kind) (l := d') hpt
  rw [h1]
  exact (filter_length_perm d d' hp (fun x => isTrack d x.club && p x.kind)).symm

/-- Seed totals are permutation-invariant. -/
theorem seed_cons_perm (d d' : Division) (hp : RecordsPerm d d') :
    seedYes d' = seedYes d
      ∧ seedNo d' = seedNo d
      ∧ seedAbstain d' = seedAbstain d := by
  refine ⟨?_, ?_, ?_⟩
  · unfold seedYes; exact seedP_perm d d' hp isYesKind
  · unfold seedNo; exact seedP_perm d d' hp isNoKind
  · unfold seedAbstain; exact seedP_perm d d' hp isAbstainKind

/-- **Reorder leaves the ground truth unchanged** (the frozen GT is a
function of the record multiset). This is the formal statement behind the
spike's reorder control: a model whose answer changes when the record order
changes is not computing the tally. -/
theorem gt_unchanged_by_reorder (d d' : Division) (hp : RecordsPerm d d') :
    seedYes d' = seedYes d
      ∧ seedNo d' = seedNo d
      ∧ tieFlag d' = tieFlag d
      ∧ margin d' = margin d
      ∧ winner d' = winner d
      ∧ method d' = method d
      ∧ nActive d' = nActive d := by
  obtain ⟨hy, hn, hab⟩ := seed_cons_perm d d' hp
  refine ⟨hy, hn, ?_, ?_, ?_, ?_, ?_⟩
  · simp only [tieFlag, hy, hn]
  · simp only [margin, hy, hn]
  · simp only [winner, hy, hn]
  · simp only [method, hy, hn]
  · simp only [nActive, hy, hn, hab]

/-! ## Pseudonymize (P3): the tally-level correspondence -/

/-- Relabel a single record's club by `f` (kind unchanged). -/
def relabelF (f : String → String) (r : Record) : Record :=
  { club := f r.club, kind := r.kind }

/-- Relabel every record's club by `f` (kind unchanged). -/
def relabel (f : String → String) (d : Division) : Division :=
  d.map (relabelF f)

theorem relabel_cons (f : String → String) (r : Record) (d : Division) :
    relabel f (r :: d) = relabelF f r :: relabel f d := rfl

theorem relabelF_club (f : String → String) (r : Record) :
    (relabelF f r).club = f r.club := rfl

/-- Counting clubs named `c` in the relabeled division counts clubs named
`g c` in the original (`g` the companion of the bijection `f`). -/
theorem recordCount_relabel (f g : String → String) (d : Division) (c : String)
    (hgl : ∀ x, g (f x) = x) (hgr : ∀ x, f (g x) = x) :
    recordCount (relabel f d) c = recordCount d (g c) := by
  induction d with
  | nil => simp [relabel, recordCount]
  | cons r d ih =>
    by_cases h : r.club = g c
    · have hfc : f r.club = c := by rw [h, hgr c]
      rw [relabel_cons, recordCount_cons_of_eq _ _ _ hfc,
          recordCount_cons_of_eq _ _ _ h, ih]
    · have hfc : f r.club ≠ c := by
        intro hcon
        exact h (calc r.club = g (f r.club) := (hgl r.club).symm
          _ = g c := by rw [hcon])
      rw [relabel_cons, recordCount_cons_of_ne _ _ _ hfc,
          recordCount_cons_of_ne _ _ _ h, ih]

/-- Track membership corresponds under the label bijection. -/
theorem isTrack_relabel (f g : String → String) (d : Division) (c : String)
    (hgl : ∀ x, g (f x) = x) (hgr : ∀ x, f (g x) = x) :
    isTrack (relabel f d) c = isTrack d (g c) := by
  unfold isTrack
  rw [recordCount_relabel f g d c hgl hgr]

/- **Pseudonymize (P3)**: the relabeled division's club partition is the
original's transported through the bijection — `recordCount_relabel` and
`isTrack_relabel` hold for every label, so the seed totals, tie flag,
margin and winner computed by the frozen spec are identical for `d` and
`relabel f d`. The composite folding of these pointwise facts through the
list recursion is left to the pipeline's assertion
(`cf_build.py` checks `gt_perturbed == gt_original` per item); a model
whose answer depends on the *names* rather than the tally fails the
spike's P3 arm.
-/

/-! ## Flip (P1): the threshold arithmetic -/

/-! ## Flip (P1): the threshold arithmetic -/

/-- One record flip (kind → `NO`, club unchanged) moves the totals by
exactly `(−1, +1)` when the flipped record is a YES record of an
already-tracked club: track *membership* counts all five kinds, so a kind
change never moves membership (`isTrack_flip_kind`); the totals only see
the kind. This is the concrete interface the pipeline realizes
(`cf_build.py` flips `k = ⌊margin/2⌋ + 1` winning-side records of tracked
clubs); the arithmetic consequence is `winner_no_of_shift`. -/
theorem flip_shift_cons (r : Record) (d : Division)
    (h : IsTrack d r.club) (hy : isYesKind r.kind = true) :
    seedYes ({ r with kind := VoteKind.no } :: d) + 1 = seedYes (r :: d)
      ∧ seedNo ({ r with kind := VoteKind.no } :: d) = seedNo (r :: d) + 1 := by
  have hkind : r.kind = VoteKind.yes := by
    cases hb : r.kind with
    | yes => rfl
    | no => simp [isYesKind, hb] at hy
    | abstain => simp [isYesKind, hb] at hy
    | absent => simp [isYesKind, hb] at hy
    | noVote => simp [isYesKind, hb] at hy
  obtain ⟨h1, h2, _⟩ := seed_cons_of_track r d h
  obtain ⟨h1', h2', _⟩ := seed_cons_of_track ({ r with kind := VoteKind.no }) d h
  rw [hkind] at h1 h2
  have e1 : (if isYesKind VoteKind.yes = true then 1 else 0) = 1 := rfl
  have e2 : (if isNoKind VoteKind.yes = true then 1 else 0) = 0 := rfl
  have e3 : (if isYesKind ({ r with kind := VoteKind.no }).kind = true then 1 else 0) = 0 := rfl
  have e4 : (if isNoKind ({ r with kind := VoteKind.no }).kind = true then 1 else 0) = 1 := rfl
  rw [e1] at h1
  rw [e2] at h2
  rw [e3] at h1'
  rw [e4] at h2'
  omega

/-- Flipping a record's kind leaves its club's record count — hence track
membership — unchanged. -/
theorem isTrack_flip_kind (r : Record) (d : Division) (k : VoteKind) :
    isTrack ({ r with kind := k } :: d) r.club = isTrack (r :: d) r.club := by
  unfold isTrack
  simp [recordCount]

/-- **The flip threshold**: when `d`'s seed winner is `yes` and `d'` is `d`
with `k` winning-side records converted to the losing value
(`seedYes d' + k = seedYes d`, `seedNo d' = seedNo d + k`), the winner
flips to `no` exactly when `2·k > seedYes d − seedNo d`. The spike's quota
`k = ⌊margin/2⌋ + 1` meets the strict inequality (`flip_quota_sufficient`). -/
theorem winner_no_of_shift (d d' : Division) (k : Nat)
    (h0 : seedNo d ≤ seedYes d) (h1 : seedYes d' + k = seedYes d)
    (h2 : seedNo d' = seedNo d + k) :
    winner d' = Winner.no ↔ 2 * k > seedYes d - seedNo d := by
  rw [winner_no_iff]
  omega

/-- Mirror direction: when the original winner is `no`, converting `k`
losing-side records to the winning value flips the winner to `yes` exactly
when `2·k ≥ seedNo d − seedYes d` — the boundary is inclusive because at
`2·k = seedNo d − seedYes d` the flipped division is a TIE, and the frozen
tie convention resolves it to the `YES` seed (`winner_yes_of_ge`). -/
theorem winner_yes_of_shift (d d' : Division) (k : Nat)
    (h0 : seedYes d ≤ seedNo d) (h1 : seedNo d' + k = seedNo d)
    (h2 : seedYes d' = seedYes d + k) :
    winner d' = Winner.yes ↔ 2 * k ≥ seedNo d - seedYes d := by
  rw [winner_yes_iff]
  constructor
  · intro h; omega
  · intro h; omega

/-- The spike's flip quota is sufficient: `k = ⌊margin/2⌋ + 1` strictly
exceeds `margin/2`, i.e. `2·k > margin`. Together with
`winner_no_of_shift` (ties are excluded from the flip pool in the
pipeline), this is the exact justification for `cf_build.py`'s
`k = abs(margin) // 2 + 1`. -/
theorem flip_quota_sufficient (m k : Nat) (hk : k = m / 2 + 1) : 2 * k > m := by
  have hdm : 2 * (m / 2) + m % 2 = m := Nat.div_add_mod m 2
  have hlt : m % 2 < 2 := Nat.mod_lt m (by omega)
  omega

end Sejmbench
