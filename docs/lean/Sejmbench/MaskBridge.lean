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
  (Python invariant flipped_idx subseteq eligible).
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

end Sejmbench
