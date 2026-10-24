---
name: sejmbench
description: "Use when working on the SejmBench benchmark or the Sejm API."
version: 1.0.0
author: Radoskop
license: MIT
metadata:
  tags: [benchmark, sejm, llm, poland, roll-call]
---

# sejmbench

Work on **SejmBench** — a reproducible benchmark measuring how well LLMs
understand Polish parliamentary decision-making, starting from roll-call
data. This file lives in the sejmbench repo itself; all paths below are
relative to the repo root.

## What is in the repo (v0.2)

- `seed_rule.py` — winner determination + per-club cohesion
  (`yes_share = YES/(YES+NO+ABSTAIN)`, `polarization = 1 - |YES-NO|/n`).
- `CODEBOOK.md` — frozen v0.2 definitions + reference prompt; scores are
  never compared across metric versions.
- `fixtures/` — real divisions from the official Sejm API with sha256 pins in
  `fixtures/manifest.json` (landslide 458:0; tight 224:196).
- `AGENTS.md` — submission contract: PR to `results/`, temperature 0, no
  tools, no network.
- `docs/RESEARCH-DECISION-SYSTEMS.md` — prior-art review (arXiv) behind the
  design.

## Sejm API (api.sejm.gov.pl) — verified recipes

- Sitting index: `GET /sejm/term{N}/votings/{sitting}` → list with
  `votingNumber`, `title`, `yes`, `no`, `abstain`, `totalVoted`.
- Division detail: `GET /sejm/term{N}/votings/{sitting}/{votingNumber}` →
  `votes` is a **list** of records
  `{MP, club, firstName, lastName, secondName, vote}`,
  `vote` ∈ `YES`/`NO`/`ABSTAIN`/`ABSENT`.
- The key field is `votingNumber` (not `votingNo`).
- The docs page at `/` loads endpoint listings dynamically (grepping the HTML
  yields nothing); `openapi.json` returns 404. Probing real paths beats
  hunting for a spec.
- Election divisions (Marshal elections etc.) carry
  `yes = no = abstain = 0` even though votes were cast — the headline counters
  do not apply to non-legislative voting.
- Club labels are **not stable within a term** (Nov 2023: `Nowa_Lewica`,
  `PSL`, `Polska2050` → Feb 2024: `Lewica`, `PSL-TD`, `Polska2050-TD`).
  Cross-division work needs a canonical club mapping — curate it by hand,
  never regex.

## Benchmark principles (non-negotiable)

1. Official sources only; every fixture carries a sha256.
2. Definitions frozen before results; versioned codebook.
3. Zero trivia — if a task is solvable by retrieval, it does not belong.
4. Measure positions ("for what", "how"), not camps ("who blocked").
5. Always report next to the club-line baseline: an LLM must beat
   "always vote with your club" to be news (prior art: arXiv 1805.08182).

## Roadmap

- v0.3 — 50 stratified pinned fixtures (margin × division type); canonical
  club mapping for term 10.
- v0.5 — cohesion over time; first cross-model scoreboard.
- v1 — the prediction backtest: history ≤ T in, division T+1 predicted,
  scored against the real roll-call (retrieval-proof).
