# m3 — basal-omni-2.0-mini-preview, term-10 checkpoint (2026-11-16)

**Verdict: checkpoint fails — do NOT start a full-corpus run.** Accuracy 0.648 sits far below
both same-contract references (9A 0.949, 9c term10 0.851 under v0.4 GT).

**Setup.** `Remek/basal-omni-2.0-mini-preview`, **pinned revision `2c8a5783…`** (lastModified
2026-11-14; base `google/gemma-4-E4B-it`, 4B), served by basal 2.8.1 `--mode fast`, bf16, GB10,
temperature 0, single attempt. 5,137 term-10 divisions (`ids-term10.txt`, sha `a632c12c…`),
`--shuffle 1234`, 10,711 s (~3.0 h), 0 errors. Two-way caps (`max_prompt 4096`) were never hit:
max input 3,560 tokens, 0 context-overflow events — the failure is not truncation.

## Headline (layer 0.1, v0.4 GT, abstain=incorrect)

| model | acc | CI95 | n |
|---|---|---|---|
| basal-omni-1.0-ultra (9A) | 0.9492 | [0.9432, 0.9550] | 5,137 |
| basal-omni-1.0-ultra v0.4 (9c, term10 subset) | 0.851 | — | 5,137 |
| **basal-omni-2.0-mini-preview (m3)** | **0.6482** | **[0.5983, 0.6892]** (cluster bootstrap, sittings, seed 20261027) | 5,137 |

Error overlap (McNemar): vs 9A 233 m3-only-correct vs 1,771 9A-only (χ²=1179); vs 9c 26 vs
1,069 (χ²=992). m3 is not merely weaker — it disagrees structurally with both references.

## Behaviour

- **Selections: zero.** The model never once chose `nie_do_okreslenia` (0/5,137) — the
  uncertainty option is unused, unlike 2.0-max (5,161 selections corpus-wide).
- **Extreme ZA bias**: predicts ZA on 82.2% of divisions vs 48.1% ground-truth ZA.
- **ECE conditional 0.286** (8-band convention). Band table:

| band | n | acc | mean conf |
|---|---|---|---|
| [0.00,0.50) | 20 | 0.800 | 0.480 |
| [0.50,0.60) | 87 | 0.621 | 0.548 |
| [0.60,0.70) | 102 | 0.775 | 0.658 |
| [0.70,0.80) | 141 | 0.844 | 0.756 |
| [0.80,0.90) | 667 | 0.688 | 0.869 |
| [0.90,0.95) | 2,140 | **0.396** | 0.929 |
| [0.95,0.99) | 1,832 | 0.878 | 0.969 |
| [0.99,1.00) | 148 | 1.000 | 0.991 |

The 0.90-0.95 band (42% of all items) carries accuracy 0.396 at stated confidence 0.929.

## Certified-threshold flag for the maintainer

`GET /v1/models` on 2.8.1 fast reports `certified {0.05: {choice 0.5994}}` for this build.
Gating at 0.5994 does not hold the 5% error target on our data: on the fit set (300 items,
out-of-sample for the shipped file) `basal-calibrate` reports 100% automated at 35.3% observed
error at max_error 0.05; on the 203-item holdout, 196/203 = 96.6% of decisions are accepted
with an observed error of 43.9%. Either the 0.05 certification does not transfer to this task
family / build, or the preview weights changed after certification. Worth a line in the issue
alongside the 2.0-max control experiment.

## Throughput

2.09 s/item sequential (vs ~2.5 s ultra) — ~1.2×, not worth the quality loss even if it were
faster.

Artifacts: scorecard `results/m3-preview-term10.scorecard.json`, raw submissions
`results/m3-preview-term10.raw.tar.gz`, server capture `calib/models-omni-mini.json`,
identity `model.identity` in the scorecard (weights pinned to `2c8a5783…`).
