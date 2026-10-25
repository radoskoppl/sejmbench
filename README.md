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

## What is in the repo (v0.2)

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
- `tests/` — 7 unit tests (synthetic hand-computed divisions) + a
  self-consistency test on the real fixture: tallies recomputed from vote
  records must reconstruct the API headline counts exactly.
- `scripts/fetch_fixtures.py` — reproduces the fixtures from the live API.
- `scripts/verify_fixtures.py` — checks fixture integrity against the manifest.

```
$ python -m pytest tests/ -v
7 passed
$ python scripts/verify_fixtures.py
OK fixtures/term10-s1-v2-landslide.json 538f9709c664
OK fixtures/term10-s6-v14-tight.json  1fd2601aeef2
```

## How to participate (agent track)

1. Read `CODEBOOK.md` (the frozen v0.2 spec + reference prompt).
2. Run your model with the reference prompt on each fixture
   (`temperature=0`, JSON-only answer).
3. Open a PR adding your result under `results/` with the required metadata
   (model name and version, date, temperature, full raw output).
4. CI recomputes the metric and scores your submission against the invariants.

Scoring (v0.2): winner exact match (1/0), per-track `yes_share` MAE,
per-track polarization MAE. No network access during evaluation.

Human track: the same fixtures, same scorecard, no prompt template —
tell us your numbers, we are curious too.

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

## License

MIT. Data: official public records of the Sejm of the Republic of Poland.

---

## Public dataset

The complete Sejm roll-call mirror produced by the pipeline below is published at:

**https://huggingface.co/datasets/patrykorwat/sejm-votings**

| config | rows | content |
|---|---|---|
| `votes` | 9,591,905 | individual votes per MP |
| `votings` | 20,907 | divisions with counts, majority, dates |
| `sittings` | 1,541 | sitting days with vote counts |
| `druki` | 21,498 | Sejm prints metadata + attachment urls |
| `druk_texts` | 40,516 | extracted print texts (99.9%) |

Provenance (sha256, per-row `source_url`, license) lives in the dataset card.
Source: official [Sejm API](https://api.sejm.gov.pl) only; nothing derived is added.

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
