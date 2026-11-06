# 9A — term-10 evaluation of basal-omni-1.0-ultra (2026-11-04)

Smoke/staging run for issue #9. Term-10 is a subset of the full corpus; per the
staged plan this run validates adapter/parser/infrastructure. Configuration was
frozen **before** launch; nothing here was tuned on eval data.

## Headline (layer 0.1, winner task)

| model | winner accuracy | 95% CI | n |
|---|---|---|---|
| majority-class (term-10 modal) | 0.519 | — | 5,137 |
| random (seed 20261027) | 0.489 | — | 5,137 |
| **basal-omni-1.0-ultra (local)** | **0.9492** | **[0.9432, 0.9550]** | 5,137 |

Layer 0.2: `tracks_answer_coverage = 0` — basal's typed decision API cannot emit
per-club numeric estimates; every item carries an explicit `tracks_abstained`
marker (partial-abstain rule, schema 1.2), so MAE is reported as null rather
than penalized. This is a property of the adapter, not of the model's
competence on that task.

## Run contract (frozen)

- population: `docs/population/ids-term10.txt`, 5,137 eligible, ids sha `a632c12c…`; GT stream sha `0f984d52…`
- prompt: corpus variant (`club | vote` lines), hash `e165643d…`
- model identity: HF revision `3c1e540f61fd0e1dfa1dbf7486e037e1cf3e1a24`, bf16,
  basal 2.5.2 systemone, gb10-a034, context 262144, temp 0 (server default)
- retry policy: single attempt per item; transport errors retried ≤3× the same
  request; content never re-rolled
- scoring: harness 0.5.0 / metric 0.3 / schema 1.2 at run time; scorecard rebuilt
  under harness 0.6.0 / schema 1.3 with the temporal-holdout block (issue #5)

## Operational evidence

- 5,137/5,137 items, **0 errors**, elapsed 13,767 s (~3.8 h), 0 context overflow
- input tokens P50 3,070 / P95 3,378 / P99 3,448 / max 3,554 — far below the
  262k context window; no silent truncation possible
- answer distribution: `za` 2,270 / `przeciw` 2,867 / `remis` 0 / abstain 0
  (the model never picked the tie option — ties are rare in term-10, but this
  is worth watching in 9B where the tie pool is larger)
- determinism: scorecard rebuilt twice → byte-identical (`cmp` clean)

## Temporal holdout (issue #5, cutoff 2026-01-01)

The frozen temporal split (CODEBOOK §9) partitions the population by official
sitting date; post-cutoff = divisions from 2026 sittings, all term 10.

| subset | n | winner acc | 95% CI |
|---|---|---|---|
| pre-cutoff (≤2025) | 3,220 | 0.9556 | [0.9484, 0.9627] |
| post-cutoff (2026) | 1,917 | 0.9384 | [0.9275, 0.9489] |

Layer 0.2 is n/a in both subsets (the model's typed API never emits per-club
tracks — partial abstention, coverage 0 by owner decision). A −1.7 pp
post-cutoff gap is consistent with pre-training memory helping on pre-cutoff
data; `declared_cutoff` stays `unknown` (unverifiable), so the split is a
control, not proof of innocence.

## Artifacts

- `results/basal-9a-term10.scorecard.json` — sha256 `0ee22bda…` (schema 1.3 rebuild with the `temporal_split` block)
- `results/basal-9a-term10.raw.tar.gz` — per-item raw responses, sha256 `c2818c3c…`
  (contains `input_tokens`, `inference_attempts`, model choice + confidence)
- runner: `scripts/run_term10_eval.py` (resumable; rerun skips completed items)

## Next (9B)

Full-corpus run (66,104 items) requires: no prompt/param changes after 9A,
tie-pool sanity check, and owner sign-off on the layer-0.2 abstention treatment.
