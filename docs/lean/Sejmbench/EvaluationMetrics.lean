import Sejmbench.FlipPair

/-!
# EvaluationMetrics (issue #24, L3 — metrics over ModelResponsePairs)

Formal definitions of the CounterfactualV2 metrics, per the review of
c8b6222 (2026-11-25). Design decisions fixed here:

* The unit of data is the pair; each pair carries TWO answers, so all
  answer-level rates use the denominator `2 * N` (both sides), while
  pair-level rates use `N`.
* Coverage = decisive answers / (2N); `bothDecisiveRate` = pairs with
  both answers decisive / N — different questions, both reported.
* The four disjoint categories (decisive, abstain, refusal,
  unresolvable) sum to the total: the identity is PROVEN
  (`disjoint_total`), not just described.
* Strict responsiveness has two estimands: conditional (over pairs
  correct on the original) and unconditional (over all pairs); a zero
  denominator yields an explicit `none`, never a default number.
* Incidental correctness stays a separate counter.
* Accuracy is pair-level (both answers correct / N); the balanced view
  of that same criterion is `balancedPairSuccess` (stratified by
  original GT class, `none` when a class has no pairs — never
  defaulted). The #22 contract view — quality of the answer about the
  PERTURBED question — lives in `perturbedAccuracy` and
  `balancedPerturbedAccuracy` (per-perturbed-class recall).

The denominators come from `List.length`, so every metric is a rational
number with a concrete denominator — no floating-point assumptions.
-/

namespace Sejmbench

/-! ## Counting helpers (List.length-backed, so `n = 2 * N` is provable) -/

/-- The list of ModelResponsePairs under evaluation. -/
def ResponseSet := List ModelResponsePair

/-- Number of pairs. -/
def ResponseSet.N (rs : ResponseSet) : Nat := rs.length

/-- Number of answer slots: two per pair. -/
def ResponseSet.nAnswers (rs : ResponseSet) : Nat := 2 * rs.length

/-- Count of pairs satisfying a boolean predicate. -/
def countPairs (rs : ResponseSet) (f : ModelResponsePair → Bool) : Nat :=
  (rs.filter f).length

/-- Count of ANSWER slots (both sides of each pair) whose answer
satisfies the boolean predicate `g`. -/
def countAnswers (rs : ResponseSet) (g : ModelAnswer → Bool) : Nat :=
  (rs.filter (fun r => g r.originalAnswer)).length +
  (rs.filter (fun r => g r.perturbedAnswer)).length

/-- The total count equals the number of answer slots — the denominator
identity all rates below rely on. -/
theorem countAnswers_total (rs : ResponseSet) :
    countAnswers rs (fun _ => true) = rs.nAnswers := by
  have h : (rs.filter (fun _ => true)) = rs := List.filter_eq_self.mpr (fun a _ => rfl)
  show ((rs.filter (fun _ => true)).length + (rs.filter (fun _ => true)).length)
      = 2 * rs.length
  rw [h]
  omega

/-! ## The four answer categories (exhaustive and disjoint) -/

/-- Is the answer an abstain? -/
def ModelAnswer.isAbstain : ModelAnswer → Bool
  | .abstain => true
  | _ => false

/-- Is the answer a refusal? -/
def ModelAnswer.isRefusal : ModelAnswer → Bool
  | .refusal => true
  | _ => false

/-- Is the answer unresolvable? -/
def ModelAnswer.isUnresolvable : ModelAnswer → Bool
  | .unresolvable => true
  | _ => false

/-- The four categories are exhaustive and disjoint: every answer is
exactly one of decisive / abstain / refusal / unresolvable. The proof is
a 5-case analysis on `ModelAnswer`. -/
theorem answer_case_split (a : ModelAnswer) :
    (if a.decisive then 1 else 0) + (if a.isAbstain then 1 else 0)
      + (if a.isRefusal then 1 else 0)
      + (if a.isUnresolvable then 1 else 0) = 1 := by
  cases a with
  | yes => simp [ModelAnswer.decisive, ModelAnswer.isAbstain,
      ModelAnswer.isRefusal, ModelAnswer.isUnresolvable]
  | no => simp [ModelAnswer.decisive, ModelAnswer.isAbstain,
      ModelAnswer.isRefusal, ModelAnswer.isUnresolvable]
  | abstain => simp [ModelAnswer.decisive, ModelAnswer.isAbstain,
      ModelAnswer.isRefusal, ModelAnswer.isUnresolvable]
  | refusal => simp [ModelAnswer.decisive, ModelAnswer.isAbstain,
      ModelAnswer.isRefusal, ModelAnswer.isUnresolvable]
  | unresolvable => simp [ModelAnswer.decisive, ModelAnswer.isAbstain,
      ModelAnswer.isRefusal, ModelAnswer.isUnresolvable]

/-- Cons decomposition of `countAnswers`: the pair `r` contributes
exactly the indicator sum of its two answers. -/
theorem countAnswers_cons (g : ModelAnswer → Bool) (r : ModelResponsePair)
    (rest : List ModelResponsePair) :
    countAnswers (r :: rest) g
      = countAnswers rest g
        + ((if g r.originalAnswer then 1 else 0)
          + (if g r.perturbedAnswer then 1 else 0)) := by
  by_cases h1 : g r.originalAnswer <;> by_cases h2 : g r.perturbedAnswer <;>
    simp [h1, h2, countAnswers] <;> omega

/-- **The disjoint-total identity** (review item B): decisive + abstain +
refusal + unresolvable counts sum to the total answer count `2N`. This
makes `Coverage + AbstainRate + RefusalRate + UnresolvableRate = 1` a
theorem about the aggregation, not a comment. -/
theorem disjoint_total (rs : ResponseSet) :
    countAnswers rs ModelAnswer.decisive
      + countAnswers rs ModelAnswer.isAbstain
      + countAnswers rs ModelAnswer.isRefusal
      + countAnswers rs ModelAnswer.isUnresolvable
      = 2 * rs.length := by
  induction rs with
  | nil => simp [countAnswers]
  | cons r rest ih =>
      rw [countAnswers_cons ModelAnswer.decisive r rest,
          countAnswers_cons ModelAnswer.isAbstain r rest,
          countAnswers_cons ModelAnswer.isRefusal r rest,
          countAnswers_cons ModelAnswer.isUnresolvable r rest]
      have h1 := answer_case_split r.originalAnswer
      have h2 := answer_case_split r.perturbedAnswer
      rw [List.length_cons]
      omega

/-! ## The metrics -/

/-- **Coverage** (review item A): decisive answers over ALL answer slots
(both sides, `2N` denominator). -/
def ResponseSet.coverageNum (rs : ResponseSet) : Nat :=
  countAnswers rs ModelAnswer.decisive

/-- **Both-decisive rate** numerator: pairs where BOTH answers are
decisive. Different question than coverage; reported alongside it. -/
def ResponseSet.bothDecisiveNum (rs : ResponseSet) : Nat :=
  countPairs rs (fun r => r.originalAnswer.decisive && r.perturbedAnswer.decisive)

/-- **Strict responsiveness numerator** (the two estimands share it). -/
def ResponseSet.strictNum (rs : ResponseSet) : Nat :=
  countPairs rs ModelResponsePair.strictlyResponsive

/-- **Original-correct numerator** (the conditional responsiveness
denominator). -/
def ResponseSet.originalCorrectNum (rs : ResponseSet) : Nat :=
  countPairs rs ModelResponsePair.originalCorrect

/-- **Incidental correctness numerator** — always a separate counter. -/
def ResponseSet.incidentalNum (rs : ResponseSet) : Nat :=
  countPairs rs ModelResponsePair.incidentallyCorrect

/-- The three invalid-response numerators, over ALL answer slots (2N
denominator, per review item B). -/
def ResponseSet.abstainNum (rs : ResponseSet) : Nat :=
  countAnswers rs ModelAnswer.isAbstain

def ResponseSet.refusalNum (rs : ResponseSet) : Nat :=
  countAnswers rs ModelAnswer.isRefusal

def ResponseSet.unresolvableNum (rs : ResponseSet) : Nat :=
  countAnswers rs ModelAnswer.isUnresolvable

/-- **Accuracy numerator** (pair-level): both answers correct. Note this
is NOT the same predicate as `strictlyResponsive` on non-reversal pairs —
here the GT is guaranteed to differ, so they coincide; the separate
definition documents the intent. -/
def ResponseSet.bothCorrectNum (rs : ResponseSet) : Nat :=
  countPairs rs (fun r => r.originalCorrect && r.perturbedCorrect)

/-- A rational with an explicit denominator; `none` models the
"undefined" case (zero denominator) instead of defaulting to a number. -/
structure Rate where
  /-- The numerator. -/
  num : Nat
  /-- The denominator (nonzero for a defined rate). -/
  den : Nat

/-- A rate is valid iff its denominator is nonzero. -/
def Rate.defined (r : Rate) : Bool := r.den != 0

/-- **Coverage** as a rate over `2N`. -/
def ResponseSet.coverage (rs : ResponseSet) : Rate :=
  { num := rs.coverageNum, den := rs.nAnswers }

/-- **Both-decisive rate** over `N` (pairs). -/
def ResponseSet.bothDecisive (rs : ResponseSet) : Rate :=
  { num := rs.bothDecisiveNum, den := rs.N }

/-- **Strict responsiveness, conditional**: over pairs correct on the
original. `none` (undefined) when the denominator is zero — never
defaulted, per review item C. -/
def ResponseSet.strictConditional (rs : ResponseSet) : Option Rate :=
  let d := rs.originalCorrectNum
  if d = 0 then none else some { num := rs.strictNum, den := d }

/-- **Strict responsiveness, unconditional**: over all pairs. -/
def ResponseSet.strictUnconditional (rs : ResponseSet) : Option Rate :=
  if rs.N = 0 then none else some { num := rs.strictNum, den := rs.N }

/-- **Incidental correctness rate** over all pairs; `none` on an empty
set. -/
def ResponseSet.incidental (rs : ResponseSet) : Option Rate :=
  if rs.N = 0 then none else some { num := rs.incidentalNum, den := rs.N }

/-- The three **invalid-response rates**, each over `2N`. -/
def ResponseSet.abstainRate (rs : ResponseSet) : Rate :=
  { num := rs.abstainNum, den := rs.nAnswers }

def ResponseSet.refusalRate (rs : ResponseSet) : Rate :=
  { num := rs.refusalNum, den := rs.nAnswers }

def ResponseSet.unresolvableRate (rs : ResponseSet) : Rate :=
  { num := rs.unresolvableNum, den := rs.nAnswers }

/-- **Accuracy** (pair-level, both answers correct over N). NOTE:
`strictUnconditional` coincides with this metric by construction — same
counter (`strictNum` = `bothCorrectNum`'s predicate) and same
denominator; they are one measure reported twice, a consequence of the
adopted criterion, not two independent estimands. -/
def ResponseSet.accuracy (rs : ResponseSet) : Option Rate :=
  if rs.N = 0 then none else some { num := rs.bothCorrectNum, den := rs.N }

/-- **Perturbed accuracy** (the #22 contract's perturbed-GT accuracy,
overall): the share of pairs in which the model's answer about the
PERTURBED division is correct — over all `N` pairs. `none` on an empty
set. -/
def ResponseSet.perturbedAccuracy (rs : ResponseSet) : Option Rate :=
  if rs.N = 0 then none
  else some { num := countPairs rs ModelResponsePair.perturbedCorrect, den := rs.N }

/-- **Balanced pair success** (formerly `balancedAccuracy`): the
balanced version of `accuracy` — the mean of per-class accuracies over
the two GT classes (stratified by `originalGT`), where a pair counts as
correct iff BOTH its answers are correct (the same criterion as
`accuracy` / `bothCorrectNum`). This measures balanced *joint pair
success* by the original GT — NOT the classical per-perturbed-class
recall; for that see `balancedPerturbedAccuracy`. Classes with no pairs
make the metric `none` — explicitly undefined, never defaulted. -/
def ResponseSet.balancedPairSuccess (rs : ResponseSet) : Option Rate :=
  let yesPairs := rs.filter (fun r => match r.originalGT with
    | .yes => true | .no => false)
  let noPairs := rs.filter (fun r => match r.originalGT with
    | .no => true | .yes => false)
  let accYes : Option Rate :=
    if yesPairs.length = 0 then none
    else some (Rate.mk (countPairs yesPairs
      (fun r => r.originalCorrect && r.perturbedCorrect)) yesPairs.length)
  let accNo : Option Rate :=
    if noPairs.length = 0 then none
    else some (Rate.mk (countPairs noPairs
      (fun r => r.originalCorrect && r.perturbedCorrect)) noPairs.length)
  match accYes, accNo with
  | some a, some b => some (Rate.mk (a.num * b.den + b.num * a.den)
      (2 * a.den * b.den))
  | _, _ => none

/-- **Balanced perturbed accuracy** (the #22 contract's balanced
accuracy): the mean of per-class recall over the two `perturbedGT`
classes, recall computed on `perturbedCorrect`. Classes with no pairs
make the metric `none` — explicitly undefined, never defaulted. -/
def ResponseSet.balancedPerturbedAccuracy (rs : ResponseSet) : Option Rate :=
  let yesPairs := rs.filter (fun r => match r.perturbedGT with
    | .yes => true | .no => false)
  let noPairs := rs.filter (fun r => match r.perturbedGT with
    | .no => true | .yes => false)
  let recYes : Option Rate :=
    if yesPairs.length = 0 then none
    else some (Rate.mk (countPairs yesPairs
      (fun r => r.perturbedCorrect)) yesPairs.length)
  let recNo : Option Rate :=
    if noPairs.length = 0 then none
    else some (Rate.mk (countPairs noPairs
      (fun r => r.perturbedCorrect)) noPairs.length)
  match recYes, recNo with
  | some a, some b => some (Rate.mk (a.num * b.den + b.num * a.den)
      (2 * a.den * b.den))
  | _, _ => none

/-! ## Bounds: every numerator is bounded by its denominator -/

/-- `countPairs` is monotone under pointwise implication of predicates. -/
theorem countPairs_mono {f g : ModelResponsePair → Bool}
    (h : ∀ r, f r = true → g r = true) (l : List ModelResponsePair) :
    (l.filter f).length ≤ (l.filter g).length := by
  induction l with
  | nil => simp
  | cons r rest ih =>
      by_cases hf : f r = true
      · have hg : g r = true := h r hf
        rw [List.filter_cons_of_pos hf, List.filter_cons_of_pos hg,
          List.length_cons, List.length_cons]
        have h2 := ih
        omega
      · rw [List.filter_cons_of_neg hf]
        by_cases hg : g r = true
        · rw [List.filter_cons_of_pos hg, List.length_cons]
          have h2 := ih
          omega
        · rw [List.filter_cons_of_neg hg]
          exact ih

/-- The pair count of any predicate is at most `N`. -/
theorem countPairs_le (rs : ResponseSet) (f : ModelResponsePair → Bool) :
    countPairs rs f ≤ rs.N :=
  List.length_filter_le f rs

/-- The answer-slot count of any predicate is at most `2N`. -/
theorem countAnswers_le (rs : ResponseSet) (g : ModelAnswer → Bool) :
    countAnswers rs g ≤ rs.nAnswers := by
  unfold countAnswers ResponseSet.nAnswers
  have h1 := List.length_filter_le (fun r => g r.originalAnswer) rs
  have h2 := List.length_filter_le (fun r => g r.perturbedAnswer) rs
  omega

/-- Strict responsiveness implies correctness on the original — so the
conditional responsiveness numerator is a true part of its denominator
(review follow-up). -/
theorem ResponseSet.strictNum_le_originalCorrectNum (rs : ResponseSet) :
    rs.strictNum ≤ rs.originalCorrectNum := by
  unfold ResponseSet.strictNum ResponseSet.originalCorrectNum
  apply countPairs_mono
  intro r h
  simp only [ModelResponsePair.strictlyResponsive, Bool.and_eq_true] at h
  exact h.1

/-- Per-metric bounds: each numerator fits its denominator, so every
`Rate` in this module is a genuine frequency. -/
theorem ResponseSet.coverageNum_le (rs : ResponseSet) :
    rs.coverageNum ≤ rs.nAnswers := countAnswers_le rs ModelAnswer.decisive

theorem ResponseSet.abstainNum_le (rs : ResponseSet) :
    rs.abstainNum ≤ rs.nAnswers := countAnswers_le rs ModelAnswer.isAbstain

theorem ResponseSet.refusalNum_le (rs : ResponseSet) :
    rs.refusalNum ≤ rs.nAnswers := countAnswers_le rs ModelAnswer.isRefusal

theorem ResponseSet.unresolvableNum_le (rs : ResponseSet) :
    rs.unresolvableNum ≤ rs.nAnswers :=
  countAnswers_le rs ModelAnswer.isUnresolvable

theorem ResponseSet.bothDecisiveNum_le (rs : ResponseSet) :
    rs.bothDecisiveNum ≤ rs.N :=
  countPairs_le rs (fun r => r.originalAnswer.decisive && r.perturbedAnswer.decisive)

theorem ResponseSet.originalCorrectNum_le (rs : ResponseSet) :
    rs.originalCorrectNum ≤ rs.N := countPairs_le rs ModelResponsePair.originalCorrect

theorem ResponseSet.incidentalNum_le (rs : ResponseSet) :
    rs.incidentalNum ≤ rs.N := countPairs_le rs ModelResponsePair.incidentallyCorrect

theorem ResponseSet.bothCorrectNum_le (rs : ResponseSet) :
    rs.bothCorrectNum ≤ rs.N :=
  countPairs_le rs (fun r => r.originalCorrect && r.perturbedCorrect)

/-- Pointwise answer equality (the five constructor pairs). -/
def ModelAnswer.sameAnswer (a b : ModelAnswer) : Bool :=
  match a, b with
  | .yes, .yes => true | .no, .no => true | .abstain, .abstain => true
  | .refusal, .refusal => true | .unresolvable, .unresolvable => true
  | _, _ => false

/-- **Stickiness numerator** (a key counterfactual failure mode): the
model was correct on the original and then REPEATED the very same
answer after the perturbation — ignoring the input change rather than
moving to abstain/refusal. A separate counter from `incidentalNum`
(wrong/non-decisive on original, correct after) and from the
non-decisive perturbed answers; all three failure modes were previously
folded into the same region of the contingency table. -/
def ResponseSet.stickyNum (rs : ResponseSet) : Nat :=
  countPairs rs (fun r => r.originalCorrect
    && ModelAnswer.sameAnswer r.perturbedAnswer r.originalAnswer)

/-- Stickiness is a part of original-correctness. -/
theorem ResponseSet.stickyNum_le_originalCorrectNum (rs : ResponseSet) :
    rs.stickyNum ≤ rs.originalCorrectNum := by
  unfold ResponseSet.stickyNum ResponseSet.originalCorrectNum
  apply countPairs_mono
  intro r h
  simp only [Bool.and_eq_true] at h
  exact h.1

/-- Multiplying each of four counts summing to `D` by `D³` (the product
of the other three denominators) makes the four fractions share the
common denominator `D⁴ = D · D³`, and the numerators sum to `D · D³`.
The arithmetic core of the Rate-level category identity. -/
theorem four_rate_sum_aux (c a r u D : Nat) (h : c + a + r + u = D) :
    c * (D * D * D) + a * (D * D * D) + r * (D * D * D) + u * (D * D * D)
      = D * (D * D * D) := by
  have h1 : (c + a + r + u) * (D * D * D)
      = c * (D * D * D) + a * (D * D * D) + r * (D * D * D) + u * (D * D * D) := by
    rw [Nat.add_mul, Nat.add_mul, Nat.add_mul]
  have h2 : D * (D * D * D) = (c + a + r + u) * (D * D * D) :=
    congrArg (fun x => x * (D * D * D)) h.symm
  rw [h2, h1]

/-- **The category identity at the `Rate` level**: the four category
rates (coverage, abstain, refusal, unresolvable), put over the common
denominator `D⁴ = D · D³` (each term being `count · D³`, where
`D = nAnswers`), satisfy the identity whose counter-level form is
`disjoint_total`. This is an equality AFTER clearing denominators —
for an empty set both sides are zero, which is NOT the statement that
four undefined rates sum to 1. This is the promised Rate-level
counterpart of `disjoint_total`. -/
theorem category_rates_sum_eq_one (rs : ResponseSet) :
    rs.coverage.num * (rs.abstainRate.den * rs.refusalRate.den * rs.unresolvableRate.den)
      + rs.abstainRate.num * (rs.coverage.den * rs.refusalRate.den * rs.unresolvableRate.den)
      + rs.refusalRate.num * (rs.coverage.den * rs.abstainRate.den * rs.unresolvableRate.den)
      + rs.unresolvableRate.num * (rs.coverage.den * rs.abstainRate.den * rs.refusalRate.den)
      = rs.coverage.den * (rs.abstainRate.den * rs.refusalRate.den * rs.unresolvableRate.den) := by
  have hDc : rs.coverage.den = rs.nAnswers := rfl
  have hDa : rs.abstainRate.den = rs.nAnswers := rfl
  have hDr : rs.refusalRate.den = rs.nAnswers := rfl
  have hDu : rs.unresolvableRate.den = rs.nAnswers := rfl
  have hNc : rs.coverage.num = rs.coverageNum := rfl
  have hNa : rs.abstainRate.num = rs.abstainNum := rfl
  have hNr : rs.refusalRate.num = rs.refusalNum := rfl
  have hNu : rs.unresolvableRate.num = rs.unresolvableNum := rfl
  rw [hDc, hDa, hDr, hDu, hNc, hNa, hNr, hNu]
  exact four_rate_sum_aux _ _ _ _ _ (disjoint_total rs)

/-- **Merging two rates**: given `a.num ≤ a.den` and `b.num ≤ b.den`,
the pooled rate `(a.num * b.den + b.num * a.den) / (2 * a.den * b.den)`
is again a genuine frequency. This is the arithmetic fact behind the
averaging step of `balancedPairSuccess` and
`balancedPerturbedAccuracy`. -/
theorem rateMerge_bound (a b : Rate) (ha : a.num ≤ a.den) (hb : b.num ≤ b.den) :
    (Rate.mk (a.num * b.den + b.num * a.den) (2 * a.den * b.den)).num
      ≤ (Rate.mk (a.num * b.den + b.num * a.den) (2 * a.den * b.den)).den := by
  have h1 : a.num * b.den ≤ a.den * b.den := Nat.mul_le_mul_right b.den ha
  have h2 : b.num * a.den ≤ b.den * a.den := Nat.mul_le_mul_right a.den hb
  have h3 : b.den * a.den = a.den * b.den := Nat.mul_comm _ _
  calc a.num * b.den + b.num * a.den
      ≤ a.den * b.den + a.den * b.den := Nat.add_le_add h1 (by
          calc b.num * a.den ≤ b.den * a.den := h2
            _ = a.den * b.den := h3)
    _ = 2 * a.den * b.den := by
        rw [Nat.mul_assoc, Nat.two_mul]

/-- Per-class bound in the exact shape the balanced metrics need: the
class counter fits the class size, for either filtered list. -/
theorem classCount_le (l : List ModelResponsePair) (f : ModelResponsePair → Bool) :
    (Rate.mk (countPairs l f) l.length).num
      ≤ (Rate.mk (countPairs l f) l.length).den :=
  countPairs_le l f

/-- **The range of `balancedPairSuccess`**: whenever
`balancedPairSuccess rs = some r`, the pooled rate `r` satisfies
`r.num ≤ r.den` — derived from the per-class bounds of the two filtered
lists. -/
theorem ResponseSet.balancedPairSuccess_num_le_den (rs : ResponseSet) :
    ∀ r : Rate, ResponseSet.balancedPairSuccess rs = some r → r.num ≤ r.den := by
  intro r hr
  simp only [ResponseSet.balancedPairSuccess] at hr
  by_cases h1 : (rs.filter (fun r => match r.originalGT with | .yes => true | .no => false)).length = 0
  · rw [ite_eq_left h1] at hr
    simp at hr
  · rw [ite_eq_right h1] at hr
    by_cases h2 : (rs.filter (fun r => match r.originalGT with | .no => true | .yes => false)).length = 0
    · rw [ite_eq_left h2] at hr
      simp at hr
    · rw [ite_eq_right h2] at hr
      injection hr with hEq
      subst hEq
      exact rateMerge_bound
        (Rate.mk (countPairs (rs.filter (fun r => match r.originalGT with | .yes => true | .no => false)) (fun r => r.originalCorrect && r.perturbedCorrect)) (rs.filter (fun r => match r.originalGT with | .yes => true | .no => false)).length)
        (Rate.mk (countPairs (rs.filter (fun r => match r.originalGT with | .no => true | .yes => false)) (fun r => r.originalCorrect && r.perturbedCorrect)) (rs.filter (fun r => match r.originalGT with | .no => true | .yes => false)).length)
        (classCount_le _ _) (classCount_le _ _)

/-- **The range of `balancedPerturbedAccuracy`**: same pooling argument,
over the `perturbedGT` classes with the `perturbedCorrect` counter. -/
theorem ResponseSet.balancedPerturbedAccuracy_num_le_den (rs : ResponseSet) :
    ∀ r : Rate, ResponseSet.balancedPerturbedAccuracy rs = some r → r.num ≤ r.den := by
  intro r hr
  simp only [ResponseSet.balancedPerturbedAccuracy] at hr
  by_cases h1 : (rs.filter (fun r => match r.perturbedGT with | .yes => true | .no => false)).length = 0
  · rw [ite_eq_left h1] at hr
    simp at hr
  · rw [ite_eq_right h1] at hr
    by_cases h2 : (rs.filter (fun r => match r.perturbedGT with | .no => true | .yes => false)).length = 0
    · rw [ite_eq_left h2] at hr
      simp at hr
    · rw [ite_eq_right h2] at hr
      injection hr with hEq
      subst hEq
      exact rateMerge_bound
        (Rate.mk (countPairs (rs.filter (fun r => match r.perturbedGT with | .yes => true | .no => false)) (fun r => r.perturbedCorrect)) (rs.filter (fun r => match r.perturbedGT with | .yes => true | .no => false)).length)
        (Rate.mk (countPairs (rs.filter (fun r => match r.perturbedGT with | .no => true | .yes => false)) (fun r => r.perturbedCorrect)) (rs.filter (fun r => match r.perturbedGT with | .no => true | .yes => false)).length)
        (classCount_le _ _) (classCount_le _ _)

/-- The perturbed-correct counter is a true part of `N`. -/
theorem ResponseSet.perturbedCorrectCount_le (rs : ResponseSet) :
    countPairs rs ModelResponsePair.perturbedCorrect ≤ rs.N :=
  countPairs_le rs ModelResponsePair.perturbedCorrect

end Sejmbench
