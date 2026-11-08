# Scorecard schema (v1.4)

This document freezes the harness contract for issue #4: deterministic,
offline scoring of saved responses, with every published number reproducible
from committed artifacts. The reference implementation is `scoring.py`; the
CLI is `scripts/sejmbench.py`.

v1.2 adds corpus-backed sets (issue #11): `--set full|term10` scores against
the frozen population in `docs/population/`, and corpus scorecards must carry
a `population` block binding them to the frozen ID list.

v1.3 adds the temporal holdout (issue #5): corpus model scorecards must
carry a `temporal_split` block with per-subset statistics (CODEBOOK §9
rule 6 — enforced by the CLI: corpus `score` runs require
`--temporal-cutoff`; tightened 2026-11-06 before any 1.3 card shipped
without the block). Baseline corpus cards carry the block when built with
`--temporal-cutoff`. `contamination.temporal_holdout_applied` is true
exactly when the block is present. The frozen cutoff is a CODEBOOK §9
rule (2026-01-01).

v1.4 adds pre-registered margin buckets (issue #14, CODEBOOK §13):
`layers["0.1"]` carries a `margin_buckets` block — per-bucket
`n` / `n_scored` / `accuracy` / `ci95` over tie | narrow | close | wide,
plus `margin_macro` (unweighted mean over non-empty buckets; weights frozen
in CODEBOOK §13) and `margin_macro_ci95` (cluster-stratified bootstrap:
resample sittings within buckets, equal weights per replicate — issue #20;
all CIs are cluster-bootstrapped by sitting). The denominator rule per bucket
matches the headline
accuracy. `validate_scorecard` verifies the bucket n values sum to layer
0.1 `n_eligible`. The leaderboard gains two parallel columns
(close-division accuracy, margin-macro); overall accuracy is never dropped.

## Outcome block (v0.4 lane, issue #17)

A scorecard with `metric_version` 0.4 carries an `outcome` block (CODEBOOK
§14): the three metrics (outcome recognition, side-picking on non-ties,
legacy seed convention compliance — each with clustered CIs), tie
precision/recall/F1, the 3×3 confusion matrix and class counts. Lane rules
(`validate_scorecard`): a metric-0.4 card must carry the block; a
metric-0.3 card must not. v0.3 and v0.4 scorecards are not directly
comparable (`cmd_compare` refuses differing metric versions).

## Two paths

- `sejmbench eval` — model execution, provider-specific, only via documented
  adapters. A bare model id does not imply runnability. Adapters are
  deliberately deferred until this scorer and the format are frozen.
- `sejmbench score` — deterministic offline scoring of saved responses: no
  network, no model calls, byte-reproducible output.

```
$ python scripts/sejmbench.py score --submission results/<model>-<date>/ \
      --set public --out results/<model>-<date>.scorecard.json
$ python scripts/sejmbench.py score --submission results/<model>-<date>/ \
      --set term10 --out results/<model>-<date>.scorecard.json
$ python scripts/sejmbench.py compare A.scorecard.json B.scorecard.json
$ python scripts/sejmbench.py rescore-check 'results/*.scorecard.json'
$ python scripts/sejmbench.py leaderboard [--check]
```

## Model identity and operational controls (v1.2, issue #12)

Model scorecards (`submission.kind == "model"`) must carry:

```json
"model": { ..., "identity": {
  "weights_sha256": "…", "tokenizer": "…", "quantization": "bf16|fp8|…",
  "runtime": "basal-serve", "runtime_version": "2.5.2",
  "context_length": 262144, "hardware": "…", "determinism_note": "…" } },
"operational": { "retry_policy": "fixed before the run; never re-roll for a better answer" }
```

The identity keys are required; `"unknown"` is an allowed value for anything
genuinely unverifiable. Raw responses may carry per-item `input_tokens`,
`context_overflow` and `inference_attempts`; the scorer passes them through to
scorecard items so truncation and retry storms are visible, never silent.

Prompts are versioned: `KNOWN_PROMPTS` pins hash → template (`reference` v0.3
and the `corpus` variant — `club | vote` lines, used when MP names are not in
the input). A template that does not match its pinned hash fails validation.

## Population block (corpus sets, v1.2)
When `set` is `full` or `term10`, the scorecard carries:

```json
"population": {
  "set": "full",
  "n": 66104,
  "ids_file": "docs/population/ids-full-corpus.txt",
  "ids_sha256": "<sha256 of the frozen ID list>",
  "gt_sha256": "<sha256 of the uncompressed GT stream>"
}
```

`set_hash` equals `gt_sha256` for corpus sets; the leaderboard validates the
`ids_sha256` against the file on disk (frozen-list drift fails). Ground truth
is the precomputed stream `docs/population/gt-<set>.jsonl.gz` built by
`scripts/build_corpus_gt.py` from the frozen population — the same seed_rule
metric as fixture scoring, computed once and hashed.

## Temporal holdout block (corpus sets, v1.3)
Required on corpus model scorecards (CODEBOOK §9 rule 6): a corpus `score`
run without `--temporal-cutoff` refuses to build, and validation rejects a
corpus model card without the block. Baseline corpus cards carry the block
when built with `--temporal-cutoff`. The scorecard carries:

```json
"temporal_split": {
  "cutoff": "2026-01-01",
  "ids_post_file": "docs/population/ids-post-2026-01-01.txt",
  "ids_post_sha256": "<sha256 of the committed post-cutoff list>",
  "n_pre": 64187, "n_post": 1917,
  "layers": {"0.1": {"pre": {"n": 1, "accuracy": 1.0, "ci95": [0.0, 1.0]},
                     "post": {"n": 1, "accuracy": 1.0, "ci95": [0.0, 1.0]}},
             "0.2": {"pre": {}, "post": {}}}
}
```

`post` = official sitting date strictly after the frozen cutoff (CODEBOOK §9
rule 6); the post-cutoff ID list is committed, and `rescore-check` verifies
its sha256 against the file on disk (drift refuses). Excluded items
(zero-counter divisions) sit outside both subsets; every other item lands in
exactly one. Subset statistics use the same bootstrap protocol as the
headline layer blocks (seed 20261027, 10,000 replicates). Baselines accept
the same flag: `baselines --temporal-cutoff` reports the subsets for
majority-class and random.

## Submission format (AGENTS.md)

One JSON file per fixture: `results/<model-name>-<YYYYMMDD>.json` with
`model`, `date`, `temperature` (must be 0), `prompt_hash`, `declared_cutoff`,
`raw_output`, `fixture`. One scorecard per PR (per model run).

Set semantics: `--set public` is the full `fixtures/manifest.json` list. A
fixture with no submission file is reported as `missing` (exclusion reason
recorded) and counts as **incorrect** for headline accuracy — an incomplete
run is a worse result, not a smaller denominator. A submission record naming
a fixture outside the set is rejected as an unknown fixture (a `problems`
entry), never silently ignored.

Missing `prompt_hash`, a hash mismatch, or a missing `declared_cutoff` is a
contract violation recorded in `problems`; a scorecard with problems is not
acceptable (CI rejects it).

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
count as incorrect (§9.4) and are reported separately. Fixtures with
`layers.0.1 = false` (zero-counter divisions, CODEBOOK §11) are excluded
with a reason; an exclusion is not an incorrect answer — it leaves both
denominators (accuracy and MAE), tracked as `n_eligible` /
`n_excluded_ineligible`.

Layer 0.2 (tracks): per-item mean absolute deviation of `yes_share` and
`polarization` over the fixture's ground-truth tracks (`seed_rule.py`,
≥ 5 active votes). Track matching is by exact club label.

- A ground-truth track missing from the answer counts as **maximum
  deviation (1.0 on both measures)**. The reference prompt requires
  "exactly the clubs with at least 5 active votes" — omitting a track is an
  instruction violation, not a neutral gap. This rule is the scorer's
  frozen interpretation; deviations are rejected, arguments get heard
  (AGENTS.md rule 5).
- Extra model-side tracks are recorded but not penalized; structural
  fidelity of the track set is reported separately (`n_exact_track_set` /
  `exact_track_set_rate`).
- A `tracks` field that is not a list does not invalidate the item: the
  winner is still scored and every ground-truth track counts as missing.
- Duplicate club labels void that club entirely: it counts as missing and
  each duplicate entry is counted as invalid.
- Non-numeric or out-of-[0,1] values count as missing for that track.
- MAE is computed over items with a valid parsed answer (§8.6: status
  `scored`); `answer_coverage` is reported alongside.

## Statistics (CODEBOOK §8)

- Bootstrap 95% CIs: 10,000 replicates, seed **20261027**, percentile
  method, `random.Random` (deterministic; the same seed restarts per
  statistic, so every CI is bit-reproducible).
- Comparing two scorecards: `compare` runs a paired bootstrap over the
  shared fixture set; differences inside the CI are **not ranked**. A
  comparison is additionally **provisional** (never a ranking) when the
  shared set is smaller than the §8.3 minimum cell count (20), and pairings
  require identical fixture sha256 on both sides (same name, different hash
  = different data, excluded). `compare` also reports both models' answer
  coverage: a coverage gap can flatter the model that answers only the easy
  items.
- Minimum cell count: 20 divisions per bucket (§8.3) — with the current
  2-fixture set all aggregates are provisional by definition.

## Hashes and provenance

- `prompt.hash` — sha256 of the reference prompt template (CODEBOOK §5,
  pinned constant in `scoring.py`). Current value:
  `d937dfcbe2e92cef97c292353371cd40017da7c226587f7da31a09682db20dc6`.
- `set_hash` — sha256 over the sorted `file:sha256` lines of the fixture
  manifest. Current public set (50 fixtures):
  `018ddcb9ec32cfae977cf176c55f5043240907fcbe0b42827ad9c8381001457b`.
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
| `temporal_split` | required on corpus model scorecards (baselines: carried in practice): cutoff, committed post-cutoff list path + sha256, n_pre/n_post, per-layer pre/post subset stats (issue #5) |
| `token_usage` / `cost_estimate` | as reported by the adapter; `null` when not supplied |
| `layers` | per layer: `n_total`, `n_eligible`, `n_scored`, `n_abstained`, `n_parse_failures`, `n_refusals`, `n_missing_files`, `n_excluded_ineligible` (zero-counter divisions — excluded from both denominators, not counted as incorrect); layer 0.1 adds `n_ties` (and per-item `gt_tie`, so a convention-winner on a tied division is never readable as "the motion passed"); layer 0.2 adds `n_exact_track_set` / `exact_track_set_rate`; accuracy/MAE with bootstrap 95% CI |
| `items` | per fixture: status, layer-0.1 pred/gt/correct, layer-0.2 track detail, submission file + sha256 |
| `problems` | contract violations (temperature ≠ 0, missing fields, prompt-hash mismatch); a scorecard with problems is not acceptable |

## Baselines (same harness)

- `baseline:majority-class` — always `yes` (the modal winner class in the
  Sejm); tracks: `yes_share` 1.0, `polarization` 0.0. Mandatory row: the
  bar every model must clear.
- `baseline:random` — seeded RNG (`20261027`) over sorted fixture order:
  fair-coin winner, uniform shares. Deterministic via CPython's stable core
  `random.Random` generator; cross-runtime bit-identity is not certified.
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
  committed content: every field is compared, not just numbers (provenance
  text, set/fixture hashes, model identity, prompt template; the `problems`
  list by length). The scorecard is additionally bound to the manifest on
  disk: `set_hash`, the fixture list (files + sha256), and the current
  contract versions must all match.
- `leaderboard --check` — `results/leaderboard.jsonl` and the README table
  are generated only from accepted scorecards; drift fails CI. Values are
  never hand-edited.
- Prediction-backtest numbers stay in `results/backtest-*.md` and are never
  merged with layer 0.1/0.2 rows.
