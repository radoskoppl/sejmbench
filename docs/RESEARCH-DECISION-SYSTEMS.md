# Prior art & research note: decision systems, legislative voting, LLM agents

Research note (2026-10-24), compiled from live arXiv API queries before the
v0.3 design work. Every entry has a real arXiv ID; abstracts were read from
the API, not guessed. Grouped by what they imply for SejmBench.

## 1. Roll-call vote prediction — the direct ancestors of our layer 3

| arXiv | Paper | What it does | Implication for SejmBench |
|---|---|---|---|
| 2412.07144 | **Political Actor Agent: Simulating Legislative System for Roll Call Votes Prediction with Large Language Models** (2024) | LLM agents simulating a legislative system, evaluated on roll-call vote prediction | **Closest existing work to layer 3.** They predict votes from role-played agents; our angle: a *frozen, hash-pinned, community-owned benchmark* with a written codebook, PL data, and mechanical scoring. Cite and position against. |
| 2505.12535 | Framework of Voting Prediction of Parliament Members (2025) | General framework for predicting parliament members' votes | Confirms vote prediction is an active task class; no PL Sejm data involved. |
| 1805.08182 | Party Matters: Enhancing Legislative Embeddings with Author Attributes for Vote Prediction (2018) | Classic pre-LLM baseline: author/committee attributes + embeddings | Establishes the honest baseline layer 3 must beat: party-line prediction is strong. Any LLM claim must be compared to "always vote with your club" — cheap, hard to beat. |
| 2505.00006 | Toward a digital twin of U.S. Congress (2025) | Congressperson-specific LLMs on daily-updated Twitter corpus; indistinguishability test | "Digital twin" framing validated in the literature; note their fidelity metric (indistinguishability) vs our task metrics. |

## 2. Ideology scaling / ideal points — candidate metric families for v0.5+

| arXiv | Paper | Implication |
|---|---|---|
| 2405.02472 | **Semantic Scaling: Bayesian Ideal Point Estimates with Large Language Models** (2024) | LLM classifies stances, then item response theory (IRT) scales actors. Directly relevant: IRT on roll-calls could give SejmBench a *continuum* metric (v0.5+), not just cohesion. |
| 2511.13238 | Computational Measurement of Political Positions: Review of Text-Based Ideal Point Estimation (2025) | Systematic review of CT-IPE; the entry point when designing any scaling layer; also a map of failure modes. |
| 2512.11610 | Euclidean Ideal Point Estimation via Distance-Based Bipartite Network Models (2025) | Bipartite-network view of MPs × votes; alternative to DW-NOMINATE-style scaling. |
| 2405.07320 | L(u)PIN: LLM-based Political Ideology Nowcasting (2024) | LLM nowcasting of ideology from sparse data — relevant to mid-term membership changes (our v0.3 club-mapping problem has a known methodological neighborhood). |

## 3. LLM agents in legislatures & collective decision-making

| arXiv | Paper | Implication |
|---|---|---|
| 2406.18702 | **Simulating The U.S. Senate: An LLM-Driven Agent Approach to Modeling Legislative Behavior and Bipartisanship** (2024) | Committee-level agent debate; bipartisan shifts under perturbation. Supports our thesis that agent-vs-roll-call comparison is meaningful; their evaluation is qualitative/small-N — a benchmark gap we fill. |
| 2502.09369 | Language Agents as Digital Representatives in Collective Decision-Making (2025) | Agents as *proxies* in group choice; mechanism-design framing. Our layer 3 scores exactly this proxy quality, on real data. |
| 2410.08345 | Large Legislative Models: Towards Efficient AI Policymaking in Economic Simulations (2024) | LLMs as sample-efficient policymakers in simulation; policy quality ≠ vote prediction, but the same discipline of frozen eval applies. |
| 2502.08691 | AgentSociety: Large-Scale Simulation of LLM-Driven Generative Agents (2025) | Infrastructure lessons for large agent societies (relevant if SejmBench grows into committee/society simulation). |
| 2503.09639 | Can A Society of Generative Agents Simulate Human Behavior... Vaccine Hesitancy (2025) | Society-simulation methodology and its pitfalls; cautionary baseline for overclaiming. |

## 4. Nearest benchmark neighbors — where the gap is

| arXiv | Paper | What it covers | The gap SejmBench fills |
|---|---|---|---|
| 2509.16264 | ParlAI Vote: Web Platform for Analyzing Gender and Political Bias in LLMs (2025) | Platform analyzing LLM political bias | Bias audits, not decision understanding; no roll-call tasks, no PL Sejm. |
| 2606.12922 | Polar: A Benchmark for Evaluating Political Bias in LLMs (2026) | Political bias benchmark | Same field (bias), different task family. |
| 2502.14122 | Benchmarking LLMs for Political Science: A United Nations Perspective (2025) | Political-science tasks on UN data | Confirms appetite for political-science benchmarks; UN votes ≠ national roll-calls with full per-MP records. |
| 2407.18008 | GermanPartiesQA (2024) | Party-alignment QA, sycophancy | Alignment quizzes, not mechanical decision scoring. |
| 2505.19558 | PoliCon: LLMs on Diverse Political Consensus Objectives (2025) | Consensus objectives evaluation | Normative/consensus framing vs our descriptive, gradeable tasks. |

**The niche in one line:** mechanical, retrieval-proof, hash-pinned tasks on
official per-MP roll-call data, in Polish, with a prediction backtest — no
existing benchmark occupies that square.

## 5. Design lessons we adopt (from the above)

1. **Baseline discipline (1805.08182):** layer 3 results will always be shown
   next to the club-line baseline; an LLM beating a majority-rule heuristic is
   the real news, otherwise it is noise.
2. **Frozen data (this repo):** Political Actor Agent and Senate-simulation
   works evaluate on data snapshots nobody can re-pull; sha256-pinned fixtures
   make scores comparable across labs and models.
3. **Codebook before scores (CODEBOOK.md):** reviews like 2511.13238 exist
   precisely because the field grew definitions-after-results; we invert that
   order.
4. **IRT as the next metric family (2405.02472):** when cohesion per division
   is mastered (v0.2–0.5), scale actors on a continuum and test whether LLM
   -inferred positions track IRT positions estimated from the same roll-calls.

## Method

Queries against `export.arxiv.org/api/query` (2026-10-24): "legislative vote
prediction", "roll call" + prediction + Congress, "ideal point estimation",
"political ideology" + embeddings, LLM + agents + legislative, "collective
decision-making" + agents, "vote prediction", LLM + political + benchmark,
parliamentary + debate + LLM, "legislative outcome" + prediction, AgentSociety
/ generative agents. Abstracts for the key IDs were read in full from the API.
No citation below is from memory — each is verifiable at
`https://arxiv.org/abs/<id>`.
