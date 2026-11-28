import Sejmbench.SeedCount

/-!
# Mask bridge (issue #24, L1 - Python indices <-> Lean mask)

Connects the Python-side flip (cf_build.py: flipped_record_indices,
in-place votes[i]["vote"] = lose_vote) with the formal flipFrom:

* maskOf idxs - the mask derived from an index list (S i <-> i in idxs);
* flipAtIndices d idxs lose - the in-place Python flip;
* flipAtIndices_eq_flipFrom - the index-list flip IS the certified
  flipFrom d (maskOf idxs) lose 0 (transformation agreement);
* eligibleFlip_of_indices - if every listed index points at an eligible
  record, the derived mask satisfies the EligibleFlip certificate
  (Python invariant flipped_idx subseteq eligible);
* selectedFrom - the INVERSE direction: the canonical index list of any
  mask over a window; its length IS selFrom (selectedCount = selFrom),
  it is Nodup and in-window, the back-derived mask agrees with S on the
  window, and the flip over the canonical list equals flipFrom.
-/

namespace Sejmbench

instance : Inhabited Record := { default := { club := "", kind := VoteKind.yes } }

/-- The mask derived from an index list: position `i` is selected iff
`i ∈ idxs`. -/
def maskOf (idxs : List Nat) : Nat → Bool := fun i => decide (i ∈ idxs)

/-- The Python-style in-place flip. -/
def flipAtIndices (d : Division) (idxs : List Nat) (lose : VoteKind) : Division :=
  List.mapIdx (fun i r => if i ∈ idxs then flipAt lose r else r) d

/-- Pointwise equal index-functions give equal `mapIdx` results. -/
theorem mapIdx_congr {α : Type} (f g : Nat → α → α) (l : List α)
    (h : ∀ j x, f j x = g j x) : List.mapIdx f l = List.mapIdx g l := by
  induction l generalizing f g with
  | nil => rfl
  | cons x xs ih =>
      simp only [List.mapIdx_cons]
      congr 1
      · exact h 0 x
      · exact ih (fun i x => f (i+1) x) (fun i x => g (i+1) x)
          (fun j x => h (j+1) x)

/-- `flipFrom` at any offset IS a `mapIdx` with the absolutely-indexed
membership predicate. -/
theorem flipFrom_eq_mapIdx (S : Nat → Bool) (lose : VoteKind) :
    ∀ (d : Division) (off : Nat),
      flipFrom d S lose off
        = List.mapIdx (fun i r => if S (off + i) then flipAt lose r else r) d := by
  intro d
  induction d with
  | nil => intro off; simp [flipFrom]
  | cons x xs ih =>
      intro off
      have htail := ih (off + 1)
      show (if S off then flipAt lose x else x)
          :: flipFrom xs S lose (off + 1)
        = List.mapIdx (fun i r => if S (off + i) then flipAt lose r else r) (x :: xs)
      rw [htail, List.mapIdx_cons]
      have hhead : (if S off then flipAt lose x else x)
          = (if S (off + 0) then flipAt lose x else x) := by simp
      rw [hhead]
      have hmap : List.mapIdx (fun i r => if S (off + 1 + i) then flipAt lose r else r) xs
          = List.mapIdx (fun i r => if S (off + (i + 1)) then flipAt lose r else r) xs := by
        apply mapIdx_congr
        intro j r
        simp only [Nat.add_assoc, Nat.add_comm 1 j]
      rw [hmap]

/-- **Transformation agreement:** the index-list flip IS the certified
`flipFrom` at offset 0 with the derived mask. -/
theorem flipAtIndices_eq_flipFrom (d : Division) (idxs : List Nat) (lose : VoteKind) :
    flipAtIndices d idxs lose = flipFrom d (maskOf idxs) lose 0 := by
  have h1 := flipFrom_eq_mapIdx (maskOf idxs) lose d 0
  rw [h1, flipAtIndices]
  apply mapIdx_congr
  intro j r
  simp [maskOf]

/-- **Certificate from the index list (mask form).** If the mask selects only
records that satisfy the club/kind eligibility at `off + j`, the derived mask
satisfies the `EligibleFlip` certificate. Offset-general so the induction
generalizes over `off`. -/
theorem eligibleFlip_maskOf (P : String → Bool) (srcKind : VoteKind → Bool)
    (lose : VoteKind) :
    ∀ (d : Division) (idxs : List Nat) (off : Nat),
      (∀ j, j < d.length → maskOf idxs (off + j) = true →
        P (d[j]!).club ∧ srcKind (d[j]!).kind) →
      EligibleFlip P (maskOf idxs) srcKind lose d off := by
  intro d
  induction d with
  | nil => intro idxs off _; exact EligibleFlip.nil off
  | cons r rest ih =>
      intro idxs off helig
      by_cases hsel : maskOf idxs off = true
      case pos =>
        have hr := helig 0 (by simp) hsel
        refine EligibleFlip.sel (lose := lose) r rest off hsel hr.1 hr.2 (ih idxs (off + 1) ?_)
        intro j hj hmask
        have hm : maskOf idxs (off + (j + 1)) = true := by
          rw [Nat.add_assoc, Nat.add_comm 1 j] at hmask
          exact hmask
        have hlen : (r :: rest).length = rest.length + 1 := rfl
        exact helig (j + 1) (by omega) hm
      case neg =>
        have hnot : ¬ (maskOf idxs off = true) := by
          intro hc; exact hsel hc
        refine EligibleFlip.keep (lose := lose) r rest off hnot (ih idxs (off + 1) ?_)
        intro j hj hmask
        have hm : maskOf idxs (off + (j + 1)) = true := by
          rw [Nat.add_assoc, Nat.add_comm 1 j] at hmask
          exact hmask
        have hlen : (r :: rest).length = rest.length + 1 := rfl
        exact helig (j + 1) (by omega) hm

/-- **Certificate from the index list:** every index in `idxs` is an in-range
pointer to an eligible record of `d`, so the derived mask satisfies the
`EligibleFlip` certificate at offset 0 — the Python invariant
`flipped_idx ⊆ eligible`.

The hypothesis is split (per review of 7b5b496): `hRange` forces every listed
index to point at an existing record (otherwise `helig` was satisfiable
vacuously by out-of-range indices, which the Python indexer would reject),
and `hElig` states the eligibility of each pointed record. -/
theorem eligibleFlip_of_indices (P : String → Bool) (srcKind : VoteKind → Bool)
    (lose : VoteKind) (d : Division) (idxs : List Nat)
    (hRange : ∀ i ∈ idxs, i < d.length)
    (hElig : ∀ i ∈ idxs, P (d[i]!).club ∧ srcKind (d[i]!).kind) :
    EligibleFlip P (maskOf idxs) srcKind lose d 0 := by
  apply eligibleFlip_maskOf P srcKind lose d idxs 0
  intro j _hj hmask
  have hmem : j ∈ idxs := by simpa [maskOf] using hmask
  have _hr : j < d.length := hRange j hmem
  exact hElig j hmem

/-! ### Index-window count agreement (Nodup + range)

Python's generator produces `flipped_idx = sorted(pick_rng.sample(eligible, k))`
— indices in range and unique (`random.sample` samples without replacement).
The formal counterpart: the mask derived from a Nodup, in-window index list
selects exactly `idxs.length` positions, so the Python quota
`k = len(flipped_record_indices)` equals the Lean certificate's
`k = selFrom (maskOf idxs) 0 d.length`. -/

/-- Unfolding lemma for the step of `selFrom`. -/
theorem selFrom_succ (S : Nat → Bool) (off n : Nat) :
    selFrom S off (n + 1) = (if S off then 1 else 0) + selFrom S (off + 1) n := rfl

/-- Pointwise-equal masks on the window give equal counts. -/
theorem selFrom_congr (S T : Nat → Bool) :
    ∀ (off n : Nat), (∀ j, j < n → S (off + j) = T (off + j)) →
      selFrom S off n = selFrom T off n := by
  intro off n
  induction n generalizing off with
  | zero => intro _; rfl
  | succ m ih =>
      intro h
      have hhead : S off = T off := h 0 (by omega)
      have htail : ∀ j, j < m → S (off + 1 + j) = T (off + 1 + j) := by
        intro j hj
        have h1 := h (j + 1) (by omega)
        have heq : off + 1 + j = off + (j + 1) := by omega
        rw [heq]
        exact h1
      simp only [selFrom_succ, hhead, ih (off + 1) htail]

/-- An element of `idxs.erase x` differs from `x` (with `idxs` Nodup). -/
theorem ne_of_mem_erase (x : Nat) :
    ∀ (idxs : List Nat), idxs.Nodup → ∀ i : Nat, i ∈ idxs.erase x → i ≠ x := by
  intro idxs
  induction idxs with
  | nil => intro _ i h; simp at h
  | cons y ys ih =>
      intro hnd i h
      by_cases hy : y = x
      · subst hy
        rw [List.erase_cons_head] at h
        have h9 : ¬ (y ∈ ys) := (List.nodup_cons.mp hnd).1
        exact fun heq => by
          rw [heq] at h
          exact h9 h
      · rw [List.erase_cons_tail (by simp [hy] : ¬(y == x) = true)] at h
        rcases List.mem_cons.mp h with rfl | h2
        · exact hy
        · exact ih (List.nodup_cons.mp hnd).2 i h2

/-- **Count agreement (window form).** For a Nodup index list entirely inside
the window `[off, off + n)`, the mask selects exactly `idxs.length` positions. -/
theorem selFrom_maskOf_window (idxs : List Nat) :
    ∀ (off n : Nat), idxs.Nodup →
      (∀ i ∈ idxs, off ≤ i) → (∀ i ∈ idxs, i < off + n) →
      selFrom (maskOf idxs) off n = idxs.length := by
  intro off n
  induction n generalizing idxs off with
  | zero =>
      intro hnd hLo hHi
      cases idxs with
      | nil => rfl
      | cons a rest =>
          exfalso
          have h1 := hLo a (by simp)
          have h2 := hHi a (by simp)
          omega
  | succ m ih =>
      intro hnd hLo hHi
      by_cases hpos : maskOf idxs off = true
      · have hmem : off ∈ idxs := by simpa [maskOf] using hpos
        have hcongr : ∀ j, j < m →
            maskOf idxs (off + 1 + j) = maskOf (idxs.erase off) (off + 1 + j) := by
          intro j hj
          have hne : off + 1 + j ≠ off := by omega
          have hmemE : (off + 1 + j) ∈ idxs.erase off ↔ (off + 1 + j) ∈ idxs :=
            List.mem_erase_of_ne hne
          unfold maskOf
          simp only [hmemE]
        have hnoderase : (idxs.erase off).Nodup := hnd.erase off
        have hLo2 : ∀ i ∈ idxs.erase off, off + 1 ≤ i := by
          intro i hi
          have h1 := List.mem_of_mem_erase hi
          have h2 := ne_of_mem_erase off idxs hnd i hi
          have h3 := hLo i h1
          omega
        have hHi2 : ∀ i ∈ idxs.erase off, i < (off + 1) + m := by
          intro i hi
          have h1 := List.mem_of_mem_erase hi
          have h2 := hHi i h1
          omega
        have hlen : (idxs.erase off).length = idxs.length - 1 :=
          List.length_erase_of_mem hmem
        have hlen0 : 0 < idxs.length := List.length_pos_of_mem hmem
        have hstep : selFrom (maskOf idxs) off (m + 1)
            = 1 + selFrom (maskOf (idxs.erase off)) (off + 1) m := by
          rw [selFrom_succ, hpos]
          show 1 + selFrom (maskOf idxs) (off + 1) m
              = 1 + selFrom (maskOf (idxs.erase off)) (off + 1) m
          rw [selFrom_congr _ _ (off + 1) m hcongr]
        rw [hstep, ih (idxs.erase off) (off + 1) hnoderase hLo2 hHi2, hlen]
        omega
      · have hnotmem : ¬ (off ∈ idxs) := by simpa [maskOf] using hpos
        have hne : ∀ i ∈ idxs, i ≠ off := by
          intro i hi heq
          subst heq
          exact hnotmem hi
        have hLo2 : ∀ i ∈ idxs, off + 1 ≤ i := by
          intro i hi
          have h3 := hLo i hi
          have h4 := hne i hi
          omega
        have hHi2 : ∀ i ∈ idxs, i < (off + 1) + m := by
          intro i hi
          have h2 := hHi i hi
          omega
        have hfalse : maskOf idxs off = false := by
          cases h : maskOf idxs off with
          | true => exact absurd h hpos
          | false => rfl
        rw [selFrom_succ, hfalse]
        show 0 + selFrom (maskOf idxs) (off + 1) m = idxs.length
        rw [ih idxs (off + 1) hnd hLo2 hHi2]
        omega

/-- **Count agreement.** For a Nodup index list pointing inside `n`, the mask
derived from the list selects exactly `idxs.length` positions of `[0, n)`:
`k_Python = len(flipped_record_indices) = selFrom (maskOf idxs) 0 n = k_Lean`. -/
theorem selFrom_maskOf_eq_length (idxs : List Nat) (n : Nat)
    (hNodup : idxs.Nodup) (hRange : ∀ i ∈ idxs, i < n) :
    selFrom (maskOf idxs) 0 n = idxs.length :=
  selFrom_maskOf_window idxs 0 n hNodup (fun i _ => Nat.zero_le i)
    (fun i hi => by have := hRange i hi; omega)

/-! ### The canonical index list of a mask (mask → list direction)

`maskOf` turns a Python index list into a mask; `selectedFrom` is the
INVERSE: the canonical, increasing index list of the positions of the
window `[off, off + n)` where the mask is true. This is the
`selectedIndices` / `List (Fin d.length)` bridge: every element is
provably in-window (`selectedFrom_bound` — i.e. a valid `Fin` index at
offset 0), the list is Nodup, and its length IS the mask's count
`selFrom S off n` — the `selectedCount = selFrom` tie, now for ANY mask
(the list → mask direction is `selFrom_maskOf_eq_length`). The flip over
the canonical list agrees with `flipFrom` (`flipFrom_eq_flipAtIndices`),
and the count is invariant under the list → mask → list round trip. -/

/-- A range-restricted `mapIdx` congruence: the functions are compared
only on the indices `mapIdx` actually queries. -/
theorem mapIdx_congr_range {α : Type} (f g : Nat → α → α) (l : List α)
    (h : ∀ i x, i < l.length → f i x = g i x) : List.mapIdx f l = List.mapIdx g l := by
  induction l generalizing f g with
  | nil => rfl
  | cons x xs ih =>
      simp only [List.mapIdx_cons]
      congr 1
      · exact h 0 x (by simp)
      · exact ih (fun i y => f (i + 1) y) (fun i y => g (i + 1) y)
          (fun j y hj => h (j + 1) y (by
            have hlen : (x :: xs).length = xs.length + 1 := rfl
            omega))

/-- The canonical index list of the mask `S` over the window
`[off, off + n)`: the selected positions, increasing. -/
def selectedFrom (S : Nat → Bool) (off : Nat) : Nat → List Nat
  | 0 => []
  | n + 1 => if S off then off :: selectedFrom S (off + 1) n else selectedFrom S (off + 1) n

/-- **`selectedCount = selFrom` (the P1 tie).** The canonical index list
of the mask has exactly `selFrom S off n` elements — only existing
records (positions inside the window) are counted. -/
theorem selectedFrom_length (S : Nat → Bool) (off : Nat) :
    ∀ n, (selectedFrom S off n).length = selFrom S off n := by
  intro n
  induction n generalizing off with
  | zero => rfl
  | succ m ih =>
      by_cases hs : S off = true
      · rw [selectedFrom, if_pos hs, List.length_cons, selFrom_succ, if_pos hs, ih (off + 1)]
        omega
      · rw [selectedFrom, if_neg hs, selFrom_succ, if_neg hs, ih (off + 1)]
        omega

/-- Every element of the canonical index list lies in the window
`[off, off + n)` — at offset 0, exactly the `Fin d.length` range bound. -/
theorem selectedFrom_bound (S : Nat → Bool) (off : Nat) :
    ∀ n x, x ∈ selectedFrom S off n → off ≤ x ∧ x < off + n := by
  intro n
  induction n generalizing off with
  | zero => intro x h; simp [selectedFrom] at h
  | succ m ih =>
      intro x h
      by_cases hs : S off = true
      · rw [selectedFrom, if_pos hs, List.mem_cons] at h
        rcases h with rfl | h2
        · omega
        · have h3 := ih (off + 1) x h2
          omega
      · rw [selectedFrom, if_neg hs] at h
        have h3 := ih (off + 1) x h
        omega

/-- **Membership characterization.** `x` is in the canonical index list
iff `x` is an in-window position the mask selects. -/
theorem selectedFrom_mem (S : Nat → Bool) (off : Nat) :
    ∀ n x, x ∈ selectedFrom S off n ↔ (off ≤ x ∧ x < off + n ∧ S x = true) := by
  intro n
  induction n generalizing off with
  | zero =>
      intro x
      have hnil : ¬ (x ∈ selectedFrom S off 0) := by simp [selectedFrom]
      constructor
      · intro hmem; exact absurd hmem hnil
      · intro h
        have h1 := h.1
        have h2 := h.2.1
        omega
  | succ m ih =>
      intro x
      by_cases hs : S off = true
      · rw [selectedFrom, if_pos hs, List.mem_cons]
        constructor
        · rintro (rfl | h2)
          · exact ⟨by omega, by omega, hs⟩
          · have h3 := (ih (off + 1) x).mp h2
            exact ⟨by omega, by omega, h3.2.2⟩
        · rintro ⟨h1, h2, h3⟩
          by_cases hxE : x = off
          · subst hxE; exact Or.inl rfl
          · exact Or.inr ((ih (off + 1) x).mpr ⟨by omega, by omega, h3⟩)
      · rw [selectedFrom, if_neg hs]
        rw [ih (off + 1) x]
        constructor
        · rintro ⟨h1, h2, h3⟩
          exact ⟨by omega, by omega, h3⟩
        · rintro ⟨h1, h2, h3⟩
          have h3copy := h3
          have hne : x ≠ off := by
            intro heq
            rw [heq] at h3copy
            exact hs h3copy
          exact ⟨by omega, by omega, h3⟩

/-- The canonical index list is Nodup — each step's head `off` is below
every element of the tail (which lives in `[off + 1, off + 1 + n)`). -/
theorem selectedFrom_nodup (S : Nat → Bool) (off : Nat) :
    ∀ n, (selectedFrom S off n).Nodup := by
  intro n
  induction n generalizing off with
  | zero => simp [selectedFrom]
  | succ m ih =>
      by_cases hs : S off = true
      · rw [selectedFrom, ite_eq_left hs, List.nodup_cons]
        refine ⟨fun hmem => ?_, ih (off + 1)⟩
        have h3 := selectedFrom_bound S (off + 1) m off hmem
        omega
      · rw [selectedFrom, ite_eq_right hs]
        exact ih (off + 1)

/-- The mask derived BACK from the canonical index list agrees with `S`
at every in-window position (no information is lost on the window). -/
theorem maskOf_selectedFrom (S : Nat → Bool) (off : Nat) :
    ∀ (n j : Nat), off ≤ j → j < off + n → maskOf (selectedFrom S off n) j = S j := by
  intro n j hLo hHi
  have hmem : j ∈ selectedFrom S off n ↔ S j = true := by
    rw [selectedFrom_mem]
    exact ⟨fun h => h.2.2, fun h => ⟨hLo, hHi, h⟩⟩
  unfold maskOf
  by_cases hs : S j = true
  · simp [hmem, hs]
  · have hjf : S j = false := by
      cases h : S j with
      | true => exact absurd h hs
      | false => rfl
    simp [hmem, hjf]

/-- **Transformation agreement (mask → list direction).** The flip over
the canonical index list IS the certified flip — the mirror of
`flipAtIndices_eq_flipFrom`, which goes list → mask. Stated at offset 0,
the form the Python flip uses: `flipAtIndices` tests POSITION indices
against the absolute-index list, and at offset 0 position = absolute. -/
theorem flip_eq_flipAtIndices (S : Nat → Bool) (lose : VoteKind) (d : Division) :
    flip d S lose = flipAtIndices d (selectedFrom S 0 (List.length d)) lose := by
  have hflip : flip d S lose = flipFrom d S lose 0 := rfl
  rw [hflip, flipFrom_eq_mapIdx, flipAtIndices]
  apply mapIdx_congr_range
  intro i r hi
  have hmem : i ∈ selectedFrom S 0 (List.length d) ↔ S i = true := by
    rw [selectedFrom_mem]
    constructor
    · rintro ⟨_, h2, h3⟩; exact h3
    · intro h3; exact ⟨by omega, by have := hi; omega, h3⟩
  by_cases hs : S i = true
  · simp [hmem, hs]
  · have hjf : S i = false := by
      cases h : S i with
      | true => exact absurd h hs
      | false => rfl
    simp [hmem, hjf]

/-- **Count round-trip.** `selFrom` is invariant under the list → mask →
list cycle: the canonical index list of any mask yields the same count.
Together with `selFrom_maskOf_eq_length` (the mask-derived direction)
this closes the count bridge in both directions. -/
theorem selFrom_maskOf_selectedFrom (S : Nat → Bool) (n : Nat) :
    selFrom (maskOf (selectedFrom S 0 n)) 0 n = selFrom S 0 n := by
  have hnd := selectedFrom_nodup S 0 n
  have hrange : ∀ i ∈ selectedFrom S 0 n, i < n := by
    intro i hi
    have h := selectedFrom_bound S 0 n i hi
    omega
  rw [selFrom_maskOf_eq_length _ n hnd hrange]
  rw [selectedFrom_length]

end Sejmbench
