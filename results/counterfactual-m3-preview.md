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
| **flip** (winner reversed, k=⌊margin/2⌋+1) | 108 | **68/108 (0.630)** | **40/108 (0.370)** | — |
| **reorder** (records permuted) | 50 | — | — | **49/50 (0.980)** |
| **club-label pseudonymization** | 50 | — | — | **50/50 (1.000)** |

## Reading

- The model reads from the record most of the time, but does not trust it
  fully: when the tally is reversed, **37% of answers echo the remembered
  real-world outcome** instead of the perturbed GT. The echo set is exactly
  the 40 items where arm A was originally right (overlap 40/40) — consistent
  with recalling the outcome its own training/retrieval associated with those
  divisions, not with miscounting (echoes are spread across sittings, max 3
  per sitting; no clustering artifact).
- The flip arm partitions cleanly: no item matched both/neither GT
  (0/208 inconsistencies), `changed_answer` agrees with the raw comparison
  on 208/208.
- Order and club-label pseudonymization do not move the answer (0.98/1.00
  stability) — no dependence on label names or record layout.
- All 108 flip items are term 10 — by construction (arm A is the term-10
  checkpoint), not by data choice. The `flip_narrow` stratum is
  under-sampled for the same reason (18/60 shortfalls, insufficient
  eligible population); conclusions are for narrow/close/wide pooled, not
  per-stratum.
- Perturbed-GT balance in the flip arm: 68 yes / 40 no — the perturbation is
  not a constant signal (`scripts/cf_leakage_check.py`, report-only).

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
