# Calibration control experiment — basal-2.0-max, 2026-11-15

**Setup.** Same 203-item holdout (stratified 503-item set, seed 20261027, split whole-sittings:
300 fit / 203 holdout, 308 sittings). Engine 2.8.1 (`release_date 2026-11-15`, revision
`4a48f84e…`, model_files `ece70feeff45b8d4`), mode fast, bf16, GB10, temperature 0, prompt v0.4
(`c84e3bb3…`). Server reported `certified: {"0.05": {"choice": 0.9343, "noul": 0.8903}}`.

## Arms

| arm | config | n | answered | acc (abstain=incorrect) | acc (determinate) | ECE cond | ECE uncond |
|---|---|---|---|---|---|---|---|
| A | shipped calibration | 203 | 193 (95.1%) | 0.547 | 0.575 | 0.207 | 0.222 |
| B | shipped + `max_error: 0.05` on choice | 203 | 193 | 0.547 | 0.575 | 0.207 | 0.222 |
| C | fitted (`basal-calibrate` on fit-300) | 203 | 193 (95.1%) | 0.542 | 0.570 | 0.107 | 0.093 |
| ref | m2 full-corpus run, same 203 items | 203 | 193 | 0.542 | 0.570 | 0.218 | — |

Arm B ≡ arm A: `max_error` is accepted in a `choice` question payload but has no effect
(0 deferred; 187 answered items below the certified 0.9343 threshold). Per API.md `max_error`
defers only for `act`/`tool`; for `choice` the gating must happen in application code against
the certified threshold.

## Client-side threshold simulation (arm A probabilities, certified 0.05 → conf ≥ 0.9343)

accepted 6/203 = 3.0%, accuracy of accepted 100% (0 wrong), deferred 97.0%.
Per bucket (accepted share): wide_yes 14.6%, wide_no 0%, close 0%, narrow 0%, tie 0%.
ECE on the accepted set: 0.053.

Interpretation: the shipped certified threshold is *valid* (100% accuracy on the accepted set,
consistent with a 5% error target) but automates only 3% of decisions on this task family —
it is conservative, not wrong. The mid-band overconfidence lives entirely in the deferred tail.

## Arm A band table (conditional, answered-only, 8 fixed bands)

| band | n | acc | mean conf |
|---|---|---|---|
| [0.00,0.50) | 16 | 0.312 | 0.451 |
| [0.50,0.60) | 21 | 0.667 | 0.555 |
| [0.60,0.70) | 20 | 0.600 | 0.661 |
| [0.70,0.80) | 40 | 0.375 | 0.755 |
| [0.80,0.90) | 84 | 0.631 | 0.847 |
| [0.90,0.95) | 10 | 1.000 | 0.923 |
| [0.95,0.99) | 2 | 1.000 | 0.955 |
| [0.99,1.00) | 0 | — | — |

Abstain shares by bucket (model-selected `nie_do_okreslenia`): wide_yes 0/41, wide_no 10/61
(16.4%), close 0/60, narrow 0/28, tie 0/13 — the inverted-selection pattern reproduces on the
stratified subset, concentrated on wide-margin NO-won divisions.

## Arm C — fitted calibration

`basal-calibrate` on labelled-fit.jsonl (300 items, 232 FIT / 68 CERT decisions, 136 groups;
sha `ab14e0fc…`; holdout sha `cfff12d8…`). Fitted choice temperature 1.354 → 2.997
(bucket 2-10: 1.634 → 2.997). On the fit set itself ECE shipped → fitted = 0.203 → 0.135;
on the untouched holdout (this table) 0.207 → 0.107 conditional / 0.222 → 0.093 unconditional.
The fitted file certifies **no** threshold at max_error 0.05 for choice (the first tested level,
confidence 0.5904, carries 43 errors against a 0.553 bound — with only 136 independent groups
the certification stops there), so serving it defers every automatic act/tool decision; for
plain `choice` answers it only re-temperatures the probabilities.

Band table (conditional): confidence collapses into 0.43-0.74 — [0,0.5) n=56 acc 0.554,
[0.5,0.6) n=61 acc 0.410, [0.6,0.7) n=68 acc 0.676, [0.7,0.8) n=8 acc 1.000. Nothing above 0.74.
Accuracy is unchanged (0.542 vs 0.547) and the model-selected `nie_do_okreslenia` abstentions are
identical (same 10 items, all wide-margin NO-won).

## Mini-preview addendum (2026-11-16)

The same two arms were run for `basal-omni-2.0-mini-preview` (pinned rev `2c8a5783…`) on the
identical holdout: shipped ECE conditional **0.347** → fitted **0.0987** (temperature fit again
collapses confidences under 0.73; accuracy unchanged at 0.5665, zero selections in both arms).
The shipped file, "as served", automates 100% of decisions at 35.3% error at max_error 0.05 —
the certified 0.5994 threshold is not merely conservative or loose, it is wrong for this task
family. So for mini too, the probability layer is a calibration problem (fit fixes ECE to the
2.0-max fitted level, 0.099 ≈ 0.107); the decision layer (accuracy 0.567 on the stratified
subset, ZA bias) is not touched by refitting.

Artifacts: `results/calib-A-mini-shipped/`, `results/calib-C-mini-fitted/` (ATX),
`calib/models-omni-mini-fitted.json`.

## Verdict

Per the pre-registered criterion: ECE(fitted) ≪ ECE(shipped) on the holdout (0.107 vs 0.207
conditional; the mid-band overconfidence disappears — no band above 0.74 carries invented
accuracy). For the probability layer, calibration/config mismatch dominates, not model
capability: a task-fitted temperature halves ECE without touching the model. What refitting
does NOT fix is the decision layer: accuracy, the ZA bias and the inverted
`nie_do_okreslenia` selections are bit-identical across arms A and C (10/10 same items) —
those remain a model/readout question. Secondary findings: `max_error` on a `choice` question
is accepted by 2.8.1 but silently ignored (deferred: 0, 187 answered items below the certified
0.9343); and 300 items in 136 sitting-groups is too few to certify a 0.05 threshold — group
structure, not item count, binds (`--keep-shipped choice` keeps shipped thresholds together).

Artifacts: `calib/labelled-{fit,holdout}.jsonl`, `docs/population/ids-calib-{500,holdout}.txt`,
`results/calib-A-shipped/`, `results/calib-B-maxerr/`, `results/calib-C-fitted/` (ATX),
`calib/models-281.json` (server `/v1/models` capture).
