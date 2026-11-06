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
metric 0.3 / schema 1.2.

## Artifacts

- `results/basal-9b-full.scorecard.json` — sha256 `288de03e…`
- `results/basal-9b-full.raw.tar.gz` — per-item raw responses, sha256 `bdcc7d2e…`
- runner: `scripts/run_term10_eval.py --ids docs/population/ids-full-corpus.txt`

## Next

Second model on this exact frozen set + contract → first real cross-model
leaderboard row pair. No new benchmark work before that.
