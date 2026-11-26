import Sejmbench.Counterfactual
import Sejmbench.EvaluationMetrics
import Sejmbench.SeedCount

/-!
# Pool & stratification (issue #24 — pool formalization, per the #22 contract)

The pool layer over `ModelResponsePair`s. Design decisions frozen by the
review of `49401d2` (round 4, judge-approved):

* **Stratification axis is the ORIGINAL margin** — `originalMarginBand`
  describes how hard the original result was to overturn (narrow ≤ 5,
  close 6–50, wide ≥ 51), computed from `margin` of the original
  division. The perturbed margin is a diagnostic quantity
  (`perturbedMargin`), NOT a partition dimension.
* **Cell key** = `(perturbedGT, direction, originalMarginBand)` — the
  class used for balancing and the leakage gate is the perturbed GT;
  direction and the original-margin band are the two remaining
  stratification dimensions.
* **Projections, not free fields**: `PoolItem` carries only `itemId`
  and the pair; the cell key is *computed* from the pair. Manifest
  convenience fields would need conformance proofs — none are stored.
* **Aggregation contract**: cell counts sum to the pool count (proofs
  below, separately for the pair level `N` and the answer level `2N`).
  No unweighted-mean claim is made anywhere.

Open conditions stated as explicit predicates: `poolWellFormed`
(unique `itemId`s), `poolLeakageGate` (`20·max(nY,nN) < 11·(nY+nN)`,
i.e. the best constant perturbed-class predictor stays below 0.55), and
`minCellSize` (a minimum cell occupancy, independent of the gate).
-/

namespace Sejmbench

/-! ## Margins over a candidate pair -/

/-- Original division of a candidate (either direction). -/
def sumOriginal (c : Sum FlipPair FlipPairRev) : Division :=
  match c with
  | .inl p => p.original
  | .inr p => p.original

/-- Perturbed division of a candidate (either direction). -/
def sumPerturbed (c : Sum FlipPair FlipPairRev) : Division :=
  match c with
  | .inl p => p.perturbed
  | .inr p => p.perturbed

/-- |margin| of a division — the magnitude of the seed margin. -/
def marginAbs (d : Division) : Nat := (margin d).natAbs

/-- The ORIGINAL margin (before perturbation) of a response pair — the
stratification axis per #22/#24. -/
def ModelResponsePair.originalMargin (r : ModelResponsePair) : Nat :=
  marginAbs (sumOriginal r.pair.candidate)

/-- The PERTURBED margin (after perturbation) — diagnostic only; it is
NOT a partition dimension. -/
def ModelResponsePair.perturbedMargin (r : ModelResponsePair) : Nat :=
  marginAbs (sumPerturbed r.pair.candidate)

/-! ## Margin bands (narrow ≤ 5, close 6–50, wide ≥ 51) -/

/-- The three difficulty bands. `narrow` = margin at most 5, `close` =
6–50, `wide` = 51 and above. -/
inductive MarginBand where
  | narrow | close | wide

/-- The band classifier: which band a margin magnitude falls into. -/
def MarginBand.of (m : Nat) : MarginBand :=
  if m ≤ 5 then .narrow else if m ≤ 50 then .close else .wide

/-- Conformance, case 1: the classifier returns `narrow` iff the margin
is at most 5. -/
theorem MarginBand.of_narrow_iff (m : Nat) :
    MarginBand.of m = MarginBand.narrow ↔ m ≤ 5 := by
  unfold MarginBand.of
  by_cases h1 : m ≤ 5 <;> by_cases h2 : m ≤ 50 <;> simp [h1, h2] <;> omega

/-- Conformance, case 2: the classifier returns `close` iff the margin
is in 6–50. -/
theorem MarginBand.of_close_iff (m : Nat) :
    MarginBand.of m = MarginBand.close ↔ 5 < m ∧ m ≤ 50 := by
  unfold MarginBand.of
  by_cases h1 : m ≤ 5 <;> by_cases h2 : m ≤ 50 <;> simp [h1, h2] <;> omega

/-- Conformance, case 3: the classifier returns `wide` iff the margin
is at least 51. -/
theorem MarginBand.of_wide_iff (m : Nat) :
    MarginBand.of m = MarginBand.wide ↔ 50 < m := by
  unfold MarginBand.of
  by_cases h1 : m ≤ 5 <;> by_cases h2 : m ≤ 50 <;> simp [h1, h2] <;> omega

/-- The direction of a reversal pair, derived from the original GT
(the confirmed pair guarantees the perturbed GT differs). -/
inductive Direction where
  | yesToNo | noToYes

/-- Direction of a response pair: which way the confirmed reversal goes. -/
def ModelResponsePair.direction (r : ModelResponsePair) : Direction :=
  match r.originalGT with
  | .yes => Direction.yesToNo
  | .no => Direction.noToYes

/-! ## Pool items and cells -/

/-- A pool item: a unique identifier bound to a response pair. All
stratification attributes (GT, direction, margin band) are *computed*
from the pair — the item stores no independent metadata that could
disagree with it. -/
structure PoolItem where
  /-- The unique item identifier. -/
  itemId : Nat
  /-- The confirmed reversal experiment's responses. -/
  pair : ModelResponsePair

/-- The original-margin band of an item, computed from the pair. -/
def PoolItem.band (p : PoolItem) : MarginBand :=
  MarginBand.of p.pair.originalMargin

/-- Pointwise equality on `Winner` (avoids deriving instances). -/
def sameGT (a b : Winner) : Bool :=
  match a, b with | .yes, .yes => true | .no, .no => true | _, _ => false

/-- Pointwise equality on `Direction`. -/
def sameDir (a b : Direction) : Bool :=
  match a, b with | .yesToNo, .yesToNo => true | .noToYes, .noToYes => true | _, _ => false

/-- Pointwise equality on `MarginBand`. -/
def sameBand (a b : MarginBand) : Bool :=
  match a, b with
  | .narrow, .narrow => true | .close, .close => true | .wide, .wide => true | _, _ => false

/-- Is the item in the `(perturbedGT = w, direction = d, band = b)` cell? -/
def PoolItem.inCell (p : PoolItem) (w : Winner) (d : Direction) (b : MarginBand) : Bool :=
  sameGT p.pair.perturbedGT w && sameDir p.pair.direction d && sameBand p.band b

/-- Count of pool items in the given cell (nested-filter form, matching
the partition lemmas). -/
def cellCount (pool : List PoolItem) (w : Winner) (d : Direction) (b : MarginBand) : Nat :=
  (((pool.filter (fun p => sameGT p.pair.perturbedGT w)).filter
      (fun p => sameDir p.pair.direction d)).filter
      (fun p => sameBand p.band b)).length

/-- Count of pool items with the given perturbed GT. -/
def gtCount (pool : List PoolItem) (w : Winner) : Nat :=
  (pool.filter (fun p => sameGT p.pair.perturbedGT w)).length

/-- Count of pool items in the `(perturbedGT = w, direction = d)` slice. -/
def gdCount (pool : List PoolItem) (w : Winner) (d : Direction) : Nat :=
  ((pool.filter (fun p => sameGT p.pair.perturbedGT w)).filter
      (fun p => sameDir p.pair.direction d)).length

/-! ## Pointwise partitions -/

/-- A predicate and its pointwise complement split any list. -/
theorem filter_complement {α : Type} (f : α → Bool) (l : List α) :
    (l.filter f).length + (l.filter (fun x => !(f x))).length = l.length := by
  induction l with
  | nil => simp
  | cons a rest ih =>
      by_cases h : f a = true
      · have h1 : (List.filter f (a :: rest)).length
            = (List.filter f rest).length + 1 := by
          rw [List.filter_cons_of_pos h, List.length_cons]
        have h2 : (List.filter (fun x => !(f x)) (a :: rest)).length
            = (List.filter (fun x => !(f x)) rest).length := by
          rw [List.filter_cons_of_neg (p := fun x => !(f x)) (by simp [h])]
        rw [h1, h2, List.length_cons]
        omega
      · have h3 : (List.filter f (a :: rest)).length
            = (List.filter f rest).length := by
          rw [List.filter_cons_of_neg h]
        have h4 : (!(f a)) = true := by simp [h]
        have h5 : (List.filter (fun x => !(f x)) (a :: rest)).length
            = (List.filter (fun x => !(f x)) rest).length + 1 := by
          rw [List.filter_cons_of_pos (p := fun x => !(f x)) h4, List.length_cons]
        rw [h3, h5, List.length_cons]
        omega

/-- Three pointwise-disjoint, exhaustive predicates split any list. -/
theorem filter_split3 {α : Type} (f g h : α → Bool)
    (hex : ∀ x, (f x || g x || h x) = true)
    (hd1 : ∀ x, (!(f x && g x)) = true) (hd2 : ∀ x, (!(f x && h x)) = true)
    (hd3 : ∀ x, (!(g x && h x)) = true) (l : List α) :
    (l.filter f).length + (l.filter g).length + (l.filter h).length = l.length := by
  induction l with
  | nil => simp
  | cons a rest ih =>
      by_cases h1 : f a = true
      · have hng : (!(f a && g a)) = true := hd1 a
        have hga : g a = false := by
          cases hg : g a with
          | false => rfl
          | true => simp [h1, hg] at hng
        have hna2 : (!(f a && h a)) = true := hd2 a
        have hha : h a = false := by
          cases hh : h a with
          | false => rfl
          | true => simp [h1, hh] at hna2
        have e1 : (List.filter f (a :: rest)).length
            = (List.filter f rest).length + 1 := by
          rw [List.filter_cons_of_pos h1, List.length_cons]
        have e2 : (List.filter g (a :: rest)).length
            = (List.filter g rest).length := by
          rw [List.filter_cons_of_neg (p := g) (by simp [hga])]
        have e3 : (List.filter h (a :: rest)).length
            = (List.filter h rest).length := by
          rw [List.filter_cons_of_neg (p := h) (by simp [hha])]
        rw [e1, e2, e3, List.length_cons]
        omega
      · by_cases h2 : g a = true
        · have hna3 : (!(g a && h a)) = true := hd3 a
          have hha : h a = false := by
            cases hh : h a with
            | false => rfl
            | true =>
              exfalso
              rw [h2, hh] at hna3
              simp at hna3
          have e1 : (List.filter f (a :: rest)).length
              = (List.filter f rest).length := by
            rw [List.filter_cons_of_neg h1]
          have e2 : (List.filter g (a :: rest)).length
              = (List.filter g rest).length + 1 := by
            rw [List.filter_cons_of_pos h2, List.length_cons]
          have e3 : (List.filter h (a :: rest)).length
              = (List.filter h rest).length := by
            rw [List.filter_cons_of_neg (p := h) (by simp [hha])]
          rw [e1, e2, e3, List.length_cons]
          omega
        · have hexp : (f a || g a || h a) = true := hex a
          have h3 : h a = true := by
            cases hh : h a with
            | false => simp [h1, h2, hh] at hexp
            | true => rfl
          have e1 : (List.filter f (a :: rest)).length
              = (List.filter f rest).length := by
            rw [List.filter_cons_of_neg h1]
          have e2 : (List.filter g (a :: rest)).length
              = (List.filter g rest).length := by
            rw [List.filter_cons_of_neg h2]
          have e3 : (List.filter h (a :: rest)).length
              = (List.filter h rest).length + 1 := by
            rw [List.filter_cons_of_pos h3, List.length_cons]
          rw [e1, e2, e3, List.length_cons]
          omega

/-- The two GT predicates are pointwise complementary. -/
theorem sameGT_no_compl (x : Winner) : (!(sameGT x Winner.yes)) = sameGT x Winner.no := by
  cases x <;> simp [sameGT]

/-- The two direction predicates are pointwise complementary. -/
theorem sameDir_no_compl (x : Direction) :
    (!(sameDir x Direction.yesToNo)) = sameDir x Direction.noToYes := by
  cases x <;> simp [sameDir]

/-- The three band predicates are pointwise disjoint and exhaustive. -/
theorem sameBand_trichotomy (x : MarginBand) :
    (sameBand x MarginBand.narrow || sameBand x MarginBand.close
      || sameBand x MarginBand.wide) = true
      ∧ (!(sameBand x MarginBand.narrow && sameBand x MarginBand.close)) = true
      ∧ (!(sameBand x MarginBand.narrow && sameBand x MarginBand.wide)) = true
      ∧ (!(sameBand x MarginBand.close && sameBand x MarginBand.wide)) = true := by
  cases x <;> simp [sameBand]

/-! ## Cell summation identities -/

/-- Within a `(perturbedGT, direction)` slice, the three band cells
sum to the slice count. -/
theorem band_cell_sum (pool : List PoolItem) (w : Winner) (d : Direction) :
    cellCount pool w d MarginBand.narrow
      + cellCount pool w d MarginBand.close
      + cellCount pool w d MarginBand.wide
      = gdCount pool w d := by
  unfold cellCount gdCount
  exact filter_split3
    (fun p : PoolItem => sameBand p.band MarginBand.narrow)
    (fun p : PoolItem => sameBand p.band MarginBand.close)
    (fun p : PoolItem => sameBand p.band MarginBand.wide)
    (fun p => (sameBand_trichotomy p.band).1)
    (fun p => (sameBand_trichotomy p.band).2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.2)
    ((pool.filter (fun p => sameGT p.pair.perturbedGT w)).filter
      (fun p => sameDir p.pair.direction d))

/-- Within a perturbed-GT class, the two direction slices sum to the
class count. -/
theorem dir_cell_sum (pool : List PoolItem) (w : Winner) :
    gdCount pool w Direction.yesToNo + gdCount pool w Direction.noToYes
      = gtCount pool w := by
  unfold gdCount gtCount
  have h := filter_complement
    (fun p : PoolItem => sameDir p.pair.direction Direction.yesToNo)
    (pool.filter (fun p => sameGT p.pair.perturbedGT w))
  have hEq : (pool.filter (fun p => sameGT p.pair.perturbedGT w)).filter
        (fun x => !(sameDir x.pair.direction Direction.yesToNo))
      = (pool.filter (fun p => sameGT p.pair.perturbedGT w)).filter
        (fun p => sameDir p.pair.direction Direction.noToYes) := by
    refine List.filter_congr (fun x _ => ?_)
    exact sameDir_no_compl x.pair.direction
  rw [hEq] at h
  omega

/-- The two perturbed-GT classes exhaust the pool. -/
theorem gt_cell_sum (pool : List PoolItem) :
    gtCount pool Winner.yes + gtCount pool Winner.no = pool.length := by
  unfold gtCount
  have h := filter_complement
    (fun p : PoolItem => sameGT p.pair.perturbedGT Winner.yes) pool
  have hEq : (pool.filter (fun x => !(sameGT x.pair.perturbedGT Winner.yes)))
      = pool.filter (fun p => sameGT p.pair.perturbedGT Winner.no) := by
    refine List.filter_congr (fun x _ => ?_)
    exact sameGT_no_compl x.pair.perturbedGT
  rw [hEq] at h
  omega

/-- **The 12-cell partition is exhaustive**: the twelve cell counts sum
to the pool size. Composition of `gt_cell_sum` × `dir_cell_sum` ×
`band_cell_sum`. -/
theorem cellCount_sum (pool : List PoolItem) :
    cellCount pool Winner.yes Direction.yesToNo MarginBand.narrow
      + cellCount pool Winner.yes Direction.yesToNo MarginBand.close
      + cellCount pool Winner.yes Direction.yesToNo MarginBand.wide
      + cellCount pool Winner.yes Direction.noToYes MarginBand.narrow
      + cellCount pool Winner.yes Direction.noToYes MarginBand.close
      + cellCount pool Winner.yes Direction.noToYes MarginBand.wide
      + cellCount pool Winner.no Direction.yesToNo MarginBand.narrow
      + cellCount pool Winner.no Direction.yesToNo MarginBand.close
      + cellCount pool Winner.no Direction.yesToNo MarginBand.wide
      + cellCount pool Winner.no Direction.noToYes MarginBand.narrow
      + cellCount pool Winner.no Direction.noToYes MarginBand.close
      + cellCount pool Winner.no Direction.noToYes MarginBand.wide
      = pool.length := by
  have h1 := band_cell_sum pool Winner.yes Direction.yesToNo
  have h2 := band_cell_sum pool Winner.yes Direction.noToYes
  have h3 := band_cell_sum pool Winner.no Direction.yesToNo
  have h4 := band_cell_sum pool Winner.no Direction.noToYes
  have h5 := dir_cell_sum pool Winner.yes
  have h6 := dir_cell_sum pool Winner.no
  have h7 := gt_cell_sum pool
  omega

/-- **Answer-slot version**: each cell holds `2 ×` its pair count in
answer slots, and the twelve answer-slot counts sum to `nAnswers`.
This is the `2N` counterpart of `cellCount_sum`. -/
theorem answerCellCount_sum (pool : List PoolItem) :
    2 * cellCount pool Winner.yes Direction.yesToNo MarginBand.narrow
      + 2 * cellCount pool Winner.yes Direction.yesToNo MarginBand.close
      + 2 * cellCount pool Winner.yes Direction.yesToNo MarginBand.wide
      + 2 * cellCount pool Winner.yes Direction.noToYes MarginBand.narrow
      + 2 * cellCount pool Winner.yes Direction.noToYes MarginBand.close
      + 2 * cellCount pool Winner.yes Direction.noToYes MarginBand.wide
      + 2 * cellCount pool Winner.no Direction.yesToNo MarginBand.narrow
      + 2 * cellCount pool Winner.no Direction.yesToNo MarginBand.close
      + 2 * cellCount pool Winner.no Direction.yesToNo MarginBand.wide
      + 2 * cellCount pool Winner.no Direction.noToYes MarginBand.narrow
      + 2 * cellCount pool Winner.no Direction.noToYes MarginBand.close
      + 2 * cellCount pool Winner.no Direction.noToYes MarginBand.wide
      = 2 * pool.length := by
  have h := cellCount_sum pool
  omega

/-! ## Pool well-formedness: unique itemIds -/

/-- Number of pool items carrying a given `itemId`. -/
def itemIdCount (pool : List PoolItem) (i : Nat) : Nat :=
  (pool.filter (fun p => decide (p.itemId = i))).length

/-- Well-formed pool: item identifiers are pairwise distinct. -/
def poolWellFormed (pool : List PoolItem) : Prop :=
  (pool.map (·.itemId)).Nodup

/-- **Uniqueness as a counting bound**: in a well-formed pool, at most
one item carries any given identifier. -/
theorem itemIdCount_le_one (pool : List PoolItem) (h : poolWellFormed pool) (i : Nat) :
    itemIdCount pool i ≤ 1 := by
  unfold itemIdCount
  induction pool with
  | nil => simp
  | cons a rest ih =>
      unfold poolWellFormed at h
      rw [List.map_cons, List.nodup_cons] at h
      by_cases hba : a.itemId = i
      · have hpos : decide (a.itemId = i) = true := by simp [hba]
        have h0 : (rest.filter (fun p : PoolItem => decide (p.itemId = i))).length = 0 := by
          rw [List.length_eq_zero_iff, List.filter_eq_nil_iff]
          intro p hp hc
          have hpi : p.itemId = i := by simpa using hc
          have hai : a.itemId = i := hba
          exact h.1 (List.mem_map.mpr ⟨p, hp, by simp [hpi, hai]⟩)
        rw [List.filter_cons_of_pos (p := fun p : PoolItem => decide (p.itemId = i)) hpos,
            List.length_cons, h0]
        omega
      · have hneg : decide (a.itemId = i) = false := by simp [hba]
        rw [List.filter_cons_of_neg (p := fun p : PoolItem => decide (p.itemId = i)) (by simp [hneg])]
        exact ih h.2

/-! ## Leakage gate (perturbedGT distribution) -/

/-- The leakage gate on raw class counts: `20·max(nY,nN) < 11·(nY+nN)`.
Equivalent to both classes staying strictly below 11/20 of the total,
i.e. the best constant perturbed-class predictor below 0.55. -/
def leakageGate (nY nN : Nat) : Bool :=
  decide (20 * max nY nN < 11 * (nY + nN))

/-- The gate decomposes into the two one-sided bounds. -/
theorem leakageGate_parts (nY nN : Nat) :
    leakageGate nY nN = true
      ↔ (20 * nY < 11 * (nY + nN) ∧ 20 * nN < 11 * (nY + nN)) := by
  unfold leakageGate
  simp only [decide_eq_true_iff]
  by_cases h : nY ≤ nN
  · rw [Nat.max_eq_right h]
    constructor
    · intro hc; exact ⟨by omega, hc⟩
    · intro hc; exact hc.2
  · rw [Nat.max_eq_left (by omega : nN ≤ nY)]
    constructor
    · intro hc; exact ⟨hc, by omega⟩
    · intro hc; exact hc.1

/-- The pool-level gate: the leakage condition on the pool's
perturbed-GT distribution (`nY = gtCount yes`, `nN = gtCount no`). -/
def poolLeakageGate (pool : List PoolItem) : Bool :=
  leakageGate (gtCount pool Winner.yes) (gtCount pool Winner.no)

/-! ## Minimum cell occupancy (independent of the gate) -/

/-- Every cell of the partition holds at least `minS` items. A separate
condition from the leakage gate: the gate can accept a degenerate pool
that the minimum-cell condition rejects. -/
def minCellSize (pool : List PoolItem) (minS : Nat) : Prop :=
  ∀ (w : Winner) (d : Direction) (b : MarginBand), minS ≤ cellCount pool w d b

end Sejmbench
