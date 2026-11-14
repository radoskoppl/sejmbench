# 9c (Basal v0.4) vs 9B (Basal v0.3) — paired comparison on the frozen corpus

Date: 2026-11-14. Population: 66,104 divisions (`ids-full-corpus.txt`, sha `0b814f62…`).
Both models' **raw responses** were re-scored against the same v0.4 headline GT
(`margin_all` sign), so every number below is apples-to-apples; the 9B card's
original seed-rule scoring is not used anywhere here.

## Setup

| | 9B | 9c |
|---|---|---|
| run dates | 2026-11-06 | 2026-11-12 → 11-14 |
| weights | `3c1e540f…` (basal-omni-1.0-ultra, bf16) | same |
| hardware / mode | gb10-a034, `fast`, temp 0, single attempt | same |
| engine | basal 2.5.2 | basal 2.6.0 |
| prompt | corpus **v0.3** (`75dca1f1…`) | corpus **v0.4** (`c84e3bb3…`) |

Confound to state: the engine version differs (2.5.2 vs 2.6.0). The two runs
cannot attribute the gap to the prompt alone.

## Headline (both under v0.4 GT)

| model | accuracy | 95% CI (cluster bootstrap, sitting) |
|---|---|---|
| 9c (v0.4 prompt) | **0.9685** | [0.9631, 0.9735] |
| 9B (v0.3 prompt) | **0.9783** | — (paired below) |

Paired per-item: both-right 63,426 (95.95%) · 9c-only right 597 · 9B-only right
1,245 · both-wrong 836. McNemar χ² = 227.3 (df 1, p ≪ 0.001) — **v0.4 is
significantly worse by −0.98 pp**. Failure overlap: 58.3% of 9c's failures are
shared with 9B.

Temporal split (CODEBOOK §9 rule 6, cutoff 2026-01-01):

| stratum | n | 9c | 9B |
|---|---|---|---|
| pre | 64,187 | 0.9713 | 0.9795 |
| post | 1,917 | 0.8748 | 0.9379 |

## Margin buckets (frozen CODEBOOK §13)

| bucket | n | 9c | 9B | Δ |
|---|---|---|---|---|
| tie (m = 0) | 43 | 0.0000 | 0.0000 | 0 |
| narrow (1–5) | 461 | 0.6421 | 0.6356 | +0.6 pp |
| close (6–50) | 13,745 | 0.8805 | 0.9163 | **−3.6 pp** |
| wide (≥51) | 51,855 | 0.9955 | 0.9986 | −0.3 pp |

The whole deficit sits in the **close band** and in the temporal post-stratum.
Narrow is a statistical dead heat. Ties: **neither model ever predicts `tie`**
(0 predicted ties against 43 GT headline ties) — the `remis` criterion in the
v0.4 prompt is never selected; tie precision/recall pools are empty and the
scorer now reports them as `null` instead of crashing.

## Calibration (confidence from `model_answer.confidence`, both under v0.4 GT)

| confidence | 9c n | 9c acc | 9B n | 9B acc |
|---|---|---|---|---|
| <0.50 | 42 | 0.476 | 22 | 0.409 |
| 0.50–0.60 | 3,907 | 0.655 | 3,024 | 0.703 |
| 0.60–0.70 | 4,672 | 0.883 | 3,667 | 0.917 |
| 0.70–0.80 | 7,104 | 0.979 | 5,583 | 0.975 |
| 0.80–0.90 | 8,091 | 0.998 | 8,230 | 0.991 |
| 0.90–0.95 | 2,665 | 1.000 | 4,777 | 1.000 |
| 0.95–0.99 | 1,852 | 1.000 | 2,667 | 1.000 |
| ≥0.99 | 37,771 | 1.000 | 38,134 | 1.000 |

ECE: 9c **0.0693**, 9B **0.0644**. Both models are *under*-confident in the
mid bands (accuracy exceeds stated confidence); there is no over-confidence
region. Confidence quality is not what separates the two prompts.

## Per-term

| term | n | 9c | 9B | Δ |
|---|---|---|---|---|
| 3 | 11,789 | 0.9377 | 0.9523 | −1.5 pp |
| 4 | 13,535 | 0.9803 | 0.9806 | ≈0 |
| 5 | 3,412 | 0.9634 | 0.9766 | −1.3 pp |
| 6 | 8,403 | 0.9895 | 0.9896 | ≈0 |
| 7 | 6,291 | 0.9916 | 0.9925 | ≈0 |
| 8 | 8,154 | 0.9990 | 0.9964 | +0.3 pp |
| 9 | 9,383 | 0.9956 | 0.9898 | +0.6 pp |
| 10 | 5,137 | **0.8513** | **0.9476** | **−9.6 pp** |

Term 10 alone accounts for most of the aggregate gap.

## Verdict

1. **v0.4 is not fit to replace v0.3 as the default contract.** −1 pp, significant, concentrated in close divisions and term 10; nothing in calibration compensates.
2. The v0.4 `outcome` reporting still earns its place as an *additive* metric (recognition / side-picking / legacy-convention compliance per issue #17) — score it alongside v0.3, not instead of it.
3. **Tie handling is untrained in both contracts**: 0/43 GT ties predicted, and the narrow/tie regions (~500 items) need a dedicated mechanism (thresholding or escalation), independent of prompt version.
4. Before any decision on v0.4 wording, re-run one arm on the *same engine* (2.6.0) to break the prompt-vs-engine confound.

Artifacts: `results/basal-9c-v04-full.raw.tar.gz` (this repo), full 9c card
`basal-9c-full.scorecard.json` (sha256 `ba1d96fd7b418847…`, 87 MB, kept off-git in
the durable workspace store; HF mirror pending — reproducible from the raw tar + frozen population),
9B raws `results/basal-9b-full.raw.tar.gz`. Scorer fixes this round:
`parse_answer` accepts outcome-only payloads (`87f9280`); empty bootstrap
pools report `null` instead of raising.
