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

- **Zero `przeciw` answers on 108 winner-reversing perturbations.** This is
  the headline diagnostic: the model did not produce a single NO answer when
  the provided tally said NO. A degenerate always-ZA predictor scores exactly
  the same on this sample (68/108 = 0.630 = the model's accuracy) with
  **balanced accuracy 0.500** (100% recall on perturbed-yes, 0% on
  perturbed-no). The 0.630 therefore provides no evidence of input reliance
  beyond a constant-yes predictor — and the experiment does not distinguish
  outcome memorization from positional or other decision bias.
- **† The flip metric is confounded with the model's ZA-bias.** Arm B answered
  `za` on **108/108 flipped tallies** (arm A on the same items: 104 yes / 4 no).
  "Follows perturbed GT 0.630" is therefore exactly the share of flip items
  whose perturbed GT is `yes` (68/108 — i.e. original GT `no`), and "matches
  original 0.370" is exactly the share whose original GT is `yes`. Consistent
  with the documented 82.2% yes-rate on the committed full run.
- On unperturbed tallies (reorder + pseudonymize arms, GT unchanged) arm B
  reproduces arm A 99/100 (49/50, 50/50) and answers `no` 23× — the model does
  produce `no` when the tally reads `no`; the uniform-yes behaviour is specific
  to the flipped (contradictory) inputs.
- The earlier "echo of the remembered outcome" reading is retracted: it is not
  distinguishable from the constant-yes policy (the echo set coincides with
  original-GT-yes items for that trivial reason), and the 4 items where arm A
  itself answered `no` (correctly) also got `za` from arm B — recall of arm A's
  answers does not explain them, uniform-yes does.
- Order and club-label pseudonymization: 49/50 and 50/50 are **empirical
  stability rates, not proof of invariance**. The single reorder divergence
  (`term10-s52-v52`: arm A `tie` → arm B `no`, GT `no` in both) shows the
  answer can move on semantically identical input; with no repeated-original
  control we cannot attribute it to record order rather than serving-mode
  variability (`--mode fast`). A repeated-original/permuted control is part of
  the follow-up.
- All 108 flip items are term 10 — by construction (arm A is the term-10
  checkpoint), not by data choice. The `flip_narrow` stratum is
  under-sampled for the same reason (18/60 shortfalls, insufficient
  eligible population); conclusions are for narrow/close/wide pooled, not
  per-stratum. Original-GT composition of the flip pool: 68 `no` / 40 `yes`
  (drives both flip rates — see †).
- Perturbed-GT balance in the flip arm: 68 yes / 40 no — the perturbation is
  not a constant signal, but an always-yes predictor still scores 0.630
  (`scripts/cf_leakage_check.py` reports it; it does not gate — the
  acceptance criterion "leakage test" stays open, see issue #15).
- **Net for issue #15**: input-reliance is not measurable for this model with
  the flip design as built (one outcome question, yes-biased responder). The
  measurable statement: **constant-`za` output across all 108 flipped inputs**
  (104/108 answers identical to the paired original run; the 4 that changed
  went `no`→`za`). A separation of "reads the tally" from "always says yes"
  needs a class-balanced flip pool (perturbed GT 60/60, stratified by margin
  and flip direction), a responder without the degenerate policy, or a design
  that perturbs toward `no`-GT on a balanced pool — before any positive claim
  about input reliance.

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
- Leakage diagnostic: majority-class baselines reported
  (`cf_leakage_check.py`, always-`za` ceiling 68/108 = 0.630 on this pool);
  no pass/fail conclusion. The leakage acceptance criterion remains open
  pending a class-balanced control (follow-up issue #22).
- DATA_LICENSE note for synthetic derived data: DATA_LICENSE.md
  "Synthetic derived data" section.
