# Backtest layers 2/3 — term 10, club affinity + title kNN

- date: 2026-10-25 · operator: agent (Hermes), owner review pending
- data: all 5,201 divisions of term 10 (`divisions.jsonl`, official API,
  sha of yesterday's fetch; regenerate with `scripts/fetch_term_dump.py`)
- protocol: chronological, warmup 60, history strictly < T, no leakage;
  club continuity mapped (Nowa_Lewica→Lewica, PSL→PSL-TD,
  Polska2050→Polska2050-TD; Centrum/RozwojPlus/Konfederacja_KP are splinters,
  kept separate — MP-set overlap verified on raw dump)
- scoring: CODEBOOK v0.2 winner exact match + per-track yes_share MAE

## Results (5,079 scored divisions)

| method | layer | winner acc | yes_share MAE |
|---|---|---|---|
| always_yes | — | 0.477 | — |
| club_mean | base | 0.477 | 0.474 |
| carry_last | base | 0.673 | 0.314 |
| ewma (HL=30) | drift | 0.559 | 0.444 |
| affinity diffusion (λ=1, 2 iters) | 2 | 0.572 | 0.453 |
| **title kNN (k=5, TF-IDF, m=0.1)** | **3** | **0.761** | **0.280** |
| blend affinity+kNN | 2+3 | 0.718 | 0.365 |

Hyperparameter sweep (winner acc / MAE), k = retrieved neighbors,
m = pseudo-count toward prior, weights sim²:

| k \ m | 0.1 | 0.3 | 1.0 | 3.0 |
|---|---|---|---|---|
| 1 | — | — | 0.699/0.349 | — |
| 3 | — | — | 0.749/0.319 | — |
| 5 | 0.761/0.279 | 0.760/0.290 | 0.753/0.315 | 0.722/0.353 |
| 10 | 0.749/0.293 | 0.747/0.300 | 0.745/0.317 | 0.727/0.346 |

Broad plateau — the 0.761 is not a config fluke.

## Reading

1. **Content beats structure.** Title retrieval alone jumps winner accuracy
   0.566→0.761 over the v0.1 bar. Layer 2 (pure co-voting affinity) adds
   almost nothing on top of recency: who votes with whom is already fully
   expressed by *which club* you are, so the graph mostly re-predicts the
   club's own mean. Affinity's real value may be cold-start for new clubs.
2. **Autocorrelation dominates means.** carry_last (previous division) beats
   every long-run mean — legislative business arrives in blocks, so the last
   division leaks today's agenda. This is why kNN-on-titles wins: it finds
   the *right* block, not the last one.
3. **Blend is worse than kNN alone** (0.718 vs 0.761): averaging expected
   counts drags kNN toward the flat structural prior. Dropped as default.
4. Note: our carry_last here (0.673) beats the v0.1 skeleton's (0.566) —
   this implementation scores only clubs actually active today; the skeleton
   summed dissolved/inactive clubs at their mean sizes, diluting the signal.
   The new number supersedes; both are documented.

Bar for future runs: **kNN 0.761 winner acc / 0.280 MAE**.
Next candidates: same-day position features (day-of-sitting index),
retrieval on druk descriptions (not just titles), per-club kNN weights.

Reproduce: `python3 scripts/backtest_layers.py divisions.jsonl`
