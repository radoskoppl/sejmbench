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

/-- **Certificate from the index list:** if every index in `idxs` points at
an eligible record of `d`, the derived mask satisfies `EligibleFlip` at
offset 0 — the Python invariant `flipped_idx ⊆ eligible`. -/
theorem eligibleFlip_of_indices (P : String → Bool) (srcKind : VoteKind → Bool)
    (lose : VoteKind) (d : Division) (idxs : List Nat)
    (helig : ∀ i ∈ idxs, i < d.length → P (d[i]!).club ∧ srcKind (d[i]!).kind) :
    EligibleFlip P (maskOf idxs) srcKind lose d 0 := by
  induction d generalizing idxs with
  | nil => exact EligibleFlip.nil 0
  | cons r rest ih =>
      intro idxs off helig
      by_cases hsel : maskOf idxs (0 + j) = true
      case pos =>
        have hr := helig 0 hsel (by simp)
        have hmask2 : maskOf idxs (off + (j + 1)) = true := hmask
        have hel := helig (j + 1) (by omega) hmask2
        refine EligibleFlip.sel (lose := lose) r rest off hsel hr.1 hr.2 hel
      case neg =>
        have hnot : ¬ (maskOf idxs off = true) := by intro hc; exact hsel hc
        have hmask2 : maskOf idxs (off + j) = true := hmask
        have hel := helig (j + 1) (by omega) hmask2
        exact EligibleFlip.keep (lose := lose) r rest (off+1) hnot hel

end Sejmbench
