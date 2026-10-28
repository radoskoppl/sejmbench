# SejmBench CODEBOOK — v0.2 (frozen)

This document is the contract. Every submitted score is graded against the
definitions here. Definitions change only via version bump (`0.2` → `0.3`),
and scores are never compared across versions.

## 1. Data model

**Division** — one roll-call vote in the Sejm, serialized exactly as returned
by the Sejm API voting detail endpoint
(`https://api.sejm.gov.pl/sejm/term{term}/votings/{sitting}/{votingNumber}`).
Fields used by v0.2: `term`, `sitting`, `votingNumber`, `title`, `date`,
`yes`, `no`, `abstain`, `totalVoted`, `votes` (list).

**Vote record** — one element of `votes`:
`{MP, club, firstName, lastName, secondName, vote}` where `vote` is one of
`YES`, `NO`, `ABSTAIN`, `ABSENT`.

**Club** — the `club` string on the vote record, taken verbatim. v0.2 does
not normalize club labels (see §6).

**Track** — a club label appearing on **≥ 5 vote records** in the division.
Clubs with fewer records are grouped as `inni`.

**Active vote** — `YES`, `NO`, or `ABSTAIN`. `ABSENT` is never an active vote.

## 2. Metric v0.2

Per track `t` with active votes `n = YES + NO + ABSTAIN` (n ≥ 5):

- `yes_share = YES / n` — abstention counts in the denominator. Stated openly:
  an abstention is half a dissent, not a hidden yes.
- `polarization = 1 - |YES - NO| / n` — `0` = unanimous (all active votes on
  one side), `1` = exact 50/50 split. `ABSTAIN` dilutes the split (reduces
  polarization) but never inflates it. Examples: 6 yes / 0 no / 0 abstain → 0.0;
  3 yes / 3 no → 1.0; 4 yes / 0 no / 6 abstain → 0.6.

Overall (tracks only): `overall_polarization` — same formula over summed
track tallies.

## 3. Seed rule (winner determination)

The seed with the **majority of active votes** (summed over tracks) wins the
division: `YES` if `YES > NO`, `NO` if `NO > YES`.

**Tie-break (including 0:0):** the earlier seed wins; the `YES` seed is
defined as the earlier seed. Deterministic, no randomness.

This tie-break is a scorer convention of this benchmark, not an
interpretation of the legal outcome of a vote. A 0:0 resolution must never
be reported as "the motion passed".

Reported alongside: `margin` (seed tracks only) and `margin_all`
(all vote records, including `inni`).

## 4. Invariants (self-consistency; CI enforces)

For every division:

1. `seed_totals.YES + inni_totals.YES == yes` (API headline)
2. `seed_totals.NO + inni_totals.NO == no`
3. `seed_totals.ABSTAIN + inni_totals.ABSTAIN == abstain`
4. `n_active + inni active == totalVoted`
5. `0.0 <= polarization <= 1.0` for every track and overall

A submission whose tallies break these is rejected before scoring.

## 5. Reference prompt (agent track, v0.2)

```
You are analyzing a roll-call division (głosowanie imienne) of the Sejm
of the Republic of Poland. Each line below is one MP: club | name | vote,
where vote is YES / NO / ABSTAIN / ABSENT.

{VOTE_RECORDS}

Answer ONLY with a JSON object:
{
  "winner": "yes" | "no",
  "tracks": [
    {"club": "<label>", "yes_share": <float>, "polarization": <float>}
  ]
}
Rules:
- Include exactly the clubs with at least 5 active votes (YES/NO/ABSTAIN).
- yes_share = YES / (YES + NO + ABSTAIN) for that club.
- polarization = 1 - |YES - NO| / (YES + NO + ABSTAIN).
```

Evaluation conditions: temperature 0, no tools, no network, single response.
Raw model output is committed alongside the parsed JSON.

## 6. Known issues (carried openly)

- **Club label instability.** Within term 10 the API label changed between
  November 2023 and February 2024: `Nowa_Lewica` → `Lewica`, `PSL` → `PSL-TD`,
  `Polska2050` → `Polska2050-TD`. v0.2 scores divisions in isolation, so this
  does not affect any v0.2 number. Layer 2 (cohesion over time) is blocked on
  a canonical club mapping — v0.3 work item, curated by hand, not regex.
- Election divisions (e.g. Marshal elections) have `yes = no = abstain = 0`
  in the API even though 459 votes were cast: the headline counters do not
  apply to non-legislative voting. v0.2 fixtures avoid these; layer 1 must
  define vote-type handling explicitly.

## 7. What is deliberately NOT in v0.2

- No sentiment or justification analysis.
- No weighting of votes by importance (that requires vote-type classification
  — layer 1).
- No prediction (layer 3). Do not submit predictions against v0.2; they will
  not be scored.

## 8. Statistical protocol (added 2026-10-27; contract for v0.3+)

These rules do not alter any v0.2 metric definition.

1. Headline accuracy and MAE are reported with a bootstrap 95% confidence
   interval (resample divisions with replacement, >= 10,000 replicates,
   fixed documented seed).
2. Comparing two scorecards requires a paired bootstrap over the shared
   division set; differences inside the CI are not ranked.
3. A bucket or cell with fewer than the minimum count defined in the release
   PR is reported but not used in aggregates.
4. No composite score across layers or metric versions. A composite requires
   a written aggregation rule in this CODEBOOK first.
5. `n` is reported with every number: scored, excluded (with reason),
   abstained, parse failures, refusals.

## 9. Model input and contamination contract (added 2026-10-27)

1. Layer 0.1/0.2 input is the full vote record list (§5). The task is
   computation on provided data; retrieval is blocked by construction
   because the answer is derivable from the input alone.
2. Every new layer must freeze, in this CODEBOOK and before fixtures ship:
   which fields the model sees, which are hidden, and a leakage check run in
   CI (no string in the input deterministically reveals the label).
3. The reference prompt is versioned by its hash; the hash is recorded in
   the scorecard.
4. Abstain, parse failure and refusal count as incorrect for headline
   accuracy and are reported separately.
5. Scorecards carry the evaluation date and the model's declared training
   cutoff (`unknown` when unverifiable). SejmBench never certifies a model
   as "uncontaminated"; the temporal holdout (issue #5) is the primary
   contamination control.
