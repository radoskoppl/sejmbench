# SejmBench

A reproducible, community-owned benchmark measuring how well LLMs understand
Polish parliamentary decision-making — starting from roll-call data.

**Status: discussion draft.** Everything below this line describes what is
already in the repo. Nothing here is a promise.

---

## Why this benchmark

Benchmarks for Polish are scarce and tend to degrade into trivia (who was
minister when, what year was the constitution adopted). Trivia is gradeable but
measures memorization, not understanding.

SejmBench starts where understanding is actually testable: **how did the Sejm
vote, and who voted how**. The data is official, structured, and free
([Sejm API](https://api.sejm.gov.pl)), and the tasks have unambiguous,
mechanically gradeable answers:

| Layer | Task | Status |
|---|---|---|
| 0.1 | Winner of a division (seed rule) | **in repo (v0.2)** |
| 0.2 | Per-club cohesion (yes_share, polarization) | **in repo (v0.2)** |
| 1 | Vote-type awareness (nominal vs procedural vs election) | spec stage |
| 2 | Coalition structure over time (rolling pairwise affinity) | spec stage |
| 3 | Prediction backtest: train on history ≤ T, predict division T+1 | spec stage |
| 4 | Cross-institution: local councils (see below) | spec stage |

Layers 0.1 and 0.2 are computation on the provided record — the answer is
derivable from the input alone (CODEBOOK section 9). Expect saturation there:
they are the calibration floor, not the comprehension frontier.

The endgame is layer 3: a **predictive backtest**. A model gets the full voting
history up to a date and must predict the next division — seat by seat, or
club by club. That is the same evaluation philosophy Radoskop applies to
municipal councils: resolutions are treated as decisions that can be scored
after the fact, so decision-making quality becomes measurable instead of
narrated. SejmBench ports that idea from city councils to the Sejm.

Prior-art review behind this design (arXiv, 2026-10-24):
[docs/RESEARCH-DECISION-SYSTEMS.md](docs/RESEARCH-DECISION-SYSTEMS.md) —
roll-call vote prediction with LLMs, ideal-point estimation, agent-based
legislative simulation, and the benchmark gap this repo fills.

## What is in the repo (v0.2 baseline — see Version axes for current)

- `GOVERNANCE.md`, `DATA_LICENSE.md` — errata policy, conflict of interest,
  data licence and provenance; `SECURITY.md`, `docs/errata.md`, `CITATION.cff`.
- `layer1_dictionary.json` + `layer1_classify.py` — layer-1 vote-type
  dictionary (DRAFT, issue #2): deterministic mapping from official
  description strings; coverage in `docs/layer1-coverage.md`.
- `fixtures/` — two real divisions fetched from the official Sejm API, with
  sha256 pins in `fixtures/manifest.json`:
  - `term10-s1-v2-landslide.json` — election of Deputy Marshals, 458:0
    (2023-11-13). Every club unanimous: the trivially-easy anchor case.
  - `term10-s6-v14-tight.json` — third reading, amendment to the Pharmaceutical
    Law, **224:196** (2024-02-22). Coalition holds at 100% except PSL-TD
    (24 yes / 7 no); PiS votes 170 no + 1 abstention; 37 MPs absent.
    Overall polarization 0.9284 on the 0-1 scale.
- `seed_rule.py` — the v0.2 metric: winner determination + per-track cohesion.
  Fully specified in `CODEBOOK.md`.
- `tests/` — unit tests (synthetic hand-computed divisions, the layer-1
  dictionary, the fixture checker) + a self-consistency test on the real
  fixture: tallies recomputed from vote records must reconstruct the API
  headline counts exactly.
- `scripts/fetch_fixtures.py` — reproduces the fixtures from the live API.
- `scripts/verify_fixtures.py` — checks fixture integrity against the manifest.

```
$ python -m pytest tests/ -v
56 passed
$ python scripts/verify_fixtures.py
OK fixtures/term10-s1-v2-landslide.json 538f9709c664
OK fixtures/term10-s6-v14-tight.json  1fd2601aeef2
```

## How to participate (agent track)

1. Read `CODEBOOK.md` (the frozen v0.2 spec + reference prompt).
2. Run your model with the reference prompt on each fixture
   (`temperature=0`, JSON-only answer), saving the AGENTS.md files.
3. Score offline with the harness (deterministic, no network):
   `python scripts/sejmbench.py score --submission results/<model>-<date>/ --set public --out results/<model>-<date>.scorecard.json`
4. Open a PR with the per-fixture result files **and the scorecard**.
5. CI rescores from the raw responses and validates schema, set hash, prompt
   hash and metric version — any mismatch fails the PR. Accepted scorecards
   feed `results/leaderboard.jsonl` and the table below; values are never
   hand-edited. Parse rules and aggregation semantics:
   [docs/scorecard-schema.md](docs/scorecard-schema.md).

Layer 0.1 headline accuracy: winner exact match against the seed rule;
abstain, parse failure, refusal and a missing file all count as incorrect.
Layer 0.2: per-track `yes_share` / polarization MAE against the seed rule,
over items with a valid parsed answer. No network access during evaluation.

Human track: the same fixtures, same scorecard, no prompt template —
tell us your numbers, we are curious too.

<!-- LEADERBOARD:START -->
Only rows reproducible from accepted scorecards in `results/`; generated by
`python scripts/sejmbench.py leaderboard`, never hand-edited. `\*` = non-model
baseline. Layer-1 rows appear only after the §10 dictionary freezes.
Prediction-backtest numbers live in `results/backtest-*.md` and are never
merged with these rows.

| model | set | n | accuracy (95% CI) | yes_share MAE (95% CI) | polarization MAE (95% CI) | scorecard |
|---|---|---|---|---|---|---|
| baseline:majority-class\* | public | 2 | 1.0000 | 0.1855 | 0.0381 | [results/baseline-majority-class-public.scorecard.json](results/baseline-majority-class-public.scorecard.json) |
| baseline:random\* | public | 2 | 1.0000 | 0.5196 | 0.4731 | [results/baseline-random-public.scorecard.json](results/baseline-random-public.scorecard.json) |
<!-- LEADERBOARD:END -->

## Principles

1. **Official sources only.** Every number traces to api.sejm.gov.pl or the
   published voting record. Every fixture carries its sha256.
2. **Definitions before results.** Every metric has a written, frozen
   definition in `CODEBOOK.md` before anyone submits a score. Changes are
   versioned; scores are never compared across metric versions.
3. **No trivia, ever.** If a task can be solved by retrieval, it does not
   belong here.
4. **"Yes" and "on what" — not "against".** The benchmark measures positions,
   not teams. Framing follows that.
5. **Small and frozen beats big and moving.** Two pinned fixtures today are
   worth more than a planned thousand tomorrow.

## Known real-world wrinkles (documented, not hidden)

- **Club labels are not stable within a term.** Between our two fixtures
  (Nov 2023 → Feb 2024) the API label changed `Nowa_Lewica` → `Lewica`,
  `PSL` → `PSL-TD`, `Polska2050` → `Polska2050-TD`. Cross-division cohesion
  therefore needs a canonical club mapping — that is a v0.3 work item, and it
  is exactly the kind of boring detail that decides whether a benchmark is
  trustworthy.
- `inni` grouping (clubs with < 5 vote records) is scored out but tallied, so
  the reconstruction invariant still holds exactly.
- Absences are not moral failures; they are data. Layer 1 will need to treat
  a 4 a.m. procedural vote differently from a third reading.

## Roadmap (in order, each gate unlocks the next)

- **v0.3** — more divisions (target: 50 pinned, stratified across sittings and
  margins), canonical club mapping for term 10.
- **v0.5** — cohesion over time per club; first cross-model scoreboard.
- **v1** — the prediction backtest: history ≤ T in, division T+1 predicted,
  scored against the actual roll-call. This is the layer with real teeth:
  it is uncheatable by retrieval and directly comparable to Radoskop's
  backtesting of municipal resolutions.
- **v1+** — port the same machinery to municipal councils (Radoskop's home
  turf: 16k+ councils, curated roll-calls where available).

## License and governance

Code: MIT. Data: official public records of the Sejm of the Republic of
Poland — the MIT licence of this repository covers code, not data; see
[DATA_LICENSE.md](DATA_LICENSE.md). Project rules (errata policy, conflict
of interest, appeals) live in [GOVERNANCE.md](GOVERNANCE.md).

---

## Public dataset

The complete Sejm roll-call mirror produced by the pipeline below is published at:

**https://huggingface.co/datasets/patrykorwat/sejm-votings**

| config | rows | content |
|---|---|---|
| `votes` | 30,511,109 | individual votes per MP |
| `votings` | 66,427 | divisions with counts, majority, dates |
| `sittings` | 1,541 | sitting days with vote counts |
| `druki` | 21,498 | Sejm prints metadata + attachment urls |
| `druk_texts` | 40,516 | extracted print texts (99.9%) |

Provenance (sha256, per-row `source_url`, license) lives in the dataset card.
Source: official [Sejm API](https://api.sejm.gov.pl) only; nothing derived is added.

## Version axes

Four versions move independently. Cite the metric version with every score;
when in doubt, cite the scorecard hash (sha256 of the scorecard file as
accepted by CI; schema in issue #4).

| axis | where | current |
|---|---|---|
| benchmark (contract) | `CODEBOOK.md` | v0.3 |
| metric | `CODEBOOK.md` | v0.3 |
| dataset | HF dataset card | v0.4.0 |
| pipeline / harness | `VERSION` | 0.4.3 |
| scorecard schema | `docs/scorecard-schema.md` | 1.0 |
| release | git tags | — |

## Contamination policy

Sejm voting records are public and may be in model training data. A hidden
holdout can prevent tuning on the exact published items, but it cannot prove
that a model never saw the underlying records. The primary contamination
control is a **temporal holdout** (divisions newer than a model's declared
training cutoff); scorecards carry the evaluation date and the declared
cutoff (`unknown` when unverifiable). SejmBench never certifies a model as
"uncontaminated". See issue #5.

## Pipeline tooling (`scripts/`)

Operator scripts that regenerate or extend the mirror. They default to the
owner's ATX layout (`~/sejm-dump`, `~/.hf-token`) — adjust paths when running elsewhere.

| script | role |
|---|---|
| `dump_sejm_hf.py` | resumable dump: raw gz snapshots, votings/votes JSONL, sha256 manifest, Hub push |
| `build_extra.py` | rebuild `votings` with full fields, build `sittings` |
| `build_druki.py` | build `druki` from the `/prints` endpoint |
| `download_druki.py` | threaded, resumable attachment downloader |
| `extract_druki.py` | text extraction: pdftotext / python-docx / striprtf / odfpy |
| `fix_docs.py` | `.doc` backfill via catdoc |
| `push_druk.py` | schema-forced push helper |
| `run_druki.sh` | supervisor loop (restart-on-failure, resumable) |
