# Changelog

All notable changes to SejmBench are documented here.
Format follows Keep-a-Changelog; versions follow SemVer.

## [Unreleased]

- 9c full-corpus run (Basal v0.4, 2026-11-12→14): 66,104/66,104 items, 0 errors; card `basal-9c-full.scorecard.json` (sha `ba1d96fd…`, kept off-git), raws `results/basal-9c-v04-full.raw.tar.gz`, paired report `results/basal-9c-vs-9b-v04.md` — v0.4 scores −0.98 pp vs v0.3 on identical raw-response re-scoring (McNemar χ²=227), concentrated in close divisions and term 10; neither prompt predicts ties (0/43 GT). Scorer fixes: `parse_answer` accepts outcome-only payloads (v0.4 runner output was scoring as parse_failure); `_outcome_metrics` reports empty bootstrap pools as `null` instead of raising (zero predicted ties). Runner: `--shuffle SEED` for uniform partial checkpoints.

- Outcome contract v0.4 (issue #17, metric/benchmark 0.4): `{"outcome": "yes"|"no"|"tie"}` — the GT outcome keys on the official headline counters (`margin_all` sign); `seed_rule.winner` preserved as the legacy field; the 0:0 count is 0 among the 43 headline ties (the tie is arithmetic; `no_decisive_votes` moot). Three metrics (recognition / side-picking / legacy compliance), tie precision-recall-F1, 3×3 confusion matrix; the lane rules in `validate_scorecard`; v0.3/v0.4 not comparable — Basal re-runs under v0.4.
- Cluster bootstrap by sitting (issue #20, harness 0.8.0): the §8.1 bootstrap resampling unit is the sitting, not the division — divisions within a sitting share the agenda and the political moment. Point estimates unchanged; CIs widen. All committed cards recomputed (CIs only); rescore-check 8/8.

- Margin-conditioned reporting (issue #14, harness 0.7.0, scorecard schema 1.4): pre-registered margin buckets frozen in CODEBOOK §13 (tie m=0 / narrow 1–5 / close 6–50 / wide ≥51; m = |yes−no| over API headline counts, same construct as §11) BEFORE any second model evaluation. `layers["0.1"]` carries an additive `margin_buckets` block (per-bucket n/n_scored/accuracy/ci95 + `margin_macro` = unweighted mean over non-empty buckets); denominator rule identical to the headline accuracy. Leaderboard gains two parallel columns (close-division accuracy, margin-macro); overall is never dropped. `validate_scorecard` checks bucket n sums; all committed scorecards rebuilt under schema 1.4. Placebo-cutoff robustness check (scope item 5): `scripts/placebo_cutoffs.py` + `results/placebo-cutoffs-2026-11-08.md` — no 2026-specific discontinuity (full-corpus gap grows −3.4 → −4.1 → −4.2 pp with later cutoffs; term-10 gap shrinks −3.1 → −2.9 → −1.7 pp).

- Large model scorecards hosted on HF (9B card = 79.96 MB, GitHub warning): `patrykorwat/sejmbench-results` (dataset, public) hosts the full artifact with a dataset card carrying the sha256; the git repo keeps only the sha256 reference (`results/basal-9b-full.md`) and `scripts/fetch_scorecards.py` (stdlib, idempotent, no token needed) pulls the card in CI before `rescore-check`, so the card is still verified end-to-end from the committed raw tar. Harness 0.6.1.

- Temporal holdout (issue #5, harness 0.6.0, scorecard schema 1.3): frozen split rule (CODEBOOK §9 rule 6) — cutoff **2026-01-01**; `scripts/temporal_split.py` derives the post-cutoff ID lists from the committed GT stream alone (`docs/population/ids-post-2026-01-01.txt`, n=1,917; `-term10` subset); corpus scorecards carry an additive `temporal_split` block (per-subset layer-0.1/0.2 stats, same bootstrap protocol) and `rescore-check` verifies the committed list by sha256; `baselines --temporal-cutoff` reports the same subsets for majority-class/random.

- Corpus rescore gate fixed (CI had been red since the 9A/9B scorecards landed): `rescore-check` binds corpus cards to the frozen population files on disk (ids/GT sha) instead of the public manifest; `rescore` supports corpus sets (GT stand-ins, population rebinding) and rebuilds model cards from the committed raw tar (`results/<dir>.raw.tar.gz`, per-file sha256 verified) when per-item files are absent; in-harness baseline items carry their marker path verbatim (CWD-independent rescore).

- Model identity + operational controls (issue #12, schema 1.2): model scorecards must carry `model.identity` (weights_sha256 / tokenizer / quantization / runtime / runtime_version / context_length; `"unknown"` allowed as a value, the key is not) and `operational.retry_policy`; per-item `input_tokens` / `context_overflow` / `inference_attempts` pass through from raw responses. Prompts are versioned via `KNOWN_PROMPTS` (reference v0.3 + corpus `club | vote` variant for division-run inputs); template-vs-hash mismatch fails validation. CLI: `--identity-json`, `--retry-policy`, `--prompt-variant`.

- Corpus-aware harness (issue #11, harness 0.5.0, scorecard schema 1.2): `--set full|term10` scores against the frozen population (`docs/population/ids-*.txt` + precomputed GT `gt-*.jsonl.gz` built by `scripts/build_corpus_gt.py`); corpus scorecards must carry a `population` block (n / ids_sha256 / gt_sha256) and the leaderboard validates it against the frozen list on disk. Fix: the majority-class baseline now predicts the modal winner of the SET BEING SCORED instead of hard-coding "yes" — on the full corpus the modal winner is "no" (p_yes = 0.389), so the old hard-coded row scored below random.

- Evaluation populations frozen (issue #11): `scripts/freeze_population.py` reconciles the four denominators — model-eval population **66,104** unique eligible keys (sha `0b814f62…`, `docs/population/ids-full-corpus.txt`), term-10 subset **5,137** (sha `a632c12c…`); 66,345 = divisions rows (eligible + 241 inconsistent-tally), 66,044 = predictive-backtest scored (different construct incl. inconsistent rows), 66,113 = prior row-level universe. Matching layer-0.1/0.2 baselines on the frozen population: majority-class 0.611 / random 0.500 (winner), constant-mean MAE 0.459 share / 0.153 polarization (cohesion).
- Reference prompt v0.3 (CODEBOOK §5): names `NO_VOTE`, separates the >=5-record winner threshold from the >=5-active-votes cohesion threshold, states the `YES == NO` tie convention (earlier seed → "yes"). Documentation-vs-code alignment, no metric change; new `prompt_hash` `75dca1f1…` (replaces `d937dfcb…`) as a loud version event. Regression tests: 0:0 tie carries `tie=True`; `NO_VOTE` cannot flip the winner; prompt-wording guard.

- Data model (CODEBOOK §1): `NO_VOTE` documented as a term-3-era non-active vote value (evidence: headline reconstruction holds with NO_VOTE excluded; `ABSENT + NO_VOTE == notParticipating` in 10/10 NO_VOTE divisions; `ABSTAIN` counted separately). `seed_rule` tallies it like ABSENT — no output change for previously-scored divisions, no metric bump. Harness: layer eligibility — zero-counter divisions are excluded from layers 0.1/0.2 (`n_eligible` / `n_excluded_ineligible`), not counted as incorrect (harness 0.4.5).
- Fixture set v0.3 (issue #1): 50-item stratified public set — 2 v0.2 anchors + 46 seeded samples + 2 curated edge cases (a real tie; a zero-counter division excluded from layers 0.1/0.2). Strata frozen in CODEBOOK §11 before sampling; committed selection (`fixtures/selection.json`, seed 20261027, frame sha256); layer eligibility per fixture in the manifest; per-fixture provenance (`response_sha256`, `source_url`); `scripts/select_fixtures.py` / `fetch_selected_fixtures.py` / `verify_provenance.py`.

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
