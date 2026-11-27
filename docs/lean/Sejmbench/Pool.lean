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

end Sejmbench
