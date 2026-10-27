# Changelog

All notable changes to SejmBench are documented here.
Format follows Keep-a-Changelog; versions follow SemVer.

## [Unreleased]

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
