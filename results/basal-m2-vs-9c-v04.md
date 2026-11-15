# Model 2: basal-2.0-max (11B) vs basal-omni-1.0-ultra (9c) — full corpus, v0.4 contract

Date: 2026-11-15. Population: 66,104 (`ids-full-corpus.txt`). Same frozen v0.4
corpus prompt, same engine (2.6.0), same hardware, same decoding (server
defaults, single attempt) — the only variable is the model.

| | 9c | m2 |
|---|---|---|
| model | basal-omni-1.0-ultra, 31B, bf16 | basal-2.0-max, 11B, bf16 |
| weights | `3c1e540f…` | `45cad99e…` |
| run | 2026-11-12→14, ~46 h | 2026-11-14→15, ~20 h |
| items / errors | 66,104 / 0 | 66,104 / 0 |

## Headline (v0.4 GT)

| model | accuracy | 95% CI |
|---|---|---|
| 9c | **0.9685** | [0.9631, 0.9735] |
| m2 (abstain counted incorrect) | **0.6516** | [0.6282, 0.6733] |
| m2 (answered only, n=60,943) | 0.7068 | — |

Paired per-item: both-right 42,561 (64.4%) · 9c-only 16,301 · m2-only 511 ·
both-wrong 1,570. McNemar χ² = 14,828 — **ultra is not slightly better, it is
the only one of the two that reads roll-call records**.

## Margin buckets (§13)

| bucket | n | m2 | 9c | 9B |
|---|---|---|---|---|
| tie | 43 | 0.000 | 0.000 | 0.000 |
| narrow | 457 | 0.503 | 0.639 | 0.632 |
| close | 13,736 | 0.362 | 0.881 | 0.916 |
| wide | 46,707 | 0.811 | 0.995 | 0.999 |

Landslide divisions — trivially countable — are where m2 fails hardest (19%
error). Per-term: m2 ranges 0.49–0.88; **term 8 at 0.493 is below the
majority-class baseline (0.611)**; term 10 (0.643) is m2's only relative win
over its own average, still −20 pp under ultra.

## Why (diagnostics, not just numbers)

- **Yes-bias**: predicts ZA on ~71% of items (corpus base rate 39%); on wide
  NO divisions it answers yes with confidence ~0.75. Manual recount of three
  such divisions (248:183, 251:169, 272:176 against) confirms the GT — the
  model is wrong, the harness is clean (`input_tokens` ~3.4k: state delivered).
- **Inverted uncertainty**: abstains 9.9% on wide divisions but 0.1% on close
  ones — it abstains where it cannot count, not where the outcome is genuinely
  ambiguous.
- **Unsafe calibration**: ECE 0.101; the 0.70–0.80 confidence band carries
  accuracy 0.541 (over-confident, dangerous direction), vs 9c's benign
  under-confidence (ECE 0.069, accuracy ≥ confidence everywhere).
- Temporal: m2 pre 0.707 / post 0.692 — flat, no contamination-shaped curve.

## Verdict

For roll-call outcome prediction on this corpus, **basal-2.0-max is not a
usable substitute for omni-ultra despite the 2× speed**: −31.7 pp headline,
below-majorile on two terms, abstention and confidence signals inverted. The
speed/quality trade does not exist here; quality collapses first. If a
text-only model is wanted later, it should be tested on this task *before*
committing GPU time to a full run (the checkpoint-sampling protocol we used
here costs ~1/10th of the run to reach this verdict).

Artifacts: `results/basal-m2-v04-full.raw.tar.gz` (repo), full card
`basal-m2-full.scorecard.json` (off-git store), 9c artifacts per
`results/basal-9c-vs-9b-v04.md`. Open confound: v0.3-vs-v0.4 gap (−0.98 pp)
still not attributable to prompt alone (engine 2.5.2 vs 2.6.0); confound-run
deferred.
