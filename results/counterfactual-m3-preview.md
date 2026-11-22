# Counterfactual input-reliance spike — basal-omni-2.0-mini-preview (issue #15)

**Status: spike executed, metrics reported. Separate track — never merged into
accuracy scorecards or the leaderboard (issue #15 caution; DATA_LICENSE.md,
"Synthetic derived data").**

**Model / arms.** `Remek/basal-omni-2.0-mini-preview`, pinned revision
`2c8a5783…`, served by basal 2.8.1 `--mode fast`, bf16, GB10 (.18), temperature 0,
single attempt — the same serve configuration as the committed arm A
(`results/m3-preview-term10`, 5,137 per-item answers, zero additional GPU).
Arm B (perturbed) = 208 synthetic items (`cf/divisions_cf.jsonl` on HF,
`585d22a5…`; manifest `7226d8fe…`), 208/208 answered, 0 errors, 417 s.
Both arms answered the SAME items with the SAME frozen v0.4 prompt contract;
only the records differ. Verdicts matched per item_id (`cf-verdicts.jsonl`).

**Result (2026-11-22, cf-report.md @ ATX `~/cf-dump`, sha `71897503…`).**

| perturbation | n | follows PERTURBED GT | matches ORIGINAL outcome | unchanged vs original run |
|---|---|---|---|---|
| **flip** (winner reversed, k=⌊margin/2⌋+1) | 108 | **68/108 (0.630)** † | **40/108 (0.370)** † | — |
| **reorder** (records permuted) | 50 | — | — | **49/50 (0.980)** |
| **club-label pseudonymization** | 50 | — | — | **50/50 (1.000)** |

## Reading

- **† The flip metric is confounded with the model's ZA-bias.** Arm B answered
  `za` on **108/108 flipped tallies** (arm A on the same items: 104 yes / 4 no).
  "Follows perturbed GT 0.630" is therefore exactly the share of flip items
  whose perturbed GT is `yes` (68/108 — i.e. original GT `no`), and "matches
  original 0.370" is exactly the share whose original GT is `yes`. The model's
  answer was **invariant to the perturbation**: it does not compute from the
  provided votes on flip items — under a contradictory tally it defaults to ZA,
  consistent with its documented 82.2% yes-rate on the committed full run.
- On unperturbed tallies (reorder + pseudonymize arms, GT unchanged) arm B
  reproduces arm A 99/100 (49/50, 50/50) and answers `no` 23× — the model does
  produce `no` when the tally reads `no`; the uniform-yes behaviour is specific
  to the flipped (contradictory) inputs.
- The earlier "echo of the remembered outcome" reading is retracted: it is not
  distinguishable from the constant-yes policy (the echo set coincides with
  original-GT-yes items for that trivial reason), and the 4 items where arm A
  itself answered `no` (correctly) also got `za` from arm B — recall of arm A's
  answers does not explain them, uniform-yes does.
- Order and club-label pseudonymization do not move the answer (0.98/1.00
  stability) — no dependence on label names or record layout.
- All 108 flip items are term 10 — by construction (arm A is the term-10
  checkpoint), not by data choice. The `flip_narrow` stratum is
  under-sampled for the same reason (18/60 shortfalls, insufficient
  eligible population); conclusions are for narrow/close/wide pooled, not
  per-stratum. Original-GT composition of the flip pool: 68 `no` / 40 `yes`
  (drives both flip rates — see †).
- Perturbed-GT balance in the flip arm: 68 yes / 40 no — the perturbation is
  not a constant signal (`scripts/cf_leakage_check.py`, report-only).
- **Net for issue #15**: input-reliance is not measurable for this model with
  the flip design as built (one outcome question, yes-biased responder). The
  measurable statement: answers are 100% invariant to the perturbation on flip
  items. A separation of "reads the tally" from "always says yes" needs a
  responder without the degenerate policy, or a design that perturbs toward
  `no`-GT on a balanced pool.

## Provenance

- Arm A: `results/m3-preview-term10` (same model/rev/engine; full 5,137
  answers) — 0 GPU.
- Arm B: `.18` GB10, 2026-11-22, `scripts/cf_run_eval.py` run
  `~/cf-dump/run-mini` (transferred to ATX, byte-identical).
- Comparator: `scripts/cf_report.py` (ATX) → `cf-verdicts.jsonl`
  (208 verdicts) + `cf-report.md`.
- Raw verdicts: `results/counterfactual-m3-preview-cf-verdicts.jsonl`
  (committed); report derived from it.
- Perturbation set + rules: `scripts/cf_build.py`; fixture manifest with
  per-item sha256 + provenance: `cf/manifest-cf.json` (HF,
  `patrykorwat/sejmbench-results`); balance of perturbation types reported
  above (108/50/50).
- Leakage test: perturbation alone does not trivially predict the verdict
  (68/40 perturbed-GT split, `cf_leakage_check.py`).
- DATA_LICENSE note for synthetic derived data: DATA_LICENSE.md
  "Synthetic derived data" section.
