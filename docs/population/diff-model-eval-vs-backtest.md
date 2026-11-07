# ID-level diff: model-eval population (66,104) vs backtest #8 scored (66,044)

Issue #16. Reconstruction run 2026-11-08 against the ATX dump. The scored set was
re-derived 1:1 from the committed logic (`scripts/backtest_layers.py` v0.4.2:
`load()` dedup + `(date, sitting, votingNumber)` sort, `actuals()` None rule,
`WARMUP = 60` applied to the row index of the sorted order) and cross-checked
against the mirror classification (`scripts/freeze_population.py::classify`).
The reconstruction reproduced the published count exactly: **scored = 66,044**
(sha256 of `ids-backtest-scored.txt`: `4151d10810069be8…`).

## Headline

- **The scored set is a subset of the model-eval population, differing by exactly
  the 60 warmup rows.** `|scored − eligible| = 0`; `|eligible − scored| = 60`,
  all in term 3 (the chronologically first divisions; votes fine, row index < 60).
- **No inconsistent-tally row was scored** (`scored ∩ inconsistent = 0`). This
  corrects the phrasing in #11 that the backtest construct "includes
  inconsistent-tally rows" — it does not.
- **The two 241s are not the same set.** Zero-active (241; no club track reaches
  `MIN_TRACK = 5` among YES/NO/ABSTAIN in the division record) is a **proper
  subset** of mirror-inconsistent (243): intersection 241, inconsistent-only 2.
  Correction (2026-11-08): the 2 inconsistent-only keys are **absent from the
  divisions file entirely** — the file holds exactly eligible (66,104) +
  zero-active (241) = 66,345 rows — so they are mirror-only rows (classify()
  flags `inconsistent` before the term check, so these are most plausibly
  out-of-terms divisions with broken counters; key list to be captured at the
  next dump pass). An earlier draft of this report wrongly placed them among
  the 60 warmup rows.
- Mirror bookkeeping correction to #11: `votings.jsonl` has 66,524 rows /
  66,503 unique keys (21 duplicate rows — matches #11), classified as
  inconsistent **243** (not 241 — that number was the zero-active count),
  zero_counter 61.

## Counts (reconstruction)

| construct | n | source |
|---|---|---|
| mirror rows / unique keys | 66,524 / 66,503 | `votings.jsonl` (21 dups) |
| mirror inconsistent / zero_counter | 243 / 61 | `classify()` |
| divisions rows (dedup) | 66,345 | `divisions_3_10.jsonl` |
| zero-active | 241 | `actuals()` None rule |
| warmup | 60 | row index < 60, sorted order |
| **backtest scored** | **66,044** | `i >= 60 ∧ act ≠ None` |
| model-eval (frozen) | 66,104 | `ids-full-corpus.txt` |

## Symmetric difference, per term

| term | eligible − scored | scored − eligible |
|---|---|---|
| 3 | 60 | 0 |
| 4–10 | 0 | 0 |

## Standing rule (CODEBOOK §12)

66,104 = model-evaluation population (consistent tallies, term 3–10, ≥1 active
vote record). 66,044 = predictive-backtest scored set = 66,104 minus the 60
warmup rows. The two populations differ by construction; never mix baselines
or compare results across them without explicit reconciliation.

## Artifacts

- `docs/population/ids-backtest-scored.txt` — 66,044 IDs, sorted, sha256 above
- `docs/population/diff-report.json` — raw reconstruction numbers
