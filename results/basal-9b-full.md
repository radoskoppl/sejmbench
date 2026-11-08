# 9B — full-corpus evaluation of basal-omni-1.0-ultra (2026-11-06)

Main deliverable of v0.5 (issue #9). Configuration identical to 9A, frozen
before launch; nothing was tuned on eval data between 9A and 9B.

## Headline (layer 0.1, winner task)

| model | winner accuracy | 95% CI | n |
|---|---|---|---|
| majority-class (full-corpus modal) | 0.611 | — | 66,104 |
| random (seed 20261027) | 0.498 | — | 66,104 |
| **basal-omni-1.0-ultra (local)** | **0.9796** | **[0.9785, 0.9807]** | 66,104 |

Layer 0.2: **unsupported by typed API** — `answer_coverage` 100%,
`tracks_answer_coverage` 0%; all items carry the explicit `tracks_abstained`
marker (owner decision 2026-11-04). No MAE is attributed; the model is not
ranked on layer 0.2.

## Per-term accuracy

| term | n | accuracy |
|---|---|---|
| 3 | 11,789 | 0.9516 |
| 4 | 13,535 | 0.9851 |
| 5 | 3,412 | 0.9763 |
| 6 | 8,403 | 0.9902 |
| 7 | 6,291 | 0.9928 |
| 8 | 8,154 | 0.9967 |
| 9 | 9,383 | 0.9913 |
| 10 | 5,137 | 0.9492 |

Term-10 reproduces the 9A number exactly (0.9492) — deterministic server, same
config. The two weakest terms are 3 (oldest data, NO_VOTE era) and 10 (most
polarized / most contested agenda).

## Tie segment (pre-registered analysis)

GT ties (`gt_tie=true`, eligible only): **n=37, accuracy 0.405**. Ties per
term: 3:9, 4:12, 5:4, 6:2, 7:5, 9:4, 10:1. The model never chose the tie
option (`remis` count = 0 across all 66,104 items) — it resolves every
division as za/przeciw, so ties are essentially coin flips for it. This is
the one systematic weakness visible in the run; it is an adapter/prompt
observation, not a scoring artifact (the scorer applies the tie convention to
GT, and the adapter does not convert `remis`).

## Operational evidence

- 66,104/66,104 items, 0 errors, 0 missing, 0 abstentions, elapsed 164,482 s (~45.7 h)
- input tokens P50 2,942 / P95 3,166 / P99 3,322 / max 5,949 — no truncation risk
- 0 context overflow; all items single-attempt (retry policy held)
- distribution: za 25,046 / przeciw 41,058 (modal "przeciw" aligns with the corpus's p_yes≈0.39)

## Run contract (frozen)

population `0b814f62…` (66,104 eligible) · GT stream sha `bdc320ba…` · prompt
corpus variant `e165643d…` · identity HF revision `3c1e540f…`, bf16, basal
2.5.2 systemone, gb10-a034, context 262144, temp 0 · retry policy: single
attempt, transport-only retries ≤3× same request · scoring harness 0.5.0 /
metric 0.3 / schema 1.2 at run time; scorecard rebuilt under harness 0.6.0 /
schema 1.3 with the temporal-holdout block (issue #5).

## Artifacts

- `results/basal-9b-full.scorecard.json` (61.4 MB) — **hosted on HF**: https://huggingface.co/datasets/patrykorwat/sejmbench-results/blob/main/scorecards/basal-9b-full.scorecard.json, sha256 `e02eb34c…` (schema 1.4 rebuild with the `temporal_split` and `margin_buckets` blocks incl. `margin_macro_ci95` (joint cluster resampling); harness 0.8.0, cluster bootstrap by sitting); `scripts/fetch_scorecards.py` pulls it so `rescore-check` covers it end-to-end from the committed raw tar
- `results/basal-9b-full.raw.tar.gz` — per-item raw responses, sha256 `bdcc7d2e…`
- runner: `scripts/run_term10_eval.py --ids docs/population/ids-full-corpus.txt`

## Error structure (added 2026-11-06)

The headline is real, but the error structure is what makes it interpretable.
All numbers below are recomputed from `basal-9b-full.scorecard.json` joined
with the frozen GT stream (`gt-full.jsonl.gz`, `metric.seed_rule`).

### Errors by margin

| margin | n | accuracy | errors |
|---|---|---|---|
| tie | 37 | 40.5% | 22 |
| 1–5 | 359 | 64.1% | 129 |
| 6–20 | 3,355 | 87.6% | 415 |
| 21–50 | 10,299 | 93.2% | 697 |
| 51–100 | 8,543 | 99.0% | 87 |
| **100+** | **43,511** | **100.00%** | **0** |

Two facts define the interpretation:
- **66% of the corpus (margin 100+) has zero errors.** Layer 0.1 with the full
  vote record is, in practice, a counting-reliability test — a for-loop scores
  ~100% there.
- **93.6% of all errors sit at margin ≤50**, and at margin 1–5 accuracy is
  64.1% — barely above a coin flip. That is the discriminating surface of the
  benchmark, not the 97.96% aggregate.

### Errors by term × width

| term | close (≤50, excl ties) | wide (51+) |
|---|---|---|
| 3 | 67.4% (n=1,613) | 99.6% |
| 4 | 77.0% (n=805) | 99.9% |
| 5 | 87.4% (n=523) | 99.5% |
| 6 | 94.4% (n=1,431) | 100.0% |
| 7 | 95.1% (n=844) | 99.9% |
| 8 | 98.7% (n=2,047) | 100.0% |
| 9 | 98.5% (n=5,271) | 100.0% |
| 10 | 84.0% (n=1,479) | 99.3% |

Wide divisions are solved in every era; all per-term variation lives in close
divisions. Notably, terms 8 and 10 have nearly identical margin profiles
(median close margin 40 vs 42, p25–p75 31–46 vs 36–46) yet 98.7% vs 84.0%
accuracy — closeness alone does not explain the gap. Term 9 is tighter
(median 23) and still 98.5%, with zero errors on 3,219 divisions at margin
21–50.

### What does NOT explain close-division errors

- **List length** — 450+ active records: 98.3%; 200–399: 76.9% (the inverse of
  the intuitive "long list is harder").
- **Attendance per se** — low-attendance close divisions are concentrated in
  early terms (91% of n_active<400 close divisions are terms 3–6); after term
  decomposition the wide tier is solved everywhere.
- **Non-deciding record share** — 13,970 of 14,013 close divisions have ≤10%
  ABSENT/ABSTAIN/NO_VOTE share (computed from `seed_totals`; club-level
  `inni_totals` only covers sub-threshold clubs and is unsuitable for share
  metrics).

### Direction, ties, calibration

- Confusion: false "no" (pred=no, GT=yes) **1,012** vs false "yes" **338** — a
  3:1 asymmetry. Predicted "yes" share 37.9% vs GT 38.9% (good base-rate
  calibration); the asymmetry is a "no" lean under uncertainty, consistent
  with the corpus modal winner being "no".
- **The model never answered "remis"** in 66,104 responses. On the 37 ties it
  said "no" 22 times (all scored incorrect under the tie convention) and
  "yes" 15 times → 40.5%, reported as abstention-affected coverage, not MAE.

### Open hypotheses (explicitly unverified)

- **Term 3**: NO_VOTE-era record formats; era-specific, not memory (the oldest
  data is also the most likely to be pre-trained on, yet it is the weakest).
- **Term 9 anomalously strong on close divisions** (median margin 23, 98.5%;
  0 errors on 3,219 divisions at margin 21–50) — pattern consistent with
  pre-training memory (2019–2023 data), which helps exactly where pure
  counting is hardest.
- **Term 10** (2023–2026, likely post-cutoff): pure counting without memory on
  the most contested votes. If this holds, per-term close accuracy is a
  natural contamination canary — and `declared_cutoff: unknown` should be
  replaced by a real cutoff + the temporal split from issue #5.

### Consequences

1. **Cross-model comparisons must be margin-conditioned.** Proposal
   (pre-registered, additive to the harness): report winner accuracy for
   wide ≥51 / close ≤50 / narrow ≤5 / tie, with baselines computed on the same
   subsets. Comparing aggregates ranks calculators, not models.
2. The close subset (≤50, n≈14k) plus ties is the natural test bed for the
   second model.
3. The t9-vs-t10 pattern strengthens the case for issue #5 (temporal split).

## Temporal holdout (issue #5, cutoff 2026-01-01)

The frozen split (CODEBOOK §9) applied to the full corpus; post-cutoff =
2026 sittings, n=1,917 — the identical subset to 9A's post-cutoff set, hence
the identical post-cutoff numbers.

| subset | n | winner acc | 95% CI |
|---|---|---|---|
| pre-cutoff (≤2025) | 64,187 | 0.9808 | [0.9797, 0.9818] |
| post-cutoff (2026) | 1,917 | 0.9384 | [0.9275, 0.9489] |

**Reading this correctly (correction 2026-11-06):** the −4.2 pp gap is NOT
a clean temporal effect — the pre-cutoff set is dominated by terms 3–9
(60,967 of 64,187 divisions, aggregate 98.21%), so it largely restates the
term-composition difference already visible in the per-term table. The
comparison that holds the term fixed is within term 10: 0.9556 pre-2026
(n=3,220) vs 0.9384 post-2026 (n=1,917) — a −1.72 pp gap. Even that does
not isolate contamination: sitting-year differences in margin mix, vote
types and agenda difficulty can produce the same shift (a cheap robustness
check — the same split at placebo cutoffs 2025-01-01/2024-01-01, where a
pure-composition explanation predicts no matching discontinuity — is queued
with the margin-conditioned reporting work). `declared_cutoff` stays
`unknown` (unverifiable); the split is the contamination control
(issue #5), not proof of innocence.

## Next

Second model on this exact frozen set + contract → first real cross-model
leaderboard row pair, reported margin-conditioned (wide ≥51 / close ≤50 /
narrow ≤5 / tie). No new benchmark work before that.
