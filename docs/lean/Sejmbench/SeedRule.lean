/-!
# SejmBench seed rule — machine-checked specification

Formalizes the frozen definitions of `CODEBOOK.md`:

* §1 (data model): a vote record is `(club, vote)` with
  `vote ∈ {YES, NO, ABSTAIN, ABSENT, NO_VOTE}`;
* §2 (metric v0.2): track activity `n = YES + NO + ABSTAIN`;
  `polarization = 1 - |YES - NO| / n`;
* §3 (seed rule, frozen as v0.3): the seed with the majority of active votes
  (summed over tracks) wins; ties (including 0:0) resolve by seeding order,
  the `YES` seed being the earlier seed; `seed_rule.tie` is `true` iff
  `YES == NO`; a tie is carried explicitly by the tie flag and
  `method = tie_seed_order` (the model constrains the representation, not
  downstream reporting); `ABSTAIN` counts toward `n_active` but never
  decides the winner;
* §4 (invariants, item 5): `0 ≤ polarization ≤ 1` for every track and
  overall.

Everything proved here is a property of the *specification*. The reference
implementation `seed_rule.py` is validated *independently* by the pytest
suite (`tests/`) — hand-computed cases and invariants; there is as yet no
machine-checked equivalence between the two implementations (no shared test
vectors, no differential testing). This artifact removes trust in prose,
not in tests.

Faithfulness note: `seed_rule.py` aggregates per-club dicts and keeps as
tracks the clubs with `sum(t.values()) >= 5`. The vote-filter definitions
below are pointwise equal to that aggregation: each record belongs to
exactly one club, so counting records satisfying a predicate over the whole
division equals summing the per-club tallies of the clubs whose records
satisfy it.

No Mathlib: the frozen core is elementary integer arithmetic; the file
builds against bare Lean 4 core so the CI dependency surface stays empty.
-/

namespace Sejmbench

/-! ## Data model (CODEBOOK §1) -/

/-- Vote kinds exactly as returned by the official Sejm API (CODEBOOK §1). -/
inductive VoteKind where
  | yes | no | abstain | absent | noVote

/-- A single roll-call record: club label plus vote kind (API `votes` entry). -/
structure Record where
  club : String
  kind : VoteKind

/-- A division is the list of its roll-call records. -/
abbrev Division := List Record

/-- Kind predicates (case-split reduces by `rfl`; no `BEq` laws needed). -/
def isYesKind : VoteKind → Bool
  | .yes => true | _ => false
def isNoKind : VoteKind → Bool
  | .no => true | _ => false
def isAbstainKind : VoteKind → Bool
  | .abstain => true | _ => false

/-- Number of records of club `c` in the division. Records of *every* kind
count towards track membership: in `seed_rule.py` a track is a club with
`sum(t.values()) >= 5`, and `t` has all five keys including ABSENT and
NO_VOTE. (An ABSENT/NO_VOTE record can therefore promote a club into a
track; it merely adds nothing to the seed totals — see `seed_cons_of_track`
and `absent_never_decides`.) -/
def recordCount (d : Division) (c : String) : Nat :=
  (d.filter (fun r => r.club == c)).length

/-- `MIN_TRACK_RECORDS` (CODEBOOK §0.2). -/
def MIN_TRACK_RECORDS : Nat := 5

/-- Boolean track predicate: club with at least `MIN_TRACK_RECORDS` records. -/
def isTrack (d : Division) (c : String) : Bool :=
  decide (recordCount d c ≥ MIN_TRACK_RECORDS)

/-- Propositional view of `isTrack`. -/
def IsTrack (d : Division) (c : String) : Prop :=
  recordCount d c ≥ MIN_TRACK_RECORDS

theorem isTrack_iff (d : Division) (c : String) :
    isTrack d c = true ↔ IsTrack d c := decide_eq_true_iff

/-! ## Seed totals (CODEBOOK §0.2/§3) -/

/-- `seed_rule.seed_totals["YES"]`: YES votes of *track* clubs only. -/
def seedYes (d : Division) : Nat :=
  (d.filter (fun r => isTrack d r.club && isYesKind r.kind)).length

/-- `seed_rule.seed_totals["NO"]`. -/
def seedNo (d : Division) : Nat :=
  (d.filter (fun r => isTrack d r.club && isNoKind r.kind)).length

/-- `seed_rule.seed_totals["ABSTAIN"]`. -/
def seedAbstain (d : Division) : Nat :=
  (d.filter (fun r => isTrack d r.club && isAbstainKind r.kind)).length

/-- `n_active` (CODEBOOK §3): ABSTAIN counts; ABSENT and NO_VOTE never enter
(they can only affect *membership*, never the totals directly). -/
def nActive (d : Division) : Nat := seedYes d + seedNo d + seedAbstain d

/-! ## Winner, method, tie flag, margin (CODEBOOK §3, metric v0.3) -/

inductive Winner where | yes | no
inductive Method where | majority | tieSeedOrder

/-- `seed_rule.tie`: `true` iff `YES == NO`, including 0:0 (CODEBOOK §3). -/
def tieFlag (d : Division) : Bool := seedYes d == seedNo d

/-- `seed_rule.margin`: `YES - NO` over seed tracks. -/
def margin (d : Division) : Int := (seedYes d : Int) - (seedNo d : Int)

/-- The seed with the majority of active votes wins; on a tie (including 0:0)
the earlier seed wins, and the `YES` seed is *defined* as the earlier seed
(CODEBOOK §3). The comparison sees only `YES` vs `NO` — `ABSTAIN` never
decides (it only ever enters `n_active`). -/
def winner (d : Division) : Winner :=
  if seedYes d > seedNo d then Winner.yes
  else if seedNo d > seedYes d then Winner.no
  else Winner.yes

/-- `seed_rule.method`: `"majority"` iff the comparison was decisive,
`"tie_seed_order"` exactly on ties. -/
def method (d : Division) : Method :=
  if seedYes d > seedNo d then Method.majority
  else if seedNo d > seedYes d then Method.majority
  else Method.tieSeedOrder

/-! ## §3: the winner is well-defined; ties are explicit, never "passed" -/

theorem winner_yes_of_ge (d : Division) (h : seedYes d ≥ seedNo d) :
    winner d = Winner.yes := by
  unfold winner
  by_cases h1 : seedYes d > seedNo d
  · simp [h1]
  · have h2 : ¬ (seedNo d > seedYes d) := by omega
    simp [h1, h2]

theorem winner_no_of_gt (d : Division) (h : seedNo d > seedYes d) :
    winner d = Winner.no := by
  unfold winner
  have h1 : ¬ (seedYes d > seedNo d) := by omega
  simp [h1, h]

theorem winner_yes_iff (d : Division) :
    winner d = Winner.yes ↔ seedYes d ≥ seedNo d := by
  constructor
  · intro hcon
    rcases Nat.lt_trichotomy (seedYes d) (seedNo d) with hl | he | hg
    · exact absurd hcon (by
        have hw : winner d = Winner.no := winner_no_of_gt d (by omega)
        simp [hw])
    · omega
    · omega
  · exact winner_yes_of_ge d

theorem winner_no_iff (d : Division) :
    winner d = Winner.no ↔ seedNo d > seedYes d := by
  constructor
  · intro hcon
    rcases Nat.lt_trichotomy (seedYes d) (seedNo d) with hl | he | hg
    · omega
    · exact absurd hcon (by
        have hw : winner d = Winner.yes := winner_yes_of_ge d (by omega)
        simp [hw])
    · exact absurd hcon (by
        have hw : winner d = Winner.yes := winner_yes_of_ge d (by omega)
        simp [hw])
  · exact winner_no_of_gt d

/-- CODEBOOK §3: `seed_rule.tie` is exactly `YES == NO` (including 0:0). -/
theorem tieFlag_iff (d : Division) : tieFlag d = true ↔ seedYes d = seedNo d := by
  simp [tieFlag, beq_iff_eq]

/-- CODEBOOK §3: a tie is represented explicitly — the tie flag is `true`,
the winner keeps the scorer-convention value (`yes`, the earlier seed) and
`method` is `tie_seed_order`. This is a contract on the *representation in
the metric*; whether a downstream consumer describes the outcome as "the
motion passed" is outside the model (the CODEBOOK governs that prose). -/
theorem tie_is_explicit (d : Division) (h : tieFlag d = true) :
    winner d = Winner.yes ∧ method d = Method.tieSeedOrder := by
  have he : seedYes d = seedNo d := (tieFlag_iff d).mp h
  simp [winner, method, he, Nat.lt_irrefl]

/-- `method = majority` exactly when the comparison was decisive. -/
theorem method_majority_iff_not_tie (d : Division) :
    method d = Method.majority ↔ seedYes d ≠ seedNo d := by
  constructor
  · intro hcon
    rcases Nat.lt_trichotomy (seedYes d) (seedNo d) with hl | he | hg
    · omega
    · exfalso; simp [method, he, Nat.lt_irrefl] at hcon
    · omega
  · intro hcon
    unfold method
    by_cases h1 : seedYes d > seedNo d
    · simp [h1]
    · have h2 : seedNo d > seedYes d := by omega
      simp [h1, h2]

theorem margin_pos_of_yes_gt (d : Division) (h : seedYes d > seedNo d) :
    margin d > 0 := by
  simp only [margin]; omega

theorem margin_neg_of_no_gt (d : Division) (h : seedNo d > seedYes d) :
    margin d < 0 := by
  simp only [margin]; omega

theorem margin_zero_of_tie (d : Division) (h : tieFlag d = true) : margin d = 0 := by
  have he : seedYes d = seedNo d := (tieFlag_iff d).mp h
  simp only [margin]; omega

/-! ## Tracks only (CODEBOOK §0.2) -/

/-- Number of YES votes in the whole division. -/
def countYes (d : Division) : Nat := (d.filter (fun r => isYesKind r.kind)).length
/-- Number of NO votes in the whole division. -/
def countNo (d : Division) : Nat := (d.filter (fun r => isNoKind r.kind)).length

theorem length_filter_le_of_implies {α : Type} (f g : α → Bool) (l : List α)
    (h : ∀ x, f x = true → g x = true) :
    (l.filter f).length ≤ (l.filter g).length := by
  have hfg : l.filter f = (l.filter g).filter f := by
    rw [List.filter_filter]
    exact List.filter_congr (p := f) (q := fun x => f x && g x) (l := l)
      (fun x _ => by
        cases hf : f x with
        | true => simp [h x hf]
        | false => simp)
  calc (l.filter f).length = ((l.filter g).filter f).length := by rw [hfg]
    _ ≤ (l.filter g).length := List.length_filter_le f (l.filter g)

/-- Seed totals see only track clubs: a YES vote by a club with fewer than
`MIN_TRACK_RECORDS` records is grouped under `inni` and never decides. -/
theorem seedYes_le_countYes (d : Division) : seedYes d ≤ countYes d := by
  unfold seedYes countYes
  exact length_filter_le_of_implies _ _ d (fun r hr =>
    ((Bool.and_eq_true _ _).mp hr).2)

theorem isTrack_cons_ne (r : Record) (d : Division) (c : String) (hne : r.club ≠ c) :
    isTrack (r :: d) c = isTrack d c := by
  unfold isTrack
  have hrc : recordCount (r :: d) c = recordCount d c := by
    unfold recordCount
    have hp : (r.club == c) = false := by
      cases hb : (r.club == c) with
      | true => exact absurd (beq_iff_eq.mp hb) hne
      | false => rfl
    simp [List.filter_cons, hp]
  simp only [hrc]

theorem recordCount_cons_self (r : Record) (d : Division) :
    recordCount (r :: d) r.club = recordCount d r.club + 1 := by
  unfold recordCount
  simp [List.filter_cons, beq_self_eq_true]

/-! ## How one more record moves the seed totals -/

/-- For a club that is *already* a track, one more record changes a seed
total by exactly the kind of that record. This is the frozen aggregation
semantics: membership uses all five kinds; the totals only YES/NO/ABSTAIN. -/
theorem seedP_cons (r : Record) (d : Division) (p : VoteKind → Bool)
    (h : IsTrack d r.club) :
    ((r :: d).filter (fun x => isTrack (r :: d) x.club && p x.kind)).length
      = (d.filter (fun x => isTrack d x.club && p x.kind)).length
        + (if p r.kind then 1 else 0) := by
  have hnew : isTrack (r :: d) r.club = true := by
    rw [isTrack_iff]
    have h5 : recordCount d r.club ≥ 5 := h
    show recordCount (r :: d) r.club ≥ 5
    rw [recordCount_cons_self]
    omega
  have hpt : ∀ x : Record, x ∈ d →
      (isTrack (r :: d) x.club && p x.kind) = (isTrack d x.club && p x.kind) := by
    intro x hx
    by_cases hxeq : x.club = r.club
    · rw [hxeq]
      have h2 : isTrack d r.club = true := (isTrack_iff _ _).mpr h
      simp [hnew, h2]
    · simp [isTrack_cons_ne r d x.club (Ne.symm hxeq)]
  rw [List.filter_cons]
  simp only [hnew, Bool.and_true]
  have hfl : d.filter (fun x => isTrack (r :: d) x.club && p x.kind)
      = d.filter (fun x => isTrack d x.club && p x.kind) :=
    List.filter_congr (p := fun x => isTrack (r :: d) x.club && p x.kind)
      (q := fun x => isTrack d x.club && p x.kind) (l := d) hpt
  rw [hfl]
  cases hp : p r.kind <;> simp [hp]

/-- The three seed totals move independently and only by the kind of the new
record (CODEBOOK §0.2 aggregation, made explicit). -/
theorem seed_cons_of_track (r : Record) (d : Division) (h : IsTrack d r.club) :
    seedYes (r :: d) = seedYes d + (if isYesKind r.kind then 1 else 0)
      ∧ seedNo (r :: d) = seedNo d + (if isNoKind r.kind then 1 else 0)
      ∧ seedAbstain (r :: d) = seedAbstain d + (if isAbstainKind r.kind then 1 else 0) := by
  unfold seedYes seedNo seedAbstain
  exact ⟨seedP_cons r d isYesKind h, seedP_cons r d isNoKind h,
    seedP_cons r d isAbstainKind h⟩

/-! ## §3: ABSTAIN (and ABSENT/NO_VOTE) never decide the winner -/

/-- An ABSTAIN record by a club that is already a track changes neither the
winner nor the tie flag. This is the precise form of CODEBOOK §3:
"`ABSTAIN` counts toward `n_active` but never decides the winner — only the
`YES` vs `NO` comparison does." (For a club *below* the threshold an abstain
record may promote it into a track — frozen behavior of the ≥5-records rule,
which the hypothesis makes visible.) -/
theorem abstain_never_decides (r : Record) (d : Division)
    (hk : r.kind = VoteKind.abstain) (h : IsTrack d r.club) :
    winner (r :: d) = winner d ∧ tieFlag (r :: d) = tieFlag d := by
  obtain ⟨hy, hn, _⟩ := seed_cons_of_track r d h
  rw [hk] at hy hn
  simp [isYesKind, isNoKind] at hy hn
  have h1 : seedYes (r :: d) = seedYes d := hy
  have h2 : seedNo (r :: d) = seedNo d := hn
  exact ⟨by simp only [winner, h1, h2], by simp only [tieFlag, h1, h2]⟩

/-- Companion to `abstain_never_decides`: an ABSTAIN record by an
already-tracked club *does* increment `n_active` by one — ABSTAIN counts
toward activity (CODEBOOK §2/§3), it merely never decides the winner. -/
theorem abstain_increments_nActive (r : Record) (d : Division)
    (hk : r.kind = VoteKind.abstain) (h : IsTrack d r.club) :
    nActive (r :: d) = nActive d + 1 := by
  obtain ⟨hy, hn, hab⟩ := seed_cons_of_track r d h
  rw [hk] at hy hn hab
  simp [isYesKind, isNoKind, isAbstainKind] at hy hn hab
  have h1 : seedYes (r :: d) = seedYes d := hy
  have h2 : seedNo (r :: d) = seedNo d := hn
  have h3 : seedAbstain (r :: d) = seedAbstain d + 1 := hab
  simp only [nActive, h1, h2, h3]
  omega

/-- An ABSENT record by an already-tracked club changes neither the winner,
the tie flag, nor `n_active` (CODEBOOK §1: ABSENT is non-active; it can only
affect *membership*, never the totals). -/
theorem absent_never_decides (r : Record) (d : Division)
    (hk : r.kind = VoteKind.absent) (h : IsTrack d r.club) :
    winner (r :: d) = winner d ∧ tieFlag (r :: d) = tieFlag d
      ∧ nActive (r :: d) = nActive d := by
  obtain ⟨hy, hn, hab⟩ := seed_cons_of_track r d h
  rw [hk] at hy hn hab
  simp [isYesKind, isNoKind, isAbstainKind] at hy hn hab
  have h1 : seedYes (r :: d) = seedYes d := hy
  have h2 : seedNo (r :: d) = seedNo d := hn
  have h3 : seedAbstain (r :: d) = seedAbstain d := hab
  exact ⟨by simp only [winner, h1, h2], by simp only [tieFlag, h1, h2],
    by simp only [nActive, h1, h2, h3]⟩

/-- NO_VOTE (a term-3-era non-active value, CODEBOOK §1) behaves like ABSENT:
for an already-tracked club it changes neither the winner, the tie flag, nor
`n_active`. Same already-tracked caveat as `absent_never_decides` — a NO_VOTE
record can promote a club *into* a track (membership counts all five kinds),
it just never adds to the totals. -/
theorem noVote_never_decides (r : Record) (d : Division)
    (hk : r.kind = VoteKind.noVote) (h : IsTrack d r.club) :
    winner (r :: d) = winner d ∧ tieFlag (r :: d) = tieFlag d
      ∧ nActive (r :: d) = nActive d := by
  obtain ⟨hy, hn, hab⟩ := seed_cons_of_track r d h
  rw [hk] at hy hn hab
  simp [isYesKind, isNoKind, isAbstainKind] at hy hn hab
  have h1 : seedYes (r :: d) = seedYes d := hy
  have h2 : seedNo (r :: d) = seedNo d := hn
  have h3 : seedAbstain (r :: d) = seedAbstain d := hab
  exact ⟨by simp only [winner, h1, h2], by simp only [tieFlag, h1, h2],
    by simp only [nActive, h1, h2, h3]⟩

/-! ## §2/§4: polarization lives in [0, 1] -/

/-- Integer core of `polarization = 1 - |YES - NO| / n ∈ [0, 1]`
(CODEBOOK §2, §4 item 5), with `n = YES + NO + ABSTAIN`. `polarization ≥ 0`
is exactly `|YES - NO| ≤ n` (division is floor); `polarization ≤ 1` holds
whenever `n > 0` because `|YES - NO| / n ≥ 0`. -/
theorem abs_le_n (yes no abstain : Int) (hy : 0 ≤ yes) (hn : 0 ≤ no)
    (ha : 0 ≤ abstain) : (yes - no).natAbs ≤ yes + no + abstain := by
  omega

/-- Strict form: with at least one abstention the normalized gap sits
strictly below its abstain-free ceiling — abstention dilutes the yes/no
disparity and never sharpens it (the docstring's "ABSTAIN dilutes the
split"). Monotonicity of `|YES-NO|/n` in the abstain count itself is
nonlinear and lives in the prose, not in this file. -/
theorem abs_lt_n_when_abstain (yes no abstain : Int) (hy : 0 ≤ yes) (hn : 0 ≤ no)
    (ha : abstain > 0) : (yes - no).natAbs < yes + no + abstain := by
  omega

/-- CODEBOOK §4 item 5, lower side: with `n = YES + NO + ABSTAIN > 0`,
`polarization ≥ 0` follows from `|YES - NO| ≤ n` (`abs_le_n`). -/
theorem polarization_nonneg (yes no abstain : Int) (hy : 0 ≤ yes) (hn : 0 ≤ no)
    (ha : 0 ≤ abstain) (hpos : 0 < yes + no + abstain)
    (h : (yes - no).natAbs ≤ yes + no + abstain) :
    0 ≤ 1 - (yes - no).natAbs / (yes + no + abstain) := by
  rcases Int.lt_trichotomy ((yes - no).natAbs / (yes + no + abstain)) 1 with hlt | heq | hgt
  · omega
  · omega
  · have hmul : 2 * (yes + no + abstain) ≤ (yes - no).natAbs :=
      (Int.le_ediv_iff_mul_le hpos).mp (by omega)
    have hbound := abs_le_n yes no abstain hy hn ha
    omega

/-- CODEBOOK §4 item 5, upper side: with `n > 0`, `polarization ≤ 1`
(the normalized gap is nonnegative). For `n = 0` the implementation
conventionally reports `0.0` — a special case, not the formula. -/
theorem polarization_le_one (yes no abstain : Int) (hy : 0 ≤ yes) (hn : 0 ≤ no)
    (ha : 0 ≤ abstain) (hpos : 0 < yes + no + abstain) :
    1 - (yes - no).natAbs / (yes + no + abstain) ≤ 1 := by
  have h0 : (0 : Nat) ≤ (yes - no).natAbs := Nat.zero_le _
  have h1 : 0 * (yes + no + abstain) ≤ (yes - no).natAbs := by omega
  have h2 : 0 ≤ (yes - no).natAbs / (yes + no + abstain) :=
    (Int.le_ediv_iff_mul_le hpos).mpr h1
  omega

end Sejmbench
