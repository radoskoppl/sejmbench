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
        rw [h1, h2, ]
        simp only [List.length_cons]
        omega
      · have h3 : (List.filter f (a :: rest)).length
            = (List.filter f rest).length := by
          rw [List.filter_cons_of_neg h]
        have h4 : (!(f a)) = true := by simp [h]
        have h5 : (List.filter (fun x => !(f x)) (a :: rest)).length
            = (List.filter (fun x => !(f x)) rest).length + 1 := by
          rw [List.filter_cons_of_pos (p := fun x => !(f x)) h4, List.length_cons]
        rw [h3, h5, ]
        simp only [List.length_cons]
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
        rw [e1, e2, e3, ]
        simp only [List.length_cons]
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
          rw [e1, e2, e3, ]
          simp only [List.length_cons]
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
          rw [e1, e2, e3, ]
          simp only [List.length_cons]
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

/-- Direction is a function of the original GT. -/
theorem direction_of_originalGT (r : ModelResponsePair) :
    r.originalGT = match r.direction with
      | Direction.yesToNo => Winner.yes
      | Direction.noToYes => Winner.no := by
  cases hr : r.originalGT with
  | yes => simp [ModelResponsePair.direction, hr]
  | no => simp [ModelResponsePair.direction, hr]

/-- The perturbed GT is determined by the direction: the confirmed
reversal guarantees the two GTs differ (`ReversalPair.hrev`), and a
`Winner` has exactly two values. -/
theorem perturbedGT_of_direction (r : ModelResponsePair) :
    (r.direction = Direction.yesToNo → r.perturbedGT = Winner.no)
      ∧ (r.direction = Direction.noToYes → r.perturbedGT = Winner.yes) := by
  constructor
  · intro hd
    cases hr : r.originalGT with
    | yes =>
        have hne : sumOrigGT r.pair.candidate ≠ sumPertGT r.pair.candidate := r.pair.hrev
        have ho : sumOrigGT r.pair.candidate = Winner.yes := hr
        rw [ho] at hne
        cases hp : r.perturbedGT with
        | no => rfl
        | yes => exact absurd hp.symm hne
    | no =>
        have hdir : r.direction = Direction.noToYes := by
          simp [ModelResponsePair.direction, hr]
        rw [hdir] at hd
        exact absurd hd (by simp)
  · intro hd
    cases hr : r.originalGT with
    | no =>
        have hne : sumOrigGT r.pair.candidate ≠ sumPertGT r.pair.candidate := r.pair.hrev
        have ho : sumOrigGT r.pair.candidate = Winner.no := hr
        rw [ho] at hne
        cases hp : r.perturbedGT with
        | yes => rfl
        | no => exact absurd hp.symm hne
    | yes =>
        have hdir : r.direction = Direction.yesToNo := by
          simp [ModelResponsePair.direction, hr]
        rw [hdir] at hd
        exact absurd hd (by simp)

/-- **Structurally empty cells**: direction and the perturbed GT are in
bijection on `ModelResponsePair` (both derived from the confirmed
reversal, whose GTs differ), so the 6 cells pairing `yes` with
`yesToNo` or `no` with `noToYes` are empty for EVERY pool. -/
theorem cellCount_zero (pool : List PoolItem) (b : MarginBand) :
    cellCount pool Winner.yes Direction.yesToNo b = 0
      ∧ cellCount pool Winner.no Direction.noToYes b = 0 := by
  constructor
  · unfold cellCount
    rw [List.length_eq_zero_iff, List.filter_eq_nil_iff]
    intro p hp
    rcases List.mem_filter.mp hp with ⟨h1, h2⟩
    rcases List.mem_filter.mp h1 with ⟨_, hgt⟩
    cases hd : p.pair.direction with
    | yesToNo =>
        apply absurd hgt
        intro hc
        have hpn : p.pair.perturbedGT = Winner.no :=
          ((perturbedGT_of_direction p.pair).1 hd)
        rw [hpn] at hc
        simp [sameGT] at hc
    | noToYes => simp [sameDir, hd] at h2
  · unfold cellCount
    rw [List.length_eq_zero_iff, List.filter_eq_nil_iff]
    intro p hp
    rcases List.mem_filter.mp hp with ⟨h1, h2⟩
    rcases List.mem_filter.mp h1 with ⟨_, hgt⟩
    cases hd : p.pair.direction with
    | noToYes =>
        apply absurd hgt
        intro hc
        have hpn : p.pair.perturbedGT = Winner.yes :=
          ((perturbedGT_of_direction p.pair).2 hd)
        rw [hpn] at hc
        simp [sameGT] at hc
    | yesToNo => simp [sameDir, hd] at h2

/-- **The 12-cell partition is exhaustive**: the twelve cell counts sum
to the pool size. Composition of `gt_cell_sum` × `dir_cell_sum` ×
`band_cell_sum`. (Six of the twelve are structurally empty — see
`cellCount_zero` — but the identity holds regardless.) -/
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

/-- Count of items with perturbed GT `w` within original-margin band `b`. -/
def gtBandCount (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
    ((pool.filter (fun p => sameBand p.band b)).filter
      (fun p => sameGT p.pair.perturbedGT w)).length

/-- Count of items in original-margin band `b`. -/
def bandCount (pool : List PoolItem) (b : MarginBand) : Nat :=
    (pool.filter (fun p => sameBand p.band b)).length

/-- Within a band, the two perturbed-GT classes split the band count. -/
theorem gtBandCount_split (pool : List PoolItem) (b : MarginBand) :
    gtBandCount pool Winner.yes b + gtBandCount pool Winner.no b
      = bandCount pool b := by
  unfold gtBandCount bandCount
  have h := filter_complement
    (fun p : PoolItem => sameGT p.pair.perturbedGT Winner.yes)
    (pool.filter (fun p => sameBand p.band b))
  have hEq : (pool.filter (fun p => sameBand p.band b)).filter
        (fun x => !(sameGT x.pair.perturbedGT Winner.yes))
      = (pool.filter (fun p => sameBand p.band b)).filter
        (fun p => sameGT p.pair.perturbedGT Winner.no) := by
    refine List.filter_congr (fun x _ => ?_)
    exact sameGT_no_compl x.pair.perturbedGT
  rw [hEq] at h
  omega

/-- Per-band leakage check: within each original-margin band, the
perturbed-GT distribution must also satisfy the gate. Diagnostic
refinement of `poolLeakageGate`, which controls only the global
balance (a pool of `narrow → YES` + `wide → NO` passes the global
check while leaking through band composition). -/
def bandLeakageGate (pool : List PoolItem) : Bool :=
  leakageGate (gtBandCount pool Winner.yes MarginBand.narrow)
      (gtBandCount pool Winner.no MarginBand.narrow)
    && leakageGate (gtBandCount pool Winner.yes MarginBand.close)
      (gtBandCount pool Winner.no MarginBand.close)
    && leakageGate (gtBandCount pool Winner.yes MarginBand.wide)
      (gtBandCount pool Winner.no MarginBand.wide)

/-- **Minimum cell occupancy over the achievable cells.** Direction and
the perturbed GT are in bijection on `ModelResponsePair`
(`perturbedGT_of_direction`), so only the 6 cells
`(w, directionOf w, b)` can be non-empty; quantifying over all 12
would make the predicate unsatisfiable for `minS ≥ 1`. -/
def minCellSize (pool : List PoolItem) (minS : Nat) : Prop :=
  ∀ (w : Winner) (b : MarginBand),
    minS ≤ cellCount pool w
      (match w with | .no => Direction.yesToNo | .yes => Direction.noToYes) b

/-- **The 6-cell partition is exhaustive**: the six achievable cell
counts sum to the pool size. From the 12-cell identity and the
structural zeros of `cellCount_zero`. -/
theorem cellCount6_sum (pool : List PoolItem) :
    cellCount pool Winner.no Direction.yesToNo MarginBand.narrow
      + cellCount pool Winner.no Direction.yesToNo MarginBand.close
      + cellCount pool Winner.no Direction.yesToNo MarginBand.wide
      + cellCount pool Winner.yes Direction.noToYes MarginBand.narrow
      + cellCount pool Winner.yes Direction.noToYes MarginBand.close
      + cellCount pool Winner.yes Direction.noToYes MarginBand.wide
      = pool.length := by
  have h12 := cellCount_sum pool
  have hz1 := (cellCount_zero pool MarginBand.narrow).1
  have hz2 := (cellCount_zero pool MarginBand.narrow).2
  have hz3 := (cellCount_zero pool MarginBand.close).1
  have hz4 := (cellCount_zero pool MarginBand.close).2
  have hz5 := (cellCount_zero pool MarginBand.wide).1
  have hz6 := (cellCount_zero pool MarginBand.wide).2
  omega


open ModelAnswer

/-! ## The #22 four-way contingency table

The mandatory 4-way contingency: original GT × perturbed GT × original
answer × perturbed answer. Because the pair is a confirmed reversal,
`(originalGT, perturbedGT)` is encoded by `direction` (bijection proved
in `direction_of_originalGT` / `perturbedGT_of_direction`), so the
table has 2 × 5 × 5 = 50 cells indexed by
`(direction, originalAnswer, perturbedAnswer)`. -/

/-- Answer predicate at the pool-item level: original answer is `c`. -/
def poolOrig (c : ModelAnswer) (p : PoolItem) : Bool :=
  sameAnswer p.pair.originalAnswer c

/-- Answer predicate at the pool-item level: perturbed answer is `c`. -/
def poolPert (c : ModelAnswer) (p : PoolItem) : Bool :=
  sameAnswer p.pair.perturbedAnswer c

/-- Count of pool items with direction `d`. -/
def directionCount (pool : List PoolItem) (d : Direction) : Nat :=
  (pool.filter (fun p => sameDir p.pair.direction d)).length

/-- Count of items in direction `d` whose original answer is `a`. -/
def origAnswerCount (pool : List PoolItem) (d : Direction) (a : ModelAnswer) : Nat :=
  ((pool.filter (fun p => sameDir p.pair.direction d)).filter (poolOrig a)).length

/-- Count of items in the `(d, a, b)` contingency cell. -/
def contingencyCount (pool : List PoolItem) (d : Direction) (a b : ModelAnswer) : Nat :=
  (((pool.filter (fun p => sameDir p.pair.direction d)).filter (poolOrig a)).filter
      (poolPert b)).length

/-- If `!(a && b) = true` and `a = true`, then `b = false`. -/
theorem and_false_of_left {a b : Bool} (h : (!(a && b)) = true) (ha : a = true) :
    b = false := by
  cases hb : b with
  | false => rfl
  | true => rw [ha, hb] at h; simp at h

/-- If `!(a && b) = true` and `b = true`, then `a = false`. -/
theorem and_false_of_right {a b : Bool} (h : (!(a && b)) = true) (hb : b = true) :
    a = false := by
  cases ha : a with
  | false => rfl
  | true => rw [ha, hb] at h; simp at h

/-- Five pointwise-disjoint, exhaustive predicates split any list. -/
theorem filter_split5 {α : Type} (f g h k j : α → Bool)
    (hex : ∀ x, (f x || g x || h x || k x || j x) = true)
    (hd1 : ∀ x, (!(f x && g x)) = true) (hd2 : ∀ x, (!(f x && h x)) = true)
    (hd3 : ∀ x, (!(f x && k x)) = true) (hd4 : ∀ x, (!(f x && j x)) = true)
    (hd5 : ∀ x, (!(g x && h x)) = true) (hd6 : ∀ x, (!(g x && k x)) = true)
    (hd7 : ∀ x, (!(g x && j x)) = true) (hd8 : ∀ x, (!(h x && k x)) = true)
    (hd9 : ∀ x, (!(h x && j x)) = true) (hd10 : ∀ x, (!(k x && j x)) = true)
    (l : List α) :
    (l.filter f).length + (l.filter g).length + (l.filter h).length
      + (l.filter k).length + (l.filter j).length = l.length := by
  induction l with
  | nil => simp
  | cons a rest ih =>
      by_cases h1 : f a = true
      · have hgn : ¬(g a = true) := by simp [and_false_of_left (hd1 a) h1]
        have hhn : ¬(h a = true) := by simp [and_false_of_left (hd2 a) h1]
        have hkn : ¬(k a = true) := by simp [and_false_of_left (hd3 a) h1]
        have hjn : ¬(j a = true) := by simp [and_false_of_left (hd4 a) h1]
        rw [List.filter_cons_of_pos h1,
            List.filter_cons_of_neg (p := g) hgn,
            List.filter_cons_of_neg (p := h) hhn,
            List.filter_cons_of_neg (p := k) hkn,
            List.filter_cons_of_neg (p := j) hjn]
        simp only [List.length_cons]
        omega
      · by_cases h2 : g a = true
        · have hfn : ¬(f a = true) := by simp [and_false_of_right (hd1 a) h2]
          have hhn : ¬(h a = true) := by simp [and_false_of_left (hd5 a) h2]
          have hkn : ¬(k a = true) := by simp [and_false_of_left (hd6 a) h2]
          have hjn : ¬(j a = true) := by simp [and_false_of_left (hd7 a) h2]
          rw [List.filter_cons_of_neg h1,
              List.filter_cons_of_pos h2,
              List.filter_cons_of_neg (p := h) hhn,
              List.filter_cons_of_neg (p := k) hkn,
              List.filter_cons_of_neg (p := j) hjn]
          simp only [List.length_cons]
          omega
        · by_cases h3 : h a = true
          · have hfn : ¬(f a = true) := by simp [and_false_of_right (hd2 a) h3]
            have hgn : ¬(g a = true) := by simp [and_false_of_right (hd5 a) h3]
            have hkn : ¬(k a = true) := by simp [and_false_of_left (hd8 a) h3]
            have hjn : ¬(j a = true) := by simp [and_false_of_left (hd9 a) h3]
            rw [List.filter_cons_of_neg h1,
                List.filter_cons_of_neg h2,
                List.filter_cons_of_pos h3,
                List.filter_cons_of_neg (p := k) hkn,
                List.filter_cons_of_neg (p := j) hjn]
            simp only [List.length_cons]
            omega
          · by_cases h4 : k a = true
            · have hgn : ¬(g a = true) := by simp [and_false_of_right (hd6 a) h4]
              have hhn : ¬(h a = true) := by simp [and_false_of_right (hd8 a) h4]
              have hjn : ¬(j a = true) := by simp [and_false_of_left (hd10 a) h4]
              rw [List.filter_cons_of_neg h1,
                  List.filter_cons_of_neg h2,
                  List.filter_cons_of_neg h3,
                  List.filter_cons_of_pos h4,
                  List.filter_cons_of_neg (p := j) hjn]
              simp only [List.length_cons]
              omega
            · have e1 : f a = false := (Bool.not_eq_true (f a)).mp h1
              have e2 : g a = false := (Bool.not_eq_true (g a)).mp h2
              have e3 : h a = false := (Bool.not_eq_true (h a)).mp h3
              have e4 : k a = false := (Bool.not_eq_true (k a)).mp h4
              have hjt : j a = true := by
                cases hj : j a with
                | true => rfl
                | false =>
                  have h := hex a
                  rw [e1, e2, e3, e4, hj] at h
                  simp at h
              rw [List.filter_cons_of_neg h1,
                  List.filter_cons_of_neg h2,
                  List.filter_cons_of_neg h3,
                  List.filter_cons_of_neg h4,
                  List.filter_cons_of_pos hjt]
              simp only [List.length_cons]
              omega

/-- The eleven pointwise facts for the `poolOrig` family. -/
theorem poolOrig_facts (x : PoolItem) :
    (poolOrig .yes x || poolOrig .no x || poolOrig .abstain x || poolOrig .refusal x || poolOrig .unresolvable x) = true
      ∧ (!(poolOrig .yes x && poolOrig .no x)) = true
      ∧ (!(poolOrig .yes x && poolOrig .abstain x)) = true
      ∧ (!(poolOrig .yes x && poolOrig .refusal x)) = true
      ∧ (!(poolOrig .yes x && poolOrig .unresolvable x)) = true
      ∧ (!(poolOrig .no x && poolOrig .abstain x)) = true
      ∧ (!(poolOrig .no x && poolOrig .refusal x)) = true
      ∧ (!(poolOrig .no x && poolOrig .unresolvable x)) = true
      ∧ (!(poolOrig .abstain x && poolOrig .refusal x)) = true
      ∧ (!(poolOrig .abstain x && poolOrig .unresolvable x)) = true
      ∧ (!(poolOrig .refusal x && poolOrig .unresolvable x)) = true
    := by
  cases h : x.pair.originalAnswer with
  | yes => simp [poolOrig, sameAnswer, h]
  | no => simp [poolOrig, sameAnswer, h]
  | abstain => simp [poolOrig, sameAnswer, h]
  | refusal => simp [poolOrig, sameAnswer, h]
  | unresolvable => simp [poolOrig, sameAnswer, h]

/-- The eleven pointwise facts for the `poolPert` family. -/
theorem poolPert_facts (x : PoolItem) :
    (poolPert .yes x || poolPert .no x || poolPert .abstain x || poolPert .refusal x || poolPert .unresolvable x) = true
      ∧ (!(poolPert .yes x && poolPert .no x)) = true
      ∧ (!(poolPert .yes x && poolPert .abstain x)) = true
      ∧ (!(poolPert .yes x && poolPert .refusal x)) = true
      ∧ (!(poolPert .yes x && poolPert .unresolvable x)) = true
      ∧ (!(poolPert .no x && poolPert .abstain x)) = true
      ∧ (!(poolPert .no x && poolPert .refusal x)) = true
      ∧ (!(poolPert .no x && poolPert .unresolvable x)) = true
      ∧ (!(poolPert .abstain x && poolPert .refusal x)) = true
      ∧ (!(poolPert .abstain x && poolPert .unresolvable x)) = true
      ∧ (!(poolPert .refusal x && poolPert .unresolvable x)) = true
    := by
  cases h : x.pair.perturbedAnswer with
  | yes => simp [poolPert, sameAnswer, h]
  | no => simp [poolPert, sameAnswer, h]
  | abstain => simp [poolPert, sameAnswer, h]
  | refusal => simp [poolPert, sameAnswer, h]
  | unresolvable => simp [poolPert, sameAnswer, h]

/-- Filter predicates commute. -/
theorem filter_filter_comm {α : Type} (P Q : α → Bool) (l : List α) :
    (l.filter Q).filter P = (l.filter P).filter Q := by
  rw [List.filter_filter, List.filter_filter]
  refine List.filter_congr (fun x _ => ?_)
  simp [Bool.and_comm]

/-- **The five poolOrig rows partition the pool.** -/
theorem fiveWay_pool_orig (pool : List PoolItem) :
    (pool.filter (poolOrig .yes)).length + (pool.filter (poolOrig .no)).length + (pool.filter (poolOrig .abstain)).length + (pool.filter (poolOrig .refusal)).length + (pool.filter (poolOrig .unresolvable)).length = pool.length := by
  refine filter_split5 (poolOrig .yes) (poolOrig .no) (poolOrig .abstain) (poolOrig .refusal) (poolOrig .unresolvable)
    (hex := fun x => (poolOrig_facts x).1)
    (hd1 := fun x => (poolOrig_facts x).2.1)
    (hd2 := fun x => (poolOrig_facts x).2.2.1)
    (hd3 := fun x => (poolOrig_facts x).2.2.2.1)
    (hd4 := fun x => (poolOrig_facts x).2.2.2.2.1)
    (hd5 := fun x => (poolOrig_facts x).2.2.2.2.2.1)
    (hd6 := fun x => (poolOrig_facts x).2.2.2.2.2.2.1)
    (hd7 := fun x => (poolOrig_facts x).2.2.2.2.2.2.2.1)
    (hd8 := fun x => (poolOrig_facts x).2.2.2.2.2.2.2.2.1)
    (hd9 := fun x => (poolOrig_facts x).2.2.2.2.2.2.2.2.2.1)
    (hd10 := fun x => (poolOrig_facts x).2.2.2.2.2.2.2.2.2.2)
        pool


/-- **The five poolPert rows partition the pool.** -/
theorem fiveWay_pool_pert (pool : List PoolItem) :
    (pool.filter (poolPert .yes)).length + (pool.filter (poolPert .no)).length + (pool.filter (poolPert .abstain)).length + (pool.filter (poolPert .refusal)).length + (pool.filter (poolPert .unresolvable)).length = pool.length := by
  refine filter_split5 (poolPert .yes) (poolPert .no) (poolPert .abstain) (poolPert .refusal) (poolPert .unresolvable)
    (hex := fun x => (poolPert_facts x).1)
    (hd1 := fun x => (poolPert_facts x).2.1)
    (hd2 := fun x => (poolPert_facts x).2.2.1)
    (hd3 := fun x => (poolPert_facts x).2.2.2.1)
    (hd4 := fun x => (poolPert_facts x).2.2.2.2.1)
    (hd5 := fun x => (poolPert_facts x).2.2.2.2.2.1)
    (hd6 := fun x => (poolPert_facts x).2.2.2.2.2.2.1)
    (hd7 := fun x => (poolPert_facts x).2.2.2.2.2.2.2.1)
    (hd8 := fun x => (poolPert_facts x).2.2.2.2.2.2.2.2.1)
    (hd9 := fun x => (poolPert_facts x).2.2.2.2.2.2.2.2.2.1)
    (hd10 := fun x => (poolPert_facts x).2.2.2.2.2.2.2.2.2.2)
        pool


/-- **Row sum of the contingency table**: for fixed direction and
original answer, the five perturbed-answer cells exhaust the slice. -/
theorem contingency_row_sum (pool : List PoolItem) (d : Direction) (a : ModelAnswer) :
    contingencyCount pool d a .yes + contingencyCount pool d a .no
      + contingencyCount pool d a .abstain + contingencyCount pool d a .refusal
      + contingencyCount pool d a .unresolvable
      = origAnswerCount pool d a := by
  refine filter_split5 (poolPert .yes) (poolPert .no) (poolPert .abstain)
    (poolPert .refusal) (poolPert .unresolvable) ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    ((pool.filter (fun p => sameDir p.pair.direction d)).filter (poolOrig a))
  all_goals
    intro x
    cases h : x.pair.perturbedAnswer with
    | yes => simp [poolPert, sameAnswer, h]
    | no => simp [poolPert, sameAnswer, h]
    | abstain => simp [poolPert, sameAnswer, h]
    | refusal => simp [poolPert, sameAnswer, h]
    | unresolvable => simp [poolPert, sameAnswer, h]

/-- **Slice sum**: for fixed direction, the five original-answer rows
exhaust the direction count. -/
theorem contingency_slice_sum (pool : List PoolItem) (d : Direction) :
    origAnswerCount pool d .yes + origAnswerCount pool d .no
      + origAnswerCount pool d .abstain + origAnswerCount pool d .refusal
      + origAnswerCount pool d .unresolvable
      = directionCount pool d := by
  refine filter_split5 (poolOrig .yes) (poolOrig .no) (poolOrig .abstain)
    (poolOrig .refusal) (poolOrig .unresolvable) ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    (pool.filter (fun p => sameDir p.pair.direction d))
  all_goals
    intro x
    cases h : x.pair.originalAnswer with
    | yes => simp [poolOrig, sameAnswer, h]
    | no => simp [poolOrig, sameAnswer, h]
    | abstain => simp [poolOrig, sameAnswer, h]
    | refusal => simp [poolOrig, sameAnswer, h]
    | unresolvable => simp [poolOrig, sameAnswer, h]

/-- **Total**: the two direction slices exhaust the pool. -/
theorem contingency_total_sum (pool : List PoolItem) :
    directionCount pool Direction.yesToNo + directionCount pool Direction.noToYes
      = pool.length := by
  unfold directionCount
  have h := filter_complement
    (fun p : PoolItem => sameDir p.pair.direction Direction.yesToNo) pool
  have hEq : (pool.filter (fun x => !(sameDir x.pair.direction Direction.yesToNo)))
      = pool.filter (fun p => sameDir p.pair.direction Direction.noToYes) := by
    refine List.filter_congr (fun x _ => ?_)
    exact sameDir_no_compl x.pair.direction
  rw [hEq] at h
  omega

/-- **The full 50-cell contingency table sums to the pool length**: all
`2 × 5 × 5` cells `(direction, originalAnswer, perturbedAnswer)`
partition the pool — the ten row sums collapse to the two slice sums
and the two slices are the pool (`contingency_total_sum`). -/
theorem contingency_all_sum (pool : List PoolItem) :
    -- the `yesToNo` slice: five original-answer rows …
    ((contingencyCount pool Direction.yesToNo ModelAnswer.yes ModelAnswer.yes
        + contingencyCount pool Direction.yesToNo ModelAnswer.yes ModelAnswer.no
        + contingencyCount pool Direction.yesToNo ModelAnswer.yes ModelAnswer.abstain
        + contingencyCount pool Direction.yesToNo ModelAnswer.yes ModelAnswer.refusal
        + contingencyCount pool Direction.yesToNo ModelAnswer.yes ModelAnswer.unresolvable)
      + (contingencyCount pool Direction.yesToNo ModelAnswer.no ModelAnswer.yes
        + contingencyCount pool Direction.yesToNo ModelAnswer.no ModelAnswer.no
        + contingencyCount pool Direction.yesToNo ModelAnswer.no ModelAnswer.abstain
        + contingencyCount pool Direction.yesToNo ModelAnswer.no ModelAnswer.refusal
        + contingencyCount pool Direction.yesToNo ModelAnswer.no ModelAnswer.unresolvable)
      + (contingencyCount pool Direction.yesToNo ModelAnswer.abstain ModelAnswer.yes
        + contingencyCount pool Direction.yesToNo ModelAnswer.abstain ModelAnswer.no
        + contingencyCount pool Direction.yesToNo ModelAnswer.abstain ModelAnswer.abstain
        + contingencyCount pool Direction.yesToNo ModelAnswer.abstain ModelAnswer.refusal
        + contingencyCount pool Direction.yesToNo ModelAnswer.abstain ModelAnswer.unresolvable)
      + (contingencyCount pool Direction.yesToNo ModelAnswer.refusal ModelAnswer.yes
        + contingencyCount pool Direction.yesToNo ModelAnswer.refusal ModelAnswer.no
        + contingencyCount pool Direction.yesToNo ModelAnswer.refusal ModelAnswer.abstain
        + contingencyCount pool Direction.yesToNo ModelAnswer.refusal ModelAnswer.refusal
        + contingencyCount pool Direction.yesToNo ModelAnswer.refusal ModelAnswer.unresolvable)
      + (contingencyCount pool Direction.yesToNo ModelAnswer.unresolvable ModelAnswer.yes
        + contingencyCount pool Direction.yesToNo ModelAnswer.unresolvable ModelAnswer.no
        + contingencyCount pool Direction.yesToNo ModelAnswer.unresolvable ModelAnswer.abstain
        + contingencyCount pool Direction.yesToNo ModelAnswer.unresolvable ModelAnswer.refusal
        + contingencyCount pool Direction.yesToNo ModelAnswer.unresolvable ModelAnswer.unresolvable))
    -- the `noToYes` slice: five original-answer rows …
      + ((contingencyCount pool Direction.noToYes ModelAnswer.yes ModelAnswer.yes
        + contingencyCount pool Direction.noToYes ModelAnswer.yes ModelAnswer.no
        + contingencyCount pool Direction.noToYes ModelAnswer.yes ModelAnswer.abstain
        + contingencyCount pool Direction.noToYes ModelAnswer.yes ModelAnswer.refusal
        + contingencyCount pool Direction.noToYes ModelAnswer.yes ModelAnswer.unresolvable)
      + (contingencyCount pool Direction.noToYes ModelAnswer.no ModelAnswer.yes
        + contingencyCount pool Direction.noToYes ModelAnswer.no ModelAnswer.no
        + contingencyCount pool Direction.noToYes ModelAnswer.no ModelAnswer.abstain
        + contingencyCount pool Direction.noToYes ModelAnswer.no ModelAnswer.refusal
        + contingencyCount pool Direction.noToYes ModelAnswer.no ModelAnswer.unresolvable)
      + (contingencyCount pool Direction.noToYes ModelAnswer.abstain ModelAnswer.yes
        + contingencyCount pool Direction.noToYes ModelAnswer.abstain ModelAnswer.no
        + contingencyCount pool Direction.noToYes ModelAnswer.abstain ModelAnswer.abstain
        + contingencyCount pool Direction.noToYes ModelAnswer.abstain ModelAnswer.refusal
        + contingencyCount pool Direction.noToYes ModelAnswer.abstain ModelAnswer.unresolvable)
      + (contingencyCount pool Direction.noToYes ModelAnswer.refusal ModelAnswer.yes
        + contingencyCount pool Direction.noToYes ModelAnswer.refusal ModelAnswer.no
        + contingencyCount pool Direction.noToYes ModelAnswer.refusal ModelAnswer.abstain
        + contingencyCount pool Direction.noToYes ModelAnswer.refusal ModelAnswer.refusal
        + contingencyCount pool Direction.noToYes ModelAnswer.refusal ModelAnswer.unresolvable)
      + (contingencyCount pool Direction.noToYes ModelAnswer.unresolvable ModelAnswer.yes
        + contingencyCount pool Direction.noToYes ModelAnswer.unresolvable ModelAnswer.no
        + contingencyCount pool Direction.noToYes ModelAnswer.unresolvable ModelAnswer.abstain
        + contingencyCount pool Direction.noToYes ModelAnswer.unresolvable ModelAnswer.refusal
        + contingencyCount pool Direction.noToYes ModelAnswer.unresolvable ModelAnswer.unresolvable))
      = pool.length := by
  rw [contingency_row_sum pool Direction.yesToNo ModelAnswer.yes,
      contingency_row_sum pool Direction.yesToNo ModelAnswer.no,
      contingency_row_sum pool Direction.yesToNo ModelAnswer.abstain,
      contingency_row_sum pool Direction.yesToNo ModelAnswer.refusal,
      contingency_row_sum pool Direction.yesToNo ModelAnswer.unresolvable,
      contingency_row_sum pool Direction.noToYes ModelAnswer.yes,
      contingency_row_sum pool Direction.noToYes ModelAnswer.no,
      contingency_row_sum pool Direction.noToYes ModelAnswer.abstain,
      contingency_row_sum pool Direction.noToYes ModelAnswer.refusal,
      contingency_row_sum pool Direction.noToYes ModelAnswer.unresolvable,
      contingency_slice_sum pool Direction.yesToNo,
      contingency_slice_sum pool Direction.noToYes]
  exact contingency_total_sum pool

/-! ## Counters as directional decompositions (aggregation layer) -/

/-- Is the pair in the sticky mode: correct on the original, then the
SAME answer repeated after the perturbation? -/
def ModelResponsePair.isSticky (r : ModelResponsePair) : Bool :=
  r.originalCorrect && sameAnswer r.perturbedAnswer r.originalAnswer

/-- **Directional decomposition of the sticky count.** -/
theorem stickyNum_cells (pool : List PoolItem) :
    (List.filter (fun p => sameDir p.pair.direction Direction.yesToNo)
        (List.filter (fun p => ModelResponsePair.isSticky p.pair) pool)).length
      + (List.filter (fun p => sameDir p.pair.direction Direction.noToYes)
          (List.filter (fun p => ModelResponsePair.isSticky p.pair) pool)).length
      = (List.filter (fun p => ModelResponsePair.isSticky p.pair) pool).length := by
  have h := filter_complement
    (fun p : PoolItem => sameDir p.pair.direction Direction.yesToNo)
    (List.filter (fun p => ModelResponsePair.isSticky p.pair) pool)
  have hEq : (List.filter (fun p => ModelResponsePair.isSticky p.pair) pool).filter
        (fun x => !(sameDir x.pair.direction Direction.yesToNo))
      = List.filter (fun p => sameDir p.pair.direction Direction.noToYes)
          (List.filter (fun p => ModelResponsePair.isSticky p.pair) pool) := by
    refine List.filter_congr (fun x _ => ?_)
    simp [sameDir_no_compl x.pair.direction]
  rw [hEq] at h
  exact h

/-- **Directional decomposition of the strict count.** -/
theorem strictNum_cells (pool : List PoolItem) :
    (List.filter (fun p => sameDir p.pair.direction Direction.yesToNo)
        (List.filter (fun p => p.pair.strictlyResponsive) pool)).length
      + (List.filter (fun p => sameDir p.pair.direction Direction.noToYes)
          (List.filter (fun p => p.pair.strictlyResponsive) pool)).length
      = (List.filter (fun p => p.pair.strictlyResponsive) pool).length := by
  have h := filter_complement
    (fun p : PoolItem => sameDir p.pair.direction Direction.yesToNo)
    (List.filter (fun p => p.pair.strictlyResponsive) pool)
  have hEq : (List.filter (fun p => p.pair.strictlyResponsive) pool).filter
        (fun x => !(sameDir x.pair.direction Direction.yesToNo))
      = List.filter (fun p => sameDir p.pair.direction Direction.noToYes)
          (List.filter (fun p => p.pair.strictlyResponsive) pool) := by
    refine List.filter_congr (fun x _ => ?_)
    simp [sameDir_no_compl x.pair.direction]
  rw [hEq] at h
  exact h

/-- **Directional decomposition of the incidental count.** -/
theorem incidentalNum_cells (pool : List PoolItem) :
    (List.filter (fun p => sameDir p.pair.direction Direction.yesToNo)
        (List.filter (fun p => p.pair.incidentallyCorrect) pool)).length
      + (List.filter (fun p => sameDir p.pair.direction Direction.noToYes)
          (List.filter (fun p => p.pair.incidentallyCorrect) pool)).length
      = (List.filter (fun p => p.pair.incidentallyCorrect) pool).length := by
  have h := filter_complement
    (fun p : PoolItem => sameDir p.pair.direction Direction.yesToNo)
    (List.filter (fun p => p.pair.incidentallyCorrect) pool)
  have hEq : (List.filter (fun p => p.pair.incidentallyCorrect) pool).filter
        (fun x => !(sameDir x.pair.direction Direction.yesToNo))
      = List.filter (fun p => sameDir p.pair.direction Direction.noToYes)
          (List.filter (fun p => p.pair.incidentallyCorrect) pool) := by
    refine List.filter_congr (fun x _ => ?_)
    simp [sameDir_no_compl x.pair.direction]
  rw [hEq] at h
  exact h


/-! ## The bridge: PoolItem → ResponseSet -/

/-- The response-set image of a pool: the pairs, forgetting itemIds. -/
def PoolItem.toResponseSet (pool : List PoolItem) : ResponseSet :=
  pool.map PoolItem.pair

/-- The direction slice of a pool. -/
def dirSlice (d : Direction) (pool : List PoolItem) : List PoolItem :=
  pool.filter (fun p => sameDir p.pair.direction d)

/-- Filtering after mapping to pairs = mapping the filtered pool. -/
theorem filter_map_pair (Q : ModelResponsePair → Bool) (pool : List PoolItem) :
    ((pool.map PoolItem.pair).filter Q) = (pool.filter (fun p => Q p.pair)).map PoolItem.pair := by
  induction pool with
  | nil => simp
  | cons p rest ih =>
    by_cases h : Q p.pair = true
    · simp [h, ih]
    · simp [h, ih]

/-- Pair-counter of the image = filter count of the pool. -/
theorem countPairs_map (Q : ModelResponsePair → Bool) (pool : List PoolItem) :
    countPairs (PoolItem.toResponseSet pool) Q = (pool.filter (fun p => Q p.pair)).length := by
  unfold countPairs PoolItem.toResponseSet
  rw [filter_map_pair, List.length_map]

/-- **Bridge (sticky)**. -/
theorem stickyNum_eq_responseSet (pool : List PoolItem) :
    (pool.filter (fun p => ModelResponsePair.isSticky p.pair)).length
      = ResponseSet.stickyNum (PoolItem.toResponseSet pool) :=
  (countPairs_map ModelResponsePair.isSticky pool).symm

/-- **Bridge (originalCorrect)**. -/
theorem originalCorrectNum_eq_responseSet (pool : List PoolItem) :
    (pool.filter (fun p => p.pair.originalCorrect)).length
      = ResponseSet.originalCorrectNum (PoolItem.toResponseSet pool) := by
  have h := countPairs_map ModelResponsePair.originalCorrect pool
  simp only [ResponseSet.originalCorrectNum] at h ⊢
  exact h.symm

/-- **Bridge (strict)**. -/
theorem strictNum_eq_responseSet (pool : List PoolItem) :
    (pool.filter (fun p => p.pair.strictlyResponsive)).length
      = ResponseSet.strictNum (PoolItem.toResponseSet pool) :=
  (countPairs_map ModelResponsePair.strictlyResponsive pool).symm

/-- **Bridge (incidental)**. -/
theorem incidentalNum_eq_responseSet (pool : List PoolItem) :
    (pool.filter (fun p => p.pair.incidentallyCorrect)).length
      = ResponseSet.incidentalNum (PoolItem.toResponseSet pool) :=
  (countPairs_map ModelResponsePair.incidentallyCorrect pool).symm

/-- **Directional decomposition of the sticky counter at the
ResponseSet level.** -/
theorem stickyNum_dir_decomp (pool : List PoolItem) :
    ResponseSet.stickyNum (PoolItem.toResponseSet pool)
      = ResponseSet.stickyNum (PoolItem.toResponseSet (dirSlice Direction.yesToNo pool))
        + ResponseSet.stickyNum (PoolItem.toResponseSet (dirSlice Direction.noToYes pool)) := by
  have h1 : ResponseSet.stickyNum (PoolItem.toResponseSet pool)
      = (pool.filter (fun p => ModelResponsePair.isSticky p.pair)).length :=
    (stickyNum_eq_responseSet pool).symm
  rw [h1]
  rw [← stickyNum_eq_responseSet (dirSlice Direction.yesToNo pool),
      ← stickyNum_eq_responseSet (dirSlice Direction.noToYes pool)]
  have h2 : ((dirSlice Direction.yesToNo pool).filter
        (fun p => ModelResponsePair.isSticky p.pair)).length
      = (List.filter (fun p => sameDir p.pair.direction Direction.yesToNo)
          (List.filter (fun p => ModelResponsePair.isSticky p.pair) pool)).length := by
    unfold dirSlice
    rw [filter_filter_comm]
  have h3 : ((dirSlice Direction.noToYes pool).filter
        (fun p => ModelResponsePair.isSticky p.pair)).length
      = (List.filter (fun p => sameDir p.pair.direction Direction.noToYes)
          (List.filter (fun p => ModelResponsePair.isSticky p.pair) pool)).length := by
    unfold dirSlice
    rw [filter_filter_comm]
  rw [h2, h3]
  exact (stickyNum_cells pool).symm

/-- **Directional decomposition of the strict counter at the
ResponseSet level.** -/
theorem strictNum_dir_decomp (pool : List PoolItem) :
    ResponseSet.strictNum (PoolItem.toResponseSet pool)
      = ResponseSet.strictNum (PoolItem.toResponseSet (dirSlice Direction.yesToNo pool))
        + ResponseSet.strictNum (PoolItem.toResponseSet (dirSlice Direction.noToYes pool)) := by
  have h1 : ResponseSet.strictNum (PoolItem.toResponseSet pool)
      = (pool.filter (fun p => p.pair.strictlyResponsive)).length :=
    (strictNum_eq_responseSet pool).symm
  rw [h1]
  rw [← strictNum_eq_responseSet (dirSlice Direction.yesToNo pool),
      ← strictNum_eq_responseSet (dirSlice Direction.noToYes pool)]
  have h2 : ((dirSlice Direction.yesToNo pool).filter
        (fun p => p.pair.strictlyResponsive)).length
      = (List.filter (fun p => sameDir p.pair.direction Direction.yesToNo)
          (List.filter (fun p => p.pair.strictlyResponsive) pool)).length := by
    unfold dirSlice
    rw [filter_filter_comm]
  have h3 : ((dirSlice Direction.noToYes pool).filter
        (fun p => p.pair.strictlyResponsive)).length
      = (List.filter (fun p => sameDir p.pair.direction Direction.noToYes)
          (List.filter (fun p => p.pair.strictlyResponsive) pool)).length := by
    unfold dirSlice
    rw [filter_filter_comm]
  rw [h2, h3]
  exact (strictNum_cells pool).symm

/-- **Directional decomposition of the incidental counter at the
ResponseSet level.** -/
theorem incidentalNum_dir_decomp (pool : List PoolItem) :
    ResponseSet.incidentalNum (PoolItem.toResponseSet pool)
      = ResponseSet.incidentalNum (PoolItem.toResponseSet (dirSlice Direction.yesToNo pool))
        + ResponseSet.incidentalNum (PoolItem.toResponseSet (dirSlice Direction.noToYes pool)) := by
  have h1 : ResponseSet.incidentalNum (PoolItem.toResponseSet pool)
      = (pool.filter (fun p => p.pair.incidentallyCorrect)).length :=
    (incidentalNum_eq_responseSet pool).symm
  rw [h1]
  rw [← incidentalNum_eq_responseSet (dirSlice Direction.yesToNo pool),
      ← incidentalNum_eq_responseSet (dirSlice Direction.noToYes pool)]
  have h2 : ((dirSlice Direction.yesToNo pool).filter
        (fun p => p.pair.incidentallyCorrect)).length
      = (List.filter (fun p => sameDir p.pair.direction Direction.yesToNo)
          (List.filter (fun p => p.pair.incidentallyCorrect) pool)).length := by
    unfold dirSlice
    rw [filter_filter_comm]
  have h3 : ((dirSlice Direction.noToYes pool).filter
        (fun p => p.pair.incidentallyCorrect)).length
      = (List.filter (fun p => sameDir p.pair.direction Direction.noToYes)
          (List.filter (fun p => p.pair.incidentallyCorrect) pool)).length := by
    unfold dirSlice
    rw [filter_filter_comm]
  rw [h2, h3]
  exact (incidentalNum_cells pool).symm

/-! ## Cells as item lists (the 6 achievable cells) -/

/-- The direction corresponding to a perturbed GT (the inverse map of
`direction_of_originalGT`). -/
def directionOf (w : Winner) : Direction :=
  match w with
  | .no => Direction.yesToNo
  | .yes => Direction.noToYes

/-- Direction is determined by the perturbed GT (the inverse of
`direction_of_originalGT` under the two-value `Winner`). -/
theorem direction_eq_directionOf (r : ModelResponsePair) :
    r.direction = directionOf r.perturbedGT := by
  cases hd : r.direction with
  | yesToNo =>
      have hp : r.perturbedGT = Winner.no := (perturbedGT_of_direction r).1 hd
      rw [hp, directionOf]
  | noToYes =>
      have hp : r.perturbedGT = Winner.yes := (perturbedGT_of_direction r).2 hd
      rw [hp, directionOf]

/-- The item list of the achievable cell `(perturbedGT = w, band = b)`.
The (redundant) direction layer is kept so that the list length is
definitionally `cellCount pool w (directionOf w) b`. -/
def cellItems (pool : List PoolItem) (w : Winner) (b : MarginBand) : List PoolItem :=
  (((pool.filter (fun p => sameGT p.pair.perturbedGT w)).filter
      (fun p => sameDir p.pair.direction (directionOf w))).filter
      (fun p => sameBand p.band b))

/-- The cell item list length IS the cell count. -/
theorem cellItems_length (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    (cellItems pool w b).length = cellCount pool w (directionOf w) b := rfl

/-- Pair-level counter of a cell (the `N` scale). -/
def cellPairCount (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  (cellItems pool w b).length

/-- Answer-slot counter of a cell (the `2N` scale). -/
def cellAnswerCount (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  2 * (cellItems pool w b).length

/-- Original-answer counter within a cell. -/
def cellOrigCount (pool : List PoolItem) (w : Winner) (b : MarginBand) (a : ModelAnswer) : Nat :=
  ((cellItems pool w b).filter (poolOrig a)).length

/-- Perturbed-answer counter within a cell. -/
def cellPertCount (pool : List PoolItem) (w : Winner) (b : MarginBand) (a : ModelAnswer) : Nat :=
  ((cellItems pool w b).filter (poolPert a)).length

/-- **The six achievable cells exhaust the pool** (item-list form). -/
theorem cellItems_sum (pool : List PoolItem) :
    (cellItems pool Winner.no MarginBand.narrow).length
      + (cellItems pool Winner.no MarginBand.close).length
      + (cellItems pool Winner.no MarginBand.wide).length
      + (cellItems pool Winner.yes MarginBand.narrow).length
      + (cellItems pool Winner.yes MarginBand.close).length
      + (cellItems pool Winner.yes MarginBand.wide).length
      = pool.length := by
  rw [cellItems_length, cellItems_length, cellItems_length,
      cellItems_length, cellItems_length, cellItems_length]
  exact cellCount6_sum pool

/-- **The answer-slot counters of the six cells sum to `2N`.** -/
theorem cellAnswerCount_sum (pool : List PoolItem) :
    cellAnswerCount pool Winner.no MarginBand.narrow
      + cellAnswerCount pool Winner.no MarginBand.close
      + cellAnswerCount pool Winner.no MarginBand.wide
      + cellAnswerCount pool Winner.yes MarginBand.narrow
      + cellAnswerCount pool Winner.yes MarginBand.close
      + cellAnswerCount pool Winner.yes MarginBand.wide
      = 2 * pool.length := by
  unfold cellAnswerCount
  have h := cellItems_sum pool
  omega

/-- Within a cell, the five original answers exhaust the cell. -/
theorem cellOrig_fiveWay (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellOrigCount pool w b .yes + cellOrigCount pool w b .no
      + cellOrigCount pool w b .abstain + cellOrigCount pool w b .refusal
      + cellOrigCount pool w b .unresolvable
      = (cellItems pool w b).length :=
  fiveWay_pool_orig (cellItems pool w b)

/-- Within a cell, the five perturbed answers exhaust the cell. -/
theorem cellPert_fiveWay (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellPertCount pool w b .yes + cellPertCount pool w b .no
      + cellPertCount pool w b .abstain + cellPertCount pool w b .refusal
      + cellPertCount pool w b .unresolvable
      = (cellItems pool w b).length :=
  fiveWay_pool_pert (cellItems pool w b)

/-- **The `2N` accounting of a cell**: the original-answer and
perturbed-answer counts (each summing to the cell size over its five
values) together account for both answer slots of every item in the
cell. The two scales are kept separate — the combined view is the
4-way contingency's per-cell row. -/
theorem cellAnswerCount_eq (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellAnswerCount pool w b
      = (cellOrigCount pool w b .yes + cellOrigCount pool w b .no
          + cellOrigCount pool w b .abstain + cellOrigCount pool w b .refusal
          + cellOrigCount pool w b .unresolvable)
        + (cellPertCount pool w b .yes + cellPertCount pool w b .no
          + cellPertCount pool w b .abstain + cellPertCount pool w b .refusal
          + cellPertCount pool w b .unresolvable) := by
  rw [cellOrig_fiveWay, cellPert_fiveWay]
  unfold cellAnswerCount
  omega

/-! ## Per-cell metrics (over the cell image) -/

/-- The response-set image of a cell. -/
def cellImage (pool : List PoolItem) (w : Winner) (b : MarginBand) : ResponseSet :=
  PoolItem.toResponseSet (cellItems pool w b)

/-- **Per-cell accuracy** (both answers correct / cell pairs). -/
def cellAccuracy (pool : List PoolItem) (w : Winner) (b : MarginBand) : Option Rate :=
  ResponseSet.accuracy (cellImage pool w b)

/-- **Per-cell perturbed accuracy.** -/
def cellPerturbedAccuracy (pool : List PoolItem) (w : Winner) (b : MarginBand) : Option Rate :=
  ResponseSet.perturbedAccuracy (cellImage pool w b)

/-- **Per-cell coverage** (decisive / 2N). -/
def cellCoverage (pool : List PoolItem) (w : Winner) (b : MarginBand) : Rate :=
  ResponseSet.coverage (cellImage pool w b)

/-- **Per-cell invalid-response rates** (each / 2N). -/
def cellAbstainRate (pool : List PoolItem) (w : Winner) (b : MarginBand) : Rate :=
  ResponseSet.abstainRate (cellImage pool w b)

def cellRefusalRate (pool : List PoolItem) (w : Winner) (b : MarginBand) : Rate :=
  ResponseSet.refusalRate (cellImage pool w b)

def cellUnresolvableRate (pool : List PoolItem) (w : Winner) (b : MarginBand) : Rate :=
  ResponseSet.unresolvableRate (cellImage pool w b)

/-- **Per-cell conditional responsiveness** (denominator: originalCorrect
within the cell). -/
def cellStrictConditional (pool : List PoolItem) (w : Winner) (b : MarginBand) : Option Rate :=
  ResponseSet.strictConditional (cellImage pool w b)

/-- **Per-cell unconditional responsiveness.** -/
def cellStrictUnconditional (pool : List PoolItem) (w : Winner) (b : MarginBand) : Option Rate :=
  ResponseSet.strictUnconditional (cellImage pool w b)

/-- **Per-cell incidental rate.** -/
def cellIncidental (pool : List PoolItem) (w : Winner) (b : MarginBand) : Option Rate :=
  ResponseSet.incidental (cellImage pool w b)

/-- **Per-cell sticky counter.** -/
def cellStickyNum (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  countPairs (cellImage pool w b) ModelResponsePair.isSticky

/-! ### Range theorems for the per-cell metrics -/

/-- Per-cell coverage is a genuine frequency. -/
theorem cellCoverage_num_le_den (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    (cellCoverage pool w b).num ≤ (cellCoverage pool w b).den :=
  countAnswers_le (cellImage pool w b) ModelAnswer.decisive

/-- Per-cell abstain rate is a genuine frequency. -/
theorem cellAbstainRate_num_le_den (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    (cellAbstainRate pool w b).num ≤ (cellAbstainRate pool w b).den :=
  countAnswers_le (cellImage pool w b) ModelAnswer.isAbstain

/-- Per-cell refusal rate is a genuine frequency. -/
theorem cellRefusalRate_num_le_den (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    (cellRefusalRate pool w b).num ≤ (cellRefusalRate pool w b).den :=
  countAnswers_le (cellImage pool w b) ModelAnswer.isRefusal

/-- Per-cell unresolvable rate is a genuine frequency. -/
theorem cellUnresolvableRate_num_le_den (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    (cellUnresolvableRate pool w b).num ≤ (cellUnresolvableRate pool w b).den :=
  countAnswers_le (cellImage pool w b) ModelAnswer.isUnresolvable

/-- **Per-cell accuracy is a genuine frequency.** -/
theorem cellAccuracy_num_le_den (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    ∀ r : Rate, cellAccuracy pool w b = some r → r.num ≤ r.den := by
  intro r hr
  simp only [cellAccuracy, ResponseSet.accuracy] at hr
  by_cases hN : (cellImage pool w b).N = 0
  · rw [ite_eq_left hN] at hr
    simp at hr
  · rw [ite_eq_right hN] at hr
    injection hr with hEq
    subst hEq
    exact ResponseSet.bothCorrectNum_le (cellImage pool w b)

/-- **Per-cell perturbed accuracy is a genuine frequency.** -/
theorem cellPerturbedAccuracy_num_le_den (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    ∀ r : Rate, cellPerturbedAccuracy pool w b = some r → r.num ≤ r.den := by
  intro r hr
  simp only [cellPerturbedAccuracy, ResponseSet.perturbedAccuracy] at hr
  by_cases hN : (cellImage pool w b).N = 0
  · rw [ite_eq_left hN] at hr
    simp at hr
  · rw [ite_eq_right hN] at hr
    injection hr with hEq
    subst hEq
    exact ResponseSet.perturbedCorrectCount_le (cellImage pool w b)

/-- **Per-cell conditional responsiveness is a genuine frequency**
(its denominator is the cell's originalCorrect count, not the cell's
pair count). -/
theorem cellStrictConditional_num_le_den (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    ∀ r : Rate, cellStrictConditional pool w b = some r → r.num ≤ r.den := by
  intro r hr
  simp only [cellStrictConditional, ResponseSet.strictConditional] at hr
  by_cases hN : (cellImage pool w b).originalCorrectNum = 0
  · rw [ite_eq_left hN] at hr
    simp at hr
  · rw [ite_eq_right hN] at hr
    injection hr with hEq
    subst hEq
    exact ResponseSet.strictNum_le_originalCorrectNum (cellImage pool w b)

/-- **Per-cell unconditional responsiveness is a genuine frequency.** -/
theorem cellStrictUnconditional_num_le_den (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    ∀ r : Rate, cellStrictUnconditional pool w b = some r → r.num ≤ r.den := by
  intro r hr
  simp only [cellStrictUnconditional, ResponseSet.strictUnconditional] at hr
  by_cases hN : (cellImage pool w b).N = 0
  · rw [ite_eq_left hN] at hr
    simp at hr
  · rw [ite_eq_right hN] at hr
    injection hr with hEq
    subst hEq
    have h1 : (cellImage pool w b).strictNum ≤ (cellImage pool w b).originalCorrectNum :=
      ResponseSet.strictNum_le_originalCorrectNum (cellImage pool w b)
    have h2 : (cellImage pool w b).originalCorrectNum ≤ (cellImage pool w b).N :=
      ResponseSet.originalCorrectNum_le (cellImage pool w b)
    show (cellImage pool w b).strictNum ≤ (cellImage pool w b).N
    omega

/-- **Per-cell incidental rate is a genuine frequency.** -/
theorem cellIncidental_num_le_den (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    ∀ r : Rate, cellIncidental pool w b = some r → r.num ≤ r.den := by
  intro r hr
  simp only [cellIncidental, ResponseSet.incidental] at hr
  by_cases hN : (cellImage pool w b).N = 0
  · rw [ite_eq_left hN] at hr
    simp at hr
  · rw [ite_eq_right hN] at hr
    injection hr with hEq
    subst hEq
    exact ResponseSet.incidentalNum_le (cellImage pool w b)

/-! ## The accuracy ≡ unconditional-strict bridge -/

/-- **`cellAccuracy` and `cellStrictUnconditional` are the same
measure**: on confirmed-reversal pairs, `strictlyResponsive` is
definitionally `originalCorrect && perturbedCorrect` — the accuracy
counter. Both are `none` exactly when the cell is empty. Prevents
reporting one number as two independent estimands. -/
theorem cellAccuracy_eq_cellStrictUnconditional (pool : List PoolItem)
    (w : Winner) (b : MarginBand) :
    cellAccuracy pool w b = cellStrictUnconditional pool w b := by
  have h : ResponseSet.bothCorrectNum (cellImage pool w b)
      = ResponseSet.strictNum (cellImage pool w b) := by
    unfold ResponseSet.bothCorrectNum ResponseSet.strictNum countPairs
      ModelResponsePair.strictlyResponsive
    congr 1
  simp only [cellAccuracy, cellStrictUnconditional, ResponseSet.accuracy,
    ResponseSet.strictUnconditional, h]

/-! ## Additivity across the six achievable cells -/

/-- The perturbed-GT slice of a pool as an item list. -/
def gtItems (pool : List PoolItem) (w : Winner) : List PoolItem :=
  pool.filter (fun p => sameGT p.pair.perturbedGT w)

/-- On a perturbed-GT slice, the `directionOf w` direction predicate
is trivially true (proved from `direction_eq_directionOf`). -/
theorem dir_true_on_slice (pool : List PoolItem) (w : Winner) :
    ∀ p ∈ pool.filter (fun q : PoolItem => sameGT q.pair.perturbedGT w),
      sameDir p.pair.direction (directionOf w) = true := by
  intro p hp
  rcases List.mem_filter.mp hp with ⟨_, hgt⟩
  have hd : p.pair.direction = directionOf p.pair.perturbedGT :=
    direction_eq_directionOf p.pair
  rw [hd]
  cases hw : w with
  | yes =>
      rw [hw] at hgt
      have hsub : p.pair.perturbedGT = Winner.yes := by
        cases hp2 : p.pair.perturbedGT with
        | yes => rfl
        | no => simp [sameGT, hp2] at hgt
      rw [hsub]
      simp [directionOf, sameDir]
  | no =>
      rw [hw] at hgt
      have hsub : p.pair.perturbedGT = Winner.no := by
        cases hp2 : p.pair.perturbedGT with
        | yes => simp [sameGT, hp2] at hgt
        | no => rfl
      rw [hsub]
      simp [directionOf, sameDir]

/-- The dir filter is vacuous on the Q-filtered perturbed-GT slice
(gtItems unfolded form). -/
theorem filter_dir_vacuous (pool : List PoolItem) (w : Winner) (Q : PoolItem → Bool) :
    (List.filter Q (pool.filter (fun p : PoolItem => sameGT p.pair.perturbedGT w))).filter
        (fun p => sameDir p.pair.direction (directionOf w))
      = List.filter Q (pool.filter (fun p : PoolItem => sameGT p.pair.perturbedGT w)) := by
  refine List.filter_eq_self.mpr (fun x hx => ?_)
  rcases List.mem_filter.mp hx with ⟨hx1, _⟩
  rcases List.mem_filter.mp hx1 with ⟨hxpool, hxgt⟩
  exact dir_true_on_slice pool w x (List.mem_filter.mpr ⟨hxpool, hxgt⟩)

/-- Any pool predicate's count splits over the two perturbed-GT
classes. The pointwise core of every additivity theorem below. -/
theorem count_split_gt (Q : PoolItem → Bool) (pool : List PoolItem) :
    (List.filter Q (gtItems pool Winner.yes)).length
      + (List.filter Q (gtItems pool Winner.no)).length
      = (pool.filter Q).length := by
  have h := filter_complement
    (fun p : PoolItem => sameGT p.pair.perturbedGT Winner.yes)
    (pool.filter Q)
  have hEq : (pool.filter Q).filter
        (fun x => !(sameGT x.pair.perturbedGT Winner.yes))
      = (pool.filter Q).filter (fun p => sameGT p.pair.perturbedGT Winner.no) := by
    refine List.filter_congr (fun x _ => ?_)
    exact sameGT_no_compl x.pair.perturbedGT
  rw [hEq] at h
  simp only [gtItems]
  rw [filter_filter_comm Q (fun p : PoolItem => sameGT p.pair.perturbedGT Winner.yes) pool,
      filter_filter_comm Q (fun p : PoolItem => sameGT p.pair.perturbedGT Winner.no) pool]
  exact h

/-- The dir filter is vacuous on the Q-filtered perturbed-GT slice
(list level, dir-outer form). -/
theorem filter_dir_vacuous_list (pool : List PoolItem) (w : Winner) (Q : PoolItem → Bool) :
    (List.filter (fun p => sameDir p.pair.direction (directionOf w))
        (List.filter Q (pool.filter (fun p : PoolItem => sameGT p.pair.perturbedGT w))))
      = (List.filter Q (pool.filter (fun p : PoolItem => sameGT p.pair.perturbedGT w))) := by
  refine List.filter_eq_self.mpr (fun x hx => ?_)
  rcases List.mem_filter.mp hx with ⟨h1, _⟩
  rcases List.mem_filter.mp h1 with ⟨h0, hgt⟩
  exact dir_true_on_slice pool w x (List.mem_filter.mpr ⟨h0, hgt⟩)

/-- The dir filter is vacuous on the Q-filtered perturbed-GT slice
(dir-outer form). -/
theorem filter_dir_vacuous_outer (pool : List PoolItem) (w : Winner) (Q : PoolItem → Bool) :
    (List.filter (fun p => sameDir p.pair.direction (directionOf w))
        (List.filter Q (pool.filter (fun p : PoolItem => sameGT p.pair.perturbedGT w)))).length
      = (List.filter Q (pool.filter (fun p : PoolItem => sameGT p.pair.perturbedGT w))).length := by
  congr 1
  exact List.filter_eq_self.mpr (fun x hx => by
    rcases List.mem_filter.mp hx with ⟨h1, _⟩
    rcases List.mem_filter.mp h1 with ⟨h0, hgt⟩
    exact dir_true_on_slice pool w x (List.mem_filter.mpr ⟨h0, hgt⟩))

/-- **Additivity (N scale)**: any pair-level predicate counter over the
pool is the sum of its six per-cell counters (the band slices of each
perturbed-GT class). -/
theorem cellPairCount_add (Q : PoolItem → Bool) (pool : List PoolItem) :
    (List.filter Q (cellItems pool Winner.no MarginBand.narrow)).length
      + (List.filter Q (cellItems pool Winner.no MarginBand.close)).length
      + (List.filter Q (cellItems pool Winner.no MarginBand.wide)).length
      + (List.filter Q (cellItems pool Winner.yes MarginBand.narrow)).length
      + (List.filter Q (cellItems pool Winner.yes MarginBand.close)).length
      + (List.filter Q (cellItems pool Winner.yes MarginBand.wide)).length
      = (pool.filter Q).length := by
  have hy := filter_split3
    (fun p : PoolItem => sameBand p.band MarginBand.narrow)
    (fun p : PoolItem => sameBand p.band MarginBand.close)
    (fun p : PoolItem => sameBand p.band MarginBand.wide)
    (fun p => (sameBand_trichotomy p.band).1)
    (fun p => (sameBand_trichotomy p.band).2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.2)
    (gtItems pool Winner.yes)
  have hno := filter_split3
    (fun p : PoolItem => sameBand p.band MarginBand.narrow)
    (fun p : PoolItem => sameBand p.band MarginBand.close)
    (fun p : PoolItem => sameBand p.band MarginBand.wide)
    (fun p => (sameBand_trichotomy p.band).1)
    (fun p => (sameBand_trichotomy p.band).2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.2)
    (gtItems pool Winner.no)
  have hsum := count_split_gt Q pool
  have h1 : (List.filter Q (cellItems pool Winner.no MarginBand.narrow)).length
      = (List.filter (fun p : PoolItem => sameBand p.band MarginBand.narrow)
          (List.filter Q (gtItems pool Winner.no))).length := by
    unfold cellItems
    rw [filter_filter_comm Q (fun p : PoolItem => sameBand p.band MarginBand.narrow),
        filter_filter_comm Q (fun p : PoolItem => sameDir p.pair.direction (directionOf Winner.no)),
        filter_dir_vacuous_list pool Winner.no Q]
    rfl
  have h2 : (List.filter Q (cellItems pool Winner.no MarginBand.close)).length
      = (List.filter (fun p : PoolItem => sameBand p.band MarginBand.close)
          (List.filter Q (gtItems pool Winner.no))).length := by
    unfold cellItems
    rw [filter_filter_comm Q (fun p : PoolItem => sameBand p.band MarginBand.close),
        filter_filter_comm Q (fun p : PoolItem => sameDir p.pair.direction (directionOf Winner.no)),
        filter_dir_vacuous_list pool Winner.no Q]
    rfl
  have h3 : (List.filter Q (cellItems pool Winner.no MarginBand.wide)).length
      = (List.filter (fun p : PoolItem => sameBand p.band MarginBand.wide)
          (List.filter Q (gtItems pool Winner.no))).length := by
    unfold cellItems
    rw [filter_filter_comm Q (fun p : PoolItem => sameBand p.band MarginBand.wide),
        filter_filter_comm Q (fun p : PoolItem => sameDir p.pair.direction (directionOf Winner.no)),
        filter_dir_vacuous_list pool Winner.no Q]
    rfl
  have h4 : (List.filter Q (cellItems pool Winner.yes MarginBand.narrow)).length
      = (List.filter (fun p : PoolItem => sameBand p.band MarginBand.narrow)
          (List.filter Q (gtItems pool Winner.yes))).length := by
    unfold cellItems
    rw [filter_filter_comm Q (fun p : PoolItem => sameBand p.band MarginBand.narrow),
        filter_filter_comm Q (fun p : PoolItem => sameDir p.pair.direction (directionOf Winner.yes)),
        filter_dir_vacuous_list pool Winner.yes Q]
    rfl
  have h5 : (List.filter Q (cellItems pool Winner.yes MarginBand.close)).length
      = (List.filter (fun p : PoolItem => sameBand p.band MarginBand.close)
          (List.filter Q (gtItems pool Winner.yes))).length := by
    unfold cellItems
    rw [filter_filter_comm Q (fun p : PoolItem => sameBand p.band MarginBand.close),
        filter_filter_comm Q (fun p : PoolItem => sameDir p.pair.direction (directionOf Winner.yes)),
        filter_dir_vacuous_list pool Winner.yes Q]
    rfl
  have h6 : (List.filter Q (cellItems pool Winner.yes MarginBand.wide)).length
      = (List.filter (fun p : PoolItem => sameBand p.band MarginBand.wide)
          (List.filter Q (gtItems pool Winner.yes))).length := by
    unfold cellItems
    rw [filter_filter_comm Q (fun p : PoolItem => sameBand p.band MarginBand.wide),
        filter_filter_comm Q (fun p : PoolItem => sameDir p.pair.direction (directionOf Winner.yes)),
        filter_dir_vacuous_list pool Winner.yes Q]
    rfl
  have qy := filter_split3
    (fun p : PoolItem => sameBand p.band MarginBand.narrow)
    (fun p : PoolItem => sameBand p.band MarginBand.close)
    (fun p : PoolItem => sameBand p.band MarginBand.wide)
    (fun p => (sameBand_trichotomy p.band).1)
    (fun p => (sameBand_trichotomy p.band).2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.2)
    (List.filter Q (gtItems pool Winner.yes))
  have qno := filter_split3
    (fun p : PoolItem => sameBand p.band MarginBand.narrow)
    (fun p : PoolItem => sameBand p.band MarginBand.close)
    (fun p : PoolItem => sameBand p.band MarginBand.wide)
    (fun p => (sameBand_trichotomy p.band).1)
    (fun p => (sameBand_trichotomy p.band).2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.1)
    (fun p => (sameBand_trichotomy p.band).2.2.2)
    (List.filter Q (gtItems pool Winner.no))
  rw [h1, h2, h3, h4, h5, h6]
  omega


/-! ## Named-predicate instantiations of `cellPairCount_add` -/

/-- **Additivity of the bothCorrect counter** (accuracy numerator). -/
theorem bothCorrectNum_add (pool : List PoolItem) :
    (List.filter (fun (p : PoolItem) => p.pair.strictlyResponsive)
        (cellItems pool Winner.no MarginBand.narrow)).length
      + (List.filter (fun p => p.pair.strictlyResponsive)
          (cellItems pool Winner.no MarginBand.close)).length
      + (List.filter (fun p => p.pair.strictlyResponsive)
          (cellItems pool Winner.no MarginBand.wide)).length
      + (List.filter (fun p => p.pair.strictlyResponsive)
          (cellItems pool Winner.yes MarginBand.narrow)).length
      + (List.filter (fun p => p.pair.strictlyResponsive)
          (cellItems pool Winner.yes MarginBand.close)).length
      + (List.filter (fun p => p.pair.strictlyResponsive)
          (cellItems pool Winner.yes MarginBand.wide)).length
      = ResponseSet.strictNum (PoolItem.toResponseSet pool) := by
  have h := cellPairCount_add (fun (p : PoolItem) => p.pair.strictlyResponsive) pool
  rw [strictNum_eq_responseSet pool] at h
  simp only [ResponseSet.strictNum, countPairs] at h ⊢
  exact h

/-- **Additivity of the originalCorrect counter** (the conditional
denominator). -/
theorem originalCorrectNum_add (pool : List PoolItem) :
    (List.filter (fun (p : PoolItem) => p.pair.originalCorrect)
        (cellItems pool Winner.no MarginBand.narrow)).length
      + (List.filter (fun p => p.pair.originalCorrect)
          (cellItems pool Winner.no MarginBand.close)).length
      + (List.filter (fun p => p.pair.originalCorrect)
          (cellItems pool Winner.no MarginBand.wide)).length
      + (List.filter (fun p => p.pair.originalCorrect)
          (cellItems pool Winner.yes MarginBand.narrow)).length
      + (List.filter (fun p => p.pair.originalCorrect)
          (cellItems pool Winner.yes MarginBand.close)).length
      + (List.filter (fun p => p.pair.originalCorrect)
          (cellItems pool Winner.yes MarginBand.wide)).length
      = ResponseSet.originalCorrectNum (PoolItem.toResponseSet pool) := by
  have h := cellPairCount_add (fun (p : PoolItem) => p.pair.originalCorrect) pool
  rw [originalCorrectNum_eq_responseSet pool] at h
  simp only [ResponseSet.originalCorrectNum, countPairs]
  exact h

/-- **Additivity of the incidental counter.** -/
theorem incidentalNum_add (pool : List PoolItem) :
    (List.filter (fun (p : PoolItem) => p.pair.incidentallyCorrect)
        (cellItems pool Winner.no MarginBand.narrow)).length
      + (List.filter (fun p => p.pair.incidentallyCorrect)
          (cellItems pool Winner.no MarginBand.close)).length
      + (List.filter (fun p => p.pair.incidentallyCorrect)
          (cellItems pool Winner.no MarginBand.wide)).length
      + (List.filter (fun p => p.pair.incidentallyCorrect)
          (cellItems pool Winner.yes MarginBand.narrow)).length
      + (List.filter (fun p => p.pair.incidentallyCorrect)
          (cellItems pool Winner.yes MarginBand.close)).length
      + (List.filter (fun p => p.pair.incidentallyCorrect)
          (cellItems pool Winner.yes MarginBand.wide)).length
      = ResponseSet.incidentalNum (PoolItem.toResponseSet pool) := by
  exact (cellPairCount_add (fun (p : PoolItem) => p.pair.incidentallyCorrect) pool).trans
    (incidentalNum_eq_responseSet pool)

/-- **Additivity of the sticky counter.** -/
theorem stickyNum_add (pool : List PoolItem) :
    (List.filter (fun p => ModelResponsePair.isSticky p.pair)
        (cellItems pool Winner.no MarginBand.narrow)).length
      + (List.filter (fun p => ModelResponsePair.isSticky p.pair)
          (cellItems pool Winner.no MarginBand.close)).length
      + (List.filter (fun p => ModelResponsePair.isSticky p.pair)
          (cellItems pool Winner.no MarginBand.wide)).length
      + (List.filter (fun p => ModelResponsePair.isSticky p.pair)
          (cellItems pool Winner.yes MarginBand.narrow)).length
      + (List.filter (fun p => ModelResponsePair.isSticky p.pair)
          (cellItems pool Winner.yes MarginBand.close)).length
      + (List.filter (fun p => ModelResponsePair.isSticky p.pair)
          (cellItems pool Winner.yes MarginBand.wide)).length
      = (List.filter (fun p => ModelResponsePair.isSticky p.pair) pool).length :=
  cellPairCount_add (fun p => ModelResponsePair.isSticky p.pair) pool

/-- **Additivity of the perturbedCorrect counter** (perturbedAccuracy
numerator). -/
theorem perturbedCorrectNum_add (pool : List PoolItem) :
    (List.filter (fun (p : PoolItem) => p.pair.perturbedCorrect)
        (cellItems pool Winner.no MarginBand.narrow)).length
      + (List.filter (fun p => p.pair.perturbedCorrect)
          (cellItems pool Winner.no MarginBand.close)).length
      + (List.filter (fun p => p.pair.perturbedCorrect)
          (cellItems pool Winner.no MarginBand.wide)).length
      + (List.filter (fun p => p.pair.perturbedCorrect)
          (cellItems pool Winner.yes MarginBand.narrow)).length
      + (List.filter (fun p => p.pair.perturbedCorrect)
          (cellItems pool Winner.yes MarginBand.close)).length
      + (List.filter (fun p => p.pair.perturbedCorrect)
          (cellItems pool Winner.yes MarginBand.wide)).length
      = (List.filter (fun (p : PoolItem) => p.pair.perturbedCorrect) pool).length :=
  cellPairCount_add (fun (p : PoolItem) => p.pair.perturbedCorrect) pool

/-- **Additivity of `N`** — the always-true predicate. -/
theorem cellN_add (pool : List PoolItem) :
    (cellItems pool Winner.no MarginBand.narrow).length
      + (cellItems pool Winner.no MarginBand.close).length
      + (cellItems pool Winner.no MarginBand.wide).length
      + (cellItems pool Winner.yes MarginBand.narrow).length
      + (cellItems pool Winner.yes MarginBand.close).length
      + (cellItems pool Winner.yes MarginBand.wide).length
      = pool.length :=
  cellItems_sum pool

/-! ## 2N-scale additivity (answer slots, per experiment stage) -/

/-- **Additivity (2N scale, original-answer side)**: any original-answer
predicate counter splits additively over the six cells. -/
theorem cellOrigCount_add (g : ModelAnswer → Bool) (pool : List PoolItem) :
    (List.filter (fun p => g p.pair.originalAnswer)
        (cellItems pool Winner.no MarginBand.narrow)).length
      + (List.filter (fun p => g p.pair.originalAnswer)
          (cellItems pool Winner.no MarginBand.close)).length
      + (List.filter (fun p => g p.pair.originalAnswer)
          (cellItems pool Winner.no MarginBand.wide)).length
      + (List.filter (fun p => g p.pair.originalAnswer)
          (cellItems pool Winner.yes MarginBand.narrow)).length
      + (List.filter (fun p => g p.pair.originalAnswer)
          (cellItems pool Winner.yes MarginBand.close)).length
      + (List.filter (fun p => g p.pair.originalAnswer)
          (cellItems pool Winner.yes MarginBand.wide)).length
      = (pool.filter (fun p => g p.pair.originalAnswer)).length :=
  cellPairCount_add (fun p => g p.pair.originalAnswer) pool

/-- **Additivity (2N scale, perturbed-answer side)**. -/
theorem cellPertCount_add (g : ModelAnswer → Bool) (pool : List PoolItem) :
    (List.filter (fun p => g p.pair.perturbedAnswer)
        (cellItems pool Winner.no MarginBand.narrow)).length
      + (List.filter (fun p => g p.pair.perturbedAnswer)
          (cellItems pool Winner.no MarginBand.close)).length
      + (List.filter (fun p => g p.pair.perturbedAnswer)
          (cellItems pool Winner.no MarginBand.wide)).length
      + (List.filter (fun p => g p.pair.perturbedAnswer)
          (cellItems pool Winner.yes MarginBand.narrow)).length
      + (List.filter (fun p => g p.pair.perturbedAnswer)
          (cellItems pool Winner.yes MarginBand.close)).length
      + (List.filter (fun p => g p.pair.perturbedAnswer)
          (cellItems pool Winner.yes MarginBand.wide)).length
      = (pool.filter (fun p => g p.pair.perturbedAnswer)).length :=
  cellPairCount_add (fun p => g p.pair.perturbedAnswer) pool

/-- **The full 2N additivity**: the sum of the six cells' answer-slot
totals equals the pool's answer-slot total (both stages). -/
theorem cellAnswerCount_add (pool : List PoolItem) :
    cellAnswerCount pool Winner.no MarginBand.narrow
      + cellAnswerCount pool Winner.no MarginBand.close
      + cellAnswerCount pool Winner.no MarginBand.wide
      + cellAnswerCount pool Winner.yes MarginBand.narrow
      + cellAnswerCount pool Winner.yes MarginBand.close
      + cellAnswerCount pool Winner.yes MarginBand.wide
      = 2 * pool.length := by
  unfold cellAnswerCount
  have h := cellItems_sum pool
  omega

/-! ## Aggregation: pool-level rates as Σnᵢ/Σdᵢ of raw per-cell counters

Per the review's aggregation principle: pool-level metrics aggregate on
RAW counters and denominators (Σnᵢ/Σdᵢ), never on `Option Rate` values —
zero-denominator cells keep their information and no `none`-as-zero
coercion exists anywhere in this substrate. -/

/-- Counter-level bridge: the both-correct counter and the strict
counter are the same measure (on confirmed-reversal pairs
`strictlyResponsive` is definitionally `originalCorrect && perturbedCorrect`). -/
theorem bothCorrectNum_eq_strictNum (rs : ResponseSet) :
    ResponseSet.bothCorrectNum rs = ResponseSet.strictNum rs := by
  unfold ResponseSet.bothCorrectNum ResponseSet.strictNum countPairs
    ModelResponsePair.strictlyResponsive
  congr 1

/-- **Raw per-cell accuracy numerator** (both answers correct over the
cell image) — no `Option` wrapper; aggregation never coerces `none`. -/
def cellBothCorrectNum (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  ResponseSet.bothCorrectNum (cellImage pool w b)

/-- The per-cell accuracy numerator in the filter form consumed by
`cellPairCount_add` (via the counter-level bridge). -/
theorem cellBothCorrectNum_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellBothCorrectNum pool w b
      = (List.filter (fun p : PoolItem => p.pair.strictlyResponsive)
          (cellItems pool w b)).length := by
  unfold cellBothCorrectNum cellImage
  rw [bothCorrectNum_eq_strictNum]
  exact countPairs_map ModelResponsePair.strictlyResponsive (cellItems pool w b)

/-- Σ of the six cells' pair counts — the raw accuracy denominator
(`N` scale). -/
def cellSumN (pool : List PoolItem) : Nat :=
  (cellItems pool Winner.no MarginBand.narrow).length
    + (cellItems pool Winner.no MarginBand.close).length
    + (cellItems pool Winner.no MarginBand.wide).length
    + (cellItems pool Winner.yes MarginBand.narrow).length
    + (cellItems pool Winner.yes MarginBand.close).length
    + (cellItems pool Winner.yes MarginBand.wide).length

/-- Σ of the six cells' raw accuracy numerators. -/
def cellSumBothCorrect (pool : List PoolItem) : Nat :=
  cellBothCorrectNum pool Winner.no MarginBand.narrow
    + cellBothCorrectNum pool Winner.no MarginBand.close
    + cellBothCorrectNum pool Winner.no MarginBand.wide
    + cellBothCorrectNum pool Winner.yes MarginBand.narrow
    + cellBothCorrectNum pool Winner.yes MarginBand.close
    + cellBothCorrectNum pool Winner.yes MarginBand.wide

theorem cellSumN_add (pool : List PoolItem) :
    cellSumN pool = pool.length :=
  cellN_add pool

theorem cellSumBothCorrect_add (pool : List PoolItem) :
    cellSumBothCorrect pool = ResponseSet.strictNum (PoolItem.toResponseSet pool) := by
  unfold cellSumBothCorrect
  rw [cellBothCorrectNum_filter, cellBothCorrectNum_filter, cellBothCorrectNum_filter,
      cellBothCorrectNum_filter, cellBothCorrectNum_filter, cellBothCorrectNum_filter]
  exact (cellPairCount_add (fun p : PoolItem => p.pair.strictlyResponsive) pool).trans
    (strictNum_eq_responseSet pool)

/-- **The Σnᵢ/Σdᵢ aggregate of the per-cell accuracy counters**, built
on raw counters. `none` iff the pool is empty — the same undefinedness
as the pool-level metric, no coercion. -/
def accuracyAgg (pool : List PoolItem) : Option Rate :=
  if cellSumN pool = 0 then none
  else some { num := cellSumBothCorrect pool, den := cellSumN pool }

/-- **Aggregation (accuracy)**: the pool-level accuracy IS the Σnᵢ/Σdᵢ
fraction of the raw per-cell counters. -/
theorem accuracy_agg (pool : List PoolItem) :
    ResponseSet.accuracy (PoolItem.toResponseSet pool) = accuracyAgg pool := by
  unfold ResponseSet.accuracy accuracyAgg
  rw [bothCorrectNum_eq_strictNum, cellSumBothCorrect_add, cellSumN_add]
  have hN : (PoolItem.toResponseSet pool).N = pool.length := by
    simp [ResponseSet.N, PoolItem.toResponseSet]
  rw [hN]

/-- `countAnswers` of a pool's image = the two original-side and
perturbed-side filter counts (the map form consumed by
`cellOrigCount_add` / `cellPertCount_add`). -/
theorem countAnswers_map (g : ModelAnswer → Bool) (pool : List PoolItem) :
    countAnswers (PoolItem.toResponseSet pool) g
      = (pool.filter (fun p : PoolItem => g p.pair.originalAnswer)).length
        + (pool.filter (fun p : PoolItem => g p.pair.perturbedAnswer)).length := by
  unfold countAnswers PoolItem.toResponseSet
  rw [filter_map_pair, List.length_map, filter_map_pair, List.length_map]

/-- **Raw per-cell coverage numerator** (decisive answer slots in the
cell image) — no `Option` wrapper. -/
def cellCoverageNum (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  ResponseSet.coverageNum (cellImage pool w b)

/-- The per-cell coverage numerator in the two-side filter form. -/
theorem cellCoverageNum_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellCoverageNum pool w b
      = ((cellItems pool w b).filter
          (fun p : PoolItem => ModelAnswer.decisive p.pair.originalAnswer)).length
        + ((cellItems pool w b).filter
          (fun p : PoolItem => ModelAnswer.decisive p.pair.perturbedAnswer)).length :=
  countAnswers_map ModelAnswer.decisive (cellItems pool w b)

/-- Σ of the six cells' raw coverage numerators. -/
def cellSumCoverage (pool : List PoolItem) : Nat :=
  cellCoverageNum pool Winner.no MarginBand.narrow
    + cellCoverageNum pool Winner.no MarginBand.close
    + cellCoverageNum pool Winner.no MarginBand.wide
    + cellCoverageNum pool Winner.yes MarginBand.narrow
    + cellCoverageNum pool Winner.yes MarginBand.close
    + cellCoverageNum pool Winner.yes MarginBand.wide

/-- Σ of the six cells' answer-slot counts — the raw coverage
denominator (the `2N` scale). -/
def cellSumAnswer (pool : List PoolItem) : Nat :=
  cellAnswerCount pool Winner.no MarginBand.narrow
    + cellAnswerCount pool Winner.no MarginBand.close
    + cellAnswerCount pool Winner.no MarginBand.wide
    + cellAnswerCount pool Winner.yes MarginBand.narrow
    + cellAnswerCount pool Winner.yes MarginBand.close
    + cellAnswerCount pool Winner.yes MarginBand.wide

theorem cellSumAnswer_add (pool : List PoolItem) :
    cellSumAnswer pool = 2 * pool.length :=
  cellAnswerCount_add pool

theorem cellSumCoverage_add (pool : List PoolItem) :
    cellSumCoverage pool = ResponseSet.coverageNum (PoolItem.toResponseSet pool) := by
  unfold cellSumCoverage
  rw [cellCoverageNum_filter, cellCoverageNum_filter, cellCoverageNum_filter,
      cellCoverageNum_filter, cellCoverageNum_filter, cellCoverageNum_filter]
  have hrhs : ResponseSet.coverageNum (PoolItem.toResponseSet pool)
      = (pool.filter (fun p : PoolItem => ModelAnswer.decisive p.pair.originalAnswer)).length
        + (pool.filter (fun p : PoolItem => ModelAnswer.decisive p.pair.perturbedAnswer)).length :=
    countAnswers_map ModelAnswer.decisive pool
  rw [hrhs]
  have ho := cellOrigCount_add ModelAnswer.decisive pool
  have hp := cellPertCount_add ModelAnswer.decisive pool
  omega

/-- **The Σnᵢ/Σdᵢ aggregate of the per-cell coverage counters** (raw). -/
def coverageAgg (pool : List PoolItem) : Rate :=
  { num := cellSumCoverage pool, den := cellSumAnswer pool }

/-- **Aggregation (coverage)**: the pool-level coverage IS the Σnᵢ/Σdᵢ
fraction of the raw per-cell counters (denominator the `2N` scale,
via `cellAnswerCount_add`). -/
theorem coverage_agg (pool : List PoolItem) :
    ResponseSet.coverage (PoolItem.toResponseSet pool) = coverageAgg pool := by
  unfold ResponseSet.coverage coverageAgg
  rw [cellSumCoverage_add, cellSumAnswer_add]
  have h2 : (PoolItem.toResponseSet pool).nAnswers = 2 * pool.length := by
    simp [ResponseSet.nAnswers, PoolItem.toResponseSet]
  rw [h2]

/-! ### The invalid-response rates: Σnᵢ/Σdᵢ over the six cells

The three `/2N` rates share the coverage denominator (`nAnswers`, the
`2N` scale), so all three aggregate through one template: raw per-cell
numerators via `countAnswers_map`, Σ-additivity via
`cellOrigCount_add` / `cellPertCount_add`, denominator via
`cellAnswerCount_add`. -/

/-- Raw per-cell abstain numerator (no `Option` wrapper). -/
def cellAbstainNum (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  ResponseSet.abstainNum (cellImage pool w b)

/-- The per-cell abstain numerator in the two-side filter form. -/
theorem cellAbstainNum_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellAbstainNum pool w b
      = ((cellItems pool w b).filter
          (fun p : PoolItem => ModelAnswer.isAbstain p.pair.originalAnswer)).length
        + ((cellItems pool w b).filter
          (fun p : PoolItem => ModelAnswer.isAbstain p.pair.perturbedAnswer)).length :=
  countAnswers_map ModelAnswer.isAbstain (cellItems pool w b)

/-- Σ of the six cells' raw abstain numerators. -/
def cellSumAbstain (pool : List PoolItem) : Nat :=
  cellAbstainNum pool Winner.no MarginBand.narrow
    + cellAbstainNum pool Winner.no MarginBand.close
    + cellAbstainNum pool Winner.no MarginBand.wide
    + cellAbstainNum pool Winner.yes MarginBand.narrow
    + cellAbstainNum pool Winner.yes MarginBand.close
    + cellAbstainNum pool Winner.yes MarginBand.wide

theorem cellSumAbstain_add (pool : List PoolItem) :
    cellSumAbstain pool = ResponseSet.abstainNum (PoolItem.toResponseSet pool) := by
  unfold cellSumAbstain
  rw [cellAbstainNum_filter, cellAbstainNum_filter, cellAbstainNum_filter,
      cellAbstainNum_filter, cellAbstainNum_filter, cellAbstainNum_filter]
  have hrhs : ResponseSet.abstainNum (PoolItem.toResponseSet pool)
      = (pool.filter (fun p : PoolItem => ModelAnswer.isAbstain p.pair.originalAnswer)).length
        + (pool.filter (fun p : PoolItem => ModelAnswer.isAbstain p.pair.perturbedAnswer)).length :=
    countAnswers_map ModelAnswer.isAbstain pool
  rw [hrhs]
  have ho := cellOrigCount_add ModelAnswer.isAbstain pool
  have hp := cellPertCount_add ModelAnswer.isAbstain pool
  omega

/-- **The Σnᵢ/Σdᵢ aggregate of the per-cell abstain counters** (raw). -/
def abstainRateAgg (pool : List PoolItem) : Rate :=
  { num := cellSumAbstain pool, den := cellSumAnswer pool }

/-- **Aggregation (abstainRate)**: the pool-level invalid-response rate
IS the Σnᵢ/Σdᵢ fraction of the raw per-cell counters (denominator the
`2N` scale, via `cellAnswerCount_add`). -/
theorem abstainRate_agg (pool : List PoolItem) :
    ResponseSet.abstainRate (PoolItem.toResponseSet pool) = abstainRateAgg pool := by
  unfold ResponseSet.abstainRate abstainRateAgg
  rw [cellSumAbstain_add, cellSumAnswer_add]
  have h2 : (PoolItem.toResponseSet pool).nAnswers = 2 * pool.length := by
    simp [ResponseSet.nAnswers, PoolItem.toResponseSet]
  rw [h2]

/-- Raw per-cell refusal numerator (no `Option` wrapper). -/
def cellRefusalNum (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  ResponseSet.refusalNum (cellImage pool w b)

/-- The per-cell refusal numerator in the two-side filter form. -/
theorem cellRefusalNum_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellRefusalNum pool w b
      = ((cellItems pool w b).filter
          (fun p : PoolItem => ModelAnswer.isRefusal p.pair.originalAnswer)).length
        + ((cellItems pool w b).filter
          (fun p : PoolItem => ModelAnswer.isRefusal p.pair.perturbedAnswer)).length :=
  countAnswers_map ModelAnswer.isRefusal (cellItems pool w b)

/-- Σ of the six cells' raw refusal numerators. -/
def cellSumRefusal (pool : List PoolItem) : Nat :=
  cellRefusalNum pool Winner.no MarginBand.narrow
    + cellRefusalNum pool Winner.no MarginBand.close
    + cellRefusalNum pool Winner.no MarginBand.wide
    + cellRefusalNum pool Winner.yes MarginBand.narrow
    + cellRefusalNum pool Winner.yes MarginBand.close
    + cellRefusalNum pool Winner.yes MarginBand.wide

theorem cellSumRefusal_add (pool : List PoolItem) :
    cellSumRefusal pool = ResponseSet.refusalNum (PoolItem.toResponseSet pool) := by
  unfold cellSumRefusal
  rw [cellRefusalNum_filter, cellRefusalNum_filter, cellRefusalNum_filter,
      cellRefusalNum_filter, cellRefusalNum_filter, cellRefusalNum_filter]
  have hrhs : ResponseSet.refusalNum (PoolItem.toResponseSet pool)
      = (pool.filter (fun p : PoolItem => ModelAnswer.isRefusal p.pair.originalAnswer)).length
        + (pool.filter (fun p : PoolItem => ModelAnswer.isRefusal p.pair.perturbedAnswer)).length :=
    countAnswers_map ModelAnswer.isRefusal pool
  rw [hrhs]
  have ho := cellOrigCount_add ModelAnswer.isRefusal pool
  have hp := cellPertCount_add ModelAnswer.isRefusal pool
  omega

/-- **The Σnᵢ/Σdᵢ aggregate of the per-cell refusal counters** (raw). -/
def refusalRateAgg (pool : List PoolItem) : Rate :=
  { num := cellSumRefusal pool, den := cellSumAnswer pool }

/-- **Aggregation (refusalRate)**: the pool-level invalid-response rate
IS the Σnᵢ/Σdᵢ fraction of the raw per-cell counters (denominator the
`2N` scale, via `cellAnswerCount_add`). -/
theorem refusalRate_agg (pool : List PoolItem) :
    ResponseSet.refusalRate (PoolItem.toResponseSet pool) = refusalRateAgg pool := by
  unfold ResponseSet.refusalRate refusalRateAgg
  rw [cellSumRefusal_add, cellSumAnswer_add]
  have h2 : (PoolItem.toResponseSet pool).nAnswers = 2 * pool.length := by
    simp [ResponseSet.nAnswers, PoolItem.toResponseSet]
  rw [h2]

/-- Raw per-cell unresolvable numerator (no `Option` wrapper). -/
def cellUnresolvableNum (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  ResponseSet.unresolvableNum (cellImage pool w b)

/-- The per-cell unresolvable numerator in the two-side filter form. -/
theorem cellUnresolvableNum_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellUnresolvableNum pool w b
      = ((cellItems pool w b).filter
          (fun p : PoolItem => ModelAnswer.isUnresolvable p.pair.originalAnswer)).length
        + ((cellItems pool w b).filter
          (fun p : PoolItem => ModelAnswer.isUnresolvable p.pair.perturbedAnswer)).length :=
  countAnswers_map ModelAnswer.isUnresolvable (cellItems pool w b)

/-- Σ of the six cells' raw unresolvable numerators. -/
def cellSumUnresolvable (pool : List PoolItem) : Nat :=
  cellUnresolvableNum pool Winner.no MarginBand.narrow
    + cellUnresolvableNum pool Winner.no MarginBand.close
    + cellUnresolvableNum pool Winner.no MarginBand.wide
    + cellUnresolvableNum pool Winner.yes MarginBand.narrow
    + cellUnresolvableNum pool Winner.yes MarginBand.close
    + cellUnresolvableNum pool Winner.yes MarginBand.wide

theorem cellSumUnresolvable_add (pool : List PoolItem) :
    cellSumUnresolvable pool = ResponseSet.unresolvableNum (PoolItem.toResponseSet pool) := by
  unfold cellSumUnresolvable
  rw [cellUnresolvableNum_filter, cellUnresolvableNum_filter, cellUnresolvableNum_filter,
      cellUnresolvableNum_filter, cellUnresolvableNum_filter, cellUnresolvableNum_filter]
  have hrhs : ResponseSet.unresolvableNum (PoolItem.toResponseSet pool)
      = (pool.filter (fun p : PoolItem => ModelAnswer.isUnresolvable p.pair.originalAnswer)).length
        + (pool.filter (fun p : PoolItem => ModelAnswer.isUnresolvable p.pair.perturbedAnswer)).length :=
    countAnswers_map ModelAnswer.isUnresolvable pool
  rw [hrhs]
  have ho := cellOrigCount_add ModelAnswer.isUnresolvable pool
  have hp := cellPertCount_add ModelAnswer.isUnresolvable pool
  omega

/-- **The Σnᵢ/Σdᵢ aggregate of the per-cell unresolvable counters**
(raw). -/
def unresolvableRateAgg (pool : List PoolItem) : Rate :=
  { num := cellSumUnresolvable pool, den := cellSumAnswer pool }

/-- **Aggregation (unresolvableRate)**: the pool-level invalid-response
rate IS the Σnᵢ/Σdᵢ fraction of the raw per-cell counters (denominator
the `2N` scale, via `cellAnswerCount_add`). -/
theorem unresolvableRate_agg (pool : List PoolItem) :
    ResponseSet.unresolvableRate (PoolItem.toResponseSet pool) = unresolvableRateAgg pool := by
  unfold ResponseSet.unresolvableRate unresolvableRateAgg
  rw [cellSumUnresolvable_add, cellSumAnswer_add]
  have h2 : (PoolItem.toResponseSet pool).nAnswers = 2 * pool.length := by
    simp [ResponseSet.nAnswers, PoolItem.toResponseSet]
  rw [h2]

/-! ## Weighted aggregation: class-specific denominators

Item 2 of the review's ordering — the two metrics whose denominator is
NOT the cell's pair count.

* `strictConditional` — same Σnᵢ/Σdᵢ shape as accuracy, but the
  denominator is the `originalCorrectNum` scale (additivity via
  `originalCorrectNum_add`).
* `balancedPerturbedAccuracy` — a mean of two per-class recall fractions
  (the `perturbedGT` classes), so the pool-level aggregate is the SAME
  cross-multiplied fraction with the per-cell class numerators and
  denominators summed — NOT Σnᵢ/Σdᵢ of per-cell balanced fractions
  (a mean of means is not the pooled mean). The class denominators are
  the `perturbedGT` class counts (`gtCount`); both aggregate on raw
  counters, never on `Option Rate` values, and `none` is preserved as
  undefinedness (a class with no pairs keeps the metric undefined). -/

/-- The perturbed-GT class predicates on a pair, in the exact match-form
the `balancedPerturbedAccuracy` definition filters with. -/
def isPertGTyes (r : ModelResponsePair) : Bool :=
  match r.perturbedGT with | .yes => true | .no => false

def isPertGTno (r : ModelResponsePair) : Bool :=
  match r.perturbedGT with | .no => true | .yes => false

/-- The match-form class predicate IS `sameGT … Winner.yes` pointwise
(the bridge consumed by the class-count aggregation). -/
theorem isPertGTyes_eq_sameGT (p : PoolItem) :
    (match p.pair.perturbedGT with | .yes => true | .no => false)
      = sameGT p.pair.perturbedGT Winner.yes := by
  cases hp : p.pair.perturbedGT <;> rfl

theorem isPertGTno_eq_sameGT (p : PoolItem) :
    (match p.pair.perturbedGT with | .no => true | .yes => false)
      = sameGT p.pair.perturbedGT Winner.no := by
  cases hp : p.pair.perturbedGT <;> rfl

-- The `Winner` match-aux constants (the metric's, and the one the
-- textual match-forms in this file elaborate to) are the same polymorphic
-- matcher; `reducible` locally so tactic matching at instances
-- transparency can see through the different aux names.
set_option allowUnsafeReducibility true in
attribute [local reducible] ModelResponsePair.direction.match_1
  minCellSize.match_1
  ResponseSet.balancedPairSuccess.match_1
  ResponseSet.balancedPairSuccess.match_3
  ResponseSet.balancedPairSuccess.match_5

/-! ### (a) Conditional responsiveness — denominator `originalCorrectNum` -/

/-- **Raw per-cell conditional denominator** — the cell's originalCorrect
count (no `Option` wrapper; aggregation never coerces `none`). -/
def cellOriginalCorrectNum (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  ResponseSet.originalCorrectNum (cellImage pool w b)

/-- The per-cell conditional denominator in the filter form consumed by
`cellPairCount_add`. -/
theorem cellOriginalCorrectNum_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellOriginalCorrectNum pool w b
      = (List.filter (fun p : PoolItem => p.pair.originalCorrect)
          (cellItems pool w b)).length :=
  countPairs_map ModelResponsePair.originalCorrect (cellItems pool w b)

/-- Σ of the six cells' raw conditional denominators. -/
def cellSumOriginalCorrect (pool : List PoolItem) : Nat :=
  cellOriginalCorrectNum pool Winner.no MarginBand.narrow
    + cellOriginalCorrectNum pool Winner.no MarginBand.close
    + cellOriginalCorrectNum pool Winner.no MarginBand.wide
    + cellOriginalCorrectNum pool Winner.yes MarginBand.narrow
    + cellOriginalCorrectNum pool Winner.yes MarginBand.close
    + cellOriginalCorrectNum pool Winner.yes MarginBand.wide

theorem cellSumOriginalCorrect_add (pool : List PoolItem) :
    cellSumOriginalCorrect pool
      = ResponseSet.originalCorrectNum (PoolItem.toResponseSet pool) := by
  unfold cellSumOriginalCorrect
  rw [cellOriginalCorrectNum_filter, cellOriginalCorrectNum_filter,
      cellOriginalCorrectNum_filter, cellOriginalCorrectNum_filter,
      cellOriginalCorrectNum_filter, cellOriginalCorrectNum_filter]
  exact (cellPairCount_add (fun p : PoolItem => p.pair.originalCorrect) pool).trans
    (originalCorrectNum_eq_responseSet pool)

/-- **The Σnᵢ/Σdᵢ aggregate of the conditional rates**: numerator the Σ
of the cells' strict counters (the same raw counter as accuracy, via the
`bothCorrectNum ≡ strictNum` bridge), denominator the Σ of the cells'
`originalCorrectNum` counts. `none` iff the pool has no original-correct
pair — the same undefinedness as the pool-level metric. -/
def strictConditionalAgg (pool : List PoolItem) : Option Rate :=
  if cellSumOriginalCorrect pool = 0 then none
  else some { num := cellSumBothCorrect pool, den := cellSumOriginalCorrect pool }

/-- **Aggregation (strictConditional)**: the pool-level conditional
responsiveness IS the Σnᵢ/Σdᵢ fraction of the raw per-cell counters,
with the class-specific denominator `originalCorrectNum` (not `N`). -/
theorem strictConditional_agg (pool : List PoolItem) :
    ResponseSet.strictConditional (PoolItem.toResponseSet pool)
      = strictConditionalAgg pool := by
  unfold ResponseSet.strictConditional strictConditionalAgg
  simp only [cellSumOriginalCorrect_add, cellSumBothCorrect_add]

/-! ### (b) Balanced perturbed accuracy — per-class denominators -/

/-- **Raw per-cell class-`yes` denominator**: pairs in the cell whose
perturbed GT is `yes` (the whole cell when the cell's GT is `yes`,
empty otherwise — no special-casing needed, the filter does it). -/
def cellClassYesDen (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  ((cellImage pool w b).filter isPertGTyes).length

/-- **Raw per-cell class-`no` denominator.** -/
def cellClassNoDen (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  ((cellImage pool w b).filter isPertGTno).length

/-- **Raw per-cell class-`yes` numerator** (perturbedCorrect within the
cell's `yes` class). -/
def cellClassYesNum (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  countPairs ((cellImage pool w b).filter isPertGTyes) (fun r => r.perturbedCorrect)

/-- **Raw per-cell class-`no` numerator.** -/
def cellClassNoNum (pool : List PoolItem) (w : Winner) (b : MarginBand) : Nat :=
  countPairs ((cellImage pool w b).filter isPertGTno) (fun r => r.perturbedCorrect)

/-- The per-cell class-`yes` denominator in the filter form consumed by
`cellPairCount_add`. -/
theorem cellClassYesDen_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellClassYesDen pool w b
      = (List.filter (fun p : PoolItem => isPertGTyes p.pair)
          (cellItems pool w b)).length := by
  simp only [cellClassYesDen, cellImage, PoolItem.toResponseSet,
    filter_map_pair, List.length_map]

theorem cellClassNoDen_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellClassNoDen pool w b
      = (List.filter (fun p : PoolItem => isPertGTno p.pair)
          (cellItems pool w b)).length := by
  unfold cellClassNoDen cellImage PoolItem.toResponseSet
  rw [filter_map_pair, List.length_map]

/-- The per-cell class-`yes` numerator in the filter form (the
two-step filter collapsed into one compound predicate). -/
theorem cellClassYesNum_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellClassYesNum pool w b
      = (List.filter (fun p : PoolItem => p.pair.perturbedCorrect && isPertGTyes p.pair)
          (cellItems pool w b)).length := by
  unfold cellClassYesNum cellImage PoolItem.toResponseSet countPairs
  rw [List.filter_filter, filter_map_pair, List.length_map]

theorem cellClassNoNum_filter (pool : List PoolItem) (w : Winner) (b : MarginBand) :
    cellClassNoNum pool w b
      = (List.filter (fun p : PoolItem => p.pair.perturbedCorrect && isPertGTno p.pair)
          (cellItems pool w b)).length := by
  unfold cellClassNoNum cellImage PoolItem.toResponseSet countPairs
  rw [List.filter_filter, filter_map_pair, List.length_map]

/-- Σ of the six cells' raw class-`yes` denominators. -/
def cellSumClassYesDen (pool : List PoolItem) : Nat :=
  cellClassYesDen pool Winner.no MarginBand.narrow
    + cellClassYesDen pool Winner.no MarginBand.close
    + cellClassYesDen pool Winner.no MarginBand.wide
    + cellClassYesDen pool Winner.yes MarginBand.narrow
    + cellClassYesDen pool Winner.yes MarginBand.close
    + cellClassYesDen pool Winner.yes MarginBand.wide

/-- Σ of the six cells' raw class-`no` denominators. -/
def cellSumClassNoDen (pool : List PoolItem) : Nat :=
  cellClassNoDen pool Winner.no MarginBand.narrow
    + cellClassNoDen pool Winner.no MarginBand.close
    + cellClassNoDen pool Winner.no MarginBand.wide
    + cellClassNoDen pool Winner.yes MarginBand.narrow
    + cellClassNoDen pool Winner.yes MarginBand.close
    + cellClassNoDen pool Winner.yes MarginBand.wide

/-- Σ of the six cells' raw class-`yes` numerators. -/
def cellSumClassYesNum (pool : List PoolItem) : Nat :=
  cellClassYesNum pool Winner.no MarginBand.narrow
    + cellClassYesNum pool Winner.no MarginBand.close
    + cellClassYesNum pool Winner.no MarginBand.wide
    + cellClassYesNum pool Winner.yes MarginBand.narrow
    + cellClassYesNum pool Winner.yes MarginBand.close
    + cellClassYesNum pool Winner.yes MarginBand.wide

/-- Σ of the six cells' raw class-`no` numerators. -/
def cellSumClassNoNum (pool : List PoolItem) : Nat :=
  cellClassNoNum pool Winner.no MarginBand.narrow
    + cellClassNoNum pool Winner.no MarginBand.close
    + cellClassNoNum pool Winner.no MarginBand.wide
    + cellClassNoNum pool Winner.yes MarginBand.narrow
    + cellClassNoNum pool Winner.yes MarginBand.close
    + cellClassNoNum pool Winner.yes MarginBand.wide

/-- **Additivity of the class-`yes` denominator**: the Σ over the six
cells IS the pool's `perturbedGT = yes` class count (`gtCount`). -/
theorem cellSumClassYesDen_add (pool : List PoolItem) :
    cellSumClassYesDen pool = gtCount pool Winner.yes := by
  unfold cellSumClassYesDen
  rw [cellClassYesDen_filter, cellClassYesDen_filter, cellClassYesDen_filter,
      cellClassYesDen_filter, cellClassYesDen_filter, cellClassYesDen_filter]
  have h := cellPairCount_add (fun p : PoolItem => isPertGTyes p.pair) pool
  rw [h]
  simp only [gtCount, isPertGTyes, isPertGTyes_eq_sameGT]

/-- **Additivity of the class-`no` denominator.** -/
theorem cellSumClassNoDen_add (pool : List PoolItem) :
    cellSumClassNoDen pool = gtCount pool Winner.no := by
  unfold cellSumClassNoDen
  rw [cellClassNoDen_filter, cellClassNoDen_filter, cellClassNoDen_filter,
      cellClassNoDen_filter, cellClassNoDen_filter, cellClassNoDen_filter]
  have h := cellPairCount_add (fun p : PoolItem => isPertGTno p.pair) pool
  rw [h]
  simp only [gtCount, isPertGTno, isPertGTno_eq_sameGT]

/-- **Additivity of the class-`yes` numerator.** -/
theorem cellSumClassYesNum_add (pool : List PoolItem) :
    cellSumClassYesNum pool
      = (pool.filter (fun p : PoolItem => p.pair.perturbedCorrect
          && sameGT p.pair.perturbedGT Winner.yes)).length := by
  unfold cellSumClassYesNum
  rw [cellClassYesNum_filter, cellClassYesNum_filter, cellClassYesNum_filter,
      cellClassYesNum_filter, cellClassYesNum_filter, cellClassYesNum_filter]
  have h := cellPairCount_add
    (fun p : PoolItem => p.pair.perturbedCorrect && isPertGTyes p.pair) pool
  rw [h]
  simp only [isPertGTyes, isPertGTyes_eq_sameGT]

/-- **Additivity of the class-`no` numerator.** -/
theorem cellSumClassNoNum_add (pool : List PoolItem) :
    cellSumClassNoNum pool
      = (pool.filter (fun p : PoolItem => p.pair.perturbedCorrect
          && sameGT p.pair.perturbedGT Winner.no)).length := by
  unfold cellSumClassNoNum
  rw [cellClassNoNum_filter, cellClassNoNum_filter, cellClassNoNum_filter,
      cellClassNoNum_filter, cellClassNoNum_filter, cellClassNoNum_filter]
  have h := cellPairCount_add
    (fun p : PoolItem => p.pair.perturbedCorrect && isPertGTno p.pair) pool
  rw [h]
  simp only [isPertGTno, isPertGTno_eq_sameGT]

/-- The pool-level class-`yes` denominator (the metric's `yesPairs`
length) IS `gtCount pool Winner.yes`. Stated over the map-form (the
`ResponseSet` alias is semireducible; the metric unfolds to this form). -/
theorem classYesDen_map (pool : List PoolItem) :
    (List.filter (fun r : ModelResponsePair => match r.perturbedGT with
        | .yes => true | .no => false)
        (pool.map PoolItem.pair)).length
      = gtCount pool Winner.yes := by
  rw [filter_map_pair, List.length_map]
  simp only [gtCount, isPertGTyes_eq_sameGT]

/-- The pool-level class-`no` denominator IS `gtCount pool Winner.no`. -/
theorem classNoDen_map (pool : List PoolItem) :
    (List.filter (fun r : ModelResponsePair => match r.perturbedGT with
        | .no => true | .yes => false)
        (pool.map PoolItem.pair)).length
      = gtCount pool Winner.no := by
  rw [filter_map_pair, List.length_map]
  simp only [gtCount, isPertGTno_eq_sameGT]

/-- The pool-level class-`yes` numerator (the metric's `recYes` counter)
in the sameGT filter form. -/
theorem classYesNum_map (pool : List PoolItem) :
    countPairs (List.filter (fun r : ModelResponsePair => match r.perturbedGT with
        | .yes => true | .no => false)
        (pool.map PoolItem.pair)) (fun r => r.perturbedCorrect)
      = (pool.filter (fun p : PoolItem => p.pair.perturbedCorrect
          && sameGT p.pair.perturbedGT Winner.yes)).length := by
  unfold countPairs
  rw [List.filter_filter, filter_map_pair, List.length_map]
  simp only [isPertGTyes_eq_sameGT]

/-- The pool-level class-`no` numerator (the metric's `recNo` counter)
in the sameGT filter form. -/
theorem classNoNum_map (pool : List PoolItem) :
    countPairs (List.filter (fun r : ModelResponsePair => match r.perturbedGT with
        | .no => true | .yes => false)
        (pool.map PoolItem.pair)) (fun r => r.perturbedCorrect)
      = (pool.filter (fun p : PoolItem => p.pair.perturbedCorrect
          && sameGT p.pair.perturbedGT Winner.no)).length := by
  unfold countPairs
  rw [List.filter_filter, filter_map_pair, List.length_map]
  simp only [isPertGTno_eq_sameGT]

/-- **The aggregate of the balanced perturbed accuracy**: the SAME
cross-multiplied fraction the pool metric builds from its two per-class
recall rates, with the class numerators/denominators replaced by their
Σ over the six cells. `none` iff either perturbed-GT class is empty in
the pool — the same undefinedness as the pool-level metric (no
`none`-as-zero coercion). -/
def balancedPerturbedAccuracyAgg (pool : List PoolItem) : Option Rate :=
  if cellSumClassYesDen pool = 0 then none
  else if cellSumClassNoDen pool = 0 then none
  else some (Rate.mk
    (cellSumClassYesNum pool * cellSumClassNoDen pool
      + cellSumClassNoNum pool * cellSumClassYesDen pool)
    (2 * cellSumClassYesDen pool * cellSumClassNoDen pool))

/-- **Aggregation (balancedPerturbedAccuracy)**: the pool-level balanced
perturbed accuracy IS the cross-multiplied aggregate of the raw per-cell
class counters, with the class denominators the `perturbedGT` class
counts (`gtCount`, additivity via `cellSumClass*Den_add`). -/
theorem balancedPerturbedAccuracy_agg (pool : List PoolItem) :
    ResponseSet.balancedPerturbedAccuracy (PoolItem.toResponseSet pool)
      = balancedPerturbedAccuracyAgg pool := by
  unfold ResponseSet.balancedPerturbedAccuracy balancedPerturbedAccuracyAgg
  simp only [PoolItem.toResponseSet, classYesDen_map, classNoDen_map,
    classYesNum_map, classNoNum_map,
    cellSumClassYesDen_add, cellSumClassNoDen_add, cellSumClassYesNum_add,
    cellSumClassNoNum_add]
  by_cases hY : gtCount pool Winner.yes = 0
  · rw [ite_eq_left hY, ite_eq_left hY]
  · by_cases hN : gtCount pool Winner.no = 0
    · rw [ite_eq_right hY, ite_eq_right hY, ite_eq_left hN, ite_eq_left hN]
    · rw [ite_eq_right hY, ite_eq_right hY, ite_eq_right hN, ite_eq_right hN]

end Sejmbench
