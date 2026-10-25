# Changelog

All notable changes to SejmBench are documented here.
Format follows Keep-a-Changelog; versions follow SemVer.

## [Unreleased]

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
