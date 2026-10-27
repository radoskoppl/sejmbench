# Backtest — full corpus, terms 3–10 (1997–2026)

- date: 2026-10-26 · operator: agent (Hermes), owner review pending
- harness: `scripts/backtest_layers.py` v0.4.2 (memory-compact load,
  dormant-club decay, uniform size weighting, empty-text guard)
- data: 66,345 divisions with roll-call votes, built by
  `scripts/build_divisions.py` from the complete dump; 61 further divisions
  have no vote rows in the API (absent from the input); 6 have no indexable
  text and are skipped by the kNN index
- protocol: chronological, warmup 60, history strictly < T, no leakage;
  club continuity mapped for term 10 only (cross-term canonical club
  mapping is still a roadmap item)
- harness note: results under harness v0.4.2 are not directly comparable
  to the term-10-only numbers from 2026-10-25 (harness v0.4.0/v0.4.1) —
  dormancy decay and uniform size weighting changed the aggregation

## Results (66,044 scored divisions)

| method | winner acc | yes_share MAE |
|---|---|---|
| always_yes | 0.388 | — |
| club_mean | 0.569 | 0.449 |
| carry_last | 0.688 | 0.287 |
| ewma | 0.612 | 0.399 |
| affinity | 0.612 | 0.419 |
| knn (titles, k=5) | 0.707 | 0.303 |
| blend | 0.700 | 0.359 |

## Per-term winner accuracy

| term | n | carry_last | knn |
|---|---|---|---|
| 3 | 11,729 | 0.644 | 0.661 |
| 4 | 13,535 | 0.674 | 0.680 |
| 5 | 3,412 | 0.669 | 0.688 |
| 6 | 8,403 | 0.728 | 0.732 |
| 7 | 6,291 | 0.718 | 0.769 |
| 8 | 8,154 | 0.731 | 0.756 |
| 9 | 9,383 | 0.687 | 0.681 |
| 10 | 5,137 | 0.671 | 0.751 |

## Reading

1. The title-retrieval layer generalizes across 30 years and 8 terms: kNN
   beats carry_last in 7 of 8 terms (only term 9 flips, by 0.006). The
   edge is largest where the agenda is most distinctive (term 10 +0.080,
   term 7 +0.051) and smallest in the oldest terms (+0.002–0.017).
2. On the full corpus the two metrics disagree about the best
   content-free method: kNN wins winner accuracy (0.707), carry_last wins
   yes_share MAE (0.287 vs 0.303). Winner accuracy is the headline
   metric; the MAE crossover should be revisited once layer 1 (division
   types) splits the pool — vote-share dynamics likely differ between
   substantive and procedural divisions.
3. club_mean gains a lot from the long history (0.569 vs 0.477 in the
   term-10-only run) — long-run club means carry real information about
   persistent blocks in the chamber.
4. Cross-term club labels are not canonically mapped (the term-10
   continuity map applies only to term 10); dormant-club decay keeps
   defunct labels from polluting expected counts. A canonical cross-term
   club mapping is the next data-quality step before cross-term
   comparisons become apples-to-apples.

Bars for the full corpus (harness v0.4.2): winner accuracy **kNN 0.707**,
yes_share MAE **carry_last 0.287** — a new method should beat both.

Reproduce: `python3 scripts/build_divisions.py --dump ~/sejm-dump --out
divisions.jsonl && python3 scripts/backtest_layers.py divisions.jsonl`
