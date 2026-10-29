# Changelog

All notable changes to SejmBench are documented here.
Format follows Keep-a-Changelog; versions follow SemVer.

## [Unreleased]

- Harness hardening (blind review round): full-field rescore comparison (provenance, hashes, model identity — not only numbers), scorecards bound to the on-disk manifest (`set_hash`/fixtures/contract versions), `prompt_hash` + `declared_cutoff` required, unknown fixture records rejected, duplicate club labels void the track, `compare` refuses to rank below the §8.3 minimum cell count (provisional instead) and reports answer coverage + fixture-hash pairing, leaderboard table shows the CIs it promises, per-fixture §4 invariant tests, scorecard schema 1.1 (harness 0.4.4).
- Harness (issue #4): deterministic offline scorer (`scoring.py` + `scripts/sejmbench.py` CLI: `score` / `baselines` / `compare` / `rescore-check` / `leaderboard`), scorecard schema 1.0 (`docs/scorecard-schema.md`), non-LLM baseline rows (majority-class, seeded random) in the leaderboard, CI rescore + leaderboard-drift gates, README version axes (harness 0.4.3).

- Full-corpus backtest results (terms 3–10, 66,044 scored divisions): two-metric bar — kNN 0.707 winner accuracy, carry_last 0.287 yes_share MAE (`results/backtest-full-corpus-2026-10-26.md`).
- Governance: `GOVERNANCE.md` (errata policy, conflict of interest, appeals) and `DATA_LICENSE.md` (MIT covers code, not data).
- README: version axes (metric / dataset / harness / release), contamination policy, dataset table corrected to v0.4.0 (30,511,109 votes, 66,427 votings).
- CODEBOOK: §3 tie-break marked as a scorer convention (0:0 is not "passed"); §8 statistical protocol; §9 model input and contamination contract.
- `scripts/verify_fixtures.py`: duplicate-entry and schema checks; optional per-fixture `layers` eligibility field (consumed by #1).
- `scripts/inventory_descriptions.py`: inventory of distinct official `description` formulas per term (input to the #2 dictionary).
- Layer 1 (issue #2): draft dictionary v0.1.0-draft (`layer1_dictionary.json`, `layer1_classify.py`), unit tests, coverage report (`docs/layer1-coverage.md`), seeded validation-sample generator (`scripts/layer1_validation_sample.py`). CODEBOOK section 10 added as DRAFT — not frozen; no layer-1 scores until freeze.
- Layer 1 (issue #2, review round): `election` fixed — accented `wybór` forms (confirmed false negatives, ~125 divisions) map via contains `wybór` / contains `wybor` (excluding `wyborcz`) / contains `nad wyborem`; `całość projektu rezolucji` and the `uchwaly` l-variant map to resolution_whole; repair map applied after casefold (case variants caught); dictionary v0.1.1-draft.
- Coverage report: dual denominators (88.6% of the described universe; 14.0% of the corpus) + canonical-formula grouping + rule-conflict counts; per-term table retained; CI-diffed snapshot `docs/layer1-formula-buckets.json` (`layer1_formula_buckets.py --check`).
- Metric v0.3 (CODEBOOK): additive `seed_rule.tie` flag (ties, including 0:0, explicit; never reportable as "passed"); MAE denominator rule for refusals/parse failures (section 8); ABSTAIN-never-decides clarification (section 3).
- Validation sample split: tuning (112 head formulas + 88 seeded tail = 200; `docs/layer1-validation-sample.csv`) and held-out test set (100 seeded tail; `docs/layer1-test-set.csv`) — the test set is scored only at dictionary freeze.
- Governance: `SECURITY.md` (vulnerability reporting), `docs/errata.md` (register), `CITATION.cff`; `DATA_LICENSE.md`: personal-data status of named votes + source reuse terms marked pending review.
- Bucket-semantics axis decision recorded (CODEBOOK §10): act-dominant taxonomy; tension cases documented; the hand-coded sample arbitrates.

## [0.4.2] - 2026-10-26
### Fixed
- kNN crash on cross-term input: a division with no indexable tokens (empty
  title/topic/description) was stored as a zero-nonzeros row of the
  retrieval index and broke `add.reduceat` when it became the last row.
  Empty-text divisions are no longer stored (nor retrievable); the summary
  reports their count.

## [0.4.1] - 2026-10-26
### Fixed
- `backtest_layers.py` memory: aggregate per division at load time — the
  full-corpus input is ~1 GB instead of ~9 GB of raw vote dicts, which
  enables cross-term runs on the 14 GB host.
- Dormant-club decay: a club's expected size decays with the same half-life
  while it is absent, so defunct clubs stop contributing phantom vote mass
  in cross-term runs; `club_mean` now weights by the same decayed size
  (uniform winner aggregation across all methods).
### Added
- Per-term winner-accuracy breakdown (carry_last vs knn) in the summary.

## [0.4.0] - 2026-10-26
### Added
- `scripts/build_divisions.py`: rebuild the divisions view (one row per
  voting, per-MP votes embedded — the backtest input format) from the dump
  offline, no API access needed. Streaming, O(one division) memory, optional
  term filter, `.gz` output. Verified to reproduce the term-10 divisions
  built during the backtest runs (5,201 divisions, byte-identical).

## [0.3.3] - 2026-10-26
### Fixed
- A failed sitting-list fetch silently fell back to first-day-only discovery,
  truncating the dump (60,128 of 66,427 divisions were pushed). Discovery now
  aborts the pass on a list-fetch failure or an empty list for a non-empty
  sitting — the supervisor retries instead of pushing incomplete data.
- The dataset card was uploaded without a `configs:` block, which collapsed
  all five configs into one `default` on the Hub. The card now declares all
  five configs with `*.parquet` globs.
- Stale parquet shards from earlier pushes are deleted before each config
  push (shard counts change between runs; leftover shards would otherwise be
  indexed alongside the new ones).

## [0.3.2] - 2026-10-26
### Fixed
- HF push crashed on JSONL schema inference: `votingOptions` structs with
  and without the optional `description` key both occur across terms, so
  chunk-wise inference failed to cast. `build_and_push` now passes explicit
  features for both configs (`votingOptions`/`links` declared as struct
  lists). Added `--push-only` to build+push from the existing JSONL without
  re-walking the raw cache.

## [0.3.1] - 2026-10-25
### Fixed
- `dump_sejm_hf.py`: multi-day sittings were silently truncated — discovery
  used `range(1, votingsNum+1)` where `votingsNum` counts only the first day
  of a sitting, while `votingNumber` is unique across the whole sitting
  (term10: 808 of 5,201 divisions). Discovery now queries the per-sitting
  list endpoint. The published HF mirror is incomplete until re-dumped.
### Changed
- `dump_sejm_hf.py` streams rows to JSONL instead of accumulating in memory
  (full corrected dump ≈ 20M rows; 14 GB hosts were not enough).

## [0.3.0] - 2026-10-25
### Added
- Public dataset mirror on Hugging Face: `patrykorwat/sejm-votings`
  (configs: votings, votes, sittings, druki, druk_texts), linked from README.
- Dump and print-pipeline tooling under `scripts/`:
  `build_extra.py`, `build_druki.py`, `download_druki.py`, `extract_druki.py`,
  `fix_docs.py`, `push_druk.py`, `run_druki.sh`.
### Changed
- Backtest skeleton and term-dump fetcher (`scripts/backtest_skeleton.py`,
  `scripts/fetch_term_dump.py`) with first content-free baseline results.
- `dump_sejm_hf.py`: network retries raised 3 -> 6; push per config
  (DatasetDict configs may now have different schemas); `sittingDay` added
  to `VOTING_FIELDS`.

## [0.2.0]
- Fixtures, seed rule, CODEBOOK (pre-versioning history, reconstructed).

## [0.1.0]
- Initial benchmark design, CI (pre-versioning history, reconstructed).
