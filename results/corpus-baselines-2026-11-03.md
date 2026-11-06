# Corpus baselines (frozen population, issue #11)

Baselines computed by the corpus-aware harness (`--set full|term10`,
scorecard schema 1.3 with the `temporal_split` block, issue #5) on the frozen
evaluation population. Reproduce with:

```
python scripts/sejmbench.py baselines --set term10 --temporal-cutoff 2026-01-01   # or --set full
```

Corpus scorecards are regenerable artifacts and stay out of git; the numbers
below are pinned by the GT hash. kNN / carry_last are predictive-backtest
constructs and are reported separately (see `results/backtest-*.md`) — they
are not layer-0.1/0.2 computation baselines.

## term-10 (n = 5,137; gt_sha256 0f984d52e1ec…)

| row | winner acc [95% CI] | yes_share MAE | polarization MAE |
|---|---|---|---|
| majority-class (predicts modal winner "yes") | 0.519 [0.506, 0.533] | 0.510 | 0.098 |
| random (seeded uniform) | 0.489 [0.476, 0.503] | 0.483 | 0.481 |
| constant-mean (predict population means) | — | 0.478 | 0.165 |

Temporal split (issue #5, cutoff 2026-01-01; post-cutoff = 2026 sittings,
n=1,917 — all of them term-10):

| row | pre-cutoff (n=3,220) | post-cutoff (n=1,917) |
|---|---|---|
| majority-class | 0.5174 [0.5003, 0.5345] | 0.5227 [0.5003, 0.5451] |
| random | 0.4913 [0.4739, 0.5090] | 0.4857 [0.4632, 0.5081] |

## full corpus (n = 66,104; gt_sha256 bdc320baed87…)

| row | winner acc [95% CI] | yes_share MAE | polarization MAE |
|---|---|---|---|
| majority-class (predicts modal winner "no") | 0.611 [0.607, 0.615] | 0.528 | 0.105 |
| random (seeded uniform) | 0.498 [0.494, 0.502] | 0.472 | 0.463 |
| constant-mean (predict population means) | — | 0.459 | 0.153 |

Temporal split (issue #5, cutoff 2026-01-01; post-cutoff = 2026 sittings,
n=1,917 — the same divisions as the term-10 post-cutoff set):

| row | pre-cutoff (n=64,187) | post-cutoff (n=1,917) |
|---|---|---|
| majority-class | 0.6136 [0.6098, 0.6172] | 0.5227 [0.5003, 0.5451] |
| random | 0.4986 [0.4948, 0.5025] | 0.4857 [0.4632, 0.5081] |

The constant-mean row is the aggregate-level computation from
`docs/population/population-v0.5.json` (mean track yes_share / polarization);
it is the strongest trivial cohesion baseline and the bar a model must beat
on MAE. Note the winner-task asymmetry: term-10 is agenda-heavy (p_yes high →
"yes" modal), the full corpus is rejection-heavy ("no" modal).
