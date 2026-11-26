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
* Accuracy is pair-level (both answers correct / N); balanced accuracy
  is over the two GT classes and is `none` when a class has no pairs —
  never defaulted.

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

/-- **Accuracy** (pair-level, both answers correct over N). -/
def ResponseSet.accuracy (rs : ResponseSet) : Option Rate :=
  if rs.N = 0 then none else some { num := rs.bothCorrectNum, den := rs.N }

/-- **Balanced accuracy**: the mean of per-class accuracies over the two
GT classes (original-GT side). Classes with no pairs make the metric
`none` — explicitly undefined, never defaulted (review item: "explicitly
define behavior when one class is missing"). -/
def ResponseSet.balancedAccuracy (rs : ResponseSet) : Option Rate :=
  let yesPairs := rs.filter (fun r => match r.originalGT with
    | .yes => true | .no => false)
  let noPairs := rs.filter (fun r => match r.originalGT with
    | .no => true | .yes => false)
  let accYes : Option Rate :=
    if yesPairs.length = 0 then none
    else some (Rate.mk (countPairs yesPairs (fun r => r.originalCorrect))
      yesPairs.length)
  let accNo : Option Rate :=
    if noPairs.length = 0 then none
    else some (Rate.mk (countPairs noPairs (fun r => r.originalCorrect))
      noPairs.length)
  match accYes, accNo with
  | some a, some b => some (Rate.mk (a.num * b.den + b.num * a.den)
      (2 * a.den * b.den))
  | _, _ => none

end Sejmbench
