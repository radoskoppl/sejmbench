# Scorecard schema (v1.0)

This document freezes the harness contract for issue #4: deterministic,
offline scoring of saved responses, with every published number reproducible
from committed artifacts. The reference implementation is `scoring.py`; the
CLI is `scripts/sejmbench.py`.

## Two paths

- `sejmbench eval` — model execution, provider-specific, only via documented
  adapters. A bare model id does not imply runnability. Adapters are
  deliberately deferred until this scorer and the format are frozen.
- `sejmbench score` — deterministic offline scoring of saved responses: no
  network, no model calls, byte-reproducible output.

```
$ python scripts/sejmbench.py score --submission results/<model>-<date>/ \
      --set public --out results/<model>-<date>.scorecard.json
$ python scripts/sejmbench.py compare A.scorecard.json B.scorecard.json
$ python scripts/sejmbench.py rescore-check 'results/*.scorecard.json'
$ python scripts/sejmbench.py leaderboard [--check]
```

## Submission format (AGENTS.md)

One JSON file per fixture: `results/<model-name>-<YYYYMMDD>.json` with
`model`, `date`, `temperature` (must be 0), `prompt_hash`, `declared_cutoff`,
`raw_output`, `fixture`. One scorecard per PR (per model run).

Set semantics: `--set public` is the full `fixtures/manifest.json` list. A
fixture with no submission file is reported as `missing` (exclusion reason
recorded) and counts as **incorrect** for headline accuracy — an incomplete
run is a worse result, not a smaller denominator.

## Parse rules (fixed)

| status | definition |
|---|---|
| `refusal` | `raw_output` is null, empty or whitespace-only |
| `parse_failure` | no JSON object extractable (string-aware balanced-brace scan after strict `json.loads` fails), or the object lacks `winner`, or `winner` is not a string |
| `abstain` | JSON parses, `winner` is a string outside `{yes, no}`, or an explicit `{"abstain": true}` marker is present |
| `scored` | `winner` in `{yes, no}` (case-insensitive, normalized to lowercase) |

Layer 0.1 (winner): exact match against the seed rule (CODEBOOK §3,
including the tie convention — a tie is never "passed"). The headline
denominator is the full set: abstain, parse failure, refusal and missing
count as incorrect (§9.4) and are reported separately.

Layer 0.2 (tracks): per-item mean absolute deviation of `yes_share` and
`polarization` over the fixture's ground-truth tracks (`seed_rule.py`,
≥ 5 active votes). Track matching is by exact club label.

- A ground-truth track missing from the answer counts as **maximum
  deviation (1.0 on both measures)**. The reference prompt requires
  "exactly the clubs with at least 5 active votes" — omitting a track is an
  instruction violation, not a neutral gap. This rule is the scorer's
  frozen interpretation; deviations are rejected, arguments get heard
  (AGENTS.md rule 5).
- Extra model-side tracks are recorded but not penalized.
- Non-numeric or out-of-[0,1] values count as missing for that track.
- MAE is computed over items with a valid parsed answer (§8.6: status
  `scored`); `answer_coverage` is reported alongside.

## Statistics (CODEBOOK §8)

- Bootstrap 95% CIs: 10,000 replicates, seed **20261027**, percentile
  method, `random.Random` (deterministic; the same seed restarts per
  statistic, so every CI is bit-reproducible).
- Comparing two scorecards: `compare` runs a paired bootstrap over the
  shared fixture set; differences inside the CI are **not ranked**.
- Minimum cell count: 20 divisions per bucket (§8.3) — with the current
  2-fixture set all aggregates are provisional by definition.

## Hashes and provenance

- `prompt.hash` — sha256 of the reference prompt template (CODEBOOK §5,
  pinned constant in `scoring.py`). Current value:
  `d937dfcbe2e92cef97c292353371cd40017da7c226587f7da31a09682db20dc6`.
- `set_hash` — sha256 over the sorted `file:sha256\n` lines of the fixture
  manifest. Current public set (2 fixtures):
  `d465a66a92ec27f779f0fb75f6ed2e1a51cc7a66d64cf62eb2bfb469e07a9f02`.
- Every item carries the submission file path and its sha256.
- Changing the prompt template or the fixture set changes these hashes by
  design; that is a version event, not a silent edit (enforced by tests).

## Scorecard fields

| field | content |
|---|---|
| `schema` / `scorecard_version` | `sejmbench.scorecard/1.0` |
| `benchmark_version` | CODEBOOK version (the contract) — v0.3 |
| `metric_version` | metric version — v0.3 (never comparable across) |
| `harness_version` | repo `VERSION` |
| `set` / `set_hash` | set name + canonical hash |
| `fixtures` | per-fixture file + sha256 |
| `model` | id, provider, revision (or `identity_mutable_alias: true` when no immutable revision is declared — bitwise reproducibility not guaranteed), call date, decoding settings actually used |
| `submission` | kind (`model` / `baseline`), per-file list (fixture, path, sha256) |
| `prompt` | hash + template itself |
| `evaluation_date` | evaluation date |
| `contamination` | `declared_cutoff` (`unknown` when unverifiable), temporal-holdout flag (issue #5) |
| `token_usage` / `cost_estimate` | as reported by the adapter; `null` when not supplied |
| `layers` | per layer: `n_total`, `n_scored`, `n_abstained`, `n_parse_failures`, `n_refusals`, `n_missing_files`, accuracy/MAE with bootstrap 95% CI |
| `items` | per fixture: status, layer-0.1 pred/gt/correct, layer-0.2 track detail, submission file + sha256 |
| `problems` | contract violations (temperature ≠ 0, missing fields, prompt-hash mismatch); a scorecard with problems is not acceptable |

## Baselines (same harness)

- `baseline:majority-class` — always `yes` (the modal winner class in the
  Sejm); tracks: `yes_share` 1.0, `polarization` 0.0. Mandatory row: the
  bar every model must clear.
- `baseline:random` — seeded RNG (`20261027`) over sorted fixture order:
  fair-coin winner, uniform shares.
- `carry_last` / kNN over titles need division history; they enter the
  leaderboard only from the corpus-backed re-run of the harness-0.4.2 bars
  (separate job; not computable on an isolated fixture set).

## Layer 1

Layer-1 scoring refuses until the §10 dictionary freezes. No layer-1 scores
may be submitted or published before that.

## Version axes

| axis | source |
|---|---|
| benchmark | `CODEBOOK.md` version |
| metric | CODEBOOK §2/§3 (`seed_rule` schema) |
| harness | repo `VERSION` |
| scorecard schema | this document |

## CI gates

- `rescore-check` — every committed scorecard must be schema-valid, carry no
  problems, and rescore from its referenced artifacts to **exactly** the
  committed numbers.
- `leaderboard --check` — `results/leaderboard.jsonl` and the README table
  are generated only from accepted scorecards; drift fails CI. Values are
  never hand-edited.
- Prediction-backtest numbers stay in `results/backtest-*.md` and are never
  merged with layer 0.1/0.2 rows.
