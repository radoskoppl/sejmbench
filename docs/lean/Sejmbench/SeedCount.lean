import Sejmbench.Counterfactual
import Sejmbench.FlipRecord

/-!
# Seed-counting under a fixed club predicate (issue #24, L1 — seed shifts)

The seed-shift milestone: `EligibleFlip ⇒ exact k ⇒ seed shifts ⇒ (nActive)`.
`k = selFrom S off d.length` throughout.

**Proved here (core Lean, axioms [propext, Classical.choice, Quot.sound]
only):** `countOn` — a filtered count under a FIXED club predicate `P` and
kind predicate `K` — with the three certificate-driven laws
`countOn_src_flipFrom` (source loses exactly `k`),
`countOn_dst_flipFrom` (target gains exactly `k`, under src/dst
disjointness), `countOn_mid_flipFrom` (a third kind is invariant), and
`countOn_congr` (pointwise equal predicates count equally). The bridge to
the seed totals: `seedYes`/`seedNo`/`seedAbstain` are definitionally
`countOn (isTrack d) · d`, and `isTrack_flipFrom` makes the predicate
constant — yielding, by specialization:

* YES → NO: `seedYes_dec_of_eligible`, `seedNo_inc_of_eligible`,
  `seedAbstain_flip_no_of_eligible`, `nActive_flip_no_of_eligible`;
* NO → YES: `seedNo_dec_of_eligible`, `seedYes_inc_of_eligible`,
  `seedAbstain_flip_yes_of_eligible`, `nActive_flip_yes_of_eligible`.

**Open (next milestone):** composition with
`winner_no_of_shift`/`winner_yes_of_shift`, the `flipped_record_indices ↔ S`
bridge, and the L3 pair structure.
-/

namespace Sejmbench

/-! ## Counting under a fixed club predicate -/

/-- Count of records satisfying the FIXED club predicate `P` and kind
predicate `K`. Unlike `seedYes d` (which recomputes `isTrack` on `d`),
`P` here is held constant across the transformation. -/
def countOn (P : String → Bool) (K : VoteKind → Bool) (d : Division) : Nat :=
  (d.filter (fun r => P r.club && K r.kind)).length

/-- The seed totals ARE `countOn` with the division's own track predicate. -/
theorem seedYes_eq_countOn (d : Division) :
    seedYes d = countOn (isTrack d) isYesKind d := rfl
theorem seedNo_eq_countOn (d : Division) :
    seedNo d = countOn (isTrack d) isNoKind d := rfl
theorem seedAbstain_eq_countOn (d : Division) :
    seedAbstain d = countOn (isTrack d) isAbstainKind d := rfl

/-- Cons step of `countOn` with a fixed predicate. -/
theorem countOn_cons (P : String → Bool) (K : VoteKind → Bool) (r : Record) (rest : Division) :
    countOn P K (r :: rest) = countOn P K rest + (if P r.club && K r.kind then 1 else 0) := by
  simp only [countOn, List.filter_cons, List.length_cons]
  by_cases h : P r.club && K r.kind
  · simp [h]
  · simp [h]

/-- `selFrom` over a cons: the head contributes its selection bit. -/
theorem selFrom_cons (S : Nat → Bool) (off : Nat) (r : Record) (rest : Division) :
    selFrom S off (List.length (r :: rest))
      = (if S off then 1 else 0) + selFrom S (off + 1) (List.length rest) := by
  simp only [selFrom, List.length_cons]

/-- Pointwise equal predicates count equally. -/
theorem countOn_congr (P P' : String → Bool) (K : VoteKind → Bool) (d : Division)
    (h : ∀ c, P c = P' c) : countOn P K d = countOn P' K d := by
  induction d with
  | nil => rfl
  | cons r rest ih =>
      have h1 := countOn_cons P K r rest
      have h2 := countOn_cons P' K r rest
      rw [ih] at h1
      have heq : (P r.club && K r.kind) = (P' r.club && K r.kind) := by rw [h r.club]
      rw [heq] at h1
      omega

/-- The selected head contributes 0 to the SOURCE count of the flipped
division: its kind is `lose`, and `srcKind lose = false`. -/
theorem countOn_flipAt_src (P : String → Bool) (srcKind : VoteKind → Bool)
    (lose : VoteKind) (r : Record) (rest : Division) (hlose : srcKind lose = false) :
    countOn P srcKind (flipAt lose r :: rest) = countOn P srcKind rest := by
  simp [countOn_cons, flipAt, hlose]

/-- The selected head contributes exactly 1 to the TARGET count of the
flipped division: its club qualifies (`P r.club`) and its kind is `lose`,
counted by `dstKind lose = true`. -/
theorem countOn_flipAt_dst (P : String → Bool) (dstKind : VoteKind → Bool)
    (lose : VoteKind) (r : Record) (rest : Division)
    (hp : P r.club = true) (hdst : dstKind lose = true) :
    countOn P dstKind (flipAt lose r :: rest) = countOn P dstKind rest + 1 := by
  simp [countOn_cons, flipAt, hdst, hp]

/-- Helper: a head NOT counted under the (P, K) pair leaves the target
count of the tail unchanged. -/
theorem countOn_cons_not (P : String → Bool) (K : VoteKind → Bool) (r : Record)
    (rest : Division) (hK : ¬ ((P r.club && K r.kind) = true)) :
    countOn P K (r :: rest) = countOn P K rest := by
  rw [countOn_cons P K r rest, if_neg (by simp [hK])]
  omega

/-! ## The three certificate-driven counting laws -/

/-- **Source' + k = Source.** Under the certificate, exactly the selected
records leave the source kind; `k = selFrom S off d.length`. -/
theorem countOn_src_flipFrom (P : String → Bool) (S : Nat → Bool) (srcKind : VoteKind → Bool)
    (lose : VoteKind) (d : Division) (off : Nat)
    (h : EligibleFlip P S srcKind lose d off)
    (hlose : srcKind lose = false) :
    countOn P srcKind (flipFrom d S lose off) + selFrom S off (List.length d) = countOn P srcKind d := by
  induction h with
  | nil off => simp [flipFrom, countOn, selFrom]
  | @keep r rest off hs hrest ih =>
      rw [flipFrom, if_neg hs, countOn_cons P srcKind r (flipFrom rest S lose (off+1)),
          countOn_cons P srcKind r rest, selFrom_cons, if_neg hs]
      omega
  | @sel r rest off hs hp hsrc hrest ih =>
      rw [flipFrom, if_pos hs, countOn_flipAt_src P srcKind lose r
            (flipFrom rest S lose (off+1)) hlose,
          countOn_cons P srcKind r rest, selFrom_cons, if_pos hs]
      have h2 : countOn P srcKind (r :: rest)
          = countOn P srcKind rest + 1 := by
        rw [countOn_cons P srcKind r rest]
        have : (P r.club && srcKind r.kind) = true := by simp [hp, hsrc]
        rw [if_pos this]
      have h3 : (if (P r.club && srcKind r.kind) = true then 1 else 0) = 1 := by
        rw [if_pos (by simp [hp, hsrc])]
      omega

/-- **Target' = Target + k.** Under the certificate and src/dst
disjointness, exactly the selected records arrive in the target kind. -/
theorem countOn_dst_flipFrom (P : String → Bool) (S : Nat → Bool) (srcKind : VoteKind → Bool)
    (dstKind : VoteKind → Bool) (lose : VoteKind) (d : Division) (off : Nat)
    (h : EligibleFlip P S srcKind lose d off)
    (hdisjoint : ∀ k, srcKind k = true → dstKind k = false)
    (hdst : dstKind lose = true) :
    countOn P dstKind (flipFrom d S lose off)
      = countOn P dstKind d + selFrom S off d.length := by
  induction h with
  | nil off => simp [flipFrom, countOn, selFrom]
  | @keep r rest off hs hrest ih =>
      rw [flipFrom, if_neg hs, countOn_cons P dstKind r (flipFrom rest S lose (off+1)),
          countOn_cons P dstKind r rest, selFrom_cons, if_neg hs]
      omega
  | @sel r rest off hs hp hsrc hrest ih =>
      rw [flipFrom, if_pos hs, countOn_flipAt_dst P dstKind lose r
            (flipFrom rest S lose (off+1)) hp hdst,
          countOn_cons P dstKind r rest, selFrom_cons, if_pos hs]
      have hk : dstKind r.kind = false := hdisjoint r.kind hsrc
      have h2 := countOn_cons_not P dstKind r rest (by rw [hk]; simp)
      have h3 : (if (P r.club && dstKind r.kind) = true then 1 else 0) = 0 := by
        rw [if_neg (by simp [hk])]
      omega

/-- **Mid' = Mid.** A kind touched by neither side (its predicate implies
the complement of the source kind, and is false at `lose`) is invariant. -/
theorem countOn_mid_flipFrom (P : String → Bool) (S : Nat → Bool) (srcKind : VoteKind → Bool)
    (mid : VoteKind → Bool) (lose : VoteKind) (d : Division) (off : Nat)
    (h : EligibleFlip P S srcKind lose d off)
    (hmid_src : ∀ k, mid k = true → srcKind k = false)
    (hmid_lose : mid lose = false) :
    countOn P mid (flipFrom d S lose off) = countOn P mid d := by
  induction h with
  | nil off => simp [flipFrom, countOn, selFrom]
  | @keep r rest off hs hrest ih =>
      rw [flipFrom, if_neg hs, countOn_cons P mid r (flipFrom rest S lose (off+1)),
          countOn_cons P mid r rest, ih]
  | @sel r rest off hs hp hsrc hrest ih =>
      have hmr : mid r.kind = false := by
        by_cases hm : mid r.kind = true
        · have hcon := hmid_src r.kind hm
          simp [hcon] at hsrc
        · simp [hm]
      have e0 : flipFrom (r :: rest) S lose off
          = flipAt lose r :: flipFrom rest S lose (off+1) := by
        simp [flipFrom, hs]
      rw [e0, countOn_cons_not P mid (flipAt lose r) (flipFrom rest S lose (off+1))
            (by simp [flipAt, hmid_lose]),
        ih, countOn_cons_not P mid r rest (by simp [hmr])]

/-- Pointwise: the flipped division's own track predicate equals the
original's (restatement of `isTrack_flipFrom` for `countOn`). -/
theorem countOn_isTrack_flipFrom (S : Nat → Bool) (lose : VoteKind)
    (d : Division) (off : Nat) (K : VoteKind → Bool) :
    countOn (isTrack (flipFrom d S lose off)) K (flipFrom d S lose off)
      = countOn (isTrack d) K (flipFrom d S lose off) := by
  apply countOn_congr
  exact isTrack_flipFrom d S lose off

/-! ## Kind disjointness (case analysis; `VoteKind` has five constructors) -/

theorem isNoKind_of_isYesKind : ∀ k, isYesKind k = true → isNoKind k = false
  | .yes, _ => rfl
  | .no, h => absurd h (by simp [isYesKind])
  | .abstain, h => absurd h (by simp [isYesKind])
  | .absent, h => absurd h (by simp [isYesKind])
  | .noVote, h => absurd h (by simp [isYesKind])
theorem isYesKind_of_isNoKind : ∀ k, isNoKind k = true → isYesKind k = false
  | .yes, h => absurd h (by simp [isNoKind])
  | .no, _ => rfl
  | .abstain, h => absurd h (by simp [isNoKind])
  | .absent, h => absurd h (by simp [isNoKind])
  | .noVote, h => absurd h (by simp [isNoKind])
theorem isYesKind_of_isAbstainKind : ∀ k, isAbstainKind k = true → isYesKind k = false
  | .yes, h => absurd h (by simp [isAbstainKind])
  | .no, h => absurd h (by simp [isAbstainKind])
  | .abstain, _ => rfl
  | .absent, h => absurd h (by simp [isAbstainKind])
  | .noVote, h => absurd h (by simp [isAbstainKind])
theorem isNoKind_of_isAbstainKind : ∀ k, isAbstainKind k = true → isNoKind k = false
  | .yes, h => absurd h (by simp [isAbstainKind])
  | .no, h => absurd h (by simp [isAbstainKind])
  | .abstain, _ => rfl
  | .absent, h => absurd h (by simp [isAbstainKind])
  | .noVote, h => absurd h (by simp [isAbstainKind])

/-! ## The four seed theorems + ABSTAIN + nActive (fixed original track) -/

/-- **YES → NO:** `seedYes d' + k = seedYes d`, `k = selFrom S off d.length`. -/
theorem seedYes_dec_of_eligible (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isYesKind VoteKind.no d off) :
    seedYes (flipFrom d S VoteKind.no off) + selFrom S off (List.length d) = seedYes d := by
  have h1 := countOn_src_flipFrom (isTrack d) S isYesKind VoteKind.no d off h
    (by simp [isYesKind])
  have h2 : seedYes (flipFrom d S VoteKind.no off)
      = countOn (isTrack d) isYesKind (flipFrom d S VoteKind.no off) := by
    rw [seedYes_eq_countOn, countOn_isTrack_flipFrom]
  have h3 : seedYes d = countOn (isTrack d) isYesKind d := seedYes_eq_countOn d
  omega

/-- **YES → NO:** `seedNo d' = seedNo d + k`. -/
theorem seedNo_inc_of_eligible (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isYesKind VoteKind.no d off) :
    seedNo (flipFrom d S VoteKind.no off)
      = seedNo d + selFrom S off (List.length d) := by
  have h1 := countOn_dst_flipFrom (isTrack d) S isYesKind isNoKind VoteKind.no d off h
    isNoKind_of_isYesKind (by simp [isNoKind])
  have h2 : seedNo (flipFrom d S VoteKind.no off)
      = countOn (isTrack d) isNoKind (flipFrom d S VoteKind.no off) := by
    rw [seedNo_eq_countOn, countOn_isTrack_flipFrom]
  have h3 : seedNo d = countOn (isTrack d) isNoKind d := seedNo_eq_countOn d
  omega

/-- **YES → NO:** ABSTAIN is invariant. -/
theorem seedAbstain_flip_no_of_eligible (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isYesKind VoteKind.no d off) :
    seedAbstain (flipFrom d S VoteKind.no off) = seedAbstain d := by
  have h1 := countOn_mid_flipFrom (isTrack d) S isYesKind isAbstainKind VoteKind.no d off h
    isYesKind_of_isAbstainKind (by simp [isAbstainKind])
  have h2 : seedAbstain (flipFrom d S VoteKind.no off)
      = countOn (isTrack d) isAbstainKind (flipFrom d S VoteKind.no off) := by
    rw [seedAbstain_eq_countOn, countOn_isTrack_flipFrom]
  have h3 : seedAbstain d = countOn (isTrack d) isAbstainKind d := seedAbstain_eq_countOn d
  omega

/-- **NO → YES:** `seedNo d' + k = seedNo d`. -/
theorem seedNo_dec_of_eligible (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isNoKind VoteKind.yes d off) :
    seedNo (flipFrom d S VoteKind.yes off) + selFrom S off (List.length d) = seedNo d := by
  have h1 := countOn_src_flipFrom (isTrack d) S isNoKind VoteKind.yes d off h
    (by simp [isNoKind])
  have h2 : seedNo (flipFrom d S VoteKind.yes off)
      = countOn (isTrack d) isNoKind (flipFrom d S VoteKind.yes off) := by
    rw [seedNo_eq_countOn, countOn_isTrack_flipFrom]
  have h3 : seedNo d = countOn (isTrack d) isNoKind d := seedNo_eq_countOn d
  omega

/-- **NO → YES:** `seedYes d' = seedYes d + k`. -/
theorem seedYes_inc_of_eligible (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isNoKind VoteKind.yes d off) :
    seedYes (flipFrom d S VoteKind.yes off)
      = seedYes d + selFrom S off (List.length d) := by
  have h1 := countOn_dst_flipFrom (isTrack d) S isNoKind isYesKind VoteKind.yes d off h
    isYesKind_of_isNoKind (by simp [isYesKind])
  have h2 : seedYes (flipFrom d S VoteKind.yes off)
      = countOn (isTrack d) isYesKind (flipFrom d S VoteKind.yes off) := by
    rw [seedYes_eq_countOn, countOn_isTrack_flipFrom]
  have h3 : seedYes d = countOn (isTrack d) isYesKind d := seedYes_eq_countOn d
  omega

/-- **NO → YES:** ABSTAIN is invariant. -/
theorem seedAbstain_flip_yes_of_eligible (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isNoKind VoteKind.yes d off) :
    seedAbstain (flipFrom d S VoteKind.yes off) = seedAbstain d := by
  have h1 := countOn_mid_flipFrom (isTrack d) S isNoKind isAbstainKind VoteKind.yes d off h
    isNoKind_of_isAbstainKind (by simp [isAbstainKind])
  have h2 : seedAbstain (flipFrom d S VoteKind.yes off)
      = countOn (isTrack d) isAbstainKind (flipFrom d S VoteKind.yes off) := by
    rw [seedAbstain_eq_countOn, countOn_isTrack_flipFrom]
  have h3 : seedAbstain d = countOn (isTrack d) isAbstainKind d := seedAbstain_eq_countOn d
  omega

/-- **YES → NO:** `nActive` is invariant (composed from the three shifts). -/
theorem nActive_flip_no_of_eligible (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isYesKind VoteKind.no d off) :
    nActive (flipFrom d S VoteKind.no off) = nActive d :=
  nActive_of_seed_shifts S d off
    (seedYes_dec_of_eligible S d off h)
    (seedNo_inc_of_eligible S d off h)
    (seedAbstain_flip_no_of_eligible S d off h)

/-- **NO → YES:** `nActive` is invariant (symmetric composition). -/
theorem nActive_flip_yes_of_eligible (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isNoKind VoteKind.yes d off) :
    nActive (flipFrom d S VoteKind.yes off) = nActive d := by
  unfold nActive
  have hy := seedYes_inc_of_eligible S d off h
  have hn := seedNo_dec_of_eligible S d off h
  have hab := seedAbstain_flip_yes_of_eligible S d off h
  omega

/-! ## Winner composition (issue #24, L1 — the closing step)

Composes the seed shifts with `winner_no_of_shift` /
`winner_yes_of_shift` (Counterfactual.lean). The two directions keep
their **asymmetric thresholds**: YES→NO flips exactly when
`2·k > seedYes d − seedNo d` (strict), NO→YES when
`2·k ≥ seedNo d − seedYes d` (inclusive — at the exact boundary the
flipped division is a tie, resolved to the YES seed by
`winner_yes_of_ge`). Original ties are excluded in both directions
(`NO < YES` / `YES < NO`), matching the experiment contract of #24. -/

/-- **YES → NO:** with an eligible flip of exactly `k = selFrom S off d.length`
winning-side records, the winner flips to `no` exactly when `2·k > margin`.
`NO < YES` excludes original ties (experiment contract). -/
theorem winner_no_of_eligible_flip
    (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isYesKind VoteKind.no d off)
    (hmajority : seedNo d < seedYes d)
    (hquota : 2 * selFrom S off (List.length d) > seedYes d - seedNo d) :
    winner (flipFrom d S VoteKind.no off) = Winner.no := by
  have h1 := seedYes_dec_of_eligible S d off h
  have h2 := seedNo_inc_of_eligible S d off h
  have hw := winner_no_of_shift d (flipFrom d S VoteKind.no off)
    (selFrom S off (List.length d))
    (by omega) h1 h2
  rw [hw]; exact hquota

/-- **NO → YES:** with an eligible flip of exactly `k = selFrom S off d.length`
losing-side records, the winner becomes `yes` exactly when
`2·k ≥ margin` — the INCLUSIVE boundary. `YES < NO` excludes original
ties. The quota `k = ⌊margin/2⌋ + 1` (`flip_quota_sufficient`) is safe for
both directions, though one record above the NO→YES minimum on even
margins. -/
theorem winner_yes_of_eligible_flip
    (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isNoKind VoteKind.yes d off)
    (hmajority : seedYes d < seedNo d)
    (hquota : 2 * selFrom S off (List.length d) ≥ seedNo d - seedYes d) :
    winner (flipFrom d S VoteKind.yes off) = Winner.yes := by
  have h1 := seedNo_dec_of_eligible S d off h
  have h2 := seedYes_inc_of_eligible S d off h
  have hw := winner_yes_of_shift d (flipFrom d S VoteKind.yes off)
    (selFrom S off (List.length d))
    hmajority h1 h2
  rw [hw]; exact hquota

/-! ## Boundary asymmetry at `2k = margin` (the review's doc-test)

The two directions behave DIFFERENTLY at the exact boundary — this is
the mathematical content of "strict vs inclusive":

* YES→NO at `2k = seedYes d − seedNo d`: **no reversal** — the flipped
  division ties (`seedYes d' = seedNo d'`) and the frozen tie convention
  resolves it to `yes`;
* NO→YES at `2k = seedNo d − seedYes d`: **reversal happens** — the
  winner becomes `yes` (the inclusive branch of `winner_yes_of_shift`). -/

/-- YES→NO at the exact boundary: the flipped division is a tie. -/
theorem seedTie_no_of_eligible_at_boundary (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isYesKind VoteKind.no d off)
    (hmajority : seedNo d ≤ seedYes d)
    (hborder : 2 * selFrom S off (List.length d) = seedYes d - seedNo d) :
    seedYes (flipFrom d S VoteKind.no off) = seedNo (flipFrom d S VoteKind.no off) := by
  have h1 := seedYes_dec_of_eligible S d off h
  have h2 := seedNo_inc_of_eligible S d off h
  omega

/-- YES→NO at the exact boundary: the winner does NOT reverse (stays `yes`
by the tie convention). -/
theorem winner_stays_yes_at_boundary (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isYesKind VoteKind.no d off)
    (hmajority : seedNo d ≤ seedYes d)
    (hborder : 2 * selFrom S off (List.length d) = seedYes d - seedNo d) :
    winner (flipFrom d S VoteKind.no off) = Winner.yes := by
  have htie := seedTie_no_of_eligible_at_boundary S d off h hmajority hborder
  exact winner_yes_of_ge (flipFrom d S VoteKind.no off) (by omega)

/-- NO→YES at the exact boundary: the winner DOES reverse to `yes`. -/
theorem winner_flips_yes_at_boundary (S : Nat → Bool) (d : Division) (off : Nat)
    (h : EligibleFlip (isTrack d) S isNoKind VoteKind.yes d off)
    (hmajority : seedYes d < seedNo d)
    (hborder : 2 * selFrom S off (List.length d) = seedNo d - seedYes d) :
    winner (flipFrom d S VoteKind.yes off) = Winner.yes :=
  winner_yes_of_eligible_flip S d off h hmajority (by omega)

end Sejmbench
